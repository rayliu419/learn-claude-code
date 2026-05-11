#!/usr/bin/env python3
"""
ch01_prompt_chaining.py - Prompt Chaining with raw Anthropic API

Prompt Chaining decomposes a complex task into a sequence of focused steps.
Each step makes one LLM call; the previous step's output feeds into the next
step's prompt template. No tool use, no agent loop - just sequential calls.

    input -> [Step 1] -> output_1 -> [Step 2] -> output_2 -> ... -> final

Key ideas from the book (Chapter 1):
- Single prompts fail on multi-layered tasks (lost context, hallucination)
- Breaking into focused steps reduces cognitive load per call
- Structured output (JSON) between steps improves reliability
- Each step can have its own role / system prompt

---------------------------------------------------------------------------

PRODUCTION INSIGHTS (from Claude Code source analysis):

Claude Code's SYSTEM PROMPT ASSEMBLY is the closest production analogue to
prompt chaining. It's a multi-stage pipeline where each stage's output feeds
the next, ultimately producing the final prompt sent to the model.

THE ASSEMBLY PIPELINE (3 layers, 8+ stages):

+-----------------------------------------------------------------------+
| Layer 1: buildEffectiveSystemPrompt() - src/utils/systemPrompt.ts     |
|                                                                       |
| Priority-based selection (highest wins):                               |
|   0. Override prompt (loop mode - REPLACES everything)                |
|   1. Coordinator prompt (multi-agent coordinator mode)                |
|   2. Agent prompt (custom agent definition)                           |
|      - Proactive mode: APPEND to default (domain adds to base)        |
|      - Normal mode: REPLACE default                                   |
|   3. Custom prompt (--system-prompt CLI flag)                         |
|   4. Default prompt (standard Claude Code prompt)                     |
|   + appendSystemPrompt always added at end (except override)           |
+-----------------------------------------------------------------------+

Layer 2: getSystemPrompt() - src/constants/prompts.ts
┌────────────────────────────────────────────────────────────────────────────┐
│ The default prompt is itself a CHAIN of sections:                          │
│                                                                            │
│ STATIC SECTIONS (cacheable, deterministic):                                │
│  1. Intro      - identity + security instructions                          │
│  2. System     - tool permissions, tags, compression notice                │
│  3. Tasks      - coding style, code quality, security rules                │
│  4. Actions    - reversibility, blast radius, confirmation rules           │
│  5. Tools      - per-tool usage guidance (Read/Edit/Bash/Agent...)         │
│  6. Tone       - conciseness, markdown, code references                    │
│  7. Efficiency - "go straight to the point" output rules                   │
│                                                                            │
│ DYNAMIC SECTIONS (registry-managed, may vary per turn):                    │
│  8. Session guidance - skill commands, session state                       │
│  9. Memory           - auto memory system instructions                     │
│ 10. Env info         - CWD, platform, shell, model name, git status        │
│ 11. Language         - locale preference                                   │
│ 12. Output style     - custom style overrides                              │
│ 13. MCP instructions - connected MCP server guidance                       │
│ 14. Scratchpad       - isolated execution environment                      │
│ 15. FRC              - function result clearing config                     │
└────────────────────────────────────────────────────────────────────────────┘

Layer 3: Context injection - src/utils/api.ts + src/context.ts
┌────────────────────────────────────────────────────────────────────────────┐
│ appendSystemContext(systemPrompt, systemContext):                          │
│  • Appends gitStatus (branch, status, recent commits) to system prompt     │
│                                                                            │
│ prependUserContext(messages, userContext):                                 │
│  • Injects a <system-reminder> user message BEFORE the conversation        │
│  • Contains: CLAUDE.md content + currentDate                               │
│  • Marked isMeta:true (not counted as real user message)                   │
└────────────────────────────────────────────────────────────────────────────┘

Finally :  API call to Claude

KEY ARCHITECTURAL INSIGHTS:
┌────────────────────────────────────────────────────────────────────────────┐
│ 1. SEPARATION OF CONCERNS: Each "section" in the prompt is a pure function │
│    that takes config and returns a string (or null to exclude). This is    │
│    the same Step pattern from this chapter but applied to prompt           │
│    construction.                                                           │
│                                                                            │
│ 2. CACHE-AWARE ORDERING: Static sections come first (prompt cache hits),   │
│    dynamic sections last (may bust cache). A BOUNDARY MARKER separates     │
│    them. This is an optimization not found in simple prompt chaining.      │
│                                                                            │
│ 3. CONDITIONAL INCLUSION: Sections can return null to opt out. For        │
│    example, MCP instructions only appear when MCP servers are connected.   │
│    This makes the chain DYNAMIC - the number of "steps" varies per         │
│    invocation.                                                             │
│                                                                            │
│ 4. TWO INJECTION POINTS for external knowledge:                           │
│    - systemContext -> appended to system prompt (gitStatus)                │
│    - userContext   -> prepended as first user message (CLAUDE.md, date)    │
│    This split exists because Claude's API caches system prompts but not    │
│    user messages - so stable context goes in system, volatile context in   │
│    user.                                                                   │
│                                                                            │
│ 5. THE QUERY LOOP as an EVOLVED CHAIN:                                     │
│    After prompt assembly, the query loop (src/query.ts) implements a       │
│    DYNAMIC chain where the model itself decides the next step via tool     │
│    calls:                                                                  │
│    Turn 1: [assembled prompt + user msg] -> Model -> [tool calls]          │
│    Turn 2: [+ tool results] -> Model -> [more tool calls]                  │
│    Turn N: -> Model -> [final text response]                               │
│    This is prompt chaining where the "steps" aren't hardcoded - the model  │
│    plans them. The book's ch01 is the static version; Claude Code is       │
│    dynamic.                                                                │
└────────────────────────────────────────────────────────────────────────────┘

COMPARISON TABLE:
┌──────────────────┬──────────────────────────┬──────────────────────────────┐
│ Aspect           │ Book ch01 (this file)    │ Claude Code production       │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ Steps            │ Hardcoded (3 steps)      │ Dynamic (model decides)      │
│ Inter-step data  │ {placeholder} templates  │ messages array accumulate    │
│ Per-step system  │ Independent per step     │ One assembled prompt         │
│ Prompt assembly  │ N/A (simple)             │ 15+ section pipeline         │
│ Error handling   │ None                     │ Multi-layer recovery         │
│ Caching          │ None                     │ Cache-aware section order    │
│ Conditional steps│ None                     │ Null-returning sections      │
└──────────────────┴──────────────────────────┴──────────────────────────────┘

Usage:
    python agents_new/ch01_prompt_chaining.py
    /Users/liurui/workspace/learn-claude-code/.venv/bin/python3 agents_new/ch01_prompt_chaining.py
"""

