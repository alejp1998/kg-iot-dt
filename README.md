# KG-IOT-DT

**Digital Twin Knowledge Graphs for IoT Platforms: Real-Time Virtual Models**

This project demonstrates the automated creation and real-time updating of a digital twin for IoT sensors within a simulated factory environment. Leveraging MQTT and a smart agent, it transforms raw device readings into a structured TypeDB Knowledge Graph, showcasing dynamic digital twin updates.

This project is inspired by the research conducted in the master thesis "Digital Twin Knowledge Graphs for IoT Platforms: Towards a Virtual Model for Real-Time Knowledge Representation in IoT Platforms" by Jarabo Peñas, A. (2023), KTH. You can access the full thesis here: [https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438&dswid=1186](https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438&dswid=1186). The focus of this work is on the design and implementation of a consistency handler algorithm that automatically builds and maintains a digital twin of an IoT platform as a knowledge graph, particularly emphasizing the integration of unanticipated devices.

**Core Functionality:**

* **IoT Device Simulation:** Provides a simulated environment that generates data representing various IoT devices within a simplified automobile production line. This environment emulates real-world scenarios where devices generate data based on their tasks and classes.
* **MQTT Data Routing:** Utilizes an MQTT broker (eclipse-mosquitto) to efficiently route data from simulated devices to a knowledge graph agent, enabling real-time data flow.
* **Automated Query Generation (Consistency Handler):** Employs a `consistency_handler` algorithm to analyze incoming data and automatically generate TypeQL queries. This algorithm is designed to interpret device classes and attributes from Semantic Definition Format (SDF) descriptions.
* **Knowledge Graph Population:** Executes generated TypeQL queries against a TypeDB Knowledge Graph, effectively populating and updating the graph with device data and relationships. This creates a structured representation of the IoT platform.
* **Unanticipated Device Integration:** Implements a similarity metric to integrate new, unforeseen devices into the knowledge graph's logical structure. The system identifies similar existing devices to infer how the new device should be integrated, ensuring adaptability.
* **Semantic Definition Format (SDF):** Uses SDF to semantically describe IoT device classes, facilitating their definition and integration into the knowledge graph. This allows for the automatic interpretation of device capabilities and data.
* **Rule-Based Reasoning:** TypeDB's reasoning capabilities are leveraged to infer new facts from explicitly stated data, enabling more sophisticated analysis and insights.

**System Architecture:**

1.  **Test Environment (`testenv.py`):**
    * Simulates a network of IoT devices within an automobile production line, each generating data at regular intervals.
    * Devices publish their data to an MQTT broker.
2.  **MQTT Broker (eclipse-mosquitto:2.0.15):**
    * Acts as a central message broker, receiving data from the simulated devices.
    * Forwards the data to the Knowledge Graph Agent.
3.  **Knowledge Graph Agent (`kgagent.py`):**
    * Subscribes to the MQTT broker and receives data messages.
    * Applies the `consistency_handler` algorithm to determine the appropriate TypeQL queries and integrate new devices, using SDF descriptions.
    * Sends the generated queries to the TypeDB Knowledge Graph.
4.  **TypeDB Knowledge Graph (vaticle/typedb:2.11.1):**
    * Stores the structured knowledge generated from the IoT device data.
    * Receives and executes TypeQL queries from the Knowledge Graph Agent.
    * Performs rule based reasoning.

**Technical Details:**

* **Dockerized Deployment:** The MQTT broker and TypeDB Knowledge Graph are deployed as Docker containers, simplifying setup and deployment.
* **Data Processing Logic (Consistency Handler):** The `consistency_handler` algorithm interprets incoming IoT data, maps it to the TypeDB schema, and integrates new devices using similarity metrics. It uses the device's UUID, class, and SDF descriptions to determine the correct schema.
* **TypeQL Queries:** The agent generates TypeQL queries to insert or update entities and relationships, ensuring data consistency and accuracy.
* **Semantic Data Integration:** Uses SDF to provide semantic descriptions of IoT device classes, enabling automated interpretation of device capabilities.
* **Similarity Metric:** Implemented to assess the similarity between new and existing devices, facilitating the integration of unanticipated devices.

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

This project demonstrates the automated population of knowledge graphs with real-time IoT data, focusing on integrating unanticipated devices and utilizing semantic descriptions. It provides a foundation for exploring knowledge graphs in IoT applications, including device monitoring, predictive maintenance, data analysis, and the dynamic adaptation of digital twins.

**Inspired by:**

* Jarabo Peñas, A. (2023). Digital Twin Knowledge Graphs for IoT Platforms: Towards a Virtual Model for Real-Time Knowledge Representation in IoT Platforms. KTH. [https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438&dswid=1186](https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1769438&dswid=1186)

**Key Concepts from the Thesis:**

* **Digital Twin (DT):** A virtual representation of a physical system that integrates and updates knowledge in real-time.
* **Knowledge Graph (KG):** A semantic graph database used to store and organize complex data in a logical structure.
* **Consistency Handler:** An algorithm that manages real-time data flow and ensures the DT accurately reflects the IoT platform's state.
* **Semantic Definition Format (SDF):** A standard used to semantically describe IoT device classes.
* **Unanticipated Device Integration:** The process of automatically integrating new, unforeseen devices into the KG using similarity metrics.
* **Rule based reasoning:** The ability to infer new information from existing information.

This project aims to address the challenges of creating and maintaining digital twins for complex IoT platforms by leveraging knowledge graphs, automated data processing, and semantic descriptions.
