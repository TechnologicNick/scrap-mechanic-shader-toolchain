// Decode the component-lane picking identifier packed into INSTANCE_DATA0.y.

float4 MainPartDecodePickingColor(uint packedInstanceY)
{
  // Preserve the original component mask and bitwise reduction. In
  // particular, lane zero must not select the second component.
  int lowTenBits = (int)(packedInstanceY & 1023u);
  int upperEightBits = (int)((packedInstanceY >> 2u) & 255u);
  int lane = lowTenBits - (upperEightBits << 2);
  int negativeLane = -lane;
  bool3 laneLessThan = (uint3)lane < uint3(1u, 2u, 3u);
  int maskedNegativeLane = negativeLane & (laneLessThan.y ? -1 : 0);
  bool4 componentMask = bool4(
      laneLessThan.x,
      maskedNegativeLane != 0,
      laneLessThan.y ? false : (lane - 3) != 0,
      !laneLessThan.z);
  uint4 selected = componentMask ? cb_arrPickingId[upperEightBits] : 0u;
  uint2 reduced = selected.yw | selected.xz;
  uint pickingId = reduced.y | reduced.x;
  return float4(
      (pickingId >> 24u) & 255u,
      (pickingId >> 16u) & 255u,
      (pickingId >> 8u) & 255u,
      pickingId & 255u) * (1.0 / 255.0);
}
