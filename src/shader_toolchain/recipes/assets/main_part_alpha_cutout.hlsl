#ifndef MAIN_PART_ALPHA_CUTOUT_HLSL
#define MAIN_PART_ALPHA_CUTOUT_HLSL

#if defined(MAIN_PART_PICKING_POINT_PHASE) \
    || defined(MAIN_PART_DEPTH_POINT_ASG_PHASE)
void ApplyMainPartPointAsgCutout(float2 uv)
{
  if (tAsg.SampleBias(PointWrapWrap_s, uv, cb_fMipBias).x < 0.5)
    discard;
}
#endif

#if defined(MAIN_PART_PICKING_LINEAR_PHASE) \
    || defined(MAIN_PART_DEPTH_LINEAR_ASG_PHASE)
void ApplyMainPartLinearAsgCutout(float2 uv)
{
  if (tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).x < 0.5)
    discard;
}
#endif

#if defined(MAIN_PART_PICKING_FLOW_PHASE) \
    || defined(MAIN_PART_DEPTH_FLOW_ASG_PHASE)
void ApplyMainPartFlowAsgCutout(float2 uv)
{
  float2 phase = frac(float2(0.0, 0.5)
      + cb_flow_map.fFlowSpeed * cb_fTime);
  float2 flow = tFlowMap.Sample(LinearWrapWrap_s, uv).xy * 2.0 - 1.0;
  float2 firstUv = uv - flow * phase.x;
  float2 secondUv = uv - flow * phase.y;
  float blend = 1.0 - abs(1.0 - phase.y * 2.0);
  float firstAlpha = tAsg.SampleBias(
      LinearWrapWrap_s, firstUv, cb_fMipBias).x;
  float secondAlpha = tAsg.SampleBias(
      LinearWrapWrap_s, secondUv, cb_fMipBias).x;
  if (firstAlpha + blend * (secondAlpha - firstAlpha) < 0.5)
    discard;
}
#endif

#endif
