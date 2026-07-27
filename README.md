# Scrap Mechanic Shader Toolchain

This Windows tool reconstructs a Scrap Mechanic 1.0.x `shaders.sbc` cache as a
deterministic corpus of exactly 80 HLSL module files. The validated cache
contains 4,141 unique Shader Model 5 programs. Every program is retained as a
selector-controlled branch in the module named by its recovered source stem.

The original source code is not stored in the cache. The generated files are
HLSL lifts of optimized DXBC bytecode, not the original comments, includes,
macros, names, or source-level control flow. See
[`docs/SHADERS-SBC-FORMAT.md`](docs/SHADERS-SBC-FORMAT.md) for the binary format
and the precise recoverability boundary.

## Prerequisites

- Windows 10 or 11;
- Git;
- [uv](https://docs.astral.sh/uv/);
- Visual Studio 2022 with the Desktop development with C++ workload;
- the .NET SDK (Visual Studio normally installs a compatible SDK).

`d3dcompiler_47.dll`, included with Windows, supplies Microsoft's compile,
disassemble, and BSCD compression/decompression functions.

## Set up

Clone with the pinned decompiler submodules and build them:

```powershell
git clone --recurse-submodules <repository-url>
Set-Location scrap-mechanic-shader-toolchain
uv sync
.\scripts\build-third-party.ps1
```

For an existing clone, initialize dependencies with:

```powershell
git submodule update --init --recursive
```

The repository pins 3DMigoto 1.4.9 and DXDecompiler by Git commit. Generated
build products are ignored.

## Reconstruct a cache

```powershell
uv run sm-shaders reconstruct `
  "C:\Program Files (x86)\Steam\steamapps\common\Scrap Mechanic\Cache\Shaders\Release\shaders.sbc" `
  output
```

The output path must not already exist. This prevents an old or partial corpus
from being mistaken for the result of the current input. A successful run
creates:

```text
output/
|-- dxbc/
|   `-- ... exact fallback bytecode by shader key ...
|-- hlsl/
|   |-- bloom_downres.hlsl
|   |-- ... exactly 80 module files ...
|   `-- upres_clouds.hlsl
`-- manifest.json
```

Each module contains one `#if`/`#elif` branch per cached permutation. Define the
branch's `SM_SHADER_<16-hex-digit-key>` symbol and use the entry point shown in
its adjacent comment or manifest record when compiling a particular lift.
`manifest.json` records every cache job, shader key, original descriptor and
define set, stage, entry point, resource-ID association, DXBC hash, lift backend,
and lift status. The `dxbc/` directory retains the exact executable programs as
a safety net for branches that a decompiler cannot express as compilable HLSL.

3DMigoto lifts 4,131 programs in the validated cache. Its decompiler rejects ten
unusual compute programs; these are retained using DXDecompiler and explicitly
marked `fallback-incomplete`. Consumers should treat all generated source as
reverse-engineering material and the fallback branches as especially likely to
need manual repair. The exact executable DXBC remains recoverable without this
loss.

## Verify an output

```powershell
uv run sm-shaders verify output
```

Verification checks that there are exactly 80 HLSL files, that manifest counts
agree, and that every one of the 4,141 shader selector branches is present. It
also prints a SHA-256 digest over every relative path and byte in the corpus.

For the cache with SHA-256
`d29a016093ec82099f34ebbff852d102d737c8efc0e28eec08bdfea1e205651f`, two
independent clean runs produced this output digest:

```text
df45cede1806eb7da3da2f56ecd38832d0cd3f4ea4427b5b3b972e51222569ea
```

Corpora produced by the current version also include exact DXBC sidecars, so
their complete digest differs from this earlier HLSL-and-manifest-only result.

## Compile HLSL back to `shaders.sbc`

```powershell
uv run sm-shaders build .\output .\rebuilt-shaders.sbc
```

Every shader permutation is independent. Builds use all logical CPUs by default
and preserve manifest order when collecting results, so parallel scheduling does
not affect the output. Override the worker count when desired:

```powershell
uv run sm-shaders build --jobs 8 .\output .\rebuilt-shaders.sbc
```

The build splits the 80 modules into selector branches, compiles each branch
with its recovered entry point and Shader Model 5 profile, packages the results
with `D3DCompressShaders`, recreates every metadata table, and writes a valid
GenericCache raw-LZ4 envelope. It then reopens the result and decompresses all
4,141 shaders before publishing the output.

When decompiler-generated HLSL does not compile, normal mode uses that branch's
exact recovered DXBC. The adjacent `rebuilt-shaders.sbc.build.json` report lists
every fallback and its stable compiler diagnostic. Use strict mode to reject
all fallbacks:

```powershell
uv run sm-shaders build --strict .\output .\rebuilt-shaders.sbc
```

Strict mode is useful while repairing individual lifts. The unmodified recovered
corpus is not strict-clean: 2,649 branches compile and 1,492 use exact-DXBC
fallback. A modified branch that compiles is always placed in the new cache; a
modified branch with a compiler error falls back unless strict mode is selected.

For the validated corpus, two independent 32-worker builds produced the same
3,357,810-byte cache with SHA-256:

```text
4a5d867150786c302be46a5aca67f0a56e4f5efef81ba7b053666be9a7ef294d
```

The rebuilt cache has been validated structurally and through a complete BSCD
decompression pass. It has not been automatically installed into or runtime-
tested by the game; keep the Steam-generated cache available when testing it.

## Extract lower-level artifacts

The cache parser can separately emit metadata, the inner BSCD bundle, exact
DXBC programs, and Microsoft assembly:

```powershell
uv run python -m shader_toolchain.sbc `
  path\to\shaders.sbc `
  --output .data\extracted `
  --extract-dxbc --disassemble
```

## Test

```powershell
uv run pytest
```
