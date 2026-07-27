#include "include/post_fxaa_abi.hlsl"

SamplerState LinearClampClamp : register(s6);
Texture2D<float4> inputBloom : register(t0);

float4 SampleInput(float2 uv)
{
    return inputBloom.SampleLevel(
        LinearClampClamp, min(cb_vUvLimitMipDown, uv), 0.0
    );
}

float4 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float2 offset = cb_vPixelSizeMipDown * cb_vDownScaleing;
    float4 sum = SampleInput(uv - offset);
    float4 positiveNegative = SampleInput(uv + float2(offset.x, -offset.y));
    float4 negativePositive = SampleInput(uv + float2(-offset.x, offset.y));
    sum = 2.0 * sum + 2.0 * positiveNegative;
    sum = 2.0 * negativePositive + sum;
    sum = 2.0 * SampleInput(uv + offset) + sum;
    sum = SampleInput(uv + float2(0.0, 2.0 * offset.y)) + sum;
    float4 positiveHorizontal = SampleInput(uv + float2(2.0 * offset.x, 0.0));
    sum = SampleInput(uv + float2(0.0, -2.0 * offset.y)) + sum;
    sum = sum + SampleInput(uv + float2(-2.0 * offset.x, 0.0));
    sum = sum + positiveHorizontal;
    return (1.0 / 12.0) * sum;
}
