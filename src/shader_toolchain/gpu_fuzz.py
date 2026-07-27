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


FULLSCREEN_UV_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    float4 uv : UV0;
    float4 unscaledUv : UNSCALED_UV0;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 coordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);
    output.uv = float4(coordinates[vertexId], 0.0, 0.0);
    output.unscaledUv = output.uv;
    return output;
}
"""

DECALS_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    noperspective centroid float2 screenUv : TEXCOORD0;
    nointerpolation uint decalIndex : INDEX0;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] = {
        float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0)
    };
    static const float2 coordinates[3] = {
        float2(0.0, 1.0), float2(2.0, 1.0), float2(0.0, -1.0)
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);
    output.screenUv = coordinates[vertexId];
    output.decalIndex = 0;
    return output;
}
"""

FULLSCREEN_GUI_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    float4 texcoord0 : TEXCOORD0;
    float4 texcoord1 : TEXCOORD1;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 coordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);
    output.texcoord0 = float4(coordinates[vertexId], 0.625, 0.875);
    output.texcoord1 = float4(coordinates[vertexId], 0.375, 0.125);
    return output;
}
"""

FULLSCREEN_DEBUG_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    float4 viewPosition : VIEW_POSITION0;
    float3 screenUv : SCREEN_UV0;
    nointerpolation float4 color : TEXCOORD0;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 coordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);
    output.viewPosition = float4(positions[vertexId], -12.0, 1.0);
    output.screenUv = float3(coordinates[vertexId], 0.5);
    output.color = float4(0.25, 0.5, 0.75, 0.625);
    return output;
}
"""

FULLSCREEN_LINE_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    float2 uv : TEXCOORD0;
    float endFade : TEXCOORD1;
    nointerpolation float fadeScale : TEXCOORD2;
    nointerpolation float3 color : COLOR0;
    noperspective centroid float3 screenUv : SCREEN_UV0;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 coordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.5, 1.0);
    output.uv = coordinates[vertexId];
    output.endFade = coordinates[vertexId].x;
    output.fadeScale = 0.625;
    output.color = float3(0.25, 0.5, 0.75);
    output.screenUv = float3(coordinates[vertexId], 0.5);
    return output;
}
"""

FULLSCREEN_IMPOSTOR_VERTEX = """
struct VertexOutput
{
    float4 position : SV_Position0;
    float4 atlasUv : TEXCOORD0;
    nointerpolation float atlasLayer : TEXCOORD1;
    linear noperspective centroid float4 screenUv : TEXCOORD2;
    nointerpolation float facingSlice : TEXCOORD3;
    nointerpolation float4 blendSlices : TEXCOORD4;
    nointerpolation float3 blendWeights : TEXCOORD5;
    nointerpolation uint packedData : TEXCOORD6;
};

VertexOutput harnessVS(uint vertexId : SV_VertexID)
{
    float2 positions[3] = {
        float2(-1.0, -1.0), float2(-1.0, 3.0), float2(3.0, -1.0)
    };
    VertexOutput output;
    float2 p = positions[vertexId];
    output.position = float4(p, 0.5, 1.0);
    output.atlasUv = float4(p * float2(0.5, -0.5) + 0.5, 0.0, 0.0);
    output.atlasLayer = (float)(vertexId & 3u);
    output.screenUv = float4(output.atlasUv.xy, 0.0, 1.0);
    output.facingSlice = 0.0;
    output.blendSlices = float4(0.0, 1.0, 2.0, 3.0);
    output.blendWeights = float3(0.25, 0.5, 0.75);
    output.packedData = 0x7f804020u + vertexId;
    return output;
}
"""

FULLSCREEN_CLUTTER_IMPOSTOR_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    float depthFade : TEXCOORD0;
    float3 viewNormal : TEXCOORD1;
    float4 texcoord : TEXCOORD2;
    nointerpolation float4 tint : TEXCOORD3;
    nointerpolation uint4 slice : TEXCOORD4;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 coordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);
    output.depthFade = 0.625;
    output.viewNormal = normalize(float3(0.35, 0.8, 0.48));
    output.texcoord = float4(coordinates[vertexId], 0.0, 0.0);
    output.tint = float4(0.25, 0.5, 0.75, asfloat(0u));
    output.slice.w = 0;
    return output;
}
"""

