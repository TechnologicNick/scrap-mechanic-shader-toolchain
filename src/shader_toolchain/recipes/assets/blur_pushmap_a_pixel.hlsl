#include "include/post_fxaa_abi.hlsl"

SamplerState LinearClampClamp : register(s6);
Texture2D<float3> inputPushMap : register(t0);

float GatherMaximum(float2 uv)
{
    float4 gathered = inputPushMap.GatherBlue(LinearClampClamp, uv);
    float2 pairs = max(gathered.xz, gathered.yw);
    return max(pairs.x, pairs.y);
}

float3 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float2 offset = 1.5 * cb_vContainerPixelSize;
    float2 topLeftUv = uv - offset;
    float2 topRightUv = uv + float2(offset.x, -offset.y);
    float2 bottomLeftUv = uv + float2(-offset.x, offset.y);
    float2 bottomRightUv = uv + offset;

    float topMaximum = max(
        GatherMaximum(topLeftUv), GatherMaximum(topRightUv)
    );
    float bottomMaximum = max(
        GatherMaximum(bottomLeftUv), GatherMaximum(bottomRightUv)
    );

    float2 sum = inputPushMap.SampleLevel(
        LinearClampClamp, topLeftUv, 0.0
    ).xy;
    sum = sum + inputPushMap.SampleLevel(
        LinearClampClamp, topRightUv, 0.0
    ).xy;
    sum = inputPushMap.SampleLevel(
        LinearClampClamp, bottomLeftUv, 0.0
    ).xy + sum;
    sum = sum + inputPushMap.SampleLevel(
        LinearClampClamp, bottomRightUv, 0.0
    ).xy;

    return float3(0.25 * sum, max(topMaximum, bottomMaximum));
}
