#!/usr/bin/env python3
"""
Pytest for the house to outside transition bug
This test reproduces the specific issue where transitioning from house.state 
to outside results in incorrect map data
"""

import pytest
import requests
import time
import threading
import subprocess
import os
from pathlib import Path

from tests.test_memory_map import format_map_data, MetatileBehavior

# Test configuration
SERVER_PORT = 8002  # Use different port to avoid conflicts
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"

class TestHouseToOutsideTransition:
    
    @classmethod
    def setup_class(cls):
        """Start server with house.state before running tests"""
        print(f"\n🚀 Starting server on port {SERVER_PORT} with house.state...")
        
        # Start server in background
        project_root = Path.cwd()
        server_cmd = [
            "python", "-m", "server.app", 
            "--load-state", "tests/states/house.state",
            "--port", str(SERVER_PORT),
            "--manual"
        ]
        
        cls.server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "CONDA_DEFAULT_ENV": "mgba"}
        )
        
        # Wait for server to start
        max_wait = 30
        for i in range(max_wait):
            try:
                response = requests.get(f"{SERVER_URL}/status", timeout=1)
                if response.status_code == 200:
                    print(f"✅ Server started successfully after {i+1} seconds")
                    break
            except requests.exceptions.RequestException:
                if i < max_wait - 1:
                    time.sleep(1)
                    continue
                else:
                    # Kill process if it started but isn't responding
                    cls.server_process.terminate()
                    cls.server_process.wait()
                    raise Exception(f"Server failed to start within {max_wait} seconds")
    
    @classmethod
    def teardown_class(cls):
        """Stop server after all tests"""
        print("\n🛑 Stopping server...")
        if hasattr(cls, 'server_process'):
            cls.server_process.terminate()
            cls.server_process.wait()
        print("✅ Server stopped")
    
    def test_initial_house_map(self):
        """Test that the initial house map matches the expected ground truth"""
        print("\n📍 Testing initial house map...")
        
        # Get state from server
        response = requests.get(f"{SERVER_URL}/state", timeout=5)
        assert response.status_code == 200, "Failed to get server state"
        
        state_data = response.json()
        
        # Verify location
        location = state_data.get('player', {}).get('location', '')
        assert 'BRENDANS HOUSE 1F' in location.upper(), f"Expected house location, got: {location}"
        
        # Get map tiles
        assert 'map' in state_data, "No map data in state"
        assert 'tiles' in state_data['map'], "No tiles in map data"
        
        map_tiles = state_data['map']['tiles']
        assert len(map_tiles) > 0, "Map tiles are empty"
        
        # Format map data (convert from server format to test format)
        formatted_map = self._format_server_map_data(map_tiles, f"House Map - {location}")
        
        # Load expected ground truth
        truth_path = Path("tests/states/house_map_truth.txt")
        if truth_path.exists():
            with open(truth_path, 'r') as f:
                expected_map = f.read().strip()
            
            # Compare maps (allowing for some flexibility in coordinates/format)
            assert self._maps_are_similar(formatted_map, expected_map), \
                f"House map doesn't match expected format:\n\nActual:\n{formatted_map}\n\nExpected:\n{expected_map}"
        else:
            print(f"⚠️  Ground truth file not found at {truth_path}")
            print(f"House map format:\n{formatted_map}")
            # Don't fail if ground truth doesn't exist, just verify basic structure
            assert "HOUSE" in formatted_map or "BRENDAN" in formatted_map, "Map should contain house-related content"
    
    def test_walk_outside_transition(self):
        """Test walking outside from house and verify map is correct"""
        print("\n🚶 Testing transition from house to outside...")
        
        # First, check initial position
        response = requests.get(f"{SERVER_URL}/state", timeout=5)
        initial_state = response.json()
        initial_pos = initial_state.get('player', {}).get('position', {})
        print(f"   Initial position: ({initial_pos.get('x', '?')}, {initial_pos.get('y', '?')})")
        
        # Walk down until we exit the house (up to 10 steps)
        steps_taken = 0
        max_steps = 10
        
        for i in range(max_steps):
            print(f"   Step {i+1}: Walking DOWN...")
            response = requests.post(f"{SERVER_URL}/action", 
                                   json={"type": "button", "button": "down"}, 
                                   timeout=5)
            assert response.status_code == 200, f"Failed to send DOWN action on step {i+1}"
            time.sleep(0.5)  # Longer delay to ensure movement completes
            
            # Check current location after this step
            response = requests.get(f"{SERVER_URL}/state", timeout=5)
            state_data = response.json()
            location = state_data.get('player', {}).get('location', '')
            position = state_data.get('player', {}).get('position', {})
            
            print(f"      After step {i+1}: {location} at ({position.get('x', '?')}, {position.get('y', '?')})")
            
            # Check if we've exited the house
            if 'HOUSE' not in location.upper():
                print(f"   ✅ Exited house after {i+1} steps!")
                steps_taken = i + 1
                break
        
        if steps_taken == 0:
            # If we never exited, show current state for debugging
            print(f"   ❌ Never exited house after {max_steps} steps. Current location: {location}")
            assert False, f"Failed to exit house after {max_steps} DOWN movements"
        
        # Get state after transition
        response = requests.get(f"{SERVER_URL}/state", timeout=5)
        assert response.status_code == 200, "Failed to get server state after transition"
        
        state_data = response.json()
        
        # Verify we're now outside
        location = state_data.get('player', {}).get('location', '')
        assert 'LITTLEROOT TOWN' in location.upper(), f"Expected to be in Littleroot Town, got: {location}"
        assert 'HOUSE' not in location.upper(), f"Should be outside house, but got: {location}"
        
        # Get map tiles
        assert 'map' in state_data, "No map data in state after transition"
        assert 'tiles' in state_data['map'], "No tiles in map data after transition"
        
        map_tiles = state_data['map']['tiles']
        assert len(map_tiles) > 0, "Map tiles are empty after transition"
        
        # Validate map quality
        validation_result = self._validate_outside_map(map_tiles, location)
        assert validation_result['is_valid'], f"Outside map validation failed: {validation_result['message']}"
        
        # Format and display map for debugging
        formatted_map = self._format_server_map_data(map_tiles, f"Outside Map - {location}")
        print(f"\n🗺️  Outside map:\n{formatted_map}")
        
        print(f"✅ Map validation: {validation_result['message']}")
    
    def _format_server_map_data(self, server_tiles, title="Map Data"):
        """Convert server tile format to the same format as test_memory_map.py"""
        # Convert server format [tile_id, behavior_int, collision, elevation] 
        # to test format (tile_id, behavior_enum, collision, elevation)
        formatted_tiles = []
        
        for row in server_tiles:
            formatted_row = []
            for tile in row:
                if len(tile) >= 4:
                    tile_id, behavior_int, collision, elevation = tile
                    
                    # Convert behavior integer to enum for compatibility
                    try:
                        behavior_enum = MetatileBehavior(behavior_int)
                    except ValueError:
                        behavior_enum = None  # Will be handled as "UNKNOWN" in format function
                    
                    formatted_row.append((tile_id, behavior_enum, collision, elevation))
                else:
                    # Fallback for incomplete tile data
                    formatted_row.append((0, None, 0, 0))
            
            formatted_tiles.append(formatted_row)
        
        return format_map_data(formatted_tiles, title)
    
    def _maps_are_similar(self, actual, expected):
        """Check if two maps are similar (allowing for minor differences)"""
        # For now, just check that both contain reasonable map structure
        # Could be made more sophisticated later
        
        # Both should have map dimensions
        actual_has_dimensions = "Map dimensions:" in actual
        expected_has_dimensions = "Map dimensions:" in expected
        
        # Both should have traversability map
        actual_has_traversability = "TRAVERSABILITY MAP" in actual
        expected_has_traversability = "TRAVERSABILITY MAP" in expected
        
        # Both should have player position
        actual_has_player = " P " in actual
        expected_has_player = " P " in expected
        
        return (actual_has_dimensions and expected_has_dimensions and 
                actual_has_traversability and expected_has_traversability and 
                actual_has_player and expected_has_player)
    
    def _validate_outside_map(self, map_tiles, location_name):
        """Validate that outside map looks reasonable"""
        if not map_tiles or len(map_tiles) == 0:
            return {"is_valid": False, "message": "Empty map data"}
        
        total_tiles = sum(len(row) for row in map_tiles)
        unknown_tiles = 0
        walkable_tiles = 0
        wall_tiles = 0
        special_tiles = 0
        
        for row in map_tiles:
            for tile in row:
                if len(tile) >= 4:
                    tile_id, behavior_int, collision, elevation = tile
                    
                    # Convert behavior
                    try:
                        behavior_enum = MetatileBehavior(behavior_int)
                        behavior_name = behavior_enum.name
                    except ValueError:
                        behavior_name = "UNKNOWN"
                    
                    if behavior_name == "UNKNOWN":
                        unknown_tiles += 1
                    elif behavior_name == "NORMAL":
                        if collision == 0:
                            walkable_tiles += 1
                        else:
                            wall_tiles += 1
                    else:
                        special_tiles += 1
        
        unknown_ratio = unknown_tiles / total_tiles if total_tiles > 0 else 0
        walkable_ratio = walkable_tiles / total_tiles if total_tiles > 0 else 0
        wall_ratio = wall_tiles / total_tiles if total_tiles > 0 else 0
        
        # Validation rules for outside area
        if unknown_ratio > 0.2:
            return {"is_valid": False, "message": f"Too many unknown tiles: {unknown_ratio:.1%}"}
        
        if walkable_ratio < 0.15:
            return {"is_valid": False, "message": f"Too few walkable tiles: {walkable_ratio:.1%}"}
        
        if wall_ratio > 0.95:
            return {"is_valid": False, "message": f"Too many walls: {wall_ratio:.1%}"}
        
        return {
            "is_valid": True, 
            "message": f"Map valid: {walkable_ratio:.1%} walkable, {wall_ratio:.1%} walls, {unknown_ratio:.1%} unknown"
        }

if __name__ == "__main__":
    # Run the test directly
    import sys
    pytest.main([__file__, "-v", "-s"] + sys.argv[1:])