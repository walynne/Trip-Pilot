import os

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
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