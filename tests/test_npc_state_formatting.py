#!/usr/bin/env python3
"""
Test NPC state formatting with toggle and terrain detection.
"""

import pytest
from utils.state_formatter import format_state_for_llm, _analyze_npc_terrain
from pokemon_env.enums import MetatileBehavior


def test_npc_toggle_enabled():
    """Test that NPCs are included when toggle is enabled."""
    mock_state = {
        'player': {'name': 'Red', 'position': {'x': 10, 'y': 10}, 'facing': 'South'},
        'map': {
            'current_map': 'Test Map',
            'tiles': [
                [(1, MetatileBehavior.NORMAL, 0, 0), (2, MetatileBehavior.NORMAL, 0, 0), (3, MetatileBehavior.ANIMATED_DOOR, 0, 0)],
                [(4, MetatileBehavior.NORMAL, 0, 0), (5, MetatileBehavior.NORMAL, 0, 0), (6, MetatileBehavior.NORMAL, 0, 0)],
                [(7, MetatileBehavior.NORMAL, 0, 0), (8, MetatileBehavior.NORMAL, 0, 0), (9, MetatileBehavior.NORMAL, 0, 0)]
            ],
            'player_coords': {'x': 10, 'y': 10},
            'object_events': [
                {'id': 1, 'current_x': 12, 'current_y': 10, 'trainer_type': 0},
                {'id': 2, 'current_x': 10, 'current_y': 8, 'trainer_type': 1}
            ]
        },
        'game': {}
    }
    
    formatted = format_state_for_llm(mock_state, include_npcs=True)
    
    assert "NPCs/TRAINERS (2 found)" in formatted
    assert "static NPC spawn positions" in formatted
    assert "NPC 1: NPC at (12, 10)" in formatted
    assert "NPC 2: Trainer at (10, 8)" in formatted


def test_npc_toggle_disabled():
    """Test that NPCs are excluded when toggle is disabled."""
    mock_state = {
        'player': {'name': 'Red', 'position': {'x': 10, 'y': 10}, 'facing': 'South'},
        'map': {
            'current_map': 'Test Map',
            'tiles': [
                [(1, MetatileBehavior.NORMAL, 0, 0), (2, MetatileBehavior.NORMAL, 0, 0), (3, MetatileBehavior.NORMAL, 0, 0)],
                [(4, MetatileBehavior.NORMAL, 0, 0), (5, MetatileBehavior.NORMAL, 0, 0), (6, MetatileBehavior.NORMAL, 0, 0)],
                [(7, MetatileBehavior.NORMAL, 0, 0), (8, MetatileBehavior.NORMAL, 0, 0), (9, MetatileBehavior.NORMAL, 0, 0)]
            ],
            'player_coords': {'x': 10, 'y': 10},
            'object_events': [
                {'id': 1, 'current_x': 12, 'current_y': 10, 'trainer_type': 0}
            ]
        },
        'game': {}
    }
    
    formatted = format_state_for_llm(mock_state, include_npcs=False)
    
    assert "NPCs/TRAINERS" not in formatted
    assert "static NPC spawn positions" not in formatted
    assert "NPC 1:" not in formatted
    # Should still show map without NPCs
    assert "FULL TRAVERSABILITY MAP" in formatted


def test_npc_terrain_detection():
    """Test that NPCs blocking doors and other terrain are detected."""
    # Test door blocking - NPC at offset (+1,0) from player should be in grid position (1,2) 
    npc_on_door = {'id': 1, 'current_x': 11, 'current_y': 10, 'trainer_type': 0}
    tiles_with_door = [
        [(1, MetatileBehavior.NORMAL, 0, 0), (2, MetatileBehavior.NORMAL, 0, 0), (3, MetatileBehavior.NORMAL, 0, 0)],
        [(4, MetatileBehavior.NORMAL, 0, 0), (5, MetatileBehavior.NORMAL, 0, 0), (6, MetatileBehavior.ANIMATED_DOOR, 0, 0)],
        [(7, MetatileBehavior.NORMAL, 0, 0), (8, MetatileBehavior.NORMAL, 0, 0), (9, MetatileBehavior.NORMAL, 0, 0)]
    ]
    player_coords = {'x': 10, 'y': 10}  # Center of 3x3 grid
    
    terrain_note = _analyze_npc_terrain(npc_on_door, tiles_with_door, player_coords)
    assert terrain_note == "BLOCKING DOOR"
    
    # Test furniture blocking - NPC at offset (-1,-1) from player should be in grid position (0,0) 
    npc_on_pc = {'id': 2, 'current_x': 9, 'current_y': 9, 'trainer_type': 0}
    tiles_with_pc = [
        [(131, MetatileBehavior.PC, 0, 0), (2, MetatileBehavior.NORMAL, 0, 0), (3, MetatileBehavior.NORMAL, 0, 0)],
        [(4, MetatileBehavior.NORMAL, 0, 0), (5, MetatileBehavior.NORMAL, 0, 0), (6, MetatileBehavior.NORMAL, 0, 0)],
        [(7, MetatileBehavior.NORMAL, 0, 0), (8, MetatileBehavior.NORMAL, 0, 0), (9, MetatileBehavior.NORMAL, 0, 0)]
    ]
    
    terrain_note = _analyze_npc_terrain(npc_on_pc, tiles_with_pc, player_coords)
    assert terrain_note == "on furniture (P)"
    
    # Test normal terrain (should return None)
    npc_on_normal = {'id': 3, 'current_x': 11, 'current_y': 10, 'trainer_type': 0}
    tiles_normal = [
        [(1, MetatileBehavior.NORMAL, 0, 0), (2, MetatileBehavior.NORMAL, 0, 0), (3, MetatileBehavior.NORMAL, 0, 0)],
        [(4, MetatileBehavior.NORMAL, 0, 0), (5, MetatileBehavior.NORMAL, 0, 0), (6, MetatileBehavior.NORMAL, 0, 0)],
        [(7, MetatileBehavior.NORMAL, 0, 0), (8, MetatileBehavior.NORMAL, 0, 0), (9, MetatileBehavior.NORMAL, 0, 0)]
    ]
    
    terrain_note = _analyze_npc_terrain(npc_on_normal, tiles_normal, player_coords)
    assert terrain_note is None


def test_full_npc_state_with_terrain():
    """Test full state formatting with NPC terrain detection."""
    mock_state = {
        'player': {'name': 'Red', 'position': {'x': 10, 'y': 10}, 'facing': 'South'},
        'map': {
            'current_map': 'Test Map',
            'tiles': [
                [(1, MetatileBehavior.NORMAL, 0, 0), (2, MetatileBehavior.ANIMATED_DOOR, 0, 0), (3, MetatileBehavior.NORMAL, 0, 0)],
                [(4, MetatileBehavior.NORMAL, 0, 0), (5, MetatileBehavior.NORMAL, 0, 0), (6, MetatileBehavior.NORMAL, 0, 0)],
                [(7, MetatileBehavior.NORMAL, 0, 0), (8, MetatileBehavior.NORMAL, 0, 0), (9, MetatileBehavior.NORMAL, 0, 0)]
            ],
            'player_coords': {'x': 10, 'y': 10},
            'object_events': [
                {'id': 1, 'current_x': 10, 'current_y': 9, 'trainer_type': 0},  # On door at grid position (0,1) - offset (0,-1)
                {'id': 2, 'current_x': 11, 'current_y': 10, 'trainer_type': 1}   # On normal terrain
            ]
        },
        'game': {}
    }
    
    formatted = format_state_for_llm(mock_state, include_npcs=True)
    
    assert "NPC 1: NPC at (10, 9) - BLOCKING DOOR" in formatted
    assert "NPC 2: Trainer at (11, 10)" in formatted  # No terrain note for normal terrain


if __name__ == "__main__":
    pytest.main([__file__, "-v"])