#include "include/post_fxaa_abi.hlsl"

SamplerState PointClampClamp : register(s1);
Texture2D<float3> frameTexture : register(t0);
Texture2D<float> depthTexture : register(t1);

float4 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float2 flippedUv = uv * float2(1.0, -1.0) + float2(0.0, 1.0);
    float2 clipPosition = flippedUv * 2.0 - 1.0;
    float2 viewPosition = cb_vNearFarViewCorner.zw * clipPosition;

    float depth = depthTexture.SampleLevel(PointClampClamp, uv, 0.0);
    float viewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + depth);
    viewPosition = viewPosition * viewDepth;

    float3 worldOffset = viewToWorld._m01_m11_m21 * viewPosition.y;
    worldOffset = viewToWorld._m00_m10_m20 * viewPosition.x + worldOffset;
    worldOffset = viewToWorld._m02_m12_m22 * -viewDepth + worldOffset;

    float distanceFromFace = length(worldOffset);
    float encodedDistance = sqrt(
        (distanceFromFace - 0.5) * 0.00784313772
    );
    float3 frame = frameTexture.SampleLevel(PointClampClamp, uv, 0.0);
    return float4(frame, encodedDistance);
}
