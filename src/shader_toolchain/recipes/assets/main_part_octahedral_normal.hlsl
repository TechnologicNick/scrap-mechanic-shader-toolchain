// Shared view-normal encoding for two-channel part G-buffers.

float2 EncodeMainPartSurfaceNormal(float3 normalView)
{
  float3 swizzled = normalView.zxy;
  swizzled *= rsqrt(dot(swizzled, swizzled));
  float l1Norm = abs(swizzled.y) + abs(swizzled.z);
  l1Norm += abs(swizzled.x);
  swizzled /= l1Norm;

  float2 folded = 1.0 - abs(swizzled.zy);
  float3 nonNegative = swizzled >= 0.0;
  float2 foldSign = nonNegative.yz ? 1.0 : -1.0;
  folded *= foldSign;
  float2 octahedral = nonNegative.x ? swizzled.yz : folded;
  return octahedral * 0.5 + 0.5;
}
