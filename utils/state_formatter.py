#!/usr/bin/env python3
"""
State Formatter Utility

Converts comprehensive game state objects to formatted text for LLM prompts and debugging.
Centralizes all state formatting logic for consistency across agent modules.
"""

import json
import logging

logger = logging.getLogger(__name__)

def format_state_for_llm(state_data, include_debug_info=False):
    """
    Format comprehensive state data into a readable context for the VLM.
    
    Args:
        state_data (dict): The comprehensive state from /state endpoint
        include_debug_info (bool): Whether to include extra debug information
    
    Returns:
        str: Formatted state context for LLM prompts
    """
    context_parts = []
    
    # Player information (from both player and game sections)
    context_parts.append("=== PLAYER INFO ===")
    
    # Check both player and game sections for player data
    player_data = state_data.get('player', {})
    game_data = state_data.get('game', {})
    
    # Player name and basic info
    if 'name' in player_data and player_data['name']:
        context_parts.append(f"Player Name: {player_data['name']}")
    
    # Position information
    position = _get_player_position(player_data)
    if position:
        context_parts.append(f"Position: X={position.get('x', 'unknown')}, Y={position.get('y', 'unknown')}")
    
    # Money (check both player and game sections)
    money = player_data.get('money') or game_data.get('money')
    if money is not None:
        context_parts.append(f"Money: ${money}")
    
    # Pokemon Party (check both player and game sections)
    party_context = _format_party_info(player_data, game_data)
    context_parts.extend(party_context)

    # Map/Location information with traversability
    map_context = _format_map_info(state_data.get('map', {}), include_debug_info)
    context_parts.extend(map_context)

    # Game state information
    game_context = _format_game_state(game_data)
    context_parts.extend(game_context)
    
    # Debug information if requested
    if include_debug_info:
        debug_context = _format_debug_info(state_data)
        context_parts.extend(debug_context)
    
    return "\n".join(context_parts)

def format_state_summary(state_data):
    """
    Create a concise one-line summary of the current state for logging.
    
    Args:
        state_data (dict): The comprehensive state from /state endpoint
    
    Returns:
        str: Concise state summary
    """
    player_data = state_data.get('player', {})
    game_data = state_data.get('game', {})
    map_info = state_data.get('map', {})
    
    summary_parts = []
    
    # Player name
    if player_data.get('name'):
        summary_parts.append(f"Player: {player_data['name']}")
    
    # Location
    if map_info.get('current_map'):
        summary_parts.append(f"Map: {map_info['current_map']}")
    
    # Position
    position = _get_player_position(player_data)
    if position:
        summary_parts.append(f"Pos: ({position.get('x', '?')}, {position.get('y', '?')})")
    
    # Battle status
    if game_data.get('in_battle'):
        summary_parts.append("In Battle")
    
    # Money
    money = player_data.get('money') or game_data.get('money')
    if money is not None:
        summary_parts.append(f"Money: ${money}")
    
    # Party size
    party_data = player_data.get('party') or game_data.get('party')
    if party_data:
        party_size = _get_party_size(party_data)
        if party_size > 0:
            summary_parts.append(f"Party: {party_size} pokemon")
    
    return " | ".join(summary_parts) if summary_parts else "No state data"

def format_state_for_debug(state_data):
    """
    Format state data for detailed debugging output.
    
    Args:
        state_data (dict): The comprehensive state from /state endpoint
    
    Returns:
        str: Detailed debug information
    """
    debug_parts = []
    debug_parts.append("=" * 60)
    debug_parts.append("COMPREHENSIVE STATE DEBUG")
    debug_parts.append("=" * 60)
    
    # Raw structure overview
    debug_parts.append("\n--- STRUCTURE OVERVIEW ---")
    for key, value in state_data.items():
        if isinstance(value, dict):
            debug_parts.append(f"{key}: dict with {len(value)} keys")
        elif isinstance(value, list):
            debug_parts.append(f"{key}: list with {len(value)} items")
        else:
            debug_parts.append(f"{key}: {type(value).__name__} = {value}")
    
    # Detailed formatted state
    debug_parts.append("\n--- FORMATTED STATE ---")
    debug_parts.append(format_state_for_llm(state_data, include_debug_info=True))
    
    # Raw JSON (truncated if too long)
    debug_parts.append("\n--- RAW JSON (truncated) ---")
    raw_json = json.dumps(state_data, indent=2)
    if len(raw_json) > 2000:
        debug_parts.append(raw_json[:2000] + "\n... (truncated)")
    else:
        debug_parts.append(raw_json)
    
    debug_parts.append("=" * 60)
    return "\n".join(debug_parts)

# Helper functions for state formatting

def _get_player_position(player_data):
    """Extract player position from various possible locations in player data."""
    if 'coordinates' in player_data:
        return player_data['coordinates']
    elif 'position' in player_data and player_data['position']:
        return player_data['position']
    return None

