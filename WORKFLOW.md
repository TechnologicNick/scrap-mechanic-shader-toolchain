We’re applying a conservative, validation-driven shader decompilation workflow:

0. Find a shader in output\semantic\include\main_part that is larger than 5kB. Read the ENTIRE file to understand what it does. This is the shader we will refactor.

1. Identify the exact permutation

We read the shader’s feature defines, stage, entry point, resources, constant buffers, inputs, and outputs. This prevents accidentally grouping superficially similar shaders with different behavior.

2. Recover semantic phases

We translate anonymous register-state operations into recognizable stages, such as:

- G-buffer or vertex decoding
- Depth and position reconstruction
- Material sampling
- Flow animation
- Lighting and reflections
- Output encoding

3. Extract reusable helpers

Stable operations become typed functions and structs in shared `.hlsl` assets. For this shader, those were thickness reconstruction, flow blending, reflection lookup, preview lighting, and final composition.

4. Replace the register program with a thin wrapper

The per-shader file retains its exact entry-point signature and resource declarations, but delegates the implementation to the shared semantic helper.

5. Compose recovered feature policies

The recipe consumes independently recovered feature contracts instead of
listing selectors or whole permutations. For example, the opaque G-buffer
family composes diffuse, ASG, normal-map, AO, alpha-cutoff, and backface-normal
policies. Each policy owns its required define(s), transferred semantics, and
typed helper call.

A shader is accepted only when every define is consumed and every required
semantic is present. Unknown or incomplete policy sets remain mechanical. This
lets one recovered policy immediately apply to compatible combinations without
creating one helper or recipe branch per permutation.

6. Preserve the runtime ABI

We compile the lifted shader and compare:

- Input and output semantics
- Constant-buffer bindings and layouts
- Texture and sampler slots
- Shader stage and entry point

Any ABI change rejects the lift.

7. Differentially validate behavior

For pixel shaders, we execute the original DXBC and lifted shader with identical randomized inputs, textures, samplers, and constant buffers. We require bit-exact results where practical.

If validation fails, the captured case is used to locate the incorrectly interpreted phase.

8. Verify the whole corpus

Finally, we run the complete test suite and verify all generated shader modules and manifest hashes.

So the progression is:

```text
Mechanical decompile
    → exact feature-policy classification
    → semantic phase recovery
    → reusable helper extraction
    → thin shader wrapper
    → ABI comparison
    → GPU differential testing
    → corpus verification
```

The important principle is that readability is introduced incrementally, with the original DXBC acting as the behavioral specification.
