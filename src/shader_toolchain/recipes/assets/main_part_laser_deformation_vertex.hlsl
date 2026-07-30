#ifndef MAIN_PART_LASER_DEFORMATION_VERTEX_HLSL
#define MAIN_PART_LASER_DEFORMATION_VERTEX_HLSL

// Local-space procedural laser deformation.  Transform, morph, picking, and
// output-transfer policies deliberately live outside this helper.
struct MainPartLaserDeformation
{
  float3 position;
  float3 normalEncoded;
  float3 color;
  float offset;
};

float MainPartLaserHash(float2 cell)
{
  float phase = dot(cell, float2(127.1, 311.7));
  return frac(sin(phase) * 43758.5453);
}

float MainPartLaserNoise(float2 samplePoint)
{
  float2 cell = floor(samplePoint);
  float2 local = frac(samplePoint);
  float2 blend = local * local * (3.0 - 2.0 * local);
  float low = lerp(
      MainPartLaserHash(cell),
      MainPartLaserHash(cell + float2(1.0, 0.0)), blend.x);
  float high = lerp(
      MainPartLaserHash(cell + float2(0.0, 1.0)),
      MainPartLaserHash(cell + float2(1.0, 1.0)), blend.x);
  return lerp(low, high, blend.y) * 2.0 - 1.0;
}

MainPartLaserDeformation EvaluateMainPartLaserDeformation(
    float3 localPosition,
    float3 normalEncoded,
    float fadeCoordinate)
{
  MainPartLaserDeformation result;
  float3 localNormal = normalEncoded * 2.0 - 1.0;

  float waveNoise = MainPartLaserNoise(
      localPosition.xy * cb_laser_displacement.fWaveNoiseIntensity);
  float wavePhase = cb_fTime * cb_laser_displacement.fDisplacementSpeed
      + localPosition.y;
  float slicePhase = localPosition.y * cb_laser_displacement.fSliceSize
      - cb_fTime * cb_laser_displacement.fDisplacementSpeed;
  float sliceGate = sin(slicePhase) >= 0.5 ? 1.0 : 0.0;
  float waveOffset = sin(wavePhase) * waveNoise * sliceGate;

  float glitchNoise = MainPartLaserNoise(
      localPosition.xz
      + cb_fTime * cb_laser_displacement.fGlitchSpeed);
  float glitchOffset = sin(glitchNoise * 130.0) >= 0.8 ? 1.0 : 0.0;
  float directedSlice = sin(
      localPosition.y * cb_laser_displacement.fSliceSize
      + cb_fTime * cb_laser_displacement.fDisplacementSpeed) >= 0.5
      ? 1.0 : 0.0;

  float flickerA = sin(cb_fTime * -(
      cb_laser_displacement.fFlickerFrequencyValue
      + cb_laser_displacement.fFlickerFrequencyOffset)) >= 0.9
      ? 1.0 : 0.0;
  float flickerB = sin(
      cb_fTime * -cb_laser_displacement.fFlickerFrequencyValue) >= 0.5
      ? 1.0 : 0.0;
  float flicker = flickerA * flickerB;

  float strength = cb_laser_displacement.fDisplacementStrength;
  float3 displacement = localNormal * (waveOffset * strength);
  displacement += localNormal * (glitchOffset * strength);
  displacement += cb_laser_displacement.vSliceDirection
      * (directedSlice * strength);
  displacement *= flicker;

  float fade = saturate((
      cb_laser_displacement.fDisplacementFadeRange
      + fadeCoordinate
      - cb_laser_displacement.fDisplacementFadeValue)
      / cb_laser_displacement.fDisplacementFadeRange);
  displacement *= 1.0 - fade;

  result.position = localPosition + displacement;
  result.normalEncoded = normalEncoded;
  result.offset = (waveOffset + glitchOffset + directedSlice) * strength;
  result.color = cb_laser_displacement.vDisplacementColor.rgb
      * cb_laser_displacement.vDisplacementColor.a
      * (result.offset / max(0.01, strength));
  return result;
}

#endif // MAIN_PART_LASER_DEFORMATION_VERTEX_HLSL
