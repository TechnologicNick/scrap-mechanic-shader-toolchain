# Semantic shader coverage

The recovered Scrap Mechanic cache contains 4,141 shader variants grouped into
80 source modules. Every variant has a readable semantic HLSL representation,
an independently fingerprinted source branch, and a reflected runtime ABI that
matches its exact recovered DXBC.

## Validation layers

1. Each semantic branch compiles with its recovered entry point and Shader
   Model 5 stage profile.
2. Reflection checks stage signatures, constant buffers, resources, dimensions,
   bind points, bind counts, return types, and structured-buffer layout.
3. Every pixel or compute permutation is run against the exact recovered DXBC
   on D3D11. Most family campaigns use 256 deterministic cases per permutation;
   the largest indirect-light campaign gives every permutation a deterministic
   base case and distributes deeper 16-256-case ranges across the family.
   Vertex permutations are compile- and reflection-checked; pixel harnesses
   supply their recovered semantics directly.
4. A forced semantic build compiles all 4,141 branches with no retained-DXBC
   fallback and no interface-change override.
5. Two independent 32-worker builds produce byte-identical `shaders.sbc` files.

The completed reference audit produced:

- corpus digest: `5a64188606275ca7d81827b1b98aa8c04bb0faec52a2fac5a2cef1fb398d8faf`;
- semantic cache size: `3,362,715` bytes;
- semantic cache SHA-256:
  `eba6bee8ff40183cf80c705a46230f404085c37b42447d1050d8b2cef52858af`;
- compiled variants: 4,141;
- DXBC fallbacks: 0.

A clean integration reconstruction on 2026-07-27, after the structural naming
pass, independently verified 80 modules and 4,141 variants with corpus digest
`7ee6bd5ded8f3615f0cdf19bf70f8098769f93bd8be1138624488e361919a473`.
An audit of its 80 generated module files plus the shared include found no
anonymous DXBC temporary identifier (`rN`) in `semantic/`.

## Readability levels

The semantic corpus has two deliberate readability levels:

- Fully structural implementations express algorithms with ordinary HLSL
  values, helpers, and control flow. This includes FXAA, godrays, volumetric
  clouds, deferred composition, and the smaller post-processing, copy, GUI,
  terrain, water, probe, and compute recipes.
- Instruction-ordered semantic implementations preserve the recovered
  arithmetic sequence but replace anonymous register state with stable domain
  names and document the algorithm phases. This applies to the largest or most
  numerically sensitive families: volumetrics, SSGI cascade filtering, main
  clutter/block/slant/voxel, character/asset/part materials, particles,
  deferred lighting, indirect cascade upscale, and indirect lighting.

Both levels receive the same compile, reflection, and GPU comparison gates.
The second level is not presented as recovered author source; it is a named,
traceable intermediate representation designed for safe incremental lifting.

Shared modules keep permutation metadata in
`metadata/semantic-variants/<module>.json`, not in the readable HLSL. For an
instruction-ordered module, `sm-shaders materialize` expands one selected
permutation into standalone HLSL and removes the generated decision tree. This
is the preferred inspection format for `main_part`, `main_asset`,
`main_character`, particles, deferred/indirect lighting, voxel materials, and
the other large families that have not yet converged to one shared source.

## Reproduce the audit

Use `uv` for every Python entry point:

```powershell
uv run sm-shaders verify .data\corpus
uv run python scripts\fuzz-module-batch.py .data\corpus <module> `
  --start 0 --count <pixel-or-compute-count> --cases 256
uv run sm-shaders build .data\corpus .data\semantic-a.sbc --recompile-all
uv run sm-shaders build .data\corpus .data\semantic-b.sbc --recompile-all
Get-FileHash -Algorithm SHA256 .data\semantic-a.sbc, .data\semantic-b.sbc
```

`scripts/apply-semantic-module.py` reapplies one recipe to an existing corpus,
refreshing its semantic module, ABI checks, execution descriptors, fingerprints,
and manifest summary without reconstructing unrelated shaders.

## Scope of the semantic proof

The harness checks behavior over deterministic synthetic resources and constant
buffers; it is not a proof over every possible IEEE-754 input or complete game
frame. Several legacy sample/gather/derivative-heavy families use a 1x1 packed
domain because independently compiled DXBC can differ in quad-lane and triangle
edge ordering on larger synthetic targets. That domain still varies textures,
constant buffers, samplers, structured inputs, branches, and arithmetic while
removing undefined spatial ordering from the comparison.

Advisory `D3D_SHADER_INPUT_BIND_DESC.Flags` are excluded from ABI equality
because they describe compiler-observed component use, not runtime binding.
Every field that affects a D3D11 binding remains strict.
