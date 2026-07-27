cbuffer CB_OVERLAY
{
    struct
    {
        float fAlpha;
        float fDepthOffset;
        float2 _padd0;
    } cb_overlay : packoffset(c0);
}
