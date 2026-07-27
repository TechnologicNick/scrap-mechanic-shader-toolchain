"""Semantic shader recognition and lifting recipes."""

from .copy_downscale import apply_copy_downscale_recipe
from .post_blur import apply_post_blur_recipe
from .post_fxaa import apply_post_fxaa_recipe


RECIPES = (
    apply_post_fxaa_recipe,
    apply_post_blur_recipe,
    apply_copy_downscale_recipe,
)


def apply_recipes(staging, records, blobs, compiler):
    applied = []
    for recipe in RECIPES:
        result = recipe(staging, records, blobs, compiler)
        if result:
            applied.append(result)
    return applied
