// Synthesized semantic family: transparent_surface_water_tangent_map_dissolve_uv0_fog_cutoff
// Policy: quality=default, reflection=multi
#ifndef cmp
#define cmp -
#endif

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy0(
  )
{

}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy1(
  inout float4 smLocalFloat40, inout float4 smLocalFloat43, inout float4 smLocalFloat44, inout float4 smLocalFloat45)
{
  smLocalFloat45.xyz = - cb_vDirectionalLightDirectionView.xyz * smLocalFloat40.zzz + smLocalFloat43.xyz;
  smLocalFloat40.z = dot (smLocalFloat45.xyz, smLocalFloat45.xyz);
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy2(
  inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat44, inout float4 smLocalFloat45)
{
  smLocalFloat45.xyz = smLocalFloat45.xyz * smLocalFloat40.zzz;
  smLocalFloat40.z = dot (smLocalFloat45.xyz, smLocalFloat41.xyz);
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy3(
  inout float4 smLocalFloat41, inout float4 smLocalFloat42)
{
  smLocalFloat41.w = max (0.00999999978, smLocalFloat41.w);
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy4(
  inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat42)
{
  smLocalFloat41.w = log2 (smLocalFloat41.w);
  smLocalFloat40.x = smLocalFloat41.w * smLocalFloat40.x;
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy5(
  inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat42, inout float4 smLocalFloat43)
{
  smLocalFloat41.w = 0.995000005 * smLocalFloat40.w;
  smLocalFloat42.w = - smLocalFloat40.w * 0.995000005 + 1;
  smLocalFloat40.z = abs (smLocalFloat40.z) * abs (smLocalFloat40.z) + - smLocalFloat41.w;
  smLocalFloat41.w = 1 / smLocalFloat42.w;
  smLocalFloat40.z = saturate (smLocalFloat41.w * smLocalFloat40.z);
  smLocalFloat41.w = smLocalFloat40.z * - 2 + 3;
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy6(
  inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat42)
{
  smLocalFloat40.z = smLocalFloat41.w * smLocalFloat40.z;
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy7(
  inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat42, inout float4 smLocalFloat43, inout float4 smLocalFloat44, inout float4 smLocalFloat45)
{

}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffClusteredLightingAndSpotCookieAndFrameComposition0(
  float3 smin_view_position0, float3 smin_screen_uv0, float4 smin_fog_color0, inout float4 smout_sv_target0, inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat42, inout float4 smLocalFloat43, inout float4 smLocalFloat44, inout float4 smLocalFloat45, inout float4 smLocalFloat46, inout float4 smLocalFloat47, inout float4 smLocalFloat48, inout float4 smLocalFloat49, inout float4 smLocalFloat410, inout float4 smLocalFloat411, inout float4 smLocalFloat412, inout float4 smLocalFloat413, inout float4 smLocalFloat414, inout float4 smLocalFloat415, inout float4 smLocalFloat416, inout float4 smLocalFloat417)
{
  if (smLocalFloat40.w != 0) {
    smLocalFloat40.w = cb_vInverseCameraRange.x * - smin_view_position0.z;
    smLocalFloat41.w = dot (- smLocalFloat43.xyz, smLocalFloat41.xyz);
    smLocalFloat41.w = smLocalFloat41.w + smLocalFloat41.w;
    smLocalFloat43.xyz = smLocalFloat41.xyz * - smLocalFloat41.www + - smLocalFloat43.xyz;
    smLocalFloat44.yzw = viewToWorld._m01_m11_m21 * smLocalFloat43.yyy;
    smLocalFloat43.xyw = viewToWorld._m00_m10_m20 * smLocalFloat43.xxx + smLocalFloat44.yzw;
    smLocalFloat43.xyz = viewToWorld._m02_m12_m22 * smLocalFloat43.zzz + smLocalFloat43.xyw;
    smLocalFloat41.w = log2 (abs (smLocalFloat44.x));
    smLocalFloat41.w = 0.75 * smLocalFloat41.w;
    smLocalFloat41.w = exp2 (smLocalFloat41.w);
    smLocalFloat44.xyz = viewToWorld._m01_m11_m21 * smin_view_position0.yyy;
    smLocalFloat44.xyz = viewToWorld._m00_m10_m20 * smin_view_position0.xxx + smLocalFloat44.xyz;
    smLocalFloat44.xyz = viewToWorld._m02_m12_m22 * smin_view_position0.zzz + smLocalFloat44.xyz;
    smLocalFloat44.xyz = viewToWorld._m03_m13_m23 + smLocalFloat44.xyz;
    smLocalFloat45.xyz = ddx_coarse (smLocalFloat44.xyz);
    smLocalFloat45.xyz = smLocalFloat45.xyz + smLocalFloat44.xyz;
    smLocalFloat46.xyz = ddy_coarse (smLocalFloat44.xyz);
    smLocalFloat45.xyz = smLocalFloat46.xyz + smLocalFloat45.xyz;
    smLocalFloat40.w = saturate (6.66666651 * smLocalFloat40.w);
    smLocalFloat40.w = 1 + - smLocalFloat40.w;
    smLocalFloat46.xy = cb_vInvRenderScale.xy * smin_screen_uv0.xy;
    smLocalFloat42.w = - smin_view_position0.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    smLocalFloat42.w = rsqrt (smLocalFloat42.w);
    smLocalFloat42.w = 1 / smLocalFloat42.w;
    smLocalFloat42.w = cb_cluster.vVoxelDims.z * smLocalFloat42.w;
    smLocalFloat42.w = floor (smLocalFloat42.w);
    smLocalFloat42.w = (uint) smLocalFloat42.w;
    smLocalFloat46.xy = cb_cluster.vVoxelDims.xy * smLocalFloat46.xy;
    smLocalFloat46.xy = (uint2) smLocalFloat46.xy;
    smLocalFloat43.w = mad ((int) smLocalFloat46.y, asint (cb_cluster.uClusterWidth), (int) smLocalFloat46.x);
    smLocalFloat42.w = mad ((int) smLocalFloat42.w, asint (cb_cluster.uClusterSliceSize), (int) smLocalFloat43.w);
    smLocalFloat43.w = (int) smLocalFloat42.w * 33;
    smLocalFloat43.w = sbVoxelLightIds [smLocalFloat43.w].x;
    smLocalFloat42.w = mad ((int) smLocalFloat42.w, 33, 1);
    smLocalFloat46.xyzw = (int4) smLocalFloat43.wwww & int4 (255, 0xff00, 0xff0000, 0xff000000);
    smLocalFloat47.xyz = cb_vDirectionalLightColor.xyz;
    smLocalFloat43.w = smLocalFloat46.x;
    while (true) {
      if (smLocalFloat43.w == 0) break;
      smLocalFloat44.w = firstbitlow ((uint) smLocalFloat43.w);
      smLocalFloat45.w = (int) smLocalFloat42.w + (int) smLocalFloat44.w;
      smLocalFloat47.w = 1 << (int) smLocalFloat44.w;
      smLocalFloat43.w = (int) smLocalFloat43.w ^ (int) smLocalFloat47.w;
      smLocalFloat45.w = sbVoxelLightIds [smLocalFloat45.w].x;
      smLocalFloat44.w = (uint) smLocalFloat44.w << 5;
      smLocalFloat48.xyz = smLocalFloat47.xyz;
      smLocalFloat47.w = smLocalFloat45.w;
      while (true) {
        if (smLocalFloat47.w == 0) break;
        smLocalFloat48.w = firstbitlow ((uint) smLocalFloat47.w);
        smLocalFloat49.x = (int) smLocalFloat44.w + (int) smLocalFloat48.w;
        smLocalFloat48.w = 1 << (int) smLocalFloat48.w;
        smLocalFloat47.w = (int) smLocalFloat47.w ^ (int) smLocalFloat48.w;
        smLocalFloat48.w = (uint) smLocalFloat49.x << 1;
        smLocalFloat49.xyz = cb_arrAmbient [smLocalFloat48.w].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat49.w = dot (smLocalFloat49.xyz, smLocalFloat49.xyz);
        smLocalFloat410.x = sqrt (smLocalFloat49.w);
        smLocalFloat410.x = saturate (cb_arrAmbient [smLocalFloat48.w].fRcpRadius * smLocalFloat410.x);
        smLocalFloat49.w = rsqrt (smLocalFloat49.w);
        smLocalFloat49.xyz = smLocalFloat49.xyz * smLocalFloat49.www;
        smLocalFloat49.x = dot (smLocalFloat49.xyz, smLocalFloat41.xyz);
        smLocalFloat49.x = abs (smLocalFloat49.x) * 0.5 + 0.5;
        smLocalFloat49.y = smLocalFloat410.x * smLocalFloat410.x;
        smLocalFloat49.y = - smLocalFloat49.y * smLocalFloat49.y + 1;
        smLocalFloat49.y = cb_arrAmbient [smLocalFloat48.w].fIntensity * smLocalFloat49.y;
        smLocalFloat49.y = smLocalFloat49.y * smLocalFloat40.w;
        smLocalFloat49.x = smLocalFloat49.y * smLocalFloat49.x;
        smLocalFloat49.xyz = cb_arrAmbient [smLocalFloat48.w].vColor.xyz * smLocalFloat49.xxx;
        smLocalFloat48.xyz = max (smLocalFloat49.xyz, smLocalFloat48.xyz);
      }
      smLocalFloat47.xyz = smLocalFloat48.xyz;
    }
    smLocalFloat48.xyz = smLocalFloat47.xyz;
    smLocalFloat49.xyz = float3 (0, 0, 0);
    smLocalFloat40.w = smLocalFloat46.y;
    while (true) {
      if (smLocalFloat40.w == 0) break;
      smLocalFloat43.w = firstbitlow ((uint) smLocalFloat40.w);
      smLocalFloat44.w = (int) smLocalFloat42.w + (int) smLocalFloat43.w;
      smLocalFloat45.w = 1 << (int) smLocalFloat43.w;
      smLocalFloat40.w = (int) smLocalFloat40.w ^ (int) smLocalFloat45.w;
      smLocalFloat44.w = sbVoxelLightIds [smLocalFloat44.w].x;
      smLocalFloat43.w = (uint) smLocalFloat43.w << 5;
      smLocalFloat410.xyz = smLocalFloat48.xyz;
      smLocalFloat411.xyz = smLocalFloat49.xyz;
      smLocalFloat45.w = smLocalFloat44.w;
      while (true) {
        if (smLocalFloat45.w == 0) break;
        smLocalFloat46.x = firstbitlow ((uint) smLocalFloat45.w);
        smLocalFloat47.w = (int) smLocalFloat43.w + (int) smLocalFloat46.x;
        smLocalFloat46.x = 1 << (int) smLocalFloat46.x;
        smLocalFloat45.w = (int) smLocalFloat45.w ^ (int) smLocalFloat46.x;
        smLocalFloat46.x = (uint) smLocalFloat47.w << 1;
        smLocalFloat46.x = (int) smLocalFloat46.x + - 512;
        smLocalFloat412.xyz = cb_arrPoint [smLocalFloat46.x].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat47.w = dot (smLocalFloat412.xyz, smLocalFloat412.xyz);
        smLocalFloat47.w = sqrt (smLocalFloat47.w);
        smLocalFloat48.w = saturate (cb_arrPoint [smLocalFloat46.x].fRcpRadius * smLocalFloat47.w);
        smLocalFloat47.w = max (0.00100000005, smLocalFloat47.w);
        smLocalFloat412.xyz = smLocalFloat412.xyz / smLocalFloat47.www;
        smLocalFloat47.w = dot (smLocalFloat412.xyz, smLocalFloat41.xyz);
        smLocalFloat47.w = abs (smLocalFloat47.w) * 0.75 + 0.25;
        smLocalFloat48.w = max (0.00999999978, smLocalFloat48.w);
        smLocalFloat48.w = log2 (smLocalFloat48.w);
        smLocalFloat48.w = cb_arrPoint [smLocalFloat46.x].fFalloffFactor * smLocalFloat48.w;
        smLocalFloat48.w = exp2 (smLocalFloat48.w);
        smLocalFloat48.w = 1 + - smLocalFloat48.w;
        smLocalFloat48.w = cb_arrPoint [smLocalFloat46.x].fIntensity * smLocalFloat48.w;
        smLocalFloat48.w = min (cb_arrPoint [smLocalFloat46.x].fMaxIntensity, smLocalFloat48.w);
        smLocalFloat49.w = asuint (cb_arrPoint [smLocalFloat46.x].uColor) >> 24;
        smLocalFloat49.w = (uint) smLocalFloat49.w;
        smLocalFloat412.x = smLocalFloat49.w * smLocalFloat47.w;
        if (8 == 0) smLocalFloat413.x = 0;
        else if (8 + 16 < 32) {
          smLocalFloat413.x = (uint) cb_arrPoint [smLocalFloat46.x].uColor << (32 - (8 + 16));
          smLocalFloat413.x = (uint) smLocalFloat413.x >> (32 - 8);
        }
        else smLocalFloat413.x = (uint) cb_arrPoint [smLocalFloat46.x].uColor >> 16;
        if (8 == 0) smLocalFloat413.y = 0;
        else if (8 + 8 < 32) {
          smLocalFloat413.y = (uint) cb_arrPoint [smLocalFloat46.x].uColor << (32 - (8 + 8));
          smLocalFloat413.y = (uint) smLocalFloat413.y >> (32 - 8);
        }
        else smLocalFloat413.y = (uint) cb_arrPoint [smLocalFloat46.x].uColor >> 8;
        smLocalFloat413.xy = (uint2) smLocalFloat413.xy;
        smLocalFloat412.yz = smLocalFloat413.xy * smLocalFloat47.ww;
        smLocalFloat412.xyz = smLocalFloat412.xyz * smLocalFloat48.www;
        smLocalFloat412.xyz = float3 (0.00392156886, 0.00392156886, 0.00392156886) * smLocalFloat412.xyz;
        smLocalFloat46.x = 1 & asint (cb_arrPoint [smLocalFloat46.x].uColor);
        smLocalFloat413.xyz = max (float3 (0, 0, 0), smLocalFloat412.xyz);
        smLocalFloat413.xyz = smLocalFloat413.xyz + smLocalFloat411.xyz;
        smLocalFloat412.xyz = max (smLocalFloat412.xyz, smLocalFloat410.xyz);
        smLocalFloat410.xyz = smLocalFloat46.xxx ? smLocalFloat410.xyz : smLocalFloat412.xyz;
        smLocalFloat411.xyz = smLocalFloat46.xxx ? smLocalFloat413.xyz : smLocalFloat411.xyz;
      }
      smLocalFloat48.xyz = smLocalFloat410.xyz;
      smLocalFloat49.xyz = smLocalFloat411.xyz;
    }
    smLocalFloat47.xyz = smLocalFloat48.xyz;
    smLocalFloat410.xyz = smLocalFloat49.xyz;
    smLocalFloat40.w = smLocalFloat46.z;
    while (true) {
      if (smLocalFloat40.w == 0) break;
      smLocalFloat43.w = firstbitlow ((uint) smLocalFloat40.w);
      smLocalFloat44.w = (int) smLocalFloat42.w + (int) smLocalFloat43.w;
      smLocalFloat45.w = 1 << (int) smLocalFloat43.w;
      smLocalFloat40.w = (int) smLocalFloat40.w ^ (int) smLocalFloat45.w;
      smLocalFloat44.w = sbVoxelLightIds [smLocalFloat44.w].x;
      smLocalFloat43.w = (uint) smLocalFloat43.w << 5;
      smLocalFloat411.xyz = smLocalFloat47.xyz;
      smLocalFloat412.xyz = smLocalFloat410.xyz;
      smLocalFloat45.w = smLocalFloat44.w;
      while (true) {
        if (smLocalFloat45.w == 0) break;
        smLocalFloat46.x = firstbitlow ((uint) smLocalFloat45.w);
        smLocalFloat46.y = (int) smLocalFloat43.w + (int) smLocalFloat46.x;
        smLocalFloat46.x = 1 << (int) smLocalFloat46.x;
        smLocalFloat45.w = (int) smLocalFloat45.w ^ (int) smLocalFloat46.x;
        smLocalFloat46.x = mad ((int) smLocalFloat46.y, 9, - 4608);
        smLocalFloat413.xyz = cb_arrSpot [smLocalFloat46.x].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat46.y = dot (smLocalFloat413.xyz, smLocalFloat413.xyz);
        smLocalFloat46.y = sqrt (smLocalFloat46.y);
        smLocalFloat47.w = cb_arrSpot [smLocalFloat46.x].fRcpRange * smLocalFloat46.y;
        smLocalFloat48.w = cmp (1 >= smLocalFloat47.w);
        if (smLocalFloat48.w != 0) {
          smLocalFloat46.y = max (0.00100000005, smLocalFloat46.y);
          smLocalFloat413.xyz = smLocalFloat413.xyz / smLocalFloat46.yyy;
          smLocalFloat46.y = dot (- smLocalFloat413.xyz, cb_arrSpot [smLocalFloat46.x].vForward.xyz);
          smLocalFloat48.w = cmp (0 < smLocalFloat46.y);
          if (smLocalFloat48.w != 0) {
            smLocalFloat48.w = dot (smLocalFloat413.xyz, smLocalFloat41.xyz);
            smLocalFloat46.y = saturate (smLocalFloat46.y * cb_arrSpot [smLocalFloat46.x].fCutoffScale + cb_arrSpot [smLocalFloat46.x].fCutoffOffset);
            smLocalFloat413.xy = int2 (240, 1) & asint (cb_arrSpot [smLocalFloat46.x].uColor);
            if (smLocalFloat413.x != 0) {
              smLocalFloat413.xzw = cb_arrSpot [smLocalFloat46.x].xClip._m01_m11_m31 * smLocalFloat44.yyy;
              smLocalFloat413.xzw = cb_arrSpot [smLocalFloat46.x].xClip._m00_m10_m30 * smLocalFloat44.xxx + smLocalFloat413.xzw;
              smLocalFloat413.xzw = cb_arrSpot [smLocalFloat46.x].xClip._m02_m12_m32 * smLocalFloat44.zzz + smLocalFloat413.xzw;
              smLocalFloat413.xzw = cb_arrSpot [smLocalFloat46.x].xClip._m03_m13_m33 + smLocalFloat413.xzw;
              smLocalFloat413.xz = smLocalFloat413.xz / smLocalFloat413.ww;
              smLocalFloat414.xy = smLocalFloat413.xz * float2 (0.5, 0.5) + float2 (0.5, 0.5);
              smLocalFloat413.xzw = cb_arrSpot [smLocalFloat46.x].xClip._m01_m11_m31 * smLocalFloat45.yyy;
              smLocalFloat413.xzw = cb_arrSpot [smLocalFloat46.x].xClip._m00_m10_m30 * smLocalFloat45.xxx + smLocalFloat413.xzw;
              smLocalFloat413.xzw = cb_arrSpot [smLocalFloat46.x].xClip._m02_m12_m32 * smLocalFloat45.zzz + smLocalFloat413.xzw;
              smLocalFloat413.xzw = cb_arrSpot [smLocalFloat46.x].xClip._m03_m13_m33 + smLocalFloat413.xzw;
              smLocalFloat413.xz = smLocalFloat413.xz / smLocalFloat413.ww;
              smLocalFloat413.xz = smLocalFloat413.xz * float2 (0.5, 0.5) + float2 (0.5, 0.5);
              smLocalFloat413.xz = smLocalFloat414.xy + - smLocalFloat413.xz;
              if (4 == 0) smLocalFloat49.w = 0;
              else if (4 + 4 < 32) {
                smLocalFloat49.w = (uint) cb_arrSpot [smLocalFloat46.x].uColor << (32 - (4 + 4));
                smLocalFloat49.w = (uint) smLocalFloat49.w >> (32 - 4);
              }
              else smLocalFloat49.w = (uint) cb_arrSpot [smLocalFloat46.x].uColor >> 4;
              smLocalFloat49.w = (int) smLocalFloat49.w + - 1;
              smLocalFloat414.z = (uint) smLocalFloat49.w;
              smLocalFloat49.w = taCookies.SampleGrad (LinearClampClamp_s, smLocalFloat414.xyz, smLocalFloat413.x, smLocalFloat413.z).x;
              smLocalFloat46.y = smLocalFloat49.w * smLocalFloat46.y;
            }
            smLocalFloat49.w = cmp (0 < smLocalFloat46.y);
            smLocalFloat47.w = max (0.00999999978, smLocalFloat47.w);
            smLocalFloat47.w = log2 (smLocalFloat47.w);
            smLocalFloat47.w = cb_arrSpot [smLocalFloat46.x].fFalloffFactor * smLocalFloat47.w;
            smLocalFloat47.w = exp2 (smLocalFloat47.w);
            smLocalFloat47.w = 1 + - smLocalFloat47.w;
            smLocalFloat47.w = cb_arrSpot [smLocalFloat46.x].fIntensity * smLocalFloat47.w;
            smLocalFloat46.y = smLocalFloat47.w * smLocalFloat46.y;
            smLocalFloat46.y = min (cb_arrSpot [smLocalFloat46.x].fMaxIntensity, smLocalFloat46.y);
            smLocalFloat47.w = abs (smLocalFloat48.w) * 0.75 + 0.25;
            smLocalFloat48.w = asuint (cb_arrSpot [smLocalFloat46.x].uColor) >> 24;
            smLocalFloat48.w = (uint) smLocalFloat48.w;
            smLocalFloat414.x = smLocalFloat48.w * smLocalFloat47.w;
            if (8 == 0) smLocalFloat413.x = 0;
            else if (8 + 16 < 32) {
              smLocalFloat413.x = (uint) cb_arrSpot [smLocalFloat46.x].uColor << (32 - (8 + 16));
              smLocalFloat413.x = (uint) smLocalFloat413.x >> (32 - 8);
            }
            else smLocalFloat413.x = (uint) cb_arrSpot [smLocalFloat46.x].uColor >> 16;
            if (8 == 0) smLocalFloat413.z = 0;
            else if (8 + 8 < 32) {
              smLocalFloat413.z = (uint) cb_arrSpot [smLocalFloat46.x].uColor << (32 - (8 + 8));
              smLocalFloat413.z = (uint) smLocalFloat413.z >> (32 - 8);
            }
            else smLocalFloat413.z = (uint) cb_arrSpot [smLocalFloat46.x].uColor >> 8;
            smLocalFloat413.xz = (uint2) smLocalFloat413.xz;
            smLocalFloat414.yz = smLocalFloat413.xz * smLocalFloat47.ww;
            smLocalFloat413.xzw = smLocalFloat414.xyz * smLocalFloat46.yyy;
            smLocalFloat413.xzw = float3 (0.00392156886, 0.00392156886, 0.00392156886) * smLocalFloat413.xzw;
            smLocalFloat414.xyz = max (float3 (0, 0, 0), smLocalFloat413.xzw);
            smLocalFloat414.xyz = smLocalFloat414.xyz + smLocalFloat412.xyz;
            smLocalFloat413.xzw = max (smLocalFloat413.xzw, smLocalFloat411.xyz);
            smLocalFloat413.xzw = smLocalFloat413.yyy ? smLocalFloat411.xyz : smLocalFloat413.xzw;
            smLocalFloat414.xyz = smLocalFloat413.yyy ? smLocalFloat414.xyz : smLocalFloat412.xyz;
            smLocalFloat411.xyz = smLocalFloat49.www ? smLocalFloat413.xzw : smLocalFloat411.xyz;
            smLocalFloat412.xyz = smLocalFloat49.www ? smLocalFloat414.xyz : smLocalFloat412.xyz;
          }
        }
      }
      smLocalFloat47.xyz = smLocalFloat411.xyz;
      smLocalFloat410.xyz = smLocalFloat412.xyz;
    }
    smLocalFloat41.xy = float2 (5, 0.5) * smLocalFloat41.ww;
    smLocalFloat40.w = min (1, smLocalFloat41.y);
    smLocalFloat40.w = 1 + - smLocalFloat40.w;
    smLocalFloat41.y = smLocalFloat41.w * 5 + - 3;
    smLocalFloat41.y = saturate (smLocalFloat41.y + smLocalFloat41.y);
    smLocalFloat41.y = 1 + - smLocalFloat41.y;
    smLocalFloat45.xyz = rcp (smLocalFloat43.xyz);
    smLocalFloat46.xyz = float3 (0, 0, 0);
    smLocalFloat48.xyz = float3 (0, 0, 0);
    smLocalFloat41.zw = float2 (0, 0);
    smLocalFloat43.w = 0;
    smLocalFloat44.w = smLocalFloat46.w;
    while (true) {
      if (smLocalFloat44.w == 0) break;
      smLocalFloat45.w = firstbitlow ((uint) smLocalFloat44.w);
      smLocalFloat47.w = (int) smLocalFloat42.w + (int) smLocalFloat45.w;
      smLocalFloat48.w = 1 << (int) smLocalFloat45.w;
      smLocalFloat44.w = (int) smLocalFloat44.w ^ (int) smLocalFloat48.w;
      smLocalFloat47.w = sbVoxelLightIds [smLocalFloat47.w].x;
      smLocalFloat45.w = (uint) smLocalFloat45.w << 5;
      smLocalFloat49.xyz = smLocalFloat46.xyz;
      smLocalFloat411.xyz = smLocalFloat48.xyz;
      smLocalFloat48.w = smLocalFloat41.z;
      smLocalFloat49.w = smLocalFloat41.w;
      smLocalFloat410.w = smLocalFloat43.w;
      smLocalFloat411.w = smLocalFloat47.w;
      while (true) {
        if (smLocalFloat411.w == 0) break;
        smLocalFloat412.x = firstbitlow ((uint) smLocalFloat411.w);
        smLocalFloat412.y = (int) smLocalFloat45.w + (int) smLocalFloat412.x;
        smLocalFloat412.x = 1 << (int) smLocalFloat412.x;
        smLocalFloat411.w = (int) smLocalFloat411.w ^ (int) smLocalFloat412.x;
        smLocalFloat412.x = mad ((int) smLocalFloat412.y, 10, - 7680);
        smLocalFloat412.yzw = cb_reflections.vecProbes [smLocalFloat412.x].vPosition.xyz + - smLocalFloat44.xyz;
        smLocalFloat412.yzw = - cb_reflections.vecProbes [smLocalFloat412.x].vExtents.xyz + abs (smLocalFloat412.yzw);
        smLocalFloat413.xyz = max (float3 (0, 0, 0), smLocalFloat412.yzw);
        smLocalFloat413.x = dot (smLocalFloat413.xyz, smLocalFloat413.xyz);
        smLocalFloat413.x = sqrt (smLocalFloat413.x);
        smLocalFloat412.y = max (smLocalFloat412.y, smLocalFloat412.z);
        smLocalFloat412.y = max (smLocalFloat412.y, smLocalFloat412.w);
        smLocalFloat412.y = min (0, smLocalFloat412.y);
        smLocalFloat412.y = smLocalFloat413.x + smLocalFloat412.y;
        smLocalFloat412.y = - cb_reflections.vecProbes [smLocalFloat412.x].fMargin + smLocalFloat412.y;
        smLocalFloat412.y = cb_reflections.vecProbes [smLocalFloat412.x].fGpuEnable * smLocalFloat412.y;
        smLocalFloat412.z = cmp (smLocalFloat412.y < 0);
        if (smLocalFloat412.z != 0) {
          smLocalFloat412.y = saturate (cb_reflections.vecProbes [smLocalFloat412.x].fMarginRcp * - smLocalFloat412.y);
          smLocalFloat412.z = cmp (0 != cb_reflections.vecProbes [smLocalFloat412.x].fIsFallback);
          smLocalFloat412.z = smLocalFloat412.z ? 1 : smLocalFloat412.y;
          smLocalFloat412.w = cb_reflections.vecProbes [smLocalFloat412.x].fBlend * smLocalFloat412.z;
          smLocalFloat413.x = cmp (1.000000 == cb_reflections.vecProbes [smLocalFloat412.x].fIsFallback);
          if (smLocalFloat413.x != 0) {
            smLocalFloat413.x = cmp (1.000000 == cb_reflections.vecProbes [smLocalFloat412.x].fParallax);
            smLocalFloat413.yzw = cb_reflections.vecProbes [smLocalFloat412.x].vMax.xyz + - smLocalFloat44.xyz;
            smLocalFloat413.yzw = smLocalFloat413.yzw * smLocalFloat45.xyz;
            smLocalFloat414.xyz = cb_reflections.vecProbes [smLocalFloat412.x].vMin.xyz + - smLocalFloat44.xyz;
            smLocalFloat414.xyz = smLocalFloat414.xyz * smLocalFloat45.xyz;
            smLocalFloat413.yzw = max (smLocalFloat414.xyz, smLocalFloat413.yzw);
            smLocalFloat413.y = min (smLocalFloat413.y, smLocalFloat413.z);
            smLocalFloat413.y = min (smLocalFloat413.y, smLocalFloat413.w);
            smLocalFloat413.yzw = smLocalFloat43.xyz * smLocalFloat413.yyy + smLocalFloat44.xyz;
            smLocalFloat413.yzw = - cb_reflections.vecProbes [smLocalFloat412.x].vPosition.xyz + smLocalFloat413.yzw;
            smLocalFloat413.xyz = smLocalFloat413.xxx ? smLocalFloat413.yzw : smLocalFloat43.xyz;
            smLocalFloat413.w = abs (smLocalFloat413.x) + abs (smLocalFloat413.y);
            smLocalFloat413.w = smLocalFloat413.w + abs (smLocalFloat413.z);
            smLocalFloat413.w = max (9.99999975e-05, smLocalFloat413.w);
            smLocalFloat413.w = rcp (smLocalFloat413.w);
            smLocalFloat413.xy = smLocalFloat413.xy * smLocalFloat413.ww;
            smLocalFloat414.xy = float2 (1, 1) + - abs (smLocalFloat413.yx);
            smLocalFloat414.zw = cmp (smLocalFloat413.xy < float2 (0, 0));
            smLocalFloat414.xy = smLocalFloat414.zw ? - smLocalFloat414.xy : smLocalFloat414.xy;
            smLocalFloat413.z = cmp (0 >= smLocalFloat413.z);
            smLocalFloat413.xy = smLocalFloat413.zz ? smLocalFloat414.xy : smLocalFloat413.xy;
            smLocalFloat413.xy = float2 (- 2, 2) + smLocalFloat413.xy;
            smLocalFloat413.z = max (abs (smLocalFloat413.x), abs (smLocalFloat413.y));
            smLocalFloat413.z = cmp (smLocalFloat413.z >= 1);
            smLocalFloat413.xy = smLocalFloat413.zz ? - smLocalFloat413.xy : smLocalFloat413.xy;
            smLocalFloat413.xy = smLocalFloat413.xy * float2 (0.5, 0.5) + float2 (0.5, 0.5);
            smLocalFloat413.z = cb_reflections.vecProbes [smLocalFloat412.x].fSlotIndex;
            smLocalFloat413.xyz = taReflection.SampleLevel (LinearMirrorMirror_s, smLocalFloat413.xyz, smLocalFloat41.x).xyz;
            smLocalFloat48.w = smLocalFloat412.z * cb_reflections.vecProbes [smLocalFloat412.x].fBlend + smLocalFloat48.w;
            smLocalFloat411.xyz = smLocalFloat413.xyz * smLocalFloat412.www + smLocalFloat411.xyz;
          }
          else {
            smLocalFloat412.z = cb_reflections.vecProbes [smLocalFloat412.x].fParallax * smLocalFloat41.y;
            smLocalFloat413.xyz = cb_reflections.vecProbes [smLocalFloat412.x].vMax.xyz + - smLocalFloat44.xyz;
            smLocalFloat413.xyz = smLocalFloat413.xyz * smLocalFloat45.xyz;
            smLocalFloat414.xyz = cb_reflections.vecProbes [smLocalFloat412.x].vMin.xyz + - smLocalFloat44.xyz;
            smLocalFloat414.xyz = smLocalFloat414.xyz * smLocalFloat45.xyz;
            smLocalFloat413.xyz = max (smLocalFloat414.xyz, smLocalFloat413.xyz);
            smLocalFloat413.x = min (smLocalFloat413.x, smLocalFloat413.y);
            smLocalFloat413.x = min (smLocalFloat413.x, smLocalFloat413.z);
            smLocalFloat413.xyz = smLocalFloat43.xyz * smLocalFloat413.xxx + smLocalFloat44.xyz;
            smLocalFloat413.xyz = - cb_reflections.vecProbes [smLocalFloat412.x].vPosition.xyz + smLocalFloat413.xyz;
            smLocalFloat413.w = dot (smLocalFloat413.xyz, smLocalFloat413.xyz);
            smLocalFloat413.w = rsqrt (smLocalFloat413.w);
            smLocalFloat413.xyz = smLocalFloat413.xyz * smLocalFloat413.www + - smLocalFloat43.xyz;
            smLocalFloat413.xyz = smLocalFloat412.zzz * smLocalFloat413.xyz + smLocalFloat43.xyz;
            smLocalFloat412.z = dot (smLocalFloat413.xyz, smLocalFloat413.xyz);
            smLocalFloat412.z = rsqrt (smLocalFloat412.z);
            smLocalFloat413.xyz = smLocalFloat413.xyz * smLocalFloat412.zzz;
            smLocalFloat412.z = abs (smLocalFloat413.x) + abs (smLocalFloat413.y);
            smLocalFloat412.z = smLocalFloat412.z + abs (smLocalFloat413.z);
            smLocalFloat412.z = max (9.99999975e-05, smLocalFloat412.z);
            smLocalFloat412.z = rcp (smLocalFloat412.z);
            smLocalFloat414.xy = smLocalFloat413.xy * smLocalFloat412.zz;
            smLocalFloat414.zw = float2 (1, 1) + - abs (smLocalFloat414.yx);
            smLocalFloat415.xy = cmp (smLocalFloat414.xy < float2 (0, 0));
            smLocalFloat414.zw = smLocalFloat415.xy ? - smLocalFloat414.zw : smLocalFloat414.zw;
            smLocalFloat412.z = cmp (0 >= smLocalFloat413.z);
            smLocalFloat414.xy = smLocalFloat412.zz ? smLocalFloat414.zw : smLocalFloat414.xy;
            smLocalFloat414.xy = float2 (- 2, 2) + smLocalFloat414.xy;
            smLocalFloat412.z = max (abs (smLocalFloat414.x), abs (smLocalFloat414.y));
            smLocalFloat412.z = cmp (smLocalFloat412.z >= 1);
            smLocalFloat414.xy = smLocalFloat412.zz ? - smLocalFloat414.xy : smLocalFloat414.xy;
            smLocalFloat414.xy = smLocalFloat414.xy * float2 (0.5, 0.5) + float2 (0.5, 0.5);
            smLocalFloat414.z = cb_reflections.vecProbes [smLocalFloat412.x].fSlotIndex;
            smLocalFloat414.xyzw = taReflection.SampleLevel (LinearMirrorMirror_s, smLocalFloat414.xyz, smLocalFloat41.x).xyzw;
            smLocalFloat412.z = smLocalFloat414.w * smLocalFloat414.w;
            smLocalFloat412.z = smLocalFloat412.z * 127.5 + 0.5;
            smLocalFloat415.xyz = smLocalFloat413.xyz * smLocalFloat412.zzz + cb_reflections.vecProbes [smLocalFloat412.x].vPosition.xyz;
            smLocalFloat416.xyz = - smLocalFloat415.xyz + smLocalFloat44.xyz;
            smLocalFloat412.z = dot (smLocalFloat416.xyz, smLocalFloat416.xyz);
            smLocalFloat415.xyz = cb_reflections.vecProbes [smLocalFloat412.x].vGpuPosition.xyz + - smLocalFloat415.xyz;
            smLocalFloat415.xyz = - cb_reflections.vecProbes [smLocalFloat412.x].vGpuExtents.xyz + abs (smLocalFloat415.xyz);
            smLocalFloat416.xyz = max (float3 (0, 0, 0), smLocalFloat415.xyz);
            smLocalFloat413.w = dot (smLocalFloat416.xyz, smLocalFloat416.xyz);
            smLocalFloat413.w = sqrt (smLocalFloat413.w);
            smLocalFloat414.w = max (smLocalFloat415.x, smLocalFloat415.y);
            smLocalFloat414.w = max (smLocalFloat414.w, smLocalFloat415.z);
            smLocalFloat414.w = min (0, smLocalFloat414.w);
            smLocalFloat413.w = smLocalFloat414.w + smLocalFloat413.w;
            smLocalFloat413.w = - cb_reflections.vecProbes [smLocalFloat412.x].fGpuMargin + smLocalFloat413.w;
            smLocalFloat412.x = saturate (cb_reflections.vecProbes [smLocalFloat412.x].fGpuMarginRcp * - smLocalFloat413.w);
            smLocalFloat413.x = dot (smLocalFloat43.xyz, smLocalFloat413.xyz);
            smLocalFloat413.x = smLocalFloat413.x * 0.5 + 0.5;
            smLocalFloat413.x = smLocalFloat413.x * smLocalFloat413.x;
            smLocalFloat412.z = 0.000244140625 * smLocalFloat412.z;
            smLocalFloat412.z = min (1, smLocalFloat412.z);
            smLocalFloat412.z = 1 + - smLocalFloat412.z;
            smLocalFloat412.z = smLocalFloat412.z * smLocalFloat412.z;
            smLocalFloat412.z = smLocalFloat412.z * smLocalFloat412.x;
            smLocalFloat412.z = smLocalFloat412.z * smLocalFloat413.x;
            smLocalFloat412.z = smLocalFloat412.z * smLocalFloat412.y;
            smLocalFloat412.z = smLocalFloat412.z * 10 + 1;
            smLocalFloat412.x = max (smLocalFloat412.x, smLocalFloat40.w);
            smLocalFloat412.x = smLocalFloat412.x * smLocalFloat412.y;
            smLocalFloat412.x = smLocalFloat412.x * smLocalFloat413.x;
            smLocalFloat412.x = smLocalFloat412.z * smLocalFloat412.x;
            smLocalFloat412.y = smLocalFloat412.x * smLocalFloat412.w;
            smLocalFloat49.w = smLocalFloat412.x * smLocalFloat412.w + smLocalFloat49.w;
            smLocalFloat412.x = cmp (0 < smLocalFloat412.x);
            smLocalFloat412.x = smLocalFloat412.x ? 1.000000 : 0;
            smLocalFloat410.w = smLocalFloat412.w * smLocalFloat412.x + smLocalFloat410.w;
            smLocalFloat412.yzw = smLocalFloat414.xyz * smLocalFloat412.yyy;
            smLocalFloat49.xyz = smLocalFloat412.yzw * smLocalFloat412.xxx + smLocalFloat49.xyz;
          }
        }
      }
      smLocalFloat46.xyz = smLocalFloat49.xyz;
      smLocalFloat48.xyz = smLocalFloat411.xyz;
      smLocalFloat41.z = smLocalFloat48.w;
      smLocalFloat41.w = smLocalFloat49.w;
      smLocalFloat43.w = smLocalFloat410.w;
    }
    smLocalFloat40.w = max (0.125, smLocalFloat41.w);
    smLocalFloat41.xyw = smLocalFloat46.xyz / smLocalFloat40.www;
    smLocalFloat40.w = max (0.00100000005, smLocalFloat41.z);
    smLocalFloat43.xyz = smLocalFloat48.xyz / smLocalFloat40.www;
    smLocalFloat43.w = saturate (smLocalFloat43.w);
    smLocalFloat40.w = smLocalFloat43.w * smLocalFloat43.w;
    smLocalFloat41.xyz = - smLocalFloat43.xyz + smLocalFloat41.xyw;
    smLocalFloat41.xyz = smLocalFloat40.www * smLocalFloat41.xyz + smLocalFloat43.xyz;
  }
  else {
    smLocalFloat47.xyz = cb_vDirectionalLightColor.xyz;
    smLocalFloat410.xyz = float3 (0, 0, 0);
    smLocalFloat41.xyz = float3 (0, 0, 0);
  }
  smLocalFloat43.xyz = smLocalFloat410.xyz + smLocalFloat47.xyz;
  smLocalFloat42.xyz = smLocalFloat43.xyz * smLocalFloat42.xyz;
  smLocalFloat41.xyz = smLocalFloat41.xyz * smLocalFloat40.yyy + - smLocalFloat42.xyz;
  smLocalFloat41.xyz = smLocalFloat40.yyy * smLocalFloat41.xyz + smLocalFloat42.xyz;
  smLocalFloat40.yzw = smLocalFloat43.xyz * smLocalFloat40.zzz + smLocalFloat41.xyz;
  smLocalFloat41.x = cmp (0.00100000005 < smLocalFloat40.x);
  if (smLocalFloat41.x != 0) {
    smLocalFloat41.xyz = tFrame.Sample (LinearClampClamp_s, smin_screen_uv0.xy).xyz;
    smLocalFloat42.xyz = - smLocalFloat41.xyz + smLocalFloat40.yzw;
    smLocalFloat40.yzw = smLocalFloat40.xxx * smLocalFloat42.xyz + smLocalFloat41.xyz;
  }
  smLocalFloat41.xyz = smin_fog_color0.xyz + - smLocalFloat40.yzw;
  smout_sv_target0.xyz = smin_fog_color0.www * smLocalFloat41.xyz + smLocalFloat40.yzw;
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy8(
  )
{

}

#include "main_part_transparent_surface_water_tangent_map_dissolve_uv0_fog_cutoff.hlsl"
