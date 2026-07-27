"""Recognize and validate the cloud ray-march and temporal resolve passes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from .common import emit_validated_module


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
1. Reconstruct a normalized world-space view ray and intersect the spherical
   cloud shell around the planet.
2. March the occupied shell interval through the 3D cloud volume, combining
   the weather map, height envelope and animated density erosion.
3. Sample the directional-light lookup along occupied steps and integrate
   front-to-back radiance and transmittance with early opacity termination.
4. Convert the integrated density through the time-of-day light palette and
   write cloud color plus the compact depth/coverage history target.
5. High quality additionally rejects rays hidden by scene depth, jitters the
   march from screen noise, and reprojects the cloud point into the cache.
6. Valid temporal history is motion/depth checked and blended with a bounded
   response rate; low-step mode emits a fresh integration without history.

The executable block stays instruction-ordered because the ray integration,
early exits and temporal accumulation are sensitive to FMA reassociation.
*/
"""


DEPTH_GUARD = """  uint2 depthMaxPixel = cb_clouds.vuDepthSize;
  int2 depthCenter = int2(v1.xy * float2(depthMaxPixel));
  const int2 depthOffsets[9] = {
    int2(-4, -4), int2(0, -4), int2(4, -4),
    int2(-4,  0), int2(0,  0), int2(4,  0),
    int2(-4,  4), int2(0,  4), int2(4,  4)
  };
  bool cloudPixelVisible = false;
  [unroll]
  for (uint depthSample = 0; depthSample < 9; ++depthSample) {
    if (!cloudPixelVisible) {
      uint2 depthPixel = min(depthMaxPixel, (uint2)(depthCenter + depthOffsets[depthSample]));
      float deviceDepth = tDepth.Load(int3(depthPixel, 0));
      float viewDepth = cb_xViewToProjection._m23
                      / (cb_xViewToProjection._m22 + deviceDepth);
      cloudPixelVisible = viewDepth >= cb_clouds.fDepthCheckDistance;
    }
  }
  if (!cloudPixelVisible) {
    o0 = 0;
    o1 = 0;
    return;
  }
"""


def _restore_depth_guard(source: str) -> str:
    """Replace 3Dmigoto's float-typed integer neighborhood state."""
    start = source.index("  r0.xy = asuint(cb_clouds.vuDepthSize.xy);")
    end = source.index("  r0.xy = v1.xy * float2(1,-1) + float2(0,1);", start)
    return source[:start] + DEPTH_GUARD + source[end:]


def apply_post_clouds_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_clouds"]
    if len(shaders) != 3 or {shader["entry_point"] for shader in shaders} != {
        "triangleVS", "mainPS"
    }:
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(
        (staging / "hlsl" / "post_clouds.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    temporal_selector = next(
        shader["selector"] for shader in shaders if "PS_TEMPORAL" in shader["defines"]
    )
    expanded[temporal_selector] = _restore_depth_guard(expanded[temporal_selector])
    bodies = {
        shader["selector"]: SEMANTIC_PHASE_MAP + expanded[shader["selector"]]
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        if shader["stage"] != "pixel":
            continue
        temporal = "PS_TEMPORAL" in shader["defines"]
        executions[shader["selector"]] = {
            "kind": "fullscreen_uv",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": [0, 1, 2, 3, 4, 5, 7] if temporal else [0, 1, 2, 3],
            "texture_kinds": (
                ["2d", "2d", "3d", "2d", "2d", "2d", "2d"]
                if temporal else ["2d", "2d", "3d", "2d"]
            ),
            "samplers": [
                {"slot": 3, "filter": "linear"},
                {"slot": 4, "filter": "linear"},
            ] + ([{"slot": 6, "filter": "linear"}] if temporal else []),
            "constant_buffers": [
                {"slot": 5, "profile": "projection"},
                {"slot": 12, "profile": "cloud"},
            ],
            "output": "color",
            "output_components": 4,
            "output_targets": 2,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="post_clouds", bodies=bodies, executions=executions,
    )
