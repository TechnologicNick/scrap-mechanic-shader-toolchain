#if defined(PS_FADE_BEHIND)
#include "include/post_fxaa_abi.hlsl"
SamplerState PointClampClamp_s : register(s1);
SamplerState LinearWrapWrap_s : register(s3);
Texture2D<float4> tDif : register(t0);
Texture2D<float4> tDepth : register(t7);

float4 commonPS(
    float4 position : SV_Position0,
    float2 uv : TEXCOORD0,
    float endFade : TEXCOORD1,
    nointerpolation float fadeScale : TEXCOORD2,
    nointerpolation float3 color : COLOR0,
    linear noperspective centroid float3 screenUv : SCREEN_UV0,
    uint frontFace : SV_IsFrontFace0) : SV_Target0
{
    float sceneDepth = tDepth.Sample(PointClampClamp_s, screenUv.xy).x;
    float sceneViewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + sceneDepth);
    float lineViewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + screenUv.z);
    float depthDifference = lineViewDepth - sceneViewDepth;
    float behind = depthDifference < 0.0 ? 0.750000 : 0.0;
    float depthFade = mad(saturate(mad(-depthDifference, 0.0399999991, 1.0)),
                          0.25, behind);
    float endMask = 1.0 - abs(mad(endFade, 2.0, -1.0));
    endMask = saturate(4.0 * fadeScale * endMask);
    float4 diffuse = tDif.Sample(LinearWrapWrap_s, uv);
    return float4(color * diffuse.rgb, diffuse.a * endMask * depthFade);
}
#elif defined(PS_PERM_DEPTH)
void commonPS(
    float4 position : SV_Position0,
    float2 uv : TEXCOORD0,
    float endFade : TEXCOORD1,
    float fadeScale : TEXCOORD2,
    float3 color : COLOR0)
{
}
#else
float fLineWidth;
float fTextureAspect;
float fScroll;
float _fPadding;
#include "include/line_perframe_abi.hlsl"
SamplerState LinearWrapWrap_s : register(s3);
Texture2D<float4> tDif : register(t0);

#if defined(PS_PERM_OVERLAY)
#include "include/post_fxaa_abi.hlsl"
SamplerState LinearClampClamp_s : register(s6);
Texture2D<float4> tDepth : register(t7);

float4 commonPS(
    float4 position : SV_Position0,
    float2 uv : TEXCOORD0,
    float endFade : TEXCOORD1,
    nointerpolation float fadeScale : TEXCOORD2,
    nointerpolation float3 color : COLOR0,
    uint frontFace : SV_IsFrontFace0) : SV_Target0
{
    float2 screenUv = position.xy / (float2)cb_vuViewportSize;
    screenUv *= cb_vPrevRenderScale;
    float sceneDepth = tDepth.SampleLevel(LinearClampClamp_s, screenUv, 0.0).x;
    if (position.z < sceneDepth)
        discard;
    float2 scrolledUv = float2(mad(cb_fTime, fScroll, uv.x), uv.y);
    return float4(color * tDif.Sample(LinearWrapWrap_s, scrolledUv).rgb, 1.0);
}
#elif defined(PS_PERM_FORWARD_BEHIND)
SamplerState PointClampClamp_s : register(s1);
Texture2D<float4> tDepth : register(t7);

struct ForwardOutput
{
    float4 color : SV_Target0;
    float4 auxiliary : SV_Target1;
};

ForwardOutput commonPS(
    float4 position : SV_Position0,
    float2 uv : TEXCOORD0,
    float endFade : TEXCOORD1,
    nointerpolation float fadeScale : TEXCOORD2,
    nointerpolation float3 color : COLOR0,
    linear noperspective centroid float3 screenUv : SCREEN_UV0,
    uint frontFace : SV_IsFrontFace0)
{
    if (screenUv.z < tDepth.SampleLevel(PointClampClamp_s, screenUv.xy, 0.0).x)
        discard;
    float2 scrolledUv = float2(mad(cb_fTime, fScroll, uv.x), uv.y);
    ForwardOutput output;
    output.color = float4(color * tDif.Sample(LinearWrapWrap_s, scrolledUv).rgb, 1.0);
    output.auxiliary = float4(0.0, 0.0, 0.0, 1.0);
    return output;
}
#elif defined(PS_PERM_FORWARD)
struct ForwardOutput
{
    float4 color : SV_Target0;
    float4 auxiliary : SV_Target1;
};

ForwardOutput commonPS(
    float4 position : SV_Position0,
    float2 uv : TEXCOORD0,
    float endFade : TEXCOORD1,
    nointerpolation float fadeScale : TEXCOORD2,
    nointerpolation float3 color : COLOR0,
    uint frontFace : SV_IsFrontFace0)
{
    float2 scrolledUv = float2(mad(cb_fTime, fScroll, uv.x), uv.y);
    ForwardOutput output;
    output.color = float4(color * tDif.Sample(LinearWrapWrap_s, scrolledUv).rgb, 1.0);
    output.auxiliary = float4(0.0, 0.0, 0.0, 1.0);
    return output;
}
#else
float4 commonPS(
    float4 position : SV_Position0,
    float2 uv : TEXCOORD0,
    float endFade : TEXCOORD1,
    nointerpolation float fadeScale : TEXCOORD2,
    nointerpolation float3 color : COLOR0,
    float3 screenUv : SCREEN_UV0,
    uint frontFace : SV_IsFrontFace0) : SV_Target0
{
    float2 scrolledUv = float2(mad(cb_fTime, fScroll, uv.x), uv.y);
    float4 diffuse = tDif.Sample(LinearWrapWrap_s, scrolledUv);
    if (diffuse.a < 0.5)
        discard;
    float endMask = 1.0 - abs(mad(endFade, 2.0, -1.0));
    endMask = saturate(4.0 * fadeScale * endMask);
    return float4(color * diffuse.rgb, endMask * diffuse.a);
}
#endif
#endif
