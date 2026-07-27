cbuffer Cluster : register(b0)
{
    struct
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
        float3 padding;
    } cb_cluster : packoffset(c0);
}

cbuffer ClusterCulling : register(b1)
{
    uint4 cb_arrRanges[90] : packoffset(c0);
    float4 cb_arrCullData[3066] : packoffset(c90);
}

RWStructuredBuffer<uint> clusteredLightIds : register(u0);

static const uint CLUSTER_RECORD_WORDS = 33;
static const uint MASK_WORDS = 8;

struct ClusterBounds
{
    float3 center;
    float3 halfExtent;
    float radius;
};

uint ExtractByte(uint value, uint byteIndex)
{
    return (value >> (byteIndex * 8)) & 255u;
}

bool SphereIntersectsCluster(float4 sphere, ClusterBounds bounds)
{
    float3 outside = abs(bounds.center - sphere.xyz) - bounds.halfExtent;
    outside = max(0.0, outside);
    return dot(outside, outside) < sphere.w;
}

bool ConeIntersectsCluster(uint recordIndex, ClusterBounds bounds)
{
    float4 outerSphere = cb_arrCullData[recordIndex];
    if (!SphereIntersectsCluster(outerSphere, bounds))
        return false;

    float4 innerSphere = cb_arrCullData[recordIndex + 1];
    float3 centerOffset = bounds.center - outerSphere.xyz;
    float3 outside = abs(centerOffset) - bounds.halfExtent;
    outside = max(0.0, outside);
    if (dot(outside, outside) >= innerSphere.w)
        return false;

    float projection = dot(centerOffset, cb_arrCullData[recordIndex + 2].xyz);
    float perpendicularSquared = dot(centerOffset, centerOffset)
        - projection * projection;
    float perpendicular = sqrt(max(0.01, perpendicularSquared));
    float2 coneScale = cb_arrCullData[recordIndex + 3].xy;
    return coneScale.x * perpendicular - coneScale.y * projection
        < bounds.radius;
}

bool FrustumIntersectsCluster(uint recordIndex, ClusterBounds bounds)
{
    float4 horizontal = cb_arrCullData[recordIndex];
    float4 packedOffsets = cb_arrCullData[recordIndex + 1];
    float4 vertical = cb_arrCullData[recordIndex + 2];
    float4 depth = cb_arrCullData[recordIndex + 3];

    if (dot(bounds.center, horizontal.xyz) + horizontal.w >= bounds.radius)
        return false;
    if (dot(bounds.center, -horizontal.xyz) + packedOffsets.x >= bounds.radius)
        return false;
    if (dot(bounds.center, vertical.xyz) + vertical.w >= bounds.radius)
        return false;
    if (dot(bounds.center, -vertical.xyz) + packedOffsets.y >= bounds.radius)
        return false;
    if (dot(bounds.center, depth.xyz) + depth.w >= bounds.radius)
        return false;
    return dot(bounds.center, -depth.xyz) + packedOffsets.z < bounds.radius;
}

void AddMaskBit(inout uint masks[MASK_WORDS], uint lightIndex)
{
    masks[lightIndex >> 5] |= 1u << lightIndex;
}

void FlushMasks(
    inout uint masks[MASK_WORDS], uint clusterBase, uint outputOffset,
    uint activeBitOffset, inout uint activeMasks)
{
    [unroll]
    for (uint maskIndex = 0; maskIndex < MASK_WORDS; ++maskIndex)
    {
        if (masks[maskIndex] != 0)
        {
            clusteredLightIds[clusterBase + outputOffset + maskIndex]
                = masks[maskIndex];
            activeMasks |= 1u << (activeBitOffset + maskIndex);
            masks[maskIndex] = 0;
        }
    }
}

