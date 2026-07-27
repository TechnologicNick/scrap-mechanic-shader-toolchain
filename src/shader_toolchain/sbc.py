#!/usr/bin/env python3
"""Inspect and extract Scrap Mechanic's Cache/Shaders/Release/shaders.sbc.

The file consists of a 16-byte GenericCache header, a small version payload,
an LZ4 block, Scrap Mechanic shader metadata, and a D3DCompressShaders bundle.
On Windows, d3dcompiler_47.dll is used to recover each individual DXBC blob and
optionally its assembly listing.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path
from typing import Any


STAGE_NAMES = {1: "vertex", 2: "pixel", 4: "compute"}


class FormatError(RuntimeError):
    pass


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def take(self, size: int) -> bytes:
        end = self.offset + size
        if size < 0 or end > len(self.data):
            raise FormatError(
                f"read past end at 0x{self.offset:x}: requested {size} bytes"
            )
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def unpack(self, fmt: str) -> tuple[Any, ...]:
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self.take(size))

    def u8(self) -> int:
        return self.unpack("<B")[0]

    def u16(self) -> int:
        return self.unpack("<H")[0]

    def u32(self) -> int:
        return self.unpack("<I")[0]

    def u64(self) -> int:
        return self.unpack("<Q")[0]


def lz4_decompress_block(source: bytes, expected_size: int) -> bytes:
    """Decode the raw LZ4 block used by GenericCache (no frame header)."""
    src = Reader(source)
    output = bytearray()
    while src.offset < len(source):
        token = src.u8()
        literal_length = token >> 4
        if literal_length == 15:
            while True:
                extra = src.u8()
                literal_length += extra
                if extra != 255:
                    break
        output.extend(src.take(literal_length))
        if src.offset == len(source):
            break

        match_offset = src.u16()
        if match_offset == 0 or match_offset > len(output):
            raise FormatError(f"invalid LZ4 match offset {match_offset}")
        match_length = (token & 0x0F) + 4
        if (token & 0x0F) == 15:
            while True:
                extra = src.u8()
                match_length += extra
                if extra != 255:
                    break
        match_start = len(output) - match_offset
        for index in range(match_length):
            output.append(output[match_start + index])

    if len(output) != expected_size:
        raise FormatError(
            f"LZ4 size mismatch: got {len(output)}, expected {expected_size}"
        )
    return bytes(output)


def parse_cache(path: Path) -> tuple[dict[str, Any], bytes]:
    file_data = path.read_bytes()
    reader = Reader(file_data)
    version, custom_size, compressed_size, uncompressed_size = reader.unpack("<4I")
    if version != 1:
        raise FormatError(f"unsupported GenericCache version {version}")
    if custom_size != 4:
        raise FormatError(f"unexpected GenericCache custom-data size {custom_size}")
    cache_version = reader.u32()
    compressed = reader.take(compressed_size)
    if reader.offset != len(file_data):
        raise FormatError(f"{len(file_data) - reader.offset} trailing cache bytes")
    payload = lz4_decompress_block(compressed, uncompressed_size)
    header = {
        "sha256": hashlib.sha256(file_data).hexdigest(),
        "file_size": len(file_data),
        "generic_cache_version": version,
        "shader_cache_version": cache_version,
        "compressed_size": compressed_size,
        "uncompressed_size": uncompressed_size,
    }
    return header, payload


def parse_payload(payload: bytes) -> tuple[dict[str, Any], bytes]:
    reader = Reader(payload)
    shader_count = reader.u16()
    shader_keys = [reader.u64() for _ in range(shader_count)]

    job_count = reader.u32()
    jobs = []
    for _ in range(job_count):
        job_key, shader_index = reader.unpack("<QH")
        if shader_index >= shader_count:
            raise FormatError(f"job refers to shader index {shader_index}")
        jobs.append({"job_key": f"0x{job_key:016x}", "shader_index": shader_index})

    resource_id_count = reader.u16()
    resource_ids = [reader.take(16).hex() for _ in range(resource_id_count)]

    bundle_size = reader.u64()
    bundle = reader.take(bundle_size)
    if not bundle.startswith(b"BSCD"):
        raise FormatError("D3DCompressShaders bundle does not start with BSCD")

    blob_indices = [reader.u16() for _ in range(shader_count)]
    if any(index >= shader_count for index in blob_indices):
        raise FormatError("shader metadata contains an invalid D3D bundle index")
    stages = [reader.u8() for _ in range(shader_count)]
    resource_counts = [reader.u16() for _ in range(shader_count)]
    descriptor_lengths = [reader.u16() for _ in range(shader_count)]

    shaders = []
    for index in range(shader_count):
        refs = [reader.u16() for _ in range(resource_counts[index])]
        if any(ref >= resource_id_count for ref in refs):
            raise FormatError(f"shader {index} contains an invalid resource ID index")
        raw_descriptor = reader.take(descriptor_lengths[index])
        descriptor = raw_descriptor.decode("utf-8", errors="replace")
        identity, _, defines = descriptor.partition("  ")
        source_name, separator, entry_point = identity.partition(":")
        shaders.append(
            {
                "index": index,
                "shader_key": f"0x{shader_keys[index]:016x}",
                "bundle_index": blob_indices[index],
                "stage_value": stages[index],
                "stage": STAGE_NAMES.get(stages[index], f"unknown-{stages[index]}"),
                "source_name": source_name,
                "entry_point": entry_point if separator else "",
                "defines": defines.split() if defines else [],
                "descriptor": descriptor,
                "resource_id_indices": refs,
            }
        )

    if reader.offset != len(payload):
        raise FormatError(f"{len(payload) - reader.offset} trailing payload bytes")
    metadata = {
        "shader_count": shader_count,
        "job_count": job_count,
        "resource_id_count": resource_id_count,
        "d3d_bundle_size": bundle_size,
        "resource_ids": resource_ids,
        "jobs": jobs,
        "shaders": shaders,
    }
    return metadata, bundle


class D3DCompiler:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("DXBC extraction requires Windows and d3dcompiler_47.dll")
        self.dll = ctypes.WinDLL("d3dcompiler_47.dll")
        self.decompress = self.dll.D3DDecompressShaders
        self.decompress.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_uint),
        ]
        self.decompress.restype = ctypes.c_long
        self.disassemble = self.dll.D3DDisassemble
        self.disassemble.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_uint,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self.disassemble.restype = ctypes.c_long

    @staticmethod
    def _blob_bytes(blob: int) -> bytes:
        vtable = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        get_pointer = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(vtable[3])
        get_size = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)(vtable[4])
        pointer = get_pointer(blob)
        size = get_size(blob)
        return ctypes.string_at(pointer, size)

    @staticmethod
    def _release(blob: int) -> None:
        vtable = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
        release(blob)

    def extract(self, bundle: bytes, shader_count: int) -> list[bytes]:
        source = ctypes.create_string_buffer(bundle)
        blobs = (ctypes.c_void_p * shader_count)()
        total = ctypes.c_uint()
        result = self.decompress(
            source, len(bundle), shader_count, 0, None, 0, blobs, ctypes.byref(total)
        )
        if result < 0:
            raise RuntimeError(f"D3DDecompressShaders failed with HRESULT 0x{result & 0xffffffff:08x}")
        if total.value != shader_count:
            raise RuntimeError(f"D3D decompressed {total.value} shaders, expected {shader_count}")
        output = []
        try:
            for blob in blobs:
                output.append(self._blob_bytes(blob))
        finally:
            for blob in blobs:
                if blob:
                    self._release(blob)
        return output

    def to_assembly(self, bytecode: bytes) -> bytes:
        source = ctypes.create_string_buffer(bytecode)
        blob = ctypes.c_void_p()
        result = self.disassemble(source, len(bytecode), 0, None, ctypes.byref(blob))
        if result < 0:
            raise RuntimeError(f"D3DDisassemble failed with HRESULT 0x{result & 0xffffffff:08x}")
        try:
            return self._blob_bytes(blob.value)
        finally:
            self._release(blob.value)


def safe_stem(shader: dict[str, Any]) -> str:
    identity = f"{shader['source_name']}-{shader['entry_point']}"
    identity = re.sub(r"[^A-Za-z0-9_.-]+", "_", identity).strip("._")
    return f"{shader['index']:04d}-{shader['stage']}-{identity or 'shader'}"


def make_summary(header: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    shaders = metadata["shaders"]
    return {
        **header,
        "shader_count": metadata["shader_count"],
        "job_count": metadata["job_count"],
        "resource_id_count": metadata["resource_id_count"],
        "d3d_bundle_size": metadata["d3d_bundle_size"],
        "stages": dict(sorted(Counter(item["stage"] for item in shaders).items())),
        "source_names": dict(
            sorted(Counter(item["source_name"] for item in shaders).items())
        ),
        "entry_points": dict(
            sorted(Counter(item["entry_point"] for item in shaders).items())
        ),
        "unique_defines": len({value for item in shaders for value in item["defines"]}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path, help="path to shaders.sbc")
    parser.add_argument("--output", type=Path, help="directory for recovered data")
    parser.add_argument("--extract-dxbc", action="store_true", help="recover individual DXBC blobs")
    parser.add_argument("--disassemble", action="store_true", help="also recover D3D assembly listings")
    args = parser.parse_args()
    if (args.extract_dxbc or args.disassemble) and args.output is None:
        parser.error("--extract-dxbc/--disassemble requires --output")

    header, payload = parse_cache(args.cache)
    metadata, bundle = parse_payload(payload)
    summary = make_summary(header, metadata)

    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        (args.output / "metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        (args.output / "shader-bundle.bscd").write_bytes(bundle)

    if args.extract_dxbc or args.disassemble:
        compiler = D3DCompiler()
        blobs = compiler.extract(bundle, metadata["shader_count"])
        dxbc_dir = args.output / "dxbc"
        dxbc_dir.mkdir(exist_ok=True)
        assembly_dir = args.output / "assembly"
        if args.disassemble:
            assembly_dir.mkdir(exist_ok=True)
        for shader in metadata["shaders"]:
            bytecode = blobs[shader["bundle_index"]]
            stem = safe_stem(shader)
            (dxbc_dir / f"{stem}.dxbc").write_bytes(bytecode)
            shader["dxbc_size"] = len(bytecode)
            shader["dxbc_sha256"] = hashlib.sha256(bytecode).hexdigest()
            if args.disassemble:
                (assembly_dir / f"{stem}.asm").write_bytes(
                    compiler.to_assembly(bytecode)
                )
        (args.output / "metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        summary["total_dxbc_size"] = sum(len(blob) for blob in blobs)
        summary["unique_dxbc_sha256"] = len(
            {hashlib.sha256(blob).digest() for blob in blobs}
        )
        (args.output / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FormatError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
