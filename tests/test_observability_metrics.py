from prometheus_client import generate_latest

from src.observability import observe_agent_latency


def test_agent_latency_metric_emits_agent_labels():
    observe_agent_latency("agent1", "generation", 0.123)
    payload = generate_latest().decode("utf-8")

    assert "capstone_agent_duration_seconds_bucket" in payload
    assert 'agent="agent1"' in payload
    assert 'operation="generation"' in payload
