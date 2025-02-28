# KGIOTDT: Digital Twin Knowledge Graphs for IoT Platforms

**Automated Knowledge Graph Population from Simulated IoT Data**

This project demonstrates how to automatically build and update a digital twin of IoT sensors in a simulated factory environment. Using MQTT and a smart agent, it transforms raw device readings into a structured TypeDB Knowledge Graph, showcasing real-time digital twin updates.

**Core Functionality:**

* **IoT Device Simulation:** The project includes a simulated environment that generates data representing various IoT devices.
* **MQTT Data Routing:** An MQTT broker is used to route data from the simulated devices to a knowledge graph agent.
* **Automated Query Generation:** The knowledge graph agent utilizes a `consistency_handler` algorithm to analyze incoming data and automatically generate TypeQL queries.
* **Knowledge Graph Population:** The generated TypeQL queries are executed against a TypeDB Knowledge Graph, effectively populating the graph with device data and relationships.

**System Architecture:**

1.  **Test Environment (`testenv.py`):**
    * Simulates a network of IoT devices, each generating data at regular intervals.
    * Devices publish their data to an MQTT broker.
2.  **MQTT Broker (eclipse-mosquitto:2.0.15):**
    * Acts as a central message broker, receiving data from the simulated devices.
    * Forwards the data to the Knowledge Graph Agent.
3.  **Knowledge Graph Agent (`kgagent.py`):**
    * Subscribes to the MQTT broker and receives data messages.
    * Applies the `consistency_handler` algorithm to determine the appropriate TypeQL queries.
    * Sends the generated queries to the TypeDB Knowledge Graph.
4.  **TypeDB Knowledge Graph (vaticle/typedb:2.11.1):**
    * Stores the structured knowledge generated from the IoT device data.
    * Receives and executes TypeQL queries from the Knowledge Graph Agent.

**Technical Details:**

* **Dockerized Deployment:** The MQTT broker and TypeDB Knowledge Graph are deployed as Docker containers, simplifying setup and deployment.
* **Data Processing Logic:** The `consistency_handler` algorithm within the Knowledge Graph Agent is responsible for interpreting the incoming IoT data and mapping it to the defined schema within the TypeDB Knowledge Graph. The algorithm uses the device's UUID and class to determin the correct schema.
* **TypeQL Queries:** The agent generates TypeQL queries to insert or update entities and relationships within the knowledge graph, ensuring data consistency and accuracy.

**Usage Instructions:**

1.  **Prerequisites:**
    * Docker and Docker Compose.
    * Python 3.
2.  **Start the Docker Containers:**
    ```bash
    docker-compose -f testbed.yaml up -d
    ```
3.  **Start the Knowledge Graph Agent:**
    ```bash
    python3 kgagent.py
    ```
    * Allow time for the initial schema and data population to complete.
    * Wait for the agent to connect to the MQTT broker.
4.  **Start the Test Environment (in a separate terminal):**
    ```bash
    python3 testenv.py
    ```
    * Simulated devices will begin publishing data, triggering the Knowledge Graph Agent to process and update the TypeDB Knowledge Graph.

**Docker Compose Configuration (`testbed.yaml`):**

```yaml
# Add your docker-compose file contents here for clarity.
# For example:
version: "3.8"
services:
  mosquitto:
    image: eclipse-mosquitto:2.0.15
    ports:
      - "1883:1883"
      - "8883:8883"
    volumes:
      - ./storage/mosquitto/config:/storage/mosquitto/config
      - ./storage/mosquitto/data:/storage/mosquitto/data
      - ./storage/mosquitto/log:/storage/mosquitto/log
  typedb:
    image: vaticle/typedb:2.11.1
    ports:
      - "1729:1729"

## Purpose
This project serves as a practical demonstration of how knowledge graphs can be automatically populated with real-time IoT data. It provides a foundation for exploring the use of knowledge graphs in IoT applications, such as device monitoring, predictive maintenance, and data analysis.
