#ifndef MAIN_PART_UV_SCROLL_VERTEX_HLSL
#define MAIN_PART_UV_SCROLL_VERTEX_HLSL

// UV scrolling is a post-geometry phase.  Keeping it independent lets rigid,
// packed, and every morph-count family reuse the same implementation.
float2 EvaluateMainPartScrolledUv(float2 baseUv)
{
  return baseUv + frac(cb_uvScroll.vSpeed * cb_fTime);
}

#endif // MAIN_PART_UV_SCROLL_VERTEX_HLSL
