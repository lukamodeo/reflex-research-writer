# Reflex Research Writer

> **Autonomous AI agent for creating analytical, verified Dossiers through web research and iterative critical review, using any LLM exposed through an OpenAI-compatible API.**

Reflex Research Writer is a **LangGraph-based Reflexion agent** that autonomously researches a topic, analyzes and verifies information from web sources, produces an analytical Dossier, and iteratively improves it through a rigorous self-critique loop.

The agent is **LLM-provider agnostic** and can use any model exposed through an **OpenAI-compatible API endpoint**, including locally hosted models served by inference engines such as **vLLM** or **llama.cpp**.

Designed to reduce unsupported or hallucinated claims, the agent grounds its output in retrieved web context and acts as a strict academic reviewer of its own work before producing the final document.

![Reflex Research Writer UI](https://z-cdn-media.chatglm.cn/files/a66bb3b6-080d-48c1-8403-f0e30d1782fe.png?auth_key=1888172596-04adf88e9f774c328d36ff5081cdc6e2-0-03598a1ad964f4f56fb9bcda284d449a)

---

## ✨ Features

* 🤖 **Autonomous research workflow** powered by LangGraph state machines
* 🧩 **LLM Provider Agnostic:** Supports any LLM exposed through an OpenAI-compatible API, including locally hosted models
* 🔎 **Pluggable web research** using configurable search providers (Tavily, SerpAPI, DuckDuckGo)
* 🧠 **Planner → Researcher (from Planner) → Writer → Critique → Researcher (On Critique) → Editor** workflow
* 🔄 **Iterative Reflexion** through successive rounds of critical self-review
* ✅ **Anti-Hallucination Grounding:** Strictly verifies every claim against retrieved web context
* 📝 Generates highly structured, analytical **Dossiers** with numbered academic citations
* 📚 **Fully Verified Bibliography:** Automatically compiles a deduplicated bibliography of all cited sources with exact URLs at the end of the document
* 🌍 **Multi-language UI** with automatic browser-language detection
* 🌐 Dossiers can be generated in a selectable target language independent of the UI language
* 🎨 Gradio-based web interface with real-time execution step tracking
* 📄 Export generated Dossiers directly to PDF
* ⚡ **Early Stopping:** Automatically exits the review loop if the Dossier reaches a high-quality score threshold

---

## 🧠 Agent Architecture

The agent is implemented using **LangGraph** and follows a Reflexion-style iterative workflow. It maintains a stateful context window that grows selectively, ensuring previous critiques and research are remembered without overwhelming the LLM.

```text
                         ┌─────────────┐
                         │   Planner   │
                         └──────┬──────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │ Research From Planner  │
                   └────────────┬───────────┘
                                │
                                ▼
                         ┌─────────────┐
                         │   Writer    │
                         └──────┬──────┘
                                │
                                ▼
                         ┌─────────────┐
                         │   Critique  │
                         └──────┬──────┘
                                │
                                ▼
                  ┌─────────────────────────┐
                  │ Research On Critique    │
                  └────────────┬────────────┘
                               │
                               ▼
                         ┌─────────────┐
                         │    Editor   │
                         │   (Writer)  │
                         └──────┬──────┘
                                │
                                ▼
                            Dossier
```

### Workflow Stages

1. **Planner:** Analyzes the requested topic and the initial web research findings to create a structured **blueprint** for the Dossier. This blueprint defines the provisional main title and the specific section titles (e.g., `## 1. Title`, `## 2. Title`) that the Writer must follow. It establishes the research objectives and guiding questions for each section without pre-emptively writing the arguments.
2. **Research From Planner:** Translates the blueprint into targeted web search queries in the desired language and gathers relevant sources to fill the context window.
3. **Writer:** Uses the research findings and the Planner's blueprint to produce the initial Dossier. The Writer is strictly forbidden from using its parametric memory for unverified facts and must adhere exactly to the structural titles defined in the blueprint.
4. **Critique:** Acts as a strict academic reviewer (technically it is a Reflection node). It evaluates the draft against the research context, flags hallucinations, identifies unsupported claims, and outputs a quality score along with specific revision instructions.
5. **Research On Critique:** Performs targeted web research *only* to verify specific flagged claims or fill explicit knowledge gaps identified by the Critique node.
6. **Editor:** The Writer node is reused as an editor to revise and improve the Dossier based on the critique and new research. It continues to use the original blueprint as the structural foundation, performing surgical edits to the existing text rather than full rewrites, ensuring valid citations are preserved.

### 📄 Dossier Output Format

The final Dossier is a highly structured Markdown document (exportable to PDF) featuring:
* A main title and numbered section headings as defined by the Planner's blueprint.
* Cohesive paragraphs synthesizing information from multiple sources.
* Inline academic citations in IEEE-style format (e.g., `[1, 3]`).
* A **Fully Verified Bibliography** at the end of the document, listing only the sources actually cited, complete with their original titles and exact URLs:

```text
- [1] GESTIONE DI UN CLUSTER HPC TRAMITE L'UTILIZZO ...: https://amslaurea.unibo.it/id/eprint/28921/1/Tesi%20Magistrale%20Mantovani%20Leonardo.pdf
- [2] Procedure consigliate per la progettazione di API Web: https://learn.microsoft.com/it-it/azure/architecture/best-practices/api-design
- [3] Cos'è una API REST: spiegata per non sviluppatori: https://brentasoft.com/blog/cos-e-una-api-rest-guida-non-sviluppatori
```

---

## 🔬 The Reflexion Process

Instead of generating a final document in a single pass, the agent iteratively refines its output through a rigorous self-correction loop.

```text
Blueprint  →  Planner Research  →  Draft  →  Critique  →  Targeted Research  →  Revision  →  Improved Dossier
```

Each revision gives the agent an opportunity to identify and address weaknesses in the previous version. This approach is designed to maximize:
* **Factual reliability** (zero-trust grounding in retrieved context)
* **Source coverage** and accurate citation mapping
* **Analytical depth** and logical progression
* **Identification and removal of unsupported claims**

---

## 🔄 Iterative Review and Early Stopping

The Dossier is not simply generated once. After the initial research and draft, the agent evaluates its own output through a **critique → research → revision** cycle.

The number of review cycles can be configured by the user from **1 to 5**.

However, the configured value represents the **maximum number of review cycles**, not necessarily the number that will always be executed.

After each critique, the agent evaluates the quality of the current Dossier. If the evaluation reaches the configured quality threshold, the Reflexion loop terminates early.

For example:

```text
Planner
   ↓
Research
   ↓
Writer
   ↓
Critique
   │
   ├── Quality < threshold
   │       ↓
   │   Research on Critique
   │       ↓
   │   Editor
   │       ↓
   │   Critique
   │
   └── Quality ≥ threshold
           ↓
        Early Stop
           ↓
        Final Dossier
```

In the screenshot example, the agent reaches a **9/10 evaluation** during the review process. Since the quality threshold has already been reached, the agent exits the Reflexion loop without executing the remaining available review cycles.

This allows the workflow to balance **quality and efficiency**:

* A weak Dossier can receive additional research and revisions.
* A Dossier that already meets the quality threshold can finish early.
* The user-defined maximum prevents the agent from performing an unbounded number of iterations.

### Example Agent Execution

The Gradio interface exposes the execution progress, allowing the user to follow the individual stages performed by the agent, including:

* planning
* web research
* initial writing
* critical evaluation
* targeted research based on the critique
* editorial revision
* quality evaluation
* loop termination

The interface therefore provides visibility into **why the agent is continuing the Reflexion loop or why it has decided to stop**.

---

## 🔎 Web Research & Source Management

The search subsystem is designed around a common search-engine abstraction, allowing different providers to be used without changing the agent workflow.

**Currently supported search providers:**
* Tavily
* Google SerpAPI
* DuckDuckGo

**Context Window Management:**
Search results are normalized, deduplicated by URL, and sanitized (filtering out tracking links and untrusted domains like social media). The agent strictly caps the total number of sources to prevent context bloat, ensuring the LLM can accurately parse and cite the provided evidence.

---

## 🌍 Languages

The Gradio interface supports:
* 🇬🇧 English (`en`)
* 🇮🇹 Italian (`it`)
* 🇫🇷 French (`fr`)
* 🇩🇪 German (`de`)
* 🇪🇸 Spanish (`es`)

### UI Language
The UI automatically detects the browser's preferred language. If the detected language is supported, the interface initializes in that language; otherwise, **English is used as the default**.

### Dossier Language
The target language of the generated Dossier is independently selectable. This means a user can have the UI in English while generating a Dossier in Italian, ensuring the web searches and final text are localized correctly.

---

## 🖥️ User Interface

The application provides a Gradio web interface where the user can:
1. Enter a topic.
2. Select the target language for the Dossier.
3. Configure the maximum number of revision rounds.
4. Configure the desired number of paragraphs.
5. Start the research and writing process.
6. Monitor the agent's progress in real-time (viewing planning, research, writing, and critique steps).
7. Read the final Critique evaluation and score.
8. Download the resulting Dossier as a PDF.

---

## 📋 Requirements

* Python 3.11+
* An **LLM exposed through an OpenAI-compatible API endpoint** (cloud or locally hosted)
* An API key, where required by the selected LLM endpoint
* API credentials for the selected search provider(s)

---

## 🚀 Installation

Clone the repository and create a virtual environment:

```bash
python -m venv .venv
```

Activate the environment:

**Windows PowerShell:**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
source .venv/bin/activate
```

Upgrade packaging tools and install the project:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

To install all supported search providers:
```bash
python -m pip install -e ".[all]"
```

Alternatively, install only the provider you need:
```bash
python -m pip install -e ".[tavily]"
python -m pip install -e ".[google]"
python -m pip install -e ".[duckduckgo]"
```

---

## 🔑 Configuration

Create a `.env` file in the project root based on the `.env.example` file:

```bash
cp .env.example .env
```

Then configure the LLM and search provider settings.

### LLM configuration

The project is **LLM-provider agnostic** and supports any LLM exposed through an **OpenAI-compatible API endpoint**.

The endpoint can be provided by a hosted API service or by a locally deployed inference server such as **vLLM** or **llama.cpp**.

Configure the following variables:

```dotenv
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
OPENAI_MODEL=your_model_name
```

**The `OPENAI_*` variable names refer to the OpenAI-compatible API interface and do not imply that the model must be hosted by OpenAI.**

The project has been specifically tested with **Qwen3.6-27B**, quantized to **INT4** and served through **vLLM** using an OpenAI-compatible API.

For example:

```dotenv
OPENAI_API_KEY=dummy-key
OPENAI_BASE_URL=http://localhost:8000/v1
OPENAI_MODEL=Qwen3.6-27B
```
Other OpenAI-compatible LLM providers and inference servers can be used by changing `OPENAI_BASE_URL`, `OPENAI_MODEL`, and, when required, `OPENAI_API_KEY`.

The exact values depend on the LLM provider or inference server being used.

#### Supported LLM setups

The agent can connect to any LLM exposing an OpenAI-compatible API, including:

* Cloud-hosted LLM APIs
* Locally hosted models served through **vLLM**
* Locally hosted models served through **llama.cpp**
* Other inference servers or gateways implementing the OpenAI-compatible API

The project has been specifically tested with:

* **Qwen3.6-27B INT4 via vLLM**
* **OpenAI GPT-4o via the OpenAI API**

### Search engine configuration

Select the search provider with `SEARCH_ENGINE`:

```dotenv
SEARCH_ENGINE=tavily
```

Supported values are:

* `tavily`
* `serpapi`
* `duckduckgo`

Configure the corresponding API key when required:

```dotenv
TAVILY_API_KEY=your_tavily_api_key
SERPAPI_API_KEY=your_serpapi_api_key
```

*Only configure the API keys required by the search providers you intend to use.*

Tavily requires `TAVILY_API_KEY`, SerpAPI requires `SERPAPI_API_KEY`, while DuckDuckGo does not require an API key.

### Concurrency

The maximum number of concurrent operations (default is `5`) can be configured with:

```dotenv
CONCURRENCY_LIMIT=5
```


#### Example: OpenAI + Tavily
```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

SEARCH_ENGINE=tavily
TAVILY_API_KEY=your_tavily_api_key
SERPAPI_API_KEY=

CONCURRENCY_LIMIT = 5
```

#### Example: Local Qwen3.6-27B via vLLM + Tavily
```env
OPENAI_API_KEY=dummy-key
OPENAI_BASE_URL=http://127.0.0.1:8000/v1
OPENAI_MODEL=Qwen3.6-27B

SEARCH_ENGINE=tavily
TAVILY_API_KEY=your_tavily_api_key
SERPAPI_API_KEY=

CONCURRENCY_LIMIT = 5
```

---

## ▶️ Running the Application

After installation and configuration, start the Gradio UI with:

```bash
reflex-ui
```

*(Alternatively, the application can be started directly through its Python entry point if required by your development setup).*

---

## ⚙️ Agent Configuration

The agent can be configured directly through the application interface:

* **Revision Rounds:** Controls how many critique/research/edit iterations are performed after the initial draft. More revisions can potentially improve the result but will increase execution time, LLM calls, web searches, and API usage.
* **Number of Paragraphs:** Controls the requested size and depth of the generated Dossier.

---

## 🗂️ Project Structure

```text
src/
└── reflex_research_writer/
    ├── __init__.py
    ├── agent/
    │   ├── __init__.py
    │   ├── factory.py
    │   ├── models.py
    │   ├── prompts.py
    │   └── reflexion_agent.py
    ├── locales/
    │   ├── __init__.py
    │   ├── localizers.py
    │   ├── messages.yaml
    │   └── ui_strings.yaml
    ├── search/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── ddg_engine.py
    │   ├── factory.py
    │   ├── formatter.py
    │   ├── serp_engine.py
    │   └── tavily_engine.py
    └── ui/
        ├── __init__.py
        ├── app.py
        ├── css.py
        ├── export.py
        └── assets/
            ├── __init__.py
            ├── custom.css
            └── NotoColorEmoji-flagsonly.ttf
```

### Main Components

| Package      | Responsibility                                                      |
| ------------ | ------------------------------------------------------------------- |
| `agent/`     | LangGraph workflow, state management, prompts, and agent logic      |
| `locales/`   | UI strings, messages, and localization                             |
| `search/`    | Search-provider abstraction, implementations, and result formatting |
| `ui/`        | Gradio interface and presentation-layer functionality               |
| `ui/assets/` | Gradio-specific CSS and font resources                              |

---

## 🛠️ Development

Install the project in editable mode with all dependencies:

```bash
python -m pip install -e ".[all]"
```

The `src` layout keeps the importable package separate from project-level files and helps ensure that the application is tested using the installed package rather than relying on the repository root being on `PYTHONPATH`.

---

## ⚠️ Limitations

The generated Dossiers depend on:
* The capabilities and limitations of the selected LLM.
* The quality and availability of web search results.
* The reliability of retrieved sources.
* The number of configured revision rounds.

Although the workflow performs grounded research and iterative review, **the generated content should still be independently verified**, especially for high-stakes or rapidly changing information.

---

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgements

This project is built using:
* [LangGraph](https://github.com/langchain-ai/langgraph)
* [LangChain](https://github.com/langchain-ai/langchain)
* [Gradio](https://github.com/gradio-app/gradio)
* Tavily, SerpAPI, and DuckDuckGo Search APIs

---

## 📌 Project Status

**Status:** Experimental / Proof of Concept

This project is primarily intended to explore autonomous research, Reflexion-style agent architectures, web-grounded generation, and iterative LLM-based document refinement.
```