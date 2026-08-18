"""Semantic Embedding Matcher for the KG-IOT-DT Digital Twin.

Future-work variant of the thesis dual-metric integration pipeline.
Replaces the string-level Levenshtein SDF comparison with dense semantic
embeddings computed by a local embedding model (Qwen3-Embedding deployed
via Ollama on the RTX 4090), while keeping the STUMPY time-series metric.

Usage:
    python scripts/embedding_matcher.py --scenario all
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

OLLAMA_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "qwen3-embedding:4b"

# One fixed task instruction per index — Qwen3 recommends instructions for
# retrieval queries; a stable instruction keeps the score distribution consistent.
INSTRUCT = (
    "Instruct: Given a question about industrial IoT devices, robotic systems, "
    "automation equipment, sensor networks, or manufacturing, retrieve relevant "
    "technical passages.\nQuery: "
)

SDF_DIR = Path(__file__).resolve().parent.parent / "sdf"


class EmbeddingMatcher:
    """Computes dense semantic similarity between SDF device schemas."""

    def __init__(self, model: str = EMBED_MODEL, url: str = OLLAMA_URL, timeout: int = 180):
        self.model = model
        self.url = url
        self.timeout = timeout
        self._class_cache: dict[str, np.ndarray] = {}

    def embed(self, text: str) -> np.ndarray:
        """Embed a single text into a normalized vector (Ollama returns L2-normalized)."""
        payload = {"model": self.model, "input": text}
        with urllib.request.urlopen(
            urllib.request.Request(
                self.url, json.dumps(payload).encode(), {"Content-Type": "application/json"}
            ),
            timeout=self.timeout,
        ) as resp:
            data = json.loads(resp.read().decode())
        vec = np.asarray(data["embeddings"][0], dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts in one request (fast ingestion path)."""
        payload = {"model": self.model, "input": texts}
        with urllib.request.urlopen(
            urllib.request.Request(
                self.url, json.dumps(payload).encode(), {"Content-Type": "application/json"}
            ),
            timeout=self.timeout,
        ) as resp:
            data = json.loads(resp.read().decode())
        matrix = np.asarray(data["embeddings"], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-9)

    def precompute_classes(self, class_descs: dict[str, str]) -> None:
        """Pre-embed and cache all static ontology classes for ultra-fast queries."""
        keys = list(class_descs.keys())
        passages = [class_descs[k] for k in keys]
        matrix = self.embed_batch(passages)
        for i, k in enumerate(keys):
            self._class_cache[k] = matrix[i]

    @staticmethod
    def query_text(text: str) -> str:
        """Prepend the fixed retrieval instruction (query-side formatting)."""
        return INSTRUCT + text

    def similarity(self, a: str, b: str) -> float:
        """Cosine similarity between two schema descriptions (both embedded as passages)."""
        va = self.embed(a)
        vb = self.embed(b)
        return float(np.dot(va, vb))

    def similarity_matrix(self, passages: list[str]) -> np.ndarray:
        """Cosine similarity matrix across all passage pairs (single batch)."""
        m = self.embed_batch(passages)
        return m @ m.T

    def rank_candidates(
        self, query_desc: str, class_descs: dict[str, str], top_k: int = 5
    ) -> list[tuple[str, float]]:
        """Rank existing device classes against a candidate description by semantic fit."""
        if not self._class_cache or len(self._class_cache) != len(class_descs):
            self.precompute_classes(class_descs)

        q_vec = self.embed(self.query_text(query_desc))
        keys = list(class_descs.keys())
        matrix = np.stack([self._class_cache[k] for k in keys])
        sims = matrix @ q_vec
        ranked = sorted(zip(keys, sims.tolist(), strict=False), key=lambda kv: -kv[1])
        return ranked[:top_k]


