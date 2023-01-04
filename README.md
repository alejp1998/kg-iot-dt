# KGIOTDT README
# Digital Twin Knowledge Graphs for IoT Platforms

## Introduction

This project aims to create a test environment for emulating a series of IoT devices that generate data. The data is then published to a MQTT broker, which forwards it to the Knowledge Graph Agent. The Knowledge Graph Agent processes the data and uses the `consistency_handler` algorithm to determine the queries to generate automatically in TypeQL language, depending on the message received and the UUID and device class of the sender. These queries are then sent to the TypeDB Knowledge Graph, which is updated accordingly.

## Components

- Test Environment: Emulates a series of IoT devices that generate data
- MQTT broker: Deployed on a docker container and listens on port 8883
- Knowledge Graph Agent: Subscribes to the MQTT broker and processes data from IoT devices using the `consistency_handler` algorithm to determine the queries to generate automatically
- TypeDB Knowledge Graph: Deployed on a docker container and listens on port 1729

## Docker Containers

This project uses the following Docker containers:

- `eclipse-mosquitto:2.0.15` for the MQTT broker, which listens on port 8883 and has volumes mounted at `/storage/mosquitto/config`, `/storage/mosquitto/data`, and `/storage/mosquitto/log`
- `vaticle/typedb:2.11.1` for the TypeDB Knowledge Graph, which listens on port 80 and has no volumes mounted

## Usage

To use this project, follow these steps:

1. Start the Docker containers by running the following command: `docker-compose -f testbed.yaml up -d`
2. Start the Knowledge Graph Agent by running the command: `python3 kgagent.py`
    - Wait for the initial definition of the schema and data population to end. 
    - Wait for the knowledge graph agent to connect to the broker. 
    - The process will finish once the agent is ready to process messages. 
3. Start the Test Environment on a separate terminal (without stopping the kg agent) by running the command: `python3 testenv.py`
    - The devices will be instantiated as threads and connect to the broker. 
    - The generation of messsages will begin, and the knowledge graph agent will begin processing them and generating queries to the TypeDB knowledge graph.