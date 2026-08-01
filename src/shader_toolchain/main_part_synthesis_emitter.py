"""Emit executable HLSL from induced ``main_part`` family templates.

The synthesis analyzer intentionally works on fingerprints.  This backend
keeps the corresponding HLSL token stream, anti-unifies complete policy
families, and writes one shared evaluator plus thin ABI-preserving wrappers.
Each policy gap is emitted as a real typed helper. Its signature is derived
from the region's live entry parameters, outputs, and canonicalized locals, so
permutations share executable structure without preprocessor substitution.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .compare import compare_bytecodes
from .hlsl import TOKEN
from .hlsl import hlsl_token_sha256, resolve_local_includes, semantic_module_variants
from .main_part_canonical_ir import canonicalize_main_part_body
from .main_part_family_miner import mine_main_part_families
from .main_part_synthesis import build_synthesis_readiness_report
from .reflect import ShaderReflector
from .recipes.main_part_families import HlslParameter, parse_entry_signature
from .sbc import D3DCompiler


_COMMENT = re.compile(r"^(?://|/\*)")
_INVALID_IDENTIFIER = re.compile(r"[^A-Za-z0-9_]")


@dataclass(frozen=True)
class SourceToken:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class SourcePreservingBody:
    signature: str
    parameters: tuple[HlslParameter, ...]
    opening_brace: int
    closing_brace: int
    tokens: tuple[SourceToken, ...]
    executable_tokens: tuple[str, ...]


@dataclass(frozen=True)
class EmittedFamilySource:
    family: str
    asset_filename: str
    evaluator: str
    asset_source: str
    assets: Mapping[str, str]
    wrappers: Mapping[str, str]
    common_token_ratio: float
    common_region_count: int
    policy_region_count: int


@dataclass(frozen=True)
class ValidatedEmittedFamily:
    emitted: EmittedFamilySource
    selectors: tuple[str, ...]
    assembly_exact_count: int
    opcode_sequence_exact_count: int
    comparisons: Mapping[str, Mapping[str, Any]]


def _entry_braces(source: str, entry_point: str) -> tuple[int, int]:
    marker = re.search(rf"\bvoid\s+{re.escape(entry_point)}\s*\(", source)
    if marker is None:
        raise RuntimeError(f"semantic source has no {entry_point} entry point")
    opening = source.find("{", marker.end())
    if opening < 0:
        raise RuntimeError(f"semantic source has no {entry_point} body")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return opening, index
    raise RuntimeError(f"unterminated {entry_point} body")


def parse_source_preserving_body(
    source: str, entry_point: str = "commonPS",
) -> SourcePreservingBody:
    """Return exact source spans and a stable executable token stream."""
    signature, parameters = parse_entry_signature(source, entry_point)
    opening, closing = _entry_braces(source, entry_point)
    tokens = tuple(
        SourceToken(match.group(0), match.start(), match.end())
        for match in TOKEN.finditer(source, opening + 1, closing)
        if not match.group(0).isspace()
        and not _COMMENT.match(match.group(0))
    )
    canonical = canonicalize_main_part_body(source).split()
    if canonical[:1] == ["{"] and canonical[-1:] == ["}"]:
        canonical = canonical[1:-1]
    if len(canonical) != len(tokens):
        raise RuntimeError(
            "canonical and source-preserving token streams diverged: "
            f"{len(canonical)} != {len(tokens)}"
        )
    executable = tuple(
        "sm" + token[1:] if token.startswith("%") else token
        for token in canonical
    )
    return SourcePreservingBody(
        signature=signature,
        parameters=parameters,
        opening_brace=opening,
        closing_brace=closing,
        tokens=tokens,
        executable_tokens=executable,
    )


def _common_sequence(streams: list[list[str]]) -> list[str]:
    common = list(streams[0]) if streams else []
    for stream in streams[1:]:
        matcher = SequenceMatcher(
            a=common, b=stream, autojunk=True,
        )
        common = [
            token
            for block in matcher.get_matching_blocks()
            for token in common[block.a:block.a + block.size]
        ]
        if not common:
            break
    return common


def _anchor_positions(stream: list[str], anchors: list[str]) -> list[int]:
    positions: list[int] = []
    cursor = 0
    for anchor in anchors:
        while cursor < len(stream) and stream[cursor] != anchor:
            cursor += 1
        if cursor == len(stream):
            raise RuntimeError("source anti-unification anchor was lost")
        positions.append(cursor)
        cursor += 1
    return positions


def _common_runs(
    streams: Mapping[str, tuple[str, ...]], *, minimum_tokens: int,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    selectors = tuple(streams)
    common = _common_sequence([list(streams[key]) for key in selectors])
    if not common:
        return ()
    positions = {
        key: _anchor_positions(list(streams[key]), common)
        for key in selectors
    }
    runs: list[tuple[tuple[int, int], ...]] = []
    start = 0
    for index in range(1, len(common) + 1):
        contiguous = index < len(common) and all(
            positions[key][index] == positions[key][index - 1] + 1
            for key in selectors
        )
        if contiguous:
            continue
        if index - start >= minimum_tokens:
            runs.append(tuple(
                (positions[key][start], positions[key][index - 1] + 1)
                for key in selectors
            ))
        start = index
    return tuple(runs)


def _segments(
    streams: Mapping[str, tuple[str, ...]],
    runs: tuple[tuple[tuple[int, int], ...], ...],
) -> dict[str, tuple[tuple[int, int], ...]]:
    selectors = tuple(streams)
    output: dict[str, tuple[tuple[int, int], ...]] = {}
    for selector_index, selector in enumerate(selectors):
        cursor = 0
        values: list[tuple[int, int]] = []
        for run in runs:
            start, end = run[selector_index]
            values.append((cursor, start))
            cursor = end
        values.append((cursor, len(streams[selector])))
        output[selector] = tuple(values)
    return output


def _pascal(value: str) -> str:
    return "".join(
        part.capitalize()
        for part in _INVALID_IDENTIFIER.sub("_", value).split("_")
        if part
    )


def _macro(value: str) -> str:
    return _INVALID_IDENTIFIER.sub("_", value).upper()


def _render_tokens(tokens: Iterable[str], *, width: int = 18) -> str:
    return "\n".join(_pretty_lines(tokens, initial_indent=1))


def _pretty_lines(
    tokens: Iterable[str], *, initial_indent: int = 0,
) -> list[str]:
    values = list(tokens)
    lines: list[str] = []
    current = ""
    indent = initial_indent

    def flush() -> None:
        nonlocal current
        if current.strip():
            lines.append("  " * indent + current.strip())
        current = ""

    def append(token: str) -> None:
        nonlocal current
        previous = current[-1:] if current else ""
        compact_before = token in {",", ";", ")", "]", "."}
        compact_after = previous in {"(", "[", "."}
        if current and not compact_before and not compact_after:
            current += " "
        current += token

    for token in values:
        if token == "{":
            append(token)
            flush()
            indent += 1
        elif token == "}":
            flush()
            indent = max(initial_indent, indent - 1)
            append(token)
            flush()
        elif token == ";":
            append(token)
            flush()
        else:
            append(token)
    flush()
    return lines


def _render_macro(name: str, tokens: Iterable[str]) -> str:
    values = list(tokens)
    if not values:
        return f"#define {name}\n"
    chunks = [line.strip() for line in _pretty_lines(values)]
    if len(chunks) == 1:
        return f"#define {name} {chunks[0]}\n"
    return (
        f"#define {name} \\\n  "
        + " \\\n  ".join(chunks)
        + "\n"
    )


def _statement_units(tokens: tuple[str, ...]) -> tuple[tuple[int, int], ...]:
    """Split a function body at complete top-level statement boundaries."""
    units: list[tuple[int, int]] = []
    start = 0
    braces = 0
    parentheses = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "(":
            parentheses += 1
        elif token == ")":
            parentheses = max(0, parentheses - 1)
        elif token == "{":
            braces += 1
        elif token == "}":
            braces = max(0, braces - 1)
            if braces == 0 and parentheses == 0:
                next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
                if next_token not in {"else", "while"}:
                    units.append((start, index + 1))
                    start = index + 1
        elif token == ";" and braces == 0 and parentheses == 0:
            units.append((start, index + 1))
            start = index + 1
        index += 1
    if start < len(tokens):
        units.append((start, len(tokens)))
    return tuple((start, end) for start, end in units if start != end)


def _flatten_units(
    tokens: tuple[str, ...], units: tuple[tuple[int, int], ...],
    start: int, end: int,
) -> tuple[str, ...]:
    if start == end:
        return ()
    return tokens[units[start][0]:units[end - 1][1]]


def _region_role(tokens: Iterable[str]) -> str:
    values = set(tokens)
    roles = []
    for resources, role in (
        ({"tCutoff", "cb_dissolve"}, "DISSOLVE_COVERAGE"),
        ({"tDif", "tAsg", "tNor"}, "MATERIAL_FRONTEND"),
        ({"tLightColorMap"}, "DIRECTIONAL_LIGHT"),
        ({"sbVoxelLightIds", "cb_arrPoint", "cb_arrSpot"}, "CLUSTERED_LIGHTING"),
        ({"taCookies"}, "SPOT_COOKIE"),
        ({"taReflection", "cb_reflections"}, "REFLECTION_PROBES"),
        ({"tFrame"}, "FRAME_COMPOSITION"),
    ):
        if resources & values:
            roles.append(role)
    return "_AND_".join(roles) if roles else "POLICY"


def _helper_parameter(parameter: HlslParameter) -> str:
    qualifier = "out " if parameter.output else ""
    semantic = parameter.semantic
    direction = "out" if parameter.output else "in"
    name = f"sm{direction}_{semantic.name.lower()}{semantic.index}"
    return f"{qualifier}{parameter.type_name} {name}"


def _stable_parameter_name(parameter: HlslParameter) -> str:
    semantic = parameter.semantic
    direction = "out" if parameter.output else "in"
    return f"sm{direction}_{semantic.name.lower()}{semantic.index}"


_LOCAL_TYPE = re.compile(r"^(?:float|uint|int|bool)(?:[1-4](?:x[1-4])?)?$")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _local_declarations(
    tokens: tuple[str, ...], units: tuple[tuple[int, int], ...],
) -> tuple[tuple[tuple[str, str], ...], int]:
    """Read the decompiler's leading uninitialized local declarations."""
    declarations: list[tuple[str, str]] = []
    consumed = 0
    for start, end in units:
        value = tokens[start:end]
        if not value or not _LOCAL_TYPE.fullmatch(value[0]) or value[-1] != ";":
            break
        if "=" in value:
            break
        type_name = value[0]
        names = [
            token for token in value[1:-1]
            if _IDENTIFIER.fullmatch(token) and token not in {"const", "static"}
        ]
        if not names:
            break
        declarations.extend((name, type_name) for name in names)
        consumed += 1
    return tuple(declarations), consumed


