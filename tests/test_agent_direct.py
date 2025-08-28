#!/usr/bin/env python3
"""
Pytest for agent_direct functionality
"""

import pytest
import requests
import json
import time

class TestAgentDirectAPI:
    """Test class for agent_direct API endpoints"""
    
    base_url = "http://localhost:8080"
    
    def test_imports_work(self):
        """Test that our imports are working"""
        import agent_direct
        assert hasattr(agent_direct, 'app')
        assert hasattr(agent_direct, 'agent_mode')
        assert hasattr(agent_direct, 'websocket_connections')
        
    def test_global_state_initialized(self):
        """Test that global state variables are properly initialized"""
        import agent_direct
        assert agent_direct.agent_mode == False  # Should start in manual mode
        assert agent_direct.agent_auto_enabled == False  # Should start with auto disabled
        assert isinstance(agent_direct.websocket_connections, set)
        assert len(agent_direct.websocket_connections) == 0  # Should start empty
        
    def test_broadcast_function_exists(self):
        """Test that broadcast function exists and is callable"""
        import agent_direct
        assert hasattr(agent_direct, 'broadcast_state_update')
        assert callable(agent_direct.broadcast_state_update)
    
    @pytest.mark.skip(reason="Requires running server")
    def test_status_endpoint(self):
        """Test the /status endpoint"""
        try:
            response = requests.get(f"{self.base_url}/status", timeout=2)
            assert response.status_code == 200
            data = response.json()
            assert "step" in data
            assert "agent_initialized" in data
        except requests.exceptions.ConnectionError:
            pytest.skip("agent_direct server not running")
    
    @pytest.mark.skip(reason="Requires running server") 
    def test_toggle_mode_endpoint(self):
        """Test the /toggle_mode endpoint"""
        try:
            response = requests.post(f"{self.base_url}/toggle_mode", timeout=2)
            assert response.status_code == 200
            data = response.json()
            assert "mode" in data
            assert "agent_mode" in data
            assert data["mode"] in ["MANUAL", "AGENT"]
        except requests.exceptions.ConnectionError:
            pytest.skip("agent_direct server not running")
    
    @pytest.mark.skip(reason="Requires running server")
    def test_toggle_auto_endpoint(self):
        """Test the /toggle_auto endpoint"""
        try:
            response = requests.post(f"{self.base_url}/toggle_auto", timeout=2)
            assert response.status_code == 200
            data = response.json()
            assert "auto_enabled" in data
            assert "status" in data
            assert data["status"] in ["ENABLED", "DISABLED"]
        except requests.exceptions.ConnectionError:
            pytest.skip("agent_direct server not running")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])