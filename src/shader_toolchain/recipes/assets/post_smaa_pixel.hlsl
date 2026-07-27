cbuffer cb : register(b0)
{
    float4 SMAA_RT_METRICS : packoffset(c0);
    float4 cb_vSubsampleIndices : packoffset(c1);
}

SamplerState PointClampClamp_s : register(s1);
SamplerState LinearClampClamp_s : register(s6);

#define SMAA_CUSTOM_SL 1
#define SMAA_INCLUDE_VS 0
#define SMAA_INCLUDE_PS 1
#define SMAA_PREDICATION 1
#define SMAA_PREDICATION_THRESHOLD 0.001
#define SMAATexture2D(tex) Texture2D<float4> tex
#define SMAATexturePass2D(tex) tex
#define SMAASampleLevelZero(tex, coord) tex.SampleLevel(LinearClampClamp_s, coord, 0.0)
#define SMAASampleLevelZeroPoint(tex, coord) tex.SampleLevel(PointClampClamp_s, coord, 0.0)
#define SMAASampleLevelZeroOffset(tex, coord, offset) tex.SampleLevel(LinearClampClamp_s, coord, 0.0, offset)
#define SMAASample(tex, coord) tex.Sample(LinearClampClamp_s, coord)
#define SMAASamplePoint(tex, coord) tex.Sample(PointClampClamp_s, coord)
#define SMAASampleOffset(tex, coord, offset) tex.Sample(LinearClampClamp_s, coord, offset)
#define SMAAGather(tex, coord) tex.Gather(LinearClampClamp_s, coord, 0)
#define SMAA_FLATTEN [flatten]
#define SMAA_BRANCH [branch]
#include "include/SMAA.hlsl"

#if defined(EDGE_DETECTION)
Texture2D<float4> tColor : register(t0);
Texture2D<float4> tHzb : register(t1);

float2 mainPS(
    float4 position : SV_Position0,
    float2 uv : UV0,
    float4 offset0 : OFFSETS0,
    float4 offset1 : OFFSETS1,
    float4 offset2 : OFFSETS2) : SV_Target0
{
    float4 offsets[3] = { offset0, offset1, offset2 };
    return SMAAColorEdgeDetectionPS(uv, offsets, tColor, tHzb);
}
#elif defined(BLENDING_WEIGHTS)
Texture2D<float4> tEdge : register(t0);
Texture2D<float4> tArea : register(t1);
Texture2D<float4> tSearch : register(t2);

float4 mainPS(
    float4 position : SV_Position0,
    float2 uv : UV0,
    float2 pixelCoordinate : PIX_COORD0,
    float4 offset0 : OFFSETS0,
    float4 offset1 : OFFSETS1,
    float4 offset2 : OFFSETS2) : SV_Target0
{
    float4 offsets[3] = { offset0, offset1, offset2 };
    return SMAABlendingWeightCalculationPS(
        uv, pixelCoordinate, offsets, tEdge, tArea, tSearch,
        cb_vSubsampleIndices);
}
#else
Texture2D<float4> tColor : register(t0);
Texture2D<float4> tBlend : register(t1);

float4 mainPS(
    float4 position : SV_Position0,
    float2 uv : UV0,
    float4 offset : OFFSET0) : SV_Target0
{
    return SMAANeighborhoodBlendingPS(uv, offset, tColor, tBlend);
}
#endif
