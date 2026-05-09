# 

AutoChain-Sentinel: Master System Design & Development Specification

**Version:** 1.0 (Production Blueprint)  
**System Identity:** A prescriptive AI "Control Tower" designed to automate the monitoring of automotive supply chains (Tiers 1-3) via real-time news feeds, leveraging Knowledge Graphs and Retrieval-Augmented Generation (RAG).

**AIM OF THE PROJECT:**   
The high-level vision of **AutoChain-Sentinel** is to transition automotive supply chain management from a "reactive" firefighting mode to an "autonomous" prescriptive mode. As a 5-year level engineering project, it moves beyond simple data analysis to building a production-grade system that manages the "Digital Twin" of a global supply network.

**WHAT IS IT ABOUT:**  
At its core, AutoChain-Sentinel is an **AI-Driven Supply Chain Control Tower**. In the modern automotive industry, a single car consists of over 30,000 parts, and a disruption at a small Tier 3 factory can shut down an entire multi-billion dollar assembly line.

This project is a software ecosystem that:

* **Listens** to the world via real-time RSS news feeds.  
* **Reasons** about those events using Large Language Models (LLMs) to identify exactly which cities or industries are in trouble.  
* **Maps** those disruptions to a Knowledge Graph to see the "ripple effect" through three tiers of suppliers.  
* **Predicts** the specific arrival delay in days for the final vehicle model using machine learning.

---

### **2\. The Aim of the Project**

The primary aim is **Automated Supply Chain Resilience**. Specifically, the project intends to:

* **Eliminate Manual Searching:** Replace the need for human managers to manually browse news and cross-reference spreadsheets during a crisis.  
* **Provide Multi-Tier Transparency:** Reveal "hidden" dependencies where multiple Tier 1 suppliers might all rely on the same single Tier 3 raw material source.  
* **Quantify Risk:** Convert vague news headlines (e.g., "Port Strike") into hard numbers, such as "Predicted 8-day delay" or "$4.2M revenue at risk".  
* **Suggest Solutions:** Automatically identify alternative suppliers who are outside the disruption zone and have the capacity to fill orders.

**DELIVERABLES:**

Since this project is designed to mirror the work of a senior-level Data Science Engineer, the expectations go beyond "working code." The expected output is a **Production-Ready Portfolio** consisting of:

* **A "Live" Interactive Dashboard:** A Streamlit-based "War Room" where a user can simulate global disasters and watch the supply chain react in real-time. Based on the news, the user would be able to see what is impacted virtually on the global screen, with predicted numbers. By simulate, I mean he should be able to see if there are other suppliers or alternatives who can provide for in a quick and efficient way and what are the expected loss numbers then?  
   \+1  
* **Architectural Depth:** A system that is fully containerized (Docker) and ready for cloud deployment (AWS), proving you can manage infrastructure, not just models.  
* **Technical Rigor:** Use of advanced data structures (Neo4j Property Graphs) and senior engineering practices like CI/CD, unit testing, and MLOps (drift monitoring).  
* **Business ROI:** A clear demonstration of how this tool saves an automotive OEM millions of dollars by preventing "line-down" events.  
   \+1

By the end of this project, you will have a "Digital Thread" that connects the most abstract news event to the most specific car part on a production line.

## **1\. Project Overview & Global Architecture**

This document serves as the absolute source of truth for the AutoChain-Sentinel application. It provides explicit schemas, prompts, and architectural decisions required for AI-assisted development .

### **1.1 Directory Structure**

autochain-sentinel/  
├── data/              \# CSV seeds, Faker scripts, synthetic generation logic  
├── backend/           \# FastAPI, LangChain agents, Neo4j drivers, XGBoost models  
├── frontend/          \# Streamlit Dashboard, PyDeck maps, Network graphs  
├── infra/             \# Docker configurations, Terraform AWS scripts  
└── tests/             \# Pytest suite (Unit, Regression, Sanity)

## **2\. Phase 1: Data Ecosystem & Knowledge Graph**

The foundation of the system is a highly structured Neo4j Property Graph. It maps the physical realities of the automotive supply chain.

### **2.1 Neo4j Graph Schema**

| Entity Type | Label | Properties |
| :---- | :---- | :---- |
| Node | Supplier | uid (String), name (String), tier\_level (Int: 1-3), risk\_score (Float: 0.0-1.0) |
| Node | Part | part\_id (String), name (String), criticality (Int: 1-10), base\_lead\_time\_days (Int) |
| Node | VehicleModel | model\_id (String), name (String), daily\_production\_target (Int) |
| Node | City | name (String), country (String), lat (Float), lon (Float) |

