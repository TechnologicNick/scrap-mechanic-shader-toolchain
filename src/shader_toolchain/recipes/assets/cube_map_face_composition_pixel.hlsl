#include "include/post_fxaa_abi.hlsl"
#include "include/perframe_abi.hlsl"

SamplerState PointClampClamp_s : register(s1);
Texture2D<float4> tLight : register(t0);
Texture2D<float4> tDepth : register(t1);

float FogCurve(float coordinate, float falloff, float minimumFalloff)
{
    return 1.0 - pow(1.0 - coordinate, max(falloff, minimumFalloff));
}

float3 mainPS(float4 position : SV_Position, float2 uv : UV0) : SV_Target0
{
    float2 ndc = (uv * float2(1.0, -1.0) + float2(0.0, 1.0))
        * 2.0 - 1.0;
    float deviceDepth = tDepth.SampleLevel(PointClampClamp_s, uv, 0.0).r;
    float viewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + deviceDepth);
    float3 viewPosition = float3(
        cb_vNearFarViewCorner.zw * ndc * viewDepth,
        -viewDepth
    );
    float worldHeight = dot(viewPosition, viewToWorld[2].xyz)
        + viewToWorld._m23;
    float viewDistance = length(viewPosition);
    uint fogIndex = worldHeight < cb_fWaterFogHeight ? 1 : 0;

    float verticalCoordinate = saturate(
        (worldHeight - cb_fogs[fogIndex].cb_fVerticalFogStart)
        * cb_fogs[fogIndex].cb_fVerticalFogInvRange
    );
    float verticalCurve = FogCurve(
        verticalCoordinate,
        cb_fogs[fogIndex].cb_fVerticalFogFalloff,
        0.01
    );
    float4 verticalColor = lerp(
        cb_fogs[fogIndex].cb_vVerticalFogStartColor,
        cb_fogs[fogIndex].cb_vVerticalFogEndColor,
        verticalCurve
    );
    float verticalDistance = 1.0 - saturate(
        cb_fogs[fogIndex].cb_fVerticalFogInvFade * viewDistance
    );
    float verticalAmount = verticalColor.a
        * (1.0 - verticalDistance * verticalDistance);

    float fogCoordinate = saturate(
        (viewDistance - cb_fogs[fogIndex].cb_fFogStart)
        * cb_fogs[fogIndex].cb_fFogInvRange
    );
    float distanceCurve = FogCurve(
        fogCoordinate,
        cb_fogs[fogIndex].cb_fFogFalloff,
        0.0001
    );
    float4 distanceColor = lerp(
        cb_fogs[fogIndex].cb_vFogStartColor,
        cb_fogs[fogIndex].cb_vFogEndColor,
        distanceCurve
    );
    float distanceAmount = distanceColor.a * saturate(
        cb_fogs[fogIndex].cb_fFogInvFade * viewDistance
    );
    float fogAmount = verticalAmount
        + distanceCurve * (distanceAmount - verticalAmount);
    float3 fogColor = distanceColor.rgb
        + verticalAmount * (verticalColor.rgb - distanceColor.rgb);

    float3 light = tLight.SampleLevel(PointClampClamp_s, uv, 0.0).rgb;
    return light + fogAmount * (fogColor - light);
}
