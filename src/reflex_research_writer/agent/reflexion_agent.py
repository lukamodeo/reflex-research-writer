# agent/reflexion_agent.py
import re
import time
import uuid
import inspect
from typing import cast, AsyncIterator

from reflex_research_writer.agent.models import (
    AgentState,
    Queries,
    StreamEvent,
    MessageKey,
    StatusEvent,
    FinalEvent,
    StatusMessage,
    FinalMessage
)

from reflex_research_writer.agent.prompts import (
    PLAN_PROMPT,
    RESEARCH_PLAN_PROMPT,
    WRITER_PROMPT,
    REFLECTION_PROMPT,
    RESEARCH_CRITIQUE_PROMPT
)

from reflex_research_writer.search.base import (
    SearchEngine,
    SearchResult
)

from reflex_research_writer.search.formatter import build_search_context

from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver


UNTRUSTED_DOMAINS = [
    "facebook.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "tiktok.com",
    "reddit.com",
    "pinterest.com",
    "linkedin.com"
]


def _renumber_citations_and_sources(final_text: str) -> str:
    """
    Renumbers inline citations and the bibliography sequentially
    to eliminate any holes (e.g., [1], [3] -> [1], [2]).
    Uses <bibliography> tags for language-agnostic splitting.
    The bibliography is used as the source of truth for renumbering.
    """
    # Split the text from the bibliography using XML tags
    match = re.search(r'(.*?)<bibliography>(.*?)</bibliography>(.*)', final_text, flags=re.DOTALL)

    if not match:
        return final_text  # Fallback if tags are missing

    body = match.group(1).strip()
    sources_section = match.group(2).strip()

    # Extract heading (if present) and clean sources_section
    heading = ""
    lines = sources_section.split('\n')
    if lines:
        first_line = lines[0].strip()
        if not re.match(r'[-*]\s*\[\d+\]', first_line) and not re.match(r'\d+\.\s', first_line):
            heading = first_line + "\n"
            sources_section = "\n".join(lines[1:]).strip()

    # Extract old source lines. Matches: - [1] Title: URL  OR  * [1] Title: URL
    source_lines = re.findall(r'[-*]\s*\[(\d+)\]\s*(.*)', sources_section)

    # Fallback if the LLM didn't use bullet points but just "1. Title: URL"
    if not source_lines:
        source_lines = re.findall(r'(\d+)\.\s*(.*)', sources_section)

    # If no sources found, return the body
    if not source_lines:
        return body

    # Find all unique numbers used in the bibliography (source of truth)
    bib_nums = set()
    for old_num_str, _ in source_lines:
        if old_num_str.isdigit():
            bib_nums.add(int(old_num_str))

    if not bib_nums:
        return body

    # Sort the old numbers and create a mapping to new sequential numbers
    sorted_old_nums = sorted(list(bib_nums))
    num_map = {old_num: new_num for new_num, old_num in enumerate(sorted_old_nums, 1)}

    # Renumber the inline citations in the body
    def replace_body_citations(m):
        nums = [n.strip() for n in m.group(1).split(',')]
        new_nums = []
        for n in nums:
            if n.isdigit() and int(n) in num_map:
                mapped_n = str(num_map[int(n)])
                if mapped_n not in new_nums:  # Avoid duplicates in multi-citations
                    new_nums.append(mapped_n)

        if not new_nums:
            return ""  # Remove citation if none of the numbers are in the bibliography

        return f"[{', '.join(new_nums)}]"

    new_body = re.sub(r'\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]', replace_body_citations, body)

    # Clean up any dangling spaces left by removed citations (e.g., "text ." -> "text.")
    new_body = re.sub(r'\s+([.,;:!?)])', r'\1', new_body)
    new_body = re.sub(r'  +', ' ', new_body)

    # Rebuild the bibliography sequentially
    new_sources = []
    for old_num_str, source_text in source_lines:
        old_num = int(old_num_str)
        if old_num in num_map:
            new_num = num_map[old_num]
            new_sources.append((new_num, f"- [{new_num}] {source_text.strip()}"))

    # Sort the new sources by their new number
    new_sources.sort(key=lambda x: x[0])
    final_new_sources = [s[1] for s in new_sources]

    # Reassemble the final draft
    final_sources = f"{heading}\n" + "\n".join(final_new_sources)

    return f"{new_body}\n\n{final_sources.strip()}"


class ReflexionAgent:

    def __init__(self, base_llm: ChatOpenAI, search_engine: SearchEngine, checkpointer: MemorySaver=None):
        self.llms = self._create_llms(base_llm)

        if not isinstance(search_engine, SearchEngine):
            raise TypeError("search_engine must implement SearchEngine")

        self.search_engine = search_engine

        self.graph = self._build_graph(checkpointer)


    @staticmethod
    def _create_llms(base_llm):
        # Specialized configurations for each role
        return {
            # Planner: Creative but structured
            "planner": base_llm.with_config(
                temperature=0.5,
                model_kwargs={"top_p": 0.9, "top_k": 40}
            ),

            # Researcher: Deterministic search query generation
            "research": base_llm.with_config(
                temperature=0.1,
                model_kwargs={"top_p": 0.95, "top_k": 10}
            ),

            # Writer (Initial Draft): Creative drafting allowed here
            "generate": base_llm.with_config(
                temperature=0.7,
                model_kwargs={"top_p": 0.95, "top_k": 50}
            ),

            # Writer (Revisions): STRICTLY DETERMINISTIC (Crucial for stable feedback)
            # Acts like an editor, not a creative writer.
            "edit": base_llm.with_config(
                temperature=0.1,       # Low temperature prevents rewriting good parts
                model_kwargs={"top_p": 0.9, "top_k": 10}
            ),

            # Critic: STRICTLY DETERMINISTIC
            "reflect": base_llm.with_config(
                temperature=0.0,
                model_kwargs={"top_p": 1.0, "top_k": 1}  # top_k=1 forces greedy decoding
            ),

            # Research Critic: Fact-checking needs high precision
            "research_critique": base_llm.with_config(
                temperature=0.1,
                model_kwargs={"top_p": 0.9, "top_k": 5}
            )
        }


    async def run_stream(self, topic: str, target_language:str, max_revisions: int, num_paragraphs: int) -> AsyncIterator[StreamEvent]:
        """
        Asynchronous streaming generator for Gradio.
        Yields (type, content) tuples for Gradio to consume without blocking the event loop.
        """
        # Generate a unique thread_id for this specific user's run!
        unique_thread_id = str(uuid.uuid4())
        thread = {"configurable": {"thread_id": unique_thread_id}}

        initial_state = AgentState(
            topic=topic,
            target_language=target_language,
            max_revisions=max_revisions,
            num_paragraphs=num_paragraphs
        )

        # Initialize current_state with initial values
        current_state = initial_state.model_dump()

        # Stream both state updates and custom messages ASYNCHRONOUSLY
        async for chunk in self.graph.astream(
                initial_state,
                config=thread,
                stream_mode=["updates", "custom"],
                version="v2"  # Recommended for unified format
        ):
            # Handle Custom Status Messages (emitted via get_stream_writer)
            if chunk["type"] == "custom":
                status = chunk["data"].get("status")
                if status:
                    yield cast(StatusEvent, ("status", status))

            # Handle Node Completion Updates (emitted when node returns)
            elif chunk["type"] == "updates":
                for node_name, updates in chunk["data"].items():
                    if updates is None:
                        continue
                    # Merge updates into current_state
                    # LangGraph does shallow merge automatically, we mimic it here
                    current_state.update(updates)

        # Once the async stream finishes, process the final draft, evaluation and score
        draft_value = _renumber_citations_and_sources(str(current_state.get("draft", "")))
        last_evaluation = current_state.get("draft_evaluation", "")
        last_score = current_state.get("draft_score", 6)
        final_payload: FinalMessage = {
            "draft": draft_value,
            "evaluation": last_evaluation,
            "score": last_score
        }

        yield cast(FinalEvent, ("final", final_payload))


    def _planning_node(self, state: AgentState):
        start_time = time.perf_counter()

        writer = get_stream_writer()
        start_payload: StatusMessage = {
            "key": MessageKey.PLANNING,
            "phase": "start",
            "params": {}
        }
        writer({"status": start_payload})

        system_prompt_template = PromptTemplate.from_template(PLAN_PROMPT)
        system_message = SystemMessage(
            content=system_prompt_template.format(
                target_language=state.target_language,
                num_paragraphs=state.num_paragraphs
            )
        )

        user_message = HumanMessage(
            content=state.topic
        )

        messages = [system_message, user_message]

        response = self.llms["planner"].invoke(messages)

        duration = time.perf_counter() - start_time

        end_payload: StatusMessage = {
            "key": MessageKey.PLANNING,
            "phase": "end",
            "params": {
                "duration": duration
            }
        }
        writer({"status": end_payload})

        return {"plan": response.content}


    def _researching_plan_node(self, state: AgentState):
        start_time = time.perf_counter()

        writer = get_stream_writer()
        start_payload: StatusMessage = {
            "key": MessageKey.SEARCHING,
            "phase": "start",
            "params": {}
        }
        writer({"status": start_payload})

        system_prompt_template = PromptTemplate.from_template(RESEARCH_PLAN_PROMPT)
        system_message = SystemMessage(
            content=system_prompt_template.format(
                target_language=state.target_language
            )
        )

        user_prompt_template = PromptTemplate.from_template(
            inspect.cleandoc("""\
                ### USER TOPIC:
                ====================
                {topic}
                ====================

                ### ORIGINAL RESEARCH BLUEPRINT:
                ====================
                {plan}
                ====================
                """
            )
        )
        user_message = HumanMessage(
            content=user_prompt_template.format(
                topic=state.topic,
                plan=state.plan
            )
        )

        messages = [system_message, user_message]

        queries = self.llms["research"].with_structured_output(Queries).invoke(messages)

        search_results = state.search_results

        for q in queries.queries:
            response: list[SearchResult] = self.search_engine.search(
                    query=q,
                    max_results=3,
                    exclude_domains=UNTRUSTED_DOMAINS
            )
            # Convert the SearchResult objects to dictionaries before extending
            search_results.extend([r.to_dict() for r in response])

        duration = time.perf_counter() - start_time

        end_payload: StatusMessage = {
            "key": MessageKey.SEARCHING,
            "phase": "end",
            "params": {
                "duration": duration,
                "len_results": len(search_results)
            }
        }
        writer({"status": end_payload})

        return {"search_results": search_results}


    def _writing_node(self, state: AgentState):
        start_time = time.perf_counter()

        writer = get_stream_writer()
        if state.revision_number <= state.max_revisions:
            start_payload: StatusMessage = {
                "key": MessageKey.GENERATING,
                "phase": "start",
                "params": {
                    "revision_number": state.revision_number
                }
            }
        else:
            start_payload: StatusMessage = {
                "key": MessageKey.FINALIZING,
                "phase": "start",
                "params": {}
            }
        writer({"status": start_payload})

        context = build_search_context(state.search_results, UNTRUSTED_DOMAINS)

        system_prompt_template = PromptTemplate.from_template(WRITER_PROMPT)
        system_message = SystemMessage(
            content=system_prompt_template.format(
                num_paragraphs=state.num_paragraphs,
                target_language=state.target_language,
                context=context
            )
        )

        user_base_prompt = inspect.cleandoc("""\
            Please write the essay based on the following information.

            ### USER TOPIC:
            ====================
            {topic}
            ====================

            ### ORIGINAL RESEARCH BLUEPRINT:
            ====================
            {plan}
            ====================
            """
        )

        if state.draft:
            user_base_prompt += inspect.cleandoc("""\

                ### PREVIOUS DRAFT:
                ====================
                {draft}
                ====================

                ### CRITIQUE/REVISION INSTRUCTIONS:
                ====================
                {revision_instructions}
                ====================
                """
            )

        user_prompt_template = PromptTemplate.from_template(user_base_prompt)

        user_message = HumanMessage(
            content=user_prompt_template.format(
                topic=state.topic,
                plan=state.plan,
                draft=state.draft if state.draft else "",                                   # Pass empty string if not revising
                revision_instructions=state.revision_instructions if state.draft else ""    # Pass empty string if not revising
            )
        )

        messages = [system_message, user_message]

        if not state.draft:
            response = self.llms["generate"].invoke(messages)
        else:
            response = self.llms["edit"].invoke(messages)

        # Strip the revision planning so the user never sees it
        # This regex finds <revision_planning> ... </revision_planning> and removes it
        clean_draft = re.sub(r'<revision_planning>.*?</revision_planning>', '', response.content, flags=re.DOTALL).strip()

        duration = time.perf_counter() - start_time

        if state.revision_number <= state.max_revisions:
            end_payload: StatusMessage = {
                "key": MessageKey.GENERATING,
                "phase": "end",
                "params": {
                    "duration": duration,
                    "len_draft": len(response.content)
                }
            }

        else:
            end_payload: StatusMessage = {
                "key": MessageKey.FINALIZING,
                "phase": "end",
                "params": {
                    "duration": duration,
                    "len_draft": len(response.content)
                }
            }
        writer({"status": end_payload})

        return {"draft": clean_draft}


    def _reflection_node(self, state: AgentState):
        start_time = time.perf_counter()

        writer = get_stream_writer()
        if state.revision_number <= state.max_revisions:
            start_payload: StatusMessage = {
                "key": MessageKey.REVISING,
                "phase": "start",
                "params": {
                    "revision_number": state.revision_number
                }
            }
        else:
            start_payload: StatusMessage = {
                "key": MessageKey.EVALUATING,
                "phase": "start",
                "params": {}
            }
        writer({"status": start_payload})

        context = build_search_context(state.search_results, UNTRUSTED_DOMAINS)

        # Safely get the previous instructions and evaluation using getattr
        # If it's the first loop, it will be None, so we provide a default string
        previous_instructions = getattr(state, 'revision_instructions', None)
        if not previous_instructions:
            previous_instructions = "None. This is the first draft."

        previous_evaluation = getattr(state, 'draft_evaluation', None)
        if not previous_evaluation:
            previous_evaluation = "None. This is the first draft."

        system_prompt_template = PromptTemplate.from_template(REFLECTION_PROMPT)
        system_message = SystemMessage(
            content=system_prompt_template.format(
                num_paragraphs=state.num_paragraphs,
                target_language=state.target_language,
            )
        )

        user_prompt_template = PromptTemplate.from_template(
            inspect.cleandoc("""\
                Please evaluate the following draft.

                ### ORIGINAL RESEARCH BLUEPRINT:
                ====================
                {plan}
                ====================
                
                ### PREVIOUS REVISION INSTRUCTIONS (Your past feedback from the last loop):
                ====================
                {previous_instructions}
                ====================
                
                ### PREVIOUS EVALUATION (Your past reasoning and analysis):
                ====================
                {previous_evaluation}
                ====================
                
                ### RESEARCH CONTEXT (FACTS TO CHECK AGAINST):
                ====================
                {context}
                ====================

                ### DRAFT TO CRITIQUE:
                ====================
                {draft}
                ====================
                """
            )
        )
        user_message = HumanMessage(
            content=user_prompt_template.format(
                plan=state.plan,
                previous_instructions=previous_instructions,
                previous_evaluation=previous_evaluation,
                context=context,
                draft=state.draft
            )
        )

        messages = [system_message, user_message]

        response = self.llms["reflect"].invoke(messages)

        content = response.content

        # Extract xml blocks using Regex
        rev_match = re.search(r'<REVISION_INSTRUCTIONS>(.*?)</REVISION_INSTRUCTIONS>', content, re.DOTALL)
        res_match = re.search(r'<RESEARCH_INTEGRATIONS>(.*?)</RESEARCH_INTEGRATIONS>', content, re.DOTALL)
        val_match = re.search(r'<EVALUATION>(.*?)</EVALUATION>', content, re.DOTALL)
        score_match = re.search(r'<SCORE>(\d+)</SCORE>', content)

        # Safely assign to state vars
        revision_instructions = rev_match.group(1).strip() if rev_match else "No revisions needed."
        draft_evaluation = val_match.group(1).strip() if val_match else ""
        draft_score = int(score_match.group(1)) if score_match else 0 # Default to 0 if parsing fails
        # Extract Research Topics (as a single text block to pass to the Researcher)
        if res_match:
            research_topics = res_match.group(1).strip()
            # Normalize the NO_NEW_RESEARCH flag in case the LLM adds extra dashes or spaces
            if "NO_NEW_RESEARCH" in research_topics:
                research_topics = "NO_NEW_RESEARCH"
        else:
            research_topics = "NO_NEW_RESEARCH"

        duration = time.perf_counter() - start_time

        if state.revision_number <= state.max_revisions:
            end_payload: StatusMessage = {
                "key": MessageKey.REVISING,
                "phase": "end",
                "params": {
                    "duration": duration,
                    "critique_score": draft_score
                }
            }
        else:
            end_payload: StatusMessage = {
                "key": MessageKey.EVALUATING,
                "phase": "end",
                "params": {
                    "duration": duration,
                    "critique_score": draft_score
                }
            }
        writer({"status": end_payload})

        if draft_score >= 9:
            exit_payload: StatusMessage = {
                "key": MessageKey.EXITING,
                "phase": "exit",
                "params": {
                    "critique_score": draft_score
                }
            }
            writer({"status": exit_payload})

        # print(f"*************************\n ## => CRITIQUE N. {state.revision_number} - Rate: {draft_score}\n\n-<REVISION_INSTRUCTIONS>\n{revision_instructions}\n</REVISION_INSTRUCTIONS>\n\n<RESEARCH_INTEGRATIONS>\n{research_topics}\n</RESEARCH_INTEGRATIONS>\n\n<EVALUATION>\n{draft_evaluation}\n</EVALUATION>\n******************************\n")

        return {
            "revision_instructions": revision_instructions,
            "research_topics": research_topics,
            "draft_evaluation": draft_evaluation,
            "draft_score": draft_score,
            "revision_number": state.revision_number + 1
        }


    def _researching_critique_node(self, state: AgentState):
        start_time = time.perf_counter()

        writer = get_stream_writer()
        start_payload: StatusMessage = {
            "key": MessageKey.INTEGRATING,
            "phase": "start",
            "params": {}
        }
        writer({"status": start_payload})

        search_results = state.search_results
        
        # Check if we need research
        if not ("NO_NEW_RESEARCH" in state.research_topics or state.draft_score >= 9):
            system_prompt_template = PromptTemplate.from_template(RESEARCH_CRITIQUE_PROMPT)
            system_message = SystemMessage(
                content=system_prompt_template.format(
                    target_language=state.target_language
                )
            )

    
            user_prompt_template = PromptTemplate.from_template(
                inspect.cleandoc("""\
                    ### RESEARCH TOPICS FROM REVIEWER:
                    ====================
                    {research_topics}
                    ====================
                    """
                )
            )
    
            user_message = HumanMessage(
                content=user_prompt_template.format(
                    research_topics=state.research_topics,
                )
            )
    
            messages = [system_message, user_message]
    
            queries = self.llms["research_critique"].with_structured_output(Queries).invoke(messages)
    
    
            for q in queries.queries:
                response: list[SearchResult] = self.search_engine.search(
                        query=q,
                        max_results=2,
                        exclude_domains=UNTRUSTED_DOMAINS
                )
                # Convert the SearchResult objects to dictionaries before extending
                search_results.extend([r.to_dict() for r in response])


        duration = time.perf_counter() - start_time

        end_payload: StatusMessage = {
            "key": MessageKey.INTEGRATING,
            "phase": "end",
            "params": {
                "duration": duration,
                "len_results": len(search_results)
            }
        }
        writer({"status": end_payload})

        return {"search_results": search_results}


    def _should_continue(self, state):
        if state.draft_score >= 9 or state.revision_number > state.max_revisions + 1:
            return "exit"
        return "continue"


    def _build_graph(self, checkpointer):
        builder = StateGraph(AgentState)

        builder.set_entry_point("planner")

        # Nodes
        builder.add_node("planner", self._planning_node)
        builder.add_node("research_plan", self._researching_plan_node)
        builder.add_node("writer", self._writing_node)
        builder.add_node("reflect", self._reflection_node)
        builder.add_node("research_critique", self._researching_critique_node)

        # Edges
        builder.add_edge("planner", "research_plan")
        builder.add_edge("research_plan", "writer")
        builder.add_edge("writer", "reflect")
        builder.add_edge("research_critique", "writer")

        builder.add_conditional_edges(
            "reflect",
            self._should_continue,
            {"exit": END, "continue": "research_critique"}
        )

        return builder.compile(checkpointer=checkpointer)


