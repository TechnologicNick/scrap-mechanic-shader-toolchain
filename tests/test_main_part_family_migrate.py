from pathlib import Path

from shader_toolchain.main_part_family_migrate import (
    _changed_assets,
    _family_asset_dependencies,
    expand_family_includes,
    render_family_snippet,
)


def test_family_include_expansion_resolves_helper_dependencies(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "assets"
    includes = tmp_path / "include"
    assets.mkdir()
    includes.mkdir()
    (assets / "outer.hlsl").write_text(
        '#include "inner.hlsl"\nfloat outer;\n', encoding="utf-8"
    )
    (assets / "inner.hlsl").write_text("float inner;\n", encoding="utf-8")
    expanded = expand_family_includes(
        '#include "include/outer.hlsl"\n',
        asset_root=assets,
        semantic_include_root=includes,
    )
    assert "float inner;" in expanded
    assert "float outer;" in expanded
    assert "#include" not in expanded


def test_family_snippet_paths_are_relative_to_split_directory() -> None:
    assert render_family_snippet(
        '#include "include/main_part_projection_abi.hlsl"\n'
    ) == '#include "../main_part_projection_abi.hlsl"\n'


def test_family_asset_dependencies_follow_nested_includes(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "assets"
    includes = tmp_path / "include"
    assets.mkdir()
    includes.mkdir()
    (assets / "outer.hlsl").write_text(
        '#include "inner.hlsl"\nfloat outer;\n', encoding="utf-8"
    )
    (assets / "inner.hlsl").write_text("float inner;\n", encoding="utf-8")

    assert _family_asset_dependencies(
        '#include "../outer.hlsl"\n',
        asset_root=assets,
        semantic_include_root=includes,
    ) == {"outer.hlsl", "inner.hlsl"}


def test_changed_assets_compare_recipe_and_installed_bytes(
    tmp_path: Path, monkeypatch,
) -> None:
    assets = tmp_path / "assets"
    includes = tmp_path / "include"
    assets.mkdir()
    includes.mkdir()
    (assets / "same.hlsl").write_text("same\n", encoding="utf-8")
    (includes / "same.hlsl").write_text("same\n", encoding="utf-8")
    (assets / "changed.hlsl").write_text("new\n", encoding="utf-8")
    (includes / "changed.hlsl").write_text("old\n", encoding="utf-8")
    (assets / "missing.hlsl").write_text("new\n", encoding="utf-8")
    monkeypatch.setattr(
        "shader_toolchain.main_part_family_migrate._asset_closure",
        lambda _root: {"same.hlsl", "changed.hlsl", "missing.hlsl"},
    )

    assert _changed_assets(assets, includes) == {
        "changed.hlsl",
        "missing.hlsl",
    }
