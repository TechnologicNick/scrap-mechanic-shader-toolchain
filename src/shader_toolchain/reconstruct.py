"""Deterministically reconstruct 80 HLSL module files from a shader cache."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from .sbc import D3DCompiler, parse_cache, parse_payload, safe_stem


TIMESTAMP_HEADER = re.compile(
    r"^// ---- Created with 3Dmigoto v([^ ]+) on .*?(?:\r?\n|$)"
)
THREAD_GROUP = re.compile(r"dcl_thread_group\s+(\d+),\s*(\d+),\s*(\d+)")


class ToolchainError(RuntimeError):
    pass


def output_digest(output: Path) -> str:
    """Hash all generated files, including their relative paths."""
    digest = hashlib.sha256()
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        relative = path.relative_to(output).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "little"))
        digest.update(relative)
        contents = path.read_bytes()
        digest.update(len(contents).to_bytes(8, "little"))
        digest.update(contents)
    return digest.hexdigest()


def verify_output(output: Path, expected_modules: int = 80) -> dict[str, Any]:
    """Validate a reconstructed corpus and return its reproducibility digest."""
    manifest_path = output / "manifest.json"
    hlsl_dir = output / "hlsl"
    if not manifest_path.is_file() or not hlsl_dir.is_dir():
        raise ToolchainError(f"not a reconstructed shader corpus: {output}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    shaders = manifest.get("shaders", [])
    summary = manifest.get("summary", {})
    hlsl_files = sorted(hlsl_dir.glob("*.hlsl"))
    source_names = {shader["source_name"] for shader in shaders}
    expected_files = {f"{source_name}.hlsl" for source_name in source_names}
    actual_files = {path.name for path in hlsl_files}

    errors = []
    if len(hlsl_files) != expected_modules:
        errors.append(f"expected {expected_modules} HLSL files, found {len(hlsl_files)}")
    if actual_files != expected_files:
        errors.append("HLSL filenames do not match the manifest source names")
    if summary.get("module_count") != len(hlsl_files):
        errors.append("manifest module count does not match the HLSL files")
    if summary.get("shader_count") != len(shaders):
        errors.append("manifest shader count does not match its shader records")

    module_text = {
        path.stem: path.read_text(encoding="utf-8", errors="strict")
        for path in hlsl_files
    }
    missing_selectors = [
        shader["selector"]
        for shader in shaders
        if shader["selector"] not in module_text.get(shader["source_name"], "")
    ]
    if missing_selectors:
        errors.append(f"{len(missing_selectors)} shader selectors are missing")
    if errors:
        raise ToolchainError("; ".join(errors))

    return {
        "digest_sha256": output_digest(output),
        "module_count": len(hlsl_files),
        "shader_count": len(shaders),
    }


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_migoto() -> Path:
    return repository_root() / "third_party/3Dmigoto/builds/x64/Release/cmd_Decompiler.exe"


def default_dx_decompiler() -> Path:
    return (
        repository_root()
        / "third_party/DXDecompiler/src/DXDecompilerCmd/bin/Release/DXDecompilerCmd.exe"
    )


def run_3dmigoto(tool: Path, dxbc_files: list[Path], batch_size: int = 32) -> str:
    if not tool.is_file():
        raise ToolchainError(
            f"3DMigoto decompiler not found at {tool}; run scripts/build-third-party.ps1"
        )
    log: list[str] = []
    for start in range(0, len(dxbc_files), batch_size):
        batch = dxbc_files[start : start + batch_size]
        process = subprocess.run(
            [str(tool), "-D", *(str(path) for path in batch)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        log.extend((process.stdout, process.stderr))
    return "".join(log)


def run_dx_decompiler(tool: Path, dxbc: Path, output: Path) -> tuple[bool, str]:
    if not tool.is_file():
        return False, f"DXDecompiler fallback not found at {tool}"
    process = subprocess.run(
        [str(tool), "-O", str(output), str(dxbc)],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return output.is_file(), process.stdout + process.stderr


def compute_parameters(source: str) -> list[str]:
    parameters = []
    if "vThreadGroupID" in source:
        parameters.append("uint3 vThreadGroupID : SV_GroupID")
    if "vThreadIDInGroup" in source:
        parameters.append("uint3 vThreadIDInGroup : SV_GroupThreadID")
    if "vThreadID" in source and "vThreadIDInGroup" not in source:
        parameters.append("uint3 vThreadID : SV_DispatchThreadID")
    if "vThreadIndexInGroup" in source:
        parameters.append("uint vThreadIndexInGroup : SV_GroupIndex")
    return parameters


def normalize_3dmigoto(source: str, assembly: str, entry_point: str) -> str:
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    match = TIMESTAMP_HEADER.match(source)
    if match:
        source = f"// Lifted with 3Dmigoto v{match.group(1)}\n" + source[match.end() :]

    broken_compute = re.search(r"(?m)^void main\)\s*$", source)
    if broken_compute:
        group = THREAD_GROUP.search(assembly)
        attribute = ""
        if group:
            attribute = f"[numthreads({group.group(1)}, {group.group(2)}, {group.group(3)})]\n"
        signature = f"void main({', '.join(compute_parameters(source))})"
        source = source[: broken_compute.start()] + attribute + signature + source[broken_compute.end() :]

    source = re.sub(r"(?m)^(\s*)void main(\s*\()", rf"\1void {entry_point}\2", source, count=1)
    return source.rstrip() + "\n"


def normalize_dx_decompiler(source: str, entry_point: str) -> str:
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    source = re.sub(
        r"(?m)^(\s*)void (?:ComputeShader|PixelShader|VertexShader)(\s*\()",
        rf"\1void {entry_point}\2",
        source,
        count=1,
    )
    return "// Fallback lift produced by DXDecompiler\n" + source.rstrip() + "\n"


def render_module(source_name: str, variants: list[dict[str, Any]]) -> str:
    lines = [
        f"// Reconstructed Scrap Mechanic shader module: {source_name}.hlsl",
        "// This is deterministic lifted source, not the unavailable original HLSL.",
        "// Define exactly one SM_SHADER_<key> selector before compiling.",
        "",
    ]
    for position, variant in enumerate(variants):
        directive = "#if" if position == 0 else "#elif"
        lines.extend(
            [
                f"{directive} defined({variant['selector']})",
                f"// Shader key: {variant['shader_key']}",
                f"// Stage: {variant['stage']}; entry point: {variant['entry_point']}",
                f"// Descriptor: {variant['descriptor']}",
                f"// Lift status: {variant['lift_status']}; backend: {variant['backend']}",
                variant["hlsl"].rstrip(),
            ]
        )
    lines.extend(["#endif", ""])
    return "\n".join(lines)


def reconstruct(
    cache: Path,
    output: Path,
    migoto: Path | None = None,
    dx_decompiler: Path | None = None,
) -> dict[str, Any]:
    if output.exists():
        raise ToolchainError(f"output path already exists: {output}")
    output_parent = output.resolve().parent
    output_parent.mkdir(parents=True, exist_ok=True)

    header, payload = parse_cache(cache)
    metadata, bundle = parse_payload(payload)
    compiler = D3DCompiler()
    blobs = compiler.extract(bundle, metadata["shader_count"])
    migoto = (migoto or default_migoto()).resolve()
    dx_decompiler = (dx_decompiler or default_dx_decompiler()).resolve()

    with tempfile.TemporaryDirectory(prefix="sm-shaders-", dir=output_parent) as temporary:
        work = Path(temporary)
        dxbc_dir = work / "dxbc"
        dxbc_dir.mkdir()
        records: list[dict[str, Any]] = []
        dxbc_files: list[Path] = []
        assemblies: dict[int, str] = {}

        for shader in metadata["shaders"]:
            bytecode = blobs[shader["bundle_index"]]
            dxbc = dxbc_dir / f"{safe_stem(shader)}.dxbc"
            dxbc.write_bytes(bytecode)
            dxbc_files.append(dxbc)
            assemblies[shader["index"]] = compiler.to_assembly(bytecode).decode(
                "utf-8", errors="replace"
            )

        run_3dmigoto(migoto, dxbc_files)
        modules: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for shader, dxbc in zip(metadata["shaders"], dxbc_files, strict=True):
            lifted = dxbc.with_suffix(".hlsl")
            backend = "3dmigoto"
            lift_status = "lifted"
            if lifted.is_file():
                hlsl = normalize_3dmigoto(
                    lifted.read_text(encoding="utf-8", errors="replace"),
                    assemblies[shader["index"]],
                    shader["entry_point"],
                )
            else:
                backend = "dxdecompiler"
                fallback = dxbc.with_suffix(".fallback.hlsl")
                ok, _log = run_dx_decompiler(dx_decompiler, dxbc, fallback)
                if ok:
                    hlsl = normalize_dx_decompiler(
                        fallback.read_text(encoding="utf-8", errors="replace"),
                        shader["entry_point"],
                    )
                    lift_status = "fallback-incomplete"
                else:
                    hlsl = "// No high-level lift was produced.\n#if 0\n" + assemblies[
                        shader["index"]
                    ] + "\n#endif\n"
                    backend = "assembly"
                    lift_status = "assembly-only"

            selector = f"SM_SHADER_{shader['shader_key'][2:].upper()}"
            record = {
                key: value for key, value in shader.items() if key != "resource_id_indices"
            }
            record.update(
                {
                    "selector": selector,
                    "backend": backend,
                    "lift_status": lift_status,
                    "dxbc_size": len(blobs[shader["bundle_index"]]),
                    "dxbc_sha256": hashlib.sha256(
                        blobs[shader["bundle_index"]]
                    ).hexdigest(),
                    "resource_id_indices": shader["resource_id_indices"],
                }
            )
            records.append(record)
            modules[shader["source_name"]].append({**record, "hlsl": hlsl})

        staging = work / "result"
        hlsl_dir = staging / "hlsl"
        hlsl_dir.mkdir(parents=True)
        for source_name in sorted(modules):
            variants = sorted(modules[source_name], key=lambda item: item["shader_key"])
            (hlsl_dir / f"{source_name}.hlsl").write_text(
                render_module(source_name, variants), encoding="utf-8", newline="\n"
            )

        summary = {
            **header,
            "module_count": len(modules),
            "shader_count": len(records),
            "backends": dict(
                sorted(
                    (backend, sum(r["backend"] == backend for r in records))
                    for backend in {r["backend"] for r in records}
                )
            ),
            "lift_statuses": dict(
                sorted(
                    (status, sum(r["lift_status"] == status for r in records))
                    for status in {r["lift_status"] for r in records}
                )
            ),
        }
        manifest = {
            "summary": summary,
            "resource_ids": metadata["resource_ids"],
            "jobs": metadata["jobs"],
            "shaders": records,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        shutil.move(str(staging), str(output))
        verify_output(output)
        return summary
