# Client / server (`server/app.py`)

Headless **FastAPI** app: game loop + REST state/action endpoints + **`POST /mcp/<tool>`** handlers that mirror MCP tool names. Agents are **HTTP clients** of this process.

**Game selection:** `GAME_TYPE` is `red` or `emerald` (default `emerald`). **`python -m server.app --game red|emerald`** sets `game_type` and syncs `os.environ["GAME_TYPE"]`. At import, `server/app.py` also reads `GAME_TYPE` from the environment so the correct emulator stack loads before `main()` runs.

## Processes and ports (typical)

| Service | Entry | Port (typical) |
|---------|--------|----------------|
| Game server | `python -m server.app --port N` | `N` (e.g. 8000) |
| Frame stream UI | `python -m server.frame_server --port N+1` | `N+1` |
| MCP proxy (CLI runs) | `server/cli/pokemon_mcp_server.py` | `MCP_PORT` or `run_cli --mcp-sse-port` (often `N+2`) |

`run.py` and `run_cli.py` both spawn the **frame server** (`server/frame_server.py`) for `stream.html`. Only `run_cli.py` starts the separate MCP proxy; `run.py` agents call the game server's HTTP routes directly.

## ROM selection (current behavior)

- **`setup_environment()`** in `server/app.py` picks ROM by **`game_type`** (from `GAME_TYPE` / `--game`):
  - **Emerald:** `Emerald-GBAdvance/rom.gba` → **`EmeraldEmulator`** (`pokemon_env/`).
  - **Red:** `PokemonRed-GBC/pokered.gbc` → **`RedEmulator`** (`pokemon_red_env/`).
- **`init_for_multiprocess()`** uses **`ROM_PATH`** from the environment (default `Emerald-GBAdvance/rom.gba`) and still branches on **`game_type`** at import time to construct `RedEmulator` vs `EmeraldEmulator`. This path is for importing `server.app` with `ROM_PATH` set, not the usual `python -m server.app` startup.
- **`run.py` / `run_cli.py`:** pass **`--game red|emerald`** on the server command line and set **`GAME_TYPE`** in the server env (and in the client process so prompt path resolution stays aligned). They do **not** pass **`--rom`** to `server.app`; the server’s default ROM paths above apply. **`run.py --rom`** adjusts the client-side default when `game==red` (Emerald default → Red ROM) but does **not** override `setup_environment()` ROM selection on the spawned server.

## Environment variables (server / launcher)

| Variable | Role |
|----------|------|
| `RUN_DATA_ID` | Stable run id; `initialize_run_data_manager` uses it so `run_data/{id}` and `.pokeagent_cache/{id}` align. Set by `run.py` when starting the server. |
| `GAME_TYPE` | `red` or `emerald`. Drives emulator class, map/state formatting branches, walkthrough parts, and (with early client env) `agents/prompts/paths.py` prompt file choice. |
| `ROM_PATH` | Used by `init_for_multiprocess()`; not the primary path when starting via `setup_environment()` + default ROM constants. |
| `RUN_NAME` | Optional name segment when server creates run id (see `run_data_manager`). |
| `LOAD_CHECKPOINT_MODE` | `"true"`: load `cumulative_metrics.json` + `checkpoint_llm.txt` early in server startup; ties to `--load-checkpoint` in `run.py`. `"false"`: fresh metrics behavior branch. |
| `LOAD_STATE` | Path passed into server for `--load-state` (e.g. checkpoint `.state` file). |
| `LLM_SESSION_ID` | Passed through for consistent logging across processes. |
| `LLM_METRICS_WRITE_ENABLED` | `"true"` on server: disk writes for cumulative metrics; `"false"` on client (`run.py` agent proc, `run_cli` host) so only server persists (see metrics doc). |
| `EXCLUDE_BUILTIN_SUBAGENTS` | `"1"` for `simple` / `simplest` / `continualharness` scaffolds: empty built-in subagent registry and scaffold-specific objective hints on the server. |
| `NO_OCR` | Used by `init_for_multiprocess()`; the normal launchers instead forward `--no-ocr` to `server.app` when their `no_ocr` argument is true. Current `run.py` / `run_cli.py` defaults make OCR dialogue detection disabled via those launchers. |

## HTTP `/mcp/*` surface (game server)

All are **`POST /mcp/<name>`** with JSON bodies. Aliases exist for legacy names (`add_knowledge` → `add_memory`, etc.).

**Perception / action:** `get_game_state`, `get_map_data`, `press_buttons`, `navigate_to`, `complete_direct_objective`.

**Memory / knowledge:** `add_memory`, `search_memory`, `get_memory_summary`, `get_memory_overview`, `process_memory`, `save_memory`.

**Skills / subagents (server-backed registry):** `get_skill_overview`, `process_skill`, `get_subagent_overview`, `process_subagent`.

**Wiki / walkthrough:** `lookup_pokemon_info`, `list_wiki_sources`, `get_walkthrough` (Bulbapedia **Red/Blue** parts 1–17 vs **Emerald** parts 1–21 depending on `game_type`).

**Objectives:** `create_direct_objectives`, `replan_objectives`, `get_full_objective_sequence`, `get_progress_summary`.

**Maps:** `save_map`, `load_map`.

**Metrics sync (not MCP tool):** `POST /sync_llm_metrics` — CLI orchestrator pushes aggregated steps; see [metrics_logging.md](metrics_logging.md).

## MCP proxy (`server/cli/pokemon_mcp_server.py`)

- For **containerized CLI** agents: **FastMCP** proxy forwarding to `POKEMON_SERVER_URL` (default `http://localhost:8000`).
- Registers **two** `@mcp.tool()` handlers: `get_game_state`, `press_buttons`. A `navigate_to` helper exists in the same file but its decorator is **commented out**—CLI agents do not get that tool via MCP (the full game server still has `POST /mcp/navigate_to`).
- Strips `raw_state` from CLI-facing `get_game_state` results; in-process HTTP clients can still receive full payloads.
- **Transport detail:** Claude, Gemini, and Codex container flows use the SSE-facing proxy surface; Hermes container mode uses streamable HTTP at `/mcp` because its MCP client sends `POST` requests rather than opening an SSE `GET /sse` stream.

## Software engineering notes

- **Large monolith:** `server/app.py` concentrates routing, game loop hooks, and MCP adapters.
- **Threading:** locks around observation / steps / memory (`obs_lock`, `step_lock`, `memory_lock`).
- **Inputs:** for **`game_type == "red"`**, invalid GBC inputs (e.g. shoulder buttons) are rejected where enforced in `server/app.py` (GBA-only buttons do not apply).
