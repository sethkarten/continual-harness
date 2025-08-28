#!/usr/bin/env python3
"""
Test battle state formatting - separate presentation for battle vs normal gameplay.
"""

import pytest
from utils.state_formatter import format_state_for_llm
from pokemon_env.enums import MetatileBehavior


def test_battle_mode_hides_map():
    """Test that battle mode doesn't show map information."""
    battle_state = {
        'player': {
            'name': 'Red',
            'position': {'x': 10, 'y': 10},
            'party': [
                {'species_name': 'Pikachu', 'level': 25, 'current_hp': 50, 'max_hp': 75, 'status': 'Normal'}
            ]
        },
        'game': {
            'is_in_battle': True,
            'battle_info': {
                'player_pokemon': {'species': 'Pikachu', 'level': 25, 'current_hp': 50, 'max_hp': 75},
                'opponent_pokemon': {'species': 'Zubat', 'level': 10, 'current_hp': 20, 'max_hp': 30}
            }
        },
        'map': {
            'tiles': [[(1, MetatileBehavior.NORMAL, 0, 0)] * 3] * 3,
            'current_map': 'Route 1'
        }
    }
    
    formatted = format_state_for_llm(battle_state)
    
    # Should show battle mode indicator
    assert "=== BATTLE MODE ===" in formatted
    assert "Currently in battle" in formatted
    
    # Should show battle status
    assert "=== BATTLE STATUS ===" in formatted
    assert "Your Pokemon: Pikachu" in formatted
    assert "Opponent: Zubat" in formatted
    
    # Should NOT show map
    assert "LOCATION & MAP INFO" not in formatted
    assert "TRAVERSABILITY MAP" not in formatted
    assert "Route 1" not in formatted


def test_battle_mode_hides_dialogue():
    """Test that battle mode doesn't show dialogue information."""
    battle_state = {
        'player': {'name': 'Red'},
        'game': {
            'is_in_battle': True,
            'dialog_text': 'Trainer wants to battle!',  # This might be residual
            'battle_info': {
                'player_pokemon': {'species': 'Charmander', 'level': 5, 'current_hp': 18, 'max_hp': 20},
                'opponent_pokemon': {'species': 'Rattata', 'level': 3, 'current_hp': 10, 'max_hp': 15}
            }
        }
    }
    
    formatted = format_state_for_llm(battle_state)
    
    # Should show battle info
    assert "Charmander" in formatted
    assert "Rattata" in formatted
    
    # Should NOT show dialogue
    assert "--- DIALOGUE ---" not in formatted
    assert "Trainer wants to battle" not in formatted
    assert "RESIDUAL TEXT" not in formatted


def test_normal_mode_shows_everything():
    """Test that normal (non-battle) mode shows all information."""
    normal_state = {
        'player': {
            'name': 'Red',
            'position': {'x': 10, 'y': 10},
            'facing': 'North',
            'party': [
                {'species_name': 'Squirtle', 'level': 10, 'current_hp': 30, 'max_hp': 35, 'status': 'Normal'}
            ]
        },
        'game': {
            'is_in_battle': False,
            'dialog_text': 'Welcome to the Pokemon Center!',
            'dialogue_detected': {'has_dialogue': True, 'confidence': 0.9}
        },
        'map': {
            'tiles': [[(1, MetatileBehavior.NORMAL, 0, 0)] * 3] * 3,
            'current_map': 'Pokemon Center'
        }
    }
    
    formatted = format_state_for_llm(normal_state)
    
    # Should show normal player info
    assert "=== PLAYER INFO ===" in formatted
    assert "Position: X=10, Y=10" in formatted
    assert "Facing: North" in formatted
    
    # Should show map
    assert "LOCATION & MAP INFO" in formatted
    
    # Should show dialogue
    assert "--- DIALOGUE ---" in formatted
    assert "Welcome to the Pokemon Center" in formatted
    assert "Detection confidence: 90.0%" in formatted
    
    # Should NOT show battle mode indicator
    assert "=== BATTLE MODE ===" not in formatted


def test_battle_party_information():
    """Test that battle mode shows full party for switching decisions."""
    battle_state = {
        'player': {
            'name': 'Red',
            'party': [
                {'species_name': 'Venusaur', 'level': 50, 'current_hp': 0, 'max_hp': 200, 'status': 'Fainted'},
                {'species_name': 'Charizard', 'level': 50, 'current_hp': 180, 'max_hp': 185, 'status': 'Normal'},
                {'species_name': 'Blastoise', 'level': 50, 'current_hp': 100, 'max_hp': 190, 'status': 'Poisoned'}
            ]
        },
        'game': {
            'in_battle': True,  # Alternative key
            'battle_info': {
                'player_pokemon': {'species': 'Venusaur', 'level': 50, 'current_hp': 0, 'max_hp': 200},
                'opponent_pokemon': {'species': 'Alakazam', 'level': 55, 'current_hp': 150, 'max_hp': 160}
            }
        }
    }
    
    formatted = format_state_for_llm(battle_state)
    
    # Should show party status section
    assert "=== PARTY STATUS ===" in formatted
    
    # Should list all party members
    assert "Venusaur" in formatted
    assert "Charizard" in formatted
    assert "Blastoise" in formatted
    
    # Should show status conditions
    assert "Fainted" in formatted or "0/200" in formatted  # Venusaur fainted
    assert "Poisoned" in formatted  # Blastoise poisoned


def test_battle_mode_detection_variants():
    """Test that both is_in_battle and in_battle keys trigger battle mode."""
    # Test with is_in_battle
    state1 = {
        'player': {'name': 'Red'},
        'game': {
            'is_in_battle': True,
            'battle_info': {'player_pokemon': {'species': 'Mew'}}
        },
        'map': {'current_map': 'Should not appear'}
    }
    
    formatted1 = format_state_for_llm(state1)
    assert "=== BATTLE MODE ===" in formatted1
    assert "Should not appear" not in formatted1
    
    # Test with in_battle
    state2 = {
        'player': {'name': 'Blue'},
        'game': {
            'in_battle': True,
            'battle_info': {'player_pokemon': {'species': 'Mewtwo'}}
        },
        'map': {'current_map': 'Also should not appear'}
    }
    
    formatted2 = format_state_for_llm(state2)
    assert "=== BATTLE MODE ===" in formatted2
    assert "Also should not appear" not in formatted2


def test_empty_battle_info():
    """Test handling of battle mode with missing battle info."""
    state = {
        'player': {'name': 'Red'},
        'game': {
            'is_in_battle': True,
            # No battle_info provided
        }
    }
    
    formatted = format_state_for_llm(state)
    
    # Should still enter battle mode
    assert "=== BATTLE MODE ===" in formatted
    
    # Should handle missing battle info gracefully
    assert "=== PARTY STATUS ===" in formatted  # Still shows party section


if __name__ == "__main__":
    pytest.main([__file__, "-v"])