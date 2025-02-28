# KG-IOT-DT

**Digital Twin Knowledge Graphs for IoT Platforms: Implementation from Master Thesis**

This project provides the code implementation corresponding to the master thesis "Digital Twin Knowledge Graphs for IoT Platforms: Towards a Virtual Model for Real-Time Knowledge Representation in IoT Platforms" by Jarabo Peñas, A. (2023), KTH. You can access the full thesis here: [https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438&dswid=1186](https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438&dswid=1186). This project demonstrates the automated creation and real-time updating of a digital twin for IoT sensors within a simulated factory environment. Leveraging MQTT and a smart agent, it transforms raw device readings into a structured TypeDB Knowledge Graph, showcasing dynamic digital twin updates, as described in the thesis.

**This is the practical implementation of the research presented in the thesis.**

**Core Functionality:**

* **IoT Device Simulation:** Provides a simulated environment, as described in the thesis, that generates data representing various IoT devices within a simplified automobile production line. This environment emulates real-world scenarios where devices generate data based on their tasks and classes.
* **MQTT Data Routing:** Utilizes an MQTT broker (eclipse-mosquitto) to efficiently route data from simulated devices to a knowledge graph agent, enabling real-time data flow, as part of the system architecture detailed in the thesis.
* **Automated Query Generation (Consistency Handler):** Implements the `consistency_handler` algorithm, as the core contribution of the thesis, to analyze incoming data and automatically generate TypeQL queries. This algorithm is designed to interpret device classes and attributes from Semantic Definition Format (SDF) descriptions.
* **Knowledge Graph Population:** Executes generated TypeQL queries against a TypeDB Knowledge Graph, effectively populating and updating the graph with device data and relationships. This creates a structured representation of the IoT platform, mirroring the virtual model described in the thesis.
* **Unanticipated Device Integration:** Implements the similarity metric, as a key component of the research, to integrate new, unforeseen devices into the knowledge graph's logical structure. The system identifies similar existing devices to infer how the new device should be integrated, ensuring adaptability, as described in the thesis.
* **Semantic Definition Format (SDF):** Uses SDF to semantically describe IoT device classes, facilitating their definition and integration into the knowledge graph. This aligns with the background research on semantic descriptions outlined in the thesis.
* **Rule-Based Reasoning:** TypeDB's reasoning capabilities are leveraged to infer new facts from explicitly stated data, enabling more sophisticated analysis and insights, as an implementation of the reasoning capabilities mentioned in the thesis.

**System Architecture:**

1.  **Test Environment (`testenv.py`):**
    * Simulates a network of IoT devices within an automobile production line, each generating data at regular intervals, mirroring the simulated environment from the thesis.
    * Devices publish their data to an MQTT broker.
2.  **MQTT Broker (eclipse-mosquitto:2.0.15):**
    * Acts as a central message broker, receiving data from the simulated devices.
    * Forwards the data to the Knowledge Graph Agent.
3.  **Knowledge Graph Agent (`kgagent.py`):**
    * Subscribes to the MQTT broker and receives data messages.
    * Applies the `consistency_handler` algorithm to determine the appropriate TypeQL queries and integrate new devices, using SDF descriptions, as detailed in the thesis.
    * Sends the generated queries to the TypeDB Knowledge Graph.
4.  **TypeDB Knowledge Graph (vaticle/typedb:2.11.1):**
    * Stores the structured knowledge generated from the IoT device data.
    * Receives and executes TypeQL queries from the Knowledge Graph Agent.
    * Performs rule based reasoning.

**Technical Details:**

* **Dockerized Deployment:** The MQTT broker and TypeDB Knowledge Graph are deployed as Docker containers, simplifying setup and deployment, aligning with the methodology used in the thesis.
* **Data Processing Logic (Consistency Handler):** The `consistency_handler` algorithm interprets incoming IoT data, maps it to the TypeDB schema, and integrates new devices using similarity metrics. It uses the device's UUID, class, and SDF descriptions to determine the correct schema, directly implementing the core contribution of the thesis.
* **TypeQL Queries:** The agent generates TypeQL queries to insert or update entities and relationships, ensuring data consistency and accuracy, as part of the knowledge graph interaction described in the thesis.
* **Semantic Data Integration:** Uses SDF to provide semantic descriptions of IoT device classes, enabling automated interpretation of device capabilities, as described in the background of the thesis.
* **Similarity Metric:** Implemented to assess the similarity between new and existing devices, facilitating the integration of unanticipated devices, a key component of the thesis's contribution.

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

**Purpose:**

This project provides the practical implementation of the research conducted in the master thesis, demonstrating the automated population of knowledge graphs with real-time IoT data, focusing on integrating unanticipated devices and utilizing semantic descriptions. It serves as a concrete example of the concepts and algorithms presented in the thesis.

**Master Thesis:**

* Jarabo Peñas, A. (2023). Digital Twin Knowledge Graphs for IoT Platforms: Towards a Virtual Model for Real-Time Knowledge Representation in IoT Platforms. KTH. [https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438&dswid=1186](https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438&dswid=1186)
