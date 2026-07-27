#include "include/post_fxaa_abi.hlsl"

SamplerState PointClampClamp : register(s1);
Texture2D<float> hierarchicalDepth : register(t0);

float4 mainPS(
    float4 position : SV_Position0,
    float4 viewPosition : VIEW_POSITION0,
    linear noperspective centroid float3 screenUv : SCREEN_UV0,
    nointerpolation float4 color : TEXCOORD0
) : SV_Target0
{
    float viewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + screenUv.z);
    float sceneDepth = hierarchicalDepth.Sample(PointClampClamp, screenUv.xy);
    float visibility = 1.0 - saturate(5.0 * (viewDepth - sceneDepth));
    float alphaMultiplier = visibility * 0.600000024 + 0.400000006;
    float colorMultiplier = max(0.600000024, alphaMultiplier);
    return color * float4(colorMultiplier.xxx, alphaMultiplier);
}