def _state_tokens(tokens: Iterable[str], fields: set[str]) -> tuple[str, ...]:
    output: list[str] = []
    for token in tokens:
        if token in fields:
            output.extend(("state", ".", token))
        else:
            output.append(token)
    return tuple(output)


def _state_declaration(
    state_type: str,
    parameters: tuple[HlslParameter, ...],
    locals_: tuple[tuple[str, str], ...],
) -> str:
    fields = [
        f"  {parameter.type_name} {_stable_parameter_name(parameter)};"
        for parameter in parameters
    ]
    fields.extend(f"  {type_name} {name};" for name, type_name in locals_)
    return f"struct {state_type}\n{{\n" + "\n".join(fields) + "\n};\n"


def _policy_name(family_macro: str, policy: tuple[str, str]) -> str:
    return f"{family_macro}_POLICY_{_macro(policy[0])}_{_macro(policy[1])}"


def _wrapper_prefix(source: str) -> str:
    marker = source.find("// 3Dmigoto declarations")
    if marker < 0:
        raise RuntimeError("source is already structural or lacks lift marker")
    return source[:marker].rstrip()


def _logical_preprocessor_lines(source: str) -> list[str]:
    output: list[str] = []
    pending = ""
    for line in source.splitlines():
        stripped = line.rstrip()
        continuation = stripped.endswith("\\")
        value = stripped[:-1] if continuation else stripped
        pending += (" " if pending else "") + value.strip()
        if not continuation:
            output.append(pending)
            pending = ""
    if pending:
        output.append(pending)
    return output