ClusterBounds BuildClusterBounds(uint depthSlice, uint2 cell)
{
    float2 depthIndices = float2(depthSlice, depthSlice + 1u);
    float2 depth = cb_cluster.vRcpVoxelDims.zz * depthIndices;
    depth *= depth;
    depth = depth * cb_cluster.fClusterRange + cb_cluster.fClusterNear;

    float4 corners = float4(cell, cell + 1u);
    corners *= cb_cluster.vRcpVoxelDims.xyxy;
    corners = corners * float4(1.0, -1.0, 1.0, -1.0)
        + float4(0.0, 1.0, 0.0, 1.0);
    corners = corners * 2.0 - 1.0;
    corners *= cb_cluster.vViewCorner.xyxy;

    float2 minimumXY;
    float2 maximumXY;
#if defined(ORTHO)
    minimumXY = min(corners.xy, corners.zw);
    maximumXY = max(corners.xy, corners.zw);
#else
    float4 farCorners = corners * depth.y;
    float2 farMinimum = min(farCorners.xy, farCorners.zw);
    float2 farMaximum = max(farCorners.xy, farCorners.zw);
    float4 nearCorners = corners * depth.x;
    float2 nearMinimum = min(nearCorners.xy, nearCorners.zw);
    float2 nearMaximum = max(nearCorners.xy, nearCorners.zw);
    minimumXY = min(nearMinimum, farMinimum);
    maximumXY = max(nearMaximum, farMaximum);
#endif

    float3 minimum = float3(minimumXY, depth.x);
    float3 maximum = float3(maximumXY, depth.y);
    ClusterBounds bounds;
    bounds.halfExtent = (maximum - minimum) * 0.5;
    bounds.center = minimum + bounds.halfExtent;
    bounds.radius = sqrt(dot(bounds.halfExtent, bounds.halfExtent));
    return bounds;
}

[numthreads(GROUP_SIZE_X, GROUP_SIZE_Y, 1)]
void mainCS(uint3 groupId : SV_GroupID, uint3 threadId : SV_GroupThreadID)
{
    uint clusterIndex = groupId.x * (GROUP_SIZE_X * GROUP_SIZE_Y)
        + threadId.y * GROUP_SIZE_X + threadId.x;
    uint clusterBase = clusterIndex * CLUSTER_RECORD_WORDS;
    uint rangeRecord = groupId.x >> 1;
    if (rangeRecord == 0)
    {
        clusteredLightIds[clusterBase] = 0;
        return;
    }

    uint2 packedRanges = (groupId.x & 1u) != 0
        ? cb_arrRanges[rangeRecord].zw
        : cb_arrRanges[rangeRecord].xy;
    uint2 sphereRange = uint2(
        ExtractByte(packedRanges.x, 0), ExtractByte(packedRanges.y, 0));
    uint2 ambientRange = uint2(
        ExtractByte(packedRanges.x, 1), ExtractByte(packedRanges.y, 1));
    uint2 coneRange = uint2(
        ExtractByte(packedRanges.x, 2), ExtractByte(packedRanges.y, 2));
    uint2 frustumRange = uint2(
        ExtractByte(packedRanges.x, 3), ExtractByte(packedRanges.y, 3));

    ClusterBounds bounds = BuildClusterBounds(groupId.x, threadId.xy);
    uint masks[MASK_WORDS] = {0, 0, 0, 0, 0, 0, 0, 0};
    uint activeMasks = 0;

    for (uint light = sphereRange.x; light < sphereRange.y; ++light)
    {
        if (SphereIntersectsCluster(cb_arrCullData[light], bounds))
            AddMaskBit(masks, light);
    }
    FlushMasks(masks, clusterBase, 1, 0, activeMasks);

    for (uint light = ambientRange.x; light < ambientRange.y; ++light)
    {
        if (SphereIntersectsCluster(
                cb_arrCullData[cb_cluster.uAmbient + light], bounds))
            AddMaskBit(masks, light);
    }
    FlushMasks(masks, clusterBase, 9, 8, activeMasks);

    for (uint light = coneRange.x; light < coneRange.y; ++light)
    {
        uint recordIndex = cb_cluster.uAmbient_Point + light * 4u;
        if (ConeIntersectsCluster(recordIndex, bounds))
            AddMaskBit(masks, light);
    }
    FlushMasks(masks, clusterBase, 17, 16, activeMasks);

    for (uint light = frustumRange.x; light < frustumRange.y; ++light)
    {
        uint recordIndex = cb_cluster.uAmbient_Point_Spot + light * 4u;
        if (FrustumIntersectsCluster(recordIndex, bounds))
            AddMaskBit(masks, light);
    }
    FlushMasks(masks, clusterBase, 25, 24, activeMasks);
    clusteredLightIds[clusterBase] = activeMasks;
}
