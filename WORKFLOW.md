
We’re applying a repeatable reverse-engineering and structural-lifting workflow:

0. Find a shader in output\semantic\include\indirect_light that is larger than 5kB. Read the ENTIRE file to understand what it does. This is the shader we will refactor.

1. Identify the permutation policy

Read the selector’s recovered defines to determine which algorithmic features are active, such as:

- Cascade occlusion
- SSAO quality
- Reflection probes
- Probe GI
- SSGI
- SSS layer count
- Perspective versus orthographic projection

2. Compare with already lifted permutations

Separate the shader into:

- Previously recovered phases that can be reused
- New behavior introduced by this permutation
- Output or resource ABI differences

This avoids reverse-engineering the entire shader again.

3. Recover the underlying algorithms

Translate decompiler register operations into named concepts and typed data:

- G-buffer surface reconstruction
- View/world-space transformations
- Depth-aware ray traversal
- Horizon-based AO
- Cluster and bitmask traversal
- Reflection-probe parallax correction
- Probe blending and diffuse GI
- SSS occlusion
- Material-profile postprocessing

Repeated unrolled blocks become parameterized functions or bounded loops.

4. Extract reusable helpers

Shared algorithms go into a semantic helper asset such as:

`indirect_light_probe_cascade.hlsl`

The helper contains meaningful structures and functions, not renamed register-state code. Feature macros prevent unavailable resources or inactive algorithms from being compiled.

5. Replace the permutation with a policy wrapper

The individual selector keeps only:

- ABI includes
- Required resource declarations
- Feature-policy macros
- Its entry-point signature
- A call to the typed implementation
- Output routing

The target is less than 5 KB per selector.

6. Integrate the transformation into the recipe

The Python recipe:

- Recognizes the exact define combination
- Replaces reflected constant buffers with ABI includes
- Selects the appropriate semantic entry point
- Emits the compact independent shader file
- Copies shared helper assets during reconstruction

This makes the lifting reproducible instead of being a one-off output edit.

7. Add focused regression tests

Tests verify:

- Correct permutation recognition
- ABI lifting
- Feature macro selection
- Entry-point and output shape
- Removal of decompiler scaffolding
- Independent per-selector emission

8. Compile only affected selectors

We compile:

- The newly lifted selector
- Existing selectors that include a changed shared helper

Unrelated shaders are not rebuilt.

9. Differentially validate against the original DXBC

The semantic HLSL and original shader are executed with identical inputs. We compare every output component and iterate on any mismatch.

10. Refresh fingerprints and verify the corpus

Only affected semantic fingerprints are updated. Finally, the complete output corpus is checked for include resolution, metadata consistency, ABI compatibility, and stable hashes.