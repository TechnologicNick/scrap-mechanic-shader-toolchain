import json

import pytest

from shader_toolchain.build import (
    meaningfully_edited,
    select_shader_source,
    serialize_cache,
    serialize_payload,
    stable_diagnostic,
)
from shader_toolchain.hlsl import hlsl_token_sha256, module_variants
from shader_toolchain.sbc import parse_cache, parse_payload
from shader_toolchain.reconstruct import ToolchainError


def test_module_variants_extracts_generated_branches() -> None:
    source = """// module
#if defined(SM_SHADER_000000000000000A)
void first() {}
#elif defined(SM_SHADER_000000000000000B)
void second() {}
#endif
"""
    assert module_variants(source) == {
        "SM_SHADER_000000000000000A": "void first() {}\n",
        "SM_SHADER_000000000000000B": "void second() {}\n",
    }


def test_cache_metadata_serialization_round_trip(tmp_path) -> None:
    manifest = {
        "jobs": [{"job_key": "0x0000000000000020", "shader_index": 0}],
        "resource_ids": ["00" * 16],
        "shaders": [
            {
                "shader_key": "0x0000000000000010",
                "stage_value": 2,
                "resource_id_indices": [0],
                "descriptor": "example:mainPS  PIXEL_SHADER",
            }
        ],
    }
    bundle = b"BSCDexample"
    cache = serialize_cache(serialize_payload(manifest, bundle))
    path = tmp_path / "shaders.sbc"
    path.write_bytes(cache)

    header, payload = parse_cache(path)
    metadata, parsed_bundle = parse_payload(payload)

    assert header["shader_cache_version"] == 1
    assert parsed_bundle == bundle
    assert metadata["shaders"][0]["source_name"] == "example"
    assert metadata["jobs"] == manifest["jobs"]


def test_stable_diagnostic_removes_local_path() -> None:
    message = (
        "D3DCompile failed: C:\\machine\\reconstructed.hlsl(12,4): "
        "error X3004: undeclared identifier 'thing'\n\x00"
    )
    assert stable_diagnostic(message) == "error X3004: undeclared identifier 'thing'"


def test_meaningful_edit_ignores_formatting_but_detects_code_change() -> None:
    shader = {
        "selector": "SM_SHADER_A",
        "hlsl_token_sha256": hlsl_token_sha256("return 1;"),
    }
    assert not meaningfully_edited(shader, "/* comment */ return   1 ;")
    assert meaningfully_edited(shader, "return 2;")


def semantic_shader() -> dict[str, str]:
    return {
        "selector": "SM_SHADER_A",
        "hlsl_token_sha256": hlsl_token_sha256("raw();"),
        "semantic_hlsl_token_sha256": hlsl_token_sha256("readable();"),
    }


def test_semantic_edit_takes_precedence_over_unchanged_raw_hlsl() -> None:
    assert select_shader_source(
        semantic_shader(), "raw();", "changed_readable();", recompile_all=False
    ) == ("changed_readable();", "semantic", "edited-semantic")


def test_unchanged_semantic_shader_preserves_exact_bytecode() -> None:
    assert select_shader_source(
        semantic_shader(), "raw();", "readable();", recompile_all=False
    ) == (None, "exact", "unchanged-exact")


def test_research_build_prefers_semantic_hlsl() -> None:
    assert select_shader_source(
        semantic_shader(), "raw();", "readable();", recompile_all=True
    ) == ("readable();", "semantic", "research-semantic")


def test_conflicting_raw_and_semantic_edits_are_rejected() -> None:
    with pytest.raises(ToolchainError, match="both raw and semantic HLSL"):
        select_shader_source(
            semantic_shader(), "changed_raw();", "changed_readable();", recompile_all=False
        )
