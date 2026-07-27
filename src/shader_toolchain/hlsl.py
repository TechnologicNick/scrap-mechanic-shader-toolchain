"""Stable parsing and fingerprints for generated HLSL modules."""

from __future__ import annotations

import hashlib
import re


SELECTOR_LINE = re.compile(
    r"(?m)^#(?:if|elif) defined\((SM_SHADER_[0-9A-F]{16})\)\r?$"
)
END_MODULE = re.compile(r"(?m)^#endif\r?$")
TOKEN = re.compile(
    r"//[^\r\n]*|/\*.*?\*/|\s+|"
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r"[A-Za-z_$][A-Za-z0-9_$]*|"
    r"(?:0[xX][0-9A-Fa-f]+|(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)[A-Za-z]*|"
    r"<<=|>>=|\+\+|--|&&|\|\||==|!=|<=|>=|<<|>>|\+=|-=|\*=|/=|%=|&=|\|=|\^=|::|"
    r".",
    re.DOTALL,
)


class HlslFormatError(RuntimeError):
    pass


def module_variants(source: str) -> dict[str, str]:
    """Extract selector branches from one generated module."""
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