FULLSCREEN_TEXT_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    float3 viewPosition : VIEW_POSITION0;
    float2 uv : UV0;
    float3 normal : NORMAL0;
    float4 color : VERTEXCOLOR0;
    nointerpolation float3 instanceAsg : INSTANCE_ASG0;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 coordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.5, 1.0);
    output.viewPosition = float3(positions[vertexId], -10.0);
    output.uv = coordinates[vertexId];
    output.normal = normalize(float3(0.35, 0.8, 0.48));
    output.color = float4(0.25, 0.5, 0.75, 0.625);
    output.instanceAsg = float3(0.07, 0.28, 0.875);
    return output;
}
"""

FULLSCREEN_BILLBOARD_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    float3 texcoord : TEXCOORD0;
    float alphaScale : TEXCOORD1;
    nointerpolation uint packedColor : COLOR0;
    float depthOffset : TEXCOORD2;
    float minimumSize : TEXCOORD3;
    float3 viewPosition : VIEW_POSITION0;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 coordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.5, 1.0);
    output.texcoord = float3(coordinates[vertexId], 0.0);
    output.alphaScale = 0.375;
    output.packedColor = 0xffc08040u;
    output.depthOffset = 0.125;
    output.minimumSize = 0.5;
    output.viewPosition = float3(positions[vertexId], -10.0);
    return output;
}
"""

FULLSCREEN_EDITOR_TERRAIN_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    float2 materialUv : TEXCOORD1;
    float2 worldUv : TEXCOORD3;
    float4 color : TEXCOORD2;
    float4 tangent : TEXCOORD4;
    float4 bitangent : TEXCOORD5;
    float3 normal : TEXCOORD6;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 coordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.5, 1.0);
    output.materialUv = coordinates[vertexId];
    output.worldUv = coordinates[vertexId] * 0.25;
    output.color = float4(0.25, 0.5, 0.75, 1.0);
    output.tangent = float4(1.0, 0.0, 0.0, 0.0);
    output.bitangent = float4(0.0, 1.0, 0.0, 0.0);
    output.normal = float3(0.0, 0.0, 1.0);
    return output;
}
"""

FULLSCREEN_TERRAIN_VERTEX = """
struct HarnessVertexOutput
{
    float4 position : SV_Position0;
    float2 uv : UV0;
    float2 worldUv : WORLD_UV0;
    float3 color : COLOR0;
    nointerpolation uint tileIndex : TILE_INDEX0;
    float4 tangent : TEXCOORD5;
    float4 bitangent : TEXCOORD6;
    float3 normal : TEXCOORD7;
};

HarnessVertexOutput harnessVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 coordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };
    HarnessVertexOutput output;
    output.position = float4(positions[vertexId], 0.5, 1.0);
    output.uv = coordinates[vertexId];
    output.worldUv = coordinates[vertexId] * 0.25;
    output.color = float3(0.25, 0.5, 0.75);
    output.tileIndex = 0;
    output.tangent = float4(1.0, 0.0, 0.0, 0.0);
    output.bitangent = float4(0.0, 1.0, 0.0, 0.0);
    output.normal = float3(0.0, 0.0, 1.0);
    return output;
}
"""

VERTEX_HARNESSES = {
    "fullscreen_uv": FULLSCREEN_UV_VERTEX,
    "decals": DECALS_VERTEX,
    "fullscreen_gui": FULLSCREEN_GUI_VERTEX,
    "fullscreen_debug": FULLSCREEN_DEBUG_VERTEX,
    "fullscreen_line": FULLSCREEN_LINE_VERTEX,
    "fullscreen_impostor": FULLSCREEN_IMPOSTOR_VERTEX,
    "fullscreen_clutter_impostor": FULLSCREEN_CLUTTER_IMPOSTOR_VERTEX,
    "fullscreen_text": FULLSCREEN_TEXT_VERTEX,
    "fullscreen_billboard": FULLSCREEN_BILLBOARD_VERTEX,
    "fullscreen_terrain": FULLSCREEN_TERRAIN_VERTEX,
    "fullscreen_editor_terrain": FULLSCREEN_EDITOR_TERRAIN_VERTEX,
}


def select_shader_pair(
    manifest: dict[str, Any], source_name: str, pixel_selector: str | None = None
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
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
    if pixel_selector is not None:
        pixels = [shader for shader in pixels if shader["selector"] == pixel_selector]
    vertices = [shader for shader in shaders if shader["stage"] == "vertex"]
    if len(pixels) != 1:
        raise ToolchainError(
            f"{source_name} needs exactly one semantic pixel variant; "
            f"found {len(pixels)}"
        )
    execution = pixels[0].get("semantic_execution", {}) if len(pixels) == 1 else {}
    if execution.get("vertex_harness") in VERTEX_HARNESSES:
        return None, pixels[0]
    vertex_selector = execution.get("vertex_selector")
    if vertex_selector:
        vertices = [
            shader
            for shader in manifest["shaders"]
            if shader["selector"] == vertex_selector and shader["stage"] == "vertex"
        ]
    if len(vertices) != 1:
        raise ToolchainError(
            f"{source_name} needs exactly one vertex variant; found {len(vertices)}"
        )
    return vertices[0], pixels[0]


def select_compute_shader(
    manifest: dict[str, Any], source_name: str, selector: str | None = None
) -> dict[str, Any]:
    shaders = [
        shader
        for shader in manifest["shaders"]
        if shader["source_name"] == source_name
        and shader["stage"] == "compute"
        and shader.get("semantic_hlsl_path")
    ]
    if selector is not None:
        shaders = [shader for shader in shaders if shader["selector"] == selector]
    if len(shaders) != 1:
        raise ToolchainError(
            f"{source_name} needs exactly one semantic compute variant; "
            f"found {len(shaders)}"
        )
    return shaders[0]


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
    profiles = {"pixel": "ps_5_0", "compute": "cs_5_0", "vertex": "vs_5_0"}
    return compiler.compile(
        source, shader["entry_point"], profiles[shader["stage"]]
    ), source


def _invoke_harness(
    harness: Path,
    vertex: Path | None,
    baseline: Path,
    candidate: Path,
    *,
    cases: int,
    seed: int,
    width: int,
    height: int,
    dispatch_width: int,
    dispatch_height: int,
    absolute_tolerance: float,
    relative_tolerance: float,
    ulp_tolerance: int,
    texture_slots: list[int],
    texture_kinds: list[str],
    texture_mips: list[int],
    texture_slices: list[int],
    smooth_texture_slots: list[int],
    structured_inputs: list[dict[str, int]],
    structured_output_elements: int,
    structured_output_stride: int,
    structured_outputs: list[dict[str, int]],
    samplers: list[dict[str, Any]],
    constant_buffers: list[dict[str, Any]],
    output_kind: str,
    output_components: int,
    output_targets: int,
    shader_stage: str,
    thread_group: list[int],
    failure_dir: Path | None,
    warp: bool,
) -> dict[str, Any]:
    command = [
        str(harness),
        "--stage",
        shader_stage,
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
        "--dispatch-width",
        str(dispatch_width),
        "--dispatch-height",
        str(dispatch_height),
        "--absolute-tolerance",
        str(absolute_tolerance),
        "--relative-tolerance",
        str(relative_tolerance),
        "--ulp-tolerance",
        str(ulp_tolerance),
        "--textures",
        ",".join(
            f"{slot}:{kind}:{mips}:{slices}"
            for slot, kind, mips, slices in zip(
                texture_slots, texture_kinds, texture_mips, texture_slices,
                strict=True
            )
        ),
        "--structured-inputs",
        ",".join(
            f"{binding['slot']}:{binding['elements']}:{binding['stride']}:{binding['profile']}"
            for binding in structured_inputs
        ),
        "--smooth-texture-slots",
        ",".join(str(slot) for slot in smooth_texture_slots),
        "--structured-output-elements",
        str(structured_output_elements),
        "--structured-output-stride",
        str(structured_output_stride),
        "--structured-outputs",
        ",".join(
            f"{binding['slot']}:{binding['elements']}:{binding['stride']}"
            for binding in structured_outputs
        ),
        "--samplers",
        ",".join(
            f"{sampler['slot']}:{sampler['filter']}"
            + (":comparison" if sampler.get("comparison", False) else "")
            for sampler in samplers
        ),
        "--constant-buffers",
        ",".join(
            f"{binding['slot']}:{binding['profile']}"
            for binding in constant_buffers
        ),
        "--output",
        output_kind,
        "--output-components",
        str(output_components),
        "--output-targets",
        str(output_targets),
        "--thread-group",
        ",".join(str(value) for value in thread_group),
    ]
    if vertex is not None:
        command.extend(("--vertex", str(vertex)))
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
    pixel_selector: str | None = None,
    cases: int = 256,
    seed: int = 0x534D465841413031,
    width: int = 64,
    height: int = 64,
    absolute_tolerance: float = 0.0,
    relative_tolerance: float = 0.0,
    ulp_tolerance: int = 0,
    failure_dir: Path | None = None,
    harness: Path | None = None,
    warp: bool = False,
    verify_corpus: bool = True,
) -> dict[str, Any]:
    """Compile a semantic pixel or compute shader and compare exact GPU output."""
    if cases < 1 or width < 1 or height < 1:
        raise ToolchainError("cases, width, and height must be positive")
    if absolute_tolerance < 0 or relative_tolerance < 0:
        raise ToolchainError("comparison tolerances must be non-negative")
    if ulp_tolerance < 0:
        raise ToolchainError("ULP tolerance must be non-negative")
    if verify_corpus:
        verify_output(corpus, verify_hlsl_fingerprints=False)
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    semantic_compute = [
        shader
        for shader in manifest["shaders"]
        if shader["source_name"] == source_name
        and shader["stage"] == "compute"
        and shader.get("semantic_hlsl_path")
    ]
    if semantic_compute:
        shader = select_compute_shader(manifest, source_name, pixel_selector)
        vertex = None
        shader_stage = "compute"
    else:
        vertex, shader = select_shader_pair(manifest, source_name, pixel_selector)
        shader_stage = "pixel"
    execution = shader.get("semantic_execution", {})
    ulp_tolerance = int(execution.get("ulp_tolerance", ulp_tolerance))
    width = int(execution.get("width", width))
    height = int(execution.get("height", height))
    dispatch_width = int(execution.get("dispatch_width", width))
    dispatch_height = int(execution.get("dispatch_height", height))
    if dispatch_width < 1 or dispatch_height < 1:
        raise ToolchainError("dispatch dimensions must be positive")
    texture_slots = [
        int(slot)
        for slot in execution.get(
            "texture_slots", [execution.get("texture_slot", 0)]
        )
    ]
    texture_kinds = [
        str(kind)
        for kind in execution.get("texture_kinds", ["2d"] * len(texture_slots))
    ]
    if len(texture_kinds) != len(texture_slots):
        raise ToolchainError("texture slots and kinds must have equal lengths")
    if any(kind not in ("2d", "3d", "2darray", "cube") for kind in texture_kinds):
        raise ToolchainError("unsupported texture kind")
    texture_mips = [
        int(mips)
        for mips in execution.get("texture_mips", [1] * len(texture_slots))
    ]
    if len(texture_mips) != len(texture_slots) or any(
        mips < 1 or mips > 13 for mips in texture_mips
    ):
        raise ToolchainError("invalid texture mip counts")
    default_slices = {"2d": 1, "3d": 4, "2darray": 6, "cube": 6}
    texture_slices = [
        int(slices)
        for slices in execution.get(
            "texture_slices", [default_slices[kind] for kind in texture_kinds]
        )
    ]
    smooth_texture_slots = [
        int(slot) for slot in execution.get("smooth_texture_slots", [])
    ]
    if len(texture_slices) != len(texture_slots) or any(
        slices < 1 or slices > 2048 for slices in texture_slices
    ) or any(
        kind == "2d" and slices != 1 or kind == "cube" and slices != 6
        for kind, slices in zip(texture_kinds, texture_slices, strict=True)
    ):
        raise ToolchainError("invalid texture slice counts")
    structured_inputs = [
        {
            "slot": int(binding["slot"]),
            "elements": int(binding["elements"]),
            "stride": int(binding.get("stride", 4)),
            "profile": str(binding.get("profile", "random")),
        }
        for binding in execution.get("structured_inputs", [])
    ]
    structured_output_elements = int(
        execution.get("structured_output_elements", 0)
    )
    structured_output_stride = int(execution.get("structured_output_stride", 4))
    structured_outputs = [
        {
            "slot": int(binding["slot"]),
            "elements": int(binding["elements"]),
            "stride": int(binding.get("stride", 4)),
            "profile": str(binding.get("profile", "zero")),
        }
        for binding in execution.get("structured_outputs", [])
    ]
    if structured_output_elements and not structured_outputs:
        structured_outputs = [{
            "slot": 0,
            "elements": structured_output_elements,
            "stride": structured_output_stride,
            "profile": "zero",
        }]
    if any(
        binding["slot"] < 0 or binding["elements"] < 1
        or binding["stride"] < 4 or binding["stride"] % 4
        or binding["profile"] not in ("random", "zero")
        for binding in structured_inputs
    ) or any(
        binding["slot"] < 0 or binding["elements"] < 1
        or binding["stride"] < 4 or binding["stride"] % 4
        or binding["profile"] not in ("zero", "hdr-feedback", "hdr-setting")
        for binding in structured_outputs
    ) or structured_output_elements < 0 or structured_output_stride < 4 \
            or structured_output_stride % 4:
        raise ToolchainError("invalid structured-buffer binding")
    samplers = execution.get(
        "samplers",
        [
            {
                "slot": int(execution.get("sampler_slot", 6)),
                "filter": str(execution.get("filter", "linear")),
            }
        ],
    )
    samplers = [
        {
            "slot": int(sampler["slot"]),
            "filter": str(sampler["filter"]),
            "comparison": bool(sampler.get("comparison", False)),
        }
        for sampler in samplers
    ]
    constant_buffers = execution.get(
        "constant_buffers",
        [
            {
                "slot": int(execution.get("constant_buffer_slot", 5)),
                "profile": str(
                    execution.get("constant_profile", "projection")
                ),
            }
        ],
    )
    constant_buffers = [
        {"slot": int(binding["slot"]), "profile": str(binding["profile"])}
        for binding in constant_buffers
    ]
    output_kind = str(execution.get("output", "color"))
    output_components = int(
        execution.get("output_components", 1 if output_kind == "depth" else 4)
    )
    output_targets = int(execution.get("output_targets", 1))
    thread_group = [int(value) for value in execution.get("thread_group", [1, 1, 1])]
    if any(sampler["filter"] not in ("point", "linear") for sampler in samplers):
        raise ToolchainError("unsupported sampler filter")
    if output_kind not in ("color", "depth"):
        raise ToolchainError(f"unsupported fuzz output: {output_kind}")
    if any(
        binding["profile"] not in (
            "projection", "random", "composition", "composition-fog", "hdr", "rect", "cluster", "reflection",
            "bloom", "ao", "fsr-easu", "fsr-rcas", "index", "auto-hdr",
            "cloud"
        )
        for binding in constant_buffers
    ):
        raise ToolchainError("unsupported constant-buffer profile")
    if output_components < 1 or output_components > 4:
        raise ToolchainError("output component count must be between one and four")
    if output_targets < 1 or output_targets > 8:
        raise ToolchainError("output target count must be between one and eight")
    if output_kind == "depth" and output_targets != 1:
        raise ToolchainError("depth execution requires one output target")
    if len(thread_group) != 3 or any(value < 1 for value in thread_group):
        raise ToolchainError("thread group must contain three positive sizes")
    compiler = D3DCompiler()
    candidate, source = compile_semantic_shader(corpus, manifest, shader, compiler)
    baseline_path = corpus / shader["dxbc_path"]
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
        temporary_path = Path(temporary)
        candidate_path = Path(temporary) / "semantic.dxbc"
        candidate_path.write_bytes(candidate)
        if shader_stage == "compute":
            vertex_path = None
            vertex_selector = None
        elif vertex is None:
            harness_name = str(execution["vertex_harness"])
            vertex_path = temporary_path / f"{harness_name}.dxbc"
            vertex_bytecode = compiler.compile(
                VERTEX_HARNESSES[harness_name], "harnessVS", "vs_5_0"
            )
            vertex_path.write_bytes(vertex_bytecode)
            vertex_selector = f"harness:{harness_name}"
        else:
            vertex_path = corpus / vertex["dxbc_path"]
            vertex_selector = vertex["selector"]
        control = _invoke_harness(
            harness_path,
            vertex_path,
            baseline_path,
            baseline_path,
            cases=min(cases, 8),
            seed=seed,
            width=width,
            height=height,
            dispatch_width=dispatch_width,
            dispatch_height=dispatch_height,
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
            ulp_tolerance=0,
            texture_slots=texture_slots,
            texture_kinds=texture_kinds,
            texture_mips=texture_mips,
            texture_slices=texture_slices,
            smooth_texture_slots=smooth_texture_slots,
            structured_inputs=structured_inputs,
            structured_output_elements=structured_output_elements,
            structured_output_stride=structured_output_stride,
            structured_outputs=structured_outputs,
            samplers=samplers,
            constant_buffers=constant_buffers,
            output_kind=output_kind,
            output_components=output_components,
            output_targets=output_targets,
            shader_stage=shader_stage,
            thread_group=thread_group,
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
            dispatch_width=dispatch_width,
            dispatch_height=dispatch_height,
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
            ulp_tolerance=ulp_tolerance,
            texture_slots=texture_slots,
            texture_kinds=texture_kinds,
            texture_mips=texture_mips,
            texture_slices=texture_slices,
            smooth_texture_slots=smooth_texture_slots,
            structured_inputs=structured_inputs,
            structured_output_elements=structured_output_elements,
            structured_output_stride=structured_output_stride,
            structured_outputs=structured_outputs,
            samplers=samplers,
            constant_buffers=constant_buffers,
            output_kind=output_kind,
            output_components=output_components,
            output_targets=output_targets,
            shader_stage=shader_stage,
            thread_group=thread_group,
            failure_dir=failure_dir,
            warp=warp,
        )

    report = {
        "source_name": source_name,
        "vertex_selector": vertex_selector,
        f"{shader_stage}_selector": shader["selector"],
        "semantic_recipe": shader["semantic_recipe"],
        "semantic_execution": {
            "texture_slots": texture_slots,
            "texture_kinds": texture_kinds,
            "texture_mips": texture_mips,
            "texture_slices": texture_slices,
            "smooth_texture_slots": smooth_texture_slots,
            "structured_inputs": structured_inputs,
            "structured_output_elements": structured_output_elements,
            "structured_output_stride": structured_output_stride,
            "structured_outputs": structured_outputs,
            "samplers": samplers,
            "constant_buffers": constant_buffers,
            "output": output_kind,
            "output_components": output_components,
            "output_targets": output_targets,
            "thread_group": thread_group,
            "dispatch_width": dispatch_width,
            "dispatch_height": dispatch_height,
            "ulp_tolerance": ulp_tolerance,
        },
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
