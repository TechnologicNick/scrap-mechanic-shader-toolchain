SamplerState LinearClamp : register(s6);
Texture2DArray<float4> diffuseImpostors : register(t0);

struct GBufferOutput
{
    float4 albedo : SV_Target0;
    float2 encodedNormal : SV_Target1;
    float4 material : SV_Target2;
};

float2 EncodeViewNormal(float3 viewNormal)
{
    float3 normal = normalize(viewNormal);
    float3 octahedron = normal.zxy / dot(abs(normal), 1.0);
    float2 wrapped = (1.0 - abs(octahedron.zy))
        * float2(octahedron.y >= 0.0 ? 1.0 : -1.0,
                 octahedron.z >= 0.0 ? 1.0 : -1.0);
    float2 encoded = octahedron.x >= 0.0 ? octahedron.yz : wrapped;
    return 0.5 * encoded + 0.5;
}

GBufferOutput mainPS(
    float4 position : SV_Position0,
    float depthFade : TEXCOORD0,
    float3 viewNormal : TEXCOORD1,
    float4 texcoord : TEXCOORD2,
    nointerpolation float3 tint : TEXCOORD3,
    nointerpolation uint4 slice : TEXCOORD4)
{
    float4 diffuse = diffuseImpostors.Sample(
        LinearClamp, float3(texcoord.xy, float(slice.w)));
    if (diffuse.a < 0.200000003)
        discard;

    GBufferOutput output;
    output.albedo = float4(tint * diffuse.rgb, 0.0);
    output.encodedNormal = EncodeViewNormal(viewNormal);
    output.material = float4(0.0700000003, 0.280000001, saturate(depthFade), 0.00784313772);
    return output;
}
