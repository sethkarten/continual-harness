#!/usr/bin/env python3
"""
Comprehensive pytest for dialogue detection system across all states
"""

import pytest
import sys
import os
import io
import subprocess
import time
import requests
import json
import base64
from pathlib import Path
from PIL import Image

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from utils.ocr_dialogue import create_ocr_detector

class TestDialogueDetection:
    """Test dialogue detection accuracy across all provided states"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.detector = create_ocr_detector()
        self.agent_port = 8000
        assert self.detector is not None, "Could not create OCR detector"
        
        # Kill any existing agent_direct processes
        subprocess.run(["pkill", "-f", "agent_direct.py"], capture_output=True)
        time.sleep(1)
    
    def teardown_method(self):
        """Cleanup after each test"""
        subprocess.run(["pkill", "-f", "agent_direct.py"], capture_output=True)
        time.sleep(0.5)
    
    def _test_state_file(self, state_file, expected_dialogue, description=""):
        """Helper to test a single state file"""
        print(f"\n🧪 Testing: {state_file}")
        print(f"   Expected dialogue: {expected_dialogue}")
        print(f"   Description: {description}")
        
        # Start agent_direct with this state
        cmd = [
            "/home/milkkarten/anaconda3/envs/mgba/bin/python", 
            "agent_direct.py", 
            "--load-state", state_file,
            "--backend", "gemini", 
            "--manual"
        ]
        
        # Start agent_direct
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        try:
            # Wait for startup
            time.sleep(3)
            
            # Test server responsiveness
            for attempt in range(5):
                try:
                    response = requests.get(f"http://localhost:{self.agent_port}/status", timeout=2)
                    if response.status_code == 200:
                        break
                    time.sleep(1)
                except:
                    time.sleep(1)
            else:
                pytest.fail(f"Agent_direct failed to start for {state_file}")
            
            # Get screenshot
            frame_response = requests.get(f"http://localhost:{self.agent_port}/api/frame", timeout=5)
            assert frame_response.status_code == 200, f"Failed to get screenshot for {state_file}"
            
            frame_data = frame_response.json()
            assert frame_data.get('frame'), f"No frame data for {state_file}"
            
            # Decode screenshot
            image_data = base64.b64decode(frame_data['frame'])
            screenshot = Image.open(io.BytesIO(image_data))
            
            # Test dialogue detection
            box_detected = self.detector.is_dialogue_box_visible(screenshot)
            ocr_text = self.detector.detect_dialogue_from_screenshot(screenshot)
            
            print(f"   📦 Box detected: {box_detected}")
            print(f"   👁️ OCR text: '{ocr_text}'")
            
            # Get memory reading for comparison
            try:
                state_response = requests.get(f"http://localhost:{self.agent_port}/state", timeout=3)
                if state_response.status_code == 200:
                    state_data = state_response.json()
                    memory_text = state_data.get('game', {}).get('dialog_text', None)
                    print(f"   💾 Memory text: '{memory_text}'")
                else:
                    memory_text = "N/A"
            except:
                memory_text = "N/A"
            
            # Verify detection accuracy
            assert box_detected == expected_dialogue, (
                f"Detection mismatch for {state_file}: expected {expected_dialogue}, got {box_detected}"
            )
            
            return {
                'state_file': state_file,
                'expected_dialogue': expected_dialogue,
                'box_detected': box_detected,
                'ocr_text': ocr_text,
                'memory_text': memory_text,
                'description': description
            }
            
        finally:
            process.terminate()
            time.sleep(1)
    
    def test_coordinate_tightness(self):
        """Test that OCR coordinates are properly tight around text area"""
        dialogue_coords = self.detector.DIALOGUE_BOX_COORDS
        ocr_coords = self.detector.OCR_TEXT_COORDS
        
        # Calculate margins
        left_margin = ocr_coords['x'] - dialogue_coords['x']
        top_margin = ocr_coords['y'] - dialogue_coords['y']
        right_margin = (dialogue_coords['x'] + dialogue_coords['width']) - (ocr_coords['x'] + ocr_coords['width'])
        bottom_margin = (dialogue_coords['y'] + dialogue_coords['height']) - (ocr_coords['y'] + ocr_coords['height'])
        
        print(f"📏 Margins - Left: {left_margin}px, Top: {top_margin}px, Right: {right_margin}px, Bottom: {bottom_margin}px")
        
        # Verify margins are reasonable (4-16 pixels to avoid borders but not cut text)
        assert 4 <= left_margin <= 16, f"Left margin {left_margin}px outside acceptable range (4-16px)"
        assert 4 <= top_margin <= 16, f"Top margin {top_margin}px outside acceptable range (4-16px)"
        assert 4 <= right_margin <= 16, f"Right margin {right_margin}px outside acceptable range (4-16px)"
        assert 4 <= bottom_margin <= 16, f"Bottom margin {bottom_margin}px outside acceptable range (4-16px)"
    
    def test_no_dialog_states(self):
        """Test states that should NOT have dialogue"""
        no_dialog_states = [
            ("tests/states/no_dialog1.state", "No dialogue state 1"),
            ("tests/states/no_dialog2.state", "No dialogue state 2"),
            ("tests/states/no_dialog3.state", "No dialogue state 3"),
        ]
        
        for state_file, description in no_dialog_states:
            if os.path.exists(state_file):
                result = self._test_state_file(state_file, False, description)
                assert result['box_detected'] == False, f"False positive detected in {state_file}"
            else:
                pytest.skip(f"State file not found: {state_file}")
    
    def test_dialog_states(self):
        """Test states that SHOULD have dialogue"""
        dialog_states = [
            ("tests/states/dialog.state", "Original dialogue state"),
            ("tests/states/dialog2.state", "Second dialogue state"),
            ("tests/states/dialog3.state", "New dialogue state 3"),
        ]
        
        for state_file, description in dialog_states:
            if os.path.exists(state_file):
                result = self._test_state_file(state_file, True, description)
                assert result['box_detected'] == True, f"Failed to detect dialogue in {state_file}"
            else:
                pytest.skip(f"State file not found: {state_file}")
    
    def test_static_image_detection(self):
        """Test detection on static images"""
        # Test known dialogue frame
        if os.path.exists("dialog_frame.png"):
            image = Image.open("dialog_frame.png")
            box_detected = self.detector.is_dialogue_box_visible(image)
            assert box_detected == True, "Failed to detect dialogue in known dialogue frame"
        
        # Test emerald.png (should be no dialogue)
        if os.path.exists("emerald.png"):
            image = Image.open("emerald.png")
            box_detected = self.detector.is_dialogue_box_visible(image)
            assert box_detected == False, "False positive detected in emerald.png"
    
    def test_ocr_preprocessing_quality(self):
        """Test that OCR preprocessing produces high-quality black/white output"""
        if os.path.exists("dialog_frame.png"):
            image = Image.open("dialog_frame.png")
            image_np = np.array(image)
            
            # Extract OCR region
            ocr_coords = self.detector.OCR_TEXT_COORDS
            ocr_region = image_np[
                ocr_coords['y']:ocr_coords['y'] + ocr_coords['height'],
                ocr_coords['x']:ocr_coords['x'] + ocr_coords['width']
            ]
            
            # Test preprocessing
            processed = self.detector._preprocess_for_ocr(ocr_region)
            
            # Verify it's binary (only 0 and 255 values)
            unique_values = np.unique(processed)
            assert len(unique_values) <= 2, f"Processed image should be binary, found {len(unique_values)} unique values"
            
            # Should have both black and white pixels (text and background)
            if len(unique_values) == 2:
                assert 0 in unique_values and 255 in unique_values, "Should have pure black (0) and white (255) pixels"

class TestDialogueIntegration:
    """Test integration with LLM agent comprehensive state"""
    
    def test_comprehensive_state_includes_dialog(self):
        """Test that comprehensive state includes dialogue reading"""
        # This test verifies the integration works but doesn't need to run agent_direct
        # Just verify the OCR detector can be imported and works
        detector = create_ocr_detector()
        assert detector is not None, "OCR detector should be available for comprehensive state"
        
        # Verify key methods exist
        assert hasattr(detector, 'is_dialogue_box_visible'), "Detector should have dialogue box detection"
        assert hasattr(detector, 'detect_dialogue_from_screenshot'), "Detector should have text detection"
        assert hasattr(detector, 'read_dialog_with_ocr_fallback'), "Detector should have smart fallback logic"

if __name__ == "__main__":
    # Allow running as script for debugging
    import numpy as np
    pytest.main([__file__, "-v", "-s"])