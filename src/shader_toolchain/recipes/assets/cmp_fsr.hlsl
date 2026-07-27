#if defined(EASU)
#include "include/post_fxaa_abi.hlsl"
#endif

cbuffer cb : register(b0)
{
    uint4 Const0 : packoffset(c0);
    uint4 Const1 : packoffset(c1);
    uint4 Const2 : packoffset(c2);
    uint4 Const3 : packoffset(c3);
};

#define A_GPU 1
#define A_HLSL 1
#if defined(HALF)
#define A_HALF 1
#endif
#include "include/ffx_a.h"

SamplerState LinearClamp : register(s6);
#if defined(HALF)
Texture2D<AH4> inputTexture : register(t0);
#else
Texture2D<float4> inputTexture : register(t0);
#endif
RWTexture2D<float4> outputTexture : register(u0);

#if defined(EASU)
#if defined(HALF)
#define FSR_EASU_H 1
AH4 FsrEasuRH(AF2 p) { return inputTexture.GatherRed(LinearClamp, min(cb_vUvLimit, p)); }
AH4 FsrEasuGH(AF2 p) { return inputTexture.GatherGreen(LinearClamp, min(cb_vUvLimit, p)); }
AH4 FsrEasuBH(AF2 p) { return inputTexture.GatherBlue(LinearClamp, min(cb_vUvLimit, p)); }
#else
#define FSR_EASU_F 1
AF4 FsrEasuRF(AF2 p) { return inputTexture.GatherRed(LinearClamp, min(cb_vUvLimit, p)); }
AF4 FsrEasuGF(AF2 p) { return inputTexture.GatherGreen(LinearClamp, min(cb_vUvLimit, p)); }
AF4 FsrEasuBF(AF2 p) { return inputTexture.GatherBlue(LinearClamp, min(cb_vUvLimit, p)); }
#endif
#else
#if defined(HALF)
#define FSR_RCAS_H 1
AH4 FsrRcasLoadH(ASW2 p) { return inputTexture.Load(ASW3(p, 0)); }
void FsrRcasInputH(inout AH1 r, inout AH1 g, inout AH1 b) {}
#else
#define FSR_RCAS_F 1
AF4 FsrRcasLoadF(ASU2 p) { return inputTexture.Load(int3(p, 0)); }
void FsrRcasInputF(inout AF1 r, inout AF1 g, inout AF1 b) {}
#endif
#endif

#include "include/ffx_fsr1.h"

void FilterPixel(uint2 pixel)
{
#if defined(EASU)
#if defined(HALF)
    AH3 color;
    FsrEasuH(color, pixel, Const0, Const1, Const2, Const3);
#else
    AF3 color;
    FsrEasuF(color, pixel, Const0, Const1, Const2, Const3);
#endif
#else
#if defined(HALF)
    AH3 color;
    FsrRcasH(color.r, color.g, color.b, pixel, Const0);
#else
    AF3 color;
    FsrRcasF(color.r, color.g, color.b, pixel, Const0);
#endif
#endif
    outputTexture[pixel] = float4(color, 1.0);
}

[numthreads(64, 1, 1)]
void mainCS(uint3 groupId : SV_GroupID, uint3 groupThreadId : SV_GroupThreadID)
{
    uint2 pixel = ARmp8x8(groupThreadId.x) + (groupId.xy << 4u);
    FilterPixel(pixel);
    pixel.x += 8u;
    FilterPixel(pixel);
    pixel.y += 8u;
    FilterPixel(pixel);
    pixel.x -= 8u;
    FilterPixel(pixel);
}
