"""
Integration tests for the LLM service (qwen-code-api).
These tests require qwen-code-api to be running at localhost:42005.

Run with: pytest tests/test_llm.py -v --llm
"""
import pytest
import httpx

LLM_BASE_URL = "http://localhost:42005"
API_KEY = "my-secret-qwen-key"


def _skip_if_llm_not_available():
    """Skip test if qwen-code-api is not reachable"""
    try:
        with httpx.Client(timeout=3) as client:
            resp = client.get(f"{LLM_BASE_URL}/health")
            if resp.status_code != 200:
                pytest.skip("qwen-code-api not healthy")
    except Exception:
        pytest.skip("qwen-code-api not reachable")


def _make_chat_request(message: str, model: str = "coder-model"):
    """Helper to make a chat completion request"""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": message}],
            },
        )
        resp.raise_for_status()
        return resp.json()


@pytest.mark.llm
class TestLLMService:
    """Tests that require a running qwen-code-api service."""

    def test_basic_math(self):
        """Test that LLM can answer a simple math question."""
        _skip_if_llm_not_available()
        response = _make_chat_request("What is 2+2?")

        choices = response.get("choices", [])
        assert len(choices) > 0, "No choices in response"

        content = choices[0].get("message", {}).get("content", "").lower()
        assert "4" in content, f"Expected '4' in response, got: {content}"

    def test_greeting(self):
        """Test that LLM responds to a greeting."""
        _skip_if_llm_not_available()
        response = _make_chat_request("Hello!")

        choices = response.get("choices", [])
        assert len(choices) > 0

        content = choices[0].get("message", {}).get("content", "")
        assert len(content) > 0, "Empty response to greeting"

    def test_health_endpoint(self):
        """Test that qwen-code-api health endpoint is reachable."""
        _skip_if_llm_not_available()
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{LLM_BASE_URL}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("status") == "ok"

    def test_models_endpoint(self):
        """Test that models endpoint returns available models."""
        _skip_if_llm_not_available()
        with httpx.Client(timeout=5) as client:
            resp = client.get(
                f"{LLM_BASE_URL}/v1/models",
                headers={"Authorization": f"Bearer {API_KEY}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "data" in data
            model_ids = [m["id"] for m in data["data"]]
            assert "coder-model" in model_ids
