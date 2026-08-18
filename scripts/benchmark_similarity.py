"""Rigorous Head-to-Head Benchmark: Levenshtein/thefuzz vs Qwen3-Embedding-4B.

Evaluates semantic accuracy, top-1/top-3 recall, Mean Reciprocal Rank (MRR),
and discriminative margins across 4 test categories (Standard, Synonyms/Paraphrases,
Minimalist, and Cross-Domain Distractors).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from thefuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embedding_matcher import EmbeddingMatcher, load_sdf_descriptions  # noqa: E402

BENCHMARK_CASES = [
    # -----------------------------------------------------------------------
    # CATEGORY A: Standard / Thesis Baseline Cases (Direct Lexical Overlap)
    # -----------------------------------------------------------------------
    {
        "id": "A1",
        "category": "Standard (Direct Lexical Overlap)",
        "query_name": "indoors_airqualitysimp",
        "description": "sensor device for air quality, measures temperature in degrees celsius, humidity percentage, particulate matter pm2.5 and pm10",
        "expected_class": "AirQualitySimplified",
    },
    {
        "id": "A2",
        "category": "Standard (Direct Lexical Overlap)",
        "query_name": "bodyconfig_pickuprob2",
        "description": "industrial pick up robot joints and actuator status, x y z position and orientation in meters",
        "expected_class": "PickUpRobot",
    },
    {
        "id": "A3",
        "category": "Standard (Direct Lexical Overlap)",
        "query_name": "outdoors_windsensor2",
        "description": "weather sensor measuring wind speed in meters per second and wind direction in degrees",
        "expected_class": "WindSensor",
    },
    # -----------------------------------------------------------------------
    # CATEGORY B: Paraphrased & Industrial Synonyms (Vocabulary Mismatch)
    # -----------------------------------------------------------------------
    {
        "id": "B1",
        "category": "Synonyms & Paraphrasing (Vocab Mismatch)",
        "query_name": "AerosolParticleAnalyzer",
        "description": "ambient atmosphere pollution monitor detecting aerosol concentration, breathable microparticles, ambient thermal conditions, and relative moisture level",
        "expected_class": "AirQuality",
    },
    {
        "id": "B2",
        "category": "Synonyms & Paraphrasing (Vocab Mismatch)",
        "query_name": "RoboticManipulatorChassisArm",
        "description": "six-axis articulated robotic handler with pneumatic end-effector for transferring heavy vehicle structural components across assembly fixtures",
        "expected_class": "PickUpRobot",
    },
    {
        "id": "B3",
        "category": "Synonyms & Paraphrasing (Vocab Mismatch)",
        "query_name": "AcousticDecibelMeter",
        "description": "factory occupational safety sound pressure transducer measuring acoustic ambient noise intensity and workplace loudness levels",
        "expected_class": "NoiseSensor",
    },
    {
        "id": "B4",
        "category": "Synonyms & Paraphrasing (Vocab Mismatch)",
        "query_name": "UltrasonicAnemometer",
        "description": "meteorological ultrasonic breeze velocity transducer and atmospheric wind flow compass tracking device",
        "expected_class": "WindSensor",
    },
    {
        "id": "B5",
        "category": "Synonyms & Paraphrasing (Vocab Mismatch)",
        "query_name": "SubsurfaceVibrationSeismograph",
        "description": "foundation structural earth tremor sensor detecting ground acceleration, tectonic vibrations, and seismic disturbances",
        "expected_class": "SeismicSensor",
    },
    {
        "id": "B6",
        "category": "Synonyms & Paraphrasing (Vocab Mismatch)",
        "query_name": "ThermalVisionFlawDetector",
        "description": "computer vision optical defect inspection scanner verifying assembly tolerances, surface blemishes, and product conformance",
        "expected_class": "QualityScanner",
    },
    {
        "id": "B7",
        "category": "Synonyms & Paraphrasing (Vocab Mismatch)",
        "query_name": "HydraulicWorkpieceVise",
        "description": "high-pressure hydraulic fixture tool for locking vehicle body panels firmly in place during machining",
        "expected_class": "ClampingRobot",
    },
    {
        "id": "B8",
        "category": "Synonyms & Paraphrasing (Vocab Mismatch)",
        "query_name": "RotaryBoreHoleSpindle",
        "description": "high-speed rotary spindle tool for cutting cylindrical holes through sheet metal and steel body sections",
        "expected_class": "DrillingRobot",
    },
    # -----------------------------------------------------------------------
    # CATEGORY C: Concise / Minimalist SDFs (Low Token Count)
    # -----------------------------------------------------------------------
    {
        "id": "C1",
        "category": "Concise / Minimalist SDFs",
        "query_name": "MiniAirMon",
        "description": "measures room pollution and climate",
        "expected_class": "AirQuality",
    },
    {
        "id": "C2",
        "category": "Concise / Minimalist SDFs",
        "query_name": "PlacerArm",
        "description": "moves vehicle pieces between conveyor stations",
        "expected_class": "PickUpRobot",
    },
    {
        "id": "C3",
        "category": "Concise / Minimalist SDFs",
        "query_name": "RainGauge",
        "description": "measures rainfall precipitation quantity",
        "expected_class": "RainSensor",
    },
    # -----------------------------------------------------------------------
    # CATEGORY D: Multi-Modal / Edge Sensors (Cross-Domain Distractors)
    # -----------------------------------------------------------------------
    {
        "id": "D1",
        "category": "Cross-Domain Distractors",
        "query_name": "SmartWeatherBeacon",
        "description": "outdoor station tracking atmospheric weather, precipitation accumulation, and wind currents",
        "expected_class": "WindSensor",  # or RainSensor
    },
    {
        "id": "D2",
        "category": "Cross-Domain Distractors",
        "query_name": "FactorySoundAlarm",
        "description": "safety emergency siren triggering loud audio warnings when environmental hazards occur",
        "expected_class": "IndoorsAlarm",
    },
]


def rank_levenshtein(query: str, class_descs: dict[str, str]) -> list[tuple[str, float]]:
    """Compute baseline string similarity using thefuzz token sort ratio (0.0 to 1.0)."""
    scores = []
    for cls_name, cls_text in class_descs.items():
        # Baseline thesis logic: fuzzy token sort ratio on concatenated strings
        combined_target = f"{cls_name} {cls_text}"
        score = fuzz.token_sort_ratio(query, combined_target) / 100.0
        scores.append((cls_name, float(score)))
    return sorted(scores, key=lambda x: -x[1])


def run_benchmark() -> dict:
    class_descs = load_sdf_descriptions()
    matcher = EmbeddingMatcher()

    print(f"Loaded {len(class_descs)} device classes from SDF corpus.")
    print(f"Running benchmark across {len(BENCHMARK_CASES)} evaluation test cases...\n")

    results = {
        "cases": [],
        "metrics": {
            "levenshtein": {"top1": 0, "top3": 0, "mrr": 0.0, "avg_margin": 0.0, "total_time_ms": 0.0},
            "embedding": {"top1": 0, "top3": 0, "mrr": 0.0, "avg_margin": 0.0, "total_time_ms": 0.0},
        },
    }

    n = len(BENCHMARK_CASES)

    for case in BENCHMARK_CASES:
        cid = case["id"]
        q_name = case["query_name"]
        q_desc = case["description"]
        expected = case["expected_class"]
        category = case["category"]

        # 1. Levenshtein / thefuzz
        t0 = time.perf_counter()
        lev_ranked = rank_levenshtein(f"{q_name} {q_desc}", class_descs)
        t_lev = (time.perf_counter() - t0) * 1000.0

        # 2. Embedding / Qwen3
        t0 = time.perf_counter()
        emb_ranked = matcher.rank_candidates(f"{q_name}: {q_desc}", class_descs, top_k=len(class_descs))
        t_emb = (time.perf_counter() - t0) * 1000.0

        # Extract ranks
        lev_classes = [c for c, _ in lev_ranked]
        emb_classes = [c for c, _ in emb_ranked]

        lev_rank = lev_classes.index(expected) + 1 if expected in lev_classes else 99
        emb_rank = emb_classes.index(expected) + 1 if expected in emb_classes else 99

        lev_top1 = lev_rank == 1
        emb_top1 = emb_rank == 1

        lev_top3 = lev_rank <= 3
        emb_top3 = emb_rank <= 3

        lev_mrr = 1.0 / lev_rank if lev_rank <= 20 else 0.0
        emb_mrr = 1.0 / emb_rank if emb_rank <= 20 else 0.0

        # Margin = score(rank 1) - score(rank 2)
        lev_margin = lev_ranked[0][1] - (lev_ranked[1][1] if len(lev_ranked) > 1 else 0.0)
        emb_margin = emb_ranked[0][1] - (emb_ranked[1][1] if len(emb_ranked) > 1 else 0.0)

        # Accumulate metrics
        results["metrics"]["levenshtein"]["top1"] += int(lev_top1)
        results["metrics"]["levenshtein"]["top3"] += int(lev_top3)
        results["metrics"]["levenshtein"]["mrr"] += lev_mrr
        results["metrics"]["levenshtein"]["avg_margin"] += lev_margin
        results["metrics"]["levenshtein"]["total_time_ms"] += t_lev

        results["metrics"]["embedding"]["top1"] += int(emb_top1)
        results["metrics"]["embedding"]["top3"] += int(emb_top3)
        results["metrics"]["embedding"]["mrr"] += emb_mrr
        results["metrics"]["embedding"]["avg_margin"] += emb_margin
        results["metrics"]["embedding"]["total_time_ms"] += t_emb

        case_entry = {
            "id": cid,
            "category": category,
            "query": q_name,
            "expected": expected,
            "levenshtein": {
                "top1_match": lev_ranked[0][0],
                "top1_score": round(lev_ranked[0][1] * 100, 1),
                "expected_rank": lev_rank,
                "expected_score": round(dict(lev_ranked).get(expected, 0.0) * 100, 1),
                "margin": round(lev_margin * 100, 1),
                "correct": lev_top1,
            },
            "embedding": {
                "top1_match": emb_ranked[0][0],
                "top1_score": round(emb_ranked[0][1] * 100, 1),
                "expected_rank": emb_rank,
                "expected_score": round(dict(emb_ranked).get(expected, 0.0) * 100, 1),
                "margin": round(emb_margin * 100, 1),
                "correct": emb_top1,
            },
        }
        results["cases"].append(case_entry)

        # Console print
        status_lev = "✅" if lev_top1 else f"❌ (Rank #{lev_rank} -> {lev_ranked[0][0]})"
        status_emb = "✅" if emb_top1 else f"❌ (Rank #{emb_rank} -> {emb_ranked[0][0]})"
        print(f"[{cid}] {q_name:30} Expected: {expected:20}")
        print(f"     Levenshtein: {status_lev:35} [Score: {dict(lev_ranked).get(expected, 0.0)*100:5.1f}%]")
        print(f"     Embedding:   {status_emb:35} [Score: {dict(emb_ranked).get(expected, 0.0)*100:5.1f}%]\n")

    # Averages
    for k in ["levenshtein", "embedding"]:
        results["metrics"][k]["top1_pct"] = round((results["metrics"][k]["top1"] / n) * 100, 1)
        results["metrics"][k]["top3_pct"] = round((results["metrics"][k]["top3"] / n) * 100, 1)
        results["metrics"][k]["mrr"] = round(results["metrics"][k]["mrr"] / n, 3)
        results["metrics"][k]["avg_margin_pct"] = round((results["metrics"][k]["avg_margin"] / n) * 100, 1)
        results["metrics"][k]["avg_latency_ms"] = round(results["metrics"][k]["total_time_ms"] / n, 2)

    return results


def main() -> None:
    res = run_benchmark()
    out_file = Path(__file__).resolve().parent / "benchmark_results.json"
    out_file.write_text(json.dumps(res, indent=2))
    print(f"Benchmark results written to {out_file}\n")

    m = res["metrics"]
    print("=" * 75)
    print("🏆 FINAL EMPIRICAL BENCHMARK SUMMARY (N = 16 cases)")
    print("=" * 75)
    print(f"{'Metric':<32} | {'Thesis (thefuzz / Lev)':<20} | {'New (Qwen3-Embed-4B)':<20}")
    print("-" * 75)
    print(f"{'Top-1 Accuracy (%)':<32} | {m['levenshtein']['top1_pct']:>18.1f}% | {m['embedding']['top1_pct']:>18.1f}%")
    print(f"{'Top-3 Accuracy (%)':<32} | {m['levenshtein']['top3_pct']:>18.1f}% | {m['embedding']['top3_pct']:>18.1f}%")
    print(f"{'Mean Reciprocal Rank (MRR)':<32} | {m['levenshtein']['mrr']:>19.3f} | {m['embedding']['mrr']:>19.3f}")
    print(f"{'Avg Discriminative Margin (%)':<32} | {m['levenshtein']['avg_margin_pct']:>18.1f}% | {m['embedding']['avg_margin_pct']:>18.1f}%")
    print(f"{'Avg Query Latency (ms)':<32} | {m['levenshtein']['avg_latency_ms']:>17.2f}ms | {m['embedding']['avg_latency_ms']:>17.2f}ms")
    print("=" * 75)


if __name__ == "__main__":
    main()
