#include "include/post_fxaa_abi.hlsl"

SamplerState PointClampClamp : register(s1);
Texture2D<float4> colorTexture : register(t0);
Texture2D<float4> depthTexture : register(t1);

float ViewDepth(float2 uv)
{
    float deviceDepth = depthTexture.Sample(PointClampClamp, uv).r;
    return cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + deviceDepth);
}

float Luminance(float3 color)
{
    return dot(color, float3(0.298999995, 0.587000012, 0.114));
}

float FocusResponse(float viewDepth, float ring)
{
    float nearResponse = -(viewDepth - 0.400000006) * 1.66666663 + 1.0;
    float farResponse = 0.00999999978 * (viewDepth - 25.0);
    float baseResponse = saturate(max(nearResponse, farResponse));
    if (ring == 1.0)
        return min(1.0, 3.0 * baseResponse);
    if (ring == 2.0)
        return saturate(3.0 * baseResponse - 1.0);
    return max(0.0, 3.0 * baseResponse - 2.0);
}

void AddTap(
    float2 uv,
    float centerDepth,
    float ring,
    float kernelScale,
    inout float3 colorSum,
    inout float weightSum
)
{
    uv = min(cb_vUvLimit, uv);
    float3 color = colorTexture.Sample(PointClampClamp, uv).rgb;
    float viewDepth = min(centerDepth, ViewDepth(uv));
    float weight = Luminance(color) * FocusResponse(viewDepth, ring);
    float scaledWeight = kernelScale * weight;
    colorSum = color * scaledWeight + colorSum;
    weightSum = weight * kernelScale + weightSum;
}

float4 DepthOfField(float2 uv, float2 pixelStep)
{
    float centerDepth = ViewDepth(uv);
    float3 colorSum = 0.0;
    float weightSum = 0.0;

    AddTap(uv - pixelStep, centerDepth, 1.0, 0.5, colorSum, weightSum);
    float3 centerColor = colorTexture.Sample(PointClampClamp, uv).rgb;
    float centerWeight = max(0.100000001, Luminance(centerColor));
    colorSum = centerColor * centerWeight + colorSum;
    weightSum = centerWeight + weightSum;
    AddTap(uv + pixelStep, centerDepth, 1.0, 0.5, colorSum, weightSum);
    AddTap(uv - 2.0 * pixelStep, centerDepth, 2.0, 0.25, colorSum, weightSum);
    AddTap(uv + 2.0 * pixelStep, centerDepth, 2.0, 0.25, colorSum, weightSum);
    AddTap(uv - 3.0 * pixelStep, centerDepth, 3.0, 0.125, colorSum, weightSum);
    AddTap(uv + 3.0 * pixelStep, centerDepth, 3.0, 0.125, colorSum, weightSum);
    return float4(colorSum / weightSum, 0.0);
}

float4 mainHorizontalPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float2 pixelStep = float2(
        cb_vDownScaleing.x * cb_vContainerPixelSize.x, 0.0
    );
    return DepthOfField(uv, pixelStep);
}

float4 mainVerticalPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float2 pixelStep = float2(
        0.0, cb_vDownScaleing.y * cb_vContainerPixelSize.y
    );
    return DepthOfField(uv, pixelStep);
}
