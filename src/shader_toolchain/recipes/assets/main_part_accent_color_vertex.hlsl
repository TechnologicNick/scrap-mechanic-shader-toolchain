#ifndef MAIN_PART_ACCENT_COLOR_VERTEX_HLSL
#define MAIN_PART_ACCENT_COLOR_VERTEX_HLSL

// INSTANCE_DATA0.y selects both a palette entry and how many packed palette
// channels contribute to the accent mask.
uint EvaluateMainPartAccentColor(uint packedInstanceY)
{
  uint mode = (packedInstanceY >> 10u) & 3u;
  uint paletteIndex = (packedInstanceY >> 12u) & 15u;
  uint4 paint = cb_arrPaintPalette[paletteIndex];
  if (mode == 0u)
    return paint.x | paint.y | paint.z;
  if (mode == 1u)
    return paint.y | paint.z;
  if (mode == 2u)
    return paint.z;
  return paint.w;
}

#endif // MAIN_PART_ACCENT_COLOR_VERTEX_HLSL
