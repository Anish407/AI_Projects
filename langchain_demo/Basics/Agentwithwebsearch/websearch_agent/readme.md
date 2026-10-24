# Local AI Web Search Agent — Google ADK + Ollama + DuckDuckGo 

A hands-on Python project that runs an AI agent using **Google Agent Development Kit (ADK)**, a **local Llama 3.2 model served by Ollama**, and a **DuckDuckGo search tool**. The project illustrates model inference, tool registration, tool execution, and inspection of traces using the ADK development Web UI.

> **Project status:** Local model connection and DuckDuckGo search tool calling have been implemented and tested. **Currency conversion is planned but not implemented.** Search answer reliability is still being improved.

## 1. Architecture

```text
Browser (ADK Web UI, localhost:8000)
             |
             v
ADK development server / Agent Runner
             |
             v
root_agent (websearch_agent/agent.py)
             |
             v
LiteLLM -> Ollama HTTP API (localhost:11434) -> llama3.2:latest
             |
       model requests a tool call
             v
ADK runs Python search_web(query)
             |
             v
DDGS -> web search results
             |
             v
ADK returns tool results to model -> final response in Web UI
```

**Separation of responsibilities:** ADK manages the agent and tool execution; LiteLLM adapts the model API; Ollama serves model inference; Llama 3.2 selects a tool and generates the answer; the Python function performs the actual web request. There is **no MCP server** in this version. Installing the Python `mcp` package does not turn this Python tool into an MCP server.

## 2. Prerequisites

- Windows with PowerShell and VS Code (commands below target Windows).
- Python 3.12 (the project used **3.12.6**).
- Ollama installed and running.
- `llama3.2:latest` downloaded (the tested model was around 3.2B parameters, Q4_K_M, approximately 2 GB on disk, with a `tools` capability).
- Internet connectivity for the DuckDuckGo search integration. **The LLM is local, but web searching is not offline.**

Check Ollama:

```powershell
ollama --version
ollama list
ollama show llama3.2
Invoke-RestMethod http://localhost:11434/api/tags
```

Look for `tools` under model capabilities. Ollama normally listens at `http://localhost:11434`. If needed, start the Ollama application or run `ollama serve` when no server is running. Don't start a second server on an occupied port.

> The model's advertised context length isn't necessarily the context actually configured or allocated by Ollama. Tool-calling capability also doesn't guarantee correct tool selection or answers.

## 3. Create and activate a Python virtual environment

From the project's root folder (for example, `Agentwithwebsearch`):

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
```

The interpreter path should end in `Agentwithwebsearch\.venv\Scripts\python.exe`.

If PowerShell blocks activation, for **this terminal session only**:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**Why:** A virtual environment separates this project's Python dependencies from global Python and other projects. VS Code's selected interpreter is independent of an activated PowerShell terminal; use **Python: Select Interpreter** to select `.venv\Scripts\python.exe` if Pylance warns that imports cannot be resolved.

## 4. Declare and install dependencies

Create `requirements.txt` in the root:

```txt
google-adk
litellm>=1.84
ddgs
mcp
```

Then install and verify:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip show google-adk
python -m pip check
adk --help
```

- `google-adk`: agent definitions, runner, development Web UI, tool orchestration and tracing.
- `litellm`: Ollama model adapter used in this project.
- `ddgs`: web-search client (the newer package name replacing `duckduckgo-search`).
- `mcp`: an SDK needed by the tested environment after a `No module named 'mcp'` runtime error; **not** used here to create an MCP server. Its necessity can depend on installed dependency versions.

**Why `-r` matters:** `python -m pip install -r requirements.txt` tells pip to read dependency specifications from the file. Simply creating the file doesn't install packages. Using `python -m pip` also helps ensure pip belongs to the intended Python interpreter.

**Reproducibility note:** These are convenient learning-project constraints, not a fully locked installation. Pin versions or use a lockfile before deployment.

## 5. Create the agent package

Final structure for the current project:

```text
Agentwithwebsearch/
├── .venv/                 # local packages; don't commit
├── requirements.txt
├── .gitignore
└── websearch_agent/
    ├── __init__.py
    ├── agent.py
    ├── tools.py
    └── .env               # local configuration; don't commit
```

Create the folder/files if they don't exist:

```powershell
New-Item -ItemType Directory -Force websearch_agent
New-Item -ItemType File -Force websearch_agent\__init__.py
New-Item -ItemType File -Force websearch_agent\agent.py
New-Item -ItemType File -Force websearch_agent\tools.py
```

In `websearch_agent/__init__.py`:

```python
from . import agent
```

**Why:** `__init__.py` makes the folder a regular Python package. When it is imported, `from . import agent` imports `agent.py`, where ADK will find `root_agent`. Importing the module constructs an agent object; it **does not** start an independent agent process or automatically send a request to Ollama. Some Python namespace packages work without `__init__.py`, but this convention is appropriate for the ADK layout.

