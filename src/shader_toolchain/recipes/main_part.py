"""Recognize the complete part material and animation permutation family."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import (
    ensure_asset_include,
    ensure_recovered_cbuffer_include,
    replace_cbuffer_with_include,
)
from .main_character import apply_character_material_recipe
from .main_part_families import lift_main_part_vertex_family
from .main_part_pixel_families import lift_main_part_pixel_family
from .main_part_picking_families import lift_main_part_picking_family
from .main_part_depth_families import lift_main_part_depth_family
from .main_part_overlay_families import lift_main_part_overlay_family
from .main_part_early_gforward_families import (
    lift_main_part_early_gforward_family,
)
from .main_part_transparent_families import lift_main_part_transparent_family
from .main_part_glass_surface_families import (
    lift_main_part_glass_surface_family,
)


MORPH_VERTEX_REQUIRED_DEFINES = {
    "VERTEX_SHADER", "VS_FULL_TRANSFORM",
    "VS_INPUT_TANGENTS", "VS_INPUT_UV1", "VS_POSE_0_ANIM",
}
MORPH_VERTEX_TRANSFER_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_UV1",
    "TRANSFER_VIEW_POSITION",
}

MORPH_CLIP_VERTEX_DEFINES = {
    "VERTEX_SHADER", "VS_FULL_TRANSFORM", "VS_POSE_0_ANIM",
}

RIGID_UV_STEP_SURFACE_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_UV0", "TRANSFER_VIEW_POSITION", "VERTEX_SHADER",
    "VS_FULL_TRANSFORM", "VS_UV0_STEP",
}

TRANSLUCENT_PREVIEW_FLOW_DEFINES = {
    "PIXEL_SHADER", "PS_AO_UV0", "PS_ASG_TEX", "PS_CUSTOM_TILING",
    "PS_FLOW_MAP_UV0", "PS_MATERIAL_TRANSLUCENT", "PS_PERM_PREVIEW",
    "PS_TRANSLUCENT_MAP_ADD", "TRANSFER_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

LEGACY_GLASS_BEHIND_HIGH_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_FLIP_BACKFACE_NORMALS", "PS_GLASS",
    "PS_LEGACY_GLASS", "PS_LEGACY_GLASS_BLOCKS", "PS_NOR_TEX",
    "PS_PERM_TRANSPARANT_BEHIND", "PS_REFLECTION_OFF", "PS_REFRACTION",
    "PS_SHADER_QUALITY_HIGH", "PS_TRANSPARENT_TINTED", "TRANSFER_COLOR",
    "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

LEGACY_GLASS_SURFACE_MULTI_MEDIUM_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_FLIP_BACKFACE_NORMALS", "PS_GLASS",
    "PS_LEGACY_GLASS", "PS_NOR_TEX", "PS_PERM_TRANSPARANT_SURFACE",
    "PS_REFLECTION_MULTI", "PS_REFRACTION", "PS_SHADER_QUALITY_MEDIUM",
    "PS_TRANSPARENT_TINTED", "TRANSFER_COLOR", "TRANSFER_FOG_COLOR",
    "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS",
    "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

LEGACY_GLASS_SURFACE_MULTI_ALPHA_DEFINES = {
    "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX",
    "PS_FLIP_BACKFACE_NORMALS", "PS_GLASS", "PS_LEGACY_GLASS",
    "PS_NOR_TEX", "PS_PERM_TRANSPARANT_SURFACE", "PS_REFLECTION_MULTI",
    "PS_REFRACTION", "PS_TRANSPARENT_TINTED", "TRANSFER_COLOR",
    "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

LEGACY_GLASS_SURFACE_OFF_ALPHA_DEFINES = (
    LEGACY_GLASS_SURFACE_MULTI_ALPHA_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_OFF"}
)

LEGACY_GLASS_SURFACE_SINGLE_ALPHA_DEFINES = (
    LEGACY_GLASS_SURFACE_MULTI_ALPHA_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_SINGLE"}
)

LEGACY_GLASS_SURFACE_MULTI_PLAIN_DEFINES = (
    LEGACY_GLASS_SURFACE_MULTI_ALPHA_DEFINES - {"PS_ALPHA_CUTOFF"}
)
LEGACY_GLASS_SURFACE_OFF_PLAIN_DEFINES = (
    LEGACY_GLASS_SURFACE_MULTI_PLAIN_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_OFF"}
)
LEGACY_GLASS_SURFACE_SINGLE_PLAIN_DEFINES = (
    LEGACY_GLASS_SURFACE_MULTI_PLAIN_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_SINGLE"}
)

TINTED_GLASS_SURFACE_MULTI_ALPHA_DEFINES = (
    LEGACY_GLASS_SURFACE_MULTI_ALPHA_DEFINES
    - {"PS_LEGACY_GLASS", "PS_REFRACTION"}
)
TINTED_GLASS_SURFACE_OFF_ALPHA_DEFINES = (
    TINTED_GLASS_SURFACE_MULTI_ALPHA_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_OFF"}
)
TINTED_GLASS_SURFACE_SINGLE_ALPHA_DEFINES = (
    TINTED_GLASS_SURFACE_MULTI_ALPHA_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_SINGLE"}
)

TINTED_TRANSMISSION_GLASS_MULTI_DEFINES = (
    TINTED_GLASS_SURFACE_MULTI_ALPHA_DEFINES
    - {"PS_ALPHA_CUTOFF"}
    | {"PS_REFRACTION", "PS_TRANSMISSION"}
)
TINTED_TRANSMISSION_GLASS_OFF_DEFINES = (
    TINTED_TRANSMISSION_GLASS_MULTI_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_OFF"}
)
TINTED_TRANSMISSION_GLASS_SINGLE_DEFINES = (
    TINTED_TRANSMISSION_GLASS_MULTI_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_SINGLE"}
)

TINTED_DISSOLVE_GLASS_MULTI_DEFINES = (
    TINTED_GLASS_SURFACE_MULTI_ALPHA_DEFINES
    | {"PS_DISSOLVE_UV1", "TRANSFER_CUTOFF", "TRANSFER_UV1"}
)
TINTED_DISSOLVE_GLASS_OFF_DEFINES = (
    TINTED_DISSOLVE_GLASS_MULTI_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_OFF"}
)
TINTED_DISSOLVE_GLASS_SINGLE_DEFINES = (
    TINTED_DISSOLVE_GLASS_MULTI_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_SINGLE"}
)

STANDARD_UNRESPONSIVE_GLASS_MULTI_DEFINES = (
    TINTED_GLASS_SURFACE_MULTI_ALPHA_DEFINES
    - {"PS_TRANSPARENT_TINTED"}
    | {"PS_REFRACTION"}
)
STANDARD_UNRESPONSIVE_GLASS_OFF_DEFINES = (
    STANDARD_UNRESPONSIVE_GLASS_MULTI_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_OFF"}
)
STANDARD_UNRESPONSIVE_GLASS_SINGLE_DEFINES = (
    STANDARD_UNRESPONSIVE_GLASS_MULTI_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_SINGLE"}
)

STANDARD_GEOMETRIC_GLASS_MULTI_DEFINES = (
    STANDARD_UNRESPONSIVE_GLASS_MULTI_DEFINES
    - {"PS_NOR_TEX", "TRANSFER_TANGENTS"}
)
STANDARD_GEOMETRIC_GLASS_OFF_DEFINES = (
    STANDARD_GEOMETRIC_GLASS_MULTI_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_OFF"}
)
STANDARD_GEOMETRIC_GLASS_SINGLE_DEFINES = (
    STANDARD_GEOMETRIC_GLASS_MULTI_DEFINES
    - {"PS_REFLECTION_MULTI"}
    | {"PS_REFLECTION_SINGLE"}
)

UV_ANIMATION_POSE0_CUTOFF_DEFINES = {
    "ALPHA", "TRANSFER_CUTOFF", "TRANSFER_UV0", "VERTEX_SHADER",
    "VS_FULL_TRANSFORM", "VS_INPUT_TANGENTS", "VS_POSE_0_ANIM",
    "VS_UV_ANIM",
}

WATER_SURFACE_SINGLE_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_PERM_TRANSPARANT_SURFACE",
    "PS_REFLECTION_SINGLE", "PS_WATER", "TRANSFER_COLOR",
    "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

VISUALIZATION_ALPHA_ASG_NORMAL_DEFINES = {
    "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX",
    "PS_FLIP_BACKFACE_NORMALS", "PS_NOR_TEX", "PS_PERM_VISUALIZATION",
    "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

VISUALIZATION_LOW_METAL_NORMAL_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_MATERIAL_METAL",
    "PS_METAL_REMAP_GLOSS_REFLECT", "PS_NOR_TEX",
    "PS_PERM_VISUALIZATION", "PS_SHADER_QUALITY_LOW", "TRANSFER_COLOR",
    "TRANSFER_NORMAL", "TRANSFER_OBJECT_TANGENT", "TRANSFER_SCREEN_UV",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_UV1",
    "TRANSFER_VIEW_POSITION",
}

GBUFFER_ASG_NORMAL_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_NOR_TEX", "PS_PERM_GBUFFER",
    "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_TANGENTS",
    "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

GBUFFER_DISSOLVE_UV0_DEFINES = {
    "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX", "PS_DISSOLVE_UV0",
    "PS_FLIP_BACKFACE_NORMALS", "PS_PERM_GBUFFER", "TRANSFER_COLOR",
    "TRANSFER_CUTOFF", "TRANSFER_NORMAL", "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION",
}

WATER_SURFACE_SINGLE_HIGH_DISSOLVE_DEFINES = {
    "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX", "PS_DISSOLVE_UV1",
    "PS_FBDRF_DIF", "PS_FLIP_BACKFACE_NORMALS", "PS_NOR_TEX",
    "PS_PERM_TRANSPARANT_SURFACE", "PS_REFLECTION_SINGLE",
    "PS_SHADER_QUALITY_HIGH", "PS_WATER", "TRANSFER_COLOR",
    "TRANSFER_CUTOFF", "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS", "TRANSFER_UV0",
    "TRANSFER_UV1", "TRANSFER_VIEW_POSITION",
}

WATER_SURFACE_SINGLE_HIGH_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_FBDRF_DIF",
    "PS_PERM_TRANSPARANT_SURFACE", "PS_REFLECTION_SINGLE",
    "PS_SHADER_QUALITY_HIGH", "PS_WATER", "TRANSFER_COLOR",
    "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

WATER_SURFACE_MULTI_HIGH_ALPHA_DEFINES = {
    "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX",
    "PS_FLIP_BACKFACE_NORMALS", "PS_PERM_TRANSPARANT_SURFACE",
    "PS_REFLECTION_MULTI", "PS_SHADER_QUALITY_HIGH", "PS_WATER",
    "TRANSFER_COLOR", "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS", "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION",
}

GLASS_CUSTOM_TILING_BEHIND_LOW_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_ASG_UV1", "PS_CUSTOM_TILING",
    "PS_DIF_UV1", "PS_FLIP_BACKFACE_NORMALS", "PS_GLASS",
    "PS_NOR_D_TEX", "PS_NOR_D_UV1", "PS_NOR_TEX",
    "PS_PERM_TRANSPARANT_BEHIND", "PS_REFLECTION_OFF", "PS_REFRACTION",
    "PS_TRANSPARENT_TINTED", "TRANSFER_COLOR", "TRANSFER_FOG_COLOR",
    "TRANSFER_NORMAL", "TRANSFER_OCCLUSION", "TRANSFER_SCREEN_UV",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_UV1",
    "TRANSFER_VIEW_POSITION",
}

GLASS_SET_PARAMS_BEHIND_SINGLE_LOW_DEFINES = {
    "PIXEL_SHADER", "PS_DEPTH_BLUR_DISTANCE", "PS_FLIP_BACKFACE_NORMALS",
    "PS_GLASS", "PS_MAT_CAP_DIF", "PS_PERM_TRANSPARANT_BEHIND",
    "PS_REFLECTION_SINGLE", "PS_REFRACTION", "PS_SET_PARAMS",
    "PS_TRANSMISSION", "TRANSFER_COLOR", "TRANSFER_FOG_COLOR",
    "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV", "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION",
}

PACKED_TRANSFORM_MORPH_UV1_CUTOFF_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_CUTOFF", "TRANSFER_NORMAL", "TRANSFER_UV0",
    "TRANSFER_UV1", "TRANSFER_VIEW_POSITION", "VERTEX_SHADER",
    "VS_INPUT_UV1", "VS_POSE_0_ANIM",
}

PACKED_TRANSFORM_MORPH_SURFACE_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_OCCLUSION",
    "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS", "TRANSFER_UV0",
    "TRANSFER_UV1", "TRANSFER_VIEW_POSITION", "VERTEX_SHADER",
    "VS_INPUT_COLOR", "VS_INPUT_TANGENTS", "VS_INPUT_UV1",
    "VS_OCCLUSION_CHANNEL_R", "VS_POSE_0_ANIM",
}

PACKED_DUAL_MORPH_OBJECT_TANGENT_DEFINES = {
    "TRANSFER_OBJECT_TANGENT", "VERTEX_SHADER", "VS_INPUT_TANGENTS",
    "VS_POSE_0_ANIM", "VS_POSE_1_ANIM",
}

PACKED_TRANSFORM_FOG_SURFACE_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS", "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION", "VERTEX_SHADER", "VS_INPUT_TANGENTS",
}

DUAL_MORPH_PARALLAX_PLANE_DEFINES = {
    "PARALLAX_PLANE", "TRANSFER_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS", "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION", "VERTEX_SHADER", "VS_FULL_TRANSFORM",
    "VS_INPUT_TANGENTS", "VS_POSE_0_ANIM", "VS_POSE_1_ANIM",
}

TRIPLE_MORPH_OCCLUSION_SURFACE_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_OCCLUSION",
    "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS", "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION", "VERTEX_SHADER", "VS_FULL_TRANSFORM",
    "VS_INPUT_COLOR", "VS_INPUT_TANGENTS", "VS_OCCLUSION_CHANNEL_G",
    "VS_POSE_0_ANIM", "VS_POSE_1_ANIM", "VS_POSE_2_ANIM", "VS_PUSH",
    "VS_PUSH_PER_VERTEX",
}

RIGID_TANGENT_UV1_CUTOFF_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_CUTOFF", "TRANSFER_NORMAL",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_UV1",
    "TRANSFER_VIEW_POSITION", "VERTEX_SHADER", "VS_FULL_TRANSFORM",
    "VS_INPUT_TANGENTS", "VS_INPUT_UV1",
}

PACKED_UV_SCROLL_UV1_CUTOFF_DEFINES = {
    "TRANSFER_CUTOFF", "TRANSFER_SCREEN_UV", "TRANSFER_UV0",
    "TRANSFER_UV1", "VERTEX_SHADER", "VS_INPUT_TANGENTS",
    "VS_INPUT_UV1", "VS_UV0_SCROLL",
}

WAVE_TRIPLE_MORPH_COLOR_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_UV0", "VERTEX_SHADER",
    "VS_FULL_TRANSFORM", "VS_POSE_0_ANIM", "VS_POSE_1_ANIM",
    "VS_POSE_2_ANIM", "VS_WAVE",
}

WAVE_TRIPLE_MORPH_UV_DEFINES = {
    "TRANSFER_UV0", "VERTEX_SHADER", "VS_FULL_TRANSFORM",
    "VS_POSE_0_ANIM", "VS_POSE_1_ANIM", "VS_POSE_2_ANIM", "VS_WAVE",
}

WAVE_MORPH_SURFACE_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_UV0", "TRANSFER_VIEW_POSITION", "VERTEX_SHADER",
    "VS_FULL_TRANSFORM", "VS_POSE_0_ANIM", "VS_WAVE",
}

PACKED_WAVE_PICKING_SCROLL_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_UV0", "VERTEX_SHADER",
    "VS_INPUT_TANGENTS", "VS_PICKING_BUFFER", "VS_UV0_SCROLL",
    "VS_WAVE_NO_SCALE",
}

PACKED_SCALED_WAVE_PICKING_SCROLL_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_UV0", "VERTEX_SHADER",
    "VS_INPUT_TANGENTS", "VS_PICKING_BUFFER", "VS_UV0_SCROLL", "VS_WAVE",
}

PACKED_SCALED_WAVE_UV_DEFINES = {
    "TRANSFER_UV0", "VERTEX_SHADER", "VS_INPUT_TANGENTS", "VS_WAVE",
}

LASER_BEHIND_FULL_DEFINES = {
    "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_FLIP_BACKFACE_NORMALS",
    "PS_LASER", "PS_LASER_FADE", "PS_LASER_FOG", "PS_LASER_FRESNEL",
    "PS_LASER_INTERSECT", "PS_LASER_MASK",
    "PS_LASER_REFRACTION_SCAN_LINES", "PS_LASER_SCAN_LINES",
    "PS_LASER_TEXTURE", "PS_PERM_TRANSPARANT_BEHIND", "PS_REFLECTION_OFF",
    "TRANSFER_COLOR", "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

LASER_BEHIND_BASIC_DEFINES = {
    "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_FLIP_BACKFACE_NORMALS",
    "PS_LASER", "PS_LASER_FADE", "PS_LASER_FOG", "PS_LASER_MASK",
    "PS_LASER_TEXTURE", "PS_PERM_TRANSPARANT_BEHIND", "PS_REFLECTION_OFF",
    "TRANSFER_COLOR", "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

GLASS_SURFACE_SINGLE_TINTED_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_FLIP_BACKFACE_NORMALS", "PS_GLASS",
    "PS_NOR_TEX", "PS_PERM_TRANSPARANT_SURFACE", "PS_REFLECTION_SINGLE",
    "PS_REFRACTION", "PS_TRANSMISSION", "PS_TRANSPARENT_TINTED",
    "TRANSFER_COLOR", "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS", "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION",
}

GLASS_BEHIND_HIGH_DEPTH_GLOW_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_DEPTH_BLUR_DISTANCE",
    "PS_FLIP_BACKFACE_NORMALS", "PS_GLASS", "PS_NOR_TEX",
    "PS_PERM_TRANSPARANT_BEHIND", "PS_REFLECTION_OFF", "PS_REFRACTION",
    "PS_RESPONSIVE_GLOW", "PS_SHADER_QUALITY_HIGH", "PS_TRANSMISSION",
    "TRANSFER_COLOR", "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS", "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION",
}

GLASS_DISSOLVE_BEHIND_SINGLE_DEFINES = {
    "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX",
    "PS_DEPTH_BLUR_DISTANCE", "PS_DISSOLVE_UV0",
    "PS_FLIP_BACKFACE_NORMALS", "PS_GLASS", "PS_NOR_TEX",
    "PS_PERM_TRANSPARANT_BEHIND", "PS_REFLECTION_SINGLE",
    "PS_REFRACTION", "PS_RESPONSIVE_GLOW", "PS_TRANSMISSION",
    "TRANSFER_COLOR", "TRANSFER_CUTOFF", "TRANSFER_FOG_COLOR",
    "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS",
    "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

VISUALIZATION_DEPTH_GLASS_PARAMS_DEFINES = {
    "PIXEL_SHADER", "PS_DEPTH_BLUR_DISTANCE", "PS_FLIP_BACKFACE_NORMALS",
    "PS_GLASS", "PS_PERM_VISUALIZATION", "PS_REFRACTION", "PS_SET_PARAMS",
    "PS_TRANSMISSION", "TRANSFER_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

PACKED_WAVE_DUAL_MORPH_UV_SCROLL_DEFINES = {
    "TRANSFER_CUTOFF", "TRANSFER_UV0", "TRANSFER_UV1", "VERTEX_SHADER",
    "VS_INPUT_TANGENTS", "VS_INPUT_UV1", "VS_POSE_0_ANIM",
    "VS_POSE_1_ANIM", "VS_UV0_SCROLL", "VS_WAVE_NO_SCALE",
}

FULL_TRANSFORM_WAVE_SCROLL_SCREEN_DEFINES = {
    "TRANSFER_SCREEN_UV", "TRANSFER_UV0", "VERTEX_SHADER",
    "VS_FULL_TRANSFORM", "VS_INPUT_TANGENTS", "VS_UV0_SCROLL",
    "VS_WAVE_NO_SCALE",
}

TRIPLE_MORPH_UV_ANIMATION_DEFINES = {
    "TRANSFER_UV0", "VERTEX_SHADER", "VS_FULL_TRANSFORM",
    "VS_INPUT_TANGENTS", "VS_POSE_0_ANIM", "VS_POSE_1_ANIM",
    "VS_POSE_2_ANIM", "VS_UV_ANIM",
}

PACKED_TRIPLE_MORPH_UV_ANIMATION_SURFACE_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_UV0", "TRANSFER_VIEW_POSITION", "VERTEX_SHADER",
    "VS_LASER_COLOR", "VS_POSE_0_ANIM", "VS_POSE_1_ANIM",
    "VS_POSE_2_ANIM", "VS_UV_ANIM",
}

GLASS_OPAQUE_FORWARD_MEDIUM_DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_FLIP_BACKFACE_NORMALS",
    "PS_GLASS_OPAQUE", "PS_NOR_TEX", "PS_PERM_GFORWARD",
    "PS_REFLECTION_OFF", "PS_RESPONSIVE_GLOW",
    "PS_SHADER_QUALITY_MEDIUM", "PS_TEMPORAL_AO_CASCADE",
    "PS_TRANSMISSION", "TRANSFER_COLOR", "TRANSFER_FOG_COLOR",
    "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS",
    "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}

LASER_DISPLACEMENT_PACKED_POSE_PICKING_DEFINES = {
    "TRANSFER_COLOR", "TRANSFER_UV0", "VERTEX_SHADER", "VS_LASER_COLOR",
    "VS_LASER_DISPLACEMENT", "VS_LASER_FADE", "VS_LASER_FLICKER",
    "VS_LASER_GLITCH", "VS_LASER_SLICES", "VS_LASER_WAVE",
    "VS_PICKING_BUFFER", "VS_POSE_0_ANIM",
}


def is_main_part_morph_vertex(defines: list[str]) -> bool:
    """Recognize pose-0 morph vertices served by the shared output model."""
    values = set(defines)
    return (
        MORPH_VERTEX_REQUIRED_DEFINES <= values
        and values <= MORPH_VERTEX_REQUIRED_DEFINES
        | MORPH_VERTEX_TRANSFER_DEFINES
    )


def is_main_part_morph_clip_vertex(defines: list[str]) -> bool:
    """Recognize the minimal explicit-LTW one-pose clip permutation."""
    return set(defines) == MORPH_CLIP_VERTEX_DEFINES


def is_main_part_rigid_uv_step_surface(defines: list[str]) -> bool:
    """Recognize rigid explicit-LTW vertices with discrete UV0 stepping."""
    return set(defines) == RIGID_UV_STEP_SURFACE_DEFINES


def is_main_part_translucent_preview_flow(defines: list[str]) -> bool:
    """Recognize the flow-mapped translucent preview pixel permutation."""
    return set(defines) == TRANSLUCENT_PREVIEW_FLOW_DEFINES


def is_main_part_legacy_glass_behind_high(defines: list[str]) -> bool:
    """Recognize the high-quality legacy tinted-glass behind pass."""
    return set(defines) == LEGACY_GLASS_BEHIND_HIGH_DEFINES


def is_main_part_legacy_glass_surface_multi_medium(defines: list[str]) -> bool:
    """Recognize medium-quality legacy glass with clustered multi-reflections."""
    return set(defines) == LEGACY_GLASS_SURFACE_MULTI_MEDIUM_DEFINES


def is_main_part_legacy_glass_surface_multi_alpha(defines: list[str]) -> bool:
    """Recognize low legacy glass policies with no sampled reflection."""
    return set(defines) in (
        LEGACY_GLASS_SURFACE_MULTI_ALPHA_DEFINES,
        LEGACY_GLASS_SURFACE_OFF_ALPHA_DEFINES,
    )


def is_main_part_legacy_glass_surface_single_alpha(defines: list[str]) -> bool:
    """Recognize low legacy glass using the global single reflection layer."""
    return set(defines) == LEGACY_GLASS_SURFACE_SINGLE_ALPHA_DEFINES


def main_part_legacy_glass_surface_plain_asset(
    defines: list[str],
) -> str | None:
    """Select a typed low-quality, non-cutout legacy reflection policy."""
    values = set(defines)
    policies = (
        (LEGACY_GLASS_SURFACE_MULTI_PLAIN_DEFINES,
         "main_part_legacy_glass_surface_plain_multi.hlsl"),
        (LEGACY_GLASS_SURFACE_OFF_PLAIN_DEFINES,
         "main_part_legacy_glass_surface_plain_off.hlsl"),
        (LEGACY_GLASS_SURFACE_SINGLE_PLAIN_DEFINES,
         "main_part_legacy_glass_surface_plain_single.hlsl"),
    )
    return next((asset for policy, asset in policies if values == policy), None)


def main_part_tinted_glass_surface_alpha_asset(
    defines: list[str],
) -> str | None:
    """Select the low tinted-glass reflection policy."""
    values = set(defines)
    policies = (
        (TINTED_GLASS_SURFACE_MULTI_ALPHA_DEFINES,
         "main_part_legacy_glass_surface_basic.hlsl"),
        (TINTED_GLASS_SURFACE_OFF_ALPHA_DEFINES,
         "main_part_tinted_glass_surface_off.hlsl"),
        (TINTED_GLASS_SURFACE_SINGLE_ALPHA_DEFINES,
         "main_part_legacy_glass_surface_single.hlsl"),
    )
    return next((asset for policy, asset in policies if values == policy), None)


def main_part_tinted_transmission_glass_asset(
    defines: list[str],
) -> str | None:
    """Select tinted transmission glass by reflection policy."""
    values = set(defines)
    policies = (
        (TINTED_TRANSMISSION_GLASS_MULTI_DEFINES,
         "main_part_tinted_glass_surface_transmission_multi.hlsl"),
        (TINTED_TRANSMISSION_GLASS_OFF_DEFINES,
         "main_part_tinted_glass_surface_transmission_off.hlsl"),
        (TINTED_TRANSMISSION_GLASS_SINGLE_DEFINES,
         "main_part_tinted_glass_surface_transmission_single.hlsl"),
    )
    return next((asset for policy, asset in policies if values == policy), None)


def main_part_tinted_dissolve_glass_asset(
    defines: list[str],
) -> str | None:
    """Select UV1-dissolve tinted glass by reflection policy."""
    values = set(defines)
    policies = (
        (TINTED_DISSOLVE_GLASS_MULTI_DEFINES,
         "main_part_tinted_glass_surface_dissolve_multi.hlsl"),
        (TINTED_DISSOLVE_GLASS_OFF_DEFINES,
         "main_part_tinted_glass_surface_dissolve_off.hlsl"),
        (TINTED_DISSOLVE_GLASS_SINGLE_DEFINES,
         "main_part_tinted_glass_surface_dissolve_single.hlsl"),
    )
    return next((asset for policy, asset in policies if values == policy), None)


def main_part_standard_unresponsive_glass_asset(
    defines: list[str],
) -> str | None:
    """Select standard non-responsive glass by reflection policy."""
    values = set(defines)
    policies = (
        (STANDARD_UNRESPONSIVE_GLASS_MULTI_DEFINES,
         "main_part_standard_glass_surface_unresponsive_multi.hlsl"),
        (STANDARD_UNRESPONSIVE_GLASS_OFF_DEFINES,
         "main_part_standard_glass_surface_unresponsive_off.hlsl"),
        (STANDARD_UNRESPONSIVE_GLASS_SINGLE_DEFINES,
         "main_part_standard_glass_surface_unresponsive_single.hlsl"),
    )
    return next((asset for policy, asset in policies if values == policy), None)


def main_part_standard_geometric_glass_asset(
    defines: list[str],
) -> str | None:
    """Select geometric-normal glass by reflection policy."""
    values = set(defines)
    policies = (
        (STANDARD_GEOMETRIC_GLASS_MULTI_DEFINES,
         "main_part_standard_glass_surface_geometric_multi.hlsl"),
        (STANDARD_GEOMETRIC_GLASS_OFF_DEFINES,
         "main_part_standard_glass_surface_geometric_off.hlsl"),
        (STANDARD_GEOMETRIC_GLASS_SINGLE_DEFINES,
         "main_part_standard_glass_surface_geometric_single.hlsl"),
    )
    return next((asset for policy, asset in policies if values == policy), None)


def is_main_part_uv_animation_pose0_cutoff(defines: list[str]) -> bool:
    """Recognize pose-0 atlas-animation vertices forwarding alpha cutoff."""
    return set(defines) == UV_ANIMATION_POSE0_CUTOFF_DEFINES


def is_main_part_water_surface_single(defines: list[str]) -> bool:
    """Recognize clustered water surfaces using one reflection layer."""
    return set(defines) == WATER_SURFACE_SINGLE_DEFINES


def is_main_part_visualization_alpha_asg_normal(defines: list[str]) -> bool:
    """Recognize the full-quality ASG-cutout visualization frontend."""
    return set(defines) == VISUALIZATION_ALPHA_ASG_NORMAL_DEFINES


def is_main_part_visualization_low_metal_normal(defines: list[str]) -> bool:
    """Recognize low-quality normal-mapped metal visualization passes."""
    return set(defines) == VISUALIZATION_LOW_METAL_NORMAL_DEFINES


def is_main_part_gbuffer_asg_normal(defines: list[str]) -> bool:
    """Recognize the textured ASG/normal opaque G-buffer permutation."""
    return set(defines) == GBUFFER_ASG_NORMAL_DEFINES


def is_main_part_gbuffer_dissolve_uv0(defines: list[str]) -> bool:
    """Recognize alpha-cutout UV0 dissolve G-buffer materials."""
    return set(defines) == GBUFFER_DISSOLVE_UV0_DEFINES


def is_main_part_water_surface_single_high_dissolve(defines: list[str]) -> bool:
    """Recognize high-quality FBDRF water with filtered UV1 dissolve."""
    return set(defines) == WATER_SURFACE_SINGLE_HIGH_DISSOLVE_DEFINES


def is_main_part_water_surface_single_high(defines: list[str]) -> bool:
    """Recognize high-quality FBDRF water without normal/dissolve layers."""
    return set(defines) == WATER_SURFACE_SINGLE_HIGH_DEFINES


def is_main_part_water_surface_multi_high_alpha(defines: list[str]) -> bool:
    """Recognize high-quality alpha-cutout water using clustered probes."""
    return set(defines) == WATER_SURFACE_MULTI_HIGH_ALPHA_DEFINES


def is_main_part_glass_custom_tiling_behind_low(defines: list[str]) -> bool:
    """Recognize custom-tiled detail-normal tinted glass behind passes."""
    return set(defines) == GLASS_CUSTOM_TILING_BEHIND_LOW_DEFINES


def is_main_part_glass_set_params_behind_single_low(
    defines: list[str],
) -> bool:
    """Recognize low-quality set-parameter glass with one reflection probe."""
    return set(defines) == GLASS_SET_PARAMS_BEHIND_SINGLE_LOW_DEFINES


def is_main_part_packed_transform_morph_uv1_cutoff(defines: list[str]) -> bool:
    """Recognize packed-transform pose vertices forwarding UV1 and cutoff."""
    return set(defines) == PACKED_TRANSFORM_MORPH_UV1_CUTOFF_DEFINES


def is_main_part_packed_transform_morph_surface(defines: list[str]) -> bool:
    """Recognize packed-transform pose vertices emitting a surface frame."""
    return set(defines) == PACKED_TRANSFORM_MORPH_SURFACE_DEFINES


def is_main_part_packed_dual_morph_object_tangent(defines: list[str]) -> bool:
    """Recognize packed two-pose vertices emitting only object tangent."""
    return set(defines) == PACKED_DUAL_MORPH_OBJECT_TANGENT_DEFINES


def is_main_part_packed_transform_fog_surface(defines: list[str]) -> bool:
    """Recognize unposed packed-transform vertices emitting vertex fog."""
    return set(defines) == PACKED_TRANSFORM_FOG_SURFACE_DEFINES


def is_main_part_dual_morph_parallax_plane(defines: list[str]) -> bool:
    """Recognize explicit-LTW dual-morph vertices with a plane anchor."""
    return set(defines) == DUAL_MORPH_PARALLAX_PLANE_DEFINES


def is_main_part_triple_morph_occlusion_surface(defines: list[str]) -> bool:
    """Recognize explicit-LTW three-pose vertices forwarding green AO."""
    return set(defines) == TRIPLE_MORPH_OCCLUSION_SURFACE_DEFINES


def is_main_part_rigid_tangent_uv1_cutoff(defines: list[str]) -> bool:
    """Recognize rigid explicit-LTW vertices with tangent frame and cutoff."""
    return set(defines) == RIGID_TANGENT_UV1_CUTOFF_DEFINES


def is_main_part_packed_uv_scroll_uv1_cutoff(defines: list[str]) -> bool:
    """Recognize packed-transform scrolling vertices forwarding UV1/cutoff."""
    return set(defines) == PACKED_UV_SCROLL_UV1_CUTOFF_DEFINES


def is_main_part_wave_triple_morph_color(defines: list[str]) -> bool:
    """Recognize wave-deformed explicit-LTW three-pose color vertices."""
    return set(defines) == WAVE_TRIPLE_MORPH_COLOR_DEFINES


def is_main_part_wave_triple_morph_uv(defines: list[str]) -> bool:
    """Recognize the UV-only sibling of the three-pose wave vertex."""
    return set(defines) == WAVE_TRIPLE_MORPH_UV_DEFINES


def is_main_part_wave_morph_surface(defines: list[str]) -> bool:
    """Recognize scale-aware wave vertices emitting a posed surface frame."""
    return set(defines) == WAVE_MORPH_SURFACE_DEFINES


def is_main_part_packed_wave_picking_scroll(defines: list[str]) -> bool:
    """Recognize packed no-scale wave vertices with picking and UV scroll."""
    return set(defines) == PACKED_WAVE_PICKING_SCROLL_DEFINES


def is_main_part_packed_scaled_wave_picking_scroll(defines: list[str]) -> bool:
    """Recognize packed scaled-wave vertices with picking and UV scroll."""
    return set(defines) == PACKED_SCALED_WAVE_PICKING_SCROLL_DEFINES


def is_main_part_packed_scaled_wave_uv(defines: list[str]) -> bool:
    """Recognize the packed scaled-wave geometry path forwarding plain UV0."""
    return set(defines) == PACKED_SCALED_WAVE_UV_DEFINES


def is_main_part_laser_behind_full(defines: list[str]) -> bool:
    """Recognize the full textured/fogged laser behind permutation."""
    return set(defines) == LASER_BEHIND_FULL_DEFINES


def is_main_part_laser_behind_basic(defines: list[str]) -> bool:
    """Recognize the masked/fogged laser behind pass without scan effects."""
    return set(defines) == LASER_BEHIND_BASIC_DEFINES


def is_main_part_glass_surface_single_tinted(defines: list[str]) -> bool:
    """Recognize tinted glass surfaces using one environment reflection."""
    return set(defines) == GLASS_SURFACE_SINGLE_TINTED_DEFINES


def is_main_part_glass_behind_high_depth_glow(defines: list[str]) -> bool:
    """Recognize high-quality depth-blurred responsive glass behind passes."""
    return set(defines) == GLASS_BEHIND_HIGH_DEPTH_GLOW_DEFINES


def is_main_part_glass_dissolve_behind_single(defines: list[str]) -> bool:
    """Recognize UV0-dissolve glass-behind passes with one probe."""
    return set(defines) == GLASS_DISSOLVE_BEHIND_SINGLE_DEFINES


def is_main_part_visualization_depth_glass_params(defines: list[str]) -> bool:
    """Recognize the depth-aware visualization compiled with glass params."""
    return set(defines) == VISUALIZATION_DEPTH_GLASS_PARAMS_DEFINES


def is_main_part_packed_wave_dual_morph_uv_scroll(defines: list[str]) -> bool:
    """Recognize packed no-scale wave vertices with two pose deltas."""
    return set(defines) == PACKED_WAVE_DUAL_MORPH_UV_SCROLL_DEFINES


def is_main_part_full_transform_wave_scroll_screen(defines: list[str]) -> bool:
    """Recognize explicit-LTW no-scale wave vertices with scrolling UV0."""
    return set(defines) == FULL_TRANSFORM_WAVE_SCROLL_SCREEN_DEFINES


def is_main_part_triple_morph_uv_animation(defines: list[str]) -> bool:
    """Recognize the minimal explicit-LTW three-pose atlas vertex path."""
    return set(defines) == TRIPLE_MORPH_UV_ANIMATION_DEFINES


def is_main_part_packed_triple_morph_uv_animation_surface(
    defines: list[str],
) -> bool:
    """Recognize packed three-pose atlas vertices with surface channels."""
    return set(defines) == PACKED_TRIPLE_MORPH_UV_ANIMATION_SURFACE_DEFINES


def is_main_part_glass_opaque_forward_medium(defines: list[str]) -> bool:
    """Recognize basic medium-quality opaque glass forward lighting."""
    return set(defines) == GLASS_OPAQUE_FORWARD_MEDIUM_DEFINES


def is_main_part_laser_displacement_packed_pose_picking(
    defines: list[str],
) -> bool:
    """Recognize packed posed procedural-laser vertices with picking output."""
    return set(defines) == LASER_DISPLACEMENT_PACKED_POSE_PICKING_DEFINES


def lift_main_part_morph_vertex(source: str) -> str:
    """Replace the register program with typed morph and frame construction."""
    source = replace_cbuffer_with_include(
        source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    source = replace_cbuffer_with_include(
        source, "CB_PERFRAME", "main_part_perframe_abi.hlsl"
    )
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    outputs = re.findall(
        r"\bout\s+(?:\w+\s+)*float\d?\s+(\w+)\s*:\s*([A-Za-z_]+)\d*",
        signature,
    )
    result_fields = {
        "SV_POSITION": "clipPosition",
        "VIEW_POSITION": "viewPosition",
        "UV": None,
        "NORMAL": "normalView",
        "TANGENT": "tangentView",
        "BITANGENT": "bitangentView",
        "VERTEXCOLOR": "color",
        "SCREEN_UV": "screenUv",
    }
    assignments = []
    uv_index = 0
    for variable, semantic in outputs:
        semantic = semantic.upper()
        if semantic == "UV":
            field = "uv0" if uv_index == 0 else "uv1"
            uv_index += 1
        else:
            field = result_fields.get(semantic)
        if field is None:
            raise RuntimeError(f"unsupported morph vertex output: {semantic}")
        assignments.append(f"  {variable} = vertex.{field};")
    return declarations + '''

#include "include/main_part_morph_vertex.hlsl"

''' + signature + '''
{
  MainPartMorphVertex vertex = EvaluateMainPartMorphVertex(
      v0, v1.xy, v2, v3, v4, v5, v6, v7, v8, v9, v10);
''' + "\n".join(assignments) + '''
}
'''


def lift_main_part_morph_clip_vertex(source: str) -> str:
    """Replace the minimal one-pose register path with its shared core."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_morph_clip_vertex.hlsl"

