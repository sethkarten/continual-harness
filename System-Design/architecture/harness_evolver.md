# HarnessEvolver (ContinualHarness scaffold)

Ground truth: `agents/utils/harness_evolver.py`, `agents/PokeAgent.py`, `agents/utils/prompt_optimizer.py`, `utils/stores/*`.

For intent and roadmap only (not behavior authority), see [CONTINUAL_HARNESS_PLAN_V1.md](../plans/CONTINUAL_HARNESS_PLAN_V1.md) and [CONTINUAL_HARNESS_PLAN_V2.md](../plans/CONTINUAL_HARNESS_PLAN_V2.md).

## Purpose

`HarnessEvolver` runs **mid-episode** “full harness” evolution: it keeps **prompt** optimization and adds **subagent**, **skill**, and **memory** passes driven by recent trajectories. It is the implementation behind `--enable-prompt-optimization` when `scaffold="continualharness"`.

## When it is constructed

In `PokeAgent.__init__`, all must hold:

- `enable_prompt_optimization=True`
- An initialized `run_data_manager` (`get_run_data_manager()`); otherwise startup raises.
- `scaffold == "continualharness"`

Then `create_harness_evolver(...)` runs with defaults matching the factory: `base_prompt_path=CONTINUAL_HARNESS_BASE_ORCHESTRATOR_POLICY_PATH`, `system_prompt_path=CONTINUAL_HARNESS_SYSTEM_PROMPT_PATH` (see `agents/utils/harness_evolver.py`). `PokeAgent.prompt_optimizer` is set to `harness_evolver.prompt_optimizer`.

For `scaffold == "continualharness"`, orchestrator **system instructions** load from `CONTINUAL_HARNESS_SYSTEM_PROMPT_PATH`. ContinualHarness is in `_NO_BUILTINS_SCAFFOLDS`, so built-in subagent **tool declarations** are not included (`include_builtins` is false for that set).

**Non-`continualharness` scaffolds** with `--enable-prompt-optimization` get **`PromptOptimizer` only** (no subagent/skill/memory evolution passes); see `PokeAgent.__init__` else-branch.

## When evolution runs

After each orchestrator step (tool-call path and text-only path), if `optimization_enabled` and `harness_evolver` is set:

1. `should_evolve(active_step, optimization_frequency)`
2. If true: `evolve(current_step=active_step, num_trajectory_steps=optimization_frequency)` then `_inject_evolution_summary(results)`.

**Schedule** (`should_evolve` in `harness_evolver.py`):

- `current_step >= MIN_WARMUP_STEPS` (**25**)
- `current_step > 0`
- **Adaptive cadence** (the `optimization_frequency` argument from `PokeAgent` is **ignored** here): while `current_step <= 200`, fire when `current_step % 25 == 0`; after that, when `current_step % 100 == 0`.

`PokeAgent` still passes `optimization_frequency` into `evolve()` as **`num_trajectory_steps`** (trajectory window size for the evolution passes), not as the step schedule.

**PromptOptimizer-only** (non-`continualharness` with `--enable-prompt-optimization`): `should_optimize` uses the **same** adaptive cadence (every **25** steps while `current_step <= 200`, then every **100**), but **`MIN_PROMPT_OPTIMIZATION_WARMUP_STEPS = 50`** in `prompt_optimizer.py`—first prompt optimization fires at step **50**, not **25** like `HarnessEvolver.should_evolve`.

If there are **no** recent trajectories, `evolve()` returns `{"skipped": True, "reason": "no_trajectories"}` before incrementing `generation` or appending `evolution_log.jsonl`.

## Four passes (order and isolation)

`evolve()` runs four passes **in order**, each wrapped in `try`/`except` so one failure does not block the others:

| Pass | Role |
|------|------|
| **prompt** | `PromptOptimizer.optimize_prompt` — rewrites tracked base prompt. |
| **subagents** | Text VLM returns JSON `create` / `update` / `retire`; applied via **subagent store**. |
| **skills** | JSON `add` / `update`; **skill store**; warns if `run_code` is heavy and `run_skill` unused. |
| **memory** | JSON `add` / `update` using lighter trajectory context (last ~20 steps for curation text); **memory store**. |

Then `generation` increments and `_save_evolution_log` runs.

## Dependencies

- **PromptOptimizer**: Composed in `HarnessEvolver.__init__`; provides `get_recent_trajectories`, `_format_trajectories_for_analysis`, `optimize_prompt`, and **text-only** `text_vlm` for evolution queries.
- **Trajectories**: `PromptOptimizer.get_recent_trajectories` uses `resolve_trajectory_path` (`trajectory_window.py`): cache `trajectory_history.jsonl`, then `run_data/{run_id}/trajectory_history.jsonl`.
- **Stores** (lazy import per pass): `get_memory_store`, `get_skill_store`, `get_subagent_store` — resolve cache dir via `get_cache_directory()`.

## Persistence

- **Audit trail**: `get_cache_path("evolution_log.jsonl")` — one JSON line per completed `evolve()` with generation, step, timestamp, per-pass summaries, optional store counts.
- **Subagents / skills / memory**: CRUD through stores → **`subagents.json`**, **`skills.json`**, **`memory.json`** under the run cache (`BaseStore` + each store’s `file_name`).

## Subagent tool allowlist (`_ALWAYS_AVAILABLE_TOOLS`)

Evolved subagents’ `available_tools` are **filtered** to this frozenset; if none valid, the code falls back to `["press_buttons"]`. The set is the **continualharness** surface in code: **no** `navigate_to`, `get_walkthrough`, `lookup_pokemon_info`, or **`get_progress_summary`**. It includes e.g. `press_buttons`, `complete_direct_objective`, `get_game_state`, `get_map_data`, `process_memory`, `process_skill`, `run_skill`, `run_code`, `process_subagent`, `execute_custom_subagent`, `process_trajectory_history`, `replan_objectives`.

The VLM prompt text may **mention** other tools in prose; **persistence** is constrained by the allowlist — `navigate_to` cannot be saved on evolved subagents.

## Constants

- `MIN_WARMUP_STEPS = 25` (warmup before first evolution)
- Full allowlist: see `harness_evolver.py`

**Prompt files:** `CONTINUAL_HARNESS_SYSTEM_PROMPT_PATH` and related ContinualHarness assets follow **`GAME_TYPE`** via `agents/prompts/paths.py` (separate Red vs Emerald markdown where present).

## Related

- [pokeagent.md](pokeagent.md) — scaffolds and orchestration loop.
- [data_persistence.md](data_persistence.md) — cache layout and trajectory file.
- [implementation_gaps.md](implementation_gaps.md) — store evolution / `mutation_history` caveats.
