# System design (architecture)

High-level, **code-grounded** notes for this repo. Read these before large refactors or multi-surface changes.

## Layout

- **`architecture/`** — canonical component summaries (`client_server`, agents, persistence, metrics, Pokémon stack). These are the release-facing design notes linked from the top-level README.
- **`plans/`** — intent / roadmap only; not behavior authority. These may remain internal.
- **`personal_notes/`** — scratch and historical context. These may remain internal.

## Multi-title (Emerald and Red)

**Both titles are supported.** `GAME_TYPE` / `run.py --game` / `run_cli.py --game` select **`pokemon_env` (mGBA + Emerald)** vs **`pokemon_red_env` (PyBoy + Red)** in `server/app.py`. Shared layers: HTTP/MCP, `.pokeagent_cache` / `run_data`, agent loop, metrics. Game-specific: ROM paths, emulator, memory/map readers, milestones, walkthrough parts, and branches in `utils/state_formatter.py` and objectives code. See [architecture/pokemon_infrastructure.md](architecture/pokemon_infrastructure.md) and [architecture/client_server.md](architecture/client_server.md).
