"""Semantic shader recognition and lifting recipes."""

from .bloom_downres import apply_bloom_downres_recipe
from .bloom_last_upres import apply_bloom_last_upres_recipe
from .bloom_upres import apply_bloom_upres_recipe
from .compiling_shaders import apply_compiling_shaders_recipe
from .copy_auto_hdr import apply_copy_auto_hdr_recipe
from .blur_down_res import apply_blur_down_res_recipe
from .blur_pushmap_a import apply_blur_pushmap_a_recipe
from .blur_pushmap_b import apply_blur_pushmap_b_recipe
from .copy_blend import apply_copy_blend_recipe
from .copy_clouds import apply_copy_clouds_recipe
from .copy_depth import apply_copy_depth_recipe
from .copy_depth_rect_to_color import apply_copy_depth_rect_to_color_recipe
from .copy_downscale import apply_copy_downscale_recipe
from .copy_rgba import apply_copy_rgba_recipe
from .copy_to_shadow_atlas import apply_copy_to_shadow_atlas_recipe
from .cube_map_face_present import apply_cube_map_face_present_recipe
from .gui_silhouette import apply_gui_silhouette_recipe
from .gui_blurry_background import apply_gui_blurry_background_recipe
from .gui_texture_3d import apply_gui_texture_3d_recipe
from .gui_texture_box_array import apply_gui_texture_box_array_recipe
from .post_blur import apply_post_blur_recipe
from .post_downsample import apply_post_downsample_recipe
from .post_fxaa import apply_post_fxaa_recipe
from .post_resolve_transparency import apply_post_resolve_transparency_recipe
from .save_paused import apply_save_paused_recipe
from .upres_clouds import apply_upres_clouds_recipe


RECIPES = (
    apply_post_fxaa_recipe,
    apply_post_blur_recipe,
    apply_copy_downscale_recipe,
    apply_copy_depth_recipe,
    apply_copy_rgba_recipe,
    apply_copy_blend_recipe,
    apply_post_resolve_transparency_recipe,
    apply_blur_down_res_recipe,
    apply_bloom_downres_recipe,
    apply_bloom_upres_recipe,
    apply_post_downsample_recipe,
    apply_bloom_last_upres_recipe,
    apply_save_paused_recipe,
    apply_compiling_shaders_recipe,
    apply_upres_clouds_recipe,
    apply_copy_depth_rect_to_color_recipe,
    apply_copy_auto_hdr_recipe,
    apply_copy_clouds_recipe,
    apply_gui_silhouette_recipe,
    apply_gui_blurry_background_recipe,
    apply_copy_to_shadow_atlas_recipe,
    apply_gui_texture_3d_recipe,
    apply_gui_texture_box_array_recipe,
    apply_blur_pushmap_a_recipe,
    apply_blur_pushmap_b_recipe,
    apply_cube_map_face_present_recipe,
)


def apply_recipes(staging, records, blobs, compiler):
    applied = []
    for recipe in RECIPES:
        result = recipe(staging, records, blobs, compiler)
        if result:
            applied.append(result)
    return applied
