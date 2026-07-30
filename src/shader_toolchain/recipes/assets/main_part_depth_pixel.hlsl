#ifndef MAIN_PART_DEPTH_PIXEL_HLSL
#define MAIN_PART_DEPTH_PIXEL_HLSL

#if defined(MAIN_PART_DEPTH_POINT_ASG_PHASE) \
    || defined(MAIN_PART_DEPTH_LINEAR_ASG_PHASE) \
    || defined(MAIN_PART_DEPTH_FLOW_ASG_PHASE)
#include "main_part_alpha_cutout.hlsl"
#endif

#if defined(MAIN_PART_DEPTH_DISSOLVE_2D_PHASE)
#include "main_part_dissolve_cutout.hlsl"
#endif

#if defined(MAIN_PART_DEPTH_POINT_ASG_PHASE)
void ApplyMainPartDepthPointAsg(float2 uv)
{
  ApplyMainPartPointAsgCutout(uv);
}
#endif

#if defined(MAIN_PART_DEPTH_LINEAR_ASG_PHASE)
void ApplyMainPartDepthLinearAsg(float2 uv)
{
  ApplyMainPartLinearAsgCutout(uv);
}
#endif

#if defined(MAIN_PART_DEPTH_FLOW_ASG_PHASE)
void ApplyMainPartDepthFlowAsg(float2 uv)
{
  ApplyMainPartFlowAsgCutout(uv);
}
#endif

#if defined(MAIN_PART_DEPTH_POINT_DIFFUSE_PHASE)
void ApplyMainPartDepthPointDiffuse(float2 uv)
{
  if (tDif.SampleBias(PointWrapWrap_s, uv, cb_fMipBias).w < 0.5)
    discard;
}
#endif

#if defined(MAIN_PART_DEPTH_ARRAY_ASG_PHASE)
void ApplyMainPartDepthArrayAsg(float2 uv)
{
  float3 arrayUv = float3(vTextureTiling.y * uv, vTextureArrayIndices.y);
  if (taAsg.SampleBias(PointWrapWrap_s, arrayUv, cb_fMipBias).x < 0.5)
    discard;
}
#endif

#if defined(MAIN_PART_DEPTH_LASER_MASK_PHASE)
void ApplyMainPartDepthLaserMask(float2 uv)
{
  if (tLaserMask.Sample(LinearWrapWrap_s, uv).x < 0.100000001)
    discard;
}
#endif

#if defined(MAIN_PART_DEPTH_DISSOLVE_3D_PHASE)
void ApplyMainPartDepthDissolve3D(float cutoffOffset)
{
  float cutoff = tCutoff.Sample(
      LinearWrapWrap_s, cb_dissolve.vScrollSpeed.xyz * cb_fTime).x;
  float loopPosition = frac(
      cb_fTime * cb_dissolve.fLoopSpeed + cutoffOffset);
  loopPosition = loopPosition * cb_dissolve.fLoopLength
      - cb_dissolve.fLoopOffset;
  if (abs(loopPosition - cutoff) >= cb_dissolve.fLength)
    discard;
}
#endif

#endif
