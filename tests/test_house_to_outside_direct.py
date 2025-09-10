#!/usr/bin/env python3
"""
Direct pytest for house to outside transition using emulator directly
This bypasses server issues and tests the core map reading functionality
"""

import pytest
import time
from pathlib import Path
from pokemon_env.emulator import EmeraldEmulator
from tests.test_memory_map import format_map_data

class TestHouseToOutsideDirectTransition:
    
    @pytest.fixture
    def emulator(self):
        """Create and initialize emulator"""
        project_root = Path.cwd()
        rom_path = str(project_root / "Emerald-GBAdvance" / "rom.gba")
        
        emu = EmeraldEmulator(rom_path, headless=True, sound=False)
        emu.initialize()
        
        yield emu
        
        emu.stop()
    
    def test_house_map_baseline(self, emulator):
        """Test that house map reads correctly as baseline"""
        print("\n📍 Testing house map baseline...")
        
        # Load house state
        emulator.load_state("tests/states/house.state")
        
        # Read initial map
        map_data = emulator.memory_reader.read_map_around_player(radius=7)
        assert map_data, "House map data should not be empty"
        
        location = emulator.memory_reader.read_location()
        position = emulator.memory_reader.read_coordinates()
        
        print(f"   Location: {location}")
        print(f"   Position: {position}")
        print(f"   Map size: {len(map_data)}x{len(map_data[0])}")
        
        # Validate house map
        validation = self._validate_map_structure(map_data, location, "house")
        assert validation['is_valid'], f"House map validation failed: {validation['message']}"
        
        # Show house map
        formatted_map = format_map_data(map_data, f"House Baseline - {location}")
        print(f"   House map:\n{formatted_map}")
    
    def test_walk_and_map_transition(self, emulator):
        """Test walking outside and check if map transitions work"""
        print("\n🚶 Testing walk outside and map transition...")
        
        # Load house state
        emulator.load_state("tests/states/house.state")
        
        # Get initial state
        initial_location = emulator.memory_reader.read_location()
        initial_position = emulator.memory_reader.read_coordinates()
        
        print(f"   Initial: {initial_location} at {initial_position}")
        
        # First, look at the house map to find the door
        house_map = emulator.memory_reader.read_map_around_player(radius=7)
        self._analyze_map_for_exits(house_map, initial_position)
        
        # Try different movement patterns to find the exit
        movements = [
            ("DOWN", [('down', 10)]),
        ]
        
        for movement_name, button_sequence in movements:
            print(f"\n   Trying movement pattern: {movement_name}")
            
            # Reload state for fresh attempt
            emulator.load_state("tests/states/house.state")
            
            # Execute button sequence
            for button, count in button_sequence:
                for i in range(count):
                    emulator.press_buttons([button], hold_frames=15, release_frames=15)
                    time.sleep(0.1)
            
            # Check result
            new_location = emulator.memory_reader.read_location()
            new_position = emulator.memory_reader.read_coordinates()
            
            print(f"      Result: {new_location} at {new_position}")
            
            # If we successfully exited the house, test the map
            if 'HOUSE' not in new_location.upper():
                print(f"   ✅ Successfully exited house with pattern: {movement_name}")
                return self._test_outside_map(emulator, new_location, new_position)
        
        # If no pattern worked, show debugging info
        print(f"   ❌ Could not exit house with any movement pattern")
        final_map = emulator.memory_reader.read_map_around_player(radius=7)
        formatted_map = format_map_data(final_map, "Final House Map")
        print(f"   Final map:\n{formatted_map}")
        
        pytest.fail("Could not exit house to test outside map transition")
    
    def _test_outside_map(self, emulator, location, position):
        """Test the outside map after successful transition"""
        print(f"\n🗺️  Testing outside map: {location} at {position}")
        
        # Read outside map
        outside_map = emulator.memory_reader.read_map_around_player(radius=7)
        
        if not outside_map:
            print("   ❌ Outside map is empty - this is the bug!")
            return False
        
        # Validate outside map
        validation = self._validate_map_structure(outside_map, location, "outside")
        
        # Show outside map regardless of validation
        formatted_map = format_map_data(outside_map, f"Outside Map - {location}")
        print(f"   Outside map:\n{formatted_map}")
        
        if validation['is_valid']:
            print(f"   ✅ Outside map validation passed: {validation['message']}")
            return True
        else:
            print(f"   ❌ Outside map validation failed: {validation['message']}")
            print("   This confirms the transition bug!")
            return False
    
    def _analyze_map_for_exits(self, map_data, player_pos):
        """Analyze house map to find potential exits"""
        print(f"   Analyzing house map for exits around player at {player_pos}...")
        
        center_y = len(map_data) // 2
        center_x = len(map_data[0]) // 2
        
        # Check tiles around player for doors or exits
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                y = center_y + dy
                x = center_x + dx
                
                if 0 <= y < len(map_data) and 0 <= x < len(map_data[0]):
                    tile = map_data[y][x]
                    if len(tile) >= 4:
                        tile_id, behavior, collision, elevation = tile
                        behavior_name = behavior.name if hasattr(behavior, 'name') else f"Raw({behavior})"
                        
                        if dy == 0 and dx == 0:
                            print(f"      Player: {behavior_name} (collision={collision})")
                        elif "DOOR" in behavior_name:
                            print(f"      Door found at ({dx:+2d},{dy:+2d}): {behavior_name}")
                        elif collision == 0:
                            print(f"      Walkable at ({dx:+2d},{dy:+2d}): {behavior_name}")
    
    def _validate_map_structure(self, map_data, location_name, area_type):
        """Validate map structure"""
        if not map_data or len(map_data) == 0:
            return {"is_valid": False, "message": "Empty map data"}
        
        total_tiles = sum(len(row) for row in map_data)
        unknown_tiles = 0
        valid_tiles = 0
        
        for row in map_data:
            for tile in row:
                if len(tile) >= 2:
                    behavior = tile[1]
                    if hasattr(behavior, 'name'):
                        behavior_name = behavior.name
                    elif isinstance(behavior, int):
                        try:
                            from pokemon_env.enums import MetatileBehavior
                            behavior_enum = MetatileBehavior(behavior)
                            behavior_name = behavior_enum.name
                        except ValueError:
                            behavior_name = "UNKNOWN"
                    else:
                        behavior_name = "UNKNOWN"
                    
                    if behavior_name == "UNKNOWN":
                        unknown_tiles += 1
                    else:
                        valid_tiles += 1
        
        unknown_ratio = unknown_tiles / total_tiles if total_tiles > 0 else 0
        
        if unknown_ratio > 0.5:
            return {"is_valid": False, "message": f"Too many unknown tiles: {unknown_ratio:.1%}"}
        
        return {
            "is_valid": True, 
            "message": f"Structure valid: {valid_tiles}/{total_tiles} valid tiles ({unknown_ratio:.1%} unknown)"
        }

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])