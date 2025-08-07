import os
import pytest
from pathlib import Path
import numpy as np
from pprint import pprint

from pokemon_env.emulator import EmeraldEmulator
from pokemon_env.enums import MetatileBehavior

def format_map_data(map_data, title="Map Data"):
    """Format the map data into a string using the agent's format"""
    lines = []
    lines.append(f"=== {title} ===")
    lines.append("Format: (MetatileID, Behavior, X, Y)")
    lines.append(f"Map dimensions: {len(map_data)}x{len(map_data[0])}")
    lines.append("")
    lines.append("--- TRAVERSABILITY MAP ---")
    
    # Column headers
    header = "     "
    for i in range(len(map_data[0])):
        header += f"{i:2} "
    lines.append(header)
    lines.append("    " + "--" * len(map_data[0]))
    
    # Find player position (center of the grid)
    center_y = len(map_data) // 2
    center_x = len(map_data[0]) // 2
    
    # Format each row
    for y in range(len(map_data)):
        row = f"{y:2}: "
        for x in range(len(map_data[y])):
            if y == center_y and x == center_x:
                row += "P"  # Player position
            else:
                tile = map_data[y][x]
                behavior = tile[1]
                # Convert behavior to map symbol using same logic as get_comprehensive_state
                tile_id, behavior, collision, elevation = tile
                behavior_name = behavior.name if behavior is not None and hasattr(behavior, 'name') else "UNKNOWN"
                
                if behavior_name == "NORMAL":
                    # For normal tiles, use collision data to determine if passable
                    row += "." if collision == 0 else "#"
                elif "TALL_GRASS" in behavior_name:
                    row += "~"  # Tall grass
                elif "WATER" in behavior_name:
                    row += "W"  # Water
                elif "JUMP" in behavior_name:
                    # Show jump direction
                    if "JUMP_EAST" in behavior_name:
                        row += "→"
                    elif "JUMP_WEST" in behavior_name:
                        row += "←"
                    elif "JUMP_NORTH" in behavior_name:
                        row += "↑"
                    elif "JUMP_SOUTH" in behavior_name:
                        row += "↓"
                    elif "JUMP_NORTHEAST" in behavior_name:
                        row += "↗"
                    elif "JUMP_NORTHWEST" in behavior_name:
                        row += "↖"
                    elif "JUMP_SOUTHEAST" in behavior_name:
                        row += "↘"
                    elif "JUMP_SOUTHWEST" in behavior_name:
                        row += "↙"
                    else:
                        row += "J"
                elif "DOOR" in behavior_name:
                    row += "D"  # Door
                else:
                    # For other behaviors, show abbreviated name
                    short_name = behavior_name.replace("_", "")[:4]
                    row += f"{short_name[:2]}"
            row += " "  # Add space between tiles
        lines.append(row.rstrip())
    
    return "\n".join(lines)

def print_map_data(map_data, title="Map Data"):
    """Pretty print the map data and return the formatted string"""
    formatted_map = format_map_data(map_data, title)
    print("\n" + formatted_map)
    print("\nLegend:")
    print("  P  = Player position")
    print("  .  = Normal walkable path")
    print("  #  = Blocked/wall")
    print("  D  = Door (can be entered)")
    print("  ~  = Tall grass (wild Pokemon encounters)")
    print("  W  = Water (requires Surf)")
    print("  IM = Impassable terrain")
    print("  SE = Sealed area (cannot enter)")
    print("  EA = East arrow (direction indicator)")
    print("  SO = Sound mat (makes sound when stepped on)")
    print("  TE = Television")
    print("  →←↑↓↗↖↘↙ = Jump ledge directions (can jump in that direction)")
    return formatted_map
    
    print("\nLegend:")
    print("  P  = Player position")
    print("  .  = Normal walkable path")
    print("  #  = Blocked/wall")
    print("  D  = Door (can be entered)")
    print("  ~  = Tall grass (wild Pokemon encounters)")
    print("  W  = Water (requires Surf)")
    print("  IM = Impassable terrain")
    print("  SE = Sealed area (cannot enter)")
    print("  EA = East arrow (direction indicator)")
    print("  SO = Sound mat (makes sound when stepped on)")
    print("  TE = Television")
    print("  →←↑↓↗↖↘↙ = Jump ledge directions (can jump in that direction)")

# Get the absolute path to the test states directory
TEST_STATES_DIR = os.path.join(os.path.dirname(__file__), "states")

@pytest.fixture
def emulator():
    """Create and initialize an emulator instance"""
    # Get path to ROM file
    project_root = Path(__file__).parent.parent
    rom_path = str(project_root / "Emerald-GBAdvance" / "rom.gba")
    
    # Initialize emulator
    emu = EmeraldEmulator(rom_path, headless=True, sound=False)
    emu.initialize()
    
    yield emu
    
    # Cleanup
    emu.stop()

