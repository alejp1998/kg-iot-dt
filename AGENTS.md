# AGENTS.md - KG-IOT-DT

This repository contains the Master's Thesis research codebase (KTH, 2023) for automated creation, real-time synchronization, and semantic integration of Digital Twin Knowledge Graphs in IoT Platforms using TypeDB and MQTT.

---

## Project Overview

- **Primary Language**: Python (3.10)
- **Core Technologies**: TypeDB (vaticle/typedb 2.11.1), TypeQL, MQTT (eclipse-mosquitto 2.0.15), STUMPY (Matrix Profile), TheFuzz, Pandas, NumPy
- **Main Entry Points**:
  - Knowledge Graph Agent: `kgagent.py` (subscribes to MQTT `#`, generates TypeQL, updates TypeDB)
  - Factory Simulation: `testenv.py` (simulates automated production line & publishes telemetry)
  - Infrastructure: `testbed.yaml` (Docker Compose running TypeDB and Mosquitto)
- **Pipeline**:
  1. `testenv.py` / `iotdevices.py` simulates production line devices and publishes JSON telemetry to MQTT topics.
  2. `kgagent.py` (`KGAgent`) receives messages, runs `consistency_handler`, and maps device attributes.
  3. For unforeseen devices, a dual similarity metric (SDF text distance via `thefuzz` + time-series pattern matching via `stumpy.mass`) discovers ontology alignments and replicates structural relationships.
  4. TypeQL queries are dispatched to `TypeDB` to dynamically populate and reason over the digital twin.

---

## Coding Agent Workflow

1. **Python Environment**: Use Python 3.10 with `typedb-client==2.11.1` in the local `.venv` (`uv venv --python 3.10 .venv && uv pip install -r requirements.txt`). TypeDB 2.x client APIs require specific transaction patterns:
   - Schema mutations: `session_type=SessionType.SCHEMA`, `transaction_type=TransactionType.WRITE`
   - Data insertions: `session_type=SessionType.DATA`, `transaction_type=TransactionType.WRITE`
2. **Wildcard Re-Exports**: `kgagent.py` / `iotdevices.py` / `testenv.py` use `from aux import *` as the documented thesis pattern. `aux.py` therefore re-exports shared names (`mqtt_client`, `dumps/loads/dump`, `uuid4`, `timedelta`, `Parallel/delayed`, typing aliases, `print` wrapper) — annotate re-exports with `# noqa: F401` and never remove them as "unused", or the consumer modules break at runtime.
3. **TypeDB Schema & Data Definitions**:
   - `typedbconfig/schema.tql` defines entities (`device`, `room`, `attribute`, `metric`), relations (`located-in`, `reports-attribute`), and rules.
   - `typedbconfig/data.tql` seeds the initial Knowledge Graph state.
   - Do not make breaking schema modifications without updating the corresponding query builders in `aux.py` and `kgagent.py`.
4. **Semantic Definition Format (SDF)**: All device specification files reside in `sdf/` as `*.sdf.json`. When introducing new device types, provide conforming SDF schemas so `SDFManager` in `aux.py` can parse capabilities and properties.
5. **Service Endpoints**:
   - TypeDB address is configured in `aux.py` (`kb_addr = '0.0.0.0:80'`).
   - MQTT broker address is configured in `aux.py` (`broker_addr = '0.0.0.0'`, `broker_port = 8883`).
6. **Quality Gates**: Run `pre-commit run --all-files`, `pytest`, and `python scripts/check_radon_complexity.py` before pushing. Ruff config lives in `pyproject.toml`.

---

## Quick Start

### 1. Launch Infrastructure (Docker)

```bash
docker compose -f testbed.yaml up -d
```

### 2. Activate Python Environment

```bash
source .venv/bin/activate
```

_(If recreating the virtualenv: `uv venv --python 3.10 .venv && uv pip install "typedb-client==2.11.1" python-benedict colorama joblib numpy pandas "paho-mqtt<2.0.0" stumpy thefuzz pyyaml`)_

### 3. Run the Knowledge Graph Agent

```bash
python3 kgagent.py
```

### 4. Run the Factory Simulation Testbed

In a separate shell:

```bash
source .venv/bin/activate
python3 testenv.py
```

---

## Project Structure

### Key Modules & Files

| File/Directory            | Purpose                                                                                                  |
| ------------------------- | -------------------------------------------------------------------------------------------------------- |
| `kgagent.py`              | `KGAgent` class implementing MQTT subscriber, consistency handler, and dynamic device integration        |
| `aux.py`                  | `TypeDBClient` wrapper, `SDFManager`, text/time-series similarity functions, and global constants        |
| `testenv.py`              | Main simulated production line testbed orchestrating multiple IoT device threads                         |
| `iotdevices.py`           | Device class definitions (`MillingRobot`, `DrillingRobot`, `AirQuality`, etc.) with telemetry generators |
| `testbed.yaml`            | Docker Compose stack for `vaticle/typedb:2.11.1` and `eclipse-mosquitto:2.0.15`                          |
| `sdf/`                    | Directory of Semantic Definition Format (SDF) JSON schemas for each device type                          |
| `typedbconfig/schema.tql` | TypeDB declarative schema (entities, attributes, relations, rules)                                       |
| `typedbconfig/data.tql`   | Initial knowledge graph seed data                                                                        |
| `visualizations.ipynb`    | Jupyter analysis notebook for experimental evaluation and metrics plotting                               |