def _get_party_size(party_data):
    """Get party size from party data regardless of format."""
    if isinstance(party_data, dict):
        return party_data.get('size', len(party_data.get('pokemon', [])))
    elif isinstance(party_data, list):
        return len(party_data)
    return 0

def _format_party_info(player_data, game_data):
    """Format pokemon party information."""
    context_parts = []
    
    # Pokemon Party (check both player and game sections)
    party_data = player_data.get('party') or game_data.get('party')
    if party_data:
        pokemon_list = []
        if isinstance(party_data, dict) and party_data.get('pokemon'):
            # Format: {"size": X, "pokemon": [...]}
            pokemon_list = party_data.get('pokemon', [])
            party_size = party_data.get('size', len(pokemon_list))
        elif isinstance(party_data, list):
            # Format: [pokemon1, pokemon2, ...]
            pokemon_list = party_data
            party_size = len(pokemon_list)
        else:
            party_size = 0
        
        if party_size > 0:
            context_parts.append(f"Pokemon Party ({party_size} pokemon):")
            for i, pokemon in enumerate(pokemon_list[:6]):
                if pokemon:
                    species = pokemon.get('species', 'Unknown')
                    level = pokemon.get('level', '?')
                    hp = pokemon.get('current_hp', '?')
                    max_hp = pokemon.get('max_hp', '?')
                    status = pokemon.get('status', 'Normal')
                    context_parts.append(f"  {i+1}. {species} (Lv.{level}) HP: {hp}/{max_hp} Status: {status}")
        else:
            context_parts.append("No Pokemon in party")
    else:
        context_parts.append("No Pokemon in party")
    
    return context_parts

def _format_map_info(map_info, include_debug_info=False):
    """Format map and traversability information."""
    context_parts = []
    
    if not map_info:
        return context_parts
    
    context_parts.append("\n=== LOCATION & MAP INFO ===")
    
    if 'current_map' in map_info:
        context_parts.append(f"Current Map: {map_info['current_map']}")
    
    # Traversability information (key for navigation)
    if 'traversability' in map_info and map_info['traversability']:
        traversability = map_info['traversability']
        context_parts.append(f"\n--- FULL TRAVERSABILITY MAP ({len(traversability)}x{len(traversability[0])}) ---")
        
        # Find player position (center of the grid)
        center_y = len(traversability) // 2
        center_x = len(traversability[0]) // 2
        
        # Display the full traversability map
        for y in range(len(traversability)):
            row_str = ""
            for x in range(len(traversability[y])):
                if y == center_y and x == center_x:
                    row_str += "P "  # Player position
                else:
                    cell = str(traversability[y][x])
                    if cell == "0":
                        row_str += "# "  # Blocked
                    elif cell == ".":
                        row_str += ". "  # Normal
                    elif "TALL" in cell:
                        row_str += "~ "  # Tall grass
                    elif "WATER" in cell:
                        row_str += "W "  # Water
                    elif "JUMP" in cell:
                        row_str += "J "  # Jump ledge
                    else:
                        # For other terrain types, use first letter
                        row_str += f"{cell[0] if cell else '?'} "
            context_parts.append(row_str.rstrip())
        
        context_parts.append("\nLegend: P=Player, .=Normal path, #=Blocked, ~=Tall grass, W=Water, J=Jump ledge")
        
        # Simple terrain summary (just key info)
        terrain_types = set()
        for row in traversability:
            for cell in row:
                cell_str = str(cell)
                if cell_str != "0" and cell_str != ".":
                    terrain_types.add(cell_str)
        
        if terrain_types:
            special_terrain = []
            for terrain in sorted(terrain_types):
                if "TALL" in terrain:
                    special_terrain.append("Tall grass (wild pokemon)")
                elif "WATER" in terrain:
                    special_terrain.append("Water (may need Surf)")
                elif "JUMP" in terrain:
                    special_terrain.append("Jump ledges")
                else:
                    special_terrain.append(terrain)
            
            if special_terrain:
                context_parts.append(f"Special terrain: {', '.join(special_terrain)}")
    
    # Current tile details (simplified)
    if 'metatile_info' in map_info and map_info['metatile_info']:
        tile_info = map_info['metatile_info']
        if tile_info and len(tile_info) > 0:
            center_y = len(tile_info) // 2
            center_x = len(tile_info[center_y]) // 2 if len(tile_info[center_y]) > 0 else 0
            
            if center_y < len(tile_info) and center_x < len(tile_info[center_y]):
                center_tile = tile_info[center_y][center_x]
                context_parts.append(f"\nCurrent Tile: {center_tile.get('behavior', 'Unknown')} - {'Passable' if center_tile.get('passable') else 'Blocked'}")
                if center_tile.get('encounter_possible'):
                    context_parts.append("Wild encounters possible here")
                if center_tile.get('surfable'):
                    context_parts.append("Can use Surf here")
    
    return context_parts

