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


def test_chat_with_tools_binds_schema_dispatches_and_summarizes(monkeypatch):
    from tools.google_hotels_tool import SEARCH_GOOGLE_HOTELS_SCHEMA

    captured = {"invoke_count": 0}
    tool_arguments = {
        "hotel_ids": ["lp12345"],
        "check_in": "2026-11-15",
        "check_out": "2026-11-17",
        "adults": 2,
        "currency": "USD",
    }

    class FakeModel:
        def __call__(self, prompt_value):
            return self.invoke(prompt_value.to_messages())

        def bind_tools(self, schemas):
            captured["schemas"] = schemas
            return self

        def invoke(self, messages):
            captured["invoke_count"] += 1
            captured.setdefault("invocations", []).append(messages)
            if captured["invoke_count"] == 1:
                return AIMessage(content="", tool_calls=[{
                    "name": "search_google_hotels",
                    "args": tool_arguments,
                    "id": "call_1",
                    "type": "tool_call",
                }])
            return AIMessage(content="Two live hotel offers found.")

    monkeypatch.setattr(nexllm_client, "ChatOpenAI", lambda **_kwargs: FakeModel())
    client = nexllm_client.NexLLMClient()
    called = {}

    result = client.chat_with_tools(
        "Find hotel availability.",
        "Check these hotels for my stay.",
        tools=[SEARCH_GOOGLE_HOTELS_SCHEMA],
        tool_handlers={
            "search_google_hotels": lambda **kwargs: called.update(kwargs) or {"properties": []},
        },
    )

    assert captured["schemas"] == [SEARCH_GOOGLE_HOTELS_SCHEMA]
    assert called == tool_arguments
    assert result["message"] == "Two live hotel offers found."
    assert result["tool_calls"] == [{
        "name": "search_google_hotels",
        "arguments": tool_arguments,
    }]
    assert result["tool_results"] == [{
        "name": "search_google_hotels",
        "result": {"properties": []},
    }]
    assert "properties" in captured["invocations"][1][-1].content