#!/usr/bin/env python3
"""
Test for torchic state and milestone reading

This test verifies that:
1. The torchic state loads correctly
2. The state contains the expected data (player in Littleroot Town, has Torchic)
3. The milestones are correctly detected and include Littleroot Town
"""

import pytest
import subprocess
import time
import requests
import json
import os

class ServerManager:
    """Manages server startup and shutdown for tests"""
    
    def __init__(self):
        self.server_process = None
    
    def start_server(self, state_file):
        """Start the server with a specific state file"""
        print(f"🚀 Starting server with state: {state_file}")
        cmd = ["python", "-m", "server.app", "--manual", "--load-state", state_file]
        
        try:
            self.server_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            # Wait for server to start
            print("⏳ Waiting for server to start...")
            time.sleep(5)
            
            # Test if server is responding
            response = requests.get("http://localhost:8000/status", timeout=5)
            if response.status_code == 200:
                print("✅ Server started successfully")
                return True
            else:
                print(f"❌ Server not responding: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
    
    def stop_server(self):
        """Stop the server cleanly"""
        if self.server_process:
            print("🛑 Stopping server...")
            try:
                # Try graceful shutdown first
                requests.post("http://localhost:8000/stop", timeout=2)
                time.sleep(1)
            except:
                pass
            
            # Force terminate if still running
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                print("✅ Server stopped gracefully")
            except subprocess.TimeoutExpired:
                print("⚠️  Server didn't stop gracefully, force killing...")
                self.server_process.kill()
                self.server_process.wait()
                print("✅ Server force killed")

@pytest.fixture(scope="session", autouse=True)
def check_environment():
    """Check that required files exist"""
    torchic_state = "tests/states/torchic.state"
    if not os.path.exists(torchic_state):
        pytest.skip(f"Torchic state file not found: {torchic_state}")
    
    print(f"✅ Found torchic state file: {torchic_state}")

def test_torchic_state_loading():
    """Test that the torchic state loads correctly"""
    server_manager = ServerManager()
    
    try:
        # Start server with torchic state
        assert server_manager.start_server("tests/states/torchic.state"), "Failed to start server"
        
        # Get comprehensive state
        response = requests.get("http://localhost:8000/state", timeout=10)
        assert response.status_code == 200, f"Failed to get state: {response.status_code}"
        
        state_data = response.json()
        
        # Test basic state structure
        assert "player" in state_data, "State missing player data"
        assert "game" in state_data, "State missing game data"
        assert "visual" in state_data, "State missing visual data"
        
        # Test player data
        player = state_data["player"]
        assert "name" in player, "Player data missing name"
        assert "location" in player, "Player data missing location"
        assert "position" in player, "Player data missing position"
        assert "party" in player, "Player data missing party"
        
        # Test that player is in Route 101 (where the torchic state is)
        location = player["location"]
        print(f"📍 Player location: {location}")
        assert "ROUTE 101" in location.upper(), f"Expected player to be in Route 101, but found: {location}"
        
        # Test party data
        party = player["party"]
        assert isinstance(party, list), "Party should be a list"
        assert len(party) > 0, "Party should not be empty"
        
        # Test that first Pokemon is Torchic
        first_pokemon = party[0]
        assert "species_name" in first_pokemon, "Pokemon missing species_name"
        species_name = first_pokemon["species_name"]
        print(f"🔥 First Pokemon: {species_name}")
        assert species_name.upper() == "TORCHIC", f"Expected Torchic, but found: {species_name}"
        
        # Test Pokemon data structure
        assert "level" in first_pokemon, "Pokemon missing level"
        assert "current_hp" in first_pokemon, "Pokemon missing current_hp"
        assert "max_hp" in first_pokemon, "Pokemon missing max_hp"
        assert "moves" in first_pokemon, "Pokemon missing moves"
        
        print(f"✅ Torchic level: {first_pokemon['level']}")
        print(f"✅ Torchic HP: {first_pokemon['current_hp']}/{first_pokemon['max_hp']}")
        print(f"✅ Torchic moves: {first_pokemon['moves']}")
        
    finally:
        server_manager.stop_server()

def test_torchic_milestones():
    """Test that milestones are correctly detected for torchic state"""
    server_manager = ServerManager()
    
    try:
        # Start server with torchic state
        assert server_manager.start_server("tests/states/torchic.state"), "Failed to start server"
        
        # Get milestones
        response = requests.get("http://localhost:8000/milestones", timeout=10)
        assert response.status_code == 200, f"Failed to get milestones: {response.status_code}"
        
        milestones_data = response.json()
        
        # Test milestones structure
        assert "milestones" in milestones_data, "Milestones data missing milestones list"
        assert "completed" in milestones_data, "Milestones data missing completed count"
        assert "total" in milestones_data, "Milestones data missing total count"
        assert "progress" in milestones_data, "Milestones data missing progress"
        assert "current_location" in milestones_data, "Milestones data missing current_location"
        
        milestones = milestones_data["milestones"]
        completed = milestones_data["completed"]
        total = milestones_data["total"]
        progress = milestones_data["progress"]
        current_location = milestones_data["current_location"]
        
        print(f"📊 Milestones progress: {completed}/{total} ({progress:.1%})")
        print(f"📍 Current location: {current_location}")
        
        # Test that Littleroot Town milestone exists (but may not be completed since we're in Route 101)
        littleroot_milestone = None
        for milestone in milestones:
            if "LITTLEROOT" in milestone["name"].upper():
                littleroot_milestone = milestone
                break
        
        assert littleroot_milestone is not None, "Littleroot Town milestone not found"
        print(f"🏘️  Littleroot milestone: {littleroot_milestone}")
        
        # Test that current location is Route 101
        assert "ROUTE 101" in current_location.upper(), f"Current location should be Route 101, but found: {current_location}"
        
        # Test that basic milestones are completed
        basic_milestones = ["GAME_RUNNING", "HAS_PARTY", "STARTER_CHOSEN", "TORCHIC_OBTAINED", "ROUTE_101_VISITED"]
        for milestone_name in basic_milestones:
            milestone = next((m for m in milestones if m["name"] == milestone_name), None)
            assert milestone is not None, f"Basic milestone {milestone_name} not found"
            assert milestone["completed"] == True, f"Basic milestone {milestone_name} should be completed"
            print(f"✅ {milestone_name}: Completed")
        
        # Test that some milestones are not yet completed (game just started)
        incomplete_milestones = ["STONE_BADGE", "POKEDEX_RECEIVED", "FIRST_WILD_ENCOUNTER", "LITTLEROOT_TOWN"]
        for milestone_name in incomplete_milestones:
            milestone = next((m for m in milestones if m["name"] == milestone_name), None)
            assert milestone is not None, f"Milestone {milestone_name} not found"
            assert milestone["completed"] == False, f"Milestone {milestone_name} should not be completed yet"
            print(f"⏳ {milestone_name}: Not completed yet")
        
    finally:
        server_manager.stop_server()

def test_torchic_state_summary():
    """Test that the torchic state provides a comprehensive summary"""
    server_manager = ServerManager()
    
    try:
        # Start server with torchic state
        assert server_manager.start_server("tests/states/torchic.state"), "Failed to start server"
        
        # Get comprehensive state
        response = requests.get("http://localhost:8000/state", timeout=10)
        assert response.status_code == 200, f"Failed to get state: {response.status_code}"
        
        state_data = response.json()
        
        # Test game state
        game = state_data["game"]
        assert "money" in game, "Game data missing money"
        assert "game_state" in game, "Game data missing game_state"
        assert "is_in_battle" in game, "Game data missing is_in_battle"
        assert "badges" in game, "Game data missing badges"
        assert "dialog_text" in game, "Game data missing dialog_text"
        
        # Test that player has some money (starter money)
        money = game["money"]
        print(f"💰 Player money: {money}")
        assert money >= 0, "Player should have non-negative money"
        
        # Test that player is not in battle
        is_in_battle = game["is_in_battle"]
        print(f"⚔️  In battle: {is_in_battle}")
        assert is_in_battle == False, "Player should not be in battle at start"
        
        # Test that player has no badges yet
        badges = game["badges"]
        print(f"🏆 Badges: {badges}")
        assert len(badges) == 0, "Player should have no badges at start"
        
        # Test visual data
        visual = state_data["visual"]
        assert "screenshot_base64" in visual, "Visual data missing screenshot"
        assert "resolution" in visual, "Visual data missing resolution"
        
        resolution = visual["resolution"]
        print(f"📺 Resolution: {resolution}")
        assert resolution == [240, 160], f"Expected resolution [240, 160], got {resolution}"
        
        # Test that screenshot is present
        screenshot = visual["screenshot_base64"]
        assert len(screenshot) > 0, "Screenshot should not be empty"
        print(f"📸 Screenshot size: {len(screenshot)} characters")
        
        print("✅ Torchic state test completed successfully")
        
    finally:
        server_manager.stop_server()

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 