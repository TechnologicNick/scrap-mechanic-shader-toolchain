#include "include/post_fxaa_abi.hlsl"

struct BoundsFeedbackBuffer
{
    float3 minimum;
    float minimumPadding;
    float3 maximum;
    float maximumPadding;
};

cbuffer CB_INDEX : register(b0)
{
    struct
    {
        uint uIndex;
        float3 _vPadding;
    } cb_index : packoffset(c0);
}

Texture2D<float> depthTexture : register(t0);
RWStructuredBuffer<BoundsFeedbackBuffer> bounds : register(u0);
#if defined(CS_Y_NEG_5)
RWStructuredBuffer<BoundsFeedbackBuffer> stagedBounds : register(u1);
#endif

groupshared float tileExtrema[1024];

float ReconstructAxisExtent(uint2 pixel)
{
    float encodedDepth = depthTexture.Load(uint3(pixel, 0));
    float viewDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + encodedDepth);
    float2 screen = float2(
        mad((float)pixel.x, 0.015625, -1.0),
        mad((float)pixel.y, -0.015625, 1.0));
    float2 viewPosition = cb_vNearFarViewCorner.zw * screen * viewDepth;
#if defined(CS_X_0) || defined(CS_X_NEG_1)
    float worldAxis = mad(viewToWorld._m00, viewPosition.x,
        viewToWorld._m01 * viewPosition.y);
    worldAxis = mad(viewToWorld._m02, -viewDepth, worldAxis);
#elif defined(CS_Y_4) || defined(CS_Y_NEG_5)
    float worldAxis = mad(viewToWorld._m10, viewPosition.x,
        viewToWorld._m11 * viewPosition.y);
    worldAxis = mad(viewToWorld._m12, -viewDepth, worldAxis);
#else
    float worldAxis = mad(viewToWorld._m20, viewPosition.x,
        viewToWorld._m21 * viewPosition.y);
    worldAxis = mad(viewToWorld._m22, -viewDepth, worldAxis);
#endif
    float extent = min(64.0, abs(worldAxis));
    return encodedDepth == 0.0 ? 0.0 : extent;
}

float AverageFour(float first, float second, float third, float fourth)
{
    float sum = first + second;
    sum += third;
    sum += fourth;
    return 0.25 * sum;
}

[numthreads(32, 32, 1)]
void mainCS(
    uint3 dispatchThread : SV_DispatchThreadID,
    uint3 groupThread : SV_GroupThreadID)
{
    uint2 tileOrigin = dispatchThread.xy * 4;
    float localMaximum = 0.5;
    [unroll]
    for (uint y = 0; y < 4; ++y)
    {
        [unroll]
        for (uint x = 0; x < 4; ++x)
        {
            localMaximum = max(
                localMaximum, ReconstructAxisExtent(tileOrigin + uint2(x, y)));
        }
    }

    uint sharedIndex = groupThread.y * 32 + groupThread.x;
    tileExtrema[sharedIndex] = localMaximum;
    GroupMemoryBarrierWithGroupSync();

    if (all((groupThread.xy & 1) == 0))
    {
        float reduced = max(tileExtrema[sharedIndex], tileExtrema[sharedIndex + 1]);
        reduced = max(reduced, tileExtrema[sharedIndex + 32]);
        reduced = max(reduced, tileExtrema[sharedIndex + 33]);
        tileExtrema[sharedIndex] = reduced;
    }
    GroupMemoryBarrierWithGroupSync();

    [unroll]
    for (uint stride = 2; stride <= 8; stride *= 2)
    {
        if (all((groupThread.xy & (stride * 2 - 1)) == 0))
        {
            tileExtrema[sharedIndex] = AverageFour(
                tileExtrema[sharedIndex],
                tileExtrema[sharedIndex + stride],
                tileExtrema[sharedIndex + stride * 32],
                tileExtrema[sharedIndex + stride * 33]);
        }
        GroupMemoryBarrierWithGroupSync();
    }

    if (all(groupThread.xy == 0))
    {
        float extent = AverageFour(
            tileExtrema[0], tileExtrema[16],
            tileExtrema[512], tileExtrema[528]);
#if defined(CS_X_0)
        bounds[cb_index.uIndex].maximum.x = extent;
#elif defined(CS_X_NEG_1)
        bounds[cb_index.uIndex].minimum.x = extent;
#elif defined(CS_Z_2)
        bounds[cb_index.uIndex].maximum.z = extent;
#elif defined(CS_Z_NEG_3)
        bounds[cb_index.uIndex].minimum.z = extent;
#elif defined(CS_Y_4)
        bounds[cb_index.uIndex].maximum.y = extent;
#else
        bounds[cb_index.uIndex].minimum.y = extent;
        stagedBounds[cb_index.uIndex].minimum =
            viewToWorld._m03_m13_m23 - bounds[cb_index.uIndex].minimum;
        stagedBounds[cb_index.uIndex].maximum =
            viewToWorld._m03_m13_m23 + bounds[cb_index.uIndex].maximum;
#endif
    }
}
