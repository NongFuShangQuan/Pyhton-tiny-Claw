# py-tiny-claw: A Minimalist Agent Harness Engine (Python Edition)

## Table of Contents

- [Core Design Philosophy](#core-design-philosophy)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Four Launch Modes](#four-launch-modes)
  - [Mode 1: CLI One-shot Task](#mode-1-cli-one-shot-task)
  - [Mode 2: Interactive REPL](#mode-2-interactive-repl)
  - [Mode 3: Feishu AgentOps ChatOps](#mode-3-feishu-agentops-chatops)
  - [Mode 4: Automated Benchmarking](#mode-4-automated-benchmarking)
- [Core Module Details](#core-module-details)
  - [Schema — Message & Tool Protocol](#schema--message--tool-protocol)
  - [Provider — LLM Adapter Layer](#provider--llm-adapter-layer)
  - [Context — Context Management](#context--context-management)
  - [Engine — ReAct Main Loop](#engine--react-main-loop)
  - [Tools — Tool System](#tools--tool-system)
  - [Observability](#observability)
  - [Feishu — Feishu Integration](#feishu--feishu-integration)
  - [Eval — Automated Evaluation](#eval--automated-evaluation)
- [Interactive CLI Command Reference](#interactive-cli-command-reference)
- [PyInstaller Packaging](#pyinstaller-packaging)
- [Environment Variables Reference](#environment-variables-reference)
- [Running Tests](#running-tests)
- [License](#license)

---

## Core Design Philosophy

### Harness over Framework

The real barrier isn't calling LLM APIs — it's orchestrating tools, managing context, and intercepting unsafe operations. `py-tiny-claw` is not a "framework" but a precision harness engineering system — like a horse's reins, it precisely controls every step of the agent's behavior.

### Minimalism is Correctness

Only four Turing-complete primitives are exposed to the LLM: `read_file`, `write_file`, `edit_file`, and `bash`. No over-engineered high-level tools are provided, forcing the agent to solve complex problems by composing basic tools — just like a human engineer.

### State Externalization

Long-running task memory and execution plans are persisted in two physical files (`PLAN.md` and `TODO.md`) rather than relying on the LLM's unreliable short-term memory. The agent automatically sniffs these files on startup to resume from checkpoints.

### Security Built-In

Dangerous commands are intercepted before execution and trigger a human approval workflow (in Feishu ChatOps mode), not after-the-fact auditing. Workspace path boundary protection ensures the agent cannot read or write outside the designated file system.

---

## System Architecture

`py-tiny-claw` consists of seven core subsystems working in concert to form a complete agent driving loop:

```
┌─────────────────────────────────────────────────────────────────┐
│                        py-tiny-claw                              │
├───────────┬───────────┬───────────┬───────────┬────────────────┤
│  Provider │  Context  │  Engine   │   Tools   │ Observability  │
│  (Brain)  │ (Memory)  │  (Heart)  │ (Hands)   │   (Nerves)    │
│           │           │           │           │                │
│ DeepSeek  │ System    │ ReAct     │ read_file │ Span Tracing   │
│ Zhipu GLM │ Prompt    │ Main Loop │ write_file│ Cost Tracking  │
│ Claude    │ Compactor │ Reminder  │ edit_file │ JSON Export    │
│           │ Recovery  │ Reporter  │ bash      │                │
│           │ Skill     │ Plan Mode │ Subagent  │                │
├───────────┴───────────┴───────────┴───────────┴────────────────┤
│                      Feishu / CLI / Eval                        │
│                  (Feishu Bot / Terminal / Benchmark)            │
└─────────────────────────────────────────────────────────────────┘
```

| Subsystem | Analogy | Responsibility |
|-----------|---------|---------------|
| **Provider** | Brain | Adapts DeepSeek / Zhipu GLM / Claude multi-vendor protocols, sends context and receives inference results |
| **Context** | Memory | Assembles System Prompt, manages conversation history, compacts context, loads skills, injects error recovery hints |
| **Engine** | Heart | ReAct main loop (with two-phase slow-thinking), Terminal/Feishu dual Reporter, infinite-loop detection and intervention |
| **Tools** | Hands/Feet | Tool registry + middleware interception chain + four primitives + subagent delegation |
| **Observability** | Nerves | Lightweight Span tree tracing + per-token cost tracker, data exported to `.claw/traces/` |
| **Feishu** | Reach | Feishu Webhook Bot, human approval manager (dangerous operation interception + group chat approval) |
| **Eval** | QA | Automated benchmark runner, supports sandbox isolation, validation scripts, and multi-provider comparison |

---

## Project Structure

```
StudyRL/
├── claw/                          # Core library (corresponds to Go edition's internal/)
│   ├── schema/                    # Message & tool protocol type definitions
│   │   ├── __init__.py
│   │   └── message.py             # Message, ToolCall, ToolResult, ToolDefinition, Usage
│   │
│   ├── provider/                  # LLM adapter layer (unified multi-vendor interface)
│   │   ├── __init__.py
│   │   ├── interface.py           # LLMProvider abstract base class
│   │   ├── claude_provider.py     # Anthropic Claude / Zhipu Anthropic-compatible endpoint
│   │   └── openai_provider.py     # OpenAI-compatible protocol (DeepSeek / Zhipu via OpenAI SDK)
│   │
│   ├── context/                   # Context management subsystem
│   │   ├── __init__.py
│   │   ├── session.py             # Session container + global SessionManager registry
│   │   ├── composer.py            # System Prompt composer (core discipline + Plan Mode + AGENTS.md + Skills)
│   │   ├── compactor.py           # Context compaction strategy (auto-collapse early messages on overflow)
│   │   ├── recovery.py            # Intelligent recovery guidance injection on tool failure
│   │   └── skill.py               # Skill plugin loader (scans .claw/skills/*/SKILL.md)
│   │
│   ├── engine/                    # Agent main loop engine
│   │   ├── __init__.py
│   │   ├── loop.py                # ReAct main loop + subagent loop (AgentEngine)
│   │   ├── reporter.py            # Reporter abstract interface
│   │   ├── terminal_reporter.py   # Terminal colored Reporter (rich rendering / plain text fallback)
│   │   └── reminder.py            # Infinite-loop detection & intervention injector (fingerprint-based)
│   │
│   ├── tools/                     # Tool registration & execution system
│   │   ├── __init__.py
│   │   ├── registry.py            # Registry + middleware chain + BaseTool abstraction
│   │   ├── read_file.py           # File read tool (workspace path boundary protection)
│   │   ├── write_file.py          # File write tool (workspace path boundary protection)
│   │   ├── edit_file.py           # Fuzzy text replacement tool (old_string → new_string)
│   │   ├── bash.py                # Bash command execution (timeout control + path boundary protection)
│   │   ├── subagent.py            # Subagent delegation tool (spawn_subagent scout)
│   │   └── _args.py               # Tool argument parsing helper
│   │
│   ├── observability/             # Observability subsystem
│   │   ├── __init__.py
│   │   ├── trace.py               # Span tree + explicit TraceContext passing + JSON export
│   │   └── tracker.py             # CostTracker decorator-style Provider (token counting + model pricing)
│   │
│   ├── feishu/                    # Feishu integration subsystem
│   │   ├── __init__.py
│   │   ├── bot.py                 # Feishu Webhook Bot dispatcher + FeishuReporter
│   │   └── approval.py            # Human approval manager + dangerous command signature database
│   │
│   ├── eval/                      # Automated evaluation subsystem
│   │   ├── __init__.py
│   │   └── benchmark.py           # BenchmarkRunner (sandbox isolation + validation scripts)
│   │
│   ├── cli/                       # Interactive CLI
│   │   ├── __init__.py
│   │   └── app.py                 # InteractiveCLI (REPL + slash commands + Rich rendering)
│   │
│   └── factory.py                 # Common factory functions (create_provider / build_registry)
│
├── tests/                         # Unit tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_schema.py
│   ├── test_session.py
│   ├── test_compactor.py
│   ├── test_reminder.py
│   ├── test_registry.py
│   ├── test_recovery.py
│   ├── test_provider.py
│   └── test_edit_file.py
│
├── workspace/                     # Default agent workspace
│   ├── AGENTS.md                  # Project-specific guide (auto-loaded into System Prompt on startup)
│   └── .claw/
│       └── skills/                # Skill plugin directory (one SKILL.md per skill)
│
├── main.py                        # CLI entry point (one-shot / interactive REPL)
├── agentops.py                    # Feishu AgentOps server entry point
├── bench.py                       # Benchmark script entry point
├── pyproject.toml                 # Project configuration & dependencies
├── claw.spec                      # PyInstaller packaging config
├── build_exe.ps1                  # PyInstaller packaging script
├── claw.bat                       # Windows quick-start batch file
├── .env                           # Environment variable config (API keys, etc.)
├── .gitignore
├── PLAN.md                        # (Runtime artifact) Task architecture plan
├── TODO.md                        # (Runtime artifact) Task execution checklist
└── README.md
```

---

## Quick Start

### Requirements

- Python 3.10+ (3.11 / 3.12 recommended)
- Windows / Linux / macOS

### Installation

```bash
# Enter project directory after cloning
cd StudyRL

# Install core dependencies
pip install -e .

# Install dev dependencies (includes pytest, ruff, PyInstaller)
pip install -e ".[dev]"
```

### Configure Environment Variables

Copy the `.env` file from the project root and fill in at least one LLM Provider API Key:

| Provider | Variable | Get From | Default Model |
|----------|---------|----------|---------------|
| DeepSeek | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/api_keys | `deepseek-v4-flash` |
| Zhipu GLM | `ZHIPU_API_KEY` | https://open.bigmodel.cn/ | `glm-4.5-air` |

**Additionally required for Feishu AgentOps mode:**

| Variable | Description |
|----------|-------------|
| `FEISHU_APP_ID` | Feishu App ID |
| `FEISHU_APP_SECRET` | Feishu App Secret |
| `FEISHU_ENCRYPT_KEY` | (Optional) Message encryption key |
| `FEISHU_VERIFY_TOKEN` | (Optional) Event verification token |

---

## Four Launch Modes

### Mode 1: CLI One-shot Task

For scripted batch processing and CI/CD pipeline automation:

```bash
# Use DeepSeek (default Provider)
python main.py --prompt "Create a hello.py that prints Hello World in the workspace" --dir ./workspace

# Use Zhipu GLM
python main.py --prompt "Your task description" --provider zhipu --model glm-4.5-air

# Use DeepSeek-R1 reasoning model for complex architecture design
python main.py --prompt "Design and implement a thread-safe LRU cache" --model deepseek-reasoner

# Enable slow-thinking mode
python main.py --prompt "Refactor all Python files in the current directory" --thinking

# Disable Plan Mode (no PLAN.md / TODO.md generation)
python main.py --prompt "Simple code modification" --no-plan

# Use a specific session ID for checkpoint resumption
python main.py --prompt "Continue previous task" --session my_project_session
```

**Full parameter list:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--prompt` | string | `None` | Task description. If omitted, enters interactive mode |
| `--dir` | string | `.` | Agent workspace directory path |
| `--provider` | string | `deepseek` | LLM Provider: `deepseek` / `zhipu` |
| `--model` | string | `deepseek-v4-flash` | Model name |
| `--thinking` | flag | `False` | Enable slow-thinking two-phase reasoning |
| `--no-plan` | flag | `False` | Disable Plan Mode state externalization |
| `--session` | string | `cli_default_session` | Session ID (same ID shares conversation history) |

### Mode 2: Interactive REPL

The default launch mode, providing a Claude Code-like terminal interaction experience:

```bash
# Start interactive mode directly
python main.py

# Specify workspace and model
python main.py --dir ./my_project --model deepseek-chat --thinking

# After installing as a CLI tool
pip install -e .
claw                          # Globally available
claw --thinking --model glm-4.5-air
```

Interactive REPL features:
- **Multi-line input**: End a line with `\` to continue
- **Slash commands**: `/help` `/model` `/session` `/cost` `/thinking` `/plan` and more
- **Rich rendering**: Colored Markdown output, real-time tool call status display
- **Session persistence**: Switch sessions for multi-task isolation
- **History**: Saved to `~/.claw_history` via readline

See [Interactive CLI Command Reference](#interactive-cli-command-reference) for the full command list.

### Mode 3: Feishu AgentOps ChatOps

Start a Feishu Webhook service to interact with the agent through Feishu group chat:

```bash
# Configure environment variables
export CLAW_PROVIDER=deepseek
export CLAW_MODEL=deepseek-v4-flash

# Start the service (default listens on :48080)
python agentops.py
```

**Feishu ChatOps features:**
- Receives Feishu group chat messages and automatically launches the agent for async processing
- **Human approval workflow**: When the agent executes `write_file`/`edit_file`/dangerous bash commands, it automatically sends approval requests to the group chat and waits for human response (`approve <task_id>` or `reject <task_id>`)
- Dangerous command interception: `rm -rf`, `sudo`, `kill`, `systemctl`, `nginx -s` and similar operations automatically trigger approval
- Reporter context passed across middleware via `threading.local`

### Mode 4: Automated Benchmarking

Built-in benchmark framework with sandbox isolation and automatic validation:

```bash
# DeepSeek benchmark (default)
python bench.py

# Zhipu benchmark
python bench.py --provider zhipu --model glm-4.5-air

# DeepSeek-R1 benchmark
python bench.py --model deepseek-reasoner
```

**Preset test cases:**

| Case ID | Name | Test Target |
|---------|------|-------------|
| `test_001_edit` | Fuzzy replacement tool accuracy | Validates `edit_file` old_string matching and replacement capability |
| `test_002_code_gen` | Code reading & file creation | Validates the agent's ability to read code and generate unit tests |

BenchmarkRunner creates an isolated sandbox directory (`workspace/{test_id}_{timestamp}/`) for each test case, auto-executes the setup script to prepare the target environment, runs the agent, then executes the validate script to verify results.

---

## Core Module Details

### Schema — Message & Tool Protocol

Location: `claw/schema/`

Defines the unified data structures that flow through the entire system:

| Type | Purpose |
|------|---------|
| `Message` | Unified message body, supports system/user/assistant roles, can carry tool_calls and tool_call_id |
| `ToolCall` | Model-side tool call request, arguments support dict/str/bytes formats, with to_dict / to_str serialization methods |
| `ToolResult` | Tool execution result, containing output text and is_error flag |
| `ToolDefinition` | JSON Schema definition for tools (name + description + input_schema), passed to the LLM |
| `Usage` | Token consumption for a single API call (prompt_tokens + completion_tokens) |

Key design: `Message.role` uses `RoleSystem = "system"`, `RoleUser = "user"`, `RoleAssistant = "assistant"` constants to maintain compatibility with OpenAI / Anthropic protocols. `ToolCall.arguments` uses `Any` type to accommodate different Provider serialization formats.

### Provider — LLM Adapter Layer

Location: `claw/provider/`

Unified multi-vendor interface via the `LLMProvider` abstract base class:

```
LLMProvider (ABC)
├── DeepSeekProvider      → OpenAI-compatible protocol (openai Python SDK)
├── ZhipuOpenAIProvider   → OpenAI-compatible protocol (Zhipu endpoint + openai SDK)
└── ClaudeProvider        → Anthropic protocol (anthropic Python SDK)
```

**Provider factory function** (`claw/factory.py`):

```python
def create_provider(name: str, model: str) -> LLMProvider:
    if name == "deepseek":
        return NewDeepSeekProvider(model)
    elif name == "zhipu":
        return NewZhipuOpenAIProvider(model)
```

Adding a new Provider only requires implementing the `LLMProvider.generate(messages, available_tools) -> Message` method.

### Context — Context Management

Location: `claw/context/`

Five subsystems collaboratively manage the agent's "memory":

#### 1. Session
- Thread-safe message history storage (`threading.RLock`)
- `get_working_memory(limit)` retrieves the most recent N messages, automatically handling orphaned tool_result at truncation edges
- Accumulated token consumption and cost tracking
- `GlobalSessionMgr`: process-level Session registry supporting multi-session concurrent isolation

#### 2. PromptComposer
Assembles the complete System Prompt sent to the LLM, containing four layers:

1. **Core identity & discipline**: Role definition + six operating conventions (use ls to check files, read before write, respond in Chinese, etc.)
2. **Plan Mode instructions** (optional): Mandatory three-step SOP — environment sniffing → single-step execution with checkmarks → lost recovery
3. **AGENTS.md**: Project-specific guide from `workspace/AGENTS.md`
4. **Skill plugins**: Specialized skills defined in `.claw/skills/*/SKILL.md`

#### 3. Compactor
- Threshold: 200,000 characters, retains the most recent 6 raw messages
- Auto-collapses early messages when exceeding the threshold: tool outputs truncated to 200-character summaries, reasoning folded into placeholder text
- Protects System Prompt from compaction
- Message-level granularity, does not break protocol structure

#### 4. RecoveryManager
Injects targeted recovery guidance based on tool type and error characteristics:
- `edit_file` failure → prompts to `read_file` first for latest content
- `read_file` / `write_file` path errors → prompts to use `ls`/`find` to explore directories first
- `bash` timeout → prompts to use `nohup` for background execution
- `bash` syntax errors → prompts to check quote escaping

#### 5. SkillLoader
Scans all `SKILL.md` files under `workspace/.claw/skills/`:
- Supports YAML frontmatter (`name`, `description` fields)
- Skill body injected into System Prompt as execution guide
- Fully compatible with Claude Code's `.claw/skills/` directory convention

### Engine — ReAct Main Loop

Location: `claw/engine/`

#### AgentEngine (Main Loop)

Core ReAct loop (`loop.py:64-224`):

```
┌──────────────────────────────────────────────────────┐
│                   ReAct Main Loop                     │
├──────────────────────────────────────────────────────┤
│  1. Assemble System Prompt (PromptComposer.build())   │
│  2. Get available tools (Registry.get_available_tools()) │
│  3. Get working memory (Session.get_working_memory(20))  │
│  4. Context compaction (Compactor.compact())           │
│  5. [Optional] Phase 1: Slow thinking (enable_thinking) │
│  6. Phase 2: Action inference (call LLM + tool list)   │
│  7. Tool calls? → Concurrent execution → Back to step 2 │
│     No tool calls? → Task complete                     │
│  8. After each step: Loop detection (ReminderInjector) │
└──────────────────────────────────────────────────────┘
```

**Key features:**
- **Two-phase slow thinking** (`enable_thinking=True`): First calls the LLM for pure text reasoning (no tools), then calls the LLM for tool operations
- **Concurrent tool execution**: Uses `ThreadPoolExecutor` (max 8 threads) to execute multiple tool calls concurrently
- **Truncation repair**: Auto-detects when the first message is an Assistant role due to context truncation, injects a placeholder User message to stabilize the multi-turn protocol
- **Plan Mode**: When enabled, the System Prompt forces the agent to follow SOP (sniff PLAN.md/TODO.md → single-step execution → real-time checkmarks)

#### Subagent Loop

- Read-only exploration loop independent from the main Session, up to 10 rounds
- Subagent System Prompt mandates tool usage, prohibits blind guessing
- Returns a plain-text summary report to the main agent

#### Reporter

```python
class Reporter(ABC):
    def on_thinking(self, ctx=None) -> None        # Slow thinking start
    def on_tool_call(self, name, args, ctx=None)   # Tool call start
    def on_tool_result(self, name, result, is_error, ctx=None)  # Tool result
    def on_message(self, content, ctx=None)         # Agent text response
```

Two implementations:
- `TerminalReporter`: Prefers rich library for colored output, falls back to plain text
- `FeishuReporter`: Sends event stream to group chat via Feishu Bot

#### ReminderInjector (Infinite Loop Intervention)

- Generates `MD5(tool_name + arguments)` parameter fingerprints for each tool call
- When the same fingerprint fails consecutively ≥ 3 times, auto-injects a forceful correction instruction as a System Reminder
- Prompts the agent to stop blind retries, change strategy, and ask the human for help

### Tools — Tool System

Location: `claw/tools/`

#### Registry Architecture

```
Registry (ABC)
└── RegistryImpl
    ├── _tools: dict[str, BaseTool]         # Tool registry
    ├── _middlewares: list[MiddlewareFunc]   # Middleware chain
    ├── register(tool)                       # Register a tool
    ├── use(middleware)                      # Mount middleware
    ├── get_available_tools()                # Get tool definitions
    └── execute(ctx, call)                   # Execute tool (with Span tracing + middleware interception)
```

**Middleware signature:** `(ToolCall) -> (allowed: bool, reject_reason: str)`

Middlewares execute in registration order; any returning `allowed=False` blocks execution. Feishu AgentOps mode uses middleware to implement dangerous command approval interception.

#### Four Core Tools

| Tool | Function | Security Policy |
|------|----------|----------------|
| `read_file` | Read file content within the workspace | Path boundary detection, rejects access outside workspace |
| `write_file` | Create or overwrite a file within the workspace | Path boundary detection |
| `edit_file` | Fuzzy text replacement based on old_string matching | Path boundary detection; requires precise old_string matching |
| `bash` | Execute shell commands | Path boundary detection; timeout control; dangerous commands trigger approval |

**`edit_file` design essence:** Not line-number editing, but `sed`-like fuzzy match and replace. The agent provides `old_string` (a text fragment that actually exists in the file), and the engine precisely matches and replaces it with `new_string`. Multiple matches trigger an error with a hint to add more context; no match prompts a re-read.

#### Subagent Tool

- Tool name: `spawn_subagent`
- Purpose: Main agent delegates deep exploration tasks to a read-only subagent (read_file + read-only bash commands)
- Subagent can only read and search, cannot modify files
- Returns a refined summary report

### Observability

Location: `claw/observability/`

#### Span Tracing

Lightweight Span tree implementation without heavy frameworks like OpenTelemetry:

```python
ctx, root_span = StartSpan(TraceContext(), "Agent.Run")
# ... create child Spans during execution ...
EndSpan(root_span)
ExportTraceToFile(root_span, work_dir, session_id)
# → Exports to workspace/.claw/traces/trace_{session_id}_{timestamp}.json
```

- `TraceContext` explicitly carries the current Span, avoiding thread-safety issues in loosely-typed context passing
- Span attributes protected with `threading.Lock` for concurrent writes
- Serialized to JSON with complete call tree, timing, and metadata

#### CostTracker

Decorator pattern wrapping the real Provider:

- Auto-tracks `prompt_tokens` and `completion_tokens` for each API call
- Built-in model pricing table (`PricingModel`), calculates real-time cost by per-million-token pricing (CNY)
- Accumulates at Session level: `total_prompt_tokens`, `total_completion_tokens`, `total_cost_cny`

**Current built-in pricing (CNY per million tokens):**

| Model | Input Price | Output Price |
|-------|------------|---------------|
| `glm-4.5-air` | 0.15 | 0.15 |
| `deepseek-chat` | 1.0 | 2.0 |
| `deepseek-reasoner` | 4.0 | 16.0 |
| `deepseek-v4-flash` | 1.0 | 2.0 |

### Feishu — Feishu Integration

Location: `claw/feishu/`

#### FeishuBot

- Uses `requests` to directly connect to Feishu OpenAPI (no official SDK dependency) — lighter and easier to debug
- Auto-manages `tenant_access_token` acquisition and refresh (with thread lock + refresh 30 seconds before expiry)
- Exposes `/webhook/event` HTTP endpoint via Flask

#### Dangerous Command Approval Flow

```
Agent calls bash/write_file/edit_file
    ↓
Registry middleware check
    ↓
IsDangerousCommand() match?
    ├── No → Allow directly
    └── Yes → GlobalApprovalMgr.wait_for_approval()
              ↓
         Send approval notice to Feishu group chat (with Task ID)
              ↓
         Thread suspended (threading.Event.wait())
              ↓
         Human replies "approve <task_id>" or "reject <task_id>"
              ↓
         resolve_approval() → event.set() wakes thread
              ↓
         Returns (allowed, reason) → Allow or Reject
```

**Dangerous command signature database** (`_DANGEROUS_PATTERNS`):
- `rm -r` — Recursive deletion
- `sudo` — Privilege escalation
- `drop` — Dangerous database commands
- `>.*\.go` — Overwriting source files
- `nginx -s` — Service control
- `systemctl` — System service management
- `kill` — Process termination

### Eval — Automated Evaluation

Location: `claw/eval/`

BenchmarkRunner provides a complete automated evaluation pipeline:

1. **Sandbox creation**: Creates an isolated `workspace/{test_id}_{timestamp}/` directory for each TestCase
2. **Target preparation**: Executes `setup_script` to create the initial files needed for testing
3. **Agent execution**: Creates an independent Session + CostTracker + AgentEngine, executes `task_prompt`
4. **Result validation**: Runs `validate_script`, checks return code to determine pass/fail
5. **Report output**: Summarizes pass rate, timing, and cost across all test cases

`TestCase` fields:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier |
| `name` | Test case name |
| `setup_script` | Bash script for preparing the initial environment |
| `task_prompt` | Task description given to the agent |
| `validate_script` | Bash script, return code 0 means pass |

---

## Interactive CLI Command Reference

Commands prefixed with `/` in interactive mode:

| Command | Description |
|---------|-------------|
| `/help`, `/h` | Show help information |
| `/exit`, `/quit`, `/q` | Exit the program |
| `/clear` | Clear the current session and create a new session ID |
| `/model [name]` | View or switch the model |
| `/provider [name]` | View or switch Provider (`deepseek` / `zhipu`) |
| `/thinking` | Toggle slow-thinking mode |
| `/plan` | Toggle Plan Mode |
| `/session [id]` | View or switch session ID |
| `/cost` | View current session token consumption and cost |
| `/status` | Display current status (model, provider, plan, cost) |
| `/dir [path]` | View or switch workspace directory |
| `/workdir [path]` | Same as `/dir` |

---

## PyInstaller Packaging

The project supports packaging into a standalone Windows executable via PyInstaller:

```powershell
# Use the pre-configured packaging script
.\build_exe.ps1

# Output: dist/claw.exe
```

After packaging, simply place the `.env` file in the same directory as `claw.exe` to run. Double-click `claw.exe` to launch the interactive CLI.

> You can also use `claw.bat` for quick startup (runs Python source directly, no packaging needed).

---

## Environment Variables Reference

### LLM Provider (at least one required)

| Variable | Description | Example |
|----------|-------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `sk-xxx` |
| `ZHIPU_API_KEY` | Zhipu GLM API Key | `xxx.yyy.zzz` |

### Feishu (AgentOps mode only)

| Variable | Description | Default |
|----------|-------------|---------|
| `FEISHU_APP_ID` | Feishu App ID | — |
| `FEISHU_APP_SECRET` | Feishu App Secret | — |
| `FEISHU_ENCRYPT_KEY` | Message encryption key (optional) | — |
| `FEISHU_VERIFY_TOKEN` | Event verification token (optional) | — |

### Service Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTOPS_PORT` | AgentOps Webhook listening port | `48080` |
| `CLAW_PROVIDER` | Default LLM Provider | `deepseek` |
| `CLAW_MODEL` | Default model name | `deepseek-v4-flash` |

---

## Running Tests

```bash
# Run all tests
pytest

# Run specific module tests
pytest tests/test_compactor.py -v
pytest tests/test_registry.py -v
pytest tests/test_reminder.py -v
pytest tests/test_edit_file.py -v

# Lint check
ruff check claw/
```

---

## License

MIT License.
