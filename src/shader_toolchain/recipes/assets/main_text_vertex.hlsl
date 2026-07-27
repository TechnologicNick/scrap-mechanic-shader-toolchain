#include "include/post_fxaa_abi.hlsl"

struct TextVertexOutput
{
    float4 position : SV_Position0;
#if defined(TRANSFER_COLOR)
    float3 viewPosition : VIEW_POSITION0;
    float2 uv : UV0;
    float3 normal : NORMAL0;
    float4 color : VERTEXCOLOR0;
    float3 instanceAsg : INSTANCE_ASG0;
#else
    float2 uv : UV0;
#endif
};

float3 AffinePosition(
    float3 localPosition, float4 localToWorld0, float4 localToWorld1, float4 localToWorld2)
{
    return float3(localToWorld0.x, localToWorld1.x, localToWorld2.x) * localPosition.x
        + float3(localToWorld0.y, localToWorld1.y, localToWorld2.y) * localPosition.y
        + float3(localToWorld0.z, localToWorld1.z, localToWorld2.z) * localPosition.z
        + float3(localToWorld0.w, localToWorld1.w, localToWorld2.w);
}

TextVertexOutput mainVS(
    float2 glyphPosition : POSITION0,
    float2 uv : UV0,
    float4 localToWorld0 : LTW0,
    float4 localToWorld1 : LTW1,
    float4 localToWorld2 : LTW2,
    float4 color : COLOR0,
    float4 instanceAsg : ASG0,
    float3 offset : OFFSET0,
    float scale : SCALE0)
{
    TextVertexOutput output;
    output.uv = uv;

#if defined(VS_CLIP_SPACE)
    float3 translation = float3(localToWorld0.w, localToWorld1.w, localToWorld2.w);
    float4 anchor = mul(worldToViewProjection, float4(translation, 1.0));
    float2 pixelSize = 2.0 * cb_vContainerPixelSize * anchor.w;
    float2 displaced = anchor.xy + (glyphPosition + offset.xz) * pixelSize * scale;
    displaced = floor(displaced / pixelSize) * pixelSize;
#if defined(VS_OVERLAY_INFINITE)
    output.position = float4(displaced, saturate(anchor.z), anchor.w);
#else
    output.position = float4(displaced, anchor.zw);
#endif
    float3 localNormal = float3(localToWorld0.y, localToWorld1.y, localToWorld2.y);
    output.normal = -mul((float3x3)worldToView, localNormal);
    float3 localGlyph = float3(glyphPosition.x, 0.0, glyphPosition.y);
    output.viewPosition = mul(worldToView, float4(
        AffinePosition(localGlyph, localToWorld0, localToWorld1, localToWorld2), 1.0)).xyz;
#else
    float3 localGlyph = float3(glyphPosition.x, 0.0, glyphPosition.y) + offset;
    float3 worldPosition = AffinePosition(
        localGlyph, localToWorld0, localToWorld1, localToWorld2);
    float4 viewPosition = mul(worldToView, float4(worldPosition, 1.0));
    output.position = mul(cb_xViewToProjection, viewPosition);
#if defined(TRANSFER_COLOR)
    output.viewPosition = viewPosition.xyz;
    float3 localNormal = float3(localToWorld0.y, localToWorld1.y, localToWorld2.y);
    output.normal = -mul((float3x3)worldToView, localNormal);
#endif
#endif

#if defined(TRANSFER_COLOR)
    output.color = color.wzyx;
    output.instanceAsg = instanceAsg.xyz;
#endif
    return output;
}
