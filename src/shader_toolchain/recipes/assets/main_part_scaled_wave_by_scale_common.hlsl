// Scale-aware wave deformation when the caller already reconstructed scale.

float3 MainPartApplyScaledWaveWithScale(
    float3 basePosition,
    float3 baseNormalEncoded,
    float waveScale)
{
  float timePhase = cb_wave.fSpeed * cb_fTime;
  float3 phase = float3(13.5, 10.0, 7.0) * timePhase;
  phase += basePosition * waveScale * float3(63.0, 51.0, 124.0);

  float3 oscillation = float3(sin(phase.x), cos(phase.y), sin(phase.z));
  oscillation *= waveScale;
  float displacement = oscillation.x * 0.125;
  displacement = mad(oscillation.y, 0.0920000002, displacement);
  displacement = mad(oscillation.z, 0.103, displacement);
  displacement *= cb_wave.fStrength;

  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  return basePosition + baseNormal * displacement;
}
