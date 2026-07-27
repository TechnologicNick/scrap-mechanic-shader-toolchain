#include "include/post_fxaa_abi.hlsl"
#include "include/perframe_abi.hlsl"
#include "include/hdr_abi.hlsl"

SamplerState PointClampClamp_s : register(s1);
Texture2D<float3> tColor : register(t0);
Texture2D<float> tGlow : register(t1);
Texture2D<float> tHzb : register(t2);

struct WeightedColor
{
    float3 color;
    float weight;
};

WeightedColor ReadWeightedColor(
    float2 uv,
    float glowScale,
    float chromaRange,
    float minimumWeight,
    float maximumWeight
)
{
    float glow = min(1.0, 2.00802994
        * tGlow.SampleLevel(PointClampClamp_s, uv, 0.0).r);
    glow *= glowScale;
    float3 color = tColor.SampleLevel(PointClampClamp_s, uv, 0.0);
    float chroma = dot(
        abs(color - color.yzx),
        float3(0.333333343, 0.333333343, 0.333333343)
    );
    chroma = saturate(chroma / chromaRange);
    float chromaWeight = minimumWeight
        + chroma * (maximumWeight - minimumWeight);
    float glowBoost = min(1.0, max(0.5, chromaWeight / maximumWeight));
    float weight = max(chromaWeight, glow * glowBoost);

    WeightedColor result;
    result.color = color * weight;
    result.weight = weight;
    return result;
}

float PackIndirectColor(float3 indirectColor)
{
    float blueAverage = indirectColor.b * 0.25;
    float redDifference = indirectColor.r * 0.25 - blueAverage;
    float luminance = redDifference * 0.5 + blueAverage;
    float greenDifference = indirectColor.g * 0.25 - luminance;
    luminance = greenDifference * 0.5 + luminance;

    uint luminanceBin = (uint)(
        sqrt(sqrt(saturate(luminance * 0.015625))) * 63.0 + 0.5
    );
    float inverseLuminance = rcp(max(0.01, luminance));
    float2 chroma = float2(redDifference, greenDifference) * inverseLuminance;
    chroma *= rsqrt(max(0.0001, 4.0 * abs(chroma)));
    uint2 chromaBins = (uint2)min(
        30.0, max(0.0, chroma * 15.0 + 15.5)
    );
    uint packed = luminanceBin * 1024 + chromaBins.x * 32 + chromaBins.y;
    return packed * 1.52590219e-05;
}

float2 mainPS(
    float4 position : SV_Position,
    float2 uv : UV0,
    float2 unscaledUv : UNSCALED_UV0
) : SV_Target0
{
    float depth = tHzb.SampleLevel(PointClampClamp_s, uv, 0.0).r;
    if (depth > hdr.maximumDepth)
    {
        return float2(0.00755321607, 1.0);
    }

    float2 offset = cb_vDownScaleing * cb_vPixelSizeMipUp;
    float glowScale = saturate(0.5 * hdr.hdrSignal) * 64.0 + 32.0;
    float chromaRange = hdr.hdrSignal * 1.5 + 0.5;
    float maximumWeight = hdr.hdrSignal * (2.0 * cb_fTodFactor) + 4.5;
    float minimumWeight = cb_fTodFactor * 0.5 + 0.5;

    WeightedColor north = ReadWeightedColor(
        uv + offset * float2(0.0, -2.0),
        glowScale, chromaRange, minimumWeight, maximumWeight
    );
    WeightedColor west = ReadWeightedColor(
        uv + offset * float2(-2.0, 0.0),
        glowScale, chromaRange, minimumWeight, maximumWeight
    );
    WeightedColor east = ReadWeightedColor(
        uv + offset * float2(2.0, 0.0),
        glowScale, chromaRange, minimumWeight, maximumWeight
    );
    WeightedColor south = ReadWeightedColor(
        uv + offset * float2(0.0, 2.0),
        glowScale, chromaRange, minimumWeight, maximumWeight
    );
    float3 indirectColor = north.color + west.color + east.color + south.color;

    float normalizedDepth = saturate(
        (depth - 0.100000001) / (hdr.maximumDepth - 0.100000001)
    );
    return float2(PackIndirectColor(indirectColor), sqrt(normalizedDepth));
}
