#ifndef MAIN_PART_TRANSFORM_BUFFER_VERTEX_HLSL
#define MAIN_PART_TRANSFORM_BUFFER_VERTEX_HLSL

struct MainPartBufferedLtw
{
  float4 row0;
  float4 row1;
  float4 row2;
};

float4 MainPartBufferedDirection(float3 direction, uint transformIndex)
{
  float4 value = transformArray[transformIndex]._m01_m11_m21_m31
      * direction.y;
  value = transformArray[transformIndex]._m00_m10_m20_m30
      * direction.x + value;
  value = transformArray[transformIndex]._m02_m12_m22_m32
      * direction.z + value;
  return value;
}

MainPartBufferedLtw ResolveMainPartBufferedLtw(
    float4 row0, float4 row1, float4 row2, uint4 packedInstance)
{
  uint transformIndex = packedInstance.y & 1023u;
  float4 axisX = MainPartBufferedDirection(
      float3(row0.x, row1.x, row2.x), transformIndex);
  float4 axisY = MainPartBufferedDirection(
      float3(row0.y, row1.y, row2.y), transformIndex);
  float4 axisZ = MainPartBufferedDirection(
      float3(row0.z, row1.z, row2.z), transformIndex);
  float4 origin = MainPartBufferedDirection(
      float3(row0.w, row1.w, row2.w), transformIndex);
  origin.xyz += transformArray[transformIndex]._m03_m13_m23;

  MainPartBufferedLtw result;
  result.row0 = float4(axisX.x, axisY.x, axisZ.x, origin.x);
  result.row1 = float4(axisX.y, axisY.y, axisZ.y, origin.y);
  result.row2 = float4(axisX.z, axisY.z, axisZ.z, origin.z);
  return result;
}

float MainPartBufferedLayer(uint4 packedInstance)
{
  return (float)((packedInstance.y >> 16u) & 16383u);
}

#endif // MAIN_PART_TRANSFORM_BUFFER_VERTEX_HLSL
