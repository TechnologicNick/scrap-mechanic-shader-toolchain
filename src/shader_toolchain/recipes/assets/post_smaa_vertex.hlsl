#include "include/post_fxaa_abi.hlsl"

cbuffer cb : register(b0)
{
    float4 SMAA_RT_METRICS : packoffset(c0);
    float4 cb_vSubsampleIndices : packoffset(c1);
}

struct SmaaVertexOutput
{
    float4 position : SV_Position0;
    float2 uv : UV0;
#if defined(BLENDING_WEIGHTS)
    float2 pixelCoordinate : PIX_COORD0;
    float4 offset0 : OFFSETS0;
    float4 offset1 : OFFSETS1;
    float4 offset2 : OFFSETS2;
#elif defined(EDGE_DETECTION)
    float4 offset0 : OFFSETS0;
    float4 offset1 : OFFSETS1;
    float4 offset2 : OFFSETS2;
#else
    float4 offset : OFFSET0;
#endif
};

SmaaVertexOutput mainVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] = {
        float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0)
    };
    static const float2 coordinates[3] = {
        float2(0.0, 0.0), float2(2.0, 0.0), float2(0.0, 2.0)
    };
    SmaaVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);
    float2 uv = coordinates[vertexId] * cb_vRenderScale;
    output.uv = uv;
#if defined(BLENDING_WEIGHTS)
    output.pixelCoordinate = SMAA_RT_METRICS.zw * uv;
    float4 horizontal = SMAA_RT_METRICS.xxyy
        * float4(-0.25, 1.25, -0.125, -0.125) + uv.xxyy;
    float4 vertical = SMAA_RT_METRICS.xyxy
        * float4(-0.125, -0.25, -0.125, 1.25) + uv.xyxy;
    output.offset0 = horizontal.xzyw;
    output.offset1 = vertical;
    horizontal.zw = vertical.yw;
    #if defined(SMAA_PRESET_LOW)
        const float searchSteps = 8.0;
    #elif defined(SMAA_PRESET_MEDIUM)
        const float searchSteps = 16.0;
    #elif defined(SMAA_PRESET_HIGH)
        const float searchSteps = 32.0;
    #else
        const float searchSteps = 64.0;
    #endif
    output.offset2 = SMAA_RT_METRICS.xxyy
        * float4(-searchSteps, searchSteps, -searchSteps, searchSteps)
        + horizontal;
#elif defined(EDGE_DETECTION)
    output.offset0 = SMAA_RT_METRICS.xyxy * float4(-1.0, 0.0, 0.0, -1.0) + uv.xyxy;
    output.offset1 = SMAA_RT_METRICS.xyxy * float4(1.0, 0.0, 0.0, 1.0) + uv.xyxy;
    output.offset2 = SMAA_RT_METRICS.xyxy * float4(-2.0, 0.0, 0.0, -2.0) + uv.xyxy;
#else
    output.offset = SMAA_RT_METRICS.xyxy * float4(1.0, 0.0, 0.0, 1.0) + uv.xyxy;
#endif
    return output;
}
