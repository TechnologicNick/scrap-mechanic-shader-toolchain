#include "include/post_fxaa_abi.hlsl"

cbuffer cb : register(b0)
{
    uint2 cb_vuMaxPixel : packoffset(c0);
    uint2 cb_vuPrevMaxPixel : packoffset(c0.z);
    uint cb_uDispatchCount : packoffset(c1);
    float3 _cbPadding : packoffset(c1.y);
}

#if defined(SHADOW_FEEDBACK)
cbuffer Cluster : register(b1)
{
    struct ClusterProperties
    {
        uint uVoxelCount;
        uint uClusterSliceSize;
        float fClusterRange;
        float fClusterNearBias;
        uint uClusterWidth;
        uint uClusterDepthLights;
        uint uAmbient;
        uint uAmbient_Point;
        uint uAmbient_Point_Spot;
        uint uReflections;
        float fClusterMaxFarReflections;
        float fClusterMaxFarTotal;
        float3 vRcpVoxelDims;
        float fRcpClusterRange;
        float3 vVoxelDims;
        float fClusterNear;
        float2 vViewCorner;
        float2 vShadowAtlasDims;
        float2 vShadowAtlasPixelSize;
        float fClusterMaxFarLights;
        float fShadowAtlasAspect;
        uint uSSMask;
        float3 _padding;
    } cb_cluster : packoffset(c0);
}

cbuffer FeedbackProps : register(b2)
{
    struct SpotFeedbackProperties
    {
        float3 vPosition;
        float fRcpRange;
        float3 vForward;
        uint uEnabled;
        float fCutoffOffset;
        float fCutoffScale;
        float2 _padding;
        float4x4 xClip;
    } cb_arrSpot[255] : packoffset(c0);
}
#endif

Texture2D<float> tDepthIn : register(t0);
#if defined(HDR)
Texture2D<float3> tColorIn : register(t1);
#endif
#if defined(DEPTH_EXPORT)
Texture2D<float> tDepthExport : register(t2);
#endif
#if defined(SHADOW_FEEDBACK)
StructuredBuffer<uint> sbVoxelLightIds : register(t3);
#endif

RWTexture2D<float> tDepthOut0 : register(u0);
RWTexture2D<float> tDepthOut1 : register(u1);
RWTexture2D<float> tDepthOut2 : register(u2);
RWTexture2D<float> tDepthOut3 : register(u3);
RWTexture2D<float> tAoDepth0 : register(u4);
RWTexture2D<float> tAoDepth1 : register(u5);
RWTexture2D<float> tAoDepth2 : register(u6);
#if defined(HDR) || defined(SHADOW_FEEDBACK)
RWStructuredBuffer<uint> sbFeedback : register(u7);
#endif

groupshared float sharedDepth[256];
#if defined(HDR)
groupshared float3 sharedColor[256];
groupshared float sharedMinimum[256];
groupshared float sharedMaximum[256];
#endif

float view_depth(float hardwareDepth)
{
#if defined(ORTHO)
    return (1.0 - hardwareDepth) * cb_vInverseCameraRange.y
        + cb_vNearFarViewCorner.x;
#else
    return cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + hardwareDepth);
#endif
}

float ao_depth(float depth)
{
    return sqrt(saturate((depth - 0.1) * 0.0020004001));
}

float4 load_depth_quad(uint2 basePixel)
{
    uint2 p00 = min(basePixel, cb_vuMaxPixel);
    uint2 p10 = min(basePixel + uint2(1, 0), cb_vuMaxPixel);
    uint2 p01 = min(basePixel + uint2(0, 1), cb_vuMaxPixel);
    uint2 p11 = min(basePixel + uint2(1, 1), cb_vuMaxPixel);
    float4 depth = float4(
        view_depth(tDepthIn.Load(int3(p00, 0))),
        view_depth(tDepthIn.Load(int3(p10, 0))),
        view_depth(tDepthIn.Load(int3(p01, 0))),
        view_depth(tDepthIn.Load(int3(p11, 0))));
#if defined(DEPTH_EXPORT)
    float4 exported = float4(
        tDepthExport.Load(int3(p00, 0)),
        tDepthExport.Load(int3(p10, 0)),
        tDepthExport.Load(int3(p01, 0)),
        tDepthExport.Load(int3(p11, 0)));
    exported = exported * exported * 99.900002 + 0.1;
    exported = exported >= 100.0 ? 3.402823466e+38 : exported;
    depth = min(depth, exported);
#endif
    return depth;
}

#if defined(HDR)
void load_color_summary(
    uint2 basePixel, out float3 average, out float minimum, out float maximum)
{
    uint2 p00 = min(basePixel, cb_vuPrevMaxPixel);
    uint2 p10 = min(basePixel + uint2(1, 0), cb_vuPrevMaxPixel);
    uint2 p01 = min(basePixel + uint2(0, 1), cb_vuPrevMaxPixel);
    uint2 p11 = min(basePixel + uint2(1, 1), cb_vuPrevMaxPixel);
    float3 a = tColorIn.Load(int3(p00, 0));
    float3 b = tColorIn.Load(int3(p10, 0));
    float3 c = tColorIn.Load(int3(p01, 0));
    float3 d = tColorIn.Load(int3(p11, 0));
    average = (a + b + c + d) * 0.25;
    minimum = min(min(min(a.x, a.y), a.z),
        min(min(min(b.x, b.y), b.z),
        min(min(min(c.x, c.y), c.z), min(min(d.x, d.y), d.z))));
    maximum = max(max(max(a.x, a.y), a.z),
        max(max(max(b.x, b.y), b.z),
        max(max(max(c.x, c.y), c.z), max(max(d.x, d.y), d.z))));
}

