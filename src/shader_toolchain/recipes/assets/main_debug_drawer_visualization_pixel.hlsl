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
    float stripe = sin(450.0 * (screenUv.x * cb_fViewportAspect + screenUv.y));
    float stripeFourth = abs(stripe) * abs(stripe);
    stripeFourth = stripeFourth * stripeFourth;
    float stripePattern = abs(stripe) * stripeFourth;

    float farFade = saturate(
        0.00999999978
        * (abs(viewPosition.z) - (cb_vNearFarViewCorner.x + 6.0))
    );
    farFade = 1.0 - farFade;

    float viewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + screenUv.z);
    float sceneDepth = hierarchicalDepth.Sample(PointClampClamp, screenUv.xy);
    bool occluded = sceneDepth < viewDepth - 0.0125000002;
    float depthFade = saturate(
        0.100000001 * ((viewDepth - sceneDepth) - 0.100000001)
    );
    depthFade = 1.0 - depthFade;
    precise float visibilityFade = depthFade * farFade;
    precise float fadedAlpha = stripePattern * visibilityFade;
    fadedAlpha = 0.330000013 * fadedAlpha;
    return float4(color.rgb, occluded ? fadedAlpha : 0.330000013);
}
