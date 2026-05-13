# In-repo agent (`run.py`, `agents/PokeAgent.py`)

## `run.py`

- **Before importing `agents`:** sets **`os.environ["GAME_TYPE"]`** from **`--game red|emerald`** (default `emerald`) so `agents/prompts/paths.py` resolves the correct prompt files at import time.
- Starts **server** subprocess: `python -m server.app --port … --game …`, with env: `RUN_DATA_ID`, `LLM_METRICS_WRITE_ENABLED=true`, **`GAME_TYPE`** (same as `--game`), optional `LOAD_CHECKPOINT_MODE`, `EXCLUDE_BUILTIN_SUBAGENTS` for minimal scaffolds, `LLM_SESSION_ID` if set.
- Starts optional **frame server** on `port+1`.
- Starts **agent** subprocess with `LLM_METRICS_WRITE_ENABLED=false` (server remains single writer to disk).
- **`--load-checkpoint`:** resolves `get_cache_path("checkpoint.state")`, passes `--load-state` to server, sets `LOAD_CHECKPOINT_MODE=true` when file exists.

## Scaffolds (`CUSTOM_AGENT_CONFIGS`)

| Key | Class | Notes |
|-----|--------|------|
| `pokeagent` | `PokeAgent` | Full tool scaffolding; **`--enable-prompt-optimization`** enables **`PromptOptimizer` only** (trajectory-based prompt rewrites), not HarnessEvolver. |
| `simple` | `PokeAgent` | Minimal scaffold. No built-in subagent tools; keeps the generic tool registry and `replan_objectives`; `EXCLUDE_BUILTIN_SUBAGENTS=1` on server. `supports_prompt_optimization` is false. |
| `simplest` | `PokeAgent` | Stronger ablation than `simple`: no built-in subagent tools, no objectives block in the prompt, and no local subagent/tool registry at all. `EXCLUDE_BUILTIN_SUBAGENTS=1` on server. |
| `continualharness` | `PokeAgent` | Minimal built-ins like `simple`, plus **`evolve_harness` tool** in declarations. **`HarnessEvolver`** (full harness evolution) runs only when **`--enable-prompt-optimization`** is set; scaffold name alone does **not** turn evolution on (see [harness_evolver.md](harness_evolver.md)). |
| `vision_only` | `VisionOnlyAgent` | Separate module. |
| `autonomous_cli` | `PokeAgent` | Legacy alias for full `PokeAgent`. |

## `PokeAgent` orchestration

- **`MCPToolAdapter`:** maps logical tool names to **`POST {server_url}/mcp/...`** (see [client_server.md](client_server.md)).
- **Loop (conceptually):** build prompt (system + history + images) → VLM returns function calls → dispatch handlers → update history, metrics, trajectory logging.
- **Context limits:** `max_context_chars` / `target_context_chars`; compaction over time.
- **Prompt assets:** `agents/prompts/paths.py` selects **`POKEAGENT.md` / `POKEAGENT_RED.md`**, **`SIMPLE.md` / `SIMPLE_RED.md`**, optimizer **`system_prompt.md` / `system_prompt_red.md`**, and ContinualHarness **`continual-harness/SYSTEM_PROMPT.md` / `SYSTEM_PROMPT_RED.md`** based on **`GAME_TYPE`**. Scaffold still picks which of those families loads (e.g. `simple` → `SIMPLE*`).
- **Bootstrap reuse:** `run.py --bootstrap-from` imports prior `memory.json`, `skills.json`, and `subagents.json`, re-paths entries under `bootstrapped/`, and can inject an evolved orchestrator prompt override before the normal scaffold prompt.

## Tools: HTTP vs local

**HTTP (MCP routes on server):** everything in `MCPToolAdapter.endpoint_map` (game, memory, objectives, map, wiki, …).

**Local-only (no `/mcp/...` route):** examples include `run_code`, `run_skill`, `process_trajectory_history`, and **local subagent** invocations (`subagent_reflect`, `subagent_verify`, …) implemented with a **tool-less `VLM`** inside `PokeAgent` / `SubagentExecutor`.

## Tool surface assembly

- **Central registry:** `agents/tools/registry.py` is now the source of truth for scaffold-visible tool declarations.
- **Expert scaffolds:** `pokeagent` gets expert tools such as `get_progress_summary`, `navigate_to`, walkthrough/wiki access, plus built-in local subagent tools.
- **Minimal scaffolds:** `simple` and `continualharness` keep the generic registry and `replan_objectives`, but exclude built-in local subagent tools.
- **`simplest`:** no local subagent tool declarations are added at all.

## Local subagents (`agents/subagents/`)

- **One-step:** reflect, verify, summarize, gym puzzle — separate VLM calls; logged with readable names (e.g. `Subagent_Reflect`).
- **Delegated loops:** e.g. battler (consumes real steps, returns summary), planner (`replan_objectives` / full sequence tools on server).
- **Trajectory text:** `resolve_trajectory_path` in `agents/subagents/utils/trajectory_window.py` — **cache** `.pokeagent_cache/{run_id}/trajectory_history.jsonl` first, else **`run_data/{run_id}/trajectory_history.jsonl`** if present. Window size is clamped via `clamp_trajectory_window` (`DEFAULT_TRAJECTORY_WINDOW` / `MAX_TRAJECTORY_WINDOW`). See [data_persistence.md](data_persistence.md).

## Reflection vs MCP

- The game server does **not** expose `/mcp/reflect`.
- “Reflection” in PokeAgent is the **`subagent_reflect`** (local VLM) path, not the CLI MCP server.