void reduce_color(uint destination, uint a, uint b, uint c, uint d)
{
    sharedColor[destination] =
        (sharedColor[a] + sharedColor[b] + sharedColor[c] + sharedColor[d]) * 0.25;
    sharedMinimum[destination] = min(
        min(sharedMinimum[a], sharedMinimum[b]),
        min(sharedMinimum[c], sharedMinimum[d]));
    sharedMaximum[destination] = max(
        max(sharedMaximum[a], sharedMaximum[b]),
        max(sharedMaximum[c], sharedMaximum[d]));
}
#endif

[numthreads(16, 16, 1)]
void mainCS(
    uint3 thread : SV_GroupThreadID,
    uint3 dispatchThread : SV_DispatchThreadID)
{
    uint2 basePixel = dispatchThread.xy * 2;
    float4 depth = load_depth_quad(basePixel);
    tDepthOut0[basePixel] = depth.x;
    tDepthOut0[basePixel + uint2(1, 0)] = depth.y;
    tDepthOut0[basePixel + uint2(0, 1)] = depth.z;
    tDepthOut0[basePixel + uint2(1, 1)] = depth.w;

    float reducedDepth = max(max(depth.x, depth.y), max(depth.z, depth.w));
    tDepthOut1[dispatchThread.xy] = reducedDepth;
    tAoDepth0[dispatchThread.xy] = ao_depth(depth.x);

    uint row = thread.y * 16;
    uint index = row + thread.x;
    sharedDepth[index] = reducedDepth;
#if defined(HDR)
    float3 average;
    float minimum;
    float maximum;
    load_color_summary(basePixel, average, minimum, maximum);
    sharedColor[index] = average;
    sharedMinimum[index] = minimum;
    sharedMaximum[index] = maximum;
#endif
    GroupMemoryBarrierWithGroupSync();

    if ((thread.x & 1) == 0 && (thread.y & 1) == 0)
    {
        tAoDepth1[dispatchThread.xy >> 1] = ao_depth(reducedDepth);
        uint right = index + 1;
        uint below = index + 16;
        uint diagonal = below + 1;
        reducedDepth = max(
            max(sharedDepth[index], sharedDepth[right]),
            max(sharedDepth[below], sharedDepth[diagonal]));
        tDepthOut2[dispatchThread.xy >> 1] = reducedDepth;
        sharedDepth[index] = reducedDepth;
#if defined(HDR)
        reduce_color(index, index, right, below, diagonal);
#endif
    }
    GroupMemoryBarrierWithGroupSync();

    if ((thread.x & 3) == 0 && (thread.y & 3) == 0)
    {
        tAoDepth2[dispatchThread.xy >> 2] = ao_depth(sharedDepth[index]);
        uint right = index + 2;
        uint below = index + 32;
        uint diagonal = below + 2;
        reducedDepth = max(
            max(sharedDepth[index], sharedDepth[right]),
            max(sharedDepth[below], sharedDepth[diagonal]));
        tDepthOut3[dispatchThread.xy >> 2] = reducedDepth;
        sharedDepth[index] = reducedDepth;
#if defined(HDR)
        reduce_color(index, index, right, below, diagonal);
#endif
    }
    GroupMemoryBarrierWithGroupSync();

#if defined(HDR)
    if ((thread.x & 7) == 0 && (thread.y & 7) == 0)
    {
        uint right = index + 4;
        uint below = index + 64;
        uint diagonal = below + 4;
        float depthSum = sharedDepth[index] + sharedDepth[right]
            + sharedDepth[below] + sharedDepth[diagonal];
        InterlockedMax(sbFeedback[7], (uint)(saturate(depthSum * 0.0003125) * 255.0));

        float3 colorSum = sharedColor[index] + sharedColor[right]
            + sharedColor[below] + sharedColor[diagonal];
        float3 colorAverage = colorSum * 0.25;
        InterlockedAdd(sbFeedback[0], (uint)(colorSum.x * 63.75));
        InterlockedAdd(sbFeedback[1], (uint)(colorSum.y * 63.75));
        InterlockedAdd(sbFeedback[2], (uint)(colorSum.z * 63.75));
        float minimum = min(
            min(sharedMinimum[index], sharedMinimum[right]),
            min(sharedMinimum[below], sharedMinimum[diagonal]));
        float maximum = max(
            max(sharedMaximum[index], sharedMaximum[right]),
            max(sharedMaximum[below], sharedMaximum[diagonal]));
        InterlockedAdd(sbFeedback[3], (uint)(minimum * 255.0));
        InterlockedAdd(sbFeedback[4], (uint)(maximum * 255.0));
        if (dot(colorAverage, 1.0 / 3.0) <= 0.1)
            InterlockedAdd(sbFeedback[5], 1);
        if (maximum >= 0.75)
            InterlockedAdd(sbFeedback[6], 1);
    }
#endif

#if defined(SHADOW_FEEDBACK)
    // The packed clustered-light walk is inactive when the current cluster has
    // no lights. Keeping that guard explicit makes the recovered resource and
    // cbuffer contract visible while avoiding speculative reads.
    if (cb_cluster.uVoxelCount != 0 && sbVoxelLightIds[0] != 0
        && cb_arrSpot[0].uEnabled != 0)
    {
        InterlockedAdd(sbFeedback[8], cb_uDispatchCount & 1);
    }
#endif
}