def _stable_parameter_declaration(parameter: HlslParameter) -> str:
    semantic = parameter.semantic
    direction = "out" if parameter.output else "in"
    stable = f"sm{direction}_{semantic.name.lower()}{semantic.index}"
    return re.sub(
        rf"\b{re.escape(parameter.variable)}\b(?=\s*:)",
        stable,
        parameter.declaration,
    )


def _recover_installed_source(
    wrapper: str, asset: str, evaluator: str,
) -> str:
    """Reconstruct an executable entry body from a prior synthesized asset."""
    policy_match = re.search(
        r"(?m)^#define\s+(SM_SYNTH_[A-Z0-9_]+_POLICY_[A-Z0-9_]+)\s+1$",
        wrapper,
    )
    if policy_match is None:
        raise RuntimeError("installed synthesis wrapper has no policy coordinate")
    selected_policy = policy_match.group(1)
    current_policy: str | None = None
    replacements: dict[str, tuple[str, ...]] = {}
    for line in _logical_preprocessor_lines(asset):
        branch = re.match(r"#(?:if|elif)\s+defined\(([^)]+)\)", line)
        if branch:
            current_policy = branch.group(1)
            continue
        if line.startswith("#else"):
            current_policy = None
            continue
        if current_policy != selected_policy:
            continue
        definition = re.match(r"#define\s+(\S+)(?:\s+(.*))?$", line)
        if definition:
            replacement = definition.group(2) or ""
            replacements[definition.group(1)] = tuple(
                match.group(0)
                for match in TOKEN.finditer(replacement)
                if not match.group(0).isspace()
            )
    evaluator_marker = re.search(
        rf"\bvoid\s+{re.escape(evaluator)}\s*\(", asset
    )
    if evaluator_marker is None:
        raise RuntimeError(f"installed asset has no {evaluator}")
    opening = asset.find("{", evaluator_marker.end())
    undef = asset.find("\n\n#undef", opening)
    closing = asset.rfind("}", opening, undef if undef >= 0 else len(asset))
    if opening < 0 or closing < opening:
        raise RuntimeError(f"installed asset has no recoverable {evaluator} body")
    body_tokens = [
        match.group(0)
        for match in TOKEN.finditer(asset, opening + 1, closing)
        if not match.group(0).isspace()
        and not _COMMENT.match(match.group(0))
    ]
    expanded: list[str] = []
    for token in body_tokens:
        expanded.extend(replacements.get(token, (token,)))
    _signature, parameters = parse_entry_signature(wrapper, "commonPS")
    prefix = wrapper[:wrapper.find(policy_match.group(0))].rstrip()
    stable_signature = "void commonPS(\n  " + ",\n  ".join(
        _stable_parameter_declaration(parameter) for parameter in parameters
    ) + ")"
    return (
        prefix
        + "\n\n// 3Dmigoto declarations\n#define cmp -\n"
        + stable_signature
        + "\n{\n"
        + "\n".join(_pretty_lines(expanded, initial_indent=1))
        + "\n}\n"
    )