## 6. Set environment configuration

In `websearch_agent/.env`:

```dotenv
OLLAMA_API_BASE=http://localhost:11434
```

Use plain `KEY=VALUE`, **not** PowerShell `$env:...` syntax and **not** a Markdown link. ADK development tooling loads the agent's `.env` configuration; your agent code below also explicitly passes the API base address, keeping that connection clear.

In the root `.gitignore`:

```gitignore
.venv/
**/.env
__pycache__/
.pytest_cache/
```

**Why:** Never commit future API keys or credentials. For production, inject configuration and secrets through the deployment environment or a secrets manager.

## 7. Implement and test the DuckDuckGo tool independently

In `websearch_agent/tools.py`:

```python
from ddgs import DDGS


def search_web(query: str) -> dict:
    """Search the web for current information.

    Args:
        query: Search terms describing the information to find.

    Returns:
        A dictionary with status, query and search results or an error.
    """
    try:
        results = DDGS(timeout=10).text(
            query=query,
            max_results=5,
            backend="duckduckgo",
        )
        return {
            "status": "success",
            "query": query,
            "results": [
                {
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", ""),
                }
                for item in results
            ],
        }
    except Exception as exc:
        return {"status": "error", "query": query, "message": str(exc)}
```

Test it **without ADK or Ollama**:

```powershell
python -c "from ddgs import DDGS; print('DDGS import OK')"
python -c "from websearch_agent.tools import search_web; from pprint import pprint; pprint(search_web('Official Python documentation'))"
```

Expect a dictionary with `status: success` and a `results` list. A successful status with an empty results list is still insufficient for answering the question. Search requests may occasionally fail due to networking, rate limits, or search-provider changes.

**Why independent tests:** If this fails, the problem is in DDGS/networking or the function, **not** in model inference or agent orchestration. Keep tool logic separate from the framework so it can later be reused in FastAPI or MCP.

## 8. Configure `root_agent` and register the tool

In `websearch_agent/agent.py`:

```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .tools import search_web

root_agent = Agent(
    name="websearch_agent",
    model=LiteLlm(
        model="ollama_chat/llama3.2:latest",
        api_base="http://localhost:11434",
    ),
    description="Local AI agent that can search the web.",
    instruction="""
    You are a research assistant with web search capabilities.

    When asked about recent events, latest products or current facts,
    use search_web instead of relying on memorized information.
    Prefer official sources, verify dates, and include source URLs.
    Do not treat photo captions as evidence of new product releases.
    Never claim that a search happened unless the tool was used.
    If search results do not substantiate an answer, say so.
    Do not invent prices, product releases or exchange rates.
    """,
    tools=[search_web],
)
```

- `root_agent` is the discoverable ADK agent definition.
- `LiteLlm(model="ollama_chat/...")` connects ADK to Ollama's chat API.
- `tools=[search_web]` registers the **Python function**, enabling ADK to expose its name, docstring and argument schema to the model.
- The model **requests** a tool call; ADK **executes** it. Llama does not run your Python function directly.

Test that imports and construction work:

```powershell
python -c "from websearch_agent.agent import root_agent; print(root_agent.name)"
```

Expected: `websearch_agent`. This test alone does **not** prove Ollama responded.

## 9. Start the ADK development Web UI

From the **parent** `Agentwithwebsearch/` directory:

```powershell
.\.venv\Scripts\Activate.ps1
adk web --port 8000 .
```

Open `http://localhost:8000` and select `websearch_agent`.

**Why the parent?** The `.` argument is the *agents directory*. ADK discovers agent application folders **inside** that directory, such as `websearch_agent/`. Running from inside `websearch_agent/` with `.` would direct discovery to the wrong level; use `..` to refer to the parent if starting there.

**Who starts the agent?** `adk web` runs the development server and loads agent definitions through ADK's runtime. You do **not** need to run `python agent.py` separately. The Ollama process is separate and should already be listening on port `11434`.

Try a basic model prompt, then:

> Use search_web to find the official Python documentation. List three results with their URLs.

ADK's Web UI on port `8000` is **not** the Ollama API. It is for development and debugging, not the recommended production serving setup.

## 10. Verify real tool execution in the ADK trace

Don't conclude a search happened simply because the model says it searched.

In the ADK Web UI, inspect **Trace / Events** for:

1. An LLM call generating `function_call`, with `name: search_web` and arguments such as `{"query":"official Python documentation"}`.
2. The Python tool executing and returning `function_response` with `status: success` and actual results.
3. A second model call incorporating those results into the final answer.