''' + signature + '''
{
  o0 = EvaluateMainPartMorphClipVertex(v0, v3, v5, v6, v7, v8);
}
'''


def lift_main_part_rigid_uv_step_surface(source: str) -> str:
    """Replace the rigid stepped-UV register path with shared typed phases."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_UV_STEP", "main_part_uv_step_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_morph_vertex.hlsl"
#include "include/main_part_uv_step.hlsl"
#include "include/main_part_rigid_uv_step_vertex.hlsl"

''' + signature + '''
{
  MainPartRigidUvStepVertex vertex = EvaluateMainPartRigidUvStepVertex(
      v0, v1, v2, v3, v4, v5, v6);
  o0 = vertex.clipPosition;
  o1 = vertex.viewPosition;
  o2 = vertex.uv0;
  o3 = vertex.normalView;
  o4 = vertex.color;
  o5 = vertex.screenUv;
}
'''


def lift_main_part_translucent_preview_flow(source: str) -> str:
    """Replace the register program with named translucent preview phases."""
    source = replace_cbuffer_with_include(
        source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    source = replace_cbuffer_with_include(
        source, "CB_PERFRAME", "main_part_perframe_abi.hlsl"
    )
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    output = re.search(
        r"\bout\s+float4\s+(\w+)\s*:\s*SV_Target0", signature
    )
    if output is None:
        raise RuntimeError("translucent preview has no float4 target")
    return declarations + '''

#include "include/main_part_translucent_preview.hlsl"

''' + signature + '''
{
  ''' + output.group(1) + ''' = EvaluateMainPartTranslucentPreview(
      v1, v2, v3, v4, v5);
}
'''


def lift_main_part_legacy_glass_behind_high(source: str) -> str:
    """Move the DXBC-sensitive glass evaluator behind a reusable ABI wrapper."""
    source = replace_cbuffer_with_include(
        source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    source = replace_cbuffer_with_include(
        source, "CB_PERFRAME", "main_part_perframe_abi.hlsl"
    )
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_legacy_glass_behind.hlsl"

''' + signature + '''
{
  EvaluateMainPartLegacyGlassBehind(
      v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, o0, o1);
}
'''


def lift_main_part_legacy_glass_surface_multi_medium(source: str) -> str:
    """Move clustered glass lighting/reflections behind a reusable wrapper."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_REFLECTIONS", "main_part_reflections_abi.hlsl"),
        ("Cluster", "main_part_cluster_abi.hlsl"),
        ("LightProps", "main_part_lightprops_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#define cmp -
#include "include/main_part_legacy_glass_multi.hlsl"

''' + signature + '''
{
  MainPartLegacyGlassMaterial material = EvaluateMainPartLegacyGlassMaterial(
      v1, v2, v3, v4, v5, v6, v9);
  MainPartLegacyGlassDirectional directional =
      EvaluateMainPartLegacyGlassDirectional(material);
  MainPartLegacyGlassLightingInput lightingInput;
  lightingInput.viewPosition = v1;
  lightingInput.screenUv = v7.xy;
  lightingInput.normalView = material.normalView;
  lightingInput.viewDirection = material.viewDirection;
  lightingInput.gloss = material.gloss;
  lightingInput.coverage = material.coverage;
  lightingInput.reflectionStrength = material.reflectionStrength;
  lightingInput.glossExponent = material.glossExponent;
  lightingInput.specularScale = material.specularScale;
  lightingInput.directionalColor = directional.color;
  lightingInput.directionalSpecular = directional.specular;
  MainPartLegacyGlassLighting lighting =
      EvaluateMainPartLegacyGlassMultiLighting(lightingInput);
  MainPartLegacyGlassForwardOutput result = ComposeMainPartLegacyGlassMulti(
      material, lighting, v7.xy, v8, v9 != 0);
  o0 = result.color;
  o1 = result.gForward;
}
'''


def lift_main_part_legacy_glass_surface_multi_alpha(source: str) -> str:
    """Factor the ordered basic glass composite behind stable runtime ABIs."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_legacy_glass_surface_basic.hlsl"

''' + signature + '''
{
  EvaluateMainPartLegacyGlassSurfaceBasic(
      v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, o0, o1);
}
'''


def lift_main_part_legacy_glass_surface_single_alpha(source: str) -> str:
    """Compose the low legacy frontend with the single-probe policy."""
    lifted = lift_main_part_legacy_glass_surface_multi_alpha(source)
    return lifted.replace(
        'include/main_part_legacy_glass_surface_basic.hlsl',
        'include/main_part_legacy_glass_surface_single.hlsl',
    )


def lift_main_part_legacy_glass_surface_plain(
    source: str, asset: str
) -> str:
    """Compose the non-cutout legacy material with a reflection policy."""
    lifted = lift_main_part_legacy_glass_surface_multi_alpha(source)
    return lifted.replace(
        'include/main_part_legacy_glass_surface_basic.hlsl',
        f'include/{asset}',
    )


def lift_main_part_tinted_transmission_glass(
    source: str, asset: str
) -> str:
    """Compose the shared material with tinted transmission composition."""
    lifted = lift_main_part_legacy_glass_surface_plain(source, asset)
    return lifted.replace(
        "EvaluateMainPartLegacyGlassSurfaceBasic",
        "EvaluateMainPartTintedTransmissionGlassSurface",
    )


def lift_main_part_tinted_dissolve_glass(source: str, asset: str) -> str:
    """Lift the UV1 dissolve frontend over typed tinted composition."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_abi.hlsl"),
        ("CB_DISSOLVE", "main_part_dissolve_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + f'''\n\n#include "include/{asset}"\n\n''' + signature + '''
{
  EvaluateMainPartTintedDissolveGlassSurface(
      v0, v1, v2, w2, v3, v4, v5, v6, v7, v8, v9, v10, o0, o1);
}
'''


def lift_main_part_uv_animation_pose0_cutoff(source: str) -> str:
    """Replace packed register arithmetic with the shared UV vertex model."""
    source = replace_cbuffer_with_include(
        source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    source = replace_cbuffer_with_include(
        source, "CB_PERFRAME", "main_part_perframe_abi.hlsl"
    )
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_uv_animation_vertex.hlsl"

''' + signature + '''
{
  MainPartUvAnimationVertex vertex = EvaluateMainPartUvAnimationVertex(
      v0, v1, v4, v6, v7, v8, v9);
  o0 = vertex.clipPosition;
  o1 = vertex.uv;
  o2 = vertex.cutoff;
}
'''


def lift_main_part_water_surface_single(source: str) -> str:
    """Factor the packed clustered-water program behind shared ABI includes."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("Cluster", "main_part_cluster_abi.hlsl"),
        ("LightProps", "main_part_lightprops_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#define cmp -

#include "include/main_part_water_surface_single.hlsl"

''' + signature + '''
{
  MainPartSingleWaterForwardOutput result =
      EvaluateMainPartSingleWaterSurface(v1, v2, v3, v4, v5, v6, v7, v8, v9);
  o0 = result.color;
  o1 = result.gForward;
}
'''


def lift_main_part_visualization_alpha_asg_normal(source: str) -> str:
    """Compose the reusable visualization core with its exact material frontend."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_VISUALIZATION_COLOR", "main_part_visualization_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_visualization.hlsl"

''' + signature + '''
{
  float alpha = tAsg.SampleBias(PointWrapWrap_s, v2, cb_fMipBias).x;
  if (alpha < 0.5) discard;

  float2 encodedNormal = tNor.SampleBias(
      LinearWrapWrap_s, v2, cb_fMipBias).xy;
  float3 normalTangent = DecodeMainPartVisualizationNormal(encodedNormal);
  float3 normalView = normalize(
      v4 * normalTangent.x + v5 * normalTangent.y + v3 * normalTangent.z);
  normalView = v8 ? normalView : -normalView;
  normalView = normalize(normalView);

  o0 = EvaluateMainPartVisualization(v1, normalView, v7);
}
'''


def lift_main_part_visualization_low_metal_normal(source: str) -> str:
    """Lift the reduced normal-mapped visualization response."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_VISUALIZATION_COLOR", "main_part_visualization_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_visualization_low.hlsl"

''' + signature + '''
{
  float2 encodedNormal = tNor.SampleBias(
      LinearWrapWrap_s, v2, cb_fMipBias).xy;
  float3 normalTangent = DecodeMainPartLowVisualizationNormal(encodedNormal);
  float3 normalView = v5 * normalTangent.y;
  normalView = v4 * normalTangent.x + normalView;
  normalView = v3 * normalTangent.z + normalView;
  normalView *= rsqrt(dot(normalView, normalView));
  o0 = EvaluateMainPartLowVisualization(v1, normalView, v7);
}
'''


def lift_main_part_gbuffer_asg_normal(source: str) -> str:
    """Replace register-style G-buffer packing with a typed surface result."""
    source = replace_cbuffer_with_include(
        source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_gbuffer.hlsl"

''' + signature + '''
{
  MainPartGBuffer surface = EvaluateMainPartGBuffer(
      v2, v3, v4, v5, v6);
  o0 = surface.albedo;
  o1 = surface.encodedNormal;
  o2 = surface.material;
}
'''


def lift_main_part_gbuffer_dissolve_uv0(source: str) -> str:
    """Factor UV0 dissolve selection and G-buffer packing."""
    for cbuffer, filename in (
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_DISSOLVE", "main_part_dissolve_b0_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_octahedral_normal.hlsl"
#include "include/main_part_gbuffer_dissolve.hlsl"

''' + signature + '''
{
  float4 asg = SampleMainPartDissolveGBufferAsg(v2);
  if (asg.x < 0.5)
    discard;
  MainPartDissolveBand dissolve = EvaluateMainPartDissolveBand(v2, v5);
  if (abs(dissolve.distance) >= cb_dissolve.fLength)
    discard;
  MainPartDissolveGBuffer surface = EvaluateMainPartDissolveGBuffer(
      v2, v3, v4, v6 != 0, asg, dissolve.fade);
  WriteMainPartDissolveGBuffer(surface, o0, o1, o2);
}
'''


def lift_main_part_water_surface_single_high_dissolve(source: str) -> str:
    """Factor the high-quality dissolve-water recipe behind stable ABIs."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_DISSOLVE", "main_part_dissolve_abi.hlsl"),
        ("Cluster", "main_part_cluster_abi.hlsl"),
        ("LightProps", "main_part_lightprops_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#define cmp -

#include "include/main_part_water_high_clustered_backend.hlsl"
#include "include/main_part_water_surface_single_high_dissolve.hlsl"

''' + signature + '''
{
  float3 waterAsg = SampleMainPartDissolveWaterAsg(v2);
  if (waterAsg.z < 0.5)
    discard;
  MainPartWaterDissolveBand dissolve =
      EvaluateMainPartWaterDissolveBand(w2, v9);
  if (abs(dissolve.distance) >= cb_dissolve.fLength)
    discard;
  MainPartDissolveWaterForwardOutput result =
      EvaluateMainPartWaterSurfaceSingleHighDissolve(
          v1, v2, w2, v3, v4, v5, v6, v7, v8, v9, v10,
          waterAsg, dissolve.fade);
  o0 = result.color;
  o1 = result.gForward;
}
'''


def lift_main_part_water_surface_single_high(source: str) -> str:
    """Factor high-quality FBDRF water through the shared clustered backend."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("Cluster", "main_part_cluster_abi.hlsl"),
        ("LightProps", "main_part_lightprops_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#define cmp -

#include "include/main_part_water_high_clustered_backend.hlsl"
#include "include/main_part_water_surface_single_high.hlsl"

''' + signature + '''
{
  MainPartWaterForwardOutput result = EvaluateMainPartWaterSurfaceSingleHigh(
      v1, v2, v3, v4, v5, v6, v7, v8, v9);
  o0 = result.color;
  o1 = result.gForward;
}
'''


def lift_main_part_water_surface_multi_high_alpha(source: str) -> str:
    """Split high-quality multi-probe water into reusable semantic phases."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_REFLECTIONS", "main_part_reflections_abi.hlsl"),
        ("Cluster", "main_part_cluster_abi.hlsl"),
        ("LightProps", "main_part_lightprops_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#define cmp -

#include "include/main_part_water_multi_high_frontend.hlsl"
#include "include/main_part_water_multi_high_lighting.hlsl"
#include "include/main_part_water_multi_high_composition.hlsl"

''' + signature + '''
{
  float3 waterAsg = SampleMainPartMultiWaterAsg(v2);
  if (waterAsg.x < 0.5)
    discard;
  MainPartMultiWaterMaterial material = EvaluateMainPartMultiWaterMaterial(
      v1, v2, v3, v6, v9, waterAsg);
  MainPartMultiWaterLightingInput lightingInput;
  lightingInput.viewPosition = v1;
  lightingInput.screenUv = v7.xy;
  lightingInput.normalView = material.normalView;
  lightingInput.viewDirection = material.viewDirection;
  lightingInput.roughnessComplement = material.roughnessComplement;
  lightingInput.reflectionStrength = material.reflectionStrength;
  MainPartMultiWaterLighting lighting =
      EvaluateMainPartMultiWaterLighting(lightingInput);
  MainPartMultiWaterCompositeInput compositeInput;
  compositeInput.viewPosition = v1;
  compositeInput.screenUv = v7.xy;
  compositeInput.fogColor = v8;
  compositeInput.reflection = lighting.reflection;
  compositeInput.directLight = lighting.directLight;
  compositeInput.diffuseColor = material.diffuseColor;
  compositeInput.normalViewXY = material.normalView.xy;
  compositeInput.viewDirectionXY = material.viewDirection.xy;
  compositeInput.normalDotView = material.normalDotView;
  compositeInput.viewDistance = lighting.viewDistance;
  compositeInput.reflectionStrength = material.reflectionStrength;
  compositeInput.fresnel = material.fresnel;
  compositeInput.surfaceBlend = material.surfaceBlend;
  MainPartMultiWaterForwardOutput result = ComposeMainPartMultiWater(compositeInput);
  o0 = result.color;
  o1 = result.gForward;
}
'''


def lift_main_part_glass_custom_tiling_behind_low(source: str) -> str:
    """Compose custom-tiled glass from shared frontend and output phases."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TILING", "main_part_tiling_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#define cmp -

// Typed custom-tiling material, lighting, and behind composition policy.
#include "include/main_part_glass_custom_tiling_behind_low.hlsl"

''' + signature + '''
{
  EvaluateMainPartCustomTilingBehindLow(
      v0, v1, w1, v2, w2, v3, v4, v5, v6, v7, v8, v9, o0, o1);
}
'''


def lift_main_part_glass_set_params_behind_single_low(source: str) -> str:
    """Lift low-quality set-parameter glass into its shared family body."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_abi.hlsl"),
        ("CB_OFFSET_PARAMS", "main_part_offset_params_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    declarations = declarations.replace(
        '\n\n#include "include/main_part_perframe_abi.hlsl"',
        '\n// Keep adjacent expanded ABIs lexically separated.\n'
        '#include "include/main_part_perframe_abi.hlsl"',
    ).replace(
        '\n\n#include "include/main_part_glass_abi.hlsl"',
        '\n// Keep adjacent expanded ABIs lexically separated.\n'
        '#include "include/main_part_glass_abi.hlsl"',
    ).replace(
        '\n\n#include "include/main_part_offset_params_abi.hlsl"',
        '\n// Keep adjacent expanded ABIs lexically separated.\n'
        '#include "include/main_part_offset_params_abi.hlsl"',
    ).replace(
        '\n\nSamplerState',
        '\n// End shared set-parameter glass ABIs.\n\nSamplerState',
    )
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#define cmp -

// Typed set-parameter material, lighting, reflection, and OIT policy.
#include "include/main_part_glass_set_params_behind_single.hlsl"

''' + signature + '''
{
  EvaluateMainPartSetParamsBehindSingle(
      v0, v1, v2, v3, v4, v5, v6, v7, o0, o1);
}
'''


def lift_main_part_packed_transform_morph_uv1_cutoff(source: str) -> str:
    """Replace packed LTW register arithmetic with the shared vertex model."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    signature = signature.replace(
        "float4 v1 : TEXCOORD0", "float2 v1 : TEXCOORD0"
    )
    return declarations + '''

#include "include/main_part_packed_transform_vertex.hlsl"

''' + signature + '''
{
  MainPartPackedTransformVertex vertex = EvaluateMainPartPackedTransformVertex(
      v0, v1, v2, v3, v4, v5, v6, v7);
  o0 = vertex.clipPosition;
  o1 = vertex.viewPosition;
  o2 = vertex.uv0;
  p2 = vertex.uv1;
  o3 = vertex.normalView;
  o4 = vertex.color;
  o5 = vertex.cutoff;
}
'''


def lift_main_part_packed_transform_morph_surface(source: str) -> str:
    """Lift packed LTW, pose, tangent, occlusion, and screen reconstruction."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    signature = signature.replace(
        "float4 v1 : TEXCOORD0", "float2 v1 : TEXCOORD0"
    )
    return declarations + '''

#include "include/main_part_packed_transform_vertex.hlsl"

''' + signature + '''
{
  MainPartPackedTransformSurfaceVertex vertex =
      EvaluateMainPartPackedTransformSurfaceVertex(
          v0, v1, v2, v3.x, v4, v5, v6, v7, v8, v9);
  o0 = vertex.clipPosition;
  o1 = vertex.viewPosition;
  p1 = vertex.occlusion;
  o2 = vertex.uv0;
  p2 = vertex.uv1;
  o3 = vertex.normalView;
  o4 = vertex.tangentView;
  o5 = vertex.bitangentView;
  o6 = vertex.color;
  o7 = vertex.screenUv;
}
'''


def lift_main_part_packed_dual_morph_object_tangent(source: str) -> str:
    """Lift packed LTW, two morph poses, and object-tangent selection."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_packed_transform_vertex.hlsl"
#include "include/main_part_packed_dual_morph_object_tangent_vertex.hlsl"

''' + signature + '''
{
  MainPartPackedDualMorphObjectTangentVertex vertex =
      EvaluateMainPartPackedDualMorphObjectTangentVertex(
          v0, v2, v4, v5, v6, v7, v8, v9);
  o0 = vertex.clipPosition;
  o1 = vertex.objectTangentView;
}
'''


def lift_main_part_packed_transform_fog_surface(source: str) -> str:
    """Lift packed LTW, tangent-frame, screen, and vertex-fog phases."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_vertex_fog.hlsl"
#include "include/main_part_packed_transform_vertex.hlsl"
#include "include/main_part_packed_transform_fog_vertex.hlsl"

''' + signature + '''
{
  MainPartPackedTransformFogSurfaceVertex vertex =
      EvaluateMainPartPackedTransformFogSurfaceVertex(
          v0, v1, v2, v3, v4, v5);
  o0 = vertex.clipPosition;
  o1 = vertex.viewPosition;
  o2 = vertex.uv0;
  o3 = vertex.normalView;
  o4 = vertex.tangentView;
  o5 = vertex.bitangentView;
  o6 = vertex.color;
  o7 = vertex.screenUv;
  o8 = vertex.fogColor;
}
'''


def lift_main_part_dual_morph_parallax_plane(source: str) -> str:
    """Compose two pose deltas through the shared explicit-LTW vertex model."""
    source = replace_cbuffer_with_include(
        source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    source = replace_cbuffer_with_include(
        source, "CB_PERFRAME", "main_part_perframe_abi.hlsl"
    )
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_morph_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_dual_morph_vertex.hlsl"
// End shared dual-morph helpers.

''' + signature + '''
{
  MainPartDualMorphVertex vertex = EvaluateMainPartDualMorphVertex(
      v0, v1, float2(0.0, 0.0), v2, v3, v4, v5, v6, v7,
      v8, v9, v10, v11);
  o0 = vertex.clipPosition;
  o1 = vertex.viewPosition;
  o2 = vertex.uv0;
  o3 = vertex.normalView;
  o4 = vertex.tangentView;
  o5 = vertex.bitangentView;
  o6 = vertex.color;
  o7 = vertex.screenUv;
  o8 = vertex.planeViewPosition;
}
'''


def lift_main_part_triple_morph_occlusion_surface(source: str) -> str:
    """Compose three independent pose deltas through the explicit-LTW model."""
    source = replace_cbuffer_with_include(
        source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    source = replace_cbuffer_with_include(
        source, "CB_PERFRAME", "main_part_perframe_abi.hlsl"
    )
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_morph_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_triple_morph_vertex.hlsl"
// End shared triple-morph helpers.

''' + signature + '''
{
  MainPartTripleMorphSurfaceVertex vertex =
      EvaluateMainPartTripleMorphSurfaceVertex(
          v0, v1, v2.y, v3, v4, v5, v6, v7, v8, v9, v10,
          v11, v12, v13, v14);
  o0 = vertex.clipPosition;
  o1 = vertex.viewPosition;
  o2 = vertex.uv0;
  p2 = vertex.occlusion;
  o3 = vertex.normalView;
  o4 = vertex.tangentView;
  o5 = vertex.bitangentView;
  o6 = vertex.color;
  o7 = vertex.screenUv;
}
'''


def lift_main_part_rigid_tangent_uv1_cutoff(source: str) -> str:
    """Lift rigid explicit-LTW transform, tangent frame, color, and cutoff."""
    source = replace_cbuffer_with_include(
        source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    source = replace_cbuffer_with_include(
        source, "CB_PERFRAME", "main_part_perframe_abi.hlsl"
    )
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    signature = signature.replace(
        "float4 v1 : TEXCOORD0", "float2 v1 : TEXCOORD0"
    )
    return declarations + '''

#include "include/main_part_morph_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_rigid_vertex.hlsl"
// End shared rigid vertex helpers.

''' + signature + '''
{
  MainPartRigidSurfaceVertex vertex = EvaluateMainPartRigidSurfaceVertex(
      v0, v1, v2, v3, v4, v5, v6, v7, v8);
  o0 = vertex.clipPosition;
  o1 = vertex.viewPosition;
  o2 = vertex.uv0;
  p2 = vertex.uv1;
  o3 = vertex.normalView;
  o4 = vertex.tangentView;
  o5 = vertex.bitangentView;
  o6 = vertex.color;
  o7 = vertex.cutoff;
}
'''


def lift_main_part_packed_uv_scroll_uv1_cutoff(source: str) -> str:
    """Lift packed rigid position, UV scrolling, screen UV, and cutoff."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ("CB_UV_SCROLL", "main_part_uv_scroll_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    signature = signature.replace(
        "float4 v1 : TEXCOORD0", "float2 v1 : TEXCOORD0"
    )
    return declarations + '''

#include "include/main_part_packed_transform_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_packed_uv_scroll_vertex.hlsl"
// End shared packed UV-scroll helpers.

''' + signature + '''
{
  MainPartPackedUvScrollVertex vertex = EvaluateMainPartPackedUvScrollVertex(
      v0, v1, v2, v5, v6);
  o0 = vertex.clipPosition;
  o1 = vertex.uv0;
  p1 = vertex.uv1;
  o2 = vertex.screenUv;
  o3 = vertex.cutoff;
}
'''


def lift_main_part_wave_triple_morph_color(source: str) -> str:
    """Lift wave deformation followed by three independent pose deltas."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_WAVE", "main_part_wave_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_morph_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_wave_vertex.hlsl"
// End shared wave vertex helpers.

''' + signature + '''
{
  MainPartWaveVertex vertex = EvaluateMainPartWaveVertex(
      v0, v1, v2, v3, v5, v7, v9, v10, v11, v12);
  o0 = vertex.clipPosition;
  o1 = vertex.uv0;
  o2 = vertex.color;
}
'''


def lift_main_part_wave_triple_morph_uv(source: str) -> str:
    """Reuse the three-pose wave evaluator for its UV-only permutation."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_WAVE", "main_part_wave_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_morph_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_wave_vertex.hlsl"
// End shared wave vertex helpers.

''' + signature + '''
{
  MainPartWaveVertex vertex = EvaluateMainPartWaveVertex(
      v0, v1, v2, v3, v5, v7, v9, v10, v11, v12);
  o0 = vertex.clipPosition;
  o1 = vertex.uv0;
}
'''


def lift_main_part_wave_morph_surface(source: str) -> str:
    """Lift scale-aware wave deformation followed by one posed surface."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_WAVE", "main_part_wave_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_morph_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_scaled_wave_common.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_wave_morph_surface_vertex.hlsl"
// End shared wave/morph surface helpers.

''' + signature + '''
{
  MainPartWaveMorphSurfaceVertex vertex =
      EvaluateMainPartWaveMorphSurfaceVertex(
          v0, v1, v2, v3, v4, v5, v6, v7, v8);
  o0 = vertex.clipPosition;
  o1 = vertex.viewPosition;
  o2 = vertex.uv0;
  o3 = vertex.normalView;
  o4 = vertex.color;
  o5 = vertex.screenUv;
}
'''


def lift_main_part_packed_wave_picking_scroll(source: str) -> str:
    """Lift packed transform, no-scale wave, UV scroll, and picking color."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ("CB_PICKING", "main_part_picking_abi.hlsl"),
        ("CB_UV_SCROLL", "main_part_uv_scroll_abi.hlsl"),
        ("CB_WAVE", "main_part_wave_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_packed_transform_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_packed_wave_picking_vertex.hlsl"
// End shared packed wave/picking helpers.

''' + signature + '''
{
  MainPartPackedWavePickingVertex vertex =
      EvaluateMainPartPackedWavePickingVertex(v0, v1, v2, v4, v5);
  o0 = vertex.clipPosition;
  o1 = vertex.uv0;
  o2 = vertex.color;
}
'''


def lift_main_part_packed_scaled_wave_picking_scroll(source: str) -> str:
    """Lift packed scale-aware wave geometry, UV scrolling, and picking."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ("CB_PICKING", "main_part_picking_abi.hlsl"),
        ("CB_UV_SCROLL", "main_part_uv_scroll_abi.hlsl"),
        ("CB_WAVE", "main_part_wave_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_packed_transform_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_scaled_wave_by_scale_common.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_picking_common.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_packed_scaled_wave_vertex.hlsl"
// End shared packed scaled-wave helpers.

''' + signature + '''
{
  o0 = EvaluateMainPartPackedScaledWaveClipPosition(v0, v2, v4, v5);
  o1 = v1 + frac(cb_uvScroll.vSpeed * cb_fTime);
  o2 = MainPartDecodePickingColor(v5.y);
}
'''


def lift_main_part_packed_scaled_wave_uv(source: str) -> str:
    """Lift packed scale-aware wave geometry with a plain UV0 policy."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ("CB_WAVE", "main_part_wave_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_packed_transform_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_scaled_wave_by_scale_common.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_packed_scaled_wave_vertex.hlsl"
// End shared packed scaled-wave helpers.

''' + signature + '''
{
  o0 = EvaluateMainPartPackedScaledWaveClipPosition(v0, v2, v4, v5);
  o1 = v1;
}
'''


def lift_main_part_laser_behind_full(source: str) -> str:
    """Lift the full laser behind pass into named material phases."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_LASER", "main_part_laser_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_laser_behind.hlsl"

''' + signature + '''
{
  float opaqueDepth = tDepth.SampleLevel(PointClampClamp_s, v5.xy, 0).x;
  if (v5.z < opaqueDepth) discard;
  float laserMask = tLaserMask.Sample(LinearWrapWrap_s, v2).x;
  if (laserMask < 0.100000001) discard;
  float textureIntensity = tLaser.Sample(LinearWrapWrap_s, v2).x;
  float sampledDepth = tDepth.Sample(LinearWrapWrap_s, v5.xy).x;
  MainPartLaserBehindResult laser = EvaluateMainPartLaserBehind(
      v1, v2, v3, v4, v5, v7,
      laserMask, textureIntensity, sampledDepth);
  o0 = laser.color;
  o1 = laser.glowAndAlpha;
}
'''


def lift_main_part_laser_behind_basic(source: str) -> str:
    """Lift the masked, fogged basic laser behind pass."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_LASER", "main_part_laser_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_laser_behind_basic.hlsl"

''' + signature + '''
{
  float opaqueDepth = tDepth.SampleLevel(PointClampClamp_s, v5.xy, 0).x;
  if (v5.z < opaqueDepth) discard;
  float laserMask = tLaserMask.Sample(LinearWrapWrap_s, v2).x;
  if (laserMask < 0.100000001) discard;
  float textureIntensity = tLaser.Sample(LinearWrapWrap_s, v2).x;
  MainPartBasicLaserBehindResult laser = EvaluateMainPartBasicLaserBehind(
      v1, v2, v4, v5, laserMask, textureIntensity);
  o0 = laser.color;
  o1 = laser.glowAndAlpha;
}
'''


def lift_main_part_glass_surface_single_tinted(source: str) -> str:
    """Factor the ordered single-reflection tinted-glass surface evaluator."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

''' + signature + '''
{
#include "include/main_part_glass_surface_single.hlsl"
}
'''


def lift_main_part_glass_behind_high_depth_glow(source: str) -> str:
    """Reuse the ordered glass-behind evaluator with modern transmission."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#define MAIN_PART_GLASS_BEHIND_TRANSMISSION_RANGE 1
#define MAIN_PART_GLASS_BEHIND_EDGE_SCALE 0.5
#include "include/main_part_legacy_glass_behind.hlsl"

''' + signature + '''
{
  EvaluateMainPartLegacyGlassBehind(
      v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, o0, o1);
}
'''


def lift_main_part_glass_dissolve_behind_single(source: str) -> str:
    """Factor the ordered dissolve frontend and single-probe glass backend."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_abi.hlsl"),
        ("CB_DISSOLVE", "main_part_dissolve_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_glass_dissolve_behind_single.hlsl"

''' + signature + '''
{
  EvaluateMainPartDissolveBehindSingle(
      v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, o0, o1);
}
'''


def lift_main_part_visualization_depth_glass_params(source: str) -> str:
    """Factor the depth-aware behind/front visualization evaluator."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_VISUALIZATION_COLOR", "main_part_visualization_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

''' + signature + '''
{
#include "include/main_part_visualization_depth.hlsl"
}
'''


def lift_main_part_packed_wave_dual_morph_uv_scroll(source: str) -> str:
    """Lift packed no-scale wave, two pose deltas, UV scroll, and cutoff."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ("CB_UV_SCROLL", "main_part_uv_scroll_abi.hlsl"),
        ("CB_WAVE", "main_part_wave_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    signature = signature.replace(
        "float4 v1 : TEXCOORD0", "float2 v1 : TEXCOORD0"
    )
    return declarations + '''

#include "include/main_part_packed_transform_vertex.hlsl"
// Keep adjacent expanded includes lexically separated.
#include "include/main_part_packed_wave_dual_morph_vertex.hlsl"
// End shared packed wave dual-morph helpers.

''' + signature + '''
{
  MainPartPackedWaveDualMorphVertex vertex =
      EvaluateMainPartPackedWaveDualMorphVertex(
          v0, v1, v2, v3, v5, v7, v9, v10);
  o0 = vertex.clipPosition;
  o1 = vertex.uv0;
  p1 = vertex.uv1;
  o2 = vertex.cutoff;
}
'''


def lift_main_part_triple_morph_uv_animation(source: str) -> str:
    """Lift the minimal three-pose atlas-animation vertex permutation."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_UVFRAME", "main_part_uvframe_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    declarations = declarations.replace(
        '\n\n#include "include/main_part_perframe_abi.hlsl"',
        '\n// Keep adjacent expanded ABIs lexically separated.\n'
        '#include "include/main_part_perframe_abi.hlsl"',
    ).replace(
        '\n\n#include "include/main_part_uvframe_abi.hlsl"',
        '\n// Keep adjacent expanded ABIs lexically separated.\n'
        '#include "include/main_part_uvframe_abi.hlsl"',
    )
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

// End shared three-pose atlas ABIs.
#include "include/main_part_triple_morph_uv_animation_vertex.hlsl"
// End shared three-pose atlas evaluator.

''' + signature + '''
{
  MainPartTripleMorphUvAnimationVertex vertex =
      EvaluateMainPartTripleMorphUvAnimationVertex(
          v0, v1, v4, v6, v8, v10, v11, v12, v13);
  o0 = vertex.clipPosition;
  o1 = vertex.uv0;
}
'''


def lift_main_part_packed_triple_morph_uv_animation_surface(
    source: str,
) -> str:
    """Lift packed LTW, three poses, atlas UV, normal, color, and screen."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ("CB_UVFRAME", "main_part_uvframe_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_packed_transform_vertex.hlsl"
#include "include/main_part_packed_triple_morph_uv_animation_vertex.hlsl"

''' + signature + '''
{
  MainPartPackedTripleMorphUvAnimationVertex vertex =
      EvaluateMainPartPackedTripleMorphUvAnimationVertex(
          v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10);
  o0 = vertex.clipPosition;
  o1 = vertex.viewPosition;
  o2 = vertex.uv0;
  o3 = vertex.normalView;
  o4 = vertex.color;
  o5 = vertex.screenUv;
}
'''


def lift_main_part_glass_opaque_forward_medium(source: str) -> str:
    """Factor medium opaque-glass forward lighting into semantic phases."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_opaque_abi.hlsl"),
        ("Cluster", "main_part_cluster_abi.hlsl"),
        ("LightProps", "main_part_lightprops_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    include_names = (
        "main_part_projection_abi.hlsl",
        "main_part_glass_opaque_abi.hlsl",
        "main_part_cluster_abi.hlsl",
        "main_part_lightprops_abi.hlsl",
    )
    for filename in include_names:
        declarations = declarations.replace(
            f'\n\n#include "include/{filename}"',
            '\n// Keep adjacent expanded ABIs lexically separated.\n'
            f'#include "include/{filename}"',
        )
    declarations = declarations.replace(
        '\n\nSamplerState',
        '\n// End shared opaque-glass forward ABIs.\n\nSamplerState',
    )
    signature_start = source.index("void commonPS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#define cmp -

#include "include/main_part_glass_opaque_medium.hlsl"

''' + signature + '''
{
  MainPartOpaqueGlassForwardOutput result =
      EvaluateMainPartOpaqueGlassForwardMedium(
          v1, v2, v3, v4, v5, v6, v7.xy, v8, v9 != 0);
  o0 = result.color;
  o1 = result.gForward;
}
'''


def lift_main_part_laser_displacement_packed_pose_picking(
    source: str,
) -> str:
    """Split the full packed posed laser vertex into reusable phases."""
    for cbuffer, filename in (
        ("CB_LASER_DISPLACEMENT", "main_part_laser_displacement_abi.hlsl"),
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ("CB_PICKING", "main_part_picking_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl",
        "main_part_picking_abi.hlsl",
    ):
        declarations = declarations.replace(
            f'\n\n#include "include/{filename}"',
            '\n// Keep adjacent expanded ABIs lexically separated.\n'
            f'#include "include/{filename}"',
        )
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

// End shared procedural-laser ABIs.
#define cmp -

#include "include/main_part_laser_displacement_packed_pose_picking.hlsl"

''' + signature + '''
{
  MainPartPackedLaserVertex result = EvaluateMainPartPackedLaserVertex(
      v0, v1, v2, v3, v4, v5, v6);
  o0 = result.clipPosition;
  o1 = result.uv;
  o2 = result.color;
}
'''


def lift_main_part_full_transform_wave_scroll_screen(source: str) -> str:
    """Compose no-scale wave, explicit LTW, UV scroll, and screen output."""
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_UV_SCROLL", "main_part_uv_scroll_abi.hlsl"),
        ("CB_WAVE", "main_part_wave_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    signature_start = source.index("void mainVS(")
    body_start = source.index("{", signature_start)
    signature = source[signature_start:body_start].rstrip()
    return declarations + '''

#include "include/main_part_wave_common.hlsl"
#include "include/main_part_wave_scroll_vertex.hlsl"

''' + signature + '''
{
  MainPartWaveScrollVertex vertex = EvaluateMainPartWaveScrollVertex(
      v0, v1, v2, v4, v5, v6, v7);
  o0 = vertex.clipPosition;
  o1 = vertex.uv0;
  o2 = vertex.screenUv;
}
'''


def lift_main_part_variant(
    _staging: Path,
    _selector: str,
    defines: list[str],
    source: str,
) -> str:
    if "VERTEX_SHADER" in defines:
        family_lift = lift_main_part_vertex_family(defines, source)
        if family_lift is not None:
            _family_name, lifted = family_lift
            return lifted
    if "PIXEL_SHADER" in defines:
        family_lift = lift_main_part_picking_family(defines, source)
        if family_lift is not None:
            _family_name, lifted = family_lift
            return lifted
        family_lift = lift_main_part_depth_family(defines, source)
        if family_lift is not None:
            _family_name, lifted = family_lift
            return lifted
        family_lift = lift_main_part_overlay_family(defines, source)
        if family_lift is not None:
            _family_name, lifted = family_lift
            return lifted
        family_lift = lift_main_part_early_gforward_family(defines, source)
        if family_lift is not None:
            _family_name, lifted = family_lift
            return lifted
        family_lift = lift_main_part_pixel_family(defines, source)
        if family_lift is not None:
            _family_name, lifted = family_lift
            return lifted
        family_lift = lift_main_part_transparent_family(defines, source)
        if family_lift is not None:
            _family_name, lifted = family_lift
            return lifted
        family_lift = lift_main_part_glass_surface_family(defines, source)
        if family_lift is not None:
            _family_name, lifted = family_lift
            return lifted
    if is_main_part_morph_vertex(defines):
        return lift_main_part_morph_vertex(source)
    if is_main_part_morph_clip_vertex(defines):
        return lift_main_part_morph_clip_vertex(source)
    if is_main_part_rigid_uv_step_surface(defines):
        return lift_main_part_rigid_uv_step_surface(source)
    if is_main_part_translucent_preview_flow(defines):
        return lift_main_part_translucent_preview_flow(source)
    if is_main_part_legacy_glass_behind_high(defines):
        return lift_main_part_legacy_glass_behind_high(source)
    if is_main_part_legacy_glass_surface_multi_medium(defines):
        return lift_main_part_legacy_glass_surface_multi_medium(source)
    if is_main_part_legacy_glass_surface_multi_alpha(defines):
        return lift_main_part_legacy_glass_surface_multi_alpha(source)
    if is_main_part_legacy_glass_surface_single_alpha(defines):
        return lift_main_part_legacy_glass_surface_single_alpha(source)
    legacy_plain_asset = main_part_legacy_glass_surface_plain_asset(defines)
    if legacy_plain_asset is not None:
        return lift_main_part_legacy_glass_surface_plain(
            source, legacy_plain_asset
        )
    tinted_alpha_asset = main_part_tinted_glass_surface_alpha_asset(defines)
    if tinted_alpha_asset is not None:
        return lift_main_part_legacy_glass_surface_plain(
            source, tinted_alpha_asset
        )
    tinted_transmission_asset = main_part_tinted_transmission_glass_asset(
        defines
    )
    if tinted_transmission_asset is not None:
        return lift_main_part_tinted_transmission_glass(
            source, tinted_transmission_asset
        )
    tinted_dissolve_asset = main_part_tinted_dissolve_glass_asset(defines)
    if tinted_dissolve_asset is not None:
        return lift_main_part_tinted_dissolve_glass(
            source, tinted_dissolve_asset
        )
    standard_unresponsive_asset = main_part_standard_unresponsive_glass_asset(
        defines
    )
    if standard_unresponsive_asset is not None:
        lifted = lift_main_part_legacy_glass_surface_plain(
            source, standard_unresponsive_asset
        )
        return lifted.replace(
            "EvaluateMainPartLegacyGlassSurfaceBasic",
            "EvaluateMainPartStandardUnresponsiveGlassSurface",
        )
    standard_geometric_asset = main_part_standard_geometric_glass_asset(
        defines
    )
    if standard_geometric_asset is not None:
        lifted = lift_main_part_legacy_glass_surface_plain(
            source, standard_geometric_asset
        )
        lifted = lifted.replace(
            "EvaluateMainPartLegacyGlassSurfaceBasic",
            "EvaluateMainPartStandardGeometricGlassSurface",
        )
        return lifted.replace(
            "v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, o0, o1",
            "v0, v1, v2, v3, v4, v5, v6, v7, o0, o1",
        )
    if is_main_part_uv_animation_pose0_cutoff(defines):
        return lift_main_part_uv_animation_pose0_cutoff(source)
    if is_main_part_water_surface_single(defines):
        return lift_main_part_water_surface_single(source)
    if is_main_part_visualization_alpha_asg_normal(defines):
        return lift_main_part_visualization_alpha_asg_normal(source)
    if is_main_part_visualization_low_metal_normal(defines):
        return lift_main_part_visualization_low_metal_normal(source)
    if is_main_part_gbuffer_asg_normal(defines):
        return lift_main_part_gbuffer_asg_normal(source)
    if is_main_part_gbuffer_dissolve_uv0(defines):
        return lift_main_part_gbuffer_dissolve_uv0(source)
    if is_main_part_water_surface_single_high_dissolve(defines):
        return lift_main_part_water_surface_single_high_dissolve(source)
    if is_main_part_water_surface_single_high(defines):
        return lift_main_part_water_surface_single_high(source)
    if is_main_part_water_surface_multi_high_alpha(defines):
        return lift_main_part_water_surface_multi_high_alpha(source)
    if is_main_part_glass_custom_tiling_behind_low(defines):
        return lift_main_part_glass_custom_tiling_behind_low(source)
    if is_main_part_glass_set_params_behind_single_low(defines):
        return lift_main_part_glass_set_params_behind_single_low(source)
    if is_main_part_packed_transform_morph_uv1_cutoff(defines):
        return lift_main_part_packed_transform_morph_uv1_cutoff(source)
    if is_main_part_packed_transform_morph_surface(defines):
        return lift_main_part_packed_transform_morph_surface(source)
    if is_main_part_packed_dual_morph_object_tangent(defines):
        return lift_main_part_packed_dual_morph_object_tangent(source)
    if is_main_part_packed_transform_fog_surface(defines):
        return lift_main_part_packed_transform_fog_surface(source)
    if is_main_part_dual_morph_parallax_plane(defines):
        return lift_main_part_dual_morph_parallax_plane(source)
    if is_main_part_triple_morph_occlusion_surface(defines):
        return lift_main_part_triple_morph_occlusion_surface(source)
    if is_main_part_rigid_tangent_uv1_cutoff(defines):
        return lift_main_part_rigid_tangent_uv1_cutoff(source)
    if is_main_part_packed_uv_scroll_uv1_cutoff(defines):
        return lift_main_part_packed_uv_scroll_uv1_cutoff(source)
    if is_main_part_wave_triple_morph_color(defines):
        return lift_main_part_wave_triple_morph_color(source)
    if is_main_part_wave_triple_morph_uv(defines):
        return lift_main_part_wave_triple_morph_uv(source)
    if is_main_part_wave_morph_surface(defines):
        return lift_main_part_wave_morph_surface(source)
    if is_main_part_packed_wave_picking_scroll(defines):
        return lift_main_part_packed_wave_picking_scroll(source)
    if is_main_part_packed_scaled_wave_picking_scroll(defines):
        return lift_main_part_packed_scaled_wave_picking_scroll(source)
    if is_main_part_packed_scaled_wave_uv(defines):
        return lift_main_part_packed_scaled_wave_uv(source)
    if is_main_part_laser_behind_full(defines):
        return lift_main_part_laser_behind_full(source)
    if is_main_part_laser_behind_basic(defines):
        return lift_main_part_laser_behind_basic(source)
    if is_main_part_glass_surface_single_tinted(defines):
        return lift_main_part_glass_surface_single_tinted(source)
    if is_main_part_glass_behind_high_depth_glow(defines):
        return lift_main_part_glass_behind_high_depth_glow(source)
    if is_main_part_glass_dissolve_behind_single(defines):
        return lift_main_part_glass_dissolve_behind_single(source)
    if is_main_part_visualization_depth_glass_params(defines):
        return lift_main_part_visualization_depth_glass_params(source)
    if is_main_part_packed_wave_dual_morph_uv_scroll(defines):
        return lift_main_part_packed_wave_dual_morph_uv_scroll(source)
    if is_main_part_triple_morph_uv_animation(defines):
        return lift_main_part_triple_morph_uv_animation(source)
    if is_main_part_packed_triple_morph_uv_animation_surface(defines):
        return lift_main_part_packed_triple_morph_uv_animation_surface(source)
    if is_main_part_glass_opaque_forward_medium(defines):
        return lift_main_part_glass_opaque_forward_medium(source)
    if is_main_part_laser_displacement_packed_pose_picking(defines):
        return lift_main_part_laser_displacement_packed_pose_picking(source)
    if is_main_part_full_transform_wave_scroll_screen(defines):
        return lift_main_part_full_transform_wave_scroll_screen(source)
    return source


def apply_main_part_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    """Lift every main_part permutation through the shared material pipeline."""
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_PERFRAME", "main_part_perframe_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_REFLECTIONS", "main_part_reflections_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "Cluster", "main_part_cluster_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "LightProps", "main_part_lightprops_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_VISUALIZATION_COLOR",
        "main_part_visualization_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_DISSOLVE", "main_part_dissolve_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_GLASS", "main_part_glass_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_TILING", "main_part_tiling_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_OFFSET_PARAMS",
        "main_part_offset_params_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_TRANSFORMS", "main_part_transforms_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_BONES", "main_part_bones_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_PAINT_PALETTE",
        "main_part_paint_palette_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_UV_SCROLL", "main_part_uv_scroll_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_WAVE", "main_part_wave_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_UVFRAME", "main_part_uvframe_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_UV_STEP", "main_part_uv_step_abi.hlsl"
    )
    ensure_asset_include(staging, "main_part_glass_opaque_abi.hlsl")
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_PICKING", "main_part_picking_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_part", "CB_LASER", "main_part_laser_abi.hlsl"
    )
    ensure_asset_include(staging, "main_part_morph_vertex.hlsl")
    ensure_asset_include(staging, "main_part_morph_clip_vertex.hlsl")
    ensure_asset_include(staging, "main_part_uv_step.hlsl")
    ensure_asset_include(staging, "main_part_rigid_uv_step_vertex.hlsl")
    ensure_asset_include(staging, "main_part_translucent_preview.hlsl")
    ensure_asset_include(staging, "main_part_legacy_glass_behind.hlsl")
    ensure_asset_include(staging, "main_part_legacy_glass_multi_lighting.hlsl")
    ensure_asset_include(staging, "main_part_legacy_glass_multi.hlsl")
    ensure_asset_include(staging, "main_part_legacy_glass_surface_basic.hlsl")
    ensure_asset_include(staging, "main_part_legacy_glass_surface_single.hlsl")
    ensure_asset_include(staging, "main_part_legacy_glass_surface_plain_multi.hlsl")
    ensure_asset_include(staging, "main_part_legacy_glass_surface_plain_off.hlsl")
    ensure_asset_include(staging, "main_part_legacy_glass_surface_plain_single.hlsl")
    ensure_asset_include(staging, "main_part_tinted_glass_surface_off.hlsl")
    ensure_asset_include(staging, "main_part_tinted_glass_surface_transmission_multi.hlsl")
    ensure_asset_include(staging, "main_part_tinted_glass_surface_transmission_off.hlsl")
    ensure_asset_include(staging, "main_part_tinted_glass_surface_transmission_single.hlsl")
    ensure_asset_include(staging, "main_part_tinted_glass_surface_dissolve_multi.hlsl")
    ensure_asset_include(staging, "main_part_tinted_glass_surface_dissolve_off.hlsl")
    ensure_asset_include(staging, "main_part_tinted_glass_surface_dissolve_single.hlsl")
    ensure_asset_include(staging, "main_part_glass_surface_shared.hlsl")
    ensure_asset_include(staging, "main_part_directional_glass_surface.hlsl")
    ensure_asset_include(
        staging, "main_part_tinted_dissolve_glass_surface.hlsl"
    )
    ensure_asset_include(staging, "main_part_directional_map.hlsl")
    ensure_asset_include(staging, "main_part_glass_clustered_lighting.hlsl")
    ensure_asset_include(staging, "main_part_light_cap.hlsl")
    ensure_asset_include(staging, "main_part_glass_surface_medium_light_cap.hlsl")
    ensure_asset_include(
        staging, "main_part_glass_surface_medium_light_cap_single.hlsl"
    )
    ensure_asset_include(
        staging, "main_part_glass_surface_medium_light_cap_off.hlsl"
    )
    ensure_asset_include(
        staging, "main_part_glass_surface_medium_light_cap_unresponsive.hlsl"
    )
    ensure_asset_include(
        staging,
        "main_part_glass_surface_medium_light_cap_single_unresponsive.hlsl",
    )
    ensure_asset_include(
        staging,
        "main_part_glass_surface_medium_light_cap_off_unresponsive.hlsl",
    )
    ensure_asset_include(staging, "main_part_glass_surface_medium_standard.hlsl")
    ensure_asset_include(
        staging, "main_part_glass_surface_medium_single_standard.hlsl"
    )
    ensure_asset_include(
        staging, "main_part_glass_surface_medium_off_standard.hlsl"
    )
    ensure_asset_include(
        staging, "main_part_glass_surface_medium_standard_geometric.hlsl"
    )
    ensure_asset_include(
        staging, "main_part_glass_surface_medium_single_standard_geometric.hlsl"
    )
    ensure_asset_include(
        staging, "main_part_glass_surface_medium_off_standard_geometric.hlsl"
    )
    ensure_asset_include(staging, "main_part_standard_glass_surface_unresponsive_multi.hlsl")
    ensure_asset_include(staging, "main_part_standard_glass_surface_unresponsive_off.hlsl")
    ensure_asset_include(staging, "main_part_standard_glass_surface_unresponsive_single.hlsl")
    ensure_asset_include(staging, "main_part_standard_glass_surface_geometric_multi.hlsl")
    ensure_asset_include(staging, "main_part_standard_glass_surface_geometric_off.hlsl")
    ensure_asset_include(staging, "main_part_standard_glass_surface_geometric_single.hlsl")
    ensure_asset_include(staging, "main_part_uv_animation_vertex.hlsl")
    ensure_asset_include(staging, "main_part_water_surface_single.hlsl")
    ensure_asset_include(staging, "main_part_visualization.hlsl")
    ensure_asset_include(staging, "main_part_visualization_low.hlsl")
    ensure_asset_include(staging, "main_part_gbuffer.hlsl")
    ensure_asset_include(staging, "main_part_octahedral_normal.hlsl")
    ensure_asset_include(staging, "main_part_gbuffer_dissolve.hlsl")
    ensure_asset_include(staging, "main_part_dissolve_b0_abi.hlsl")
    ensure_asset_include(
        staging, "main_part_water_surface_single_high_dissolve.hlsl"
    )
    ensure_asset_include(staging, "main_part_water_high_clustered_backend.hlsl")
    ensure_asset_include(staging, "main_part_water_surface_single_high.hlsl")
    ensure_asset_include(staging, "main_part_water_multi_high_frontend.hlsl")
    ensure_asset_include(staging, "main_part_water_multi_high_lighting.hlsl")
    ensure_asset_include(staging, "main_part_water_multi_high_composition.hlsl")
    ensure_asset_include(
        staging, "main_part_glass_set_params_behind_single.hlsl"
    )
    ensure_asset_include(
        staging, "main_part_glass_custom_tiling_behind_low.hlsl"
    )
    ensure_asset_include(staging, "main_part_packed_transform_vertex.hlsl")
    ensure_asset_include(staging, "main_part_packed_multi_morph_vertex.hlsl")
    ensure_asset_include(
        staging, "main_part_packed_dual_morph_object_tangent_vertex.hlsl"
    )
    ensure_asset_include(staging, "main_part_vertex_fog.hlsl")
    ensure_asset_include(
        staging, "main_part_packed_transform_fog_vertex.hlsl"
    )
    ensure_asset_include(staging, "main_part_dual_morph_vertex.hlsl")
    ensure_asset_include(staging, "main_part_triple_morph_vertex.hlsl")
    ensure_asset_include(staging, "main_part_rigid_vertex.hlsl")
    ensure_asset_include(staging, "main_part_rigid_normal_vertex.hlsl")
    ensure_asset_include(staging, "main_part_packed_uv_scroll_vertex.hlsl")
    ensure_asset_include(staging, "main_part_uv_scroll_vertex.hlsl")
    ensure_asset_include(staging, "main_part_wave_vertex.hlsl")
    ensure_asset_include(staging, "main_part_scaled_wave_common.hlsl")
    ensure_asset_include(staging, "main_part_scaled_wave_by_scale_common.hlsl")
    ensure_asset_include(staging, "main_part_wave_morph_surface_vertex.hlsl")
    ensure_asset_include(staging, "main_part_packed_wave_picking_vertex.hlsl")
    ensure_asset_include(staging, "main_part_picking_common.hlsl")
    ensure_asset_include(staging, "main_part_picking_pixel.hlsl")
    ensure_asset_include(staging, "main_part_flow_map_abi.hlsl")
    ensure_asset_include(staging, "main_part_alpha_cutout.hlsl")
    ensure_asset_include(staging, "main_part_dissolve_cutout.hlsl")
    ensure_asset_include(staging, "main_part_depth_pixel.hlsl")
    ensure_asset_include(staging, "main_part_overlay_pixel.hlsl")
    ensure_asset_include(staging, "main_part_early_gforward.hlsl")
    ensure_asset_include(staging, "main_part_packed_scaled_wave_vertex.hlsl")
    ensure_asset_include(staging, "main_part_laser_behind.hlsl")
    ensure_asset_include(staging, "main_part_laser_behind_basic.hlsl")
    ensure_asset_include(staging, "main_part_glass_surface_single.hlsl")
    ensure_asset_include(
        staging, "main_part_glass_dissolve_behind_single.hlsl"
    )
    ensure_asset_include(staging, "main_part_visualization_depth.hlsl")
    ensure_asset_include(staging, "main_part_wave_common.hlsl")
    ensure_asset_include(staging, "main_part_wave_scroll_vertex.hlsl")
    ensure_asset_include(staging, "main_part_packed_wave_dual_morph_vertex.hlsl")
    ensure_asset_include(
        staging, "main_part_triple_morph_uv_animation_vertex.hlsl"
    )
    ensure_asset_include(
        staging, "main_part_packed_triple_morph_uv_animation_vertex.hlsl"
    )
    ensure_asset_include(staging, "main_part_glass_opaque_medium_clustered.hlsl")
    ensure_asset_include(staging, "main_part_glass_opaque_medium.hlsl")
    ensure_asset_include(staging, "main_part_laser_displacement_abi.hlsl")
    ensure_asset_include(staging, "main_part_laser_deformation_policy.hlsl")
    ensure_asset_include(staging, "main_part_laser_packed_transform.hlsl")
    ensure_asset_include(
        staging, "main_part_laser_displacement_color_policy.hlsl"
    )
    ensure_asset_include(staging, "main_part_laser_deformation_vertex.hlsl")
    ensure_asset_include(staging, "main_part_planar_world_abi.hlsl")
    ensure_asset_include(staging, "main_part_planar_world_vertex.hlsl")
    ensure_asset_include(staging, "main_part_adaptive_uv_vertex.hlsl")
    ensure_asset_include(staging, "main_part_packed_adaptive_uv_vertex.hlsl")
    ensure_asset_include(staging, "main_part_transform_buffer_vertex.hlsl")
    ensure_asset_include(staging, "main_part_laser_picking_color.hlsl")
    ensure_asset_include(
        staging, "main_part_laser_displacement_packed_pose_picking.hlsl"
    )
    return apply_character_material_recipe(
        staging, records, blobs, compiler,
        source_name="main_part", shader_count=1812, pixel_count=921,
        split_variants=True,
        variant_lifter=lift_main_part_variant,
    )