def _format_game_state(game_data):
    """Format game state information."""
    context_parts = []
    
    if not game_data:
        return context_parts
    
    context_parts.append("\n=== GAME STATE ===")
    
    if 'in_battle' in game_data:
        context_parts.append(f"In Battle: {game_data['in_battle']}")
    
    if 'battle_info' in game_data and game_data['battle_info']:
        battle = game_data['battle_info']
        context_parts.append("Battle Information:")
        if 'player_pokemon' in battle:
            player_pkmn = battle['player_pokemon']
            context_parts.append(f"  Your Pokemon: {player_pkmn.get('species', 'Unknown')} (Lv.{player_pkmn.get('level', '?')}) HP: {player_pkmn.get('current_hp', '?')}/{player_pkmn.get('max_hp', '?')}")
        if 'opponent_pokemon' in battle:
            opp_pkmn = battle['opponent_pokemon']
            context_parts.append(f"  Opponent: {opp_pkmn.get('species', 'Unknown')} (Lv.{opp_pkmn.get('level', '?')}) HP: {opp_pkmn.get('current_hp', '?')}/{opp_pkmn.get('max_hp', '?')}")
    
    if 'game_state' in game_data:
        context_parts.append(f"Game State: {game_data['game_state']}")
    
    return context_parts

def _format_debug_info(state_data):
    """Format additional debug information."""
    context_parts = []
    
    context_parts.append("\n=== DEBUG INFO ===")
    
    # Step information
    if 'step_number' in state_data:
        context_parts.append(f"Step Number: {state_data['step_number']}")
    
    if 'status' in state_data:
        context_parts.append(f"Status: {state_data['status']}")
    
    # Visual data info
    if 'visual' in state_data:
        visual = state_data['visual']
        if 'resolution' in visual:
            context_parts.append(f"Resolution: {visual['resolution']}")
        if 'screenshot_base64' in visual:
            context_parts.append(f"Screenshot: Available ({len(visual['screenshot_base64'])} chars)")
    
    return context_parts

# Convenience functions for specific use cases

def get_movement_options(state_data):
    """
    Extract movement options from traversability data.
    
    Returns:
        dict: Direction -> description mapping
    """
    map_info = state_data.get('map', {})
    if 'traversability' not in map_info or not map_info['traversability']:
        return {}
    
    traversability = map_info['traversability']
    center_y = len(traversability) // 2
    center_x = len(traversability[0]) // 2
    
    directions = {
        'UP': (0, -1), 'DOWN': (0, 1), 
        'LEFT': (-1, 0), 'RIGHT': (1, 0)
    }
    
    movement_options = {}
    for direction, (dx, dy) in directions.items():
        new_x, new_y = center_x + dx, center_y + dy
        if 0 <= new_y < len(traversability) and 0 <= new_x < len(traversability[new_y]):
            cell = str(traversability[new_y][new_x])
            if cell == "0":
                movement_options[direction] = "BLOCKED"
            elif cell == ".":
                movement_options[direction] = "Normal path"
            elif "TALL" in cell:
                movement_options[direction] = "Tall grass (wild encounters)"
            elif "WATER" in cell:
                movement_options[direction] = "Water (need Surf)"
            else:
                movement_options[direction] = cell
        else:
            movement_options[direction] = "Out of bounds"
    
    return movement_options

def get_party_health_summary(state_data):
    """
    Get a summary of party health status.
    
    Returns:
        dict: Summary with healthy_count, total_count, critical_pokemon
    """
    player_data = state_data.get('player', {})
    game_data = state_data.get('game', {})
    party_data = player_data.get('party') or game_data.get('party')
    
    if not party_data:
        return {"healthy_count": 0, "total_count": 0, "critical_pokemon": []}
    
    pokemon_list = []
    if isinstance(party_data, dict) and party_data.get('pokemon'):
        pokemon_list = party_data.get('pokemon', [])
    elif isinstance(party_data, list):
        pokemon_list = party_data
    
    healthy_count = 0
    critical_pokemon = []
    
    for i, pokemon in enumerate(pokemon_list[:6]):
        if pokemon:
            hp = pokemon.get('current_hp', 0)
            max_hp = pokemon.get('max_hp', 1)
            status = pokemon.get('status', 'Normal')
            species = pokemon.get('species', 'Unknown')
            
            if hp > 0 and status == 'Normal':
                healthy_count += 1
            
            hp_percent = (hp / max_hp * 100) if max_hp > 0 else 0
            if hp_percent < 25 or status != 'Normal':
                critical_pokemon.append(f"{species} ({hp_percent:.0f}% HP, {status})")
    
    return {
        "healthy_count": healthy_count,
        "total_count": len(pokemon_list),
        "critical_pokemon": critical_pokemon
    } 