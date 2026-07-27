"""Run semantic pixel shaders against exact DXBC on a D3D11 device."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .hlsl import module_variants, resolve_local_includes
from .reconstruct import ToolchainError, repository_root, verify_output
from .sbc import D3DCompiler


def select_shader_pair(
    manifest: dict[str, Any], source_name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select the single semantic pixel shader and matching exact vertex shader."""
    shaders = [
        shader
        for shader in manifest["shaders"]
        if shader["source_name"] == source_name
    ]
    pixels = [
        shader
        for shader in shaders
        if shader["stage"] == "pixel" and shader.get("semantic_hlsl_path")
    ]
    vertices = [shader for shader in shaders if shader["stage"] == "vertex"]
    if len(pixels) != 1:
        raise ToolchainError(
            f"{source_name} needs exactly one semantic pixel variant; "
            f"found {len(pixels)}"
        )
    if len(vertices) != 1:
        raise ToolchainError(
            f"{source_name} needs exactly one vertex variant; found {len(vertices)}"
        )
    return vertices[0], pixels[0]


def compile_semantic_shader(
    corpus: Path,
    manifest: dict[str, Any],
    shader: dict[str, Any],
    compiler: D3DCompiler,
) -> tuple[bytes, str]:
    relative = shader["semantic_hlsl_path"]
    module_path = corpus / relative
    semantic_root = corpus / "semantic"
    definitions = {
        record["selector"]: record["defines"]
        for record in manifest["shaders"]
        if record.get("semantic_hlsl_path") == relative
    }
    variants = module_variants(
        module_path.read_text(encoding="utf-8"), definitions
    )
    try:
        source = variants[shader["selector"]]
    except KeyError as error:
        raise ToolchainError(
            f"semantic module does not contain {shader['selector']}"
        ) from error
    source = resolve_local_includes(source, module_path, semantic_root)
    return compiler.compile(source, shader["entry_point"], "ps_5_0"), source


def _invoke_harness(
    harness: Path,
    vertex: Path,
    baseline: Path,
    candidate: Path,
    *,
    cases: int,
    seed: int,
    width: int,
    height: int,
    absolute_tolerance: float,
    relative_tolerance: float,
    failure_dir: Path | None,
    warp: bool,
) -> dict[str, Any]:
    command = [
        str(harness),
        "--vertex",
        str(vertex),
        "--baseline",
        str(baseline),
        "--candidate",
        str(candidate),
        "--cases",
        str(cases),
        "--seed",
        str(seed),
        "--width",
        str(width),
        "--height",
        str(height),
        "--absolute-tolerance",
        str(absolute_tolerance),
        "--relative-tolerance",
        str(relative_tolerance),
    ]
    if failure_dir is not None:
        command.extend(("--failure-dir", str(failure_dir)))
    if warp:
        command.append("--warp")
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode not in (0, 2):
        diagnostic = process.stderr.strip() or process.stdout.strip()
        raise ToolchainError(f"GPU differential runner failed: {diagnostic}")
    try:
        report = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise ToolchainError("GPU differential runner returned invalid JSON") from error
    if bool(report.get("passed")) != (process.returncode == 0):
        raise ToolchainError("GPU differential runner result disagrees with exit code")
    return report


def fuzz_semantic_shader(
    corpus: Path,
    *,
    source_name: str = "post_fxaa",
    cases: int = 256,
    seed: int = 0x534D465841413031,
    width: int = 64,
    height: int = 64,
    absolute_tolerance: float = 0.0,
    relative_tolerance: float = 0.0,
    failure_dir: Path | None = None,
    harness: Path | None = None,
    warp: bool = False,
) -> dict[str, Any]:
    """Compile a semantic pixel shader and compare its pixels with exact DXBC."""
    if cases < 1 or width < 1 or height < 1:
        raise ToolchainError("cases, width, and height must be positive")
    if absolute_tolerance < 0 or relative_tolerance < 0:
        raise ToolchainError("comparison tolerances must be non-negative")
    verify_output(corpus, verify_hlsl_fingerprints=False)
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    vertex, pixel = select_shader_pair(manifest, source_name)
    compiler = D3DCompiler()
    candidate, source = compile_semantic_shader(corpus, manifest, pixel, compiler)
    vertex_path = corpus / vertex["dxbc_path"]
    baseline_path = corpus / pixel["dxbc_path"]
    harness_path = (
        harness
        or repository_root() / "build" / "gpu_diff" / "sm-gpu-diff.exe"
    )
    if not harness_path.is_file():
        raise ToolchainError(
            f"GPU harness not found at {harness_path}; "
            "run .\\scripts\\build-gpu-harness.ps1"
        )

    with tempfile.TemporaryDirectory(prefix="sm-gpu-fuzz-") as temporary:
        candidate_path = Path(temporary) / "semantic.dxbc"
        candidate_path.write_bytes(candidate)
        control = _invoke_harness(
            harness_path,
            vertex_path,
            baseline_path,
            baseline_path,
            cases=min(cases, 8),
            seed=seed,
            width=width,
            height=height,
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
            failure_dir=None,
            warp=warp,
        )
        if not control["passed"] or control["max_absolute_error"] != 0:
            raise ToolchainError("GPU control run was not bit-exact")
        comparison = _invoke_harness(
            harness_path,
            vertex_path,
            baseline_path,
            candidate_path,
            cases=cases,
            seed=seed,
            width=width,
            height=height,
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
            failure_dir=failure_dir,
            warp=warp,
        )

    report = {
        "source_name": source_name,
        "vertex_selector": vertex["selector"],
        "pixel_selector": pixel["selector"],
        "semantic_recipe": pixel["semantic_recipe"],
        "baseline_dxbc_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        "candidate_dxbc_sha256": hashlib.sha256(candidate).hexdigest(),
        "control": control,
        "comparison": comparison,
        "failure_directory": (
            str(failure_dir)
            if failure_dir and not comparison["passed"]
            else None
        ),
    }
    if failure_dir is not None and not comparison["passed"]:
        failure_dir.mkdir(parents=True, exist_ok=True)
        (failure_dir / "candidate.hlsl").write_text(
            source, encoding="utf-8", newline="\n"
        )
        (failure_dir / "run.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report
