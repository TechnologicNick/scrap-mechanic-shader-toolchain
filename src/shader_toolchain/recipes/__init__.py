"""Semantic shader recognition and lifting recipes."""

from .bloom_downres import apply_bloom_downres_recipe
from .bloom_first_downres import apply_bloom_first_downres_recipe
from .bloom_last_upres import apply_bloom_last_upres_recipe
from .bloom_upres import apply_bloom_upres_recipe
from .bloom_upres_depth import apply_bloom_upres_depth_recipe
from .compiling_shaders import apply_compiling_shaders_recipe
from .cmp_water_normal import apply_cmp_water_normal_recipe
from .cmp_water_init_spectrum import apply_cmp_water_init_spectrum_recipe
from .cmp_cluster_to_volumetrics import apply_cmp_cluster_to_volumetrics_recipe
from .cmp_auto_hdr import apply_cmp_auto_hdr_recipe
from .cmp_depth_bounds import apply_cmp_depth_bounds_recipe
from .cmp_fft_butterfly_shared import apply_cmp_fft_butterfly_shared_recipe
from .cmp_fsr import apply_cmp_fsr_recipe
from .cmp_normal_mips import apply_cmp_normal_mips_recipe
from .cmp_update_reflection import apply_cmp_update_reflection_recipe
from .copy_auto_hdr import apply_copy_auto_hdr_recipe
from .blur_down_res import apply_blur_down_res_recipe
from .blur_pushmap_a import apply_blur_pushmap_a_recipe
from .blur_pushmap_b import apply_blur_pushmap_b_recipe
from .blur_vol_a import apply_blur_vol_a_recipe
from .blur_vol_b import apply_blur_vol_b_recipe
from .copy_blend import apply_copy_blend_recipe
from .copy_clouds import apply_copy_clouds_recipe
from .copy_depth import apply_copy_depth_recipe
from .copy_depth_rect_to_color import apply_copy_depth_rect_to_color_recipe
from .copy_downscale import apply_copy_downscale_recipe
from .copy_rgba import apply_copy_rgba_recipe
from .copy_to_shadow_atlas import apply_copy_to_shadow_atlas_recipe
from .copy_lut_brightness import apply_copy_lut_brightness_recipe
from .cube_map_face_present import apply_cube_map_face_present_recipe
from .cube_map_blend import apply_cube_map_blend_recipe
from .cube_map_composition import apply_cube_map_composition_recipe
from .cube_map_face_composition import apply_cube_map_face_composition_recipe
from .gui_silhouette import apply_gui_silhouette_recipe
from .gen_gi_ao_probe import apply_gen_gi_ao_probe_recipe
from .gui import apply_gui_recipe
from .gui_blurry_background import apply_gui_blurry_background_recipe
from .gui_texture_3d import apply_gui_texture_3d_recipe
from .gui_texture_box_array import apply_gui_texture_box_array_recipe
from .indirect_temporal import apply_indirect_temporal_recipe
from .main_debug_drawer import apply_main_debug_drawer_recipe
from .main_decals import apply_main_decals_recipe
from .main_clutter_impostor import apply_main_clutter_impostor_recipe
from .main_billboard import apply_main_billboard_recipe
from .main_text import apply_main_text_recipe
from .main_terrain_surface import apply_main_terrain_surface_recipe
from .main_editor_terrain_surface import apply_main_editor_terrain_surface_recipe
from .main_line import apply_main_line_recipe
from .main_impostor import apply_main_impostor_recipe
from .post_blur import apply_post_blur_recipe
from .post_downsample import apply_post_downsample_recipe
from .post_dof import apply_post_dof_recipe
from .post_depth_to_pushmap import apply_post_depth_to_pushmap_recipe
from .post_fxaa import apply_post_fxaa_recipe
from .post_resolve_transparency import apply_post_resolve_transparency_recipe
from .post_sky import apply_post_sky_recipe
from .post_smaa import apply_post_smaa_recipe
from .save_paused import apply_save_paused_recipe
from .upres_clouds import apply_upres_clouds_recipe
from .ssgi_prepass import apply_ssgi_prepass_recipe
from .ssgi_denoise import apply_ssgi_denoise_recipe


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
    apply_bloom_first_downres_recipe,
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
    apply_copy_lut_brightness_recipe,
    apply_gui_texture_3d_recipe,
    apply_gui_texture_box_array_recipe,
    apply_indirect_temporal_recipe,
    apply_blur_pushmap_a_recipe,
    apply_blur_pushmap_b_recipe,
    apply_cube_map_face_present_recipe,
    apply_blur_vol_a_recipe,
    apply_blur_vol_b_recipe,
    apply_bloom_upres_depth_recipe,
    apply_gui_recipe,
    apply_cmp_water_normal_recipe,
    apply_cmp_water_init_spectrum_recipe,
    apply_post_dof_recipe,
    apply_main_debug_drawer_recipe,
    apply_main_decals_recipe,
    apply_main_clutter_impostor_recipe,
    apply_main_billboard_recipe,
    apply_main_text_recipe,
    apply_main_terrain_surface_recipe,
    apply_main_editor_terrain_surface_recipe,
    apply_main_line_recipe,
    apply_main_impostor_recipe,
    apply_cmp_cluster_to_volumetrics_recipe,
    apply_cmp_auto_hdr_recipe,
    apply_cmp_depth_bounds_recipe,
    apply_cmp_fft_butterfly_shared_recipe,
    apply_cmp_fsr_recipe,
    apply_cube_map_blend_recipe,
    apply_cube_map_composition_recipe,
    apply_cube_map_face_composition_recipe,
    apply_post_sky_recipe,
    apply_post_smaa_recipe,
    apply_ssgi_prepass_recipe,
    apply_ssgi_denoise_recipe,
    apply_cmp_normal_mips_recipe,
    apply_post_depth_to_pushmap_recipe,
    apply_cmp_update_reflection_recipe,
    apply_gen_gi_ao_probe_recipe,
)


def apply_recipes(staging, records, blobs, compiler):
    applied = []
    for recipe in RECIPES:
        result = recipe(staging, records, blobs, compiler)
        if result:
            applied.append(result)
    return applied