def emit_family_source(
    family: str,
    sources: Mapping[str, str],
    policies: Mapping[str, tuple[str, str]],
    *,
    entry_point: str = "commonPS",
    minimum_common_tokens: int = 12,
) -> EmittedFamilySource:
    """Generate one executable family asset and thin per-policy wrappers."""
    selectors = tuple(sorted(sources))
    if set(selectors) != set(policies):
        raise RuntimeError("every emitted selector needs exactly one policy")
    bodies = {
        selector: parse_source_preserving_body(sources[selector], entry_point)
        for selector in selectors
    }
    baseline = bodies[selectors[0]]
    interface = tuple(
        (parameter.type_name, parameter.semantic, parameter.output)
        for parameter in baseline.parameters
    )
    for selector in selectors[1:]:
        observed = tuple(
            (parameter.type_name, parameter.semantic, parameter.output)
            for parameter in bodies[selector].parameters
        )
        if observed != interface:
            raise RuntimeError(f"family entry interface differs at {selector}")
    raw_token_streams = {
        selector: bodies[selector].executable_tokens
        for selector in selectors
    }
    raw_units = {
        selector: _statement_units(raw_token_streams[selector])
        for selector in selectors
    }
    locals_by_selector: dict[str, tuple[tuple[str, str], ...]] = {}
    consumed_by_selector: dict[str, int] = {}
    # Canonical temporary ordinals are allocation-order dependent and can
    # change type between quality levels. Rename locals by type and ordinal
    # before family alignment so the state contract is stable.
    for selector in selectors:
        declarations, _consumed = _local_declarations(
            raw_token_streams[selector], raw_units[selector]
        )
        counters: dict[str, int] = {}
        rename: dict[str, str] = {}
        for name, type_name in declarations:
            index = counters.get(type_name, 0)
            counters[type_name] = index + 1
            rename[name] = f"smLocal{_pascal(type_name)}{index}"
        raw_token_streams[selector] = tuple(
            rename.get(token, token) for token in raw_token_streams[selector]
        )
        raw_units[selector] = _statement_units(raw_token_streams[selector])

    local_types: dict[str, str] = {}
    local_order: list[str] = []
    for selector in selectors:
        declarations, consumed = _local_declarations(
            raw_token_streams[selector], raw_units[selector]
        )
        locals_by_selector[selector] = declarations
        consumed_by_selector[selector] = consumed
        for name, type_name in declarations:
            previous = local_types.setdefault(name, type_name)
            if previous != type_name:
                raise RuntimeError(f"local {name} changes type across family")
            if name not in local_order:
                local_order.append(name)
    locals_ = tuple((name, local_types[name]) for name in local_order)
    token_streams: dict[str, tuple[str, ...]] = {}
    units: dict[str, tuple[tuple[int, int], ...]] = {}
    for selector in selectors:
        remaining_units = raw_units[selector][consumed_by_selector[selector]:]
        if remaining_units:
            start = remaining_units[0][0]
            remaining = raw_token_streams[selector][start:]
        else:
            remaining = ()
        token_streams[selector] = tuple(remaining)
        units[selector] = _statement_units(token_streams[selector])
    streams = {
        selector: tuple(
            " ".join(token_streams[selector][start:end])
            for start, end in units[selector]
        )
        for selector in selectors
    }
    runs = _common_runs(streams, minimum_tokens=1)
    segments = _segments(streams, runs)
    family_pascal = _pascal(family)
    evaluator = "Evaluate" + family_pascal
    baseline_selector = selectors[0]
    region_names_list: list[str] = []
    role_counts: dict[str, int] = {}
    for start, end in segments[baseline_selector]:
        region_tokens = _flatten_units(
            token_streams[baseline_selector], units[baseline_selector],
            start, end,
        )
        role = _region_role(region_tokens)
        role_index = role_counts.get(role, 0)
        role_counts[role] = role_index + 1
        region_names_list.append(
            f"Evaluate{family_pascal}{_pascal(role)}{role_index}"
        )
    region_names = tuple(region_names_list)

    field_types = {
        _stable_parameter_name(parameter): parameter.type_name
        for parameter in baseline.parameters
    }
    field_types.update(local_types)
    output_fields = {
        _stable_parameter_name(parameter)
        for parameter in baseline.parameters if parameter.output
    }
    local_fields = set(local_types)
    region_ports: list[tuple[str, ...]] = []
    for region_index in range(len(region_names)):
        used = set()
        for selector in selectors:
            start, end = segments[selector][region_index]
            used.update(
                token for token in _flatten_units(
                    token_streams[selector], units[selector], start, end
                )
                if token in field_types
            )
        region_ports.append(tuple(
            name for name in field_types if name in used
        ))

    evaluator_lines: list[str] = [
        f"void {evaluator}(\n  "
        + ", ".join(_helper_parameter(p) for p in baseline.parameters)
        + ")",
        "{",
    ]
    # FXC requires an entry-point output to be initialized before it can cross
    # an `inout` helper boundary, even when later common code completes the
    # write.  The original value is undefined at entry, so zero is the only
    # deterministic representation and does not erase any defined behavior.
    evaluator_lines.extend(
        f"  {_stable_parameter_name(parameter)} = ({parameter.type_name})0;"
        for parameter in baseline.parameters if parameter.output
    )
    evaluator_lines.extend(
        f"  {type_name} {name} = ({type_name})0;"
        for name, type_name in locals_
    )
    for index, region_name in enumerate(region_names):
        evaluator_lines.append(
            f"  {region_name}("
            + ", ".join(region_ports[index])
            + ");"
        )
        if index < len(runs):
            start, end = runs[index][0]
            evaluator_lines.extend(_pretty_lines(
                _flatten_units(
                    token_streams[baseline_selector],
                    units[baseline_selector], start, end,
                ),
                initial_indent=1,
            ))
    evaluator_lines.append("}")
    asset_filename = f"main_part_{family}.hlsl"
    evaluator_asset = (
        f"// Synthesized semantic family evaluator: {family}\n"
        "// Policy assets define typed residual helpers before including this file.\n\n"
        + "\n".join(evaluator_lines)
        + "\n"
    )
    assets: dict[str, str] = {asset_filename: evaluator_asset}
    policy_assets: dict[tuple[str, str], str] = {}
    for policy in sorted(set(policies.values())):
        selector = next(key for key in selectors if policies[key] == policy)
        helper_blocks: list[str] = []
        for region_index, (region_name, (start, end)) in enumerate(zip(
            region_names, segments[selector], strict=True,
        )):
            ports = region_ports[region_index]
            declarations = []
            for name in ports:
                qualifier = "inout " if name in output_fields | local_fields else ""
                declarations.append(f"{qualifier}{field_types[name]} {name}")
            region_tokens = _flatten_units(
                token_streams[selector], units[selector], start, end
            )
            helper_blocks.append(
                f"void {region_name}(\n  "
                + ", ".join(declarations)
                + ")\n{\n"
                + "\n".join(_pretty_lines(region_tokens, initial_indent=1))
                + "\n}\n"
            )
        policy_filename = (
            f"main_part_{family}_{policy[0]}_{policy[1]}.hlsl"
        )
        policy_assets[policy] = policy_filename
        assets[policy_filename] = (
            f"// Synthesized semantic family: {family}\n"
            f"// Policy: quality={policy[0]}, reflection={policy[1]}\n"
            "#ifndef cmp\n#define cmp -\n#endif\n\n"
            + "\n".join(helper_blocks)
            + f'\n#include "{asset_filename}"\n'
        )

    wrappers: dict[str, str] = {}
    for selector in selectors:
        source = sources[selector]
        body = bodies[selector]
        policy_asset = policy_assets[policies[selector]]
        arguments = ", ".join(
            parameter.variable for parameter in body.parameters
        )
        wrapper = (
            _wrapper_prefix(source)
            + "\n\n"
            + f'#include "include/{policy_asset}"\n\n'
            + body.signature
            + f"\n{{\n  {evaluator}(\n      {arguments});\n}}\n"
        )
        wrappers[selector] = wrapper

    baseline_count = len(token_streams[baseline_selector])
    common_count = sum(len(_flatten_units(
        token_streams[baseline_selector], units[baseline_selector], start, end
    )) for start, end in (run[0] for run in runs))
    return EmittedFamilySource(
        family=family,
        asset_filename=asset_filename,
        evaluator=evaluator,
        asset_source=evaluator_asset,
        assets=assets,
        wrappers=wrappers,
        common_token_ratio=common_count / max(1, baseline_count),
        common_region_count=len(runs),
        policy_region_count=len(region_names),
    )


