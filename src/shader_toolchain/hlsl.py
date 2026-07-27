"""Stable parsing and fingerprints for generated HLSL modules."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


SELECTOR_LINE = re.compile(
    r"(?m)^#(?:if|elif) defined\((SM_SHADER_[0-9A-F]{16})\)\r?$"
)
END_MODULE = re.compile(r"(?m)^#endif\r?$")
FACTORED_MARKER = "// SM_FACTORED_MODULE 1"
SHARED_MARKER = "// SM_SHARED_MODULE 1"
VARIANT_MARKER = re.compile(r"^// SM_VARIANT (SM_SHADER_[0-9A-F]{16}):")
SELECT_MARKER = re.compile(
    r"^#(if|elif|else)(?: (.*?))? // SM_SELECT: "
    r"(SM_SHADER_[0-9A-F]{16}(?: SM_SHADER_[0-9A-F]{16})*)$"
)
SELECT_END = "#endif // SM_SELECT"
TOKEN = re.compile(
    r"//[^\r\n]*|/\*.*?\*/|\s+|"
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r"[A-Za-z_$][A-Za-z0-9_$]*|"
    r"(?:0[xX][0-9A-Fa-f]+|(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)[A-Za-z]*|"
    r"<<=|>>=|\+\+|--|&&|\|\||==|!=|<=|>=|<<|>>|\+=|-=|\*=|/=|%=|&=|\|=|\^=|::|"
    r".",
    re.DOTALL,
)
LOCAL_INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"\s*$', re.MULTILINE)


class HlslFormatError(RuntimeError):
    pass


def module_variants(
    source: str, definitions: dict[str, list[str]] | None = None
) -> dict[str, str]:
    """Extract selector branches from one generated module."""
    if FACTORED_MARKER in source:
        return _factored_module_variants(source, definitions)
    return _legacy_module_variants(source)


def render_shared_module(source_name: str, source: str) -> str:
    """Render one human-authored source compiled with recovered definitions."""
    return (
        f"// Semantic Scrap Mechanic shader module: {source_name}.hlsl\n"
        "// Compiled once per manifest variant with its recovered definitions.\n"
        f"{SHARED_MARKER}\n\n"
        + source.strip()
        + "\n"
    )


def semantic_module_variants(
    source: str, definitions: dict[str, list[str]]
) -> dict[str, str]:
    """Expand a shared semantic source or parse a factored semantic module."""
    if SHARED_MARKER not in source:
        return module_variants(source, definitions)
    return {
        selector: _definition_preamble(tokens) + source
        for selector, tokens in definitions.items()
    }


def _definition_preamble(tokens: list[str]) -> str:
    lines = ["// Recovered compile definitions."]
    for token in tokens:
        name, value = _define_parts(token)
        lines.append(f"#define {name} {value}")
    return "\n".join(lines) + "\n"


def _legacy_module_variants(source: str) -> dict[str, str]:
    matches = list(SELECTOR_LINE.finditer(source))
    variants: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            closing = END_MODULE.search(source, start)
            if not closing:
                raise HlslFormatError("generated HLSL module has no closing #endif")
            end = closing.start()
        variants[match.group(1)] = source[start:end].strip() + "\n"
    return variants


def _macro_values(selector: str, definitions: dict[str, list[str]]) -> dict[str, str]:
    values = {selector: "1"}
    for token in definitions[selector]:
        name, value = _define_parts(token)
        values[name] = value
    return values


def _evaluate_generated_expression(expression: str, values: dict[str, str]) -> bool:
    for alternative in expression.split(" || "):
        alternative = alternative.strip()
        plain = re.fullmatch(r"defined\(([A-Za-z_][A-Za-z0-9_]*)\)", alternative)
        if plain:
            if plain.group(1) in values:
                return True
            continue
        valued = re.fullmatch(
            r"\(defined\(([A-Za-z_][A-Za-z0-9_]*)\) && "
            r"([A-Za-z_][A-Za-z0-9_]*) == ([A-Za-z0-9_+.-]+)\)",
            alternative,
        )
        if valued and valued.group(1) == valued.group(2):
            if values.get(valued.group(1)) == valued.group(3):
                return True
            continue
        raise HlslFormatError(
            f"unsupported generated selection expression: {expression}"
        )
    return False


def _define_bridge_lines(
    variants: list[tuple[str, list[str]]]
) -> list[str]:
    lines = []
    for index, (selector, defines) in enumerate(variants):
        keyword = "#if" if index == 0 else "#elif"
        lines.append(f"{keyword} defined({selector})")
        for token in defines:
            name, value = _define_parts(token)
            lines.append(f"#define {name} {value}")
    lines.append("#endif")
    return lines


def _factored_module_variants(
    source: str, definitions: dict[str, list[str]] | None
) -> dict[str, str]:
    lines = source.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    selectors = [
        match.group(1)
        for line in lines
        if (match := VARIANT_MARKER.match(line)) is not None
    ]
    if not selectors or len(selectors) != len(set(selectors)):
        raise HlslFormatError("factored module has missing or duplicate variants")
    if definitions is not None:
        if set(definitions) != set(selectors):
            raise HlslFormatError("factored module variants differ from the manifest")
        begin = lines.index("// SM_DEFINE_BEGIN")
        end = lines.index("// SM_DEFINE_END")
        expected_bridge = _define_bridge_lines(
            [(selector, definitions[selector]) for selector in selectors]
        )
        if lines[begin + 1 : end] != expected_bridge:
            raise HlslFormatError("selector-to-define bridge differs from the manifest")
    output = {selector: [] for selector in selectors}
    active = set(selectors)
    stack: list[tuple[set[str], set[str]]] = []
    in_define_bridge = False
    for line in lines:
        if line == "// SM_DEFINE_BEGIN":
            in_define_bridge = True
            continue
        if line == "// SM_DEFINE_END":
            in_define_bridge = False
            continue
        if in_define_bridge or line == FACTORED_MARKER or VARIANT_MARKER.match(line):
            continue
        marker = SELECT_MARKER.match(line)
        if marker:
            kind, expression, selector_list = marker.groups()
            branch = set(selector_list.split())
            if kind == "if":
                stack.append((active, set()))
            elif not stack:
                raise HlslFormatError("factored module has an unmatched selection branch")
            parent, covered = stack[-1]
            if definitions is not None:
                if kind == "else":
                    evaluated = parent - covered
                else:
                    available = parent - covered
                    evaluated = {
                        selector
                        for selector in available
                        if _evaluate_generated_expression(
                            expression or "", _macro_values(selector, definitions)
                        )
                    }
                if evaluated != branch:
                    raise HlslFormatError(
                        "generated selection expression disagrees with its variants"
                    )
            active = parent & branch
            stack[-1] = (parent, covered | active)
            continue
        if line == SELECT_END:
            if not stack:
                raise HlslFormatError("factored module has an unmatched selection end")
            active, _covered = stack.pop()
            continue
        for selector in active:
            output[selector].append(line)
    if stack or in_define_bridge:
        raise HlslFormatError("factored module has an unterminated generated block")
    return {
        selector: "\n".join(variant).strip() + "\n"
        for selector, variant in output.items()
    }


def _common_prefix(values: list[list[str]]) -> list[str]:
    limit = min(map(len, values))
    index = 0
    while index < limit and all(
        value[index] == values[0][index] for value in values[1:]
    ):
        index += 1
    return values[0][:index]


def _common_suffix(values: list[list[str]]) -> list[str]:
    limit = min(map(len, values))
    size = 0
    while size < limit and all(
        value[-1 - size] == values[0][-1 - size] for value in values[1:]
    ):
        size += 1
    return values[0][-size:] if size else []


def _define_parts(token: str) -> tuple[str, str]:
    name, separator, value = token.partition("=")
    return name, value if separator else "1"


def _selector_expression(selectors: list[str]) -> str:
    return " || ".join(f"defined({selector})" for selector in selectors)


def _semantic_expression(
    group: list[dict[str, Any]], parent: list[dict[str, Any]]
) -> str | None:
    group_selectors = {variant["selector"] for variant in group}
    candidates = []
    tokens = sorted({token for variant in parent for token in variant["defines"]})
    for token in tokens:
        present = {
            variant["selector"] for variant in parent if token in variant["defines"]
        }
        if present != group_selectors:
            continue
        name, value = _define_parts(token)
        expression = (
            f"defined({name})"
            if value == "1" and "=" not in token
            else f"(defined({name}) && {name} == {value})"
        )
        candidates.append(expression)
    return min(candidates, key=lambda item: (len(item), item)) if candidates else None


def _factor_lines(variants: list[dict[str, Any]]) -> list[str]:
    values = [variant["lines"] for variant in variants]
    prefix = _common_prefix(values)
    remaining = [
        {**variant, "lines": variant["lines"][len(prefix) :]}
        for variant in variants
    ]
    suffix = _common_suffix([variant["lines"] for variant in remaining])
    if suffix:
        remaining = [
            {**variant, "lines": variant["lines"][: -len(suffix)]}
            for variant in remaining
        ]
    nonempty = [variant for variant in remaining if variant["lines"]]
    if not nonempty:
        return prefix + suffix

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for variant in nonempty:
        grouped[variant["lines"][0]].append(variant)
    groups = list(grouped.values())
    if len(groups) == 1 and len(nonempty) == len(variants):
        groups = [[variant] for variant in nonempty]

    described = [
        (_semantic_expression(group, variants), group) for group in groups
    ]
    described.sort(
        key=lambda item: (
            item[0] is None,
            item[0] or "",
            min(variant["selector"] for variant in item[1]),
        )
    )
    complete_partition = len(nonempty) == len(variants)
    output = list(prefix)
    for index, (semantic, group) in enumerate(described):
        selectors = sorted(variant["selector"] for variant in group)
        use_else = complete_partition and index == len(described) - 1
        if use_else:
            directive = "#else"
        else:
            keyword = "#if" if index == 0 else "#elif"
            directive = f"{keyword} {semantic or _selector_expression(selectors)}"
        output.append(f"{directive} // SM_SELECT: {' '.join(selectors)}")
        if len(group) == 1:
            output.extend(group[0]["lines"])
        else:
            output.extend(_factor_lines(group))
    output.append(SELECT_END)
    output.extend(suffix)
    return output


def render_factored_module(source_name: str, variants: list[dict[str, Any]]) -> str:
    """Render variants as a nested, definition-aware preprocessor decision tree."""
    variants = sorted(variants, key=lambda item: item["selector"])
    lines = [
        f"// Reconstructed Scrap Mechanic shader module: {source_name}.hlsl",
        "// Shared code is factored; define exactly one SM_SHADER_<key> selector.",
        FACTORED_MARKER,
    ]
    for variant in variants:
        defines = " ".join(variant["defines"]) or "<none>"
        lines.append(
            f"// SM_VARIANT {variant['selector']}: {variant['stage']} "
            f"{variant['entry_point']}; defines: {defines}"
        )

    lines.extend(["", "// SM_DEFINE_BEGIN"])
    lines.extend(
        _define_bridge_lines(
            [(variant["selector"], variant["defines"]) for variant in variants]
        )
    )
    lines.extend(["// SM_DEFINE_END", ""])

    factored = [
        {
            **variant,
            "lines": variant["hlsl"].replace("\r\n", "\n").replace("\r", "\n").rstrip().split("\n"),
        }
        for variant in variants
    ]
    lines.extend(_factor_lines(factored))
    lines.append("")
    return "\n".join(lines)


def hlsl_tokens(source: str) -> list[str]:
    """Return lexical tokens while deliberately ignoring comments and whitespace."""
    tokens = []
    for match in TOKEN.finditer(source):
        value = match.group(0)
        if value.isspace() or value.startswith("//") or value.startswith("/*"):
            continue
        tokens.append(value)
    return tokens


def hlsl_token_sha256(source: str) -> str:
    """Hash an unambiguous length-prefixed HLSL token stream."""
    digest = hashlib.sha256()
    for token in hlsl_tokens(source):
        encoded = token.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "little"))
        digest.update(encoded)
    return digest.hexdigest()


def resolve_local_includes(
    source: str,
    source_path: Path,
    root: Path,
    _stack: frozenset[Path] | None = None,
) -> str:
    """Inline quoted includes while preventing paths from escaping the corpus."""
    root = root.resolve()
    source_path = source_path.resolve()
    stack = (_stack or frozenset()) | {source_path}

    def replace(match: re.Match[str]) -> str:
        include = (source_path.parent / match.group(1)).resolve()
        try:
            include.relative_to(root)
        except ValueError as error:
            raise HlslFormatError(f"include escapes semantic root: {match.group(1)}") from error
        if not include.is_file():
            raise HlslFormatError(f"semantic include does not exist: {match.group(1)}")
        if include in stack:
            raise HlslFormatError(f"cyclic semantic include: {match.group(1)}")
        included = include.read_text(encoding="utf-8")
        return resolve_local_includes(included, include, root, stack).rstrip()

    return LOCAL_INCLUDE.sub(replace, source)
