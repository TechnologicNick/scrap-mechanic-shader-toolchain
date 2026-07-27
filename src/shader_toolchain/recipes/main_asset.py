"""Recognize the shared rigid, animated, glass, water, and effect material."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .main_character import apply_character_material_recipe


def apply_main_asset_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    """Lift every main_asset permutation through the shared material pipeline."""
    return apply_character_material_recipe(
        staging, records, blobs, compiler,
        source_name="main_asset", shader_count=447, pixel_count=282,
    )