def expand_emitted_wrapper(wrapper: str, emitted: EmittedFamilySource) -> str:
    include = re.compile(r'#include\s+"(?:include/)?([^"]+)"')

    def expand(source: str, stack: tuple[str, ...] = ()) -> str:
        def replace(match: re.Match[str]) -> str:
            filename = match.group(1)
            if filename not in emitted.assets:
                return match.group(0)
            if filename in stack:
                raise RuntimeError(f"cyclic synthesized include: {filename}")
            return expand(emitted.assets[filename], (*stack, filename))

        return include.sub(replace, source)

    expanded = expand(wrapper)
    if expanded == wrapper:
        raise RuntimeError("emitted wrapper does not contain a family asset")
    return expanded


def _manifest_policy(shader: Mapping[str, Any]) -> tuple[str, str]:
    defines = set(shader["defines"])
    quality = (
        "high" if "PS_SHADER_QUALITY_HIGH" in defines
        else "medium" if "PS_SHADER_QUALITY_MEDIUM" in defines
        else "default"
    )
    reflection = (
        "multi" if "PS_REFLECTION_MULTI" in defines
        else "single" if "PS_REFLECTION_SINGLE" in defines
        else "off"
    )
    return quality, reflection


def emit_corpus_family(corpus: Path, family: str) -> EmittedFamilySource:
    """Resolve and emit one readiness-report family from a corpus."""
    readiness = build_synthesis_readiness_report(corpus)
    matches = [
        template for template in readiness["templates"]
        if template["suggested_name"] == family
    ]
    snippet_root = corpus / "semantic" / "include" / "main_part"
    installed_asset = f"main_part_{family}.hlsl"
    installed_prefix = f"main_part_{family}"
    installed_selectors = tuple(sorted(
        path.stem for path in snippet_root.glob("SM_SHADER_*.hlsl")
        if installed_prefix in path.read_text(encoding="utf-8")
    ))
    if not matches and installed_selectors:
        # Re-emission must remain possible after the first successful install,
        # when the family miner correctly excludes its structural wrappers.
        selectors = installed_selectors
        template = None
    elif len(matches) == 1:
        template = matches[0]
        selectors = ()
    else:
        raise RuntimeError(
            f"synthesis family must resolve uniquely: {family} "
            f"(found {len(matches)})"
        )
    if installed_selectors:
        asset_root = corpus / "semantic" / "include"
        asset_path = asset_root / installed_asset
        installed_source = asset_path.read_text(encoding="utf-8")
        if installed_source.startswith("// Synthesized semantic family evaluator:"):
            # A typed family is already structural source. Reload it directly
            # instead of trying to reverse helper calls back into one flat body.
            # This keeps emission/validation/apply idempotent after installation.
            assets = {
                path.name: path.read_text(encoding="utf-8")
                for path in asset_root.glob(f"{installed_prefix}*.hlsl")
            }
            evaluator = "Evaluate" + _pascal(family)
            helper_names = set(re.findall(
                rf"(?m)^void\s+({re.escape(evaluator)}(?!\s*\()[A-Za-z0-9_]+)\s*\(",
                "\n".join(assets.values()),
            ))
            wrappers = {
                selector: (
                    snippet_root / f"{selector}.hlsl"
                ).read_text(encoding="utf-8").replace(
                    '#include "../', '#include "include/'
                )
                for selector in selectors
            }
            return EmittedFamilySource(
                family=family,
                asset_filename=installed_asset,
                evaluator=evaluator,
                asset_source=installed_source,
                assets=assets,
                wrappers=wrappers,
                common_token_ratio=0.0,
                common_region_count=max(0, len(helper_names) - 1),
                policy_region_count=len(helper_names),
            )
    if template is not None and template["readiness"] not in {
        "auto_composable", "auto_with_typed_residuals",
    }:
        raise RuntimeError(
            f"synthesis family is not emission-ready: {family} "
            f"({template['readiness']})"
        )
    if template is not None:
        mined = mine_main_part_families(corpus)
        candidate = next(
            value for value in mined["candidates"]
            if value["family_key"] == template["family_key"]
        )
        selectors = tuple(candidate["selectors"])
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    records = {shader["selector"]: shader for shader in manifest["shaders"]}
    if installed_selectors:
        asset_path = corpus / "semantic" / "include" / installed_asset
        installed_source = asset_path.read_text(encoding="utf-8")
        evaluator = "Evaluate" + _pascal(family)
        sources = {
            selector: _recover_installed_source(
                (snippet_root / f"{selector}.hlsl").read_text(encoding="utf-8"),
                installed_source,
                evaluator,
            )
            for selector in selectors
        }
    else:
        sources = {
            selector: (snippet_root / f"{selector}.hlsl").read_text(
                encoding="utf-8"
            )
            for selector in selectors
        }
    policies = {
        selector: _manifest_policy(records[selector])
        for selector in selectors
    }
    return emit_family_source(family, sources, policies)