### **2.2 Relationship Definitions (Edges)**

* (Supplier)-\[:PRODUCES\]-\>(Part)  
* (Part)-\[:COMPONENT\_OF\]-\>(Part) *// Hierarchical relationship linking Tier 3 to Tier 2, and Tier 2 to Tier 1\.*  
* (Part)-\[:REQUIRED\_FOR\]-\>(VehicleModel)  
* (Supplier)-\[:LOCATED\_IN\]-\>(City)

### **2.3 Synthetic Data Generation Strategy (data\_factory.py)**

To populate the database without expensive enterprise APIs, utilize the Python Faker library combined with standard pandas manipulation.

1. **Target Demographics:** Generate 100 suppliers weighted geographically (30% Germany, 30% China, 20% USA, 20% Mexico) to ensure realistic supply chain distributions.  
2. You could use this dataset: [https://www.kaggle.com/datasets/bertnardomariouskono/global-supply-chain-disruption-and-resilience](https://www.kaggle.com/datasets/bertnardomariouskono/global-supply-chain-disruption-and-resilience)  
   * It has these columns: Order\_ID  
   * \# Content The dataset consists of \*\*10,000 shipment records\*\* spanning major global trade routes (e.g., Shanghai to Rotterdam via Suez, Hamburg to New York). It moves beyond simple time-series forecasting by incorporating \*\*External Risk Factors\*\*. Key features include: \* \*\*Disruption Events:\*\* Categorical events like 'Geopolitical Conflict', 'Port Congestion', and 'Severe Weather'. \* \*\*Risk Indices:\*\* Quantitative scores for geopolitical stability and weather severity. \* \*\*Financial Impact:\*\* Dynamic calculation of shipping costs based on mode (Sea vs. Air) and risk premiums. \* \*\*Prescriptive Actions:\*\* A dedicated column (\`Mitigation\_Action\_Taken\`) simulating human managerial decisions (e.g., re-routing or expediting via air) in response to risks. \# Methodology (Risk-Adjusted Simulation) This dataset uses a \*\*Logic-Based Event Simulation\*\* engine: 1\. \*\*Route Profiling:\*\* Each trade route has specific risk probabilities (e.g., Suez Canal has higher geopolitical risk; Pacific routes have higher weather risk in Q3). 2\. \*\*Delay Injection:\*\* Delays are not random; they are causally linked to specific disruption events. 3\. \*\*Cost Dynamics:\*\* Shipping costs fluctuate based on the \`Transportation\_Mode\` and \`Inflation\_Rate\`. 4\. \*\*Mitigation Logic:\*\* High-value goods (e.g., Semiconductors) trigger different mitigation actions compared to commodities when disruptions occur.  
   * Order\_Date  
   * Timestamp of order placement.  
   * Origin\_City  
   * The city where the shipment originates.  
   * Destination\_City  
   * The final destination of the shipment.  
   * Route\_Type  
   * Strategic trade route used (e.g., Suez Canal, Trans-Pacific). Crucial for risk correlation.  
   * Transportation\_Mode  
   * Method of transport (Sea, Air, Rail, Road). Affects cost and speed significantly.  
   * Product\_Category  
   * Category of the goods. Determines sensitivity to delay and cost.  
   * Base\_Lead\_Time\_Days  
   * Expected days for delivery under perfect conditions.  
   * Scheduled\_Lead\_Time\_Days  
   * Promised delivery time (Base \+ Buffer).  
   * Actual\_Lead\_Time\_Days  
   * Actual days taken for  
     If this data could be used, synthetic data generation would be unnecessary.   
       
3. **Tier Assignment:** Programmatically assign suppliers to tiers. Tier 3 suppliers output raw materials (e.g., Lithium, Raw Steel). Tier 2 suppliers output sub-assemblies (e.g., Battery Cells). Tier 1 suppliers output major components (e.g., Battery Packs, Transmissions).  
4. **Validation:** The script must include a verification function ensuring every VehicleModel has an unbroken graph path down to at least five Tier 3 suppliers. Orphaned nodes must be dropped or re-linked.

## **3\. Phase 2: Backend & AI Intelligence Engine**

The backend operates via FastAPI and orchestrates the NLP extraction and machine learning predictions.

### **3.1 RSS Ingestion & Named Entity Recognition (NER)**

The system monitors RSS feeds (e.g., via the feedparser library) for global business and logistics news. When a headline is ingested, it is passed to a LangChain agent.  
**Pydantic Output Parser Schema:**

class DisruptionEvent(BaseModel):  
    city: str \= Field(description="The exact city name where the disruption is occurring.")  
    country: str \= Field(description="The country of the city.")  
    industry\_affected: str \= Field(description="The industrial sector impacted.")  
    severity\_score: int \= Field(description="Severity on a scale of 1 to 10 (10 being complete shutdown).")  
    event\_type: str \= Field(description="Nature of the event (e.g., Weather, Strike, Financial).")

### **3.2 Predictive Modeling (XGBoost)**

Once an event is structured, the system queries Neo4j to find the shortest path from the affected City to the VehicleModel. These graph metrics feed into the predictive model.

* **Features (X):** Graph\_Hops (Distance in the graph), severity\_score (From the LLM), Part\_Criticality (From Neo4j), Historical\_Risk\_Score (From Neo4j).  
* **Target (Y):** Predicted\_Delay\_Days.  
* **Cold Start Strategy:** A localized script will generate 1,500 rows of synthetic historical data, where increasing hops and severity mathematically increase the delay days, allowing the XGBoost model to train and save a \`.pkl\` artifact.

## **4\. Phase 3: Interactive Frontend & UI (Streamlit)**

The frontend is designed to demonstrate full-stack capabilities to recruiters, operating as an interactive "War Room."

### **4.1 Layout & Components**

| UI Area | Component Tool | Functionality |
| :---- | :---- | :---- |
| Main View | PyDeck (pydeck\_chart) | A 3D globe (like as if popping out of screen rotating slowly) with scatterplot of global suppliers. Colors shift from green to red dynamically based on the active. disruption state fetched from the backend. On the main page, also the news is showed side by side, giving a clear validation of why the region is impacting.  |
| Sidebar | Streamlit Text Input | "What-If Simulator": Allows users to manually type a fake news headline to test the NER and graph traversal logic in real-time. |
| Bottom Pane | streamlit-agraph | Renders a localized network graph of the specific impacted sub-tier, showing exactly how the disruption propagates up to the vehicle model. |

### **4.2 The Mitigation Engine**

When a delay is predicted, the UI triggers a prescriptive query. It searches Neo4j for alternative suppliers producing the identical part\_id who are located in a different City. The results are displayed in a clean comparative dataframe.

## **5\. Phase 4: Engineering, Quality Assurance & MLOps**

Senior-level engineering is proven by the robustness of the system. Testing and monitoring are mandatory.

### **5.1 Pytest Suite Requirements**

1. **Unit Testing:** Validate that the Pydantic parser correctly handles malformed LLM responses (e.g., catching exceptions when a severity score is returned as text instead of an integer).  
2. **Graph Integrity Testing:** A script that runs a Cypher query asserting that zero Part nodes lack an incoming PRODUCES relationship.  
3. **E2E / Sanity Testing:** A mock \`POST\` request to the /process-news endpoint simulating a "Port Strike in Shanghai," asserting that the endpoint returns a 200 OK and a predicted delay greater than 0\.

### **5.2 MLOps & Drift Monitoring**

Implement Evidently AI to monitor model decay. The backend must log incoming "severity\_scores" from the live RSS feed. If the rolling 7-day average of severity scores deviates significantly from the training data baseline, the system logs a "Concept Drift Warning" to the console.

## **6\. Phase 5: Cloud Infrastructure & Deployment**

The application will be deployed using AWS and Docker to ensure environment parity and scalable execution.

### **6.1 Infrastructure as Code (Terraform)**

A main.tf file must be created to provision:

* An AWS ECS (Elastic Container Service) Fargate cluster to run the FastAPI and Streamlit images serverlessly.  
* An S3 bucket mapped for storing model artifacts and MLflow experiment tracking logs.  
* Secure IAM roles ensuring the ECS tasks can communicate with the external Neo4j AuraDB instance.

### **6.2 Docker Orchestration**

version: '3.8'  
services:  
  sentinel-api:  
    build: ./backend  
    ports:  
      \- "8000:8000"  
    environment:  
      \- OPENAI\_API\_KEY=${OPENAI\_API\_KEY}  
      \- NEO4J\_URI=${NEO4J\_URI}  
      \- NEO4J\_USER=${NEO4J\_USER}  
      \- NEO4J\_PASSWORD=${NEO4J\_PASSWORD}

  sentinel-ui:  
    build: ./frontend  
    ports:  
      \- "8501:8501"  
    environment:  
      \- API\_URL=http://sentinel-api:8000  
    depends\_on:  
      \- sentinel-api  
