# Observability Stack

This folder contains the local monitoring stack for the AI Day Planner app.

## What each piece does

- Prometheus collects the `/metrics` endpoint exposed by the FastAPI backend.
- Grafana visualizes Prometheus metrics and can also be used to inspect the app's health trends.
- Loki stores the backend JSON-line logs written to `logs/capstone.jsonl` through Promtail.
- DeepEval evaluates a generated day plan through `POST /deepeval/evaluate` and returns plan-quality scores.
- Agent-wise latency is tracked in Prometheus with `capstone_agent_duration_seconds` and shown in Grafana as separate panels for Agent 1 to Agent 4 plus a combined view.

## End-to-end flow

1. Start the backend and UI.
2. Generate a plan from the Streamlit dashboard.
3. Open the observability stack.
4. Use Prometheus to confirm the API metrics are being scraped.
5. Use Grafana to inspect the dashboard data and logs.
6. Run DeepEval against the latest plan to check office alignment, diet fit, workout fit, and reading fit.

## Local URLs

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Loki: `http://localhost:3100`
- FastAPI metrics: `http://127.0.0.1:8000/metrics`
- DeepEval API: `http://127.0.0.1:8000/deepeval/evaluate`
- Streamlit observability page: `http://localhost:8501`
