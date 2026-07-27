#include "include/post_fxaa_abi.hlsl"

SamplerState PointClampClamp : register(s1);
SamplerState LinearClampClamp : register(s6);
Texture2D<float3> lowResolutionVolumetrics : register(t0);
Texture2D<float> hierarchicalDepth : register(t1);

float3 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float centerDepth = hierarchicalDepth.SampleLevel(
        PointClampClamp, uv, 2.0
    );
    float4 scaledPixel = cb_vDownScaleing.xyxy * cb_vPixelSizeMipUp.xyxy;

    float4 neighborDepth;
    float2 depthCoordinates = scaledPixel.zw * float2(-14.0, 14.0) + uv;
    neighborDepth.z = hierarchicalDepth.SampleLevel(
        PointClampClamp, depthCoordinates, 2.0
    );
    depthCoordinates = scaledPixel.zw * float2(14.0, 14.0) + uv;
    neighborDepth.w = hierarchicalDepth.SampleLevel(
        PointClampClamp, depthCoordinates, 2.0
    );
    float4 topDepthCoordinates = scaledPixel.zwzw
        * float4(-14.0, -14.0, 14.0, -14.0) + uv.xyxy;
    neighborDepth.x = hierarchicalDepth.SampleLevel(
        PointClampClamp, topDepthCoordinates.xy, 2.0
    );
    neighborDepth.y = hierarchicalDepth.SampleLevel(
        PointClampClamp, topDepthCoordinates.zw, 2.0
    );

    float4 depthDelta = neighborDepth - centerDepth;
    float depthTolerance = max(0.01, 0.1 * (centerDepth * centerDepth));
    float4 weights = saturate(depthDelta / depthTolerance);
    weights = 1.0 - weights;
    weights = weights + weights;
    weights = depthDelta > 0.0 ? weights : 2.0;

    float2 halfUv = 0.5 * uv;
    float4 crossUvs = scaledPixel
        * float4(3.5, -3.5, -3.5, 3.5) + halfUv.xyxy;
    float2 lowResolutionLimit = cb_vRenderScale * 0.5
        - cb_vPixelSizeMipDown;
    crossUvs = min(crossUvs, lowResolutionLimit.xyxy);
    float3 topRight = lowResolutionVolumetrics.SampleLevel(
        LinearClampClamp, crossUvs.xy, 0.0
    );
    float3 bottomLeft = lowResolutionVolumetrics.SampleLevel(
        LinearClampClamp, crossUvs.zw, 0.0
    );
    topRight = topRight * weights.y;

    float2 topLeftUv = scaledPixel.zw * float2(-3.5, -3.5) + halfUv;
    float2 bottomRightUv = scaledPixel.zw * float2(3.5, 3.5) + halfUv;
    float3 center = lowResolutionVolumetrics.SampleLevel(
        LinearClampClamp, halfUv, 0.0
    );
    bottomRightUv = min(bottomRightUv, lowResolutionLimit);
    topLeftUv = min(topLeftUv, lowResolutionLimit);
    float3 topLeft = lowResolutionVolumetrics.SampleLevel(
        LinearClampClamp, topLeftUv, 0.0
    );
    float3 result = topLeft * weights.x + topRight;
    result = bottomLeft * weights.z + result;
    float3 bottomRight = lowResolutionVolumetrics.SampleLevel(
        LinearClampClamp, bottomRightUv, 0.0
    );
    result = bottomRight * weights.w + result;

    float totalWeight = 4.0 + dot(weights, 1.0);
    result = center * 4.0 + result;
    return result / totalWeight;
}
