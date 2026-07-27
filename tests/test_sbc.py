import pytest

from shader_toolchain.sbc import (
    FormatError,
    lz4_compress_literals,
    lz4_decompress_block,
)


def test_lz4_literal_only_block() -> None:
    assert lz4_decompress_block(b"\x50hello", 5) == b"hello"


def test_lz4_size_mismatch_is_rejected() -> None:
    with pytest.raises(FormatError, match="size mismatch"):
        lz4_decompress_block(b"\x50hello", 6)


@pytest.mark.parametrize("size", [0, 1, 14, 15, 270, 4096])
def test_literal_lz4_round_trip(size: int) -> None:
    source = bytes(index % 251 for index in range(size))
    assert lz4_decompress_block(lz4_compress_literals(source), size) == source
