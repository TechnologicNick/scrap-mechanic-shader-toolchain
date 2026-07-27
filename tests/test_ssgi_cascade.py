from shader_toolchain.recipes.common import asset
from shader_toolchain.recipes.ssgi_cascade import (
    _lift_cascade_quad_contributions,
)


def test_cascade_asset_exposes_typed_quad_and_contribution_helpers() -> None:
    source = asset("ssgi_cascade_primitives.hlsl")
    assert "struct CascadeQuad" in source
    assert "struct CascadeContribution" in source
    assert "CascadeQuad DecodeCascadeQuad" in source
    assert "CascadeContribution ResolveCascadeContribution" in source
    assert source.count("// SM_COVERAGE_CANARY: cascade_contribution") == 1


def test_weighted_gather_cluster_becomes_one_typed_contribution() -> None:
    source = """  // Decode the gathered 6:5:5 indirect-light words.
  colorState.xyz = DecodeCascadeIndirect((uint)packedState.x);
  sampleOne.xyz = DecodeCascadeIndirect((uint)packedState.y);
  sampleTwo.xyz = DecodeCascadeIndirect((uint)packedState.z);
  sampleThree.xyz = DecodeCascadeIndirect((uint)packedState.w);
  weights.xyzw = float4(0.25,0.25,0.25,0.25) * rawWeights.xyzw;
  weightSum.x = weights.x + weights.y;
  weightSum.x = rawWeights.z * 0.25 + weightSum.x;
  weightSum.x = rawWeights.w * 0.25 + weightSum.x;
  totalWeight.x = weightSum.x + totalWeight.x;
  scratch.xyz = weights.yyy * sampleOne.xyz;
  scratch.xyz = colorState.xyz * weights.xxx + scratch.xyz;
  nextScratch.xyz = sampleTwo.xyz * weights.zzz + scratch.xyz;
  nextScratch.xyz = sampleThree.xyz * weights.www + nextScratch.xyz;
  totalColor.xyz = nextScratch.xyz + totalColor.xyz;
"""

    lifted = _lift_cascade_quad_contributions(source)

    assert "CascadeContribution filteredNeighborhood0" in lifted
    assert "ResolveCascadeContribution(" in lifted
    assert "(uint4)packedState, rawWeights.xyzw);" in lifted
    assert "totalWeight.x = filteredNeighborhood0.weight + totalWeight.x;" in lifted
    assert "totalColor.xyz = filteredNeighborhood0.indirect + totalColor.xyz;" in lifted
    assert "DecodeCascadeIndirect" not in lifted
