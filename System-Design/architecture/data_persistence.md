# Data persistence (`utils/data_persistence/`)

## `RunDataManager` (`run_data_manager.py`)

- **Root:** `run_data/{run_id}/` (run_id from ctor, or `RUN_DATA_ID` / naming rules with `run_name`, objectives).
- **Layout:**
  - `prompt_evolution/llm_traces/` — copies of LLM traces for analysis.
  - `end_state/` — `game_state/`, `map_data/`, `frame_cache/`, `videos/`, `logs/`.
  - `agent_scratch_space/` — tool-written files; objectives copies land here via sync helpers.
- **Metadata:** written into **`cumulative_metrics.json`** via `LLMLogger` (not a separate `metadata.json`).

## `.pokeagent_cache/{run_id}/` (runtime)

Resolved by `get_cache_directory()` / `get_cache_path(...)` when a run is active.

**Notable files:** `checkpoint.state`, `checkpoint_llm.txt`, `cumulative_metrics.json`, `objectives.json`, `memory.json` (or legacy `knowledge_base.json`), `skills.json`, `subagents.json`, `milestones_progress.json`, `trajectory_history.jsonl`, `frame_cache.json`, CLI `workspace/`, backend memory dirs (`claude_memory`, …).

**Reusable bootstrap artifacts:** finalized runs also populate `.pokeagent_cache/{run_id}/bootstrap/` with `memory.json`, `skills.json`, `subagents.json`, and the latest evolved orchestrator policy when present.

## Trajectories vs conversation

| Artifact | What it is |
|----------|------------|
| **`trajectory_history.jsonl`** (cache) | **Primary** append-only log from `RunDataManager.log_trajectory` (step, reasoning, action, pre_state, outcome, …). |
| **`run_data/{run_id}/trajectory_history.jsonl`** | Synced copy when `sync_trajectories_to_run_data()` runs; also the **fallback** read path in `trajectory_window.resolve_trajectory_path` if the cache file is missing. |
| **`prompt_evolution/.../trajectories.jsonl`** (historical) | Older experiments only; **not** referenced by current `resolve_trajectory_path` / `PromptOptimizer.get_recent_trajectories`. |
| **PokeAgent `conversation_history`** | In-memory rolling window; **not** restored from backup zip by itself. |

## Backups (`backup_manager.py`)

- **`create_cache_backup`:** zips **run-specific cache** into `backups/{run_id}/<timestamp>_<objective>.zip`. Skips unreadable container-owned files with warnings.
- **`restore_cache_from_backup`:** extracts into target cache dir (optional pre-restore zip of current cache).
- **Restore semantics:** restores **on-disk** cache state (objectives, memory, checkpoint, **trajectory_history.jsonl** if present, metrics files, etc.). **Does not** rebuild the orchestrator’s in-memory short-term chat; long-term stores on disk load on next use.
- **Milestone-triggered backups:** when objective-triggered backups are absent, milestone completion can trigger backups for CLI runs and objective-free runs such as `simplest`.

## Run export on finalization

- **Archival copy:** `RunDataManager._export_bootstrap_artifacts()` writes a second bootstrap bundle to `run_data/{run_id}/end_state/game_state/bootstrap/`.
- **Purpose:** future runs can point `--bootstrap-from` at either the live cache bootstrap directory or the archived run-data copy.

## Related

- CLI bind mounts: [cli_agents/external_mcp_agents.md](cli_agents/external_mcp_agents.md).
- Metrics file: [metrics_logging.md](metrics_logging.md).