In the observed project trace, two LLM calls took much longer than the search tool (approximately **29.78 s** and **20.97 s**, versus **1.09 s** for the search). This is a local observation, not a benchmark; it illustrates that local model inference can dominate end-to-end response latency.

## 11. Debugging the incorrect “latest iPhone” answer

The test question `Which is the latest iPhone?` initially generated an inaccurate answer naming iPhone 15 models and combining them with a newer A20 Pro chip. After changing the prompt, the model answered iPhone 17, which was also outdated for October 2026.

The trace established that tool invocation **did happen**. The model sent `search_web` a query similar to `latest iPhone model`, which returned snippets including:

- A Wikipedia **image caption** listing iPhone 15 models.
- An Apple landing-page snippet mentioning **A20 Pro** but not explicitly naming a phone in that snippet.
- Generic Apple model comparison and support pages.
- A comparison article mentioning **iPhone 18**.

The LLM appears to have mixed details across results instead of verifying an authoritative announcement. This is a **grounding/evidence-selection failure**, compounded by broad search queries and short snippets. The exact reason for each generated token cannot be established from the trace.

### How to debug this systematically

1. Verify whether `function_call` occurred. If not, improve tool routing or enforce retrieval in application code.
2. Inspect the **exact query** the model generated. A query without the current year can retrieve old results.
3. Inspect the **actual returned snippets**, their relevance, dates and source quality.
4. Verify whether the correct answer is present in the tool results. If it is, the failure is downstream in answer generation/evidence selection.
5. Compare against official manufacturer release announcements; search snippets are not always sufficient evidence.
6. If needed, enhance the tool to search official sites or fetch page content, and evaluate a stronger tool-calling model.

Reproduce a targeted search directly:

```powershell
python -c "from websearch_agent.tools import search_web; from pprint import pprint; pprint(search_web('Apple latest iPhone October 2026 site:apple.com'))"
```

**Important:** Merely instructing a model to “always search” does not guarantee that it will follow the instruction. For production correctness, enforce mandatory retrieval and validation using Python application logic, add trusted-source filtering, and test with an evaluation set.

## 12. Common troubleshooting

| Symptom | Likely cause | What to check |
|---|---|---|
| `adk` not recognized | ADK not installed in active environment or `.venv/Scripts` not on PATH | Activate `.venv`; `python -m pip show google-adk`; `Get-Command adk`; try `.\.venv\Scripts\adk.exe --help` |
| Yellow/blue VS Code import underline | Pylance interpreter/diagnostic | Hover over underline; select `.venv` using **Python: Select Interpreter**; confirm imports in terminal |
| `No module named 'mcp'` inside LiteLLM error | Missing dependency in tested environment | Add `mcp` to requirements, reinstall, `python -c "import mcp"`, `python -m pip check` |
| Agent not visible in Web UI | Incorrect agents directory/layout/import errors | Run `adk web --port 8000 .` from project root; check `__init__.py` and `root_agent` |
| Ollama connection error | Ollama stopped or wrong URL/port | `Invoke-RestMethod http://localhost:11434/api/tags`; verify model name |
| Tool exists but isn't called | Tool-selection failure | Inspect model `function_call`, improve description and prompt, or enforce call in code |
| Tool called but answer wrong | Poor query, outdated snippets, weak grounding | Inspect `function_response`; compare primary source; improve retrieval and evaluation |

Useful checks:

```powershell
python -c "import sys; print(sys.executable)"
python -m pip --version
python -m pip show google-adk litellm ddgs mcp
python -m pip check
Get-Command adk
```

## 13. Next steps (not implemented yet)

1. Improve search quality: date-aware queries, primary-source lookup, page extraction, and explicit evidence validation.
2. Add `convert_currency(amount, from_currency, to_currency)` backed by a reliable exchange-rate API. Validate ISO currency codes, handle failures and timestamps, and **never ask the LLM to invent an exchange rate**.
3. Test orchestration: ask for an online product price, inspect source currency and price, obtain a live rate, then convert using deterministic Python arithmetic.
4. Write automated tests for tools and evaluation cases for the agent.
5. Explore converting functions into an **MCP server** if interoperability with other hosts is necessary.
6. Later, containerize the app and design an appropriate production API/session store and model-hosting strategy on AWS. **Don't use `adk web` as your production server.**

## Key lessons

- **Python package**: `__init__.py` controls package initialization; importing a package can execute module-level code.
- **Agent vs model**: ADK orchestrates; Ollama performs local inference.
- **Agent vs tool**: Agent chooses operations; ADK executes registered Python tools.
- **Tool integration vs MCP**: Registering a Python function as an ADK tool does not require an MCP server.
- **Correctness**: A successful tool call is not proof of a correct final answer.
- **Engineering workflow**: Validate individual functions, examine runtime traces, then improve retrieval and model behavior separately.
