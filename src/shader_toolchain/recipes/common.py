"""Shared emission and validation machinery for semantic shader recipes."""

from __future__ import annotations

import os
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ..compare import compare_bytecodes
from ..hlsl import (
    hlsl_token_sha256,
    module_variants,
    render_factored_module,
    render_shared_module,
    semantic_module_variants,
    resolve_local_includes,
)
from ..reflect import ShaderReflector
from ..sbc import D3DCompiler


PROFILES = {"vertex": "vs_5_0", "pixel": "ps_5_0", "compute": "cs_5_0"}


def rename_register_state(
    source: str, names: dict[int, str], *, note: str
) -> str:
    """Replace anonymous decompiler registers with stable domain state names."""
    for index in sorted(names, reverse=True):
        source = re.sub(rf"\br{index}\b", names[index], source)
    source = re.sub(r"\bbitmask\b", "packedBitmask", source)
    source = re.sub(r"\buiDest\b", "integerDestination", source)
    source = re.sub(r"\bfDest\b", "floatDestination", source)
    source = source.replace(
        "  uint4 packedBitmask, integerDestination;\n"
        "  float4 floatDestination;\n",
        f"  // {note}\n"
        "  uint4 packedBitmask, integerDestination;\n"
        "  float4 floatDestination;\n",
    )
    return source


def semantic_worker_count(task_count: int) -> int:
    """Choose the bounded semantic validation pool size."""
    configured = os.environ.get("SM_SHADERS_JOBS")
    try:
        requested = int(configured) if configured is not None else (os.cpu_count() or 1)
    except ValueError as error:
        raise RuntimeError("SM_SHADERS_JOBS must be an integer") from error
    if requested < 1:
        raise RuntimeError("SM_SHADERS_JOBS must be at least one")
    return min(requested, task_count) if task_count else 0


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


def replace_cbuffer_with_include(
    source: str, cbuffer_name: str, filename: str
) -> str:
    """Replace one balanced cbuffer declaration with its recovered ABI include."""
    marker = f"cbuffer {cbuffer_name}"
    start = source.find(marker)
    if start < 0:
        raise RuntimeError(f"semantic source does not declare {cbuffer_name}")
    opening = source.find("{", start)
    if opening < 0:
        raise RuntimeError(f"{cbuffer_name} declaration has no body")
    depth = 0
    end = None
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise RuntimeError(f"unterminated {cbuffer_name} declaration")
    while end < len(source) and source[end] in " \t\r\n":
        end += 1
    return source[:start] + f'#include "include/{filename}"\n\n' + source[end:]


def emit_validated_module(
    staging: Path,
    shaders: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
    *,
    recipe_name: str,
    bodies: dict[str, str],
    executions: dict[str, dict[str, Any]] | None = None,
    shared_source: str | None = None,
) -> dict[str, Any]:
    """Emit, compile, reflect, and fingerprint one complete semantic module."""
    semantic_root = staging / "semantic"
    semantic_root.mkdir(parents=True, exist_ok=True)
    variants = [
        {**shader, "hlsl": bodies[shader["selector"]]} for shader in shaders
    ]
    module_path = semantic_root / f"{recipe_name}.hlsl"
    module_path.write_text(
        render_shared_module(recipe_name, shared_source)
        if shared_source is not None
        else render_factored_module(recipe_name, variants),
        encoding="utf-8",
        newline="\n",
    )
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = semantic_module_variants(
        module_path.read_text(encoding="utf-8"), definitions
    )
    metadata_dir = staging / "metadata" / "semantic-variants"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / f"{recipe_name}.json").write_text(
        json.dumps(
            [
                {
                    "selector": shader["selector"],
                    "stage": shader["stage"],
                    "entry_point": shader["entry_point"],
                    "defines": shader["defines"],
                }
                for shader in sorted(shaders, key=lambda item: item["selector"])
            ],
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tasks = []
    for index, shader in enumerate(shaders):
        source = resolve_local_includes(
            expanded[shader["selector"]], module_path, semantic_root
        )
        tasks.append((index, shader, source))

    thread_state = threading.local()

    def validate_one(
        index: int, shader: dict[str, Any], source: str
    ) -> tuple[int, str, dict[str, Any]]:
        worker_compiler = getattr(thread_state, "compiler", None)
        if worker_compiler is None:
            worker_compiler = D3DCompiler()
            thread_state.compiler = worker_compiler
            thread_state.reflector = ShaderReflector()
        try:
            candidate = worker_compiler.compile(
                source, shader["entry_point"], PROFILES[shader["stage"]]
            )
        except RuntimeError as error:
            raise RuntimeError(
                f"{recipe_name} {shader['selector']} semantic recipe does not "
                f"compile: {error}"
            ) from error
        comparison, _baseline_assembly, _candidate_assembly = compare_bytecodes(
            blobs[shader["bundle_index"]], candidate,
            worker_compiler, thread_state.reflector,
        )
        if not comparison["abi_compatible"]:
            changed = ", ".join(comparison["abi_differences"])
            raise RuntimeError(
                f"{recipe_name} {shader['selector']} semantic recipe changes "
                f"runtime ABI: {changed}"
            )
        return index, hlsl_token_sha256(source), comparison

    results: list[tuple[str, dict[str, Any]] | None] = [None] * len(tasks)
    worker_count = semantic_worker_count(len(tasks))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(validate_one, *task) for task in tasks]
        with tqdm(
            total=len(futures),
            desc=f"semantic {recipe_name}",
            unit="shader",
            dynamic_ncols=True,
        ) as progress:
            for future in as_completed(futures):
                index, fingerprint, comparison = future.result()
                results[index] = (fingerprint, comparison)
                progress.update()

    assembly_exact = 0
    for shader, result in zip(shaders, results, strict=True):
        if result is None:
            raise RuntimeError(f"{recipe_name} semantic validation result is missing")
        fingerprint, comparison = result
        assembly_exact += int(comparison["assembly_exact"])
        shader.update(
            {
                "semantic_recipe": recipe_name,
                "semantic_hlsl_path": f"semantic/{recipe_name}.hlsl",
                "semantic_module_kind": (
                    "shared" if shared_source is not None else "factored"
                ),
                "semantic_hlsl_token_sha256": fingerprint,
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
