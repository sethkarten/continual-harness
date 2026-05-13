# Pokémon / emulator

Two first-class stacks share the same HTTP/MCP contract from `server/app.py`; ROM and `GAME_TYPE` select which stack runs.

## Emerald — `pokemon_env/`

### `EmeraldEmulator` (`emulator.py`)

- Wraps **pylibmgba** (`mgba.core`, …): load ROM, advance frames, capture RGB frames.
- Uses **`PokemonEmeraldReader`** (`memory_reader.py`) for structured game state (party, map, flags, …).
- **Milestones:** `MilestoneTracker` persists to cache (`milestones_progress.json` under `get_cache_directory()`).
  - `MILESTONE_PHASES` is the single ordered source of truth in `pokemon_env/emulator.py`.
  - `ORDERED_PROGRESS_MILESTONES` is derived from it and drives detection order + split ordering.
  - `COMPARISON_MILESTONES` mirrors `ORDERED_PROGRESS_MILESTONES` so CLI checkpoint backups align with the same sequence.
  - First-gym redundancy was removed (`ROXANNE_DEFEATED` / `FIRST_GYM_COMPLETE`); progression uses `STONE_BADGE`.
  - **Post-Rustboro → third gym (canonical IDs, phase order):**  
    Phase 8: `ROUTE_116`, `RUSTURF_TUNNEL`, `DEVON_CORP_3F_MR_STONE`, `MR_BRINEYS_HOUSE`, `DEWFORD_TOWN`.  
    Phase 9a (Steven path): `ROUTE_106`, `GRANITE_CAVE_STEVEN`.  
    Phase 10: `SLATEPORT_CITY`, `OCEANIC_MUSEUM_AQUA`, `ROUTE_110`.  
    Phase 11: `RIVAL_BATTLE_ROUTE_110`, `MAUVILLE_CITY`, `MAUVILLE_GYM_ENTERED`, `DYNAMO_BADGE`.  
    Phase 9b (optional Dewford gym, **after** phase 11 in the flat list): `DEWFORD_GYM_ENTERED`, `KNUCKLE_BADGE`.  
  - **Branching:** `_check_milestone_condition` allows `SLATEPORT_CITY` after **`GRANITE_CAVE_STEVEN` or `KNUCKLE_BADGE`** so Steven-first routes are valid without early Brawly.
- Integrates **persistent world map** helpers (`utils/state_formatter` save/load).

### Server integration (Emerald)

- When `game_type != "red"`, `server/app.py` holds a global **`EmeraldEmulator`** as `env`, drives stepping, action timing (`SPEED_PRESETS`: fast / normal / slow), optional **video recording** to `run_data/.../end_state/videos/`.
- **Anti-cheat / submission:** `utils/anticheat.AntiCheatTracker` used for submission logging.

### Maps (Emerald)

- Porymap-backed map data and stitching toggles live in server + `pokemon_env` / `utils` mapping helpers (see `pokemon_env/README.md`). `/state` can build **`visual_map`** via porymap-aware paths; pathfinding and LLM ASCII map use `utils/mapping/porymap_state.py` and related code.

---

## Red — `pokemon_red_env/`

### `RedEmulator` (`red_emulator.py`)

- **PyBoy**-backed Game Boy Color emulation (`pokered.gbc`). Surface area is kept compatible with what `server/app.py` expects from Emerald (step, state, buttons, milestones).
- **`RedMemoryReader`**, **`RedMapReader`**, milestone ordering via **`RED_MILESTONES_ORDER`** (see `red_emulator.py`).
- **Maps:** LLM-facing map text and `get_map_data` come from **`RedMapReader.format_map_for_llm`** (not Porymap). `/whole_map` for Red uses **`RedEmulator.get_whole_map()`** instead of the Emerald Porymap stack.

### Shared layers

- **HTTP/MCP**, **`.pokeagent_cache` / `run_data`**, objectives registry (with **`GAME_TYPE == "red"`** branches in `agents/objectives/direct_objectives.py` where applicable), **LLM metrics**, and the **agent loop** stay shared; `utils/state_formatter.py` branches on **`GAME_TYPE == "red"`** for map/facing formatting.
