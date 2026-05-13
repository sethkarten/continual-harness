# Pathfinding mini benchmark

Ground truth: `thesis/sethpaper-continual-harness-data/scripts/map_skill_benchmark.py` and `thesis/sethpaper-continual-harness-data/scripts/_lib/map_skill_benchmark.py`.

## Purpose

This benchmark is a focused offline test of the **code-backed navigation skills** produced by the continual-harness runs. It asks a narrow question:

> If we take every navigation-skill version an experiment produced, and run it on a fixed set of map-navigation tasks, how well does that skill move the player toward the target?

It is meant to measure the quality of the evolved **navigation tool code**, not the full end-to-end agent.

## What is being tested

- Subject runs: the `H_auto` family only:
  - `continual_harness_p1`
  - `bootstrap_frozen`
  - `bootstrap_continued`
- Subject artifacts: every reconstructed **code version** of every navigation-like skill in each run's `skills.json`
- Evaluation style: each skill version is executed in a sandbox that mimics the production tool surface the agent used during live play:
  - `get_map_data()`
  - `get_game_state()`
  - `press_buttons()`
  - `process_memory()`

This means we are testing whether the navigation code itself works when given production-style map payloads, without requiring a live emulator session.

## Benchmark maps and tasks

The current corpus covers six representative maps:

- Route 104 North
- Petalburg Woods
- Slateport City
- Rustboro Gym
- Littleroot Town
- Oldale Town

For each map, the benchmark builds two families of cases:

1. **warp_to_warp**
   - start from a walkable tile adjacent to one warp/door/stair
   - navigate to the coordinate of another warp/door/stair
   - evaluate both directions

2. **intermediate_to_adjacent**
   - start from a central walkable tile, or from a tile adjacent to a warp
   - navigate to another plain walkable tile adjacent to the target warp
   - this is intentionally easier than landing directly on the special tile

The benchmark excludes malformed or unreachable cases during map-bundle construction and records those exclusions alongside the results.

## Main metrics

Each skill-version/case execution records:

- `exact_success`: whether the final player position exactly matches the target coordinate
- `distance_to_target`: shortest-path remaining distance when available
- `manhattan_distance_to_target`: fallback geometric remaining distance
- `normalized_progress_ratio`: fraction of the initial distance closed by the skill
- `normalized_progress_ratio_clamped`: the same metric, clipped to `[0, 1]` for aggregation
- `distance_to_target_over_expert_reference_steps`: remaining distance normalized by the number of steps an expert `navigate_to()`-style pathfinder would take with variance `0`
- `buttons_pressed` and `successful_moves`
- failure tags such as `no_movement`, `partial_progress`, or `moved_farther_from_target`

In practice, the two headline summaries are:

- **exact success rate**: how often the skill lands exactly on target
- **mean clamped progress**: how much of the route it completes on average, even when it fails

## What this benchmark does not test

This benchmark does **not** measure:

- the full agent's planning quality
- objective selection
- subagent orchestration
- long-horizon game progress
- whether the agent knows **when** to call a navigation skill

It isolates the question: "once a navigation skill is called, does the navigation code actually move toward the requested destination?"

## Why this is useful

This gives us a cleaner signal than full-run completion alone. Two runs may look similar at the episode level while producing very different navigation code. By replaying every navigation-skill version directly on the same fixed tasks, we can compare:

- model families
- `H_auto` vs `H_auto-frozen` vs `H_auto-continued`
- early vs later skill versions within a run
- top-performing variants over time during the first 24 hours of a run

## Outputs

Per-run benchmark outputs live under each experiment folder:

- `paper-data/<model>/<run>/mini_mapping_benchmark/`

Setting-level aggregate tables and plots live here:

- `paper-data/pathfinding_mini_benchmark/`

## Related

- [harness_evolver.md](harness_evolver.md) - how `H_auto` produces evolved skills, memories, and subagents
- [data_persistence.md](data_persistence.md) - where run artifacts such as `skills.json` and `cumulative_metrics.json` live
