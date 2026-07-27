#include "include/post_fxaa_abi.hlsl"

SamplerState LinearWrap : register(s3);
Texture2D<float4> fontTexture : register(t0);

float2 EncodeViewNormal(float3 viewNormal)
{
    float3 normal = normalize(viewNormal).zxy;
    normal /= dot(abs(normal), 1.0);
    float2 wrapped = (1.0 - abs(normal.zy))
        * float2(normal.y >= 0.0 ? 1.0 : -1.0,
                 normal.z >= 0.0 ? 1.0 : -1.0);
    return 0.5 * (normal.x >= 0.0 ? normal.yz : wrapped) + 0.5;
}

#if defined(PS_ALPHA_CUTOFF)
struct TextGBuffer
{
    float4 albedo : SV_Target0;
    float2 normal : SV_Target1;
    float4 material : SV_Target2;
};

TextGBuffer commonPS(
    float4 position : SV_Position0,
    float3 viewPosition : VIEW_POSITION0,
    float2 uv : UV0,
    float3 viewNormal : NORMAL0,
    float4 vertexColor : VERTEXCOLOR0,
    nointerpolation float3 instanceAsg : INSTANCE_ASG0,
    uint frontFace : SV_IsFrontFace0)
{
    float fontCoverage = fontTexture.SampleBias(LinearWrap, uv, cb_fMipBias).r;
    if (fontCoverage < 0.5)
        discard;

    TextGBuffer output;
    output.albedo = float4(vertexColor.rgb, instanceAsg.z * vertexColor.a);
    output.normal = EncodeViewNormal(viewNormal);
    output.material = float4(instanceAsg.xy, 0.0, 0.0);
    return output;
}
#else
#include "main_text_overlay_abi.hlsl"

SamplerState LinearClamp : register(s6);
Texture2D<float4> sceneDepth : register(t7);
Texture2D<float> hierarchicalDepth : register(t10);

float4 commonPS(
    float4 position : SV_Position0,
    float3 viewPosition : VIEW_POSITION0,
    float2 uv : UV0,
    float3 viewNormal : NORMAL0,
    float4 vertexColor : VERTEXCOLOR0,
    float3 instanceAsg : INSTANCE_ASG0,
    uint frontFace : SV_IsFrontFace0) : SV_Target0
{
    float2 screenUv = cb_vPrevRenderScale
        * (position.xy / float2(cb_vuViewportSize));
    float resolvedDepth = sceneDepth.SampleLevel(LinearClamp, screenUv, 0).r;
    if (position.z < resolvedDepth)
        discard;

    float fontCoverage = fontTexture.SampleBias(LinearWrap, uv, cb_fMipBias).r;
    float baseAlpha = vertexColor.a * fontCoverage;
    float hzbDepth = hierarchicalDepth.SampleLevel(LinearClamp, screenUv, 0);
    float viewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + position.z);
    bool behindGeometry = hzbDepth < viewDepth - cb_overlay.fDepthOffset;

#if defined(PS_OVERLAY_DEPTH_FADE)
    float alpha = behindGeometry ? cb_overlay.fAlpha * baseAlpha : baseAlpha;
#else
    if (behindGeometry)
        discard;
    float alpha = baseAlpha;
#endif
    return float4(vertexColor.rgb, alpha);
}
#endif
