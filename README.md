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

Semantic compilation and reflection use all logical CPUs by default and show a
per-module `tqdm` progress bar. To cap CPU and memory use, set
`SM_SHADERS_JOBS` before reconstruction, for example:

```powershell
$env:SM_SHADERS_JOBS = 16
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
|-- semantic/
|   |-- include/
|   |   `-- post_fxaa_abi.hlsl
|   `-- post_fxaa.hlsl
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

### Readable semantic lifts

All 80 recovered modules (4,141 shader variants) now have semantic HLSL with
reflection-compatible runtime interfaces and differential GPU coverage. See
[the semantic coverage audit](docs/SEMANTIC-COVERAGE.md) for the validation
layers, reproducible commands, reference hashes, and fuzz-domain limitations.

The `hlsl/` modules remain the mechanical, lossless reverse-engineering layer.
Recognized shaders additionally receive a hand-readable implementation under
`semantic/`. This separates proven cache recovery from higher-level inference:
the raw lift remains available for instruction-level investigation, while the
semantic version uses meaningful types, variable names, constants, and control
flow.

Semantic coverage and structural readability are tracked separately. Some
large modules still retain instruction-ordered decompiler blocks inside a
documented semantic recipe; those blocks compile, reflect, and fuzz correctly,
but remain candidates for deeper lifting. A fully structural lift removes the
anonymous register program, factors shared ABI declarations into includes, and
expresses the recovered algorithm as named data and helpers.

The first recipe recognizes both stages of `post_fxaa`. Its pixel shader is
expressed as the compact FXAA algorithm: a five-sample luminance neighborhood,
edge direction and span reduction, inner/outer filtering, and a luminance-range
choice. Its vertex shader names the full-screen triangle and the center and
north-west sample coordinates. The recovered `CB_PROJECTION` layout is kept in
a shared include.

`post_godrays` is another fully structural lift. Its two pixel variants share
view-ray reconstruction, cascade transformation and comparison filtering,
temporal reprojection, and HDR encoding. `PS_UNDER_WATER` adds the recovered
water-plane and caustic integration without duplicating the shader. Its large
projection, per-frame, and HDR buffers are retained exactly in generated ABI
includes. The GPU harness uses a dedicated `godrays` constant profile to drive
inside/outside cascade samples, water intersections and rejections, shadow
filtering, and temporal history.

`post_clouds` and all 24 `post_composition` permutations are fully structural
lifts as well. Clouds expose named ray construction, shell intersection,
weather sampling, density integration, lighting, and temporal-noise phases.
Composition shares one implementation for its dry and underwater feature
combinations, with named HDR decode/encode, fog, bloom, refraction, caustics,
color grading, and final output stages.

The remaining large permutation families no longer expose anonymous `rN`
temporaries. Volumetrics, SSGI cascade filtering, clutter, block/slant/voxel
materials, character/asset/part materials, particles, deferred lighting, and
indirect-light reconstruction use stable domain-specific state names and a
documented phase map. Their arithmetic stays in recovered instruction order
where packed masks, floating-point reassociation, derivatives, or hundreds of
feature combinations make further restructuring especially sensitive. This is
an intermediate semantic form: much easier to trace, while still clearly
marked as a candidate for future helper-level lifting.

Shared semantic modules do not contain selector hashes or generated
`SM_SELECT` blocks. Reconstruction stores the selector, stage, entry point, and
recovered definitions separately under `metadata/semantic-variants/`; builds
prepend those definitions to the shared source in memory.

Large instruction-ordered families still need variant-specific arithmetic. Do
not read their aggregate decision tree directly. Materialize the permutation
you want to investigate as standalone HLSL instead:

```powershell
# Inspect selectors and their recovered definitions.
uv run sm-shaders materialize output main_part --list

# Produce one normal HLSL file with all SM_SELECT dispatch removed.
uv run sm-shaders materialize output main_part readable\main_part.hlsl `
  --selector SM_SHADER_FFD8D5BCBA95D168
```

`--define NAME` can be repeated instead of `--selector` when the requested
definition combination identifies exactly one permutation. The materialized
file includes the recovered compile definitions, resolved local includes,
stage, and entry point, so it can be read and compiled without the aggregate
module around it.

Semantic recipes are not accepted merely because they compile. Reconstruction
compiles each generated implementation and reflects it against the recovered
DXBC. Signatures, texture and sampler slots, constant-buffer layout, and shader
stage must remain compatible. The manifest records its source path, token
fingerprint, recipe name, ABI result, and whether its assembly happens to be
exact.

### GPU differential fuzzing

Build the native D3D11 runner together with the decompiler dependencies, or by
itself:

```powershell
.\scripts\build-third-party.ps1
# or
.\scripts\build-gpu-harness.ps1
```

Then compare the exact recovered DXBC with the current semantic FXAA shader:

```powershell
uv run sm-shaders gpu-fuzz .\output `
  --shader post_fxaa --cases 256 --seed 0x534D465841413031 `
  --width 64 --height 64 --report fxaa-fuzz.json
```

The runner compiles the semantic pixel shader, uses the exact recovered vertex
shader, and renders both pixel shaders through the same D3D11 pipeline. It uses
an `R32G32B32A32_FLOAT` source and target, linear-clamp sampling, and the
recovered `b5`, `t0`, and `s6` bindings. Cases include flat colors, horizontal,
vertical and diagonal edges, a checkerboard, a single-pixel impulse, gradients,
uniform random colors, HDR values, and noisy gradients.

Comparison is bit-exact by default. Explicit absolute and relative tolerances
are available for shaders where equivalent compiler transformations introduce
rounding differences. Every run first compares the baseline shader against
itself at zero tolerance. On failure, `gpu-fuzz-failure/` receives the input,
both outputs, all three DXBC programs, expanded candidate HLSL, and JSON needed
to reproduce and inspect the case. `--warp` selects Microsoft's software D3D11
rasterizer for a driver-independent secondary run.

The validated FXAA campaigns and their limitations are recorded in
[`docs/FXAA-GPU-FUZZING.md`](docs/FXAA-GPU-FUZZING.md).

## Verify an output

```powershell
uv run sm-shaders verify output
```

Verification checks that there are exactly 80 HLSL files, that manifest counts
agree, and that every one of the 4,141 shader selector branches is present. It
also prints a SHA-256 digest over every relative path and byte in the corpus.

For the cache with SHA-256
`d29a016093ec82099f34ebbff852d102d737c8efc0e28eec08bdfea1e205651f`,
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

For shaders with a semantic recipe, edit the file under `semantic/` to work at
the readable level. An unchanged semantic file still uses the exact retained
DXBC; it is not recompiled just because a readable version exists. A semantic
edit compiles only affected selectors and receives the same ABI and assembly
diff checks as a raw edit. If both the raw and semantic representations of one
selector are changed, the build stops and asks you to keep one representation
authoritative. `--recompile-all` prefers semantic HLSL where it is available.

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
