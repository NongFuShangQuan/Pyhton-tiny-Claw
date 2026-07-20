# py-tiny-claw: 极简智能体驾驭引擎 (Python 版)

## 目录

- [核心设计哲学](#核心设计哲学)
- [系统架构](#系统架构)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [三种启动模式](#三种启动模式)
  - [模式一：CLI 一次性任务](#模式一cli-一次性任务)
  - [模式二：交互式 REPL](#模式二交互式-repl)
  - [模式三：飞书 AgentOps ChatOps](#模式三飞书-agentops-chatops)
  - [模式四：自动化跑分](#模式四自动化跑分)
- [核心模块详解](#核心模块详解)
  - [Schema — 消息与工具协议](#schema--消息与工具协议)
  - [Provider — LLM 适配层](#provider--llm-适配层)
  - [Context — 上下文管理](#context--上下文管理)
  - [Engine — ReAct 主循环](#engine--react-主循环)
  - [Tools — 工具系统](#tools--工具系统)
  - [Observability — 可观测性](#observability--可观测性)
  - [Feishu — 飞书集成](#feishu--飞书集成)
  - [Eval — 自动化评测](#eval--自动化评测)
- [交互式 CLI 命令参考](#交互式-cli-命令参考)
- [与 Go 版的对应关系](#与-go-版的对应关系)
- [Go 版与 Python 版实现差异](#go-版与-python-版实现差异)
- [PyInstaller 打包](#pyinstaller-打包)
- [环境变量参考](#环境变量参考)
- [运行测试](#运行测试)
- [License](#license)

---

## 核心设计哲学

### Harness over Framework

真正的壁垒不在于调用大模型 API，而在于如何调度工具、管理上下文和安全拦截。`py-tiny-claw` 不是一个"框架"，而是一套精密的驾驭工程系统——它像马的缰绳一样，精确地控制 Agent 的每一步行为。

### 极简即是正义

仅向大模型暴露四个图灵完备的原语：`read_file`、`write_file`、`edit_file`、`bash`。不提供任何过度封装的 high-level 工具，迫使 Agent 像人类工程师一样用基础工具组合解决复杂问题。

### 状态外部化

将长程任务的记忆与执行计划持久化在 `PLAN.md` 与 `TODO.md` 两个物理文件中，而非依赖大模型不可靠的短期记忆。Agent 启动时自动嗅探这两个文件实现断点续传。

### 安全内建

危险命令在执行前拦截并触发人工审批流程（飞书 ChatOps 模式下），而非事后审计。工作区路径越界保护确保 Agent 无法读写工作区以外的文件系统。

---

## 系统架构

`py-tiny-claw` 由七个核心子系统协同工作，构成完整的 Agent 驾驶循环：

```
┌─────────────────────────────────────────────────────────────────┐
│                        py-tiny-claw                              │
├───────────┬───────────┬───────────┬───────────┬────────────────┤
│  Provider │  Context  │  Engine   │   Tools   │ Observability  │
│  (大脑)   │  (记忆)   │  (心脏)   │  (手脚)   │   (神经)      │
│           │           │           │           │                │
│ DeepSeek  │ System    │ ReAct     │ read_file │ Span 链路追踪  │
│ 智谱 GLM  │ Prompt    │ 主循环    │ write_file│ Cost 成本追踪  │
│ Claude    │ Compactor │ Reminder  │ edit_file │ JSON 导出      │
│           │ Recovery  │ Reporter  │ bash      │                │
│           │ Skill     │ Plan Mode │ Subagent  │                │
├───────────┴───────────┴───────────┴───────────┴────────────────┤
│                      Feishu / CLI / Eval                        │
│                    (飞书Bot / 终端 / 跑分)                       │
└─────────────────────────────────────────────────────────────────┘
```

| 子系统 | 比喻 | 职责 |
|--------|------|------|
| **Provider** | 大脑 | 适配 DeepSeek / 智谱 GLM / Claude 等多厂商协议，发送上下文并接收推理结果 |
| **Context** | 记忆 | 组装 System Prompt、管理会话历史、上下文压缩、技能加载、错误恢复提示注入 |
| **Engine** | 心脏 | ReAct 主循环（支持慢思考两阶段）、Terminal/飞书双 Reporter、死循环预警注入 |
| **Tools** | 手脚 | 工具注册中心 + 中间件拦截链 + 四大原语 + 子代理委派（Subagent） |
| **Observability** | 神经 | 轻量 Span 树链路追踪 + 按 Token 计费的成本追踪器，数据导出至 `.claw/traces/` |
| **Feishu** | 外延 | 飞书 Webhook Bot、人工审批管理器（高危操作拦截 + 群聊审批） |
| **Eval** | 质检 | Benchmark 自动化跑分框架，支持沙箱隔离、验证脚本、多 Provider 对比 |

---

## 项目结构

```
StudyRL/
├── claw/                          # 核心库（对应 Go 版 internal/）
│   ├── schema/                    # 消息与工具协议类型定义
│   │   ├── __init__.py
│   │   └── message.py             # Message, ToolCall, ToolResult, ToolDefinition, Usage
│   │
│   ├── provider/                  # LLM 适配层（多厂商协议统一接口）
│   │   ├── __init__.py
│   │   ├── interface.py           # LLMProvider 抽象基类
│   │   ├── claude_provider.py     # Anthropic Claude / 智谱 Anthropic 兼容端点
│   │   └── openai_provider.py     # OpenAI 兼容协议（DeepSeek / 智谱 OpenAI SDK）
│   │
│   ├── context/                   # 上下文管理子系统
│   │   ├── __init__.py
│   │   ├── session.py             # Session 会话容器 + 全局 SessionManager 注册表
│   │   ├── composer.py            # System Prompt 组装器（核心纪律 + Plan Mode + AGENTS.md + Skills）
│   │   ├── compactor.py           # 上下文压缩策略（超阈值自动折叠早期消息）
│   │   ├── recovery.py            # 工具执行失败时的智能救援指引注入
│   │   └── skill.py               # 技能外挂加载器（扫描 .claw/skills/*/SKILL.md）
│   │
│   ├── engine/                    # Agent 主循环引擎
│   │   ├── __init__.py
│   │   ├── loop.py                # ReAct 主循环 + 子代理循环（AgentEngine）
│   │   ├── reporter.py            # Reporter 抽象接口
│   │   ├── terminal_reporter.py   # 终端彩色 Reporter（rich 渲染 / 纯文本回退）
│   │   └── reminder.py            # 死循环探测与干预注入器（基于参数指纹）
│   │
│   ├── tools/                     # 工具注册与执行系统
│   │   ├── __init__.py
│   │   ├── registry.py            # Registry 注册中心 + 中间件拦截链 + BaseTool 抽象
│   │   ├── read_file.py           # 文件读取工具（工作区路径越界保护）
│   │   ├── write_file.py          # 文件写入工具（工作区路径越界保护）
│   │   ├── edit_file.py           # 模糊文本替换工具（old_string → new_string）
│   │   ├── bash.py                # Bash 命令执行工具（超时控制 + 路径越界保护）
│   │   ├── subagent.py            # 子代理委派工具（spawn_subagent 探路者）
│   │   └── _args.py               # 工具参数解析辅助
│   │
│   ├── observability/             # 可观测性子系统
│   │   ├── __init__.py
│   │   ├── trace.py               # Span 树 + TraceContext 显式传递 + JSON 导出
│   │   └── tracker.py             # CostTracker 装饰式 Provider（Token 计数 + 模型定价）
│   │
│   ├── feishu/                    # 飞书集成子系统
│   │   ├── __init__.py
│   │   ├── bot.py                 # 飞书 Webhook Bot 调度器 + FeishuReporter
│   │   └── approval.py            # 人工审批管理器 + 危险命令特征库
│   │
│   ├── eval/                      # 自动化评测子系统
│   │   ├── __init__.py
│   │   └── benchmark.py           # BenchmarkRunner（沙箱隔离 + 验证脚本）
│   │
│   ├── cli/                       # 交互式 CLI
│   │   ├── __init__.py
│   │   └── app.py                 # InteractiveCLI（REPL + 斜杠命令 + Rich 渲染）
│   │
│   └── factory.py                 # 公共工厂函数（create_provider / build_registry）
│
├── tests/                         # 单元测试
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
├── workspace/                     # Agent 默认工作区
│   ├── AGENTS.md                  # 项目专属指南（Agent 启动时自动加载进 System Prompt）
│   └── .claw/
│       └── skills/                # 技能外挂目录（每个技能一个 SKILL.md）
│
├── main.py                        # CLI 入口（一次性任务 / 交互式 REPL）
├── agentops.py                    # 飞书 AgentOps 服务端入口
├── bench.py                       # 跑分脚本入口
├── pyproject.toml                 # 项目配置与依赖声明
├── claw.spec                      # PyInstaller 打包配置
├── build_exe.ps1                  # PyInstaller 打包脚本
├── claw.bat                       # Windows 快速启动批处理
├── .env                           # 环境变量配置（API Key 等）
├── .gitignore
├── PLAN.md                        # （运行时产物）任务架构计划
├── TODO.md                        # （运行时产物）任务执行清单
└── README.md
```

---

## 快速开始

### 环境要求

- Python 3.10+（推荐 3.11 / 3.12）
- Windows / Linux / macOS

### 安装

```bash
# 克隆项目后进入目录
cd StudyRL

# 安装核心依赖
pip install -e .

# 安装开发依赖（含 pytest、ruff、PyInstaller）
pip install -e ".[dev]"
```

### 配置环境变量

复制项目根目录的 `.env` 文件，填入至少一个 LLM Provider 的 API Key：

| Provider | 环境变量 | 获取地址 | 默认模型 |
|----------|---------|---------|---------|
| DeepSeek | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/api_keys | `deepseek-v4-flash` |
| 智谱 GLM | `ZHIPU_API_KEY` | https://open.bigmodel.cn/ | `glm-4.5-air` |

**飞书 AgentOps 模式额外需要：**

| 环境变量 | 说明 |
|----------|------|
| `FEISHU_APP_ID` | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret |
| `FEISHU_ENCRYPT_KEY` | （可选）消息加密密钥 |
| `FEISHU_VERIFY_TOKEN` | （可选）事件验证 Token |

---

## 三种启动模式

### 模式一：CLI 一次性任务

适用于脚本化批处理、CI/CD 流水线中的自动任务：

```bash
# 使用 DeepSeek（默认 Provider）
python main.py --prompt "在工作区创建一个 hello.py，输出 Hello World" --dir ./workspace

# 使用智谱 GLM
python main.py --prompt "你的任务描述" --provider zhipu --model glm-4.5-air

# 使用 DeepSeek-R1 推理模型处理复杂架构设计
python main.py --prompt "设计并实现一个线程安全的 LRU 缓存" --model deepseek-reasoner

# 开启慢思考模式
python main.py --prompt "重构当前目录下的所有 Python 文件" --thinking

# 关闭 Plan Mode（不生成 PLAN.md / TODO.md）
python main.py --prompt "简单的代码修改" --no-plan

# 使用指定会话 ID 支持断点续传
python main.py --prompt "继续之前的任务" --session my_project_session
```

**完整参数列表：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--prompt` | string | `None` | 任务描述。不提供则进入交互模式 |
| `--dir` | string | `.` | Agent 工作区目录路径 |
| `--provider` | string | `deepseek` | LLM Provider：`deepseek` / `zhipu` |
| `--model` | string | `deepseek-v4-flash` | 模型名称 |
| `--thinking` | flag | `False` | 开启慢思考两阶段推理 |
| `--no-plan` | flag | `False` | 关闭 Plan Mode 状态外部化 |
| `--session` | string | `cli_default_session` | 会话 ID（相同 ID 共享会话历史） |

![image-20260720112650792](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260720112650792.png)

![image-20260720112658898](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260720112658898.png)

### 模式二：交互式 REPL

默认启动模式，提供类似 Claude Code 的终端交互体验：

```bash
# 直接启动交互模式
python main.py

# 指定工作区和模型
python main.py --dir ./my_project --model deepseek-chat --thinking

# 安装为命令行工具后
pip install -e .
claw                          # 全局可用
claw --thinking --model glm-4.5-air
```

交互式 REPL 支持：
- **多行输入**：行尾加 `\` 续行
- **斜杠命令**：`/help` `/model` `/session` `/cost` `/thinking` `/plan` 等
- **Rich 渲染**：彩色 Markdown 输出、工具调用状态实时显示
- **会话持久化**：支持切换 Session 实现多任务隔离
- **历史记录**：通过 readline 保存到 `~/.claw_history`

详细命令列表见 [交互式 CLI 命令参考](#交互式-cli-命令参考)。

![image-20260720112731588](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260720112731588.png)

![image-20260720112743990](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260720112743990.png)

### 模式三：飞书 AgentOps ChatOps

启动飞书 Webhook 服务，通过飞书群聊与 Agent 交互：

```bash
# 配置环境变量
export CLAW_PROVIDER=deepseek
export CLAW_MODEL=deepseek-v4-flash

# 启动服务（默认监听 :48080）
python agentops.py
```

**飞书 ChatOps 特性：**
- 接收飞书群聊消息，自动拉起 Agent 异步处理
- **人工审批流程**：Agent 执行 `write_file`/`edit_file`/危险 bash 命令时，自动向群聊发送审批请求，等待人工回复 `approve <task_id>` 或 `reject <task_id>`
- 高危命令拦截：`rm -rf`、`sudo`、`kill`、`systemctl`、`nginx -s` 等操作自动触发审批
- 通过 `threading.local` 实现 Reporter 上下文跨中间件传递

### 模式四：自动化跑分

内置 Benchmark 框架，支持沙箱隔离执行和自动验证：

```bash
# DeepSeek 跑分（默认）
python bench.py

# 智谱跑分
python bench.py --provider zhipu --model glm-4.5-air

# DeepSeek-R1 跑分
python bench.py --model deepseek-reasoner
```

**预设评测用例：**

| 用例 ID | 名称 | 测试目标 |
|---------|------|---------|
| `test_001_edit` | 模糊替换工具准确性 | 验证 `edit_file` 的 old_string 匹配与替换能力 |
| `test_002_code_gen` | 代码阅读与文件创建 | 验证 Agent 阅读代码并生成单元测试的综合能力 |

BenchmarkRunner 为每个用例创建独立沙箱目录（`workspace/{test_id}_{timestamp}/`），自动执行 setup 脚本准备靶机环境，Agent 执行后运行 validate 脚本验证结果。

---

## 核心模块详解

### Schema — 消息与工具协议

位置：`claw/schema/`

定义了整个系统中流转的统一数据结构：

| 类型 | 用途 |
|------|------|
| `Message` | 统一消息体，支持 system/user/assistant 三种角色，可携带 tool_calls 和 tool_call_id |
| `ToolCall` | 模型侧工具调用请求，arguments 支持 dict/str/bytes 多种格式，提供 to_dict / to_str 等多种序列化方法 |
| `ToolResult` | 工具执行结果，包含 output 文本和 is_error 标志 |
| `ToolDefinition` | 工具的 JSON Schema 定义（name + description + input_schema），用于传递给 LLM |
| `Usage` | 单次 API 调用的 Token 消耗（prompt_tokens + completion_tokens） |

关键设计：`Message.role` 使用 `RoleSystem = "system"`、`RoleUser = "user"`、`RoleAssistant = "assistant"` 三个常量，保持与 OpenAI / Anthropic 协议的兼容性。`ToolCall.arguments` 采用 `Any` 类型以兼容不同 Provider 的序列化格式。

### Provider — LLM 适配层

位置：`claw/provider/`

通过 `LLMProvider` 抽象基类统一多厂商接口：

```
LLMProvider (ABC)
├── DeepSeekProvider      → OpenAI 兼容协议（openai Python SDK）
├── ZhipuOpenAIProvider   → OpenAI 兼容协议（智谱端点 + openai SDK）
└── ClaudeProvider        → Anthropic 协议（anthropic Python SDK）
```

**Provider 工厂函数** (`claw/factory.py`)：

```python
def create_provider(name: str, model: str) -> LLMProvider:
    if name == "deepseek":
        return NewDeepSeekProvider(model)
    elif name == "zhipu":
        return NewZhipuOpenAIProvider(model)
```

新增 Provider 只需实现 `LLMProvider.generate(messages, available_tools) -> Message` 方法。

### Context — 上下文管理

位置：`claw/context/`

四个子系统协同管理 Agent 的"记忆"：

#### 1. Session（会话容器）
- 线程安全的消息历史存储（`threading.RLock`）
- `get_working_memory(limit)` 获取最近 N 条消息，自动处理截断边缘的孤儿 tool_result
- 累计 Token 消耗与费用统计
- `GlobalSessionMgr`：进程级 Session 注册表，支持多会话并发隔离

#### 2. PromptComposer（System Prompt 组装）
组装发给大模型的完整 System Prompt，包含四层内容：

1. **核心身份与纪律**：角色定义 + 六条操作规范（使用 ls 检查文件、先读后写、中文回复等）
2. **Plan Mode 指令**（可选）：强制三步流程——环境嗅探 → 单步执行与打勾 → 迷失自救
3. **AGENTS.md**：工作区 `workspace/AGENTS.md` 的项目专属指南
4. **Skill 外挂**：`.claw/skills/*/SKILL.md` 中定义的专业技能

#### 3. Compactor（上下文压缩）
- 阈值：200,000 字符，保留最近 6 条原始消息
- 超出阈值时自动折叠早期消息：工具输出截断保留 200 字符摘要，推理过程折叠为占位文本
- 保护 System Prompt 不被压缩
- 消息级别粒度，不破坏协议结构

#### 4. RecoveryManager（错误恢复）
根据工具类型和报错特征注入针对性的救援指引：
- `edit_file` 失败 → 提示先 read_file 获取最新内容
- `read_file` / `write_file` 路径错误 → 提示先用 ls/find 探查目录
- `bash` 超时 → 提示使用 nohup 后台执行
- `bash` 语法错误 → 提示检查引号转义

#### 5. SkillLoader（技能外挂）
扫描 `workspace/.claw/skills/` 下所有 `SKILL.md` 文件：
- 支持 YAML frontmatter（`name`、`description` 字段）
- 技能正文作为执行指南注入 System Prompt
- 与 Claude Code 的 `.claw/skills/` 目录约定完全兼容

### Engine — ReAct 主循环

位置：`claw/engine/`

#### AgentEngine（主循环）

核心 ReAct 循环 (`loop.py:64-224`)：

```
┌──────────────────────────────────────────────────────┐
│                    ReAct 主循环                        │
├──────────────────────────────────────────────────────┤
│  1. 组装 System Prompt (PromptComposer.build())       │
│  2. 获取可用工具列表 (Registry.get_available_tools()) │
│  3. 获取工作记忆 (Session.get_working_memory(20))     │
│  4. 上下文压缩 (Compactor.compact())                  │
│  5. [可选] Phase 1: 慢思考 (enable_thinking)          │
│  6. Phase 2: Action 推理 (调用 LLM + 工具列表)       │
│  7. 工具调用？→ 并发执行 → 回到步骤 2                 │
│     无工具调用？→ 任务结束                             │
│  8. 每一步后：死循环检测 (ReminderInjector)            │
└──────────────────────────────────────────────────────┘
```

**关键特性：**
- **慢思考两阶段** (`enable_thinking=True`)：先调用 LLM 进行纯文本推理（无工具），再调用 LLM 执行工具操作
- **并发工具执行**：使用 `ThreadPoolExecutor`（最多 8 线程）并发执行多个工具调用
- **截断修复**：自动检测上下文截断导致的首条消息为 Assistant 角色，注入占位 User 消息稳住多轮协议
- **Plan Mode**：启用后 System Prompt 会强制 Agent 按 SOP 流程执行（嗅探 PLAN.md/TODO.md → 单步执行 → 实时打勾）

#### Subagent 子代理循环

- 独立于主 Session 的只读探索循环，最多 10 轮
- 子代理 System Prompt 强制其必须使用工具，禁止盲猜
- 返回纯文本摘要报告给主 Agent

#### Reporter（事件报告器接口）

```python
class Reporter(ABC):
    def on_thinking(self, ctx=None) -> None        # 慢思考开始
    def on_tool_call(self, name, args, ctx=None)   # 工具调用开始
    def on_tool_result(self, name, result, is_error, ctx=None)  # 工具结果
    def on_message(self, content, ctx=None)         # Agent 文本回复
```

两种实现：
- `TerminalReporter`：优先使用 rich 库渲染彩色输出，无 rich 时退化为纯文本
- `FeishuReporter`：通过飞书 Bot 将事件流发送到群聊

#### ReminderInjector（死循环干预）

- 对每次工具调用生成 `MD5(tool_name + arguments)` 参数指纹
- 同一指纹连续失败 ≥ 3 次时，自动注入强力修正指令 System Reminder
- 提示 Agent 停止盲目重试、改变策略、向人类求助

### Tools — 工具系统

位置：`claw/tools/`

#### 注册中心架构

```
Registry (ABC)
└── RegistryImpl
    ├── _tools: dict[str, BaseTool]    # 工具注册表
    ├── _middlewares: list[MiddlewareFunc]  # 中间件链
    ├── register(tool)                 # 注册工具
    ├── use(middleware)                # 挂载中间件
    ├── get_available_tools()          # 获取工具定义列表
    └── execute(ctx, call)             # 执行工具（含 Span 埋点 + 中间件拦截）
```

**中间件签名：** `(ToolCall) -> (allowed: bool, reject_reason: str)`

中间件按注册顺序依次执行，任一返回 `allowed=False` 即阻断执行。飞书 AgentOps 模式通过中间件实现高危命令的审批拦截。

#### 四大核心工具

| 工具 | 功能 | 安全策略 |
|------|------|---------|
| `read_file` | 读取工作区内的文件内容 | 路径越界检测，拒绝访问工作区之外的路径 |
| `write_file` | 创建或覆写工作区内的文件 | 路径越界检测 |
| `edit_file` | 基于 old_string 匹配的模糊文本替换 | 路径越界检测；需要精确的 old_string 匹配 |
| `bash` | 执行 Shell 命令 | 路径越界检测；超时控制；危险命令触发审批 |

**`edit_file` 设计精髓：** 非行号编辑，而是类似 `sed` 的模糊匹配替换。Agent 提供 `old_string`（文件中实际存在的文本片段），引擎精确匹配后替换为 `new_string`。匹配到多处时报错并提示增加上下文；未匹配到时提示重新 read_file。

#### Subagent 子代理工具

- 工具名：`spawn_subagent`
- 用途：主 Agent 将深度探索任务委派给只读子代理（read_file + bash 只读命令）
- 子代理仅能阅读和搜索，不能修改文件
- 返回精炼摘要报告

### Observability — 可观测性

位置：`claw/observability/`

#### Span 链路追踪

轻量级 Span 树实现，不使用 OpenTelemetry 等重型框架：

```python
ctx, root_span = StartSpan(TraceContext(), "Agent.Run")
# ... 执行过程中创建子 Span ...
EndSpan(root_span)
ExportTraceToFile(root_span, work_dir, session_id)
# → 导出至 workspace/.claw/traces/trace_{session_id}_{timestamp}.json
```

- `TraceContext` 显式携带当前 Span，避免弱类型上下文传递的线程安全问题
- Span 属性使用 `threading.Lock` 保护并发写入
- 最终序列化为 JSON 文件，包含完整的调用树、耗时和元数据

#### CostTracker（成本追踪）

装饰器模式包裹真实 Provider：

- 自动统计每次 API 调用的 `prompt_tokens` 和 `completion_tokens`
- 内置模型定价表（`PricingModel`），按百万 Token 单价实时计算费用（人民币）
- 累加到 Session 级别：`total_prompt_tokens`、`total_completion_tokens`、`total_cost_cny`

**当前内置定价（元/百万 tokens）：**

| 模型 | 输入价格 | 输出价格 |
|------|---------|---------|
| `glm-4.5-air` | 0.15 | 0.15 |
| `deepseek-chat` | 1.0 | 2.0 |
| `deepseek-reasoner` | 4.0 | 16.0 |
| `deepseek-v4-flash` | 1.0 | 2.0 |

### Feishu — 飞书集成

位置：`claw/feishu/`

#### FeishuBot（飞书 Bot 调度器）

- 使用 `requests` 直连飞书 OpenAPI（不依赖官方 SDK），更轻量、便于排错
- 自动管理 `tenant_access_token` 的获取与刷新（带线程锁 + 过期前 30 秒提前刷新）
- 通过 Flask 暴露 `/webhook/event` HTTP 端点

#### 高危命令审批流程

```
Agent 调用 bash/write_file/edit_file
    ↓
Registry 中间件检查
    ↓
IsDangerousCommand() 命中？
    ├── 否 → 直接放行
    └── 是 → GlobalApprovalMgr.wait_for_approval()
              ↓
         飞书群聊发送审批通知（含 Task ID）
              ↓
         线程挂起（threading.Event.wait()）
              ↓
         人类回复 "approve <task_id>" 或 "reject <task_id>"
              ↓
         resolve_approval() → event.set() 唤醒
              ↓
         返回 (allowed, reason) → 放行或拒绝
```

**危险命令特征库** (`_DANGEROUS_PATTERNS`)：
- `rm -r` — 递归删除
- `sudo` — 提权操作
- `drop` — 数据库危险命令
- `>.*\.go` — 覆写源码文件
- `nginx -s` — 服务控制
- `systemctl` — 系统服务管理
- `kill` — 进程终止

### Eval — 自动化评测

位置：`claw/eval/`

BenchmarkRunner 提供完整的自动化评测流水线：

1. **沙箱创建**：为每个 TestCase 创建独立的 `workspace/{test_id}_{timestamp}/` 目录
2. **靶机准备**：执行 `setup_script` 创建测试所需的初始文件
3. **Agent 执行**：创建独立 Session + CostTracker + AgentEngine，执行 `task_prompt`
4. **结果验证**：运行 `validate_script`，检查 return code 判定通过/失败
5. **报告输出**：汇总所有用例的通过率、耗时和成本

`TestCase` 字段：

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识 |
| `name` | 用例名称 |
| `setup_script` | Bash 脚本，用于准备初始环境 |
| `task_prompt` | 给 Agent 的任务描述 |
| `validate_script` | Bash 脚本，return code 0 表示通过 |

---

## 交互式 CLI 命令参考

交互模式下以 `/` 开头触发命令：

| 命令 | 说明 |
|------|------|
| `/help`, `/h` | 显示帮助信息 |
| `/exit`, `/quit`, `/q` | 退出程序 |
| `/clear` | 清空当前会话，创建新会话 ID |
| `/model [name]` | 查看或切换模型 |
| `/provider [name]` | 查看或切换 Provider（`deepseek` / `zhipu`） |
| `/thinking` | 开关慢思考模式 |
| `/plan` | 开关 Plan Mode |
| `/session [id]` | 查看或切换会话 ID |
| `/cost` | 查看当前会话 Token 消耗与费用 |
| `/status` | 显示当前状态（模型、Provider、Plan、费用） |
| `/dir [path]` | 查看或切换工作区目录 |
| `/workdir [path]` | 同 `/dir` |

## 

---

## PyInstaller 打包

项目支持通过 PyInstaller 打包为独立 Windows 可执行文件：

```powershell
# 使用预配置的打包脚本
.\build_exe.ps1

# 输出：dist/claw.exe
```

打包后只需将 `.env` 文件放在 `claw.exe` 同级目录即可运行。双击 `claw.exe` 启动交互式 CLI。

> 也可通过 `claw.bat` 快速启动（无需打包，直接运行 Python 源码）。

---

## 环境变量参考

### LLM Provider（至少配置一个）

| 变量 | 说明 | 示例 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `sk-xxx` |
| `ZHIPU_API_KEY` | 智谱 GLM API Key | `xxx.yyy.zzz` |

### 飞书（仅 AgentOps 模式需要）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FEISHU_APP_ID` | 飞书应用 App ID | — |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret | — |
| `FEISHU_ENCRYPT_KEY` | 消息加密密钥（可选） | — |
| `FEISHU_VERIFY_TOKEN` | 事件验证 Token（可选） | — |

### 服务配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AGENTOPS_PORT` | AgentOps Webhook 监听端口 | `48080` |
| `CLAW_PROVIDER` | 默认 LLM Provider | `deepseek` |
| `CLAW_MODEL` | 默认模型名称 | `deepseek-v4-flash` |

---

## 运行测试

```bash
# 运行全部测试
pytest

# 运行特定模块测试
pytest tests/test_compactor.py -v
pytest tests/test_registry.py -v
pytest tests/test_reminder.py -v
pytest tests/test_edit_file.py -v

# 代码检查
ruff check claw/
```

---

## License

MIT License.
