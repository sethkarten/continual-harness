#!/usr/bin/env python3
"""
Test agent and emulator running directly without separate server process
"""

import pytest
import os
import time
from pathlib import Path
from pokemon_env.emulator import EmeraldEmulator


class TestDirectAgentEmulator:
    """Test agent functionality by running emulator directly"""
    
    @pytest.fixture(scope="class")
    def output_dir(self):
        """Create output directory for test results"""
        output_path = Path("test_outputs/direct_agent_maps")
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path
    
    def format_map_for_comparison(self, tiles, title, location, position):
        """Format map tiles for comparison"""
        if not tiles:
            return f"=== {title} ===\nNo tiles available\n"
        
        output = []
        output.append(f"=== {title} ===")
        output.append(f"Format: (MetatileID, Behavior, X, Y)")
        output.append(f"Map dimensions: {len(tiles)}x{len(tiles[0]) if tiles else 0}")
        output.append("")
        output.append("--- TRAVERSABILITY MAP ---")
        
        # Header with column numbers
        header = "      " + "  ".join(f"{i:2}" for i in range(len(tiles[0]) if tiles else 0))
        output.append(header)
        output.append("    " + "-" * (len(header) - 4))
        
        # Map rows
        for row_idx, row in enumerate(tiles):
            traversability_row = []
            for col_idx, tile in enumerate(row):
                if len(tile) >= 4:
                    tile_id, behavior, collision, elevation = tile
                    behavior_val = behavior if not hasattr(behavior, 'value') else behavior.value
                    
                    # Convert to traversability symbol
                    if behavior_val == 0:  # NORMAL
                        symbol = "." if collision == 0 else "#"
                    elif behavior_val == 1:  # SECRET_BASE_WALL
                        symbol = "#"
                    elif behavior_val == 51:  # IMPASSABLE_SOUTH
                        symbol = "IM"
                    elif behavior_val == 96:  # NON_ANIMATED_DOOR
                        symbol = "D"
                    elif behavior_val == 101:  # SOUTH_ARROW_WARP
                        symbol = "SO"
                    elif behavior_val == 105:  # ANIMATED_DOOR
                        symbol = "D"
                    elif behavior_val == 134:  # TELEVISION
                        symbol = "TE"
                    else:
                        symbol = "."  # Default to walkable for other behaviors
                    
                    # Mark player position
                    if position and len(position) >= 2:
                        # Player is at center of 15x15 map (position 7,7)
                        if row_idx == 7 and col_idx == 7:
                            symbol = "P"
                    
                    traversability_row.append(symbol)
                else:
                    traversability_row.append("?")
            
            # Format row with row number
            row_str = f"{row_idx:2}: " + " ".join(f"{symbol:1}" for symbol in traversability_row)
            output.append(row_str)
        
        return "\n".join(output)
    
    def save_map_output(self, tiles, output_file, title, location, position):
        """Save map output to file"""
        formatted_output = self.format_map_for_comparison(tiles, title, location, position)
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(formatted_output)
        
        return formatted_output
    
    def test_direct_emulator_house_to_outside(self, output_dir):
        """Test direct emulator movement from house to outside"""
        print("🏠➡️🌳 DIRECT EMULATOR: House to Outside Movement Test")
        
        # Initialize emulator directly
        rom_path = "Emerald-GBAdvance/rom.gba"
        if not os.path.exists(rom_path):
            pytest.skip(f"ROM not found at {rom_path}")
        
        emulator = EmeraldEmulator(rom_path=rom_path, headless=True, sound=False)
        emulator.initialize()
        emulator.load_state('tests/states/house.state')
        
        try:
            # Get initial house map
            print("\n1️⃣ Getting initial house map...")
            house_state = emulator.get_comprehensive_state()
            house_location = house_state['player']['location']
            house_position = (house_state['player']['position']['x'], house_state['player']['position']['y'])
            house_tiles = house_state['map']['tiles']
            
            print(f"House state: {house_location} at {house_position}")
            
            # Save house map
            house_output_file = output_dir / "direct_emulator_house.txt"
            house_content = self.save_map_output(
                house_tiles, house_output_file,
                f"Direct Emulator House - {house_location}", house_location, house_position
            )
            
            # Analyze house map
            house_corruption = self.analyze_map_corruption(house_tiles)
            print(f"House map: {house_corruption['total']} tiles, {house_corruption['im_count']} IM tiles")
            
            # Move to outside area
            print("\n2️⃣ Moving to outside area...")
            moves_made = 0
            max_moves = 8
            
            for move_num in range(max_moves):
                print(f"Move {move_num + 1}: Pressing DOWN")
                emulator.press_buttons(['down'], hold_frames=25, release_frames=25)
                time.sleep(0.1)  # Small delay for transition
                moves_made += 1
                
                # Check if we've left the house
                current_state = emulator.get_comprehensive_state()
                current_location = current_state['player']['location']
                current_position = (current_state['player']['position']['x'], current_state['player']['position']['y'])
                
                print(f"  Position: {current_position}, Location: {current_location}")
                
                if "HOUSE" not in current_location:
                    print(f"✅ Reached outside area after {moves_made} moves!")
                    break
            else:
                print(f"❌ Still in house after {max_moves} moves")
            
            # Wait for any transition effects to complete
            time.sleep(0.5)
            
            # Get final outside map
            print("\n3️⃣ Getting final outside map...")
            outside_state = emulator.get_comprehensive_state()
            outside_location = outside_state['player']['location']
            outside_position = (outside_state['player']['position']['x'], outside_state['player']['position']['y'])
            outside_tiles = outside_state['map']['tiles']
            
            print(f"Outside state: {outside_location} at {outside_position}")
            
            # Save outside map
            outside_output_file = output_dir / "direct_emulator_outside.txt"
            outside_content = self.save_map_output(
                outside_tiles, outside_output_file,
                f"Direct Emulator Outside - {outside_location}", outside_location, outside_position
            )
            
            # Analyze outside map
            outside_corruption = self.analyze_map_corruption(outside_tiles)
            print(f"Outside map: {outside_corruption['total']} tiles, {outside_corruption['im_count']} IM tiles")
            
            print(f"\n4️⃣ Map Analysis:")
            print(f"House map saved to: {house_output_file}")
            print(f"Outside map saved to: {outside_output_file}")
            
            # Test assertions
            assert house_tiles is not None, "House map should exist"
            assert outside_tiles is not None, "Outside map should exist"
            assert len(house_tiles) == 15, "House map should be 15x15"
            assert len(outside_tiles) == 15, "Outside map should be 15x15"
            
            # Check that we actually moved to outside area
            assert "HOUSE" not in outside_location, f"Should be outside, but location is: {outside_location}"
            
            # Check for reasonable corruption levels
            if outside_corruption['im_count'] > 50:
                print(f"⚠️  WARNING: High corruption in outside map ({outside_corruption['im_count']} IM tiles)")
                print("This indicates area transition detection may not be working properly")
            else:
                print(f"✅ Outside map looks clean ({outside_corruption['im_count']} IM tiles is acceptable)")
            
            print("✅ DIRECT EMULATOR TEST PASSED!")
            
        finally:
            emulator.stop()
    
    def analyze_map_corruption(self, tiles):
        """Analyze map for corruption (IM tiles)"""
        if not tiles:
            return {'total': 0, 'im_count': 0, 'corruption_ratio': 0.0}
        
        total_tiles = sum(len(row) for row in tiles)
        im_count = 0
        behavior_distribution = {}
        
        for row in tiles:
            for tile in row:
                if len(tile) >= 2:
                    behavior = tile[1].value if hasattr(tile[1], 'value') else tile[1]
                    behavior_distribution[behavior] = behavior_distribution.get(behavior, 0) + 1
                    
                    if behavior == 51:  # IMPASSABLE_SOUTH
                        im_count += 1
        
        corruption_ratio = im_count / total_tiles if total_tiles > 0 else 0.0
        
        return {
            'total': total_tiles,
            'im_count': im_count,
            'corruption_ratio': corruption_ratio,
            'behavior_distribution': behavior_distribution
        }
    
    def test_direct_agent_simulation(self, output_dir):
        """Test simulating agent decision-making with direct emulator access"""
        print("🤖 DIRECT AGENT SIMULATION: Testing agent-like behavior")
        
        rom_path = "Emerald-GBAdvance/rom.gba"
        if not os.path.exists(rom_path):
            pytest.skip(f"ROM not found at {rom_path}")
        
        emulator = EmeraldEmulator(rom_path=rom_path, headless=True, sound=False)
        emulator.initialize()
        emulator.load_state('tests/states/house.state')
        
        try:
            print("\n🎯 Goal: Navigate from house to outside using agent-like logic")
            
            steps = 0
            max_steps = 10
            
            while steps < max_steps:
                # Get current state (like agent perception)
                current_state = emulator.get_comprehensive_state()
                location = current_state['player']['location']
                position = (current_state['player']['position']['x'], current_state['player']['position']['y'])
                
                print(f"\nStep {steps + 1}: {location} at {position}")
                
                # Simple agent logic: if in house, move down
                if "HOUSE" in location:
                    print("  🤖 Agent decision: In house, moving DOWN")
                    emulator.press_buttons(['down'], hold_frames=25, release_frames=25)
                    time.sleep(0.1)
                else:
                    print("  🎉 Agent goal achieved: Reached outside area!")
                    break
                
                steps += 1
            
            # Get final state for analysis
            final_state = emulator.get_comprehensive_state()
            final_location = final_state['player']['location']
            final_position = (final_state['player']['position']['x'], final_state['player']['position']['y'])
            final_tiles = final_state['map']['tiles']
            
            print(f"\n📊 Final Result:")
            print(f"Location: {final_location}")
            print(f"Position: {final_position}")
            print(f"Steps taken: {steps}")
            
            # Save agent simulation result
            agent_output_file = output_dir / "direct_agent_simulation.txt"
            self.save_map_output(
                final_tiles, agent_output_file,
                f"Direct Agent Simulation - {final_location}", final_location, final_position
            )
            
            corruption = self.analyze_map_corruption(final_tiles)
            print(f"Map quality: {corruption['total']} tiles, {corruption['im_count']} IM tiles")
            print(f"Agent simulation saved to: {agent_output_file}")
            
            # Test passed if agent successfully navigated
            success = "HOUSE" not in final_location
            if success:
                print("✅ AGENT SIMULATION SUCCESSFUL!")
            else:
                print("❌ Agent failed to navigate out of house")
            
            assert steps < max_steps, "Agent should complete navigation within step limit"
            
        finally:
            emulator.stop()


if __name__ == "__main__":
    # Allow running as script for manual testing
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))