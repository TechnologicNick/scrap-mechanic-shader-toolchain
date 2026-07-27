#include "include/post_fxaa_abi.hlsl"

SamplerState LinearClampClamp : register(s6);
Texture2D<float4> inputColor : register(t0);

float4 mainDownsamplePS(float4 position : SV_Position0, float2 uv : UV0)
    : SV_Target0
{
    float2 offset = cb_vContainerPixelSize;
    float3 sum = inputColor.SampleLevel(LinearClampClamp, uv - offset, 0.0).rgb;
    sum = inputColor.SampleLevel(
        LinearClampClamp, uv + float2(offset.x, -offset.y), 0.0
    ).rgb + sum;
    sum = sum + inputColor.SampleLevel(
        LinearClampClamp, uv + float2(-offset.x, offset.y), 0.0
    ).rgb;
    sum = inputColor.SampleLevel(LinearClampClamp, uv + offset, 0.0).rgb + sum;
    return float4(0.25 * sum, 1.0);
}
