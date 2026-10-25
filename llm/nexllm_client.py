import os
import json

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI

load_dotenv()


class NexLLMClient:

    def __init__(self):

        self.model = ChatOpenAI(
            model=os.getenv(
                "NEXLLM_CHAT_MODEL"
            ),
            api_key=os.getenv(
                "NEXLLM_API_KEY"
            ),
            base_url=os.getenv(
                "NEXLLM_BASE_URL"
            )
        )

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{user_prompt}")
            ]
        )
        self.chain = self.prompt | self.model

    def chat(
        self,
        system_prompt,
        user_prompt
    ):

        response = self.chain.invoke(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt
            }
        )

        return response.content

    def chat_with_tools(self, system_prompt, user_prompt, tools, tool_handlers):
        """Invoke model-proposed tools once, then summarize their results."""
        messages = self.prompt.format_messages(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        response = self.model.bind_tools(tools).invoke(messages)
        tool_calls = getattr(response, "tool_calls", []) or []
        if not tool_calls:
            return {
                "message": response.content,
                "tool_calls": [],
                "tool_results": [],
            }

        tool_messages = []
        tool_results = []
        for call in tool_calls:
            name = call.get("name")
            arguments = call.get("args") or {}
            handler = tool_handlers.get(name)
            if handler is None:
                result = {"error": f"Unsupported tool: {name}"}
            else:
                try:
                    result = handler(**arguments)
                except Exception as exc:
                    result = {"error": str(exc)}

            tool_results.append({"name": name, "result": result})
            tool_messages.append(ToolMessage(
                content=json.dumps(result, default=str),
                tool_call_id=call.get("id", name or "unknown"),
            ))

        final_response = self.model.invoke(messages + [response] + tool_messages)
        return {
            "message": final_response.content,
            "tool_calls": [
                {"name": call.get("name"), "arguments": call.get("args") or {}}
                for call in tool_calls
            ],
            "tool_results": tool_results,
        }