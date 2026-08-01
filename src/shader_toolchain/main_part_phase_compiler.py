"""Compile a ``main_part`` semantic descriptor through a validated graph template."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .main_part_permutation_graph import (
    MainPartPermutationDescriptor,
    describe_main_part_permutation,
    resolve_phase_graph,
)
from .recipes.main_part_graph_templates import (
    find_main_part_graph_template,
)


@dataclass(frozen=True)
class CompiledMainPartPhaseGraph:
    template: str
    family: str
    descriptor: MainPartPermutationDescriptor
    source: str


def compile_main_part_phase_graph(
    defines: Iterable[str], source: str, *, selector: str = "",
) -> CompiledMainPartPhaseGraph | None:
    """Render one permutation through a selector-independent graph template."""
    values = frozenset(defines)
    descriptor = describe_main_part_permutation(selector, values, source)
    graph = resolve_phase_graph(descriptor)
    if not graph.phase_inventory_complete:
        return None
    template = find_main_part_graph_template(values, source)
    if template is None:
        return None
    result = template.render(values, source)
    if result is None:
        raise RuntimeError(
            f"template {template.name} accepted but did not render"
        )
    family, lifted = result
    return CompiledMainPartPhaseGraph(
        template=template.name,
        family=family,
        descriptor=descriptor,
        source=lifted,
    )
