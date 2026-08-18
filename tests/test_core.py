"""Automated test suite for the KG-IoT Digital Twin repository.

These tests exercise the pure-Python components of the codebase
(SDF parsing, similarity/voting metrics, device data generation)
without requiring a live TypeDB server or MQTT broker.
"""

import os
import sys

import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

import aux  # noqa: E402
from aux import (  # noqa: E402
    SDFManager,
    calc_voting_result_df,
    gen_header,
    gen_robot_data,
    get_closest_classes,
    get_closest_devs,
)


# ---------------------------------------------------------------------------
# SDF Manager
# ---------------------------------------------------------------------------
def test_sdf_manager_loads_all_files():
    """SDFManager must discover every *.sdf.json in the sdf/ directory."""
    manager = SDFManager(path=os.path.join(REPO_ROOT, "sdf"))
    sdfs, sdfs_dfs = manager.get_all_sdfs()
    assert len(sdfs) >= 6, f"expected >=6 SDF definitions, got {len(sdfs)}"
    assert len(sdfs_dfs) == len(sdfs)


def test_sdf_df_columns():
    """The SDF DataFrame must expose the documented schema columns."""
    manager = SDFManager(path=os.path.join(REPO_ROOT, "sdf"))
    _, sdfs_dfs = manager.get_all_sdfs()
    for dev_class, sdf_df in sdfs_dfs.items():
        assert "thing" in sdf_df.columns
        assert "obj" in sdf_df.columns
        assert "prop" in sdf_df.columns
        assert not sdf_df.empty, f"{dev_class} SDF DataFrame is empty"


def test_sdf_manager_build_single():
    """build_sdf must return (dict, DataFrame) for an existing class."""
    manager = SDFManager(path=os.path.join(REPO_ROOT, "sdf"))
    dev_class = min(os.listdir(manager.path)).replace(".sdf.json", "")
    sdf, sdf_df = manager.build_sdf(dev_class)
    assert isinstance(sdf, dict)
    assert isinstance(sdf_df, pd.DataFrame)


# ---------------------------------------------------------------------------
# Similarity & voting
# ---------------------------------------------------------------------------
def test_calc_voting_result_df():
    """Voting aggregation must sum scores per candidate."""
    votes = [{"A": 3, "B": 1}, {"A": 2, "B": 2}, {"B": 3}]
    result = calc_voting_result_df(votes)
    assert result.loc[result.candidate == "A", "score"].iloc[0] == 5
    assert result.loc[result.candidate == "B", "score"].iloc[0] == 6


def test_get_closest_classes_scores():
    """get_closest_classes must return a dict keyed by candidate."""
    manager = SDFManager(path=os.path.join(REPO_ROOT, "sdf"))
    sdfs, sdfs_dfs = manager.get_all_sdfs()
    sdfs_df = pd.concat(list(sdfs_dfs.values())).reset_index(drop=True)

    dev_class = "AirQuality"
    noninteg_class = sdfs_df[sdfs_df.thing == dev_class]
    integ_classes = sdfs_df[sdfs_df.thing != dev_class]

    if noninteg_class.shape[0] == 0:
        pytest.skip("AirQuality class not present in SDF files")

    result = get_closest_classes(noninteg_class, integ_classes, 0)
    assert isinstance(result, dict)
    assert len(result) > 0


def test_get_closest_devs_returns_votes():
    """get_closest_devs must return a dict with candidate votes for the closest device."""
    from aux import SDFManager

    manager = SDFManager(path=os.path.join(REPO_ROOT, "sdf"))
    sdfs, sdfs_dfs = manager.get_all_sdfs()

    # Build a tiny devs_df-like frame for one non-integrated device and one integrated device
    val_cols = [f"v{i}" for i in range(24)]
    cols = ["uuid", "class", "integ", "mod", "attrib", "dev", *val_cols]
    noninteg_dev = pd.DataFrame(
        [
            [
                "new_dev",
                "AirQuality",
                False,
                "air_quality_sensor",
                "temp",
                "AirQuality/air_quality_sensor/temp",
                *([1.0] * len(val_cols)),
            ]
        ],
        columns=cols,
    )
    integ_devs = pd.DataFrame(
        [
            [
                "old_dev",
                "AirQuality",
                True,
                "air_quality_sensor",
                "temp",
                "AirQuality/air_quality_sensor/temp",
                *([1.0] * len(val_cols)),
            ]
        ],
        columns=cols,
    )
    result = get_closest_devs(noninteg_dev, integ_devs, ["AirQuality"], 0)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Data generation helpers
# ---------------------------------------------------------------------------
def test_gen_robot_data_shape():
    """gen_robot_data must return joint + actuator structures."""
    data = gen_robot_data(offset=1.0, A=2.0, T=40.0, phi=0.0, actuator_status=True)
    assert "joint" in data
    assert "actuator" in data
    assert "x_position" in data["joint"]
    assert "actuator_status" in data["actuator"]


def test_gen_robot_data_sine_bounds():
    """Sine values must stay within amplitude bounds."""
    data = gen_robot_data(offset=0.0, A=3.0, T=40.0, phi=0.0, actuator_status=True)
    assert -3.5 <= data["joint"]["x_position"] <= 3.5


def test_gen_header_fields():
    """gen_header must produce topic/uuid/class/timestamp."""
    header = gen_header(dev_class="MillingRobot", topic="robot/milling", uuid="abc-123")
    assert header["topic"] == "robot/milling"
    assert header["uuid"] == "abc-123"
    assert header["class"] == "MillingRobot"
    assert "timestamp" in header


def test_sample_sine_clamps_to_thresholds():
    """sample_sine must return values within 1-sigma of the mean."""
    samples = [aux.sample_sine(offset=0, amp=0.001, T=100, phi=0.0) for _ in range(200)]
    assert all(0 - 0.01 <= s <= 0 + 0.01 for s in samples), (
        "sine values must clamp within thresholds"
    )


# ---------------------------------------------------------------------------
# TypeQL helpers (string builders)
# ---------------------------------------------------------------------------
def test_typeql_query_helpers_exist():
    """The TypeDBClient must expose the documented TypeQL query methods."""
    from aux import TypeDBClient

    client = TypeDBClient.__new__(TypeDBClient)  # avoid touching network
    assert callable(client.match_query)
    assert callable(client.insert_query)
    assert callable(client.define_query)