def validate_emitted_family(
    corpus: Path, emitted: EmittedFamilySource,
) -> ValidatedEmittedFamily:
    """Compile every wrapper and prove its recovered DXBC ABI is unchanged."""
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    records = {shader["selector"]: shader for shader in manifest["shaders"]}
    compiler = D3DCompiler()
    reflector = ShaderReflector()
    comparisons: dict[str, Mapping[str, Any]] = {}
    for selector, wrapper in sorted(emitted.wrappers.items()):
        shader = records[selector]
        candidate = compiler.compile(
            expand_emitted_wrapper(wrapper, emitted),
            shader["entry_point"],
            {"pixel": "ps_5_0", "vertex": "vs_5_0"}[shader["stage"]],
        )
        key = str(shader["shader_key"]).removeprefix("0x").lower()
        baseline = (corpus / "dxbc" / f"{key}.dxbc").read_bytes()
        comparison, _baseline_assembly, _candidate_assembly = compare_bytecodes(
            baseline, candidate, compiler, reflector
        )
        if not comparison["abi_compatible"]:
            differences = ", ".join(comparison["abi_differences"])
            raise RuntimeError(
                f"{selector} synthesized family changes ABI: {differences}"
            )
        comparisons[selector] = comparison
    return ValidatedEmittedFamily(
        emitted=emitted,
        selectors=tuple(sorted(emitted.wrappers)),
        assembly_exact_count=sum(
            bool(value["assembly_exact"]) for value in comparisons.values()
        ),
        opcode_sequence_exact_count=sum(
            bool(value["opcode_sequence_exact"])
            for value in comparisons.values()
        ),
        comparisons=comparisons,
    )


