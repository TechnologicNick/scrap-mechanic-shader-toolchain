# FXAA GPU differential validation

The semantic `post_fxaa` pixel shader is tested against its exact recovered
DXBC by rendering both programs with identical D3D11 state and resources. This
is empirical behavioral evidence in addition to the reflection-based ABI gate.

## Pipeline held constant

Both runs use:

- selector `SM_SHADER_5098D83798AA5E07` as the pixel baseline;
- exact vertex selector `SM_SHADER_AD271D5DDB1D1DF2`;
- the same full-screen triangle and viewport;
- `R32G32B32A32_FLOAT` input and output textures;
- a linear min/mag/mip sampler with clamp addressing at `s6`;
- the input SRV at `t0`;
- recovered `CB_PROJECTION` at `b5`;
- `cb_vContainerPixelSize = 1 / dimensions`;
- `cb_vRenderScale = (1, 1)`; and
- `cb_vUvLimit` at the final texel center.

The native runner reads both render targets back and compares every component.
NaNs compare equal to NaNs; current generators otherwise use finite values.
Zero absolute and relative tolerance requires identical IEEE-754 bits.

## Validated campaign

On 2026-07-27, the following candidate pair was tested:

```text
baseline DXBC SHA-256:
19c8a94a72233d1b9ec0350f4fd8203503cc1b69b94ede725448e1e446d9766c

semantic DXBC SHA-256:
0cfa59c0673019bc99c19280de260893e1078bb766aa93c1715b6ade40f6e169
```

Hardware adapter: NVIDIA GeForce RTX 5090, D3D feature level 11_1.

| Size | Cases | Seed | Components | Result |
| ---: | ---: | ---: | ---: | :--- |
| 64×64 | 256 | `0x534D465841413031` | 4,194,304 | bit-exact |
| 31×17 | 128 | `0x1` | 269,824 | bit-exact |
| 127×71 | 128 | `0xDEADBEEF` | 4,616,704 | bit-exact |

The hardware total is 512 generated images and 9,080,832 exactly equal output
components. A separate Microsoft WARP run tested 64 cases at 64×64, adding
1,048,576 bit-exact component comparisons.

The primary campaign can be repeated with:

```powershell
uv run sm-shaders gpu-fuzz .data\semantic-final `
  --cases 256 --width 64 --height 64 `
  --seed 0x534D465841413031 --absolute-tolerance 0 `
  --relative-tolerance 0 --report .data\fxaa-hardware-report.json
```

## Mutation control

To establish that the harness can detect a plausible semantic transcription
error, `FXAA_SPAN_MAX` was temporarily changed from `8.0` to `7.0`. The run
failed on case 5, the checkerboard pattern:

```text
differing pixels:      124
differing components:  372
maximum absolute error: 0.166015625
```

The mutation was reverted after the test.

## What this establishes

These results show identical pixels for the tested state, patterns, randomized
inputs, dimensions, device driver, and WARP implementation. Combined with the
ABI check and the direct instruction-to-expression audit, this is strong
evidence that the semantic FXAA lift preserves the recovered shader's behavior.

It is not a formal proof over all possible inputs or D3D11 implementations. The
current harness is specialized for the `post_fxaa` vertex/pixel pipeline, does
not generate NaN or infinity inputs, does not vary sampler state or render
scale, and has so far run on one hardware vendor plus WARP. Those are explicit
future coverage dimensions rather than properties implied by this campaign.
