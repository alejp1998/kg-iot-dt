# KG-IOT-DT: Digital Twin Knowledge Graphs for IoT Platforms

**Automated Creation, Real-Time Updating, and Semantic Integration of Digital Twin Knowledge Graphs in IoT Platforms**

[![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![TypeDB](https://img.shields.io/badge/TypeDB-2.11.1-734B9C?logo=typedb&logoColor=white)](https://vaticle.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?logo=eclipsemosquitto&logoColor=white)](https://mosquitto.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![KTH DiVA](https://img.shields.io/badge/KTH%20DiVA-diva2%3A1769438-00569B)](https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Master Thesis Reference

This repository contains the practical implementation and experimental evaluation framework for the Master's Thesis:

> **Alejandro Jarabo-Peñas**, *"Digital Twin Knowledge Graphs for IoT Platforms: Towards a Virtual Model for Real-Time Knowledge Representation in IoT Platforms,"* Master's Thesis, **KTH Royal Institute of Technology**, Stockholm, Sweden, 2023.  
> **DiVA Portal:** [https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438](https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438)

---

## Contents

- [Overview](#overview)
- [Key Technical Highlights](#key-technical-highlights)
- [System Architecture](#system-architecture)
  - [Component Pipeline](#component-pipeline)
  - [Knowledge Graph Agent (`kgagent.py`)](#knowledge-graph-agent-kgagentpy)
  - [Consistency Handler & Unforeseen Device Integration](#consistency-handler--unforeseen-device-integration)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Launch Docker Infrastructure](#1-launch-docker-infrastructure)
  - [2. Start the Knowledge Graph Agent](#2-start-the-knowledge-graph-agent)
  - [3. Run the Simulated IoT Testbed](#3-run-the-simulated-iot-testbed)
- [Semantic Definition Format (SDF)](#semantic-definition-format-sdf)
- [Repository Structure](#repository-structure)
- [Citation](#citation)
- [License](#license)

---

## Overview

Industrial IoT platforms require virtual models (Digital Twins) that can dynamically adapt to real-time telemetry, evolving plant topologies, and the spontaneous addition or replacement of smart devices without manual schema redesign.

**KG-IOT-DT** implements an autonomous Knowledge Graph Agent that bridges MQTT IoT networks with a **TypeDB** Knowledge Graph. Using semantic device specifications encoded in the **Semantic Definition Format (SDF)**, the agent automatically:
1. Translates streaming IoT device messages into TypeQL schema definitions and data insertions.
2. Maintains real-time state synchronization of the digital twin across factory production line and safety zones.
3. Automatically discovers and integrates **unanticipated devices** into the ontology by combining text similarity (Levenshtein distance) on SDF definitions with time-series pattern matching (STUMPY / MASS algorithm).
4. Executes rule-based reasoning over the Knowledge Graph to infer logical relations and operational constraints.

---

## Key Technical Highlights

* **Automated TypeQL Query Generation**: Transforms incoming JSON device telemetry and SDF specifications into declarative TypeQL queries on the fly.
* **Dual-Metric Similarity for Unforeseen Devices**:
  - *Syntactic/Semantic Match*: Fuzzy string matching (`thefuzz`) across SDF class hierarchies to identify the closest ontological parent.
  - *Behavioral Match*: Matrix profile time-series sub-sequence similarity (`stumpy.mass`) over telemetry buffers to identify matching device behaviors.
* **Dynamic Digital Twin Lifecycle**: Automatic entity instantiation, relationship replication, and replacement pruning when existing devices are superseded.
* **Multi-Domain Factory Simulation**: Multi-threaded simulated environment (`testenv.py`) modeling an automobile manufacturing plant (clamping, milling, drilling, tag scanners, conveyors, air quality, alarms).
* **Containerized Infrastructure**: Docker Compose deployment for the TypeDB graph database and Eclipse Mosquitto MQTT broker.

---

## System Architecture

### Component Pipeline

```
┌───────────────────────────────────────────────────────────────┐
│              Simulated IoT Network (testenv.py)               │
│   Production Line Robots (Milling, Drilling, Clamping, etc.)  │
│   Safety & Environmental Sensors (Air Quality, Alarms, etc.)  │
└───────────────────────────────┬───────────────────────────────┘
                                │ MQTT Pub (port 8883)
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                MQTT Message Broker (Mosquitto)                │
└───────────────────────────────┬───────────────────────────────┘
                                │ MQTT Sub (#)
                                ▼
┌───────────────────────────────────────────────────────────────┐
│             Knowledge Graph Agent (kgagent.py)                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                  Consistency Handler                    │  │
│  │  - Device Registration & Schema Validation              │  │
│  │  - Dual-Metric Integration (SDF Text + STUMPY TS Match) │  │
│  │  - TypeQL Query Compiler                                │  │
│  └────────────────────────────┬────────────────────────────┘  │
└───────────────────────────────┼───────────────────────────────┘
                                │ TypeQL Queries
                                ▼
┌───────────────────────────────────────────────────────────────┐
│            TypeDB Knowledge Graph (vaticle/typedb)            │
│         Schema (schema.tql) & Facts / Rules (data.tql)        │
└───────────────────────────────────────────────────────────────┘
```

---

## Getting Started

### Prerequisites

- **Docker & Docker Compose**
- **Python 3.10** (or `uv`)

### 1. Launch Docker Infrastructure

Start TypeDB (port 80/1729) and the Mosquitto MQTT broker (port 8883):

```bash
docker compose -f testbed.yaml up -d
```

### 2. Start the Knowledge Graph Agent

Create the virtual environment and launch the agent:

```bash
# Create and activate environment
uv venv --python 3.10 .venv
source .venv/bin/activate

# Install dependencies
uv pip install "typedb-client==2.11.1" python-benedict colorama joblib numpy pandas "paho-mqtt<2.0.0" stumpy thefuzz pyyaml

# Start the agent (initializes schema and connects to MQTT)
python3 kgagent.py
```

### 3. Run the Simulated IoT Testbed

In a separate terminal, launch the simulated factory testbed:

```bash
source .venv/bin/activate
python3 testenv.py
```

The simulated devices will start publishing telemetry to MQTT, and the Knowledge Graph Agent will process events, infer topologies, and populate the TypeDB Knowledge Graph in real time.

---

## Semantic Definition Format (SDF)

The `sdf/` directory contains IETF Semantic Definition Format JSON files defining device capabilities, actions, properties, and events for all modeled equipment:

| Device Category | SDF Specification Files |
|-----------------|-------------------------|
| **Robotic Machining** | `DrillingRobot.sdf.json`, `MillingRobot.sdf.json`, `ClampingRobot.sdf.json`, `PickUpRobot.sdf.json` |
| **Material Handling** | `ConveyorBelt.sdf.json`, `PieceDetector.sdf.json`, `PoseDetector.sdf.json` |
| **Quality & Tracking** | `QualityScanner.sdf.json`, `TagScanner.sdf.json`, `ConfigurationScanner.sdf.json` |
| **Safety & Environment** | `AirQuality.sdf.json`, `SmokeSensor.sdf.json`, `NoiseSensor.sdf.json`, `WindSensor.sdf.json`, `SeismicSensor.sdf.json`, `IndoorsAlarm.sdf.json`, `OutdoorsAlarm.sdf.json` |
| **Supervisory Control** | `ProductionControl.sdf.json`, `RepairControl.sdf.json`, `FaultNotifier.sdf.json` |

---

## Repository Structure

```
kg-iot-dt/
├── kgagent.py                  # Core Knowledge Graph Agent & MQTT listener
├── aux.py                      # TypeDB client wrapper, SDF manager & math helpers
├── testenv.py                  # Multi-threaded automobile production line simulator
├── iotdevices.py               # Simulated IoT device classes and MQTT publishers
├── testbed.yaml                # Docker Compose file for TypeDB and Mosquitto
├── sdf/                        # Semantic Definition Format (SDF) JSON definitions
├── typedbconfig/
│   ├── schema.tql              # TypeDB schema definition (entities, relations, attributes)
│   └── data.tql                # Initial Knowledge Graph seed data
└── visualizations.ipynb        # Analysis, benchmark plots, and experimental results
```

---

## Citation

If you build upon this work, please cite the Master's Thesis:

```bibtex
@mastersthesis{jarabo2023digital,
  author={Jarabo-Pe{\~n}as, Alejandro},
  title={Digital Twin Knowledge Graphs for IoT Platforms: Towards a Virtual Model for Real-Time Knowledge Representation in IoT Platforms},
  school={KTH Royal Institute of Technology, School of Electrical Engineering and Computer Science},
  year={2023},
  url={https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438}
}
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
