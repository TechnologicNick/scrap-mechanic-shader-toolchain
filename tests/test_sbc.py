import pytest

from shader_toolchain.sbc import FormatError, lz4_decompress_block


def test_lz4_literal_only_block() -> None:
    assert lz4_decompress_block(b"\x50hello", 5) == b"hello"


def test_lz4_size_mismatch_is_rejected() -> None:
    with pytest.raises(FormatError, match="size mismatch"):
        lz4_decompress_block(b"\x50hello", 6)