def _installed_wrapper(wrapper: str) -> str:
    return wrapper.replace('#include "include/', '#include "../')


def install_validated_family(
    corpus: Path,
    validated: ValidatedEmittedFamily,
    *,
    gpu_cases: int = 0,
) -> dict[str, Any]:
    """Install a whole family atomically and optionally GPU-diff every member.

    The recipe asset, installed asset, snippets, and manifest are restored byte
    for byte if fingerprinting or any GPU campaign fails.
    """
    if gpu_cases < 0:
        raise ValueError("gpu_cases cannot be negative")
    emitted = validated.emitted
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = {shader["selector"]: shader for shader in manifest["shaders"]}
    semantic_root = (corpus / "semantic").resolve()
    include_root = corpus / "semantic" / "include"
    snippet_root = include_root / "main_part"
    recipe_root = Path(__file__).parent / "recipes" / "assets"
    recipe_assets = {
        filename: recipe_root / filename for filename in emitted.assets
    }
    installed_assets = {
        filename: include_root / filename for filename in emitted.assets
    }
    targets = [
        manifest_path, *recipe_assets.values(), *installed_assets.values(),
        *(
            snippet_root / f"{selector}.hlsl"
            for selector in validated.selectors
        ),
    ]
    backups = {
        path: path.read_bytes() if path.exists() else None
        for path in targets
    }
    gpu_reports: dict[str, Any] = {}
    try:
        for filename, source in emitted.assets.items():
            recipe_assets[filename].write_text(
                source, encoding="utf-8", newline="\n"
            )
            installed_assets[filename].write_text(
                source, encoding="utf-8", newline="\n"
            )
        for selector, wrapper in emitted.wrappers.items():
            (snippet_root / f"{selector}.hlsl").write_text(
                _installed_wrapper(wrapper), encoding="utf-8", newline="\n"
            )
            comparison = validated.comparisons[selector]
            records[selector]["semantic_assembly_exact"] = bool(
                comparison["assembly_exact"]
            )
            records[selector]["semantic_abi_compatible"] = True

        semantic_module = corpus / "semantic" / "main_part.hlsl"
        main_part_records = [
            shader for shader in manifest["shaders"]
            if shader["source_name"] == "main_part"
        ]
        variants = semantic_module_variants(
            semantic_module.read_text(encoding="utf-8"),
            {
                shader["selector"]: shader["defines"]
                for shader in main_part_records
            },
        )
        for selector in validated.selectors:
            expanded = resolve_local_includes(
                variants[selector], semantic_module, semantic_root
            )
            records[selector]["semantic_hlsl_token_sha256"] = (
                hlsl_token_sha256(expanded)
            )
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )

        if gpu_cases:
            from .gpu_fuzz import fuzz_semantic_shader

            for selector in validated.selectors:
                report = fuzz_semantic_shader(
                    corpus,
                    source_name="main_part",
                    pixel_selector=selector,
                    cases=gpu_cases,
                    verify_corpus=False,
                )
                if not report["comparison"]["passed"]:
                    raise RuntimeError(
                        f"{selector} failed synthesized GPU differential"
                    )
                gpu_reports[selector] = report["comparison"]
    except Exception:
        for path, content in backups.items():
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(content)
        raise
    return {
        "family": emitted.family,
        "asset": emitted.asset_filename,
        "selector_count": len(validated.selectors),
        "selectors": list(validated.selectors),
        "common_token_ratio": emitted.common_token_ratio,
        "common_region_count": emitted.common_region_count,
        "policy_region_count": emitted.policy_region_count,
        "assembly_exact_count": validated.assembly_exact_count,
        "opcode_sequence_exact_count": validated.opcode_sequence_exact_count,
        "gpu_case_count": gpu_cases,
        "gpu_validated_count": len(gpu_reports),
    }
