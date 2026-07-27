#include "include/reflection_info_abi.hlsl"

struct Bounds
{
    float3 vMin;
    float _padding0;
    float3 vMax;
    float _padding1;
};

struct ReflectionProps
{
    float3 vPosition;
    float fSlotIndex;
    float3 vExtents;
    float fParallax;
    float fBlend;
    float fGiInfinit;
    float fGiEnable;
    float fMarginRcp;
    float3 vMin;
    float fMinDistance;
    float3 vMax;
    float fMargin;
    float3 vOrignalPosition;
    float fIsFallback;
    float fGpuEnable;
    float3 vGpuExtents;
    float3 vGpuPosition;
    float fGpuMargin;
    float3 vGpuMin;
    float fGpuMarginRcp;
    float3 vGpuMax;
    float _padding;
};

StructuredBuffer<Bounds> sbBounds : register(t0);
RWStructuredBuffer<ReflectionProps> sbProps : register(u0);

[numthreads(128, 1, 1)]
void mainCS(uint3 dispatchThreadId : SV_DispatchThreadID)
{
    uint probeIndex = dispatchThreadId.x;
    ReflectionProps source = cb_reflections.vecProbes[probeIndex];
    ReflectionProps output = source;

    if (source.fSlotIndex >= 3.0)
    {
        Bounds bounds = sbBounds[(uint)source.fSlotIndex];
        float3 boundsCenter = (bounds.vMin + bounds.vMax) * 0.5;
        float3 boundsExtents = abs(bounds.vMax - bounds.vMin) * 0.5;
        float largestBoundsExtent = max(
            boundsExtents.x, max(boundsExtents.y, boundsExtents.z)
        );
        float smallestBoundsExtent = min(
            boundsExtents.x, min(boundsExtents.y, boundsExtents.z)
        );

        float3 probeExtent = abs(source.vExtents);
        float3 probeMin = source.vPosition - probeExtent;
        float3 probeMax = source.vPosition + probeExtent;
        float3 clippedMin = max(probeMin, bounds.vMin);
        float3 clippedMax = min(probeMax, bounds.vMax);
        float3 clippedExtents = max(
            2.0, abs(clippedMax - clippedMin) * 0.5
        );

        output.vPosition = (clippedMin + clippedMax) * 0.5;
        output.vExtents = clippedExtents;
        output.fParallax = largestBoundsExtent < 32.0
            && min(clippedExtents.x, min(clippedExtents.y, clippedExtents.z)) < 32.0;
        output.fGiInfinit = max(
            source.vExtents.x, max(source.vExtents.y, source.vExtents.z)
        ) >= 64.0;
        output.fGiEnable = smallestBoundsExtent >= 2.0;
        output.vMin = probeMin;
        output.vMax = probeMax;

        output.fGpuEnable = smallestBoundsExtent >= 1.0;
        output.vGpuExtents = boundsExtents;
        output.vGpuPosition = boundsCenter;
        output.fGpuMargin = largestBoundsExtent * 0.125;
        output.vGpuMin = bounds.vMin;
        output.fGpuMarginRcp = rcp(max(0.001, output.fGpuMargin));
        output.vGpuMax = bounds.vMax;
    }
    else
    {
        output.fGpuEnable = 1.0;
    }

    sbProps[probeIndex] = output;
}
