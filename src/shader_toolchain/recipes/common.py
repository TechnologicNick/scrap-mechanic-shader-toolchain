"""Shared emission and validation machinery for semantic shader recipes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..compare import compare_bytecodes
from ..hlsl import (
    hlsl_token_sha256,
    module_variants,
    render_factored_module,
    resolve_local_includes,
)
from ..reflect import ShaderReflector


PROFILES = {"vertex": "vs_5_0", "pixel": "ps_5_0", "compute": "cs_5_0"}


def asset(name: str) -> str:
    return (Path(__file__).parent / "assets" / name).read_text(encoding="utf-8")


def ensure_projection_include(staging: Path) -> None:
    include_dir = staging / "semantic" / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    path = include_dir / "post_fxaa_abi.hlsl"
    if not path.exists():
        path.write_text(
            asset("post_fxaa_abi.hlsl"), encoding="utf-8", newline="\n"
        )


def ensure_hdr_include(staging: Path) -> None:
    include_dir = staging / "semantic" / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    path = include_dir / "hdr_abi.hlsl"
    if not path.exists():
        path.write_text(asset("hdr_abi.hlsl"), encoding="utf-8", newline="\n")


def ensure_asset_include(staging: Path, filename: str) -> None:
    """Copy a shared semantic helper into the generated include directory."""
    include_dir = staging / "semantic" / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    path = include_dir / filename
    if not path.exists():
        path.write_text(asset(filename), encoding="utf-8", newline="\n")


def ensure_recovered_cbuffer_include(
    staging: Path,
    source_name: str,
    cbuffer_name: str,
    filename: str,
) -> None:
    """Reuse an exact reflected cbuffer declaration from the mechanical lift."""
    include_dir = staging / "semantic" / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    path = include_dir / filename
    if path.exists():
        return
    module = (staging / "hlsl" / f"{source_name}.hlsl").read_text(
        encoding="utf-8"
    )
    marker = f"cbuffer {cbuffer_name}"
    start = module.find(marker)
    if start < 0:
        raise RuntimeError(f"{source_name} does not declare {cbuffer_name}")
    opening = module.find("{", start)
    depth = 0
    end = None
    for index in range(opening, len(module)):
        if module[index] == "{":
            depth += 1
        elif module[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise RuntimeError(f"unterminated {cbuffer_name} declaration")
    path.write_text(
        "// Exact declaration recovered from DXBC reflection.\n"
        + module[start:end]
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def emit_validated_module(
    staging: Path,
    shaders: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
    *,
    recipe_name: str,
    bodies: dict[str, str],
    executions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Emit, compile, reflect, and fingerprint one complete semantic module."""
    semantic_root = staging / "semantic"
    semantic_root.mkdir(parents=True, exist_ok=True)
    variants = [
        {**shader, "hlsl": bodies[shader["selector"]]} for shader in shaders
    ]
    module_path = semantic_root / f"{recipe_name}.hlsl"
    module_path.write_text(
        render_factored_module(recipe_name, variants),
        encoding="utf-8",
        newline="\n",
    )
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(module_path.read_text(encoding="utf-8"), definitions)
    reflector = ShaderReflector()
    assembly_exact = 0
    for shader in shaders:
        source = resolve_local_includes(
            expanded[shader["selector"]], module_path, semantic_root
        )
        candidate = compiler.compile(
            source, shader["entry_point"], PROFILES[shader["stage"]]
        )
        comparison, _baseline_assembly, _candidate_assembly = compare_bytecodes(
            blobs[shader["bundle_index"]], candidate, compiler, reflector
        )
        if not comparison["abi_compatible"]:
            changed = ", ".join(comparison["abi_differences"])
            raise RuntimeError(
                f"{recipe_name} {shader['selector']} semantic recipe changes "
                f"runtime ABI: {changed}"
            )
        assembly_exact += int(comparison["assembly_exact"])
        shader.update(
            {
                "semantic_recipe": recipe_name,
                "semantic_hlsl_path": f"semantic/{recipe_name}.hlsl",
                "semantic_hlsl_token_sha256": hlsl_token_sha256(source),
                "semantic_assembly_exact": comparison["assembly_exact"],
                "semantic_abi_compatible": True,
            }
        )
        execution = (executions or {}).get(shader["selector"])
        if execution:
            shader["semantic_execution"] = execution
    return {
        "name": recipe_name,
        "shader_count": len(shaders),
        "assembly_exact_count": assembly_exact,
    }
