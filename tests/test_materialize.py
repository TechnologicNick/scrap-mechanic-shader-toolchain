import json

import pytest

from shader_toolchain.materialize import (
    materialize_semantic_variant,
    select_semantic_record,
)
from shader_toolchain.reconstruct import ToolchainError


RECORDS = [
    {
        "selector": "SM_SHADER_0000000000000001",
        "source_name": "example",
        "stage": "pixel",
        "entry_point": "mainPS",
        "defines": ["PIXEL_SHADER", "FEATURE"],
        "semantic_hlsl_path": "semantic/example.hlsl",
    },
    {
        "selector": "SM_SHADER_0000000000000002",
        "source_name": "example",
        "stage": "pixel",
        "entry_point": "mainPS",
        "defines": ["PIXEL_SHADER"],
        "semantic_hlsl_path": "semantic/example.hlsl",
    },
]


def test_select_semantic_record_by_definition() -> None:
    assert select_semantic_record(RECORDS, required_defines=["FEATURE"])[
        "selector"
    ].endswith("1")


def test_ambiguous_semantic_selection_is_rejected() -> None:
    with pytest.raises(ToolchainError, match="matched 2 shaders"):
        select_semantic_record(RECORDS)


def test_materialize_shared_semantic_variant(tmp_path) -> None:
    corpus = tmp_path / "corpus"
    semantic = corpus / "semantic"
    semantic.mkdir(parents=True)
    (corpus / "manifest.json").write_text(
        json.dumps({"shaders": RECORDS}), encoding="utf-8"
    )
    (semantic / "example.hlsl").write_text(
        "// SM_SHARED_MODULE 1\nfloat4 mainPS() : SV_Target { return 1; }\n",
        encoding="utf-8",
    )
    output = tmp_path / "readable.hlsl"

    result = materialize_semantic_variant(
        corpus, "example", output, required_defines=["FEATURE"]
    )

    source = output.read_text(encoding="utf-8")
    assert result["selector"].endswith("1")
    assert "#define FEATURE 1" in source
    assert "SM_SELECT" not in source
