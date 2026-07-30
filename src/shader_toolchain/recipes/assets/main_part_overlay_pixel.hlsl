#ifndef MAIN_PART_OVERLAY_PIXEL_HLSL
#define MAIN_PART_OVERLAY_PIXEL_HLSL

#if defined(MAIN_PART_WIREFRAME_PHASE)
void WriteMainPartWireframe(out float4 colorTarget)
{
  colorTarget = float4(1.0, 1.0, 1.0, 0.25999999);
}
#endif

#if defined(MAIN_PART_EDITOR_OVERLAY_CLIPPED_PHASE)
void RejectMainPartEditorOverlayBehindPlane(
    float3 viewPosition, float4 planeViewPosition)
{
  if (viewPosition.z < planeViewPosition.z)
    discard;
}
#endif

#if defined(MAIN_PART_EDITOR_OVERLAY_PHASE) \
    || defined(MAIN_PART_EDITOR_OVERLAY_CLIPPED_PHASE)
void WriteMainPartEditorOverlay(float2 uv, out float4 colorTarget)
{
  colorTarget = float4(
      tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).xyz, 1.0);
}
#endif

#if defined(MAIN_PART_CONNECT_OVERLAY_PHASE)
void RejectMainPartConnectOverlayBehindDepth(float4 screenPosition)
{
  float2 depthUv = screenPosition.xy / (float2)cb_vuViewportSize;
  depthUv *= cb_vPrevRenderScale;
  float depth = tDepth.SampleLevel(LinearClampClamp_s, depthUv, 0).x;
  if (screenPosition.z < depth)
    discard;
}

void WriteMainPartConnectOverlay(
    float3 arrayUv, float4 vertexColor, out float4 colorTarget)
{
  float4 diffuse = taDif.SampleBias(
      LinearWrapWrap_s, arrayUv, cb_fMipBias);
  colorTarget.xyz = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  colorTarget.w = 1.0;
}
#endif

#endif
