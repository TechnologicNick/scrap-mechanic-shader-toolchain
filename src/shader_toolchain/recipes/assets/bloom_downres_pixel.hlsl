#include "include/post_fxaa_abi.hlsl"

SamplerState LinearClampClamp : register(s6);
Texture2D<float3> inputBloom : register(t0);

float3 SampleInput(float2 uv)
{
    return inputBloom.Sample(LinearClampClamp, min(cb_vUvLimitMipUp, uv));
}

float3 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float2 offset = cb_vPixelSizeMipUp * cb_vDownScaleing;
    float3 sum = SampleInput(uv - offset);
    sum = 4.0 * SampleInput(uv) + sum;
    sum = SampleInput(uv + float2(offset.x, -offset.y)) + sum;
    sum = sum + SampleInput(uv + float2(-offset.x, offset.y));
    sum = SampleInput(uv + offset) + sum;
    return 0.125 * sum;
}
