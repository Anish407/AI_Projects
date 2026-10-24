from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .tools import search_web

root_agent = Agent(
    name="websearch_agent",

    model=LiteLlm(
        model="ollama_chat/llama3.2:latest",
        api_base="http://localhost:11434",
    ),

    description="A local AI assistant with future web search and currency conversion capabilities.",


    instruction="""
            You are a research assistant with web search capabilities.

            For questions asking about the latest, newest, current,
            recent, or released products, always use search_web.

            When interpreting search results:

            1. Prefer official manufacturer announcements.
            2. Identify the actual product name and release date.
            3. Do not treat image captions as product announcements.
            4. Do not assume the first search result is the most recent.
            5. Compare evidence across multiple results.
            6. Never mix specifications from different product generations.
            7. If search results do not establish the answer, search
            again with a more specific query.
            8. If the answer cannot be verified, say so.
            9. Include source URLs when answering.
            """,

    tools=[search_web],
)