"""Semantic shader recognition and lifting recipes."""

from .blur_down_res import apply_blur_down_res_recipe
from .copy_blend import apply_copy_blend_recipe
from .copy_depth import apply_copy_depth_recipe
from .copy_downscale import apply_copy_downscale_recipe
from .copy_rgba import apply_copy_rgba_recipe
from .post_blur import apply_post_blur_recipe
from .post_fxaa import apply_post_fxaa_recipe
from .post_resolve_transparency import apply_post_resolve_transparency_recipe


RECIPES = (
    apply_post_fxaa_recipe,
    apply_post_blur_recipe,
    apply_copy_downscale_recipe,
    apply_copy_depth_recipe,
    apply_copy_rgba_recipe,
    apply_copy_blend_recipe,
    apply_post_resolve_transparency_recipe,
    apply_blur_down_res_recipe,
)


def apply_recipes(staging, records, blobs, compiler):
    applied = []
    for recipe in RECIPES:
        result = recipe(staging, records, blobs, compiler)
        if result:
            applied.append(result)
    return applied
