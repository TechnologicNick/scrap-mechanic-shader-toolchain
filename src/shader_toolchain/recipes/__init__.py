"""Semantic shader recognition and lifting recipes."""

from .post_blur import apply_post_blur_recipe
from .post_fxaa import apply_post_fxaa_recipe


RECIPES = (apply_post_fxaa_recipe, apply_post_blur_recipe)


def apply_recipes(staging, records, blobs, compiler):
    applied = []
    for recipe in RECIPES:
        result = recipe(staging, records, blobs, compiler)
        if result:
            applied.append(result)
    return applied
