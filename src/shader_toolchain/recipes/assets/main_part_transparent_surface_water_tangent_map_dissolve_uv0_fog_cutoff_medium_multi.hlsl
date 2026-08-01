// Synthesized semantic family: transparent_surface_water_tangent_map_dissolve_uv0_fog_cutoff
// Policy: quality=medium, reflection=multi
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
  smLocalFloat42.w = max (0.00999999978, smLocalFloat41.w);
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy4(
  inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat42)
{
  smLocalFloat42.w = log2 (smLocalFloat42.w);
  smLocalFloat40.x = smLocalFloat42.w * smLocalFloat40.x;
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy5(
  inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat42, inout float4 smLocalFloat43)
{
  smLocalFloat42.w = 0.995000005 * smLocalFloat40.w;
  smLocalFloat43.w = - smLocalFloat40.w * 0.995000005 + 1;
  smLocalFloat40.z = abs (smLocalFloat40.z) * abs (smLocalFloat40.z) + - smLocalFloat42.w;
  smLocalFloat42.w = 1 / smLocalFloat43.w;
  smLocalFloat40.z = saturate (smLocalFloat42.w * smLocalFloat40.z);
  smLocalFloat42.w = smLocalFloat40.z * - 2 + 3;
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy6(
  inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat42)
{
  smLocalFloat40.z = smLocalFloat42.w * smLocalFloat40.z;
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
    smLocalFloat42.w = dot (- smLocalFloat43.xyz, smLocalFloat41.xyz);
    smLocalFloat42.w = smLocalFloat42.w + smLocalFloat42.w;
    smLocalFloat44.yzw = smLocalFloat41.xyz * - smLocalFloat42.www + - smLocalFloat43.xyz;
    smLocalFloat45.xyz = viewToWorld._m01_m11_m21 * smLocalFloat44.zzz;
    smLocalFloat45.xyz = viewToWorld._m00_m10_m20 * smLocalFloat44.yyy + smLocalFloat45.xyz;
    smLocalFloat44.yzw = viewToWorld._m02_m12_m22 * smLocalFloat44.www + smLocalFloat45.xyz;
    smLocalFloat42.w = log2 (abs (smLocalFloat44.x));
    smLocalFloat42.w = 0.75 * smLocalFloat42.w;
    smLocalFloat42.w = exp2 (smLocalFloat42.w);
    smLocalFloat45.xyz = viewToWorld._m01_m11_m21 * smin_view_position0.yyy;
    smLocalFloat45.xyz = viewToWorld._m00_m10_m20 * smin_view_position0.xxx + smLocalFloat45.xyz;
    smLocalFloat45.xyz = viewToWorld._m02_m12_m22 * smin_view_position0.zzz + smLocalFloat45.xyz;
    smLocalFloat45.xyz = viewToWorld._m03_m13_m23 + smLocalFloat45.xyz;
    smLocalFloat46.xyz = ddx_coarse (smLocalFloat45.xyz);
    smLocalFloat46.xyz = smLocalFloat46.xyz + smLocalFloat45.xyz;
    smLocalFloat47.xyz = ddy_coarse (smLocalFloat45.xyz);
    smLocalFloat46.xyz = smLocalFloat47.xyz + smLocalFloat46.xyz;
    smLocalFloat40.w = saturate (6.66666651 * smLocalFloat40.w);
    smLocalFloat40.w = 1 + - smLocalFloat40.w;
    smLocalFloat43.zw = cb_vInvRenderScale.xy * smin_screen_uv0.xy;
    smLocalFloat44.x = - smin_view_position0.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    smLocalFloat44.x = rsqrt (smLocalFloat44.x);
    smLocalFloat44.x = 1 / smLocalFloat44.x;
    smLocalFloat44.x = cb_cluster.vVoxelDims.z * smLocalFloat44.x;
    smLocalFloat44.x = floor (smLocalFloat44.x);
    smLocalFloat44.x = (uint) smLocalFloat44.x;
    smLocalFloat43.zw = cb_cluster.vVoxelDims.xy * smLocalFloat43.zw;
    smLocalFloat43.zw = (uint2) smLocalFloat43.zw;
    smLocalFloat43.z = mad ((int) smLocalFloat43.w, asint (cb_cluster.uClusterWidth), (int) smLocalFloat43.z);
    smLocalFloat43.z = mad ((int) smLocalFloat44.x, asint (cb_cluster.uClusterSliceSize), (int) smLocalFloat43.z);
    smLocalFloat43.w = (int) smLocalFloat43.z * 33;
    smLocalFloat43.w = sbVoxelLightIds [smLocalFloat43.w].x;
    smLocalFloat43.z = mad ((int) smLocalFloat43.z, 33, 1);
    smLocalFloat47.xyzw = (int4) smLocalFloat43.wwww & int4 (255, 0xff00, 0xff0000, 0xff000000);
    smLocalFloat48.xyz = cb_vDirectionalLightColor.xyz;
    smLocalFloat43.w = smLocalFloat47.x;
    while (true) {
      if (smLocalFloat43.w == 0) break;
      smLocalFloat44.x = firstbitlow ((uint) smLocalFloat43.w);
      smLocalFloat45.w = (int) smLocalFloat43.z + (int) smLocalFloat44.x;
      smLocalFloat46.w = 1 << (int) smLocalFloat44.x;
      smLocalFloat43.w = (int) smLocalFloat43.w ^ (int) smLocalFloat46.w;
      smLocalFloat45.w = sbVoxelLightIds [smLocalFloat45.w].x;
      smLocalFloat44.x = (uint) smLocalFloat44.x << 5;
      smLocalFloat49.xyz = smLocalFloat48.xyz;
      smLocalFloat46.w = smLocalFloat45.w;
      while (true) {
        if (smLocalFloat46.w == 0) break;
        smLocalFloat48.w = firstbitlow ((uint) smLocalFloat46.w);
        smLocalFloat49.w = (int) smLocalFloat44.x + (int) smLocalFloat48.w;
        smLocalFloat48.w = 1 << (int) smLocalFloat48.w;
        smLocalFloat46.w = (int) smLocalFloat46.w ^ (int) smLocalFloat48.w;
        smLocalFloat48.w = (uint) smLocalFloat49.w << 1;
        smLocalFloat410.xyz = cb_arrAmbient [smLocalFloat48.w].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat49.w = dot (smLocalFloat410.xyz, smLocalFloat410.xyz);
        smLocalFloat410.w = sqrt (smLocalFloat49.w);
        smLocalFloat410.w = saturate (cb_arrAmbient [smLocalFloat48.w].fRcpRadius * smLocalFloat410.w);
        smLocalFloat49.w = rsqrt (smLocalFloat49.w);
        smLocalFloat410.xyz = smLocalFloat410.xyz * smLocalFloat49.www;
        smLocalFloat49.w = dot (smLocalFloat410.xyz, smLocalFloat41.xyz);
        smLocalFloat49.w = abs (smLocalFloat49.w) * 0.5 + 0.5;
        smLocalFloat410.x = smLocalFloat410.w * smLocalFloat410.w;
        smLocalFloat410.x = - smLocalFloat410.x * smLocalFloat410.x + 1;
        smLocalFloat410.x = cb_arrAmbient [smLocalFloat48.w].fIntensity * smLocalFloat410.x;
        smLocalFloat410.x = smLocalFloat410.x * smLocalFloat40.w;
        smLocalFloat49.w = smLocalFloat410.x * smLocalFloat49.w;
        smLocalFloat410.xyz = cb_arrAmbient [smLocalFloat48.w].vColor.xyz * smLocalFloat49.www;
        smLocalFloat49.xyz = max (smLocalFloat410.xyz, smLocalFloat49.xyz);
      }
      smLocalFloat48.xyz = smLocalFloat49.xyz;
    }
    smLocalFloat49.xyz = smLocalFloat48.xyz;
    smLocalFloat410.xyz = float3 (0, 0, 0);
    smLocalFloat40.w = smLocalFloat47.y;
    while (true) {
      if (smLocalFloat40.w == 0) break;
      smLocalFloat43.w = firstbitlow ((uint) smLocalFloat40.w);
      smLocalFloat44.x = (int) smLocalFloat43.w + (int) smLocalFloat43.z;
      smLocalFloat45.w = 1 << (int) smLocalFloat43.w;
      smLocalFloat40.w = (int) smLocalFloat40.w ^ (int) smLocalFloat45.w;
      smLocalFloat44.x = sbVoxelLightIds [smLocalFloat44.x].x;
      smLocalFloat43.w = (uint) smLocalFloat43.w << 5;
      smLocalFloat411.xyz = smLocalFloat49.xyz;
      smLocalFloat412.xyz = smLocalFloat410.xyz;
      smLocalFloat45.w = smLocalFloat44.x;
      while (true) {
        if (smLocalFloat45.w == 0) break;
        smLocalFloat46.w = firstbitlow ((uint) smLocalFloat45.w);
        smLocalFloat47.x = (int) smLocalFloat43.w + (int) smLocalFloat46.w;
        smLocalFloat46.w = 1 << (int) smLocalFloat46.w;
        smLocalFloat45.w = (int) smLocalFloat45.w ^ (int) smLocalFloat46.w;
        smLocalFloat46.w = (uint) smLocalFloat47.x << 1;
        smLocalFloat46.w = (int) smLocalFloat46.w + - 512;
        smLocalFloat413.xyz = cb_arrPoint [smLocalFloat46.w].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat47.x = dot (smLocalFloat413.xyz, smLocalFloat413.xyz);
        smLocalFloat47.x = sqrt (smLocalFloat47.x);
        smLocalFloat48.w = saturate (cb_arrPoint [smLocalFloat46.w].fRcpRadius * smLocalFloat47.x);
        smLocalFloat47.x = max (0.00100000005, smLocalFloat47.x);
        smLocalFloat413.xyz = smLocalFloat413.xyz / smLocalFloat47.xxx;
        smLocalFloat47.x = dot (smLocalFloat413.xyz, smLocalFloat41.xyz);
        smLocalFloat47.x = abs (smLocalFloat47.x) * 0.75 + 0.25;
        smLocalFloat48.w = max (0.00999999978, smLocalFloat48.w);
        smLocalFloat48.w = log2 (smLocalFloat48.w);
        smLocalFloat48.w = cb_arrPoint [smLocalFloat46.w].fFalloffFactor * smLocalFloat48.w;
        smLocalFloat48.w = exp2 (smLocalFloat48.w);
        smLocalFloat48.w = 1 + - smLocalFloat48.w;
        smLocalFloat48.w = cb_arrPoint [smLocalFloat46.w].fIntensity * smLocalFloat48.w;
        smLocalFloat48.w = min (cb_arrPoint [smLocalFloat46.w].fMaxIntensity, smLocalFloat48.w);
        smLocalFloat49.w = asuint (cb_arrPoint [smLocalFloat46.w].uColor) >> 24;
        smLocalFloat49.w = (uint) smLocalFloat49.w;
        smLocalFloat413.x = smLocalFloat49.w * smLocalFloat47.x;
        if (8 == 0) smLocalFloat414.x = 0;
        else if (8 + 16 < 32) {
          smLocalFloat414.x = (uint) cb_arrPoint [smLocalFloat46.w].uColor << (32 - (8 + 16));
          smLocalFloat414.x = (uint) smLocalFloat414.x >> (32 - 8);
        }
        else smLocalFloat414.x = (uint) cb_arrPoint [smLocalFloat46.w].uColor >> 16;
        if (8 == 0) smLocalFloat414.y = 0;
        else if (8 + 8 < 32) {
          smLocalFloat414.y = (uint) cb_arrPoint [smLocalFloat46.w].uColor << (32 - (8 + 8));
          smLocalFloat414.y = (uint) smLocalFloat414.y >> (32 - 8);
        }
        else smLocalFloat414.y = (uint) cb_arrPoint [smLocalFloat46.w].uColor >> 8;
        smLocalFloat414.xy = (uint2) smLocalFloat414.xy;
        smLocalFloat413.yz = smLocalFloat414.xy * smLocalFloat47.xx;
        smLocalFloat413.xyz = smLocalFloat413.xyz * smLocalFloat48.www;
        smLocalFloat413.xyz = float3 (0.00392156886, 0.00392156886, 0.00392156886) * smLocalFloat413.xyz;
        smLocalFloat46.w = 1 & asint (cb_arrPoint [smLocalFloat46.w].uColor);
        smLocalFloat414.xyz = max (float3 (0, 0, 0), smLocalFloat413.xyz);
        smLocalFloat414.xyz = smLocalFloat414.xyz + smLocalFloat412.xyz;
        smLocalFloat413.xyz = max (smLocalFloat413.xyz, smLocalFloat411.xyz);
        smLocalFloat411.xyz = smLocalFloat46.www ? smLocalFloat411.xyz : smLocalFloat413.xyz;
        smLocalFloat412.xyz = smLocalFloat46.www ? smLocalFloat414.xyz : smLocalFloat412.xyz;
      }
      smLocalFloat49.xyz = smLocalFloat411.xyz;
      smLocalFloat410.xyz = smLocalFloat412.xyz;
    }
    smLocalFloat48.xyz = smLocalFloat49.xyz;
    smLocalFloat411.xyz = smLocalFloat410.xyz;
    smLocalFloat40.w = smLocalFloat47.z;
    while (true) {
      if (smLocalFloat40.w == 0) break;
      smLocalFloat43.w = firstbitlow ((uint) smLocalFloat40.w);
      smLocalFloat44.x = (int) smLocalFloat43.w + (int) smLocalFloat43.z;
      smLocalFloat45.w = 1 << (int) smLocalFloat43.w;
      smLocalFloat40.w = (int) smLocalFloat40.w ^ (int) smLocalFloat45.w;
      smLocalFloat44.x = sbVoxelLightIds [smLocalFloat44.x].x;
      smLocalFloat43.w = (uint) smLocalFloat43.w << 5;
      smLocalFloat412.xyz = smLocalFloat48.xyz;
      smLocalFloat413.xyz = smLocalFloat411.xyz;
      smLocalFloat45.w = smLocalFloat44.x;
      while (true) {
        if (smLocalFloat45.w == 0) break;
        smLocalFloat46.w = firstbitlow ((uint) smLocalFloat45.w);
        smLocalFloat47.x = (int) smLocalFloat43.w + (int) smLocalFloat46.w;
        smLocalFloat46.w = 1 << (int) smLocalFloat46.w;
        smLocalFloat45.w = (int) smLocalFloat45.w ^ (int) smLocalFloat46.w;
        smLocalFloat46.w = mad ((int) smLocalFloat47.x, 9, - 4608);
        smLocalFloat414.xyz = cb_arrSpot [smLocalFloat46.w].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat47.x = dot (smLocalFloat414.xyz, smLocalFloat414.xyz);
        smLocalFloat47.x = sqrt (smLocalFloat47.x);
        smLocalFloat47.y = cb_arrSpot [smLocalFloat46.w].fRcpRange * smLocalFloat47.x;
        smLocalFloat48.w = cmp (1 >= smLocalFloat47.y);
        if (smLocalFloat48.w != 0) {
          smLocalFloat47.x = max (0.00100000005, smLocalFloat47.x);
          smLocalFloat414.xyz = smLocalFloat414.xyz / smLocalFloat47.xxx;
          smLocalFloat47.x = dot (- smLocalFloat414.xyz, cb_arrSpot [smLocalFloat46.w].vForward.xyz);
          smLocalFloat48.w = cmp (0 < smLocalFloat47.x);
          if (smLocalFloat48.w != 0) {
            smLocalFloat48.w = dot (smLocalFloat414.xyz, smLocalFloat41.xyz);
            smLocalFloat47.x = saturate (smLocalFloat47.x * cb_arrSpot [smLocalFloat46.w].fCutoffScale + cb_arrSpot [smLocalFloat46.w].fCutoffOffset);
            smLocalFloat414.xy = int2 (240, 1) & asint (cb_arrSpot [smLocalFloat46.w].uColor);
            if (smLocalFloat414.x != 0) {
              smLocalFloat414.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m01_m11_m31 * smLocalFloat45.yyy;
              smLocalFloat414.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m00_m10_m30 * smLocalFloat45.xxx + smLocalFloat414.xzw;
              smLocalFloat414.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m02_m12_m32 * smLocalFloat45.zzz + smLocalFloat414.xzw;
              smLocalFloat414.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m03_m13_m33 + smLocalFloat414.xzw;
              smLocalFloat414.xz = smLocalFloat414.xz / smLocalFloat414.ww;
              smLocalFloat415.xy = smLocalFloat414.xz * float2 (0.5, 0.5) + float2 (0.5, 0.5);
              smLocalFloat414.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m01_m11_m31 * smLocalFloat46.yyy;
              smLocalFloat414.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m00_m10_m30 * smLocalFloat46.xxx + smLocalFloat414.xzw;
              smLocalFloat414.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m02_m12_m32 * smLocalFloat46.zzz + smLocalFloat414.xzw;
              smLocalFloat414.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m03_m13_m33 + smLocalFloat414.xzw;
              smLocalFloat414.xz = smLocalFloat414.xz / smLocalFloat414.ww;
              smLocalFloat414.xz = smLocalFloat414.xz * float2 (0.5, 0.5) + float2 (0.5, 0.5);
              smLocalFloat414.xz = smLocalFloat415.xy + - smLocalFloat414.xz;
              if (4 == 0) smLocalFloat49.w = 0;
              else if (4 + 4 < 32) {
                smLocalFloat49.w = (uint) cb_arrSpot [smLocalFloat46.w].uColor << (32 - (4 + 4));
                smLocalFloat49.w = (uint) smLocalFloat49.w >> (32 - 4);
              }
              else smLocalFloat49.w = (uint) cb_arrSpot [smLocalFloat46.w].uColor >> 4;
              smLocalFloat49.w = (int) smLocalFloat49.w + - 1;
              smLocalFloat415.z = (uint) smLocalFloat49.w;
              smLocalFloat49.w = taCookies.SampleGrad (LinearClampClamp_s, smLocalFloat415.xyz, smLocalFloat414.x, smLocalFloat414.z).x;
              smLocalFloat47.x = smLocalFloat49.w * smLocalFloat47.x;
            }
            smLocalFloat49.w = cmp (0 < smLocalFloat47.x);
            smLocalFloat47.y = max (0.00999999978, smLocalFloat47.y);
            smLocalFloat47.y = log2 (smLocalFloat47.y);
            smLocalFloat47.y = cb_arrSpot [smLocalFloat46.w].fFalloffFactor * smLocalFloat47.y;
            smLocalFloat47.y = exp2 (smLocalFloat47.y);
            smLocalFloat47.y = 1 + - smLocalFloat47.y;
            smLocalFloat47.y = cb_arrSpot [smLocalFloat46.w].fIntensity * smLocalFloat47.y;
            smLocalFloat47.x = smLocalFloat47.y * smLocalFloat47.x;
            smLocalFloat47.x = min (cb_arrSpot [smLocalFloat46.w].fMaxIntensity, smLocalFloat47.x);
            smLocalFloat47.y = abs (smLocalFloat48.w) * 0.75 + 0.25;
            smLocalFloat48.w = asuint (cb_arrSpot [smLocalFloat46.w].uColor) >> 24;
            smLocalFloat48.w = (uint) smLocalFloat48.w;
            smLocalFloat415.x = smLocalFloat48.w * smLocalFloat47.y;
            if (8 == 0) smLocalFloat414.x = 0;
            else if (8 + 16 < 32) {
              smLocalFloat414.x = (uint) cb_arrSpot [smLocalFloat46.w].uColor << (32 - (8 + 16));
              smLocalFloat414.x = (uint) smLocalFloat414.x >> (32 - 8);
            }
            else smLocalFloat414.x = (uint) cb_arrSpot [smLocalFloat46.w].uColor >> 16;
            if (8 == 0) smLocalFloat414.z = 0;
            else if (8 + 8 < 32) {
              smLocalFloat414.z = (uint) cb_arrSpot [smLocalFloat46.w].uColor << (32 - (8 + 8));
              smLocalFloat414.z = (uint) smLocalFloat414.z >> (32 - 8);
            }
            else smLocalFloat414.z = (uint) cb_arrSpot [smLocalFloat46.w].uColor >> 8;
            smLocalFloat414.xz = (uint2) smLocalFloat414.xz;
            smLocalFloat415.yz = smLocalFloat414.xz * smLocalFloat47.yy;
            smLocalFloat414.xzw = smLocalFloat415.xyz * smLocalFloat47.xxx;
            smLocalFloat414.xzw = float3 (0.00392156886, 0.00392156886, 0.00392156886) * smLocalFloat414.xzw;
            smLocalFloat415.xyz = max (float3 (0, 0, 0), smLocalFloat414.xzw);
            smLocalFloat415.xyz = smLocalFloat415.xyz + smLocalFloat413.xyz;
            smLocalFloat414.xzw = max (smLocalFloat414.xzw, smLocalFloat412.xyz);
            smLocalFloat414.xzw = smLocalFloat414.yyy ? smLocalFloat412.xyz : smLocalFloat414.xzw;
            smLocalFloat415.xyz = smLocalFloat414.yyy ? smLocalFloat415.xyz : smLocalFloat413.xyz;
            smLocalFloat412.xyz = smLocalFloat49.www ? smLocalFloat414.xzw : smLocalFloat412.xyz;
            smLocalFloat413.xyz = smLocalFloat49.www ? smLocalFloat415.xyz : smLocalFloat413.xyz;
          }
        }
      }
      smLocalFloat48.xyz = smLocalFloat412.xyz;
      smLocalFloat411.xyz = smLocalFloat413.xyz;
    }
    smLocalFloat46.xy = float2 (5, 0.5) * smLocalFloat42.ww;
    smLocalFloat40.w = min (1, smLocalFloat46.y);
    smLocalFloat40.w = 1 + - smLocalFloat40.w;
    smLocalFloat41.z = smLocalFloat42.w * 5 + - 3;
    smLocalFloat41.z = saturate (smLocalFloat41.z + smLocalFloat41.z);
    smLocalFloat41.z = 1 + - smLocalFloat41.z;
    smLocalFloat46.yzw = rcp (smLocalFloat44.yzw);
    smLocalFloat47.xyz = float3 (0, 0, 0);
    smLocalFloat49.xyz = float3 (0, 0, 0);
    smLocalFloat42.w = 0;
    smLocalFloat43.w = 0;
    smLocalFloat44.x = 0;
    smLocalFloat45.w = smLocalFloat47.w;
    while (true) {
      if (smLocalFloat45.w == 0) break;
      smLocalFloat48.w = firstbitlow ((uint) smLocalFloat45.w);
      smLocalFloat49.w = (int) smLocalFloat43.z + (int) smLocalFloat48.w;
      smLocalFloat410.x = 1 << (int) smLocalFloat48.w;
      smLocalFloat45.w = (int) smLocalFloat45.w ^ (int) smLocalFloat410.x;
      smLocalFloat49.w = sbVoxelLightIds [smLocalFloat49.w].x;
      smLocalFloat48.w = (uint) smLocalFloat48.w << 5;
      smLocalFloat410.xyz = smLocalFloat47.xyz;
      smLocalFloat412.xyz = smLocalFloat49.xyz;
      smLocalFloat410.w = smLocalFloat42.w;
      smLocalFloat411.w = smLocalFloat43.w;
      smLocalFloat412.w = smLocalFloat44.x;
      smLocalFloat413.x = smLocalFloat49.w;
      while (true) {
        if (smLocalFloat413.x == 0) break;
        smLocalFloat413.y = firstbitlow ((uint) smLocalFloat413.x);
        smLocalFloat413.z = (int) smLocalFloat48.w + (int) smLocalFloat413.y;
        smLocalFloat413.y = 1 << (int) smLocalFloat413.y;
        smLocalFloat413.x = (int) smLocalFloat413.y ^ (int) smLocalFloat413.x;
        smLocalFloat413.y = mad ((int) smLocalFloat413.z, 10, - 7680);
        smLocalFloat414.xyz = cb_reflections.vecProbes [smLocalFloat413.y].vPosition.xyz + - smLocalFloat45.xyz;
        smLocalFloat414.xyz = - cb_reflections.vecProbes [smLocalFloat413.y].vExtents.xyz + abs (smLocalFloat414.xyz);
        smLocalFloat415.xyz = max (float3 (0, 0, 0), smLocalFloat414.xyz);
        smLocalFloat413.z = dot (smLocalFloat415.xyz, smLocalFloat415.xyz);
        smLocalFloat413.z = sqrt (smLocalFloat413.z);
        smLocalFloat413.w = max (smLocalFloat414.x, smLocalFloat414.y);
        smLocalFloat413.w = max (smLocalFloat413.w, smLocalFloat414.z);
        smLocalFloat413.w = min (0, smLocalFloat413.w);
        smLocalFloat413.z = smLocalFloat413.z + smLocalFloat413.w;
        smLocalFloat413.z = - cb_reflections.vecProbes [smLocalFloat413.y].fMargin + smLocalFloat413.z;
        smLocalFloat413.z = cb_reflections.vecProbes [smLocalFloat413.y].fGpuEnable * smLocalFloat413.z;
        smLocalFloat413.w = cmp (smLocalFloat413.z < 0);
        if (smLocalFloat413.w != 0) {
          smLocalFloat413.z = saturate (cb_reflections.vecProbes [smLocalFloat413.y].fMarginRcp * - smLocalFloat413.z);
          smLocalFloat413.w = cmp (0 != cb_reflections.vecProbes [smLocalFloat413.y].fIsFallback);
          smLocalFloat413.w = smLocalFloat413.w ? 1 : smLocalFloat413.z;
          smLocalFloat414.x = cb_reflections.vecProbes [smLocalFloat413.y].fBlend * smLocalFloat413.w;
          smLocalFloat414.y = cmp (1.000000 == cb_reflections.vecProbes [smLocalFloat413.y].fIsFallback);
          if (smLocalFloat414.y != 0) {
            smLocalFloat414.y = cmp (1.000000 == cb_reflections.vecProbes [smLocalFloat413.y].fParallax);
            smLocalFloat415.xyz = cb_reflections.vecProbes [smLocalFloat413.y].vMax.xyz + - smLocalFloat45.xyz;
            smLocalFloat415.xyz = smLocalFloat415.xyz * smLocalFloat46.yzw;
            smLocalFloat416.xyz = cb_reflections.vecProbes [smLocalFloat413.y].vMin.xyz + - smLocalFloat45.xyz;
            smLocalFloat416.xyz = smLocalFloat416.xyz * smLocalFloat46.yzw;
            smLocalFloat415.xyz = max (smLocalFloat416.xyz, smLocalFloat415.xyz);
            smLocalFloat414.z = min (smLocalFloat415.x, smLocalFloat415.y);
            smLocalFloat414.z = min (smLocalFloat414.z, smLocalFloat415.z);
            smLocalFloat415.xyz = smLocalFloat44.yzw * smLocalFloat414.zzz + smLocalFloat45.xyz;
            smLocalFloat415.xyz = - cb_reflections.vecProbes [smLocalFloat413.y].vPosition.xyz + smLocalFloat415.xyz;
            smLocalFloat414.yzw = smLocalFloat414.yyy ? smLocalFloat415.xyz : smLocalFloat44.yzw;
            smLocalFloat415.x = abs (smLocalFloat414.y) + abs (smLocalFloat414.z);
            smLocalFloat415.x = smLocalFloat415.x + abs (smLocalFloat414.w);
            smLocalFloat415.x = max (9.99999975e-05, smLocalFloat415.x);
            smLocalFloat415.x = rcp (smLocalFloat415.x);
            smLocalFloat414.yz = smLocalFloat415.xx * smLocalFloat414.yz;
            smLocalFloat415.xy = float2 (1, 1) + - abs (smLocalFloat414.zy);
            smLocalFloat415.zw = cmp (smLocalFloat414.yz < float2 (0, 0));
            smLocalFloat415.xy = smLocalFloat415.zw ? - smLocalFloat415.xy : smLocalFloat415.xy;
            smLocalFloat414.w = cmp (0 >= smLocalFloat414.w);
            smLocalFloat414.yz = smLocalFloat414.ww ? smLocalFloat415.xy : smLocalFloat414.yz;
            smLocalFloat414.yz = float2 (- 2, 2) + smLocalFloat414.yz;
            smLocalFloat414.w = max (abs (smLocalFloat414.y), abs (smLocalFloat414.z));
            smLocalFloat414.w = cmp (smLocalFloat414.w >= 1);
            smLocalFloat414.yz = smLocalFloat414.ww ? - smLocalFloat414.yz : smLocalFloat414.yz;
            smLocalFloat415.xy = smLocalFloat414.yz * float2 (0.5, 0.5) + float2 (0.5, 0.5);
            smLocalFloat415.z = cb_reflections.vecProbes [smLocalFloat413.y].fSlotIndex;
            smLocalFloat414.yzw = taReflection.SampleLevel (LinearMirrorMirror_s, smLocalFloat415.xyz, smLocalFloat46.x).xyz;
            smLocalFloat410.w = smLocalFloat413.w * cb_reflections.vecProbes [smLocalFloat413.y].fBlend + smLocalFloat410.w;
            smLocalFloat412.xyz = smLocalFloat414.yzw * smLocalFloat414.xxx + smLocalFloat412.xyz;
          }
          else {
            smLocalFloat413.w = cb_reflections.vecProbes [smLocalFloat413.y].fParallax * smLocalFloat41.z;
            smLocalFloat414.yzw = cb_reflections.vecProbes [smLocalFloat413.y].vMax.xyz + - smLocalFloat45.xyz;
            smLocalFloat414.yzw = smLocalFloat414.yzw * smLocalFloat46.yzw;
            smLocalFloat415.xyz = cb_reflections.vecProbes [smLocalFloat413.y].vMin.xyz + - smLocalFloat45.xyz;
            smLocalFloat415.xyz = smLocalFloat415.xyz * smLocalFloat46.yzw;
            smLocalFloat414.yzw = max (smLocalFloat415.xyz, smLocalFloat414.yzw);
            smLocalFloat414.y = min (smLocalFloat414.y, smLocalFloat414.z);
            smLocalFloat414.y = min (smLocalFloat414.y, smLocalFloat414.w);
            smLocalFloat414.yzw = smLocalFloat44.yzw * smLocalFloat414.yyy + smLocalFloat45.xyz;
            smLocalFloat414.yzw = - cb_reflections.vecProbes [smLocalFloat413.y].vPosition.xyz + smLocalFloat414.yzw;
            smLocalFloat415.x = dot (smLocalFloat414.yzw, smLocalFloat414.yzw);
            smLocalFloat415.x = rsqrt (smLocalFloat415.x);
            smLocalFloat414.yzw = smLocalFloat414.yzw * smLocalFloat415.xxx + - smLocalFloat44.yzw;
            smLocalFloat414.yzw = smLocalFloat413.www * smLocalFloat414.yzw + smLocalFloat44.yzw;
            smLocalFloat413.w = dot (smLocalFloat414.yzw, smLocalFloat414.yzw);
            smLocalFloat413.w = rsqrt (smLocalFloat413.w);
            smLocalFloat414.yzw = smLocalFloat414.yzw * smLocalFloat413.www;
            smLocalFloat413.w = abs (smLocalFloat414.y) + abs (smLocalFloat414.z);
            smLocalFloat413.w = smLocalFloat413.w + abs (smLocalFloat414.w);
            smLocalFloat413.w = max (9.99999975e-05, smLocalFloat413.w);
            smLocalFloat413.w = rcp (smLocalFloat413.w);
            smLocalFloat415.xy = smLocalFloat414.yz * smLocalFloat413.ww;
            smLocalFloat415.zw = float2 (1, 1) + - abs (smLocalFloat415.yx);
            smLocalFloat416.xy = cmp (smLocalFloat415.xy < float2 (0, 0));
            smLocalFloat415.zw = smLocalFloat416.xy ? - smLocalFloat415.zw : smLocalFloat415.zw;
            smLocalFloat413.w = cmp (0 >= smLocalFloat414.w);
            smLocalFloat415.xy = smLocalFloat413.ww ? smLocalFloat415.zw : smLocalFloat415.xy;
            smLocalFloat415.xy = float2 (- 2, 2) + smLocalFloat415.xy;
            smLocalFloat413.w = max (abs (smLocalFloat415.x), abs (smLocalFloat415.y));
            smLocalFloat413.w = cmp (smLocalFloat413.w >= 1);
            smLocalFloat415.xy = smLocalFloat413.ww ? - smLocalFloat415.xy : smLocalFloat415.xy;
            smLocalFloat415.xy = smLocalFloat415.xy * float2 (0.5, 0.5) + float2 (0.5, 0.5);
            smLocalFloat415.z = cb_reflections.vecProbes [smLocalFloat413.y].fSlotIndex;
            smLocalFloat415.xyzw = taReflection.SampleLevel (LinearMirrorMirror_s, smLocalFloat415.xyz, smLocalFloat46.x).xyzw;
            smLocalFloat413.w = smLocalFloat415.w * smLocalFloat415.w;
            smLocalFloat413.w = smLocalFloat413.w * 127.5 + 0.5;
            smLocalFloat416.xyz = smLocalFloat414.yzw * smLocalFloat413.www + cb_reflections.vecProbes [smLocalFloat413.y].vPosition.xyz;
            smLocalFloat417.xyz = - smLocalFloat416.xyz + smLocalFloat45.xyz;
            smLocalFloat413.w = dot (smLocalFloat417.xyz, smLocalFloat417.xyz);
            smLocalFloat416.xyz = cb_reflections.vecProbes [smLocalFloat413.y].vGpuPosition.xyz + - smLocalFloat416.xyz;
            smLocalFloat416.xyz = - cb_reflections.vecProbes [smLocalFloat413.y].vGpuExtents.xyz + abs (smLocalFloat416.xyz);
            smLocalFloat417.xyz = max (float3 (0, 0, 0), smLocalFloat416.xyz);
            smLocalFloat415.w = dot (smLocalFloat417.xyz, smLocalFloat417.xyz);
            smLocalFloat415.w = sqrt (smLocalFloat415.w);
            smLocalFloat416.x = max (smLocalFloat416.x, smLocalFloat416.y);
            smLocalFloat416.x = max (smLocalFloat416.x, smLocalFloat416.z);
            smLocalFloat416.x = min (0, smLocalFloat416.x);
            smLocalFloat415.w = smLocalFloat416.x + smLocalFloat415.w;
            smLocalFloat415.w = - cb_reflections.vecProbes [smLocalFloat413.y].fGpuMargin + smLocalFloat415.w;
            smLocalFloat413.y = saturate (cb_reflections.vecProbes [smLocalFloat413.y].fGpuMarginRcp * - smLocalFloat415.w);
            smLocalFloat414.y = dot (smLocalFloat44.yzw, smLocalFloat414.yzw);
            smLocalFloat414.y = smLocalFloat414.y * 0.5 + 0.5;
            smLocalFloat414.y = smLocalFloat414.y * smLocalFloat414.y;
            smLocalFloat413.w = 0.000244140625 * smLocalFloat413.w;
            smLocalFloat413.w = min (1, smLocalFloat413.w);
            smLocalFloat413.w = 1 + - smLocalFloat413.w;
            smLocalFloat413.w = smLocalFloat413.w * smLocalFloat413.w;
            smLocalFloat413.w = smLocalFloat413.w * smLocalFloat413.y;
            smLocalFloat413.w = smLocalFloat413.w * smLocalFloat414.y;
            smLocalFloat413.w = smLocalFloat413.w * smLocalFloat413.z;
            smLocalFloat413.w = smLocalFloat413.w * 10 + 1;
            smLocalFloat413.y = max (smLocalFloat413.y, smLocalFloat40.w);
            smLocalFloat413.y = smLocalFloat413.y * smLocalFloat413.z;
            smLocalFloat413.y = smLocalFloat413.y * smLocalFloat414.y;
            smLocalFloat413.y = smLocalFloat413.w * smLocalFloat413.y;
            smLocalFloat413.z = smLocalFloat413.y * smLocalFloat414.x;
            smLocalFloat411.w = smLocalFloat413.y * smLocalFloat414.x + smLocalFloat411.w;
            smLocalFloat413.y = cmp (0 < smLocalFloat413.y);
            smLocalFloat413.y = smLocalFloat413.y ? 1.000000 : 0;
            smLocalFloat412.w = smLocalFloat414.x * smLocalFloat413.y + smLocalFloat412.w;
            smLocalFloat414.xyz = smLocalFloat415.xyz * smLocalFloat413.zzz;
            smLocalFloat410.xyz = smLocalFloat414.xyz * smLocalFloat413.yyy + smLocalFloat410.xyz;
          }
        }
      }
      smLocalFloat47.xyz = smLocalFloat410.xyz;
      smLocalFloat49.xyz = smLocalFloat412.xyz;
      smLocalFloat42.w = smLocalFloat410.w;
      smLocalFloat43.w = smLocalFloat411.w;
      smLocalFloat44.x = smLocalFloat412.w;
    }
    smLocalFloat40.w = max (0.125, smLocalFloat43.w);
    smLocalFloat44.yzw = smLocalFloat47.xyz / smLocalFloat40.www;
    smLocalFloat40.w = max (0.00100000005, smLocalFloat42.w);
    smLocalFloat45.xyz = smLocalFloat49.xyz / smLocalFloat40.www;
    smLocalFloat44.x = saturate (smLocalFloat44.x);
    smLocalFloat40.w = smLocalFloat44.x * smLocalFloat44.x;
    smLocalFloat44.xyz = - smLocalFloat45.xyz + smLocalFloat44.yzw;
    smLocalFloat44.xyz = smLocalFloat40.www * smLocalFloat44.xyz + smLocalFloat45.xyz;
  }
  else {
    smLocalFloat48.xyz = cb_vDirectionalLightColor.xyz;
    smLocalFloat411.xyz = float3 (0, 0, 0);
    smLocalFloat44.xyz = float3 (0, 0, 0);
  }
  smLocalFloat45.xyz = smLocalFloat411.xyz + smLocalFloat48.xyz;
  smLocalFloat42.xyz = smLocalFloat45.xyz * smLocalFloat42.xyz;
  smLocalFloat44.xyz = smLocalFloat44.xyz * smLocalFloat40.yyy + - smLocalFloat42.xyz;
  smLocalFloat42.xyz = smLocalFloat40.yyy * smLocalFloat44.xyz + smLocalFloat42.xyz;
  smLocalFloat40.yzw = smLocalFloat45.xyz * smLocalFloat40.zzz + smLocalFloat42.xyz;
  smLocalFloat41.z = cmp (0.00100000005 < smLocalFloat40.x);
  if (smLocalFloat41.z != 0) {
    smLocalFloat41.z = - smLocalFloat41.w * smLocalFloat41.w + 1;
    smLocalFloat41.z = - smLocalFloat41.z * 0.565323055 + 1;
    smLocalFloat41.z = sqrt (smLocalFloat41.z);
    smLocalFloat41.z = smLocalFloat41.w * - 0.751879692 + - smLocalFloat41.z;
    smLocalFloat41.xy = smLocalFloat41.zz * smLocalFloat41.xy;
    smLocalFloat41.xy = smLocalFloat43.xy * float2 (0.751879692, 0.751879692) + smLocalFloat41.xy;
    smLocalFloat41.z = 0.100000001 * cb_fProjectionScale;
    smLocalFloat41.w = max (9.99999997e-07, - smin_view_position0.z);
    smLocalFloat41.z = smLocalFloat41.z / smLocalFloat41.w;
    smLocalFloat41.xy = smLocalFloat41.xy * smLocalFloat41.zz;
    smLocalFloat41.xy = cb_vContainerPixelSize.xy * smLocalFloat41.xy;
    smLocalFloat41.xy = smLocalFloat41.xy * cb_vRenderScale.xy + smin_screen_uv0.xy;
    smLocalFloat41.xyz = tFrame.Sample (LinearClampClamp_s, smLocalFloat41.xy).xyz;
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
