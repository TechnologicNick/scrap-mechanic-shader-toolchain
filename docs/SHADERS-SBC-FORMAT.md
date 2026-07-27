# Scrap Mechanic `shaders.sbc` format and recoverability

This note documents `Cache/Shaders/Release/shaders.sbc` from Scrap Mechanic
1.0.x. The format was recovered from the 1.0.0.867 and 1.0.1.869 executables
with Binary Ninja and validated by extracting the live 1.0.1 cache.

## Loader evidence

The relevant 1.0.0.867 functions are:

- `GenericCache.cpp::sub_140da6b70` at `0x140da6b70`: validates the outer
  header and decompresses its payload with raw LZ4.
- `DX11ShaderCompiler.cpp::sub_140daf0f0` at `0x140daf0f0`: parses the shader
  metadata and calls `D3DDecompressShaders` at `0x140daf649`.
- `ByteStream.h::sub_140dae040` at `0x140dae040`: serializes the same fields
  and calls `D3DCompressShaders` at `0x140dae7be`.

The 1.0.1.869 reader is structurally identical at `0x140daf440`; its
`D3DDecompressShaders` call is at `0x140daf999`. Both builds expect shader-cache
version 1. The Release path string is referenced from `sub_140222580` in both
builds.

## On-disk structure

All integers are little-endian. Sizes and counts are trusted only after bounds
checking by the extractor.

### GenericCache envelope

| Offset | Type | Meaning |
| --- | --- | --- |
| `0x00` | `u32` | GenericCache version; currently `1` |
| `0x04` | `u32` | custom-data size; currently `4` |
| `0x08` | `u32` | LZ4-compressed payload size |
| `0x0c` | `u32` | uncompressed payload size |
| `0x10` | `u32` | shader-cache version; currently `1` |
| `0x14` | bytes | raw LZ4 block (not an LZ4 frame) |

### Uncompressed shader payload

| Order | Type | Meaning |
| --- | --- | --- |
| 1 | `u16` | number of unique compiled shaders, `N` |
| 2 | `u64[N]` | shader identity/hash keys |
| 3 | `u32` | number of compile jobs, `J` |
| 4 | `J * {u64, u16}` | job hash and shader index |
| 5 | `u16` | number of opaque 128-bit resource IDs, `R` |
| 6 | `byte[R][16]` | resource IDs |
| 7 | `u64` | size of the following Microsoft bundle |
| 8 | bytes | `BSCD` bundle produced by `D3DCompressShaders` |
| 9 | `u16[N]` | each shader's index in the Microsoft bundle |
| 10 | `u8[N]` | stage: `1` vertex, `2` pixel, `4` compute |
| 11 | `u16[N]` | count of resource-ID references per shader |
| 12 | `u16[N]` | byte length of each compilation descriptor |
| 13 | repeated `N` times | `u16` resource-ID indices, then UTF-8 descriptor bytes |

A descriptor preserves the source stem, entry point, and active preprocessor
defines. For example:

```text
main_character:commonPS  PIXEL_SHADER PS_ASG_TEX PS_NOR_TEX
PS_PERM_CHARACTER_ICON TRANSFER_NORMAL TRANSFER_TANGENTS TRANSFER_UV0
TRANSFER_VIEW_POSITION
```

The job table is larger than the shader table because multiple compile jobs can
deduplicate to the same bytecode entry.

## Validated cache contents

The analyzed cache has SHA-256
`d29a016093ec82099f34ebbff852d102d737c8efc0e28eec08bdfea1e205651f`.

| Item | Recovered value |
| --- | ---: |
| File size | 2,106,634 bytes |
| Uncompressed inner payload | 3,282,586 bytes |
| Unique DXBC shaders | 4,141 |
| Compile-job mappings | 6,862 |
| Vertex / pixel / compute shaders | 1,360 / 2,646 / 135 |
| Source module stems | 80 |
| Entry-point names | 14 |
| Unique define tokens | 363 |
| Opaque 128-bit resource IDs | 143 |
| Total decompressed DXBC size | 98,794,432 bytes |

