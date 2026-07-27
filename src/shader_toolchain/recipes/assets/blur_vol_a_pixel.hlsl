#include "include/post_fxaa_abi.hlsl"

SamplerState PointClampClamp : register(s1);
SamplerState LinearClampClamp : register(s6);
Texture2D<float3> volumetrics : register(t0);
Texture2D<float> hierarchicalDepth : register(t1);

float3 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float centerDepth = hierarchicalDepth.SampleLevel(
        PointClampClamp, uv, 2.0
    );
    float4 scaledPixel = cb_vDownScaleing.xyxy * cb_vPixelSizeMipUp.xyxy;
    float4 depthCoordinates = scaledPixel.zwzw
        * float4(-3.0, -3.0, 3.0, -3.0) + uv.xyxy;
    float4 neighborDepth;
    neighborDepth.x = hierarchicalDepth.SampleLevel(
        PointClampClamp, depthCoordinates.xy, 2.0
    );
    neighborDepth.y = hierarchicalDepth.SampleLevel(
        PointClampClamp, depthCoordinates.zw, 2.0
    );
    depthCoordinates = scaledPixel.zwzw
        * float4(-3.0, 3.0, -1.5, -1.5) + uv.xyxy;
    neighborDepth.z = hierarchicalDepth.SampleLevel(
        PointClampClamp, depthCoordinates.xy, 2.0
    );
    float2 topLeftUv = min(cb_vUvLimitMipDown, depthCoordinates.zw);
    float3 topLeft = volumetrics.SampleLevel(
        LinearClampClamp, topLeftUv, 0.0
    );
    depthCoordinates = scaledPixel.zwzw
        * float4(3.0, 3.0, 1.5, 1.5) + uv.xyxy;
    float4 diagonalUvs = scaledPixel
        * float4(1.5, -1.5, -1.5, 1.5) + uv.xyxy;
    diagonalUvs = min(cb_vUvLimitMipDown.xyxy, diagonalUvs);
    neighborDepth.w = hierarchicalDepth.SampleLevel(
        PointClampClamp, depthCoordinates.xy, 2.0
    );
    float2 bottomRightUv = min(cb_vUvLimitMipDown, depthCoordinates.zw);
    float3 bottomRight = volumetrics.SampleLevel(
        LinearClampClamp, bottomRightUv, 0.0
    );

    float4 depthDelta = neighborDepth - centerDepth;
    float depthTolerance = max(0.01, 0.1 * (centerDepth * centerDepth));
    float4 weights = saturate(depthDelta / depthTolerance);
    weights = 1.0 - weights;
    weights = weights + weights;
    weights = depthDelta > 0.0 ? weights : 2.0;

    float3 topRight = volumetrics.SampleLevel(
        LinearClampClamp, diagonalUvs.xy, 0.0
    );
    float3 bottomLeft = volumetrics.SampleLevel(
        LinearClampClamp, diagonalUvs.zw, 0.0
    );
    topRight = topRight * weights.y;
    float3 result = topLeft * weights.x + topRight;
    result = bottomLeft * weights.z + result;
    result = bottomRight * weights.w + result;

    float totalWeight = 4.0 + dot(weights, 1.0);
    result = volumetrics.SampleLevel(LinearClampClamp, uv, 0.0) * 4.0 + result;
    return result / totalWeight;
}
