// Synthesized semantic family: transparent_surface_water_tangent_map_dissolve_uv0_fog_cutoff
// Policy: quality=default, reflection=off
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
  smLocalFloat44.xzw = - cb_vDirectionalLightDirectionView.xyz * smLocalFloat40.zzz + smLocalFloat43.xyz;
  smLocalFloat40.z = dot (smLocalFloat44.xzw, smLocalFloat44.xzw);
}

void EvaluateTransparentSurfaceWaterTangentMapDissolveUv0FogCutoffPolicy2(
  inout float4 smLocalFloat40, inout float4 smLocalFloat41, inout float4 smLocalFloat44, inout float4 smLocalFloat45)
{
  smLocalFloat44.xzw = smLocalFloat44.xzw * smLocalFloat40.zzz;
  smLocalFloat40.z = dot (smLocalFloat44.xzw, smLocalFloat41.xyz);
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
    smLocalFloat43.xyz = viewToWorld._m01_m11_m21 * smin_view_position0.yyy;
    smLocalFloat43.xyz = viewToWorld._m00_m10_m20 * smin_view_position0.xxx + smLocalFloat43.xyz;
    smLocalFloat43.xyz = viewToWorld._m02_m12_m22 * smin_view_position0.zzz + smLocalFloat43.xyz;
    smLocalFloat43.xyz = viewToWorld._m03_m13_m23 + smLocalFloat43.xyz;
    smLocalFloat44.xyz = ddx_coarse (smLocalFloat43.xyz);
    smLocalFloat44.xyz = smLocalFloat44.xyz + smLocalFloat43.xyz;
    smLocalFloat45.xyz = ddy_coarse (smLocalFloat43.xyz);
    smLocalFloat44.xyz = smLocalFloat45.xyz + smLocalFloat44.xyz;
    smLocalFloat40.w = saturate (6.66666651 * smLocalFloat40.w);
    smLocalFloat40.w = 1 + - smLocalFloat40.w;
    smLocalFloat45.xy = cb_vInvRenderScale.xy * smin_screen_uv0.xy;
    smLocalFloat41.w = - smin_view_position0.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    smLocalFloat41.w = rsqrt (smLocalFloat41.w);
    smLocalFloat41.w = 1 / smLocalFloat41.w;
    smLocalFloat41.w = cb_cluster.vVoxelDims.z * smLocalFloat41.w;
    smLocalFloat41.w = floor (smLocalFloat41.w);
    smLocalFloat41.w = (uint) smLocalFloat41.w;
    smLocalFloat45.xy = cb_cluster.vVoxelDims.xy * smLocalFloat45.xy;
    smLocalFloat45.xy = (uint2) smLocalFloat45.xy;
    smLocalFloat42.w = mad ((int) smLocalFloat45.y, asint (cb_cluster.uClusterWidth), (int) smLocalFloat45.x);
    smLocalFloat41.w = mad ((int) smLocalFloat41.w, asint (cb_cluster.uClusterSliceSize), (int) smLocalFloat42.w);
    smLocalFloat42.w = (int) smLocalFloat41.w * 33;
    smLocalFloat42.w = sbVoxelLightIds [smLocalFloat42.w].x;
    smLocalFloat41.w = mad ((int) smLocalFloat41.w, 33, 1);
    smLocalFloat45.xyz = (int3) smLocalFloat42.www & int3 (255, 0xff00, 0xff0000);
    smLocalFloat46.xyz = cb_vDirectionalLightColor.xyz;
    smLocalFloat42.w = smLocalFloat45.x;
    while (true) {
      if (smLocalFloat42.w == 0) break;
      smLocalFloat43.w = firstbitlow ((uint) smLocalFloat42.w);
      smLocalFloat44.w = (int) smLocalFloat41.w + (int) smLocalFloat43.w;
      smLocalFloat45.w = 1 << (int) smLocalFloat43.w;
      smLocalFloat42.w = (int) smLocalFloat42.w ^ (int) smLocalFloat45.w;
      smLocalFloat44.w = sbVoxelLightIds [smLocalFloat44.w].x;
      smLocalFloat43.w = (uint) smLocalFloat43.w << 5;
      smLocalFloat47.xyz = smLocalFloat46.xyz;
      smLocalFloat45.w = smLocalFloat44.w;
      while (true) {
        if (smLocalFloat45.w == 0) break;
        smLocalFloat46.w = firstbitlow ((uint) smLocalFloat45.w);
        smLocalFloat47.w = (int) smLocalFloat43.w + (int) smLocalFloat46.w;
        smLocalFloat46.w = 1 << (int) smLocalFloat46.w;
        smLocalFloat45.w = (int) smLocalFloat45.w ^ (int) smLocalFloat46.w;
        smLocalFloat46.w = (uint) smLocalFloat47.w << 1;
        smLocalFloat48.xyz = cb_arrAmbient [smLocalFloat46.w].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat47.w = dot (smLocalFloat48.xyz, smLocalFloat48.xyz);
        smLocalFloat48.w = sqrt (smLocalFloat47.w);
        smLocalFloat48.w = saturate (cb_arrAmbient [smLocalFloat46.w].fRcpRadius * smLocalFloat48.w);
        smLocalFloat47.w = rsqrt (smLocalFloat47.w);
        smLocalFloat48.xyz = smLocalFloat48.xyz * smLocalFloat47.www;
        smLocalFloat47.w = dot (smLocalFloat48.xyz, smLocalFloat41.xyz);
        smLocalFloat47.w = abs (smLocalFloat47.w) * 0.5 + 0.5;
        smLocalFloat48.x = smLocalFloat48.w * smLocalFloat48.w;
        smLocalFloat48.x = - smLocalFloat48.x * smLocalFloat48.x + 1;
        smLocalFloat48.x = cb_arrAmbient [smLocalFloat46.w].fIntensity * smLocalFloat48.x;
        smLocalFloat48.x = smLocalFloat48.x * smLocalFloat40.w;
        smLocalFloat47.w = smLocalFloat48.x * smLocalFloat47.w;
        smLocalFloat48.xyz = cb_arrAmbient [smLocalFloat46.w].vColor.xyz * smLocalFloat47.www;
        smLocalFloat47.xyz = max (smLocalFloat48.xyz, smLocalFloat47.xyz);
      }
      smLocalFloat46.xyz = smLocalFloat47.xyz;
    }
    smLocalFloat47.xyz = smLocalFloat46.xyz;
    smLocalFloat48.xyz = float3 (0, 0, 0);
    smLocalFloat40.w = smLocalFloat45.y;
    while (true) {
      if (smLocalFloat40.w == 0) break;
      smLocalFloat42.w = firstbitlow ((uint) smLocalFloat40.w);
      smLocalFloat43.w = (int) smLocalFloat41.w + (int) smLocalFloat42.w;
      smLocalFloat44.w = 1 << (int) smLocalFloat42.w;
      smLocalFloat40.w = (int) smLocalFloat40.w ^ (int) smLocalFloat44.w;
      smLocalFloat43.w = sbVoxelLightIds [smLocalFloat43.w].x;
      smLocalFloat42.w = (uint) smLocalFloat42.w << 5;
      smLocalFloat49.xyz = smLocalFloat47.xyz;
      smLocalFloat410.xyz = smLocalFloat48.xyz;
      smLocalFloat44.w = smLocalFloat43.w;
      while (true) {
        if (smLocalFloat44.w == 0) break;
        smLocalFloat45.x = firstbitlow ((uint) smLocalFloat44.w);
        smLocalFloat45.w = (int) smLocalFloat42.w + (int) smLocalFloat45.x;
        smLocalFloat45.x = 1 << (int) smLocalFloat45.x;
        smLocalFloat44.w = (int) smLocalFloat44.w ^ (int) smLocalFloat45.x;
        smLocalFloat45.x = (uint) smLocalFloat45.w << 1;
        smLocalFloat45.x = (int) smLocalFloat45.x + - 512;
        smLocalFloat411.xyz = cb_arrPoint [smLocalFloat45.x].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat45.w = dot (smLocalFloat411.xyz, smLocalFloat411.xyz);
        smLocalFloat45.w = sqrt (smLocalFloat45.w);
        smLocalFloat46.w = saturate (cb_arrPoint [smLocalFloat45.x].fRcpRadius * smLocalFloat45.w);
        smLocalFloat45.w = max (0.00100000005, smLocalFloat45.w);
        smLocalFloat411.xyz = smLocalFloat411.xyz / smLocalFloat45.www;
        smLocalFloat45.w = dot (smLocalFloat411.xyz, smLocalFloat41.xyz);
        smLocalFloat45.w = abs (smLocalFloat45.w) * 0.75 + 0.25;
        smLocalFloat46.w = max (0.00999999978, smLocalFloat46.w);
        smLocalFloat46.w = log2 (smLocalFloat46.w);
        smLocalFloat46.w = cb_arrPoint [smLocalFloat45.x].fFalloffFactor * smLocalFloat46.w;
        smLocalFloat46.w = exp2 (smLocalFloat46.w);
        smLocalFloat46.w = 1 + - smLocalFloat46.w;
        smLocalFloat46.w = cb_arrPoint [smLocalFloat45.x].fIntensity * smLocalFloat46.w;
        smLocalFloat46.w = min (cb_arrPoint [smLocalFloat45.x].fMaxIntensity, smLocalFloat46.w);
        smLocalFloat47.w = asuint (cb_arrPoint [smLocalFloat45.x].uColor) >> 24;
        smLocalFloat47.w = (uint) smLocalFloat47.w;
        smLocalFloat411.x = smLocalFloat47.w * smLocalFloat45.w;
        if (8 == 0) smLocalFloat412.x = 0;
        else if (8 + 16 < 32) {
          smLocalFloat412.x = (uint) cb_arrPoint [smLocalFloat45.x].uColor << (32 - (8 + 16));
          smLocalFloat412.x = (uint) smLocalFloat412.x >> (32 - 8);
        }
        else smLocalFloat412.x = (uint) cb_arrPoint [smLocalFloat45.x].uColor >> 16;
        if (8 == 0) smLocalFloat412.y = 0;
        else if (8 + 8 < 32) {
          smLocalFloat412.y = (uint) cb_arrPoint [smLocalFloat45.x].uColor << (32 - (8 + 8));
          smLocalFloat412.y = (uint) smLocalFloat412.y >> (32 - 8);
        }
        else smLocalFloat412.y = (uint) cb_arrPoint [smLocalFloat45.x].uColor >> 8;
        smLocalFloat412.xy = (uint2) smLocalFloat412.xy;
        smLocalFloat411.yz = smLocalFloat412.xy * smLocalFloat45.ww;
        smLocalFloat411.xyz = smLocalFloat411.xyz * smLocalFloat46.www;
        smLocalFloat411.xyz = float3 (0.00392156886, 0.00392156886, 0.00392156886) * smLocalFloat411.xyz;
        smLocalFloat45.x = 1 & asint (cb_arrPoint [smLocalFloat45.x].uColor);
        smLocalFloat412.xyz = max (float3 (0, 0, 0), smLocalFloat411.xyz);
        smLocalFloat412.xyz = smLocalFloat412.xyz + smLocalFloat410.xyz;
        smLocalFloat411.xyz = max (smLocalFloat411.xyz, smLocalFloat49.xyz);
        smLocalFloat49.xyz = smLocalFloat45.xxx ? smLocalFloat49.xyz : smLocalFloat411.xyz;
        smLocalFloat410.xyz = smLocalFloat45.xxx ? smLocalFloat412.xyz : smLocalFloat410.xyz;
      }
      smLocalFloat47.xyz = smLocalFloat49.xyz;
      smLocalFloat48.xyz = smLocalFloat410.xyz;
    }
    smLocalFloat45.xyw = smLocalFloat47.xyz;
    smLocalFloat46.xyz = smLocalFloat48.xyz;
    smLocalFloat40.w = smLocalFloat45.z;
    while (true) {
      if (smLocalFloat40.w == 0) break;
      smLocalFloat42.w = firstbitlow ((uint) smLocalFloat40.w);
      smLocalFloat43.w = (int) smLocalFloat41.w + (int) smLocalFloat42.w;
      smLocalFloat44.w = 1 << (int) smLocalFloat42.w;
      smLocalFloat40.w = (int) smLocalFloat40.w ^ (int) smLocalFloat44.w;
      smLocalFloat43.w = sbVoxelLightIds [smLocalFloat43.w].x;
      smLocalFloat42.w = (uint) smLocalFloat42.w << 5;
      smLocalFloat49.xyz = smLocalFloat45.xyw;
      smLocalFloat410.xyz = smLocalFloat46.xyz;
      smLocalFloat44.w = smLocalFloat43.w;
      while (true) {
        if (smLocalFloat44.w == 0) break;
        smLocalFloat46.w = firstbitlow ((uint) smLocalFloat44.w);
        smLocalFloat47.w = (int) smLocalFloat42.w + (int) smLocalFloat46.w;
        smLocalFloat46.w = 1 << (int) smLocalFloat46.w;
        smLocalFloat44.w = (int) smLocalFloat44.w ^ (int) smLocalFloat46.w;
        smLocalFloat46.w = mad ((int) smLocalFloat47.w, 9, - 4608);
        smLocalFloat411.xyz = cb_arrSpot [smLocalFloat46.w].vPosition.xyz + - smin_view_position0.xyz;
        smLocalFloat47.w = dot (smLocalFloat411.xyz, smLocalFloat411.xyz);
        smLocalFloat47.w = sqrt (smLocalFloat47.w);
        smLocalFloat48.w = cb_arrSpot [smLocalFloat46.w].fRcpRange * smLocalFloat47.w;
        smLocalFloat49.w = cmp (1 >= smLocalFloat48.w);
        if (smLocalFloat49.w != 0) {
          smLocalFloat47.w = max (0.00100000005, smLocalFloat47.w);
          smLocalFloat411.xyz = smLocalFloat411.xyz / smLocalFloat47.www;
          smLocalFloat47.w = dot (- smLocalFloat411.xyz, cb_arrSpot [smLocalFloat46.w].vForward.xyz);
          smLocalFloat49.w = cmp (0 < smLocalFloat47.w);
          if (smLocalFloat49.w != 0) {
            smLocalFloat49.w = dot (smLocalFloat411.xyz, smLocalFloat41.xyz);
            smLocalFloat47.w = saturate (smLocalFloat47.w * cb_arrSpot [smLocalFloat46.w].fCutoffScale + cb_arrSpot [smLocalFloat46.w].fCutoffOffset);
            smLocalFloat411.xy = int2 (240, 1) & asint (cb_arrSpot [smLocalFloat46.w].uColor);
            if (smLocalFloat411.x != 0) {
              smLocalFloat411.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m01_m11_m31 * smLocalFloat43.yyy;
              smLocalFloat411.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m00_m10_m30 * smLocalFloat43.xxx + smLocalFloat411.xzw;
              smLocalFloat411.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m02_m12_m32 * smLocalFloat43.zzz + smLocalFloat411.xzw;
              smLocalFloat411.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m03_m13_m33 + smLocalFloat411.xzw;
              smLocalFloat411.xz = smLocalFloat411.xz / smLocalFloat411.ww;
              smLocalFloat412.xy = smLocalFloat411.xz * float2 (0.5, 0.5) + float2 (0.5, 0.5);
              smLocalFloat411.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m01_m11_m31 * smLocalFloat44.yyy;
              smLocalFloat411.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m00_m10_m30 * smLocalFloat44.xxx + smLocalFloat411.xzw;
              smLocalFloat411.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m02_m12_m32 * smLocalFloat44.zzz + smLocalFloat411.xzw;
              smLocalFloat411.xzw = cb_arrSpot [smLocalFloat46.w].xClip._m03_m13_m33 + smLocalFloat411.xzw;
              smLocalFloat411.xz = smLocalFloat411.xz / smLocalFloat411.ww;
              smLocalFloat411.xz = smLocalFloat411.xz * float2 (0.5, 0.5) + float2 (0.5, 0.5);
              smLocalFloat411.xz = smLocalFloat412.xy + - smLocalFloat411.xz;
              if (4 == 0) smLocalFloat410.w = 0;
              else if (4 + 4 < 32) {
                smLocalFloat410.w = (uint) cb_arrSpot [smLocalFloat46.w].uColor << (32 - (4 + 4));
                smLocalFloat410.w = (uint) smLocalFloat410.w >> (32 - 4);
              }
              else smLocalFloat410.w = (uint) cb_arrSpot [smLocalFloat46.w].uColor >> 4;
              smLocalFloat410.w = (int) smLocalFloat410.w + - 1;
              smLocalFloat412.z = (uint) smLocalFloat410.w;
              smLocalFloat410.w = taCookies.SampleGrad (LinearClampClamp_s, smLocalFloat412.xyz, smLocalFloat411.x, smLocalFloat411.z).x;
              smLocalFloat47.w = smLocalFloat410.w * smLocalFloat47.w;
            }
            smLocalFloat410.w = cmp (0 < smLocalFloat47.w);
            smLocalFloat48.w = max (0.00999999978, smLocalFloat48.w);
            smLocalFloat48.w = log2 (smLocalFloat48.w);
            smLocalFloat48.w = cb_arrSpot [smLocalFloat46.w].fFalloffFactor * smLocalFloat48.w;
            smLocalFloat48.w = exp2 (smLocalFloat48.w);
            smLocalFloat48.w = 1 + - smLocalFloat48.w;
            smLocalFloat48.w = cb_arrSpot [smLocalFloat46.w].fIntensity * smLocalFloat48.w;
            smLocalFloat47.w = smLocalFloat48.w * smLocalFloat47.w;
            smLocalFloat47.w = min (cb_arrSpot [smLocalFloat46.w].fMaxIntensity, smLocalFloat47.w);
            smLocalFloat48.w = abs (smLocalFloat49.w) * 0.75 + 0.25;
            smLocalFloat49.w = asuint (cb_arrSpot [smLocalFloat46.w].uColor) >> 24;
            smLocalFloat49.w = (uint) smLocalFloat49.w;
            smLocalFloat412.x = smLocalFloat49.w * smLocalFloat48.w;
            if (8 == 0) smLocalFloat411.x = 0;
            else if (8 + 16 < 32) {
              smLocalFloat411.x = (uint) cb_arrSpot [smLocalFloat46.w].uColor << (32 - (8 + 16));
              smLocalFloat411.x = (uint) smLocalFloat411.x >> (32 - 8);
            }
            else smLocalFloat411.x = (uint) cb_arrSpot [smLocalFloat46.w].uColor >> 16;
            if (8 == 0) smLocalFloat411.z = 0;
            else if (8 + 8 < 32) {
              smLocalFloat411.z = (uint) cb_arrSpot [smLocalFloat46.w].uColor << (32 - (8 + 8));
              smLocalFloat411.z = (uint) smLocalFloat411.z >> (32 - 8);
            }
            else smLocalFloat411.z = (uint) cb_arrSpot [smLocalFloat46.w].uColor >> 8;
            smLocalFloat411.xz = (uint2) smLocalFloat411.xz;
            smLocalFloat412.yz = smLocalFloat411.xz * smLocalFloat48.ww;
            smLocalFloat411.xzw = smLocalFloat412.xyz * smLocalFloat47.www;
            smLocalFloat411.xzw = float3 (0.00392156886, 0.00392156886, 0.00392156886) * smLocalFloat411.xzw;
            smLocalFloat412.xyz = max (float3 (0, 0, 0), smLocalFloat411.xzw);
            smLocalFloat412.xyz = smLocalFloat412.xyz + smLocalFloat410.xyz;
            smLocalFloat411.xzw = max (smLocalFloat411.xzw, smLocalFloat49.xyz);
            smLocalFloat411.xzw = smLocalFloat411.yyy ? smLocalFloat49.xyz : smLocalFloat411.xzw;
            smLocalFloat412.xyz = smLocalFloat411.yyy ? smLocalFloat412.xyz : smLocalFloat410.xyz;
            smLocalFloat49.xyz = smLocalFloat410.www ? smLocalFloat411.xzw : smLocalFloat49.xyz;
            smLocalFloat410.xyz = smLocalFloat410.www ? smLocalFloat412.xyz : smLocalFloat410.xyz;
          }
        }
      }
      smLocalFloat45.xyw = smLocalFloat49.xyz;
      smLocalFloat46.xyz = smLocalFloat410.xyz;
    }
  }
  else {
    smLocalFloat45.xyw = cb_vDirectionalLightColor.xyz;
    smLocalFloat46.xyz = float3 (0, 0, 0);
  }
  smLocalFloat41.xyz = smLocalFloat46.xyz + smLocalFloat45.xyw;
  smLocalFloat42.xyz = smLocalFloat42.xyz * smLocalFloat41.xyz;
  smLocalFloat42.xyz = smLocalFloat40.yyy * - smLocalFloat42.xyz + smLocalFloat42.xyz;
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
