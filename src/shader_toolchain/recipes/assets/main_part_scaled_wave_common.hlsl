// Shared scale-aware wave deformation used by explicit-LTW vertex families.

float3 MainPartApplyScaledWave(
    float3 basePosition,
    float3 baseNormalEncoded,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2)
{
  float timePhase = cb_wave.fSpeed * cb_fTime;
  float3 phase = float3(13.5, 10.0, 7.0) * timePhase;
  const float3 diagonal = float3(
      0.577350259, 0.577350259, 0.577350259);
  float3 transformedDiagonal = float3(
      dot(localToWorldRow0.xyz, diagonal),
      dot(localToWorldRow1.xyz, diagonal),
      dot(localToWorldRow2.xyz, diagonal));
  float waveScale = sqrt(dot(transformedDiagonal, transformedDiagonal));
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
