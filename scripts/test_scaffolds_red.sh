#!/bin/bash
# Test commands for the three scaffolds

# ContinualHarness scaffold (H_auto: empty registry + harness evolution)
uv run python run.py --game red --backend gemini --model-name gemini-3.1-pro-preview \
  --port 2778 --agent-auto --scaffold continualharness \
  --backup-state PokemonRed-GBC/red_init.zip \
  --enable-prompt-optimization --optimization-window-length 100 \
  --direct-objectives autonomous_objective_creation \
  --direct-objectives-start 4 --run-name ae_continual_harness_video

# Simplest scaffold (H_min: only press_buttons and process_memory available)
uv run python run.py --game red --backend gemini --model-name gemini-3.1-pro-preview \
  --port 2980 --agent-auto --scaffold simplest \
  --backup-state PokemonRed-GBC/red_init.zip \
  --run-name simplest

# PokeAgent scaffold (H_expert: full built-in subagents + walkthrough)
uv run python run.py --game red --backend gemini --model-name gemini-3.1-pro-preview \
  --port 2978 --agent-auto --scaffold pokeagent \
  --backup-state PokemonRed-GBC/red_init.zip \
  --direct-objectives autonomous_objective_creation \
  --direct-objectives-start 4 --run-name ae_pokeagent
