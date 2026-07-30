#ifndef MAIN_PART_PLANAR_WORLD_VERTEX_HLSL
#define MAIN_PART_PLANAR_WORLD_VERTEX_HLSL

// Construct a stable surface-aligned planar basis in world space.  This phase
// only replaces UV0; geometry and the laser-mask source remain independent.
float2 EvaluateMainPartPlanarWorldUv(
    float3 worldPosition, float3 surfaceNormal)
{
  float3 normal = surfaceNormal * rsqrt(dot(surfaceNormal, surfaceNormal));
  float3 reference = abs(normal.z) < 0.999
      ? float3(0.0, 0.0, 1.0) : float3(0.0, 1.0, 0.0);
  float3 tangent = cross(reference, normal);
  tangent *= rsqrt(dot(tangent, tangent));
  float3 bitangent = cross(normal, tangent);
  return cb_planarWorldSpace.vScale
      * float2(dot(worldPosition, tangent), dot(worldPosition, bitangent));
}

#endif // MAIN_PART_PLANAR_WORLD_VERTEX_HLSL