Every one of the 4,141 DXBC blobs has a distinct SHA-256 digest. They use shader
model 5.0 (`vs_5_0`, `ps_5_0`, or `cs_5_0`). Across the Microsoft assembly
listings, reflection data exposes at least 63 constant-buffer names, 521
constant-buffer field names, 215 bound resource names, and 73 signature
semantics.

## What is and is not recoverable

Fully recoverable:

- the exact executable DXBC for every cached permutation;
- Microsoft shader assembly and instruction-level control flow;
- source module stems, entry points, active define sets, and permutation hashes;
- input/output signatures and semantic names;
- reflected constant-buffer layouts, field names/types/offsets, textures,
  samplers, UAVs, resource dimensions, and register bindings;
- shader-stage tags, job-to-shader mappings, and per-shader opaque resource IDs.

Not present in this cache:

- original HLSL text, comments, whitespace, include contents, or macro bodies;
- high-level expressions and control structures in their original form;
- identifiers removed by optimization and any unused source code.

The DXBC containers contain only `RDEF`, `ISGN`/`ISG1`, `OSGN`/`OSG1`, `SHEX`,
`STAT`, and (for two shaders) `SFI0` chunks. No `SDBG`, `SPDB`, `ILDB`, or other
debug/source chunk is present. HLSL-like pseudocode can therefore be generated
by a decompiler, but it cannot be the exact original source.

## Extractor

Run the checked-in extractor on Windows with uv:

```powershell
uv run python -m shader_toolchain.sbc `
  "C:\Program Files (x86)\Steam\steamapps\common\Scrap Mechanic\Cache\Shaders\Release\shaders.sbc" `
  --output .data/shaders-recovered `
  --extract-dxbc --disassemble
```

It uses a built-in raw-LZ4 decoder and the system `d3dcompiler_47.dll`. The
output contains `summary.json`, complete `metadata.json`, the `BSCD` bundle,
4,141 `.dxbc` files, and 4,141 `.asm` files. `.data` is ignored by Git.

## Deterministic HLSL reconstruction

The higher-level command decompresses the same DXBC programs, disassembles them,
lifts them with the pinned decompiler submodules, and groups each permutation
under its recovered source stem:

```powershell
uv run sm-shaders reconstruct path\to\shaders.sbc output
uv run sm-shaders verify output
```

The validated cache becomes exactly 80 `.hlsl` modules. A generated
`SM_SHADER_<key>` preprocessor selector identifies each of the 4,141 variants;
the manifest preserves the complete mapping back to cache metadata and exact
DXBC hashes. Normalization removes decompiler timestamps and repairs mechanical
compute-signature defects using the authoritative DXBC thread-group declaration,
making repeated runs byte-for-byte reproducible.

## Cache serialization

The reverse path uses the retained manifest as the authoritative table layout.
It compiles every selector branch with Microsoft's `D3DCompile`, supplies the
stage-appropriate Shader Model 5 profile, and orders the resulting bytecode by
the original shader index. `D3DCompressShaders` creates a new BSCD bundle.

The serializer retains all original shader and job keys, job mappings, resource
IDs, stages, resource references, and descriptors. It replaces the BSCD bundle
and its one-to-one indices, then emits a GenericCache version-1 header and a
deterministic valid raw-LZ4 block. The current encoder uses one literal sequence:
this is larger than fully compressed LZ4 but simple and deterministic.

Before the temporary output is renamed, the tool parses it again and uses
`D3DDecompressShaders` to recover all 4,141 bytecode programs:

```powershell
uv run sm-shaders build --jobs 32 output rebuilt-shaders.sbc
```

Because optimized DXBC cannot always be expressed as recompilable HLSL by the
available decompilers, reconstruction also retains each exact DXBC blob. Normal
build mode uses it only when `D3DCompile` rejects that branch; `--strict`
disables this behavior. This hybrid is necessary for a complete cache until the
remaining lift defects are repaired.
