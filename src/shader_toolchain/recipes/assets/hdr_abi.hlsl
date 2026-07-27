cbuffer cb_hdr_settings : register(b9)
{
    struct
    {
        float average;
        float minimum;
        float maximum;
        float hdrSignal;
        float averageTarget;
        float minimumTarget;
        float maximumTarget;
        float hdrSignalTarget;
        float low;
        float high;
        float lowTarget;
        float highTarget;
        float3 averageColor;
        float exponent;
        float glowy;
        float glowyTarget;
        float baseValue;
        float inverseRange;
        float maximumDepth;
        float previousMaximumDepth;
        float maximumDepthTarget;
        float previousPreviousMaximumDepth;
        float maximumDepthTarget2;
        float maximumDepthTarget3;
        float maximumDepthTarget4;
        float maximumDepthTarget5;
    } hdr : packoffset(c0);
}
