"""Compare rebuilt shader bytecode with a baseline cache."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .reconstruct import ToolchainError
from .reflect import ShaderReflector, abi_differences
from .sbc import D3DCompiler, parse_cache, parse_payload


def normalized_assembly(bytecode: bytes, compiler: D3DCompiler) -> str:
    return (
        compiler.to_assembly(bytecode)
        .decode("utf-8", errors="replace")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .rstrip("\x00")
    )


def executable_lines(assembly: str) -> list[str]:
    return [
        line.strip()
        for line in assembly.splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    ]


def opcode_sequence(lines: list[str]) -> list[str]:
    return [re.split(r"[\s,]", line, maxsplit=1)[0] for line in lines]


def compare_bytecodes(
    baseline: bytes,
    candidate: bytes,
    compiler: D3DCompiler,
    reflector: ShaderReflector,
) -> tuple[dict[str, Any], str, str]:
    baseline_assembly = normalized_assembly(baseline, compiler)
    candidate_assembly = normalized_assembly(candidate, compiler)
    baseline_lines = executable_lines(baseline_assembly)
    candidate_lines = executable_lines(candidate_assembly)
    differences = abi_differences(
        reflector.abi(baseline), reflector.abi(candidate)
    )
    result = {
        "assembly_exact": baseline_assembly == candidate_assembly,
        "executable_exact": baseline_lines == candidate_lines,
        "opcode_sequence_exact": opcode_sequence(baseline_lines)
        == opcode_sequence(candidate_lines),
        "abi_compatible": not differences,
        "abi_differences": differences,
        "baseline_instruction_lines": len(baseline_lines),
        "candidate_instruction_lines": len(candidate_lines),
        "baseline_assembly_sha256": hashlib.sha256(
            baseline_assembly.encode("utf-8")
        ).hexdigest(),
        "candidate_assembly_sha256": hashlib.sha256(
            candidate_assembly.encode("utf-8")
        ).hexdigest(),
    }
    return result, baseline_assembly, candidate_assembly


def compare_caches(
    baseline_path: Path,
    candidate_path: Path,
    *,
    report_path: Path | None = None,
    diff_dir: Path | None = None,
) -> dict[str, Any]:
    baseline_header, baseline_payload = parse_cache(baseline_path)
    baseline_metadata, baseline_bundle = parse_payload(baseline_payload)
    candidate_header, candidate_payload = parse_cache(candidate_path)
    candidate_metadata, candidate_bundle = parse_payload(candidate_payload)
    baseline_shaders = baseline_metadata["shaders"]
    candidate_shaders = candidate_metadata["shaders"]
    baseline_keys = [shader["shader_key"] for shader in baseline_shaders]
    candidate_keys = [shader["shader_key"] for shader in candidate_shaders]
    if baseline_keys != candidate_keys:
        raise ToolchainError("shader keys or ordering differ between caches")

    compiler = D3DCompiler()
    reflector = ShaderReflector()
    baseline_blobs = compiler.extract(baseline_bundle, len(baseline_shaders))
    candidate_blobs = compiler.extract(candidate_bundle, len(candidate_shaders))
    records = []
    counts: Counter[str] = Counter()
    for shader, baseline, candidate in zip(
        baseline_shaders, baseline_blobs, candidate_blobs, strict=True
    ):
        comparison, baseline_assembly, candidate_assembly = compare_bytecodes(
            baseline, candidate, compiler, reflector
        )
        selector = f"SM_SHADER_{shader['shader_key'][2:].upper()}"
        record = {
            "index": shader["index"],
            "selector": selector,
            "source_name": shader["source_name"],
            "entry_point": shader["entry_point"],
            **comparison,
        }
        records.append(record)
        for field in (
            "assembly_exact",
            "executable_exact",
            "opcode_sequence_exact",
            "abi_compatible",
        ):
            counts[f"{field}_{str(comparison[field]).lower()}"] += 1
        if diff_dir is not None and not comparison["assembly_exact"]:
            diff_dir.mkdir(parents=True, exist_ok=True)
            difference = difflib.unified_diff(
                baseline_assembly.splitlines(),
                candidate_assembly.splitlines(),
                fromfile="baseline",
                tofile="candidate",
                lineterm="",
            )
            (diff_dir / f"{selector}.diff").write_text(
                "\n".join(difference) + "\n", encoding="utf-8", newline="\n"
            )

    metadata_fields = ("resource_ids", "jobs", "shaders")
    summary = {
        "shader_count": len(records),
        "baseline_sha256": baseline_header["sha256"],
        "candidate_sha256": candidate_header["sha256"],
        "metadata_equal": all(
            baseline_metadata[field] == candidate_metadata[field]
            for field in metadata_fields
        ),
        **dict(sorted(counts.items())),
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps({"summary": summary, "shaders": records}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return summary
