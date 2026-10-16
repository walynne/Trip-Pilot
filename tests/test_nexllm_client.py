from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from llm import nexllm_client


def test_chat_passes_system_and_user_prompts(monkeypatch):
    captured = {}

    def fake_model(**kwargs):
        def respond(prompt_value):
            captured["messages"] = prompt_value.to_messages()
            return AIMessage(content="Trip suggestion")

        return RunnableLambda(respond)

    monkeypatch.setattr(nexllm_client, "ChatOpenAI", fake_model)
    monkeypatch.setenv("NEXLLM_CHAT_MODEL", "test-model")
    monkeypatch.setenv("NEXLLM_API_KEY", "test-key")
    monkeypatch.setenv("NEXLLM_BASE_URL", "https://example.test/v1")

    client = nexllm_client.NexLLMClient()
    result = client.chat("You are a travel planner.", "Plan a trip to Tokyo.")

    assert result == "Trip suggestion"
    assert captured["messages"][0].content == "You are a travel planner."
    assert captured["messages"][1].content == "Plan a trip to Tokyo."