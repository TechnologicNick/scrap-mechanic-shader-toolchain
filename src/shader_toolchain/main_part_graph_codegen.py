"""Generic HLSL entry-wrapper generation for declarative main-part graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .recipes.common import replace_cbuffer_with_include
from .recipes.main_part_families import SemanticKey, parse_entry_signature


@dataclass(frozen=True)
class PolicyAxis:
    """Map one semantic policy axis to compile-time HLSL defines."""

    name: str
    defines: Mapping[str, str | None]


@dataclass(frozen=True)
class AbiIncludeRule:
    """Install one ABI include when all axis predicates match."""

    cbuffer: str
    asset: str
    predicates: tuple[tuple[str, frozenset[str]], ...] = ()

    def matches(self, policies: Mapping[str, str]) -> bool:
        return all(policies.get(axis) in values
                   for axis, values in self.predicates)


@dataclass(frozen=True)
class GraphEntrySpecification:
    """Selector-independent recipe for one typed graph entry point."""

    name: str
    include_asset: str
    evaluator: str
    semantics: tuple[SemanticKey, ...]
    axes: tuple[PolicyAxis, ...]
    abi_includes: tuple[AbiIncludeRule, ...]


def render_main_part_graph_entry(
    specification: GraphEntrySpecification,
    policies: Mapping[str, str],
    source: str,
) -> str:
    """Render a thin wrapper using only a graph spec and recovered ABI."""
    signature, parameters = parse_entry_signature(source, "commonPS")
    variables = {parameter.semantic: parameter.variable
                 for parameter in parameters}
    missing = [semantic for semantic in specification.semantics
               if semantic not in variables]
    if missing:
        rendered = ", ".join(
            f"{semantic.name}{semantic.index}" for semantic in missing
        )
        raise RuntimeError(
            f"graph {specification.name} entry is missing semantics: {rendered}"
        )

    for rule in specification.abi_includes:
        if rule.matches(policies):
            source = replace_cbuffer_with_include(
                source, rule.cbuffer, rule.asset
            )

    marker = source.index("// 3Dmigoto declarations")
    prefix = source[:marker].rstrip()
    defines: list[str] = []
    for axis in specification.axes:
        value = policies.get(axis.name)
        if value not in axis.defines:
            raise RuntimeError(
                f"graph {specification.name} does not support "
                f"{axis.name}={value}"
            )
        define = axis.defines[value]
        if define:
            defines.append(f"#define {define}")

    arguments = [variables[semantic] for semantic in specification.semantics]
    body = (
        "{\n  " + specification.evaluator + "(\n      "
        + ", ".join(arguments) + ");\n}\n"
    )
    policy_block = ("\n".join(defines) + "\n") if defines else ""
    return (
        prefix + "\n\n" + policy_block
        + f'#include "include/{specification.include_asset}"\n\n'
        + signature + "\n" + body
    )

