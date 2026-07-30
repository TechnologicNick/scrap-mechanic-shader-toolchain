// Shared no-scale procedural wave used before rigid or pose deformation.

float3 MainPartApplyNoScaleWave(float3 basePosition, float3 normalEncoded)
{
  float timePhase = cb_wave.fSpeed * cb_fTime;
  float3 phase = basePosition * float3(15.75, 12.75, 31.0)
      + timePhase * float3(13.5, 10.0, 7.0);
  float3 oscillation = float3(sin(phase.x), cos(phase.y), sin(phase.z));
  float displacement = cb_wave.fStrength * (
      oscillation.x * 0.03125
      + oscillation.y * 0.023
      + oscillation.z * 0.02575);
  return (normalEncoded * 2.0 - 1.0) * displacement + basePosition;
}
