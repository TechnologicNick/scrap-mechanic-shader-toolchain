"""Compile reconstructed HLSL modules and serialize a shaders.sbc cache."""

from __future__ import annotations

import hashlib
import difflib
import json
import os
import re
import struct
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from .compare import compare_bytecodes, normalized_assembly
from .hlsl import (
    hlsl_token_sha256,
    module_variants,
    resolve_local_includes,
    semantic_module_variants,
)
from .reconstruct import ToolchainError, verify_output
from .reflect import ShaderReflector
from .sbc import D3DCompiler, lz4_compress_literals, parse_cache, parse_payload


PROFILES = {"vertex": "vs_5_0", "pixel": "ps_5_0", "compute": "cs_5_0"}
DIAGNOSTIC = re.compile(r"\b((?:error|warning) X\d+:.*)")


def stable_diagnostic(message: str) -> str:
    """Remove machine-specific source paths from D3DCompile diagnostics."""
    diagnostics = []
    for line in message.replace("\x00", "").splitlines():
        match = DIAGNOSTIC.search(line)
        if match:
            diagnostics.append(match.group(1))
    return "\n".join(diagnostics) or "D3DCompile failed without a diagnostic"


def meaningfully_edited(shader: dict[str, Any], source: str) -> bool:
    baseline = shader.get("hlsl_token_sha256")
    if not baseline:
        raise ToolchainError(
            f"{shader['selector']} has no HLSL fingerprint; rerun sm-shaders reconstruct"
        )
    return hlsl_token_sha256(source) != baseline


def select_shader_source(
    shader: dict[str, Any],
    raw_source: str,
    semantic_source: str | None,
    *,
    recompile_all: bool,
) -> tuple[str | None, str, str]:
    """Choose exact bytecode, raw HLSL, or readable semantic HLSL for a variant."""
    raw_changed = meaningfully_edited(shader, raw_source)
    semantic_changed = False
    if semantic_source is not None:
        baseline = shader.get("semantic_hlsl_token_sha256")
        if not baseline:
            raise ToolchainError(
                f"{shader['selector']} has semantic HLSL but no semantic fingerprint"
            )
        semantic_changed = hlsl_token_sha256(semantic_source) != baseline
    if raw_changed and semantic_changed:
        raise ToolchainError(
            f"{shader['selector']}: both raw and semantic HLSL were edited; "
            "keep only one representation changed"
        )
    if recompile_all:
        if semantic_source is not None:
            return semantic_source, "semantic", "research-semantic"
        return raw_source, "raw", "research-raw"
    if semantic_changed:
        return semantic_source, "semantic", "edited-semantic"
    if raw_changed:
        return raw_source, "raw", "edited-raw"
    return None, "exact", "unchanged-exact"


def serialize_payload(manifest: dict[str, Any], bundle: bytes) -> bytes:
    shaders = manifest["shaders"]
    jobs = manifest["jobs"]
    resource_ids = manifest["resource_ids"]
    if len(shaders) > 0xFFFF or len(resource_ids) > 0xFFFF:
        raise ToolchainError("cache table exceeds its 16-bit count field")

    output = bytearray(struct.pack("<H", len(shaders)))
    for shader in shaders:
        output.extend(struct.pack("<Q", int(shader["shader_key"], 16)))
    output.extend(struct.pack("<I", len(jobs)))
    for job in jobs:
        output.extend(
            struct.pack("<QH", int(job["job_key"], 16), job["shader_index"])
        )
    output.extend(struct.pack("<H", len(resource_ids)))
    for resource_id in resource_ids:
        raw = bytes.fromhex(resource_id)
        if len(raw) != 16:
            raise ToolchainError(f"resource ID is not 16 bytes: {resource_id}")
        output.extend(raw)

    output.extend(struct.pack("<Q", len(bundle)))
    output.extend(bundle)
    for index in range(len(shaders)):
        output.extend(struct.pack("<H", index))
    output.extend(bytes(shader["stage_value"] for shader in shaders))
    for shader in shaders:
        output.extend(struct.pack("<H", len(shader["resource_id_indices"])))
    descriptors = [shader["descriptor"].encode("utf-8") for shader in shaders]
    for descriptor in descriptors:
        if len(descriptor) > 0xFFFF:
            raise ToolchainError("shader descriptor exceeds its 16-bit length field")
        output.extend(struct.pack("<H", len(descriptor)))
    for shader, descriptor in zip(shaders, descriptors, strict=True):
        for resource_index in shader["resource_id_indices"]:
            output.extend(struct.pack("<H", resource_index))
        output.extend(descriptor)
    return bytes(output)


def serialize_cache(payload: bytes, shader_cache_version: int = 1) -> bytes:
    compressed = lz4_compress_literals(payload)
    return (
        struct.pack("<4I", 1, 4, len(compressed), len(payload))
        + struct.pack("<I", shader_cache_version)
        + compressed
    )


