#include "include/post_fxaa_abi.hlsl"

void mainVS(
    float3 position : POSITION0,
    float4 localToWorld0 : LTW0,
    float4 localToWorld1 : LTW1,
    float4 localToWorld2 : LTW2,
    float4 color : COLOR0,
    out float4 clipPosition : SV_Position0,
    out float4 viewPosition : VIEW_POSITION0,
    out float3 screenUv : SCREEN_UV0,
    out float4 outputColor : TEXCOORD0
)
{
    float4 localPosition = float4(position, 1.0);
    float3 transformed = float3(
        dot(localToWorld0, localPosition),
        dot(localToWorld1, localPosition),
        dot(localToWorld2, localPosition)
    );
    float4 worldPosition = float4(transformed, 1.0);
    clipPosition = mul(worldToViewProjection, worldPosition);
    viewPosition = mul(worldToView, worldPosition);
    float3 normalizedPosition = clipPosition.xyz / clipPosition.w;
    screenUv = normalizedPosition * float3(0.5, -0.5, 1.0)
        + float3(0.5, 0.5, 0.0);
    screenUv.xy = cb_vRenderScale * screenUv.xy;
    outputColor = color.wzyx;
}
