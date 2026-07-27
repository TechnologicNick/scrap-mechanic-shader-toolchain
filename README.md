# Scrap Mechanic Shader Toolchain

This Windows tool reconstructs a Scrap Mechanic 1.0.x `shaders.sbc` cache as a
deterministic corpus of exactly 80 HLSL module files. The validated cache
contains 4,141 unique Shader Model 5 programs. Variants are merged into the
module named by their recovered source stem, with common HLSL emitted once.

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

Each module is a nested preprocessor decision tree. Shared prefixes and suffixes
are emitted once, and divergences use recovered permutation definitions such as
`VS_FULL_TRANSFORM` or `TRANSFER_NORMAL` when they describe the split. Opaque
`SM_SHADER_<16-hex-digit-key>` conditions are used only when the original
definitions cannot distinguish a group.

Define one `SM_SHADER_<key>` symbol when compiling a module. Its generated
selector bridge defines the exact original flags, including valued definitions
such as `GROUP_SIZE_X=8`, and selects the appropriate shared-code path.
`manifest.json` records every cache job, shader key, original descriptor and
define set, stage, entry point, resource-ID association, DXBC hash, lift backend,
and lift status. It also records a comment/whitespace-insensitive token
fingerprint for each branch. The `dxbc/` directory retains the exact executable
programs as the lossless baseline.

3DMigoto lifts 4,131 programs in the validated cache. Its decompiler rejects ten
unusual compute programs; these are retained using DXDecompiler and explicitly
marked `fallback-incomplete`. Consumers should treat all generated source as
reverse-engineering material and the fallback branches as especially likely to
need manual repair. The exact executable DXBC remains recoverable without this
loss.

The validated corpus shrinks from 102,490,876 bytes of flat duplicated HLSL to
51,197,843 bytes in 80 factored modules, a reduction of approximately 50%.
Generated `SM_DEFINE` and `SM_SELECT` blocks are structural metadata; edit the
HLSL around them rather than those blocks. Verification checks that their actual
preprocessor behavior still agrees with the manifest.

## Verify an output

```powershell
uv run sm-shaders verify output
```

Verification checks that there are exactly 80 HLSL files, that manifest counts
agree, and that every one of the 4,141 shader selector branches is present. It
also prints a SHA-256 digest over every relative path and byte in the corpus.

For the cache with SHA-256
`d29a016093ec82099f34ebbff852d102d737c8efc0e28eec08bdfea1e205651f`, two
the current v2 corpus has this output digest:

```text
77aa3c70f9fd46d3ceeb9d33825a45bbc6ffb16464244d813081327b82644445
```

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

The default build expands every selector through the decision tree before
fingerprinting it. Comments and formatting do not count as an edit. Changing a
shared block recompiles every affected selector; unaffected variants remain
lossless. An edited selector is compiled with its recovered entry point and
Shader Model 5 profile. Edited shaders must preserve their reflected runtime ABI:
signatures, resource bindings, constant-buffer layouts, and compute thread-group
dimensions. Compilation errors and ABI changes are fatal and never silently
fall back to the old shader.

The adjacent `rebuilt-shaders.sbc.build.json` classifies every selector. Edited
branches also receive deterministic Microsoft assembly diffs under
`rebuilt-shaders.sbc.diffs/`. An explicitly coordinated engine-side ABI change
can be allowed with:

```powershell
uv run sm-shaders build --allow-interface-changes .\output .\rebuilt-shaders.sbc
```

For decompiler research, force every branch through the compiler with
`--recompile-all`. Add `--allow-dxbc-fallback` to retain exact originals for
decompiler output that does not compile. The deprecated `--strict` flag is an
alias for `--recompile-all`.

For the untouched validated corpus, the lossless build performs zero HLSL
compilations and classifies all 4,141 branches as `unchanged-exact`. Its cache
SHA-256 is:

```text
9d7c6d7a753def3b5435faa2375706c9476dbf4d2ac01e40b75fb564e90bf54f
```

## Compare caches

Compare Microsoft disassembly and normalized runtime ABI independently:

```powershell
uv run sm-shaders compare original-shaders.sbc rebuilt-shaders.sbc `
  --report comparison.json --diff-dir assembly-diffs
```

The untouched acceptance build matches all 4,141 original disassemblies,
executable streams, opcode sequences, ABIs, and metadata tables. It has not been
automatically installed into or runtime-tested by the game; keep the
Steam-generated cache available when testing it.

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
