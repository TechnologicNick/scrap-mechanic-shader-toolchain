Texture2D<float2> tNormalIn : register(t0);
RWTexture2D<float2> tOut0 : register(u0);
RWTexture2D<float2> tOut1 : register(u1);
RWTexture2D<float2> tOut2 : register(u2);
RWTexture2D<float2> tOut3 : register(u3);

groupshared float3 groupNormals[1024];

float3 DecodeNormal(float2 encoded)
{
    float2 xy = encoded * 2.0 - 1.0;
    return normalize(float3(xy, 1.0 - abs(xy.x) - abs(xy.y)));
}

float2 EncodeNormal(float3 normal)
{
    normal /= abs(normal.x) + abs(normal.y) + abs(normal.z);
    return normal.xy * 0.5 + 0.5;
}

float3 AverageFour(float3 a, float3 b, float3 c, float3 d)
{
    float3 sum = a + b;
    sum += c;
    sum += d;
    return normalize(sum * 0.25);
}

uint SharedIndex(uint2 coordinate)
{
    return coordinate.y * 32 + coordinate.x;
}

float3 ReduceShared(uint2 localCoordinate, uint stride)
{
    float3 topLeft = groupNormals[SharedIndex(localCoordinate)];
    float3 topRight = groupNormals[SharedIndex(localCoordinate + uint2(stride, 0))];
    float3 bottomLeft = groupNormals[SharedIndex(localCoordinate + uint2(0, stride))];
    float3 bottomRight = groupNormals[
        SharedIndex(localCoordinate + uint2(stride, stride))
    ];
    return AverageFour(topLeft, topRight, bottomLeft, bottomRight);
}

[numthreads(32, 32, 1)]
void mainCS(
    uint3 dispatchThreadId : SV_DispatchThreadID,
    uint3 groupThreadId : SV_GroupThreadID
)
{
    uint2 source = dispatchThreadId.xy * 2;
    float3 normal = AverageFour(
        DecodeNormal(tNormalIn.Load(uint3(source, 0))),
        DecodeNormal(tNormalIn.Load(uint3(source + uint2(1, 0), 0))),
        DecodeNormal(tNormalIn.Load(uint3(source + uint2(0, 1), 0))),
        DecodeNormal(tNormalIn.Load(uint3(source + uint2(1, 1), 0)))
    );
    tOut0[dispatchThreadId.xy] = EncodeNormal(normal);

    uint sharedIndex = SharedIndex(groupThreadId.xy);
    groupNormals[sharedIndex] = normal;
    GroupMemoryBarrierWithGroupSync();

    if ((groupThreadId.x & 1) == 0 && (groupThreadId.y & 1) == 0)
    {
        normal = ReduceShared(groupThreadId.xy, 1);
        tOut1[dispatchThreadId.xy >> 1] = EncodeNormal(normal);
        groupNormals[sharedIndex] = normal;
    }
    GroupMemoryBarrierWithGroupSync();

    if ((groupThreadId.x & 3) == 0 && (groupThreadId.y & 3) == 0)
    {
        normal = ReduceShared(groupThreadId.xy, 2);
        tOut2[dispatchThreadId.xy >> 2] = EncodeNormal(normal);
        groupNormals[sharedIndex] = normal;
    }
    GroupMemoryBarrierWithGroupSync();

    if ((groupThreadId.x & 7) == 0 && (groupThreadId.y & 7) == 0)
    {
        normal = ReduceShared(groupThreadId.xy, 4);
        tOut3[dispatchThreadId.xy >> 3] = EncodeNormal(normal);
    }
}
