#!/usr/bin/env python3
"""
Test dialogue detection functionality.
"""

import pytest
import numpy as np
from utils.state_formatter import detect_dialogue_on_frame, format_state_for_llm


def test_dialogue_detection_with_blue_box():
    """Test dialogue detection with typical blue dialogue box."""
    # Create a mock frame with dialogue box characteristics (240x160 GBA resolution)
    frame = np.zeros((160, 240, 3), dtype=np.uint8)
    
    # Add blue dialogue box in bottom 50 pixels
    # Blue color (R, G, B) where blue is dominant
    frame[110:160, :] = [50, 70, 150]  # Bluish background
    
    # Add some white text areas
    frame[120:130, 20:220] = [220, 220, 220]  # White text area
    
    # Add border lines
    frame[110:112, :] = [100, 100, 100]  # Top border
    frame[158:160, :] = [100, 100, 100]  # Bottom border
    
    result = detect_dialogue_on_frame(frame_array=frame)
    
    assert result['has_dialogue'] == True
    assert result['confidence'] > 0.5
    assert 'blue dialogue box' in result['reason'].lower()


def test_no_dialogue_detection():
    """Test that normal gameplay doesn't trigger dialogue detection."""
    # Create a mock frame with varied gameplay content (no dialogue)
    frame = np.random.randint(0, 255, (160, 240, 3), dtype=np.uint8)
    
    # Make it less random - add some structure but not dialogue-like
    frame[0:80, :] = [100, 150, 100]  # Greenish top (grass/trees)
    frame[80:160, :] = [150, 130, 100]  # Brownish bottom (ground)
    
    result = detect_dialogue_on_frame(frame_array=frame)
    
    assert result['has_dialogue'] == False
    assert result['confidence'] < 0.5


def test_dialogue_detection_grayscale():
    """Test dialogue detection with grayscale input."""
    # Create a grayscale frame
    frame = np.zeros((160, 240), dtype=np.uint8)
    
    # Add high contrast pattern in dialogue area
    frame[110:160, :] = 50  # Dark background
    frame[120:130, 20:220] = 200  # Light text area
    
    # Add horizontal edges
    frame[110:112, :] = 150
    frame[158:160, :] = 150
    
    result = detect_dialogue_on_frame(frame_array=frame)
    
    # Should detect based on contrast and structure
    assert 'text contrast' in result['reason'].lower() or 'borders' in result['reason'].lower()


def test_dialogue_validation_in_state():
    """Test that dialogue validation works in state formatting."""
    # State with dialogue text but no frame detection
    state_no_detection = {
        'player': {'name': 'Red', 'position': {'x': 10, 'y': 10}},
        'game': {
            'dialog_text': 'Hello trainer! Would you like to battle?',
            'dialogue_detected': {'has_dialogue': True, 'confidence': 0.8}
        },
        'map': {}
    }
    
    formatted = format_state_for_llm(state_no_detection)
    assert 'DIALOGUE' in formatted
    assert 'Hello trainer' in formatted
    assert 'Detection confidence: 80.0%' in formatted
    
    # State with dialogue text but frame says no dialogue visible
    state_no_visible = {
        'player': {'name': 'Red', 'position': {'x': 10, 'y': 10}},
        'game': {
            'dialog_text': 'Hello trainer! Would you like to battle?',
            'dialogue_detected': {'has_dialogue': False, 'confidence': 0.1}
        },
        'map': {}
    }
    
    formatted = format_state_for_llm(state_no_visible)
    assert 'RESIDUAL TEXT' in formatted
    assert 'not visible' in formatted
    
    # State with no dialogue detection info (backwards compatibility)
    state_legacy = {
        'player': {'name': 'Red', 'position': {'x': 10, 'y': 10}},
        'game': {
            'dialog_text': 'Hello trainer! Would you like to battle?'
        },
        'map': {}
    }
    
    formatted = format_state_for_llm(state_legacy)
    assert 'Hello trainer' in formatted  # Should still show dialogue


def test_dialogue_detection_edge_cases():
    """Test edge cases for dialogue detection."""
    # Test with None
    result = detect_dialogue_on_frame(frame_array=None)
    assert result['has_dialogue'] == False
    assert 'No frame data' in result['reason']
    
    # Test with wrong shape
    small_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    result = detect_dialogue_on_frame(frame_array=small_frame)
    # Should still work but likely no dialogue detected
    assert 'has_dialogue' in result
    assert 'confidence' in result
    
    # Test with very small dialogue region
    tiny_frame = np.zeros((50, 240, 3), dtype=np.uint8)
    result = detect_dialogue_on_frame(frame_array=tiny_frame)
    assert 'has_dialogue' in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])