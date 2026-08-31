from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from reflex_research_writer.agent.reflexion_agent import ReflexionAgent
from reflex_research_writer.search.base import SearchEngine


def create_reflexion_agent(openai_model: str, search_engine: SearchEngine) -> ReflexionAgent:
    """Assembles and returns a ready-to-use ReflexionAgent."""

    # ChatOpenAI automatically get OPENAI_API_KEY and OPENAI_BASE_URL as environment variables
    base_llm = ChatOpenAI(
        model=openai_model,
        temperature=0.7,        # set only as fallback
        timeout=360.0
    )

    checkpointer = None # MemorySaver()

    return ReflexionAgent(
        base_llm=base_llm,
        search_engine=search_engine,
        checkpointer=checkpointer
    )