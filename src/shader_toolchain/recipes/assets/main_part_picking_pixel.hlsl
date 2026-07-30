#ifndef MAIN_PART_PICKING_PIXEL_HLSL
#define MAIN_PART_PICKING_PIXEL_HLSL

#include "main_part_alpha_cutout.hlsl"

#if defined(MAIN_PART_PICKING_POINT_PHASE)
void ApplyMainPartPickingPointCutout(float2 uv)
{
  ApplyMainPartPointAsgCutout(uv);
}
#endif

#if defined(MAIN_PART_PICKING_LINEAR_PHASE)
void ApplyMainPartPickingLinearCutout(float2 uv)
{
  ApplyMainPartLinearAsgCutout(uv);
}
#endif

#if defined(MAIN_PART_PICKING_FLOW_PHASE)
void ApplyMainPartPickingFlowCutout(float2 uv)
{
  ApplyMainPartFlowAsgCutout(uv);
}
#endif

void WriteMainPartPickingColor(
    float4 pickingColor, out float4 colorTarget)
{
  colorTarget = pickingColor;
}

#endif
