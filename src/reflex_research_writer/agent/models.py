from enum import StrEnum
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Literal, Dict, Any, TypeAlias, TypedDict


class MessageKey(StrEnum):
    PLANNING = "planning"
    SEARCHING = "searching"
    GENERATING = "generating"
    REVISING = "revising"
    INTEGRATING = "integrating"
    FINALIZING = "finalizing"
    EVALUATING = "evaluating"
    EXITING = "exiting"

class StatusMessage(TypedDict):
    key: MessageKey
    phase: Literal["start", "end", "exit"]
    params: Dict[str, Any]


class FinalMessage(TypedDict):
    draft: str
    evaluation: str
    score: int


StatusEvent: TypeAlias = Tuple[
    Literal["status"],
    StatusMessage,
]

FinalEvent: TypeAlias = Tuple[
    Literal["final"],
    FinalMessage,
]

# The shared streaming contract
StreamEvent: TypeAlias = StatusEvent | FinalEvent


# Structured output for LLM nodes
class Queries(BaseModel):
    queries: List[str] = Field(default_factory=list)

# The LangGraph State
class AgentState(BaseModel):
    topic: str
    target_language: str
    plan: Optional[str] = None
    draft: Optional[str] = None
    revision_instructions: Optional[str] = None
    research_topics: Optional[str] = None
    draft_evaluation: Optional[str] = None
    draft_score: int = 0
    search_results:List[Dict] = Field(default_factory=list)
    revision_number: int = 1
    max_revisions: int = 3
    num_paragraphs: int = 5
