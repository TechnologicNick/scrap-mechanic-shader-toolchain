// Dissolve parameters for legacy permutations bound at b0.
cbuffer CB_DISSOLVE : register(b0)
{
  struct
  {
    float fLength;
    float fRcpFade;
    float fFadePower;
    float fLoopSpeed;
    float fLoopLength;
    float fLoopOffset;
    float2 _padd0;
    float4 vStartColor;
    float4 vEndColor;
    float fScale;
    float3 vScrollSpeed;
  } cb_dissolve : packoffset(c0);
}

