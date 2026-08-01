"""Typed data-flow and runtime-resource contracts for reusable HLSL phases."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re

from .main_part_permutation_graph import PHASE_IMPLEMENTATIONS


@dataclass(frozen=True)
class PhasePort:
    name: str
    type_name: str


@dataclass(frozen=True)
class RuntimeResource:
    kind: str
    name: str
    slot: int
    abi_asset: str = ""


@dataclass(frozen=True)
class PhaseContract:
    key: str
    symbol: str
    asset: str
    inputs: tuple[PhasePort, ...] = ()
    outputs: tuple[PhasePort, ...] = ()
    resources: tuple[RuntimeResource, ...] = ()
    after: tuple[str, ...] = ()
    activation_fixtures: tuple[str, ...] = ()
    port_source: str = "missing"


_GLASS_MATERIAL = (
    PhasePort("viewPosition", "float3"),
    PhasePort("uv", "float2"),
    PhasePort("normalView", "float3"),
    PhasePort("vertexColor", "float4"),
)
_GLASS_VALUE = (PhasePort("material", "MainPartDissolveGlassMaterial"),)
_GLASS_LIGHTING = (PhasePort("lighting", "MainPartGlassLighting"),)


def _split_parameters(value: str) -> tuple[str, ...]:
    parameters: list[str] = []
    current: list[str] = []
    depth = 0
    for character in value:
        if character in "(<[":
            depth += 1
        elif character in ")>]":
            depth = max(0, depth - 1)
        if character == "," and depth == 0:
            parameters.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    if current:
        parameters.append("".join(current).strip())
    return tuple(item for item in parameters if item and item != "void")


def _infer_symbol_ports() -> dict[
    str, tuple[tuple[PhasePort, ...], tuple[PhasePort, ...]]
]:
    """Read typed helper signatures already present in semantic assets."""
    root = Path(__file__).parent / "recipes" / "assets"
    signatures: dict[
        str, tuple[tuple[PhasePort, ...], tuple[PhasePort, ...]]
    ] = {}
    pattern = re.compile(
        r"^[ \t]*([A-Za-z_][A-Za-z0-9_<>]*)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^{}]*?)\)\s*\{",
        re.DOTALL | re.MULTILINE,
    )
    for path in sorted(root.glob("*.hlsl")):
        source = re.sub(
            r"//[^\n]*|/\*.*?\*/", " ",
            path.read_text(encoding="utf-8"), flags=re.DOTALL,
        )
        for match in pattern.finditer(source):
            return_type, symbol, raw_parameters = match.groups()
            inputs: list[PhasePort] = []
            outputs: list[PhasePort] = []
            for parameter in _split_parameters(raw_parameters):
                parameter = parameter.split(":", 1)[0].strip()
                tokens = parameter.replace("[", " [").split()
                if len(tokens) < 2:
                    continue
                direction = (
                    tokens[0]
                    if tokens[0] in {"in", "out", "inout"}
                    else "in"
                )
                if direction != "in":
                    tokens = tokens[1:]
                if len(tokens) < 2:
                    continue
                port = PhasePort(
                    tokens[-1].split("[")[0], tokens[-2]
                )
                if direction in {"in", "inout"}:
                    inputs.append(port)
                if direction in {"out", "inout"}:
                    outputs.append(port)
            if return_type != "void":
                outputs.insert(0, PhasePort("result", return_type))
            signatures.setdefault(symbol, (tuple(inputs), tuple(outputs)))
    return signatures


def _base_contracts() -> dict[str, PhaseContract]:
    inferred = _infer_symbol_ports()
    return {
        implementation.key: PhaseContract(
            key=implementation.key,
            symbol=implementation.symbol,
            asset=implementation.asset,
            inputs=inferred.get(implementation.symbol, ((), ()))[0],
            outputs=inferred.get(implementation.symbol, ((), ()))[1],
            port_source=(
                "policy" if implementation.symbol == "CompileTimePolicy"
                else "inferred" if implementation.symbol in inferred
                else "missing"
            ),
        )
        for implementation in PHASE_IMPLEMENTATIONS
    }


def phase_contract_registry() -> dict[str, PhaseContract]:
    """Return contracts enriched where phase boundaries are already typed."""
    contracts = _base_contracts()
    contracts["material.glass"] = replace(
        contracts["material.glass"],
        inputs=_GLASS_MATERIAL,
        outputs=_GLASS_VALUE,
        resources=(
            RuntimeResource("texture", "tDif", 0),
            RuntimeResource("texture", "tAsg", 1),
            RuntimeResource("texture", "tNor", 2),
        ),
        activation_fixtures=("material_textures",),
        port_source="curated",
    )
    contracts["lighting.standard"] = replace(
        contracts["lighting.standard"],
        inputs=(PhasePort("viewPosition", "float3"), *_GLASS_VALUE),
        outputs=_GLASS_LIGHTING,
        resources=(
            RuntimeResource(
                "cbuffer", "CB_PERFRAME", 12,
                "main_part_perframe_abi.hlsl",
            ),
            RuntimeResource("texture", "tLightColorMap", 9),
        ),
        after=("material",),
        activation_fixtures=("directional_light",),
        port_source="curated",
    )
    contracts["reflection.single"] = replace(
        contracts["reflection.single"],
        inputs=_GLASS_VALUE,
        outputs=(PhasePort("reflectedColor", "float3"),),
        resources=(RuntimeResource("texture", "taReflection", 14),),
        after=("lighting",),
        activation_fixtures=("single_reflection",),
        port_source="curated",
    )
    contracts["reflection.multi"] = replace(
        contracts["reflection.multi"],
        inputs=(
            PhasePort("cluster", "MainPartGlassClusterAddress"),
            *_GLASS_VALUE,
        ),
        outputs=(PhasePort("reflectedColor", "float3"),),
        resources=(
            RuntimeResource(
                "cbuffer", "CB_REFLECTIONS", 11,
                "main_part_reflections_abi.hlsl",
            ),
            RuntimeResource("buffer", "sbVoxelLightIds", 11),
            RuntimeResource("texture", "taReflection", 14),
        ),
        after=("lighting",),
        activation_fixtures=("cluster_reflection_masks", "reflection_probes"),
        port_source="curated",
    )
    contracts["composition.standard"] = replace(
        contracts["composition.standard"],
        inputs=(
            PhasePort("screenUv", "float3"),
            PhasePort("fogColor", "float4"),
            *_GLASS_VALUE,
            *_GLASS_LIGHTING,
        ),
        outputs=(PhasePort("surface", "MainPartGlassSurfaceComposite"),),
        resources=(
            RuntimeResource("cbuffer", "CB_GLASS", 0,
                            "main_part_glass_abi.hlsl"),
            RuntimeResource("texture", "tFrame", 15),
        ),
        after=("reflection",),
        activation_fixtures=("frame_composition", "fog"),
        port_source="curated",
    )
    return contracts


def contract_is_typed(contract: PhaseContract | None) -> bool:
    return contract is not None and contract.port_source != "missing"


def resource_closure(phase_keys: tuple[str, ...]) -> tuple[RuntimeResource, ...]:
    contracts = phase_contract_registry()
    resources = {
        (resource.kind, resource.slot, resource.name): resource
        for key in phase_keys
        if key in contracts
        for resource in contracts[key].resources
    }
    return tuple(resources[key] for key in sorted(resources))


def fixture_closure(phase_keys: tuple[str, ...]) -> tuple[str, ...]:
    contracts = phase_contract_registry()
    return tuple(sorted({
        fixture
        for key in phase_keys
        if key in contracts
        for fixture in contracts[key].activation_fixtures
    }))