def load_sdf_descriptions() -> dict[str, str]:
    """Load all SDF files and build a semantic description per device class."""
    descriptions: dict[str, str] = {}
    for sdf_file in sorted(SDF_DIR.glob("*.json")):
        try:
            sdf = json.loads(sdf_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        class_name = sdf_file.stem.replace(".sdf", "")
        # Walk the SDF structure: collect thing descriptions, object names and
        # property names with units into a single semantic description.
        parts: list[str] = []
        things = sdf.get("sdfThing") or {}
        for thing_name, thing in things.items():
            if isinstance(thing, dict):
                if thing.get("description"):
                    parts.append(thing["description"])
                objects = thing.get("sdfObject", {})
                for obj_name, obj in objects.items():
                    if isinstance(obj, dict):
                        if obj.get("description"):
                            parts.append(obj["description"])
                        props = obj.get("sdfProperty", {})
                        for prop_name, prop in props.items():
                            if not isinstance(prop, dict):
                                continue
                            unit = prop.get("unit", "")
                            desc = prop.get("description", prop_name)
                            parts.append(f"{desc} [{unit}]".replace(" []", ""))
        if parts:
            descriptions[class_name] = ". ".join(parts)
    return descriptions


def load_demo_devices() -> dict:
    """Load the demo scenario devices (new + disappeared) from JSON."""
    demo_path = Path(__file__).resolve().parent / "demo_devices.json"
    return json.loads(demo_path.read_text())


def run_scenario(name: str, matcher: EmbeddingMatcher, class_descs: dict[str, str]) -> dict:
    """Run a single demo scenario and return structured results."""
    demo = load_demo_devices()
    scenario = demo[name]
    print(f"\n=== SCENARIO: {scenario['title']} ===")
    print(f"    {scenario['description']}\n")

    results: dict = {"scenario": scenario["title"], "matches": []}

    if name == "disappearance":
        # Operational flow: a device stops publishing → we know its KG class →
        # rank incoming new devices against that class to suggest a replacement.
        for missing in scenario.get("disappeared", []):
            missing_class = missing["class"]
            class_desc = class_descs.get(missing_class, missing.get("sdf_description"))
            print(
                f"  🚫 Disappeared device: {missing['name']} ({missing_class}) — {missing['last_seen']}"
            )
            print(f"     Incoming candidates ranked against class '{missing_class}':")
            candidates = scenario.get("candidates", [])
            cand_texts = [c["sdf_description"] for c in candidates]
            sims = matcher.similarity_matrix([class_desc, *cand_texts])[0, 1:]
            ranked_cands = sorted(
                zip(candidates, sims.tolist(), strict=False), key=lambda cv: -cv[1]
            )
            suggested = None
            for cand, score in ranked_cands:
                marker = ""
                if cand.get("name") == missing.get("replacement_suggestion"):
                    marker = " 👈 suggested replacement"
                    suggested = cand
                print(f"       {score*100:6.1f}%  {cand['name']}{marker}")
            results["matches"].append(
                {
                    "disappeared": missing["name"],
                    "class": missing_class,
                    "suggested_replacement": suggested["name"]
                    if suggested
                    else ranked_cands[0][0]["name"],
                    "candidates": [
                        {"name": c["name"], "score": round(float(s), 4)} for c, s in ranked_cands
                    ],
                }
            )
        return results

    for candidate in scenario["candidates"]:
        cand_desc = candidate["sdf_description"]
        ranked = matcher.rank_candidates(cand_desc, class_descs, top_k=3)
        print(f"  📦 New device: {candidate['name']}")
        print(f"     SDF: {cand_desc[:100]}...")
        print("     Top classes:")
        best = ranked[0]
        for cls, score in ranked:
            marker = " 👈" if cls == candidate.get("expected_class") else ""
            print(f"       {score*100:6.1f}%  {cls}{marker}")
        results["matches"].append(
            {
                "name": candidate["name"],
                "sdf": cand_desc,
                "expected_class": candidate.get("expected_class"),
                "ranked": [{"class": c, "score": round(float(s), 4)} for c, s in ranked],
                "best": best[0],
                "best_score": round(float(best[1]), 4),
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Embedding-based semantic integration matcher")
    parser.add_argument(
        "--scenario",
        default="all",
        choices=["all", "replacement", "complementary", "disappearance"],
        help="Which demo scenario to run",
    )
    parser.add_argument("--model", default=EMBED_MODEL, help="Ollama embedding model tag")
    args = parser.parse_args()

    matcher = EmbeddingMatcher(model=args.model)
    class_descs = load_sdf_descriptions()
    print(f"📚 Loaded {len(class_descs)} device classes from SDF corpus:")
    for c in sorted(class_descs)[:6]:
        print(f"   - {c}")
    print(f"   ... ({len(class_descs)} total)")

    scenarios = (
        ["replacement", "complementary", "disappearance"]
        if args.scenario == "all"
        else [args.scenario]
    )
    all_results = {}
    for s in scenarios:
        all_results[s] = run_scenario(s, matcher, class_descs)

    out_path = Path(__file__).resolve().parent / "embedding_results.json"
    out_path.write_text(json.dumps(all_results, indent=2))
    print(f"\n💾 Results saved to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