def test_house_state_map_reading(emulator):
    """Test map reading functionality in the house state"""
    # Load the house state
    state_path = os.path.join(TEST_STATES_DIR, "house.state")
    emulator.load_state(state_path)
    
    # Get map data around player using the same function as the agent
    map_data = emulator.memory_reader.read_map_around_player(radius=7)
    
    # Format the map data
    formatted_map = print_map_data(map_data, "House State Map")
    
    # Load ground truth
    truth_path = os.path.join(TEST_STATES_DIR, "house_map_truth.txt")
    with open(truth_path, 'r') as f:
        expected_map = f.read().strip()
    
    # Compare with ground truth
    assert formatted_map == expected_map, "Map output does not match ground truth"
    
    # Basic structure tests
    assert map_data is not None, "Map data should not be None"
    assert isinstance(map_data, list), "Map data should be a list"
    assert len(map_data) > 0, "Map data should not be empty"
    assert isinstance(map_data[0], list), "Map data should be a 2D list"
    
    # Test map dimensions
    height = len(map_data)
    width = len(map_data[0])
    assert height == 15, f"Map height should be 15 (2*radius + 1), got {height}"
    assert width == 15, f"Map width should be 15 (2*radius + 1), got {width}"
    
    # Test tile data structure
    center_tile = map_data[7][7]  # Center tile where player is
    assert isinstance(center_tile, tuple), "Tile data should be a tuple"
    assert len(center_tile) == 4, "Tile data should contain metatile ID, behavior, x, and y coordinates"
    
    # Test that we're indoors (should have indoor tiles)
    center_behavior = center_tile[1]
    assert isinstance(center_behavior, MetatileBehavior), "Tile behavior should be MetatileBehavior enum"
    assert center_behavior in [MetatileBehavior.INDOOR_ENCOUNTER, MetatileBehavior.NORMAL], \
        "Center tile should be an indoor tile"

def test_truck_state_map_reading(emulator):
    """Test map reading functionality in the truck state (game start)"""
    # Load the truck state
    state_path = os.path.join(TEST_STATES_DIR, "truck.state")
    emulator.load_state(state_path)
    
    # Get map data around player using the same function as the agent
    map_data = emulator.memory_reader.read_map_around_player(radius=7)
    
    # Format the map data
    formatted_map = print_map_data(map_data, "Truck State Map")
    
    # Load ground truth
    truth_path = os.path.join(TEST_STATES_DIR, "truck_map_truth.txt")
    with open(truth_path, 'r') as f:
        expected_map = f.read().strip()
    
    # Compare with ground truth
    assert formatted_map == expected_map, "Map output does not match ground truth"
    
    # Basic structure tests
    assert map_data is not None, "Map data should not be None"
    assert isinstance(map_data, list), "Map data should be a list"
    assert len(map_data) > 0, "Map data should not be empty"
    assert isinstance(map_data[0], list), "Map data should be a 2D list"
    
    # Test map dimensions
    height = len(map_data)
    width = len(map_data[0])
    assert height == 15, f"Map height should be 15 (2*radius + 1), got {height}"
    assert width == 15, f"Map width should be 15 (2*radius + 1), got {width}"
    
    # Test tile data structure
    center_tile = map_data[7][7]  # Center tile where player is
    assert isinstance(center_tile, tuple), "Tile data should be a tuple"
    assert len(center_tile) == 4, "Tile data should contain metatile ID, behavior, x, and y coordinates"
    
    # Test that we're in the truck (should have indoor/special tiles)
    center_behavior = center_tile[1]
    assert isinstance(center_behavior, MetatileBehavior), "Tile behavior should be MetatileBehavior enum"
    assert center_behavior in [MetatileBehavior.INDOOR_ENCOUNTER, MetatileBehavior.NORMAL], \
        "Center tile should be an indoor tile"

def test_door_behavior(emulator):
    """Test that doors are properly identified and not marked as blocked"""
    # Load the house state
    state_path = os.path.join(TEST_STATES_DIR, "house.state")
    emulator.load_state(state_path)
    
    # Get map data around player using the same function as the agent
    map_data = emulator.memory_reader.read_map_around_player(radius=7)
    
    # Print the map data for visual inspection
    print_map_data(map_data, "House State Map (Door Test)")
    
    # Find any door tiles
    door_found = False
    door_behaviors = [MetatileBehavior.NON_ANIMATED_DOOR, 
                     MetatileBehavior.ANIMATED_DOOR,
                     MetatileBehavior.WATER_DOOR]
    
    for row in map_data:
        for tile in row:
            behavior = tile[1]
            if behavior in door_behaviors:
                door_found = True
                # Verify door tile is not marked as blocked
                assert behavior != MetatileBehavior.NORMAL, "Door should not be marked as normal path"
                assert behavior in door_behaviors, "Door should have proper door behavior"
    
    # We should find at least one door in the house state
    assert door_found, "No doors found in house state"

def test_map_data_validation(emulator):
    """Test validation of map data structure and content"""
    # Load any state (using truck state)
    state_path = os.path.join(TEST_STATES_DIR, "truck.state")
    emulator.load_state(state_path)
    
    # Test different radius values
    for radius in [3, 5, 7]:
        map_data = emulator.memory_reader.read_map_around_player(radius=radius)
        
        # Check dimensions
        expected_size = 2 * radius + 1
        assert len(map_data) == expected_size, f"Map height should be {expected_size} for radius {radius}"
        assert all(len(row) == expected_size for row in map_data), \
            f"All rows should have width {expected_size} for radius {radius}"
        
        # Check tile data consistency
        for row in map_data:
            for tile in row:
                    # Check tile structure
                    assert isinstance(tile, tuple), "Tile data should be a tuple"
                    assert len(tile) == 4, "Tile data should contain metatile ID, behavior, x, and y coordinates"
                    
                    # Check metatile ID
                    metatile_id = tile[0]
                    assert isinstance(metatile_id, int), "Metatile ID should be an integer"
                    assert metatile_id >= 0, "Metatile ID should be non-negative"
                
                    # Check behavior
                    behavior = tile[1]
                    assert isinstance(behavior, MetatileBehavior), "Behavior should be MetatileBehavior enum"
                    assert behavior.value >= 0, "Behavior value should be non-negative"