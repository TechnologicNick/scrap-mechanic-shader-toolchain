#include "include/post_fxaa_abi.hlsl"
#include "include/hdr_abi.hlsl"

Texture2D<float3> inputColor : register(t0);

float3 mainPS(
    float4 position : SV_Position0, float2 unscaledUv : UNSCALED_UV0
) : SV_Target0
{
    uint2 sourcePixel = (uint2)(unscaledUv * cb_vuViewportSize);
    float3 color = saturate(inputColor.Load(uint3(sourcePixel, 0)));
    color = exp2(hdr.exponent * log2(color));
    color = color - hdr.baseValue;
    return saturate(hdr.inverseRange * color);
}
