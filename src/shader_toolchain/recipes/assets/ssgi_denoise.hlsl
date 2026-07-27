#include "include/post_fxaa_abi.hlsl"
#include "include/ao_settings_abi.hlsl"

SamplerState PointClamp : register(s1);
SamplerState LinearClamp : register(s6);
Texture2D<float4> indirectInput : register(t0);
Texture2D<float> aoDepth : register(t1);
Texture2D<float> materialInput : register(t3);

#if defined(PS_SSS_COUNT)
#if PS_SSS_COUNT == 1
#define SSS_VALUE float
#elif PS_SSS_COUNT == 2
#define SSS_VALUE float2
#elif PS_SSS_COUNT == 3
#define SSS_VALUE float3
#else
#define SSS_VALUE float4
#endif
Texture2D<SSS_VALUE> subsurfaceInput : register(t4);
#endif

float ViewDepth(float encodedDepth)
{
    float squaredDepth = encodedDepth * encodedDepth;
    return mad(squaredDepth, 499.899994, 0.100000001);
}

bool AcceptNeighborhood(float2 scaledUv, float2 offset, float2 stepSize,
                        float centerDepth, float thresholdSquared)
{
    float4 depths = aoDepth.Gather(
        LinearClamp, scaledUv + offset * stepSize);
    depths = depths * depths;
    depths = mad(depths, 499.899994, 0.100000001) - centerDepth;
    return all(depths * depths < thresholdSquared);
}

#if defined(PS_SSS_COUNT)
struct DenoiseOutput
{
    float4 indirect : SV_Target0;
    SSS_VALUE subsurface : SV_Target1;
};
#else
struct DenoiseOutput
{
    float4 indirect : SV_Target0;
};
#endif

DenoiseOutput mainPS(
    float4 position : SV_Position0,
    float2 uv : UV0,
    float2 unscaledUv : UNSCALED_UV0)
{
    DenoiseOutput output;
    float2 scaledUv = cb_settings.vRenderScale * unscaledUv;
    float centerDepth = ViewDepth(
        aoDepth.SampleLevel(PointClamp, scaledUv, 0.0));
    if (centerDepth >= cb_vNearFarViewCorner.y - 1.0)
    {
        output.indirect = float4(0.0, 0.0, 0.0, 1.0);
#if defined(PS_SSS_COUNT)
        output.subsurface = (SSS_VALUE)0.0;
#endif
        return output;
    }

    float material = materialInput.SampleLevel(PointClamp, scaledUv, 0.0);
    float shapedMaterial = 1.0 - pow(abs(1.0 - material), 0.75);
    float edgeMix = saturate(3.5999999 * shapedMaterial * material);
    edgeMix = min(1.0, max(0.0, edgeMix - 0.150000006) * 1.42857146);
    edgeMix = 1.0 - edgeMix;
    edgeMix *= edgeMix;
    float neighborWeight = edgeMix * edgeMix;
    float centerWeight = max(0.0001, 1.0 - neighborWeight);

    float4 center = indirectInput.SampleLevel(PointClamp, uv, 0.0);
    float3 indirectSum = center.rgb * centerWeight;
    float weightSum = centerWeight;
    float aoSum = center.a;
    float sampleCount = 1.0;
#if defined(PS_SSS_COUNT)
    SSS_VALUE subsurfaceSum = subsurfaceInput.SampleLevel(
        PointClamp, min(cb_settings.vUvLimit, uv), 0.0);
#endif

    float2 stepSize = cb_vContainerPixelSize * (neighborWeight + 0.25);
    float threshold = min(
        0.5, max(0.01, cb_settings.fThresholdBase
            * centerDepth * centerDepth));
    float thresholdSquared = threshold * threshold;
    static const float2 offsets[8] = {
        float2(-1.0, -1.0), float2( 0.0, -1.0),
        float2( 1.0, -1.0), float2(-1.0,  0.0),
        float2( 1.0,  0.0), float2(-1.0,  1.0),
        float2( 0.0,  1.0), float2( 1.0,  1.0),
    };

    [unroll] for (uint index = 0; index < 8; ++index)
    {
        float2 offset = offsets[index];
        if (AcceptNeighborhood(
                scaledUv, offset, stepSize, centerDepth, thresholdSquared))
        {
            float2 sampleUv = min(cb_settings.vUvLimit, uv + offset * stepSize);
            float4 neighbor = indirectInput.SampleLevel(
                LinearClamp, sampleUv, 0.0);
            indirectSum += neighbor.rgb * neighborWeight;
            weightSum += neighborWeight;
            aoSum += neighbor.a;
            sampleCount += 1.0;
#if defined(PS_SSS_COUNT)
            subsurfaceSum += subsurfaceInput.SampleLevel(
                LinearClamp, sampleUv, 0.0);
#endif
        }
    }

    output.indirect = float4(
        indirectSum / weightSum, aoSum / sampleCount);
#if defined(PS_SSS_COUNT)
    output.subsurface = subsurfaceSum / sampleCount;
#endif
    return output;
}
