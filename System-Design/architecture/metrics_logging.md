# Metrics and logging

## `LLMLogger` (`utils/data_persistence/llm_logger.py`)

- Primary persistent aggregate: **`.pokeagent_cache/{run_id}/cumulative_metrics.json`** (tokens, cost, actions, steps, milestones, embedded run metadata).
- **`LLM_METRICS_WRITE_ENABLED`:** when not `"true"`, **disk** persistence of cumulative metrics is skipped for that process; **in-memory** aggregation may still update so `POST /sync_llm_metrics` can merge.
- **Single-writer pattern:** game **server** process sets `LLM_METRICS_WRITE_ENABLED=true`.
  - **`run.py` agent child:** `false` — logs through server or sync path as implemented.
  - **`run_cli.py` host:** `false` — accumulates CLI metrics in memory and **`POST /sync_llm_metrics`** to the server (`utils/agent_infrastructure/cli_agent_backends.py`, `utils/metric_tracking/server_metrics.py`).

## Server endpoint

- **`POST /sync_llm_metrics`** (`server/app.py`): applies the client’s cumulative payload, then **restores server-owned fields** (e.g. milestones, objectives, gameplay timers where applicable) and keeps **aggregate token/cost counters monotonic** (`max` with prior server values). The client’s **`steps` list is authoritative** for step rows (no server-side rebase/merge of steps).

## Per-session logs

- **PokeAgent / backends:** `llm_logs/` (paths depend on backend config).
- **CLI backends:** JSONL / session files under `.pokeagent_cache/{run_id}/<backend>_memory/`; readers in `utils/metric_tracking/*_session_reader.py`.

## Local subagent steps

- One-step local subagents record usage so interaction names appear with token rows (synthetic `tool_calls` / logging path — see codebase comments in `PokeAgent` / logger).
