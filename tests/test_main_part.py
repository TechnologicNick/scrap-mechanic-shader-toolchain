from pathlib import Path

from shader_toolchain.recipes.main_character import (
    emit_character_variant_snippets,
)


def test_main_part_variants_are_emitted_as_independent_snippets(
    tmp_path: Path,
) -> None:
    bodies = emit_character_variant_snippets(
        tmp_path,
        "main_part",
        {
            "SM_SHADER_VERTEX": (
                '#include "include/shared_abi.hlsl"\n'
                "void mainVS() {}\n"
            ),
            "SM_SHADER_PIXEL": "void commonPS() {}\n",
        },
    )

    root = tmp_path / "semantic" / "include" / "main_part"
    vertex = (root / "SM_SHADER_VERTEX.hlsl").read_text(encoding="utf-8")
    pixel = (root / "SM_SHADER_PIXEL.hlsl").read_text(encoding="utf-8")
    assert "Semantic phase map" in vertex
    assert '#include "../shared_abi.hlsl"' in vertex
    assert "mainVS" in vertex and "commonPS" not in vertex
    assert "commonPS" in pixel and "mainVS" not in pixel
    assert bodies == {
        "SM_SHADER_VERTEX": (
            '#include "include/main_part/SM_SHADER_VERTEX.hlsl"\n'
        ),
        "SM_SHADER_PIXEL": (
            '#include "include/main_part/SM_SHADER_PIXEL.hlsl"\n'
        ),
    }