def build_cache(
    corpus: Path,
    output: Path,
    *,
    recompile_all: bool = False,
    allow_dxbc_fallback: bool = False,
    allow_interface_changes: bool = False,
    jobs: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Losslessly rebuild a corpus, compiling only meaningfully edited branches."""
    report_path = output.with_suffix(output.suffix + ".build.json")
    diff_path = output.with_suffix(output.suffix + ".diffs")
    for target in (output, report_path, diff_path):
        if target.exists():
            raise ToolchainError(f"output path already exists: {target}")
    if allow_dxbc_fallback and not recompile_all:
        raise ToolchainError("--allow-dxbc-fallback requires --recompile-all")
    verify_output(corpus, verify_hlsl_fingerprints=False)
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("corpus_format_version") != 2:
        raise ToolchainError(
            "corpus has no v2 HLSL fingerprints; rerun sm-shaders reconstruct"
        )
    shaders = manifest["shaders"]
    modules: dict[str, dict[str, str]] = {}
    for source_name in {shader["source_name"] for shader in shaders}:
        path = corpus / "hlsl" / f"{source_name}.hlsl"
        modules[source_name] = module_variants(
            path.read_text(encoding="utf-8"),
            {
                shader["selector"]: shader["defines"]
                for shader in shaders
                if shader["source_name"] == source_name
            },
        )
    semantic_modules: dict[str, dict[str, str]] = {}
    semantic_paths = {
        shader["semantic_hlsl_path"]
        for shader in shaders
        if shader.get("semantic_hlsl_path")
    }
    semantic_root = corpus / "semantic"
    for relative_path in semantic_paths:
        path = corpus / relative_path
        variants = semantic_module_variants(
            path.read_text(encoding="utf-8"),
            {
                shader["selector"]: shader["defines"]
                for shader in shaders
                if shader.get("semantic_hlsl_path") == relative_path
            },
        )
        semantic_modules[relative_path] = {
            selector: resolve_local_includes(source, path, semantic_root)
            for selector, source in variants.items()
        }

    requested_workers = jobs if jobs is not None else (os.cpu_count() or 1)
    if requested_workers < 1:
        raise ToolchainError("worker count must be at least one")
    thread_state = threading.local()
    bytecodes: list[bytes | None] = [None] * len(shaders)
    build_records: list[dict[str, Any] | None] = [None] * len(shaders)
    compile_tasks: list[tuple[int, dict[str, Any], str, bytes, str, str, str]] = []

    for index, shader in enumerate(shaders):
        selector = shader["selector"]
        try:
            raw_source = modules[shader["source_name"]][selector]
        except KeyError as error:
            raise ToolchainError(f"missing HLSL branch {selector}") from error
        semantic_source = None
        semantic_path = shader.get("semantic_hlsl_path")
        if semantic_path:
            try:
                semantic_source = semantic_modules[semantic_path][selector]
            except KeyError as error:
                raise ToolchainError(f"missing semantic HLSL branch {selector}") from error
        source, representation, mode = select_shader_source(
            shader,
            raw_source,
            semantic_source,
            recompile_all=recompile_all,
        )
        exact_path = corpus / shader["dxbc_path"]
        exact_bytecode = exact_path.read_bytes()
        if source is None:
            bytecodes[index] = exact_bytecode
            build_records[index] = {
                "selector": selector,
                "mode": mode,
                "source_representation": representation,
                "compiled": False,
                "hlsl_token_sha256": hlsl_token_sha256(raw_source),
                "assembly_exact": True,
                "abi_compatible": True,
            }
        else:
            current_fingerprint = hlsl_token_sha256(source)
            compile_tasks.append(
                (
                    index,
                    shader,
                    source,
                    exact_bytecode,
                    current_fingerprint,
                    representation,
                    mode,
                )
            )

    worker_count = min(requested_workers, len(compile_tasks)) if compile_tasks else 0

    def compile_one(
        index: int,
        shader: dict[str, Any],
        source: str,
        exact_bytecode: bytes,
        current_fingerprint: str,
        representation: str,
        mode: str,
    ) -> tuple[int, bytes, dict[str, Any], str | None]:
        profile = PROFILES.get(shader["stage"])
        if profile is None:
            raise ToolchainError(f"unsupported shader stage: {shader['stage']}")
        selector = shader["selector"]
        compiler = getattr(thread_state, "compiler", None)
        if compiler is None:
            compiler = D3DCompiler()
            thread_state.compiler = compiler
            thread_state.reflector = ShaderReflector()
        try:
            bytecode = compiler.compile(source, shader["entry_point"], profile)
        except RuntimeError as error:
            if not recompile_all or not allow_dxbc_fallback:
                raise ToolchainError(f"{selector}: {error}") from error
            return index, exact_bytecode, {
                "selector": selector,
                "mode": "recompile-fallback",
                "requested_mode": mode,
                "source_representation": representation,
                "compiled": False,
                "hlsl_token_sha256": current_fingerprint,
                "error": stable_diagnostic(str(error)),
                "assembly_exact": True,
                "abi_compatible": True,
            }, None

        comparison, baseline_assembly, candidate_assembly = compare_bytecodes(
            exact_bytecode, bytecode, compiler, thread_state.reflector
        )
        if not comparison["abi_compatible"] and not allow_interface_changes:
            changed = ", ".join(comparison["abi_differences"])
            raise ToolchainError(
                f"{selector}: edited shader changes runtime ABI sections: {changed}"
            )
        record = {
            "selector": selector,
            "mode": mode,
            "source_representation": representation,
            "compiled": True,
            "hlsl_token_sha256": current_fingerprint,
            **comparison,
        }
        difference = None
        if not recompile_all and not comparison["assembly_exact"]:
            difference = "\n".join(
                difflib.unified_diff(
                    baseline_assembly.splitlines(),
                    candidate_assembly.splitlines(),
                    fromfile="baseline",
                    tofile="candidate",
                    lineterm="",
                )
            ) + "\n"
        return index, bytecode, record, difference

    assembly_diffs: dict[str, str] = {}
    if compile_tasks:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(compile_one, *task) for task in compile_tasks]
            for completed, future in enumerate(as_completed(futures), start=1):
                index, bytecode, record, difference = future.result()
                bytecodes[index] = bytecode
                build_records[index] = record
                if difference:
                    assembly_diffs[record["selector"]] = difference
                if progress and (
                    completed % 100 == 0 or completed == len(compile_tasks)
                ):
                    progress(completed, len(compile_tasks))

    compiled_bytecodes = [bytecode for bytecode in bytecodes if bytecode is not None]
    if len(compiled_bytecodes) != len(shaders):
        raise ToolchainError("one or more shader compilation results are missing")
    completed_records = [record for record in build_records if record is not None]
    if len(completed_records) != len(shaders):
        raise ToolchainError("one or more shader build records are missing")

    compiler = D3DCompiler()
    bundle = compiler.compress(compiled_bytecodes)
    payload = serialize_payload(manifest, bundle)
    cache_version = manifest["summary"].get("shader_cache_version", 1)
    cache_data = serialize_cache(payload, cache_version)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_bytes(cache_data)
    try:
        header, validated_payload = parse_cache(temporary)
        metadata, validated_bundle = parse_payload(validated_payload)
        extracted = compiler.extract(validated_bundle, len(shaders))
        if metadata["shader_count"] != len(shaders) or len(extracted) != len(shaders):
            raise ToolchainError("rebuilt cache failed shader-count validation")
        if metadata["jobs"] != manifest["jobs"]:
            raise ToolchainError("rebuilt cache job table differs from the manifest")
        if metadata["resource_ids"] != manifest["resource_ids"]:
            raise ToolchainError("rebuilt cache resource IDs differ from the manifest")
        compared_fields = (
            "shader_key",
            "bundle_index",
            "stage_value",
            "descriptor",
            "resource_id_indices",
        )
        for actual, expected in zip(metadata["shaders"], shaders, strict=True):
            if any(actual[field] != expected[field] for field in compared_fields):
                raise ToolchainError(
                    f"rebuilt metadata differs for shader {expected['index']}"
                )
        for index, record in enumerate(completed_records):
            if record["mode"] == "unchanged-exact" and normalized_assembly(
                extracted[index], compiler
            ) != normalized_assembly(compiled_bytecodes[index], compiler):
                raise ToolchainError(
                    f"{record['selector']}: lossless assembly validation failed"
                )
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()

    mode_counts = {
        mode: sum(record["mode"] == mode for record in completed_records)
        for mode in sorted({record["mode"] for record in completed_records})
    }
    summary = {
        **header,
        "modes": mode_counts,
        "compiled_count": sum(record["compiled"] for record in completed_records),
        "fallback_count": mode_counts.get("recompile-fallback", 0),
        "unchanged_exact_count": mode_counts.get("unchanged-exact", 0),
        "shader_count": len(shaders),
        "bundle_size": len(bundle),
        "jobs": worker_count,
        "output_sha256": hashlib.sha256(cache_data).hexdigest(),
    }
    report = {"summary": summary, "shaders": completed_records}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if assembly_diffs:
        diff_path.mkdir(parents=True, exist_ok=False)
        for selector, difference in sorted(assembly_diffs.items()):
            (diff_path / f"{selector}.diff").write_text(
                difference, encoding="utf-8", newline="\n"
            )
    return {
        **summary,
        "report": report_path.name,
        "diff_directory": diff_path.name if assembly_diffs else None,
    }
