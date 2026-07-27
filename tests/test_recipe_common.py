import pytest

from shader_toolchain.recipes.common import semantic_worker_count


def test_semantic_worker_count_defaults_to_logical_cpus(monkeypatch) -> None:
    monkeypatch.delenv("SM_SHADERS_JOBS", raising=False)
    monkeypatch.setattr("shader_toolchain.recipes.common.os.cpu_count", lambda: 12)

    assert semantic_worker_count(20) == 12
    assert semantic_worker_count(4) == 4


def test_semantic_worker_count_honors_environment(monkeypatch) -> None:
    monkeypatch.setenv("SM_SHADERS_JOBS", "3")
    assert semantic_worker_count(20) == 3


@pytest.mark.parametrize("value", ["0", "-1", "many"])
def test_semantic_worker_count_rejects_invalid_environment(
    monkeypatch, value: str
) -> None:
    monkeypatch.setenv("SM_SHADERS_JOBS", value)
    with pytest.raises(RuntimeError, match="SM_SHADERS_JOBS"):
        semantic_worker_count(20)
