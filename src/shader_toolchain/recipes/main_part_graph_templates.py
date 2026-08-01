"""Registry of fully wired and differentially validated main-part graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .main_part_directional_glass_surface import (
    classify_main_part_directional_glass_surface,
    lift_main_part_directional_glass_surface,
)
from .main_part_glass_surface_families import (
    classify_main_part_glass_surface_family,
    lift_main_part_glass_surface_family,
)
from .main_part_tinted_dissolve_glass_surface import (
    classify_main_part_tinted_dissolve_glass_surface,
    lift_main_part_tinted_dissolve_glass_surface,
)


GraphMatcher = Callable[[Iterable[str], str], object | None]
GraphRenderer = Callable[[Iterable[str], str], tuple[str, str] | None]


@dataclass(frozen=True)
class MainPartGraphTemplate:
    name: str
    matcher: GraphMatcher
    renderer: GraphRenderer

    def matches(self, defines: Iterable[str], source: str) -> bool:
        return self.matcher(defines, source) is not None

    def render(
        self, defines: Iterable[str], source: str,
    ) -> tuple[str, str] | None:
        return self.renderer(defines, source)


MAIN_PART_GRAPH_TEMPLATES = (
    MainPartGraphTemplate(
        "tinted_dissolve_glass_surface",
        classify_main_part_tinted_dissolve_glass_surface,
        lift_main_part_tinted_dissolve_glass_surface,
    ),
    MainPartGraphTemplate(
        "transparent_glass_surface",
        classify_main_part_glass_surface_family,
        lift_main_part_glass_surface_family,
    ),
    MainPartGraphTemplate(
        "directional_glass_surface",
        classify_main_part_directional_glass_surface,
        lift_main_part_directional_glass_surface,
    ),
)


def find_main_part_graph_template(
    defines: Iterable[str], source: str,
) -> MainPartGraphTemplate | None:
    """Return the one validated template accepting this full permutation."""
    values = frozenset(defines)
    matches = tuple(
        template for template in MAIN_PART_GRAPH_TEMPLATES
        if template.matches(values, source)
    )
    if len(matches) > 1:
        names = ", ".join(template.name for template in matches)
        raise RuntimeError(f"ambiguous main_part graph templates: {names}")
    return matches[0] if matches else None