import json
import logging
import os
from dataclasses import dataclass, field

from anthropic import Anthropic
from dotenv import load_dotenv

# ----------------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ.get("MODEL_ID", "claude-sonnet-4-6")

# ----------------------------------------------------------------------------
# Core: Step definition and chain runner
# ----------------------------------------------------------------------------

@dataclass
class Step:
    """One step in a prompt chain.

    Attributes:
        name:       Human-readable label for this step.
        system:     System prompt (role / instructions for this step).
        template:   User prompt template. Use {placeholder} for variables.
                    The chain runner injects previous output via these.
        output_key: Key name to store this step's output for downstream steps.
    """
    name: str
    system: str
    template: str
    output_key: str = "output"

@dataclass
class ChainResult:
    """Accumulated results from running a chain."""
    steps: list[dict] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)

    @property
    def final_output(self) -> str:
        return self.steps[-1]["output"] if self.steps else ""

def run_chain(steps: list[Step], initial_vars: dict[str, str],
              chain_name: str = "prompt-chain") -> ChainResult:
    """Execute a prompt chain: run each step sequentially, feeding outputs forward.

    Args:
        steps:        Ordered list of Step definitions.
        initial_vars: Starting variables (e.g. {"input": "some text"}).
        chain_name:   Name for the trace log.

    Returns:
        ChainResult with all intermediate outputs and variables.
    """
    result = ChainResult(variables=dict(initial_vars))

    logger.info(f"Chain '{chain_name}' started | steps={len(steps)} | input_keys={list(initial_vars.keys())}")

    for i, step in enumerate(steps, 1):
        # Format the template with all accumulated variables
        try:
            user_prompt = step.template.format(**result.variables)
        except KeyError as e:
            raise ValueError(
                f"Step '{step.name}' requires variable {e} "
                f"but available variables are: {list(result.variables.keys())}"
            )
        print(f"\n{'='*60}")
        print(f"Step {i}/{len(steps)}: {step.name}")
        print(f"{'='*60}")

        logger.info("[%s] Calling model=%s | system=%s...",
                     step.name, MODEL, step.system[:50])
        logger.debug("[%s] User prompt:\n%s", step.name, user_prompt)

        response = client.messages.create(
            model=MODEL,
            system=step.system,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4096,
        )

        output = next(
            block.text for block in response.content
            if hasattr(block, "text")
        )
        usage = response.usage

        logger.info("[%s] Done | input_tokens=%d | output_tokens=%d",
                     step.name, usage.input_tokens, usage.output_tokens)
        logger.debug("[%s] Output:\n%s", step.name, output[:500])

        # Store output for downstream steps
        result.variables[step.output_key] = output
        result.steps.append({
            "name": step.name,
            "output": output,
            "usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            },
        })

        # Show a preview
        preview = output[:300] + ("..." if len(output) > 300 else "")
        print(preview)

    total_in = sum(s["usage"]["input_tokens"] for s in result.steps)
    total_out = sum(s["usage"]["output_tokens"] for s in result.steps)
    logger.info("Chain '%s' completed | total_input_tokens=%d | total_output_tokens=%s",
                 chain_name, total_in, total_out)

    return result

