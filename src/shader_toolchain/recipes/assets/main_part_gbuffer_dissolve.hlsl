// Typed alpha-cutout dissolve frontend and opaque G-buffer composition.

struct MainPartDissolveGBuffer
{
  float4 albedo;
  float2 encodedNormal;
  float4 material;
};

struct MainPartDissolveBand
{
  float distance;
  float fade;
};

float4 SampleMainPartDissolveGBufferAsg(float2 uv)
{
  return tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
}

MainPartDissolveBand EvaluateMainPartDissolveBand(
    float2 uv, float cutoffOffset)
{
  float2 dissolveUv = uv * cb_dissolve.fScale
      + cb_dissolve.vScrollSpeed.xy * cb_fTime;
  float4 dissolveSamples = tCutoff.Gather(
      LinearWrapWrap_s, dissolveUv);
  float2 pairMaximum = max(
      dissolveSamples.xz, dissolveSamples.yw);
  float dissolveThreshold = max(
      pairMaximum.x, pairMaximum.y) - 0.125;
  float4 selectedSamples = dissolveSamples > dissolveThreshold;
  float selectedCount = dot(
      selectedSamples, float4(1.0, 1.0, 1.0, 1.0));
  float selectedMean = dot(
      selectedSamples * dissolveSamples,
      float4(1.0, 1.0, 1.0, 1.0));
  selectedMean /= selectedCount;
  selectedMean = selectedCount != 0.0 ? selectedMean : 0.0;

  float dissolvePhase = frac(
      cb_fTime * cb_dissolve.fLoopSpeed + cutoffOffset);
  dissolvePhase = dissolvePhase * cb_dissolve.fLoopLength
      - cb_dissolve.fLoopOffset;
  MainPartDissolveBand result;
  result.distance = dissolvePhase - selectedMean;

  result.fade = saturate(cb_dissolve.fRcpFade
      * (cb_dissolve.fLength - abs(result.distance)));
  result.fade = exp2(cb_dissolve.fFadePower * log2(result.fade));
  return result;
}

MainPartDissolveGBuffer EvaluateMainPartDissolveGBuffer(
    float2 uv, float3 normalView, float4 vertexColor,
    bool frontFace, float4 asg, float dissolveFade)
{
  MainPartDissolveGBuffer result;
  float3 surfaceNormal = frontFace ? normalView : -normalView;
  surfaceNormal *= rsqrt(dot(surfaceNormal, surfaceNormal));

  float4 diffuse = tDif.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias);
  float3 baseColor = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  float4 dissolveColor = cb_dissolve.vStartColor
      + dissolveFade * (
          cb_dissolve.vEndColor - cb_dissolve.vStartColor);

  result.albedo.xyz = dissolveColor.xyz
      + dissolveFade * (baseColor - dissolveColor.xyz);
  result.albedo.w = dissolveColor.w
      + dissolveFade * (asg.z * vertexColor.w - dissolveColor.w);
  result.encodedNormal = EncodeMainPartSurfaceNormal(surfaceNormal);
  result.material = float4(asg.w, asg.y, 0.0, 0.0);
  return result;
}

void WriteMainPartDissolveGBuffer(
    MainPartDissolveGBuffer surface,
    out float4 albedoTarget,
    out float2 normalTarget,
    out float4 materialTarget)
{
  albedoTarget = surface.albedo;
  normalTarget = surface.encodedNormal;
  materialTarget = surface.material;
}
