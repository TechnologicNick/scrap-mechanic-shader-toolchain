#ifndef MAIN_PART_PAINT_PALETTE_ABI_HLSL
#define MAIN_PART_PAINT_PALETTE_ABI_HLSL

cbuffer CB_PAINT_PALETTE
{
  uint4 cb_arrPaintPalette[10] : packoffset(c0);
}

#endif // MAIN_PART_PAINT_PALETTE_ABI_HLSL
