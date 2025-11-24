Below is a **clean, production-ready README.md** for your multi-service AI application.
It assumes your repo contains:

* `frontend_svc/`
* `backend_svc/`
* `searchxng_svc/`
* `docker-compose.yml`
* Your custom tools, prompts, and LLM pipeline.

You can copy/paste this directly as **README.md** at the project root.

---

# 🧠 AI Chatbot with Tool Calling — Full Stack (Frontend + Backend + SearchXNG)

This project implements a **full AI agent system** using:

* **Ollama** for LLM inference
* **Custom tool calling** (weather, date, and web search)
* **SearchXNG** as the search backend
* **FastAPI** backend for orchestrating requests
* **Gradio** frontend chat UI
* **Docker Compose** for running the entire system

The LLM automatically decides whether to call one of the available tools:

* `searchxng`
* `get_weather`
* `get_date`

It then processes the tool result and returns a final answer to the user.

---

## 🚀 Features

### ✔️ Intelligent tool-calling

The backend injects tool routing instructions into the LLM’s prompt.
The model can call at most **one tool per turn**, and tool results are fed back into a second LLM pass to generate a clean final response.

### ✔️ Web search using SearchXNG

Search queries like:

```
Who is the prime minister of Japan?
What is the population of Brazil?
```

trigger the `searchxng` tool automatically.

### ✔️ Weather querying

Query example:

```
What is the weather in New York?
```

Triggers the internal weather lookup tool.

### ✔️ Robust date tool

Explicitly called only when the user clearly asks for the date:

```
What is today's date?
What day is it?
```

### ✔️ Gradio Frontend

A simple, clean web UI for interacting with the agent.

### ✔️ Fully containerized

All services run through docker-compose:

* **frontend_svc** (Gradio)
* **backend_svc** (FastAPI + tool routing + LLM integration)
* **searchxng_svc** (Search)
* **Ollama** (LLM runtime)

---

## 📁 Project Structure

```
.
├── README.md
├── docker-compose.yml
│
├── backend_svc/
│   ├── app.py
│   ├── prompts.py
│   ├── utils.py
│   ├── tools/
│   │   ├── get_weather.py
│   │   ├── get_date.py
│   │   ├── searchxng.py
│   │   ├── tool_schemas.py
│   │   ├── *.json
│   └── requirements.txt
│
├── frontend_svc/
│   ├── app.py
│   └── requirements.txt
│
└── searchxng_svc/
    └── (SearchXNG server)
```

---

## 🛠️ Requirements

* Docker
* Docker Compose
* At least one local model installed in Ollama, e.g.:

```
ollama pull granite4:350m
```

You can also configure other models in `backend_svc/app.py`.

---

## ▶️ Running The Project

From the project root:

```bash
docker-compose up --build
```

This launches:

* **Ollama** on port `11434`
* **Backend** on port `8000`
* **Frontend** on port `7860`
* **SearchXNG** on port `8080`

Once running:

### Open the Chat UI:

👉 [http://localhost:7860](http://localhost:7860)

### Backend docs:

👉 [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 💬 Example Queries

| Query                                 | Expected Tool | Result               |
| ------------------------------------- | ------------- | -------------------- |
| “Who is the prime minister of Japan?” | searchxng     | Uses recent news     |
| “Weather in Toronto?”                 | get_weather   | Weather summary      |
| “What is today’s date?”               | get_date      | Returns current date |
| “Explain black holes”                 | none          | Direct LLM answer    |

---

## ⚙️ How Tool Calling Works

### 1️⃣ First LLM Pass → Decide tool or answer directly

The LLM sees rules for tool routing and returns either:

* A normal text response
* OR a `tool_call` block like:

```json
{
  "tool_calls": [
    {
      "id": "call_123",
      "function": {
        "name": "searchxng",
        "arguments": { "query": "prime minister of Japan" }
      }
    }
  ]
}
```

### 2️⃣ Backend runs the tool

The backend parses the tool call, routes to:

* `tools/searchxng.py`
* `tools/get_weather.py`
* `tools/get_date.py`

and captures the output.

### 3️⃣ Second LLM Pass → Final Answer

The backend creates a **follow-up prompt** with:

* The user question
* The tool result
* Strict instructions to answer directly

This eliminates hallucinations.

---

## 🧩 Troubleshooting

### 🔸 The model picks the wrong tool

This is expected with small models (350M).
Tool routing is controlled in `prompts.py`:

* Tighten rules
* Add forbidden patterns
* Upgrade to a larger model

### 🔸 SearchXNG returns too many results

Adjust `count=` inside `tools/searchxng.py`.

### 🔸 Empty or messy LLM outputs

Inspect backend logs:

```
docker logs backend_svc
```

---

## 🧪 Running Backend Without Docker

Inside `backend_svc/`:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

---

## 🧱 Customizing Tools

Add a new tool in:

```
backend_svc/tools/
```

Add its JSON schema in:

```
backend_svc/tools/*.json
```

Then expose it in:

```
backend_svc/tools/__init__.py
```

The backend automatically includes it in the tool-calling prompt.

---



---

## 📝 License

MIT License

---
