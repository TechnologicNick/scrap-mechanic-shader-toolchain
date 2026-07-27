#include "include/post_fxaa_abi.hlsl"

SamplerState LinearClampClamp : register(s6);
Texture2D<float3> inputColor : register(t0);

float3 SampleInput(float2 uv)
{
    return inputColor.SampleLevel(LinearClampClamp, min(cb_vUvLimit, uv), 0.0);
}

float4 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float2 offset = cb_vPixelSizeMipUp * cb_vRenderScale;
    float3 sum = SampleInput(uv - offset);
    sum = SampleInput(uv + float2(offset.x, -offset.y)) + sum;
    sum = sum + SampleInput(uv + float2(-offset.x, offset.y));
    sum = SampleInput(uv + offset) + sum;
    return float4(0.25 * sum, 1.0);
}
