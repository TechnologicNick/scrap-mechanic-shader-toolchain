#include "include/post_fxaa_abi.hlsl"

SamplerState LinearClamp : register(s6);
Texture2D<float> sceneDepth : register(t7);
#if !defined(PS_SOLID_COLOR)
Texture2DArray<float4> diffuseBillboards : register(t0);
#if defined(PS_BLUR)
Texture2D<float> alphaMaskTexture : register(t1);
Texture2D<float4> blurredScene : register(t15);
#endif
#if defined(PS_OVERLAY_DEPTH_FADE)
Texture2D<float> hierarchicalDepth : register(t10);
#endif
#endif

float4 DecodeColor(uint packedColor)
{
    return float4(
        float(packedColor & 255u),
        float((packedColor >> 8) & 255u),
        float((packedColor >> 16) & 255u),
        float(packedColor >> 24)) * 0.00392156886;
}

float2 ScreenUv(float4 position)
{
    return cb_vPrevRenderScale * (position.xy / float2(cb_vuViewportSize));
}

void RejectBehindResolvedDepth(float4 position, float2 screenUv)
{
    if (position.z < sceneDepth.SampleLevel(LinearClamp, screenUv, 0))
        discard;
}

float4 commonPS(
    float4 position : SV_Position0,
    float3 texcoord : TEXCOORD0,
    float alphaScale : TEXCOORD1,
    nointerpolation uint packedColor : COLOR0,
    float depthOffset : TEXCOORD2,
    float minimumSize : TEXCOORD3,
    float3 viewPosition : VIEW_POSITION0,
    uint frontFace : SV_IsFrontFace0) : SV_Target0
{
    float2 unscaledScreenUv = position.xy / float2(cb_vuViewportSize);
    float2 screenUv = cb_vPrevRenderScale * unscaledScreenUv;
    RejectBehindResolvedDepth(position, screenUv);
    float4 color = DecodeColor(packedColor);

#if defined(PS_SOLID_COLOR)
    if (float(packedColor >> 24) < 127.499992)
        discard;
    return float4(color.rgb * color.rgb, color.a);
#else
    float4 diffuse = diffuseBillboards.Sample(LinearClamp, texcoord);

#if defined(PS_BLUR)
    float alphaMask = alphaMaskTexture.Sample(LinearClamp, texcoord.xy);
    if (alphaMask < 0.5)
        discard;

    float blend = diffuse.a < 0.5 ? diffuse.a * color.a : diffuse.a;
    float3 background = blurredScene.SampleLevel(LinearClamp, unscaledScreenUv, 0).rgb;
#if defined(PS_BLUR_COLOR)
    background *= color.rgb;
#endif
    background *= 0.5;
    float3 foreground = diffuse.xzy * color.rgb;
    float3 rgb = lerp(background, foreground, blend);
#if defined(PS_OVERLAY_DEPTH_FADE)
    float hzbDepth = hierarchicalDepth.SampleLevel(LinearClamp, screenUv, 0);
    float viewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + position.z);
    bool occluded = hzbDepth < viewDepth - depthOffset;
    float alpha = (occluded ? alphaScale * alphaMask : alphaMask) * color.a;
#else
    float alpha = alphaMask * color.a;
#endif
    return float4(rgb, alpha);
#else
    if (diffuse.a < 0.5)
        discard;
    float3 colorBytes = float3(
        float(packedColor & 255u),
        float((packedColor >> 8) & 255u),
        float((packedColor >> 16) & 255u));
    float3 rgb = (diffuse.rgb * colorBytes) * 0.00392156886;
#if defined(PS_OVERLAY_DEPTH_FADE)
    float hzbDepth = hierarchicalDepth.SampleLevel(LinearClamp, screenUv, 0);
    float viewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + position.z);
    bool occluded = hzbDepth < viewDepth - depthOffset;
    float alpha = (occluded ? alphaScale * diffuse.a : diffuse.a) * color.a;
#else
    float alpha = (diffuse.a * float(packedColor >> 24)) * 0.00392156886;
#endif
    return float4(rgb, alpha);
#endif
#endif
}
