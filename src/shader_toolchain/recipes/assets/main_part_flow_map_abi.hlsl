#ifndef MAIN_PART_FLOW_MAP_ABI_HLSL
#define MAIN_PART_FLOW_MAP_ABI_HLSL

cbuffer CB_FLOW_MAP
{
  struct
  {
    float fFlowSpeed;
    float3 _padd0;
  } cb_flow_map : packoffset(c0);
}

#endif
