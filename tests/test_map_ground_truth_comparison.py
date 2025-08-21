#!/usr/bin/env python3
"""
Pytest to create output maps and compare to ground truth for both direct and server
"""

import pytest
import os
import time
import subprocess
import requests
import tempfile
from pathlib import Path
from pokemon_env.emulator import EmeraldEmulator


class TestMapGroundTruthComparison:
    """Test suite for comparing map outputs to ground truth"""
    
    @pytest.fixture(scope="class")
    def output_dir(self):
        """Create output directory for test results"""
        output_path = Path("test_outputs/pytest_maps")
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path
    
    @pytest.fixture(scope="class")
    def ground_truth_dir(self):
        """Path to ground truth files"""
        return Path("tests/ground_truth")
    
    def format_map_for_comparison(self, tiles, title, location, position):
        """Format map tiles for comparison with ground truth format"""
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
                        # Calculate if this tile is player position
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
    
    def compare_with_ground_truth(self, output_content, ground_truth_file):
        """Compare output with ground truth file"""
        if not os.path.exists(ground_truth_file):
            return False, f"Ground truth file not found: {ground_truth_file}"
        
        with open(ground_truth_file, 'r') as f:
            ground_truth_content = f.read()
        
        # Extract just the traversability map for comparison
        def extract_traversability_map(content):
            lines = content.split('\n')
            map_lines = []
            in_map_section = False
            
            for line in lines:
                if "--- TRAVERSABILITY MAP ---" in line:
                    in_map_section = True
                    continue
                elif in_map_section and line.strip() and not line.startswith('='):
                    if line.strip().startswith('---') or 'Map dimensions' in line:
                        continue
                    if ':' in line:  # Map row
                        map_lines.append(line)
            
            return '\n'.join(map_lines)
        
        output_map = extract_traversability_map(output_content)
        ground_truth_map = extract_traversability_map(ground_truth_content)
        
        lines_match = output_map.strip() == ground_truth_map.strip()
        
        if not lines_match:
            # Calculate similarity metrics
            output_lines = output_map.strip().split('\n')
            gt_lines = ground_truth_map.strip().split('\n')
            
            matching_lines = 0
            total_lines = max(len(output_lines), len(gt_lines))
            
            for i in range(min(len(output_lines), len(gt_lines))):
                if output_lines[i] == gt_lines[i]:
                    matching_lines += 1
            
            similarity = (matching_lines / total_lines * 100) if total_lines > 0 else 0
            
            return False, f"Maps don't match (similarity: {similarity:.1f}%)\nExpected:\n{ground_truth_map}\nActual:\n{output_map}"
        
        return True, "Maps match ground truth perfectly"
    
    def test_direct_emulator_house_map(self, output_dir, ground_truth_dir):
        """Test direct emulator house map against ground truth"""
        # Initialize direct emulator
        emu = EmeraldEmulator('Emerald-GBAdvance/rom.gba', headless=True, sound=False)
        emu.initialize()
        emu.load_state('tests/states/house.state')
        
        try:
            # Get house map
            state = emu.memory_reader.get_comprehensive_state()
            location = state['player']['location']
            position = state['player']['position']
            tiles = state['map']['tiles']
            
            # Save output
            output_file = output_dir / "direct_emulator_house.txt"
            output_content = self.save_map_output(
                tiles, output_file, 
                f"House - {location}", location, position
            )
            
            # Compare with ground truth
            ground_truth_file = ground_truth_dir / "house_direct_emulator.txt"
            matches, message = self.compare_with_ground_truth(output_content, ground_truth_file)
            
            print(f"Direct emulator house map saved to: {output_file}")
            print(f"Comparison result: {message}")
            
            # Allow test to pass even if ground truth doesn't exist yet
            if not os.path.exists(ground_truth_file):
                pytest.skip(f"Ground truth file not found: {ground_truth_file}")
            
            assert matches, f"Direct emulator house map doesn't match ground truth: {message}"
            
        finally:
            emu.stop()
    
    def test_direct_emulator_outside_map(self, output_dir, ground_truth_dir):
        """Test direct emulator outside map against ground truth"""
        # Initialize direct emulator
        emu = EmeraldEmulator('Emerald-GBAdvance/rom.gba', headless=True, sound=False)
        emu.initialize()
        emu.load_state('tests/states/house.state')
        
        try:
            # Move outside
            for i in range(3):
                emu.press_buttons(['down'], hold_frames=25, release_frames=25)
                time.sleep(0.2)
            
            # Wait for transition to complete
            time.sleep(0.5)
            
            # Get outside map
            state = emu.memory_reader.get_comprehensive_state()
            location = state['player']['location']
            position = state['player']['position']
            tiles = state['map']['tiles']
            
            # Save output
            output_file = output_dir / "direct_emulator_outside.txt"
            output_content = self.save_map_output(
                tiles, output_file,
                f"Outside - {location}", location, position
            )
            
            # Compare with ground truth
            ground_truth_file = ground_truth_dir / "outside_direct_emulator.txt"
            matches, message = self.compare_with_ground_truth(output_content, ground_truth_file)
            
            print(f"Direct emulator outside map saved to: {output_file}")
            print(f"Comparison result: {message}")
            
            # Allow test to pass even if ground truth doesn't exist yet
            if not os.path.exists(ground_truth_file):
                pytest.skip(f"Ground truth file not found: {ground_truth_file}")
            
            assert matches, f"Direct emulator outside map doesn't match ground truth: {message}"
            
        finally:
            emu.stop()
    
    def test_server_house_map(self, output_dir, ground_truth_dir):
        """Test server house map against ground truth"""
        # Kill any existing server
        os.system("pkill -f 'server.app' 2>/dev/null")
        time.sleep(2)
        
        # Start server
        server_cmd = ["python", "-m", "server.app", "--load-state", "tests/states/house.state", "--port", "8101", "--manual"]
        server_process = subprocess.Popen(server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        server_url = "http://127.0.0.1:8101"
        
        try:
            # Wait for server startup
            for i in range(20):
                try:
                    response = requests.get(f"{server_url}/status", timeout=2)
                    if response.status_code == 200:
                        break
                except requests.exceptions.RequestException:
                    time.sleep(1)
            else:
                pytest.fail("Server failed to start")
            
            # Get house map
            response = requests.get(f"{server_url}/state", timeout=5)
            state = response.json()
            
            location = state['player']['location']
            position = (state['player']['position']['x'], state['player']['position']['y'])
            tiles = state['map']['tiles']
            
            # Save output
            output_file = output_dir / "server_house.txt"
            output_content = self.save_map_output(
                tiles, output_file,
                f"House - {location}", location, position
            )
            
            # Compare with ground truth
            ground_truth_file = ground_truth_dir / "house_server.txt"
            matches, message = self.compare_with_ground_truth(output_content, ground_truth_file)
            
            print(f"Server house map saved to: {output_file}")
            print(f"Comparison result: {message}")
            
            # Allow test to pass even if ground truth doesn't exist yet
            if not os.path.exists(ground_truth_file):
                pytest.skip(f"Ground truth file not found: {ground_truth_file}")
            
            assert matches, f"Server house map doesn't match ground truth: {message}"
            
        finally:
            server_process.terminate()
            try:
                server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server_process.kill()
    
    def test_server_outside_map(self, output_dir, ground_truth_dir):
        """Test server outside map against ground truth"""
        # Kill any existing server
        # os.system("pkill -f 'server.app' 2>/dev/null")
        # time.sleep(2)
        
        # Start server
        # server_cmd = ["python", "-m", "server.app", "--load-state", "tests/states/house.state", "--port", "8102", "--manual"]
        # server_process = subprocess.Popen(server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        server_url = "http://127.0.0.1:8000"
        
        try:
            # Wait for server startup
            for i in range(20):
                try:
                    response = requests.get(f"{server_url}/status", timeout=2)
                    if response.status_code == 200:
                        break
                except requests.exceptions.RequestException:
                    time.sleep(1)
            else:
                pytest.fail("Server failed to start")
            
            # Enhanced movement to reach position (5,11) like direct emulator
            target_pos = (5, 11)
            max_moves = 6
            for move_num in range(max_moves):
                try:
                    # Check current position
                    response = requests.get(f"{server_url}/state", timeout=10)
                    state = response.json()
                    current_pos = (state['player']['position']['x'], state['player']['position']['y'])
                    current_location = state['player']['location']
                    
                    # If we've reached the target position, stop
                    if current_pos == target_pos:
                        break
                    
                    # If we're in outdoor area but not at target Y, keep moving down
                    if "LITTLEROOT TOWN" in current_location and "HOUSE" not in current_location:
                        if current_pos[1] < target_pos[1]:
                            print('Posting action down')
                            requests.post(f"{server_url}/action", json={"buttons": ["DOWN"]}, timeout=5)
                            time.sleep(0.2)
                            continue
                        else:
                            break
                    else:
                        # Still in house, keep moving down
                        requests.post(f"{server_url}/action", json={"buttons": ["DOWN"]}, timeout=5)
                        time.sleep(0.2)
                    
                except Exception:
                    time.sleep(0.5)
            
            # Enhanced buffer synchronization
            # for i in range(3):
            #     try:
            #         requests.post(f"{server_url}/debug/clear_cache", json={}, timeout=5)
            #         time.sleep(0.2)
            #     except:
            #         pass
            
            # try:
            #     requests.post(f"{server_url}/debug/force_buffer_redetection", json={}, timeout=5)
            #     time.sleep(1.0)
            # except:
            #     pass
            
            # Get outside map
            response = requests.get(f"{server_url}/state", timeout=15)
            state = response.json()
            
            location = state['player']['location']
            position = (state['player']['position']['x'], state['player']['position']['y'])
            tiles = state['map']['tiles']
            
            # Save output
            output_file = output_dir / "server_outside.txt"
            output_content = self.save_map_output(
                tiles, output_file,
                f"Outside - {location}", location, position
            )
            
            # Compare with ground truth
            ground_truth_file = ground_truth_dir / "outside_server.txt"
            matches, message = self.compare_with_ground_truth(output_content, ground_truth_file)
            
            print(f"Server outside map saved to: {output_file}")
            print(f"Comparison result: {message}")
            
            # Allow test to pass even if ground truth doesn't exist yet
            if not os.path.exists(ground_truth_file):
                pytest.skip(f"Ground truth file not found: {ground_truth_file}")
            
            assert matches, f"Server outside map doesn't match ground truth: {message}"
            
        finally:
            server_process.terminate()
            try:
                server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server_process.kill()
    
    def test_cross_comparison_house(self, output_dir):
        """Test that direct emulator and server produce identical house maps"""
        # This test runs after the individual tests and compares their outputs
        direct_file = output_dir / "direct_emulator_house.txt"
        server_file = output_dir / "server_house.txt"
        
        if not direct_file.exists() or not server_file.exists():
            pytest.skip("Individual map tests must run first")
        
        with open(direct_file, 'r') as f:
            direct_content = f.read()
        
        with open(server_file, 'r') as f:
            server_content = f.read()
        
        # Compare the traversability maps
        def extract_traversability_map(content):
            lines = content.split('\n')
            map_lines = []
            in_map_section = False
            
            for line in lines:
                if "--- TRAVERSABILITY MAP ---" in line:
                    in_map_section = True
                    continue
                elif in_map_section and line.strip() and ':' in line:
                    map_lines.append(line)
            
            return '\n'.join(map_lines)
        
        direct_map = extract_traversability_map(direct_content)
        server_map = extract_traversability_map(server_content)
        
        assert direct_map == server_map, f"House maps don't match between direct emulator and server:\nDirect:\n{direct_map}\nServer:\n{server_map}"
    
    def test_cross_comparison_outside(self, output_dir):
        """Test that direct emulator and server produce identical outside maps"""
        # This test runs after the individual tests and compares their outputs
        direct_file = output_dir / "direct_emulator_outside.txt"
        server_file = output_dir / "server_outside.txt"
        
        if not direct_file.exists() or not server_file.exists():
            pytest.skip("Individual map tests must run first")
        
        with open(direct_file, 'r') as f:
            direct_content = f.read()
        
        with open(server_file, 'r') as f:
            server_content = f.read()
        
        # Compare the traversability maps
        def extract_traversability_map(content):
            lines = content.split('\n')
            map_lines = []
            in_map_section = False
            
            for line in lines:
                if "--- TRAVERSABILITY MAP ---" in line:
                    in_map_section = True
                    continue
                elif in_map_section and line.strip() and ':' in line:
                    map_lines.append(line)
            
            return '\n'.join(map_lines)
        
        direct_map = extract_traversability_map(direct_content)
        server_map = extract_traversability_map(server_content)
        
        assert direct_map == server_map, f"Outside maps don't match between direct emulator and server:\nDirect:\n{direct_map}\nServer:\n{server_map}"


if __name__ == "__main__":
    # Allow running as script for manual testing
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))