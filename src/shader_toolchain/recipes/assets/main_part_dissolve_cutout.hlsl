#ifndef MAIN_PART_DISSOLVE_CUTOUT_HLSL
#define MAIN_PART_DISSOLVE_CUTOUT_HLSL

struct MainPartSurfaceDissolveBand
{
  float distance;
  float fade;
};

MainPartSurfaceDissolveBand EvaluateMainPartSurfaceDissolveBand(
    float2 uv, float cutoffOffset)
{
  float2 cutoffUv = uv * cb_dissolve.fScale
      + cb_dissolve.vScrollSpeed.xy * cb_fTime;
  float4 cutoffSamples = tCutoff.Gather(LinearWrapWrap_s, cutoffUv);
  float2 pairMaximum = max(cutoffSamples.xz, cutoffSamples.yw);
  float gatherMaximum = max(pairMaximum.x, pairMaximum.y) - 0.125;
  float4 accepted = gatherMaximum < cutoffSamples ? 1.0 : 0.0;
  float acceptedCount = dot(accepted, 1.0);
  float acceptedMean = dot(accepted * cutoffSamples, 1.0)
      / acceptedCount;
  acceptedMean = acceptedCount != 0.0 ? acceptedMean : 0.0;

  float loopPosition = frac(
      cb_fTime * cb_dissolve.fLoopSpeed + cutoffOffset);
  loopPosition = loopPosition * cb_dissolve.fLoopLength
      - cb_dissolve.fLoopOffset;
  MainPartSurfaceDissolveBand result;
  result.distance = loopPosition - acceptedMean;
  result.fade = saturate(cb_dissolve.fRcpFade
      * (cb_dissolve.fLength - abs(result.distance)));
  result.fade = exp2(cb_dissolve.fFadePower * log2(result.fade));
  return result;
}

void ApplyMainPartSurfaceDissolveWindow(
    MainPartSurfaceDissolveBand band)
{
  if (abs(band.distance) >= cb_dissolve.fLength)
    discard;
}

#endif
