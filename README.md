# ⚖️ SmartArbitrage Agent - Kaggle Capstone Project

**SmartArbitrage Agent** is a multi-agent financial research and analysis system designed to identify and evaluate resale arbitrage opportunities on the European market (with a primary and default focus on **Italy**). 

This project was developed as part of the **Kaggle AI Agent Vibe Coding Intensive Course** and implements state-of-the-art concepts from Google's **ADK 2.0 (Agent Development Kit)**, the **MCP (Model Context Protocol)**, and agent security.

---

## 🚀 Key Features

1. **Multi-Agent Architecture (ADK 2.0)**:
   - 🕵️ **Inspector (ProductInspectorAgent)**: Identifies the product (brand, model, version, condition) from a simple text description, an URL, or an **image (Multimodal)**.
   - 🔍 **Scanner (MarketScannerAgent)**: Scans the target European market (Italy, France, Germany, Spain) via our local Model Context Protocol (MCP) tool server to retrieve active listings.
   - 🛡️ **Security (SafetyAgent)**: Computes a trust score and detects scam or counterfeit risks if the prices are abnormally low.
   - 📊 **Financial Analyst (ArbitrageAnalystAgent)**: Deterministically calculates platform selling fees (e.g., eBay commission), deducts shipping costs, and provides a clear verdict: **GREAT DEAL (BUY)**, **NEUTRAL (HOLD)**, or **BAD DEAL (PASS)**.
   - 👑 **Orchestrator (Director)**: Coordinates the sequence and merges all conclusions into a final structured Markdown report.

2. **Local Tool Server (MCP / ADK Tools)**:
   - Real-time scraper for **eBay Europe** (`ebay.it`, `ebay.fr`, etc.).
   - Meta-searcher **Google Shopping** to aggregate dozens of e-commerce shops.
   - **Smart local cache fallback** (SQLite / config) to ensure fast and offline demonstrations for judges without IP bans or scraping blocks.
   - **Barcode / QR Code Resolver**: Automatically lookup EAN/UPC barcode numbers in public databases (Open Food Facts, Open Beauty Facts) to identify brands and names in real-time.

3. **Built-in Enterprise Security**:
   - **Input Shield (before_model_callback)**: Deterministic regex-based security layer to neutralize prompt injections (e.g., *jailbreaks*, *instruction overrides*) with zero token cost.
   - **Output Shield (after_model_callback)**: Automatic censorship of personally identifiable information (PII) such as emails and phone numbers.

4. **Premium Streamlit UI (Zinc Design)**:
   - Sleek dark theme, clean KPI profit cards, price distribution box-plots with **Plotly**, and camera photo capture/drag-and-drop.

---

## 📁 Project Structure

```
smart-arbitrage-agent/
├── app/
│   ├── agent.py               # ADK 2.0 agents & workflow definitions
│   ├── mcp_server.py          # Local MCP tool server for scraping & math
│   ├── dashboard.py           # Streamlit user interface
│   └── agent_runtime_app.py   # Hosting application for Cloud Run deployment
├── tests/
│   ├── unit/                  # Unit tests (Scraping, Fees, Security)
│   ├── integration/           # Integration tests for agent workflows
│   └── eval/                  # Agent evaluation scenarios (Kaggle Eval)
├── .env                       # Environment variables (GCP Project, US-Central1, etc.)
└── pyproject.toml             # Project configuration & Dependencies
```

---

## 🛠️ Installation & Configuration

### Prerequisites
- **Python 3.11+**
- **uv** (Ultra-fast package manager): [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Google Cloud SDK** (Authenticated with active credentials for Vertex AI)

### 1. Install Dependencies
Within the `smart-arbitrage-agent` folder, synchronize the virtual environment and packages:
```bash
uv sync
```

### 2. Configure Environment Variables
Create or edit the `.env` file at the root of the project:
```env
GOOGLE_CLOUD_PROJECT="your-project-id"
GOOGLE_CLOUD_LOCATION="us-central1"
GOOGLE_GENAI_USE_VERTEXAI="True"
```

---

## 🎮 How to Run the Project

### A. Launch the Streamlit Interface (Recommended)
To interact visually with the multi-agent system, run the Streamlit app:
```bash
uv run streamlit run app/dashboard.py
```
Open the address printed in your terminal (usually `http://localhost:8501`).

### B. Launch the ADK Playground
To test the agent in CLI or via the official ADK web playground interface:
```bash
uvx google-agents-cli playground
```

---

## 🧪 Tests & Evaluation

### 1. Run Unit and Integration Tests
We use `pytest` to verify the business logic, fee calculator, and security guards:
```bash
uv run pytest
```

### 2. Run Automatic Agent Evaluation
To run the evaluation suite (which measures the quality of agent responses on real-world queries and assigns a score from 1 to 5 using Vertex AI):
```bash
uvx google-agents-cli eval run
```