# ----------------------------------------------------------------------------
# Demo: Tech spec extraction -> JSON -> Purchase recommendation
# ----------------------------------------------------------------------------

DEMO_CHAIN = [
    Step(
        name="Extract tech specs",
        system="You are a hardware analyst. Extract technical specifications precisely.",
        template=(
            "从以下产品描述中提取所有技术规格，列出每项参数及其分值: \n\n{input}"
        ),
        output_key="specs",
    ),
    Step(
        name="Convert to JSON",
        system=(
            "You are a data engineer. Output ONLY valid JSON, no markdown fences, "
            "no explanation."
        ),
        template=(
            "将以下技术规格转为 JSON 格式。要求包含以下键（如有）: \n"
            "\"cpu, cores, memory, storage, display, battery, weight, price\n"
            "\"缺失字段设为 null。\n\n{specs}"
        ),
        output_key="json_specs",
    ),
    Step(
        name="Purchase recommendation",
        system="You are a tech reviewer who gives concise, practical buying advice.",
        template=(
            "根据以下 JSON 规格，给出性能评价和购买建议（200 字以内）: \n\n{json_specs}"
        ),
        output_key="recommendation",
    ),
]

DEMO_INPUT = (
    "新款 MacBook Pro 配备 M4 Max 芯片，16 核 CPU 和 40 核 GPU，"
    "搭载 48GB 统一内存和 1TB SSD，16.2 英寸 Liquid Retina XDR 显示屏，"
    "续航长达 24 小时，重量 2.14 公斤，售价 27999 元。"
)

if __name__ == "__main__":
    result = run_chain(DEMO_CHAIN, initial_vars={"input": DEMO_INPUT}, chain_name="ch01-spec")

    print(f"\n{'='*60}")
    print(f"Final output:\n{result.final_output}")

    # Show intermediate JSON
    if "json_specs" in result.variables:
        print(f"\n{'-'*60}")
        print("Intermediate JSON:")
        try:
            parsed = json.loads(result.variables["json_specs"])
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(result.variables["json_specs"])