"""Compile reconstructed HLSL modules and serialize a shaders.sbc cache."""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from .reconstruct import ToolchainError, verify_output
from .sbc import D3DCompiler, lz4_compress_literals, parse_cache, parse_payload


PROFILES = {"vertex": "vs_5_0", "pixel": "ps_5_0", "compute": "cs_5_0"}
SELECTOR_LINE = re.compile(
    r"(?m)^#(?:if|elif) defined\((SM_SHADER_[0-9A-F]{16})\)\r?$"
)
END_MODULE = re.compile(r"(?m)^#endif\r?$")
DIAGNOSTIC = re.compile(r"\b((?:error|warning) X\d+:.*)")


def module_variants(source: str) -> dict[str, str]:
    """Extract selector branches from one generated module."""
    matches = list(SELECTOR_LINE.finditer(source))
    variants: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            closing = END_MODULE.search(source, start)
            if not closing:
                raise ToolchainError("generated HLSL module has no closing #endif")
            end = closing.start()
        variants[match.group(1)] = source[start:end].strip() + "\n"
    return variants


def stable_diagnostic(message: str) -> str:
    """Remove machine-specific source paths from D3DCompile diagnostics."""
    diagnostics = []
    for line in message.replace("\x00", "").splitlines():
        match = DIAGNOSTIC.search(line)
        if match:
            diagnostics.append(match.group(1))
    return "\n".join(diagnostics) or "D3DCompile failed without a diagnostic"


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
    allow_dxbc_fallback: bool = True,
    jobs: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Compile a reconstructed corpus and atomically write a validated cache."""
    if output.exists():
        raise ToolchainError(f"output path already exists: {output}")
    verify_output(corpus)
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    shaders = manifest["shaders"]
    modules: dict[str, dict[str, str]] = {}
    for source_name in {shader["source_name"] for shader in shaders}:
        path = corpus / "hlsl" / f"{source_name}.hlsl"
        modules[source_name] = module_variants(path.read_text(encoding="utf-8"))

    worker_count = jobs if jobs is not None else (os.cpu_count() or 1)
    if worker_count < 1:
        raise ToolchainError("worker count must be at least one")
    worker_count = min(worker_count, len(shaders))
    thread_state = threading.local()
    bytecodes: list[bytes | None] = [None] * len(shaders)
    fallbacks: list[dict[str, str]] = []

    def compile_one(index: int, shader: dict[str, Any]) -> tuple[int, bytes, dict[str, str] | None]:
        profile = PROFILES.get(shader["stage"])
        if profile is None:
            raise ToolchainError(f"unsupported shader stage: {shader['stage']}")
        selector = shader["selector"]
        try:
            source = modules[shader["source_name"]][selector]
        except KeyError as error:
            raise ToolchainError(f"missing HLSL branch {selector}") from error
        compiler = getattr(thread_state, "compiler", None)
        if compiler is None:
            compiler = D3DCompiler()
            thread_state.compiler = compiler
        try:
            bytecode = compiler.compile(source, shader["entry_point"], profile)
        except RuntimeError as error:
            fallback_path = corpus / shader.get("dxbc_path", "")
            if not allow_dxbc_fallback or not fallback_path.is_file():
                raise ToolchainError(f"{selector}: {error}") from error
            bytecode = fallback_path.read_bytes()
            return index, bytecode, {
                "selector": selector,
                "error": stable_diagnostic(str(error)),
            }
        return index, bytecode, None

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(compile_one, index, shader)
            for index, shader in enumerate(shaders)
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            index, bytecode, fallback = future.result()
            bytecodes[index] = bytecode
            if fallback:
                fallbacks.append(fallback)
            if progress and (completed % 100 == 0 or completed == len(shaders)):
                progress(completed, len(shaders))

    compiled_bytecodes = [bytecode for bytecode in bytecodes if bytecode is not None]
    if len(compiled_bytecodes) != len(shaders):
        raise ToolchainError("one or more shader compilation results are missing")
    fallbacks.sort(key=lambda item: item["selector"])

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
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()

    summary = {
        **header,
        "compiled_count": len(shaders) - len(fallbacks),
        "fallback_count": len(fallbacks),
        "shader_count": len(shaders),
        "bundle_size": len(bundle),
        "jobs": worker_count,
        "output_sha256": hashlib.sha256(cache_data).hexdigest(),
    }
    report_path = output.with_suffix(output.suffix + ".build.json")
    report = {"summary": summary, "fallbacks": fallbacks}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {**summary, "report": report_path.name}
