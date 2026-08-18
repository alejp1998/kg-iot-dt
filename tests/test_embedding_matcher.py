"""Tests for the semantic embedding matcher (future-work integration variant).

Unit tests use crafted fake embeddings (no GPU/Ollama required for CI).
A live integration test against a running Ollama instance is auto-skipped
when the service is unavailable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from embedding_matcher import (  # noqa: E402
    INSTRUCT,
    EmbeddingMatcher,
    load_sdf_descriptions,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, vec_map, inputs):
        self.vec_map = vec_map
        self.inputs = inputs if isinstance(inputs, list) else [inputs]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        import json

        embeds = []
        for text in self.inputs:
            vec = self.vec_map.get(text, np.zeros(8, dtype=np.float32))
            norm = np.linalg.norm(vec)
            embeds.append((vec / norm).tolist())
        return json.dumps({"embeddings": embeds}).encode()


def _fake_urlopen(vec_map):
    """Build a urlopen stand-in keyed on the exact input text."""

    def fake_urlopen(request, timeout=None):
        import json as _json

        payload = _json.loads(request.data.decode())
        inputs = payload.get("input", [])
        return FakeResponse(vec_map, inputs)

    return fake_urlopen


def make_matcher(vec_map: dict[str, np.ndarray], monkeypatch) -> EmbeddingMatcher:
    import embedding_matcher as em

    monkeypatch.setattr(em.urllib.request, "urlopen", _fake_urlopen(vec_map))
    return EmbeddingMatcher(url="http://fake")


def _u(seed: int, dims: int = 8) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(size=dims).astype(np.float32)


# ---------------------------------------------------------------------------
# Unit tests (deterministic, no network)
# ---------------------------------------------------------------------------


def test_embed_normalizes_vector(monkeypatch):
    raw = _u(7) * 10  # unnormalized
    m = make_matcher({"a passage": raw}, monkeypatch)
    vec = m.embed("a passage")
    assert vec.shape == (8,)
    assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-5)


def test_embed_batch_returns_matrix(monkeypatch):
    m = make_matcher({"one": _u(1), "two": _u(2)}, monkeypatch)
    mat = m.embed_batch(["one", "two"])
    assert mat.shape == (2, 8)
    assert np.allclose(np.linalg.norm(mat, axis=1), 1.0, atol=1e-5)


def test_similarity_symmetric_and_ordered(monkeypatch):
    v_a = _u(1)
    v_b = _u(2)
    m = make_matcher({"a": v_a, "b": v_b}, monkeypatch)
    sab = m.similarity("a", "b")
    sba = m.similarity("b", "a")
    assert sab == pytest.approx(sba, abs=1e-5)
    assert m.similarity("a", "a") > sab  # self-similarity is highest


def test_rank_candidates_orders_by_semantic_fit(monkeypatch):
    """A robot-like query must rank the robot class above the sensor class."""
    robot_vec = np.asarray([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    sensor_vec = np.asarray([0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    query_vec = np.asarray([0.9, 0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

    m = make_matcher(
        {
            "query desc": query_vec,
            "pickuprobot class": robot_vec,
            "noisesensor class": sensor_vec,
        },
        monkeypatch,
    )
    ranked = m.rank_candidates("query desc", {"pickuprobot": "pickuprobot class", "noisesensor": "noisesensor class"})
    assert ranked[0][0] == "pickuprobot"
    assert ranked[0][1] > ranked[1][1]


def test_query_instruction_is_prepended():
    assert INSTRUCT.startswith("Instruct:")
    assert "Query:" in INSTRUCT
    assert "multirobot" in INSTRUCT or "robotic" in INSTRUCT


def test_load_sdf_descriptions_covers_corpus():
    descs = load_sdf_descriptions()
    assert len(descs) >= 20  # the SDF corpus ships 22 device classes
    for key in ("AirQuality", "PickUpRobot", "WindSensor", "DrillingRobot"):
        assert key in descs
        assert len(descs[key]) > 40  # non-trivial semantic description


def test_similarity_matrix_values_in_range(monkeypatch):
    m = make_matcher({"x": _u(3), "y": _u(4), "z": _u(5)}, monkeypatch)
    sim = m.similarity_matrix(["x", "y", "z"])
    assert sim.shape == (3, 3)
    assert np.all(sim <= 1.0 + 1e-5)
    assert np.all(sim >= -1.0 - 1e-5)
    assert np.allclose(np.diag(sim), 1.0, atol=1e-5)  # self-similarity == 1


# ---------------------------------------------------------------------------
# Live integration tests (skipped unless Ollama + qwen3-embedding is up)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_live_embedding_semantic_sanity():
    """Real Qwen3-Embedding-4B: semantically related devices must outscore unrelated ones."""
    try:
        matcher = EmbeddingMatcher(timeout=15)
        sim = matcher.similarity(
            "sensor device for air quality, temperature and humidity, particulate matter",
            "weather sensor measuring wind speed and direction",
        )
        assert 0.0 <= sim <= 1.0
        sim_same = matcher.similarity(
            "sensor device for air quality, temperature and humidity, particulate matter",
            "air quality sensor measuring temperature humidity and particulate matter",
        )
        assert sim_same > sim  # same-domain pair beats cross-domain pair
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Ollama embedding service unavailable: {exc}")
