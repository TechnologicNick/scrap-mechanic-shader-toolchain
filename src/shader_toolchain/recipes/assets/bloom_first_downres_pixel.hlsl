#include "include/post_fxaa_abi.hlsl"
#include "include/perframe_abi.hlsl"
#include "include/hdr_abi.hlsl"

SamplerState PointClamp : register(s1);
SamplerState LinearClamp : register(s6);
Texture2D<float3> colorTexture : register(t0);
Texture2D<float> glowTexture : register(t1);
Texture2D<float> hierarchicalDepth : register(t2);

struct BloomSample
{
    float3 color;
    float weight;
};

float3 DecodeHdrColor(float3 color)
{
    color = saturate(color);
    color = exp2(hdr.exponent * log2(color));
    color = saturate(hdr.inverseRange * (color - hdr.baseValue));
    return exp2(2.20000005 * log2(color));
}

BloomSample SampleBloom(
    float2 uv,
    float distanceScale,
    float threshold,
    float inverseThreshold)
{
    uv = min(cb_vUvLimitMipUp, uv);

    BloomSample sample;
    float glow = glowTexture.SampleLevel(LinearClamp, uv, 0);
    sample.color = DecodeHdrColor(colorTexture.SampleLevel(LinearClamp, uv, 0));

    float linearGlow = min(1.0, 2.00802994 * glow);
    float curvedGlow = saturate(2.00802994 * (glow - 0.5));
    float glowWeight = (linearGlow + cb_bloom.fGlowCurveMax * curvedGlow) * distanceScale;

    float luminance = dot(sample.color, float3(0.212599993, 0.715200007, 0.0722000003));
    float thresholdWeight = max(0.0, luminance - threshold) * inverseThreshold;
    thresholdWeight *= cb_bloom.fThresholdScale;
    sample.weight = max(glowWeight, thresholdWeight);
    return sample;
}

float3 CombineKernel(BloomSample a, BloomSample b, BloomSample c, BloomSample d)
{
    float4 weights = float4(a.weight, b.weight, c.weight, d.weight);
    float weightSum = dot(weights, 1.0);
    float4 normalizedWeights = weightSum != 0.0 ? weights / weightSum : 0.0;

    float3 result = (a.weight * a.color) * normalizedWeights.x;
    result = (b.weight * b.color) * normalizedWeights.y + result;
    result = (c.weight * c.color) * normalizedWeights.z + result;
    result = 2.0 * ((d.weight * d.color) * normalizedWeights.w) + result;
    return result;
}

float3 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float depth = hierarchicalDepth.SampleLevel(PointClamp, uv, 3);
    float distance = saturate(cb_bloom.fDistanceRcp * depth);
    distance *= distance;
    distance *= distance;

    float glowRange = cb_bloom.fFarGlow - cb_bloom.fBaseGlow;
    float distanceScale = cb_bloom.fBaseGlow + glowRange * distance;
    float threshold = cb_bloom.fMaxThreshold + hdr.glowy * glowRange;
    float inverseThreshold = rcp(threshold);
    float2 lower = mad(-cb_vPixelSizeMipUp, cb_vDownScaleing, uv);
    float2 lowerLeft = mad(-cb_vPixelSizeMipUp, cb_vDownScaleing, lower);
    float2 offset = cb_vDownScaleing * cb_vPixelSizeMipUp;
    float2 lowerRight = mad(offset, float2(-1.0, 1.0), lower);
    float2 upperLeft = lower + float2(offset.x, -offset.y);
    float2 upper = offset + uv;
    float4 diagonal = uv.xyxy + float4(offset.x, -offset.y, -offset.x, offset.y);

    float4 rightPair = diagonal.xyxy + float4(offset.x, -offset.y, offset.x, offset.y);
    float4 centerAndLeftTop = mad(
        offset.xyxy, float4(-1.0, 1.0, -1.0, 1.0), diagonal);
    float4 lowerMiddleAndLeft = mad(
        -cb_vPixelSizeMipUp.xyxy, cb_vDownScaleing.xyxy, diagonal);
    float4 centerAndUpperMiddle = diagonal.zwzw
        + float4(offset.x, -offset.y, offset.x, offset.y);
    float4 rightMiddleAndTop = upper.xyxy
        + float4(offset.x, -offset.y, offset.x, offset.y);
    float2 upperMiddle = mad(offset, float2(-1.0, 1.0), upper);

    BloomSample center = SampleBloom(uv, distanceScale, threshold, inverseThreshold);

    float3 result = CombineKernel(
        SampleBloom(lowerLeft, distanceScale, threshold, inverseThreshold),
        SampleBloom(upperLeft, distanceScale, threshold, inverseThreshold),
        SampleBloom(lowerRight, distanceScale, threshold, inverseThreshold),
        center);

    result = 4.0 * CombineKernel(
        SampleBloom(lower, distanceScale, threshold, inverseThreshold),
        SampleBloom(diagonal.xy, distanceScale, threshold, inverseThreshold),
        SampleBloom(diagonal.zw, distanceScale, threshold, inverseThreshold),
        SampleBloom(upper, distanceScale, threshold, inverseThreshold)) + result;

    result = CombineKernel(
        SampleBloom(lowerMiddleAndLeft.xy, distanceScale, threshold, inverseThreshold),
        SampleBloom(rightPair.xy, distanceScale, threshold, inverseThreshold),
        SampleBloom(centerAndLeftTop.xy, distanceScale, threshold, inverseThreshold),
        SampleBloom(rightPair.zw, distanceScale, threshold, inverseThreshold)) + result;

    result = CombineKernel(
        SampleBloom(lowerMiddleAndLeft.zw, distanceScale, threshold, inverseThreshold),
        SampleBloom(centerAndUpperMiddle.xy, distanceScale, threshold, inverseThreshold),
        SampleBloom(centerAndLeftTop.zw, distanceScale, threshold, inverseThreshold),
        SampleBloom(centerAndUpperMiddle.zw, distanceScale, threshold, inverseThreshold)) + result;

    result = CombineKernel(
        center,
        SampleBloom(rightMiddleAndTop.xy, distanceScale, threshold, inverseThreshold),
        SampleBloom(upperMiddle, distanceScale, threshold, inverseThreshold),
        SampleBloom(rightMiddleAndTop.zw, distanceScale, threshold, inverseThreshold)) + result;

    return 0.125 * result;
}
