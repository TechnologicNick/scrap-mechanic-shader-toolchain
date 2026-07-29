// Projection-independent cascade and clustered SSS visibility composition.
// The caller supplies a surface reconstructed with the appropriate camera
// policy (perspective or orthographic).

#ifndef INDIRECT_LIGHT_CASCADE_COMPILED_COUNT
#define INDIRECT_LIGHT_CASCADE_COMPILED_COUNT 4
#endif

#if INDIRECT_LIGHT_CASCADE_COMPILED_COUNT > 1
float EvaluateIndirectLightCascadeVisibilityLayer(
    IndirectLightSurface surface,
    uint clusterIndex,
    bool clusterHasSubsurface,
    bool thinSurface,
    uint layerIndex)
{
  if (!clusterHasSubsurface)
    return 1.0;
  uint lightWord = sbVoxelLightIds[
      clusterIndex * 33u + 1u
      + cb_settings.arrSsLight[layerIndex].uWordIndex];
  if ((lightWord & cb_settings.arrSsLight[layerIndex].uBitIndex) == 0u)
    return 1.0;
  return TraceIndirectLightSubsurface(
      surface, cb_settings.arrSsLight[layerIndex].vPointView, thinSurface);
}
#endif

float4 EvaluateIndirectLightCascadeVisibilitySet(
    IndirectLightSurface surface,
    float2 unscaledUv,
    uint outputCount)
{
  float4 visibility = 1.0;
  if (outputCount == 0u)
    return visibility;

  float directionalFacing = dot(
      surface.normalView, cb_vDirectionalLightDirectionView);
  if (directionalFacing < 0.330000013)
    visibility.x = TraceIndirectLightCascade(surface, directionalFacing);

#if INDIRECT_LIGHT_CASCADE_COMPILED_COUNT > 1
  if (outputCount > 1u)
  {
    uint slice = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(
        surface.depth * cb_cluster.fRcpClusterRange
        + cb_cluster.fClusterNearBias));
    uint2 tile = (uint2)(cb_cluster.vVoxelDims.xy * unscaledUv);
    uint clusterIndex = slice * cb_cluster.uClusterSliceSize
        + tile.y * cb_cluster.uClusterWidth + tile.x;
    uint clusterMask = sbVoxelLightIds[clusterIndex * 33u];
    bool clusterHasSubsurface =
        (clusterMask & cb_settings.uSSMask) != 0u;
    bool thinSurface = any(surface.neighborProfiles == 2u);

    visibility.y = EvaluateIndirectLightCascadeVisibilityLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface, 1u);
    if (outputCount > 2u)
      visibility.z = EvaluateIndirectLightCascadeVisibilityLayer(
          surface, clusterIndex, clusterHasSubsurface, thinSurface, 2u);
    if (outputCount > 3u)
      visibility.w = EvaluateIndirectLightCascadeVisibilityLayer(
          surface, clusterIndex, clusterHasSubsurface, thinSurface, 3u);
  }
#endif

  return lerp(1.0, visibility, cb_settings.fInvSSGIKillSwitch);
}
