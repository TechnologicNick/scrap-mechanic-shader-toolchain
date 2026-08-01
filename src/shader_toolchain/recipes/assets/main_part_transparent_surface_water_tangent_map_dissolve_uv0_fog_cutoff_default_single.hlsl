// Synthesized semantic family: transparent_surface_water_tangent_map_dissolve_uv0_fog_cutoff
// Policy: quality=default, reflection=single
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
  smLocalFloat40.w = dot (- smLocalFloat43.xyz, smLocalFloat41.xyz);
  smLocalFloat40.w = smLocalFloat40.w + smLocalFloat40.w;
  smLocalFloat43.xyz = smLocalFloat41.xyz * - smLocalFloat40.www + - smLocalFloat43.xyz;
  smLocalFloat44.yzw = viewToWorld._m01_m11_m21 * smLocalFloat43.yyy;
  smLocalFloat43.xyw = viewToWorld._m00_m10_m20 * smLocalFloat43.xxx + smLocalFloat44.yzw;
  smLocalFloat43.xyz = viewToWorld._m02_m12_m22 * smLocalFloat43.zzz + smLocalFloat43.xyw;
  smLocalFloat40.w = max (0.00999999978, smLocalFloat44.x);
  smLocalFloat40.w = rsqrt (smLocalFloat40.w);
  smLocalFloat40.w = 1 / smLocalFloat40.w;
  smLocalFloat40.w = 5 * smLocalFloat40.w;
  smLocalFloat41.w = abs (smLocalFloat43.x) + abs (smLocalFloat43.y);
  smLocalFloat41.w = smLocalFloat41.w + abs (smLocalFloat43.z);
  smLocalFloat41.w = max (9.99999975e-05, smLocalFloat41.w);
  smLocalFloat41.w = rcp (smLocalFloat41.w);
  smLocalFloat43.xy = smLocalFloat43.xy * smLocalFloat41.ww;
  smLocalFloat44.xy = float2 (1, 1) + - abs (smLocalFloat43.yx);
  smLocalFloat44.zw = cmp (smLocalFloat43.xy < float2 (0, 0));
  smLocalFloat44.xy = smLocalFloat44.zw ? - smLocalFloat44.xy : smLocalFloat44.xy;
  smLocalFloat41.w = cmp (0 >= smLocalFloat43.z);
  smLocalFloat43.xy = smLocalFloat41.ww ? smLocalFloat44.xy : smLocalFloat43.xy;
  smLocalFloat43.xy = float2 (- 2, 2) + smLocalFloat43.xy;
  smLocalFloat41.w = max (abs (smLocalFloat43.x), abs (smLocalFloat43.y));
  smLocalFloat41.w = cmp (smLocalFloat41.w >= 1);
  smLocalFloat43.xy = smLocalFloat41.ww ? - smLocalFloat43.xy : smLocalFloat43.xy;
  smLocalFloat43.xy = smLocalFloat43.xy * float2 (0.5, 0.5) + float2 (0.5, 0.5);
  smLocalFloat43.z = 0;
  smLocalFloat43.xyz = taReflection.SampleLevel (LinearMirrorMirror_s, smLocalFloat43.xyz, smLocalFloat40.w).xyz;
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffClusteredLightingAndSpotCookieAndFrameComposition0(
  float3 smin_view_position0, float3 smin_screen_uv0, float4 smin_fog_color0, inout float4 smout_sv_target0, inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat42, inout float4 smLocalFloat43, inout float4 smLocalFloat44, inout float4 smLocalFloat45, inout float4 smLocalFloat46, inout float4 smLocalFloat47, inout float4 smLocalFloat48, inout float4 smLocalFloat49, inout float4 smLocalFloat410, inout float4 smLocalFloat411, inout float4 smLocalFloat412, inout float4 smLocalFloat413, inout float4 smLocalFloat414, inout float4 smLocalFloat415, inout float4 smLocalFloat416, inout float4 smLocalFloat417)
{
  if (smLocalFloat40.w != 0) {
    smLocalFloat40.w = cb_vInverseCameraRange.x * - smin_view_position0.z;
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
    smLocalFloat41.w = - smin_view_position0.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    smLocalFloat41.w = rsqrt (smLocalFloat41.w);
    smLocalFloat41.w = 1 / smLocalFloat41.w;
    smLocalFloat41.w = cb_cluster.vVoxelDims.z * smLocalFloat41.w;
    smLocalFloat41.w = floor (smLocalFloat41.w);
    smLocalFloat41.w = (uint) smLocalFloat41.w;
    smLocalFloat46.xy = cb_cluster.vVoxelDims.xy * smLocalFloat46.xy;
    smLocalFloat46.xy = (uint2) smLocalFloat46.xy;
    smLocalFloat42.w = mad ((int) smLocalFloat46.y, asint (cb_cluster.uClusterWidth), (int) smLocalFloat46.x);
    smLocalFloat41.w = mad ((int) smLocalFloat41.w, asint (cb_cluster.uClusterSliceSize), (int) smLocalFloat42.w);
    smLocalFloat42.w = (int) smLocalFloat41.w * 33;
    smLocalFloat42.w = sbVoxelLightIds [smLocalFloat42.w].x;
    smLocalFloat41.w = mad ((int) smLocalFloat41.w, 33, 1);
    smLocalFloat46.xyz = (int3) smLocalFloat42.www & int3 (255, 0xff00, 0xff0000);
    smLocalFloat47.xyz = cb_vDirectionalLightColor.xyz;
    smLocalFloat42.w = smLocalFloat46.x;
    while (true) {
      if (smLocalFloat42.w == 0) break;
      smLocalFloat43.w = firstbitlow ((uint) smLocalFloat42.w);
      smLocalFloat44.w = (int) smLocalFloat41.w + (int) smLocalFloat43.w;
      smLocalFloat45.w = 1 << (int) smLocalFloat43.w;
      smLocalFloat42.w = (int) smLocalFloat42.w ^ (int) smLocalFloat45.w;
      smLocalFloat44.w = sbVoxelLightIds [smLocalFloat44.w].x;
      smLocalFloat43.w = (uint) smLocalFloat43.w << 5;
      smLocalFloat48.xyz = smLocalFloat47.xyz;
      smLocalFloat45.w = smLocalFloat44.w;
      while (true) {
        if (smLocalFloat45.w == 0) break;
        smLocalFloat46.w = firstbitlow ((uint) smLocalFloat45.w);
        smLocalFloat47.w = (int) smLocalFloat43.w + (int) smLocalFloat46.w;
        smLocalFloat46.w = 1 << (int) smLocalFloat46.w;
        smLocalFloat45.w = (int) smLocalFloat45.w ^ (int) smLocalFloat46.w;
        smLocalFloat46.w = (uint) smLocalFloat47.w << 1;
        smLocalFloat49.xyz = cb_arrAmbient [smLocalFloat46.w].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat47.w = dot (smLocalFloat49.xyz, smLocalFloat49.xyz);
        smLocalFloat48.w = sqrt (smLocalFloat47.w);
        smLocalFloat48.w = saturate (cb_arrAmbient [smLocalFloat46.w].fRcpRadius * smLocalFloat48.w);
        smLocalFloat47.w = rsqrt (smLocalFloat47.w);
        smLocalFloat49.xyz = smLocalFloat49.xyz * smLocalFloat47.www;
        smLocalFloat47.w = dot (smLocalFloat49.xyz, smLocalFloat41.xyz);
        smLocalFloat47.w = abs (smLocalFloat47.w) * 0.5 + 0.5;
        smLocalFloat48.w = smLocalFloat48.w * smLocalFloat48.w;
        smLocalFloat48.w = - smLocalFloat48.w * smLocalFloat48.w + 1;
        smLocalFloat48.w = cb_arrAmbient [smLocalFloat46.w].fIntensity * smLocalFloat48.w;
        smLocalFloat48.w = smLocalFloat48.w * smLocalFloat40.w;
        smLocalFloat47.w = smLocalFloat48.w * smLocalFloat47.w;
        smLocalFloat49.xyz = cb_arrAmbient [smLocalFloat46.w].vColor.xyz * smLocalFloat47.www;
        smLocalFloat48.xyz = max (smLocalFloat49.xyz, smLocalFloat48.xyz);
      }
      smLocalFloat47.xyz = smLocalFloat48.xyz;
    }
    smLocalFloat48.xyz = smLocalFloat47.xyz;
    smLocalFloat49.xyz = float3 (0, 0, 0);
    smLocalFloat40.w = smLocalFloat46.y;
    while (true) {
      if (smLocalFloat40.w == 0) break;
      smLocalFloat42.w = firstbitlow ((uint) smLocalFloat40.w);
      smLocalFloat43.w = (int) smLocalFloat41.w + (int) smLocalFloat42.w;
      smLocalFloat44.w = 1 << (int) smLocalFloat42.w;
      smLocalFloat40.w = (int) smLocalFloat40.w ^ (int) smLocalFloat44.w;
      smLocalFloat43.w = sbVoxelLightIds [smLocalFloat43.w].x;
      smLocalFloat42.w = (uint) smLocalFloat42.w << 5;
      smLocalFloat410.xyz = smLocalFloat48.xyz;
      smLocalFloat411.xyz = smLocalFloat49.xyz;
      smLocalFloat44.w = smLocalFloat43.w;
      while (true) {
        if (smLocalFloat44.w == 0) break;
        smLocalFloat45.w = firstbitlow ((uint) smLocalFloat44.w);
        smLocalFloat46.x = (int) smLocalFloat42.w + (int) smLocalFloat45.w;
        smLocalFloat45.w = 1 << (int) smLocalFloat45.w;
        smLocalFloat44.w = (int) smLocalFloat44.w ^ (int) smLocalFloat45.w;
        smLocalFloat45.w = (uint) smLocalFloat46.x << 1;
        smLocalFloat45.w = (int) smLocalFloat45.w + - 512;
        smLocalFloat412.xyz = cb_arrPoint [smLocalFloat45.w].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat46.x = dot (smLocalFloat412.xyz, smLocalFloat412.xyz);
        smLocalFloat46.x = sqrt (smLocalFloat46.x);
        smLocalFloat46.w = saturate (cb_arrPoint [smLocalFloat45.w].fRcpRadius * smLocalFloat46.x);
        smLocalFloat46.x = max (0.00100000005, smLocalFloat46.x);
        smLocalFloat412.xyz = smLocalFloat412.xyz / smLocalFloat46.xxx;
        smLocalFloat46.x = dot (smLocalFloat412.xyz, smLocalFloat41.xyz);
        smLocalFloat46.x = abs (smLocalFloat46.x) * 0.75 + 0.25;
        smLocalFloat46.w = max (0.00999999978, smLocalFloat46.w);
        smLocalFloat46.w = log2 (smLocalFloat46.w);
        smLocalFloat46.w = cb_arrPoint [smLocalFloat45.w].fFalloffFactor * smLocalFloat46.w;
        smLocalFloat46.w = exp2 (smLocalFloat46.w);
        smLocalFloat46.w = 1 + - smLocalFloat46.w;
        smLocalFloat46.w = cb_arrPoint [smLocalFloat45.w].fIntensity * smLocalFloat46.w;
        smLocalFloat46.w = min (cb_arrPoint [smLocalFloat45.w].fMaxIntensity, smLocalFloat46.w);
        smLocalFloat47.w = asuint (cb_arrPoint [smLocalFloat45.w].uColor) >> 24;
        smLocalFloat47.w = (uint) smLocalFloat47.w;
        smLocalFloat412.x = smLocalFloat47.w * smLocalFloat46.x;
        if (8 == 0) smLocalFloat413.x = 0;
        else if (8 + 16 < 32) {
          smLocalFloat413.x = (uint) cb_arrPoint [smLocalFloat45.w].uColor << (32 - (8 + 16));
          smLocalFloat413.x = (uint) smLocalFloat413.x >> (32 - 8);
        }
        else smLocalFloat413.x = (uint) cb_arrPoint [smLocalFloat45.w].uColor >> 16;
        if (8 == 0) smLocalFloat413.y = 0;
        else if (8 + 8 < 32) {
          smLocalFloat413.y = (uint) cb_arrPoint [smLocalFloat45.w].uColor << (32 - (8 + 8));
          smLocalFloat413.y = (uint) smLocalFloat413.y >> (32 - 8);
        }
        else smLocalFloat413.y = (uint) cb_arrPoint [smLocalFloat45.w].uColor >> 8;
        smLocalFloat413.xy = (uint2) smLocalFloat413.xy;
        smLocalFloat412.yz = smLocalFloat413.xy * smLocalFloat46.xx;
        smLocalFloat412.xyz = smLocalFloat412.xyz * smLocalFloat46.www;
        smLocalFloat412.xyz = float3 (0.00392156886, 0.00392156886, 0.00392156886) * smLocalFloat412.xyz;
        smLocalFloat45.w = 1 & asint (cb_arrPoint [smLocalFloat45.w].uColor);
        smLocalFloat413.xyz = max (float3 (0, 0, 0), smLocalFloat412.xyz);
        smLocalFloat413.xyz = smLocalFloat413.xyz + smLocalFloat411.xyz;
        smLocalFloat412.xyz = max (smLocalFloat412.xyz, smLocalFloat410.xyz);
        smLocalFloat410.xyz = smLocalFloat45.www ? smLocalFloat410.xyz : smLocalFloat412.xyz;
        smLocalFloat411.xyz = smLocalFloat45.www ? smLocalFloat413.xyz : smLocalFloat411.xyz;
      }
      smLocalFloat48.xyz = smLocalFloat410.xyz;
      smLocalFloat49.xyz = smLocalFloat411.xyz;
    }
    smLocalFloat46.xyw = smLocalFloat48.xyz;
    smLocalFloat47.xyz = smLocalFloat49.xyz;
    smLocalFloat40.w = smLocalFloat46.z;
    while (true) {
      if (smLocalFloat40.w == 0) break;
      smLocalFloat42.w = firstbitlow ((uint) smLocalFloat40.w);
      smLocalFloat43.w = (int) smLocalFloat41.w + (int) smLocalFloat42.w;
      smLocalFloat44.w = 1 << (int) smLocalFloat42.w;
      smLocalFloat40.w = (int) smLocalFloat40.w ^ (int) smLocalFloat44.w;
      smLocalFloat43.w = sbVoxelLightIds [smLocalFloat43.w].x;
      smLocalFloat42.w = (uint) smLocalFloat42.w << 5;
      smLocalFloat410.xyz = smLocalFloat46.xyw;
      smLocalFloat411.xyz = smLocalFloat47.xyz;
      smLocalFloat44.w = smLocalFloat43.w;
      while (true) {
        if (smLocalFloat44.w == 0) break;
        smLocalFloat45.w = firstbitlow ((uint) smLocalFloat44.w);
        smLocalFloat47.w = (int) smLocalFloat42.w + (int) smLocalFloat45.w;
        smLocalFloat45.w = 1 << (int) smLocalFloat45.w;
        smLocalFloat44.w = (int) smLocalFloat44.w ^ (int) smLocalFloat45.w;
        smLocalFloat45.w = mad ((int) smLocalFloat47.w, 9, - 4608);
        smLocalFloat412.xyz = cb_arrSpot [smLocalFloat45.w].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat47.w = dot (smLocalFloat412.xyz, smLocalFloat412.xyz);
        smLocalFloat47.w = sqrt (smLocalFloat47.w);
        smLocalFloat48.w = cb_arrSpot [smLocalFloat45.w].fRcpRange * smLocalFloat47.w;
        smLocalFloat49.w = cmp (1 >= smLocalFloat48.w);
        if (smLocalFloat49.w != 0) {
          smLocalFloat47.w = max (0.00100000005, smLocalFloat47.w);
          smLocalFloat412.xyz = smLocalFloat412.xyz / smLocalFloat47.www;
          smLocalFloat47.w = dot (- smLocalFloat412.xyz, cb_arrSpot [smLocalFloat45.w].vForward.xyz);
          smLocalFloat49.w = cmp (0 < smLocalFloat47.w);
          if (smLocalFloat49.w != 0) {
            smLocalFloat49.w = dot (smLocalFloat412.xyz, smLocalFloat41.xyz);
            smLocalFloat47.w = saturate (smLocalFloat47.w * cb_arrSpot [smLocalFloat45.w].fCutoffScale + cb_arrSpot [smLocalFloat45.w].fCutoffOffset);
            smLocalFloat412.xy = int2 (240, 1) & asint (cb_arrSpot [smLocalFloat45.w].uColor);
            if (smLocalFloat412.x != 0) {
              smLocalFloat412.xzw = cb_arrSpot [smLocalFloat45.w].xClip._m01_m11_m31 * smLocalFloat44.yyy;
              smLocalFloat412.xzw = cb_arrSpot [smLocalFloat45.w].xClip._m00_m10_m30 * smLocalFloat44.xxx + smLocalFloat412.xzw;
              smLocalFloat412.xzw = cb_arrSpot [smLocalFloat45.w].xClip._m02_m12_m32 * smLocalFloat44.zzz + smLocalFloat412.xzw;
              smLocalFloat412.xzw = cb_arrSpot [smLocalFloat45.w].xClip._m03_m13_m33 + smLocalFloat412.xzw;
              smLocalFloat412.xz = smLocalFloat412.xz / smLocalFloat412.ww;
              smLocalFloat413.xy = smLocalFloat412.xz * float2 (0.5, 0.5) + float2 (0.5, 0.5);
              smLocalFloat412.xzw = cb_arrSpot [smLocalFloat45.w].xClip._m01_m11_m31 * smLocalFloat45.yyy;
              smLocalFloat412.xzw = cb_arrSpot [smLocalFloat45.w].xClip._m00_m10_m30 * smLocalFloat45.xxx + smLocalFloat412.xzw;
              smLocalFloat412.xzw = cb_arrSpot [smLocalFloat45.w].xClip._m02_m12_m32 * smLocalFloat45.zzz + smLocalFloat412.xzw;
              smLocalFloat412.xzw = cb_arrSpot [smLocalFloat45.w].xClip._m03_m13_m33 + smLocalFloat412.xzw;
              smLocalFloat412.xz = smLocalFloat412.xz / smLocalFloat412.ww;
              smLocalFloat412.xz = smLocalFloat412.xz * float2 (0.5, 0.5) + float2 (0.5, 0.5);
              smLocalFloat412.xz = smLocalFloat413.xy + - smLocalFloat412.xz;
              if (4 == 0) smLocalFloat410.w = 0;
              else if (4 + 4 < 32) {
                smLocalFloat410.w = (uint) cb_arrSpot [smLocalFloat45.w].uColor << (32 - (4 + 4));
                smLocalFloat410.w = (uint) smLocalFloat410.w >> (32 - 4);
              }
              else smLocalFloat410.w = (uint) cb_arrSpot [smLocalFloat45.w].uColor >> 4;
              smLocalFloat410.w = (int) smLocalFloat410.w + - 1;
              smLocalFloat413.z = (uint) smLocalFloat410.w;
              smLocalFloat410.w = taCookies.SampleGrad (LinearClampClamp_s, smLocalFloat413.xyz, smLocalFloat412.x, smLocalFloat412.z).x;
              smLocalFloat47.w = smLocalFloat410.w * smLocalFloat47.w;
            }
            smLocalFloat410.w = cmp (0 < smLocalFloat47.w);
            smLocalFloat48.w = max (0.00999999978, smLocalFloat48.w);
            smLocalFloat48.w = log2 (smLocalFloat48.w);
            smLocalFloat48.w = cb_arrSpot [smLocalFloat45.w].fFalloffFactor * smLocalFloat48.w;
            smLocalFloat48.w = exp2 (smLocalFloat48.w);
            smLocalFloat48.w = 1 + - smLocalFloat48.w;
            smLocalFloat48.w = cb_arrSpot [smLocalFloat45.w].fIntensity * smLocalFloat48.w;
            smLocalFloat47.w = smLocalFloat48.w * smLocalFloat47.w;
            smLocalFloat47.w = min (cb_arrSpot [smLocalFloat45.w].fMaxIntensity, smLocalFloat47.w);
            smLocalFloat48.w = abs (smLocalFloat49.w) * 0.75 + 0.25;
            smLocalFloat49.w = asuint (cb_arrSpot [smLocalFloat45.w].uColor) >> 24;
            smLocalFloat49.w = (uint) smLocalFloat49.w;
            smLocalFloat413.x = smLocalFloat49.w * smLocalFloat48.w;
            if (8 == 0) smLocalFloat412.x = 0;
            else if (8 + 16 < 32) {
              smLocalFloat412.x = (uint) cb_arrSpot [smLocalFloat45.w].uColor << (32 - (8 + 16));
              smLocalFloat412.x = (uint) smLocalFloat412.x >> (32 - 8);
            }
            else smLocalFloat412.x = (uint) cb_arrSpot [smLocalFloat45.w].uColor >> 16;
            if (8 == 0) smLocalFloat412.z = 0;
            else if (8 + 8 < 32) {
              smLocalFloat412.z = (uint) cb_arrSpot [smLocalFloat45.w].uColor << (32 - (8 + 8));
              smLocalFloat412.z = (uint) smLocalFloat412.z >> (32 - 8);
            }
            else smLocalFloat412.z = (uint) cb_arrSpot [smLocalFloat45.w].uColor >> 8;
            smLocalFloat412.xz = (uint2) smLocalFloat412.xz;
            smLocalFloat413.yz = smLocalFloat412.xz * smLocalFloat48.ww;
            smLocalFloat412.xzw = smLocalFloat413.xyz * smLocalFloat47.www;
            smLocalFloat412.xzw = float3 (0.00392156886, 0.00392156886, 0.00392156886) * smLocalFloat412.xzw;
            smLocalFloat413.xyz = max (float3 (0, 0, 0), smLocalFloat412.xzw);
            smLocalFloat413.xyz = smLocalFloat413.xyz + smLocalFloat411.xyz;
            smLocalFloat412.xzw = max (smLocalFloat412.xzw, smLocalFloat410.xyz);
            smLocalFloat412.xzw = smLocalFloat412.yyy ? smLocalFloat410.xyz : smLocalFloat412.xzw;
            smLocalFloat413.xyz = smLocalFloat412.yyy ? smLocalFloat413.xyz : smLocalFloat411.xyz;
            smLocalFloat410.xyz = smLocalFloat410.www ? smLocalFloat412.xzw : smLocalFloat410.xyz;
            smLocalFloat411.xyz = smLocalFloat410.www ? smLocalFloat413.xyz : smLocalFloat411.xyz;
          }
        }
      }
      smLocalFloat46.xyw = smLocalFloat410.xyz;
      smLocalFloat47.xyz = smLocalFloat411.xyz;
    }
  }
  else {
    smLocalFloat46.xyw = cb_vDirectionalLightColor.xyz;
    smLocalFloat47.xyz = float3 (0, 0, 0);
  }
  smLocalFloat41.xyz = smLocalFloat47.xyz + smLocalFloat46.xyw;
  smLocalFloat42.xyz = smLocalFloat42.xyz * smLocalFloat41.xyz;
  smLocalFloat43.xyz = smLocalFloat43.xyz * smLocalFloat40.yyy + - smLocalFloat42.xyz;
  smLocalFloat42.xyz = smLocalFloat40.yyy * smLocalFloat43.xyz + smLocalFloat42.xyz;
  smLocalFloat40.yzw = smLocalFloat41.xyz * smLocalFloat40.zzz + smLocalFloat42.xyz;
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
