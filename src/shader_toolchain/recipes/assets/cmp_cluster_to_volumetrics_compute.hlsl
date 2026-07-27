cbuffer Cluster : register(b0)
{
    struct
    {
        uint voxelCount;
        uint clusterSliceSize;
        float clusterRange;
        float clusterNearBias;
        uint clusterWidth;
        uint clusterDepthLights;
        uint ambient;
        uint ambientPoint;
        uint ambientPointSpot;
        uint reflections;
        float clusterMaxFarReflections;
        float clusterMaxFarTotal;
        float3 reciprocalVoxelDimensions;
        float reciprocalClusterRange;
        float3 voxelDimensions;
        float clusterNear;
        float2 viewCorner;
        float2 shadowAtlasDimensions;
        float2 shadowAtlasPixelSize;
        float clusterMaxFarLights;
        float shadowAtlasAspect;
        uint screenSpaceMask;
        float3 _padding;
    } cluster : packoffset(c0);
}

StructuredBuffer<uint> voxelLightIds : register(t0);
RWStructuredBuffer<uint> volumetricIds : register(u0);

[numthreads(64, 1, 1)]
void mainCS(uint3 dispatchThreadId : SV_DispatchThreadID)
{
    uint sliceIndex = dispatchThreadId.x;
    if (sliceIndex >= cluster.clusterSliceSize)
        return;

    uint mergedLightMask = 0;
    uint mergedVoxelMasks[16] = {
        0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0
    };

    for (uint depth = 0; depth < cluster.clusterDepthLights; ++depth)
    {
        uint voxelIndex = depth * cluster.clusterSliceSize + sliceIndex;
        uint recordOffset = voxelIndex * 33;
        uint activeLights = (voxelLightIds[recordOffset] >> 8) & 0xffff;
        mergedLightMask |= activeLights;
        uint lightMaskOffset = recordOffset + 9;
        while (activeLights != 0)
        {
            uint light = firstbitlow(activeLights);
            activeLights ^= 1u << light;
            mergedVoxelMasks[light] |= voxelLightIds[lightMaskOffset + light];
        }
    }

    uint outputOffset = sliceIndex * 17;
    volumetricIds[outputOffset] = mergedLightMask;
    while (mergedLightMask != 0)
    {
        uint light = firstbitlow(mergedLightMask);
        mergedLightMask ^= 1u << light;
        volumetricIds[outputOffset + 1 + light] = mergedVoxelMasks[light];
    }
}
