"""
OCR-based dialogue detection for Pokemon Emerald.
Provides fallback text detection when memory reading fails or returns stale data.
"""

import cv2
import numpy as np
from PIL import Image
from typing import Optional, List, Tuple
import re
import logging

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.warning("pytesseract not available - OCR dialogue detection disabled")

logger = logging.getLogger(__name__)

class OCRDialogueDetector:
    """OCR-based dialogue detection for Pokemon Emerald"""
    
    # Pokemon Emerald dialogue box coordinates (corrected for actual dialogue position)
    DIALOGUE_BOX_COORDS = {
        'x': 0,       # Full width - dialogue spans entire bottom
        'y': 104,     # Dialogue starts around row 104 (from debug analysis)
        'width': 240, # Full screen width
        'height': 56  # Bottom portion height (160-104=56)
    }
    
    # Tighter OCR coordinates - just the text area inside the border (adjusted lower)
    OCR_TEXT_COORDS = {
        'x': 8,       # Skip left border 
        'y': 116,     # Moved down 4px for better text alignment (104 + 12)
        'width': 224, # Skip both side borders (240 - 16)
        'height': 36  # Reduced height to maintain bottom margin (56 - 20)
    }
    
    # Pokemon Emerald dialogue text colors (based on actual RGB values)
    DIALOGUE_TEXT_COLORS = [
        # Exact text color from user
        (99, 99, 99),      # Exact text color
        # Close variations for anti-aliasing and slight rendering differences  
        (95, 95, 95),      # Slightly darker
        (103, 103, 103),   # Slightly lighter
        (91, 91, 91),      # Darker variant
        (107, 107, 107),   # Lighter variant
        (99, 99, 95),      # Slight color shift
        (99, 95, 99),      # Slight color shift
        (95, 99, 99),      # Slight color shift
        # Additional gray tones that might appear due to rendering
        (87, 87, 87),      # Darker gray
        (111, 111, 111),   # Lighter gray
        (79, 79, 79),      # Much darker
        (119, 119, 119),   # Much lighter
        # Shadow colors (darker, often with slight offset)
        (64, 64, 64),      # Dark shadow
        (72, 72, 72),      # Medium shadow
        (56, 56, 56),      # Darker shadow
        (48, 48, 48),      # Very dark shadow
        # Possible highlighting/special text colors
        (99, 99, 128),     # Blue-tinted for names
        (128, 99, 99),     # Red-tinted for special text
        (99, 128, 99),     # Green-tinted for special text
    ]
    
    # Color tolerance for matching (RGB distance) - increased to capture more text pixels
    COLOR_TOLERANCE = 40
    
    # Pokemon Emerald dialogue box background colors (based on actual RGB values)
    DIALOGUE_BOX_BACKGROUND_COLORS = [
        # Exact green line/border color from user
        (85, 204, 128),    # Exact green border color
        # Variations of the green border for anti-aliasing and shadows
        (80, 199, 123),    # Slightly darker green
        (90, 209, 133),    # Slightly lighter green
        (85, 204, 128),    # Exact match (duplicate for emphasis)
        (75, 194, 118),    # Darker green variant
        (95, 214, 138),    # Lighter green variant
        # Exact white text background from user
        (255, 255, 255),   # Exact white text background
        # Close variations for anti-aliasing and compression artifacts
        (254, 254, 254),   # Very close to white
        (253, 253, 253),   # Slightly off white  
        (252, 252, 252),   # Light gray-white
        (248, 248, 248),   # Near white
        (240, 240, 240),   # Light off-white
        (255, 255, 254),   # Slight yellow tint
        (254, 255, 255),   # Slight cyan tint
    ]
    
    # How much of the dialogue box should be background color to consider it "active"
    DIALOGUE_BOX_BACKGROUND_THRESHOLD = 0.4  # 40% of dialogue area should be box color (mostly off-white background)
    
    # Battle text area (different position)
    BATTLE_TEXT_COORDS = {
        'x': 8,
        'y': 120,
        'width': 224,
        'height': 40
    }
    
    def __init__(self):
        self.last_detected_text = ""
        self.text_stability_threshold = 2  # Frames text must be stable
        self.stable_text_count = 0
        self.debug_color_detection = False  # Set to True for color debugging
        self.use_full_frame_scan = False  # Set to True to enable full-frame scanning (may pick up noise)
        self.skip_dialogue_box_detection = False  # Set to True to temporarily bypass dialogue box detection
        
    def detect_dialogue_from_screenshot(self, screenshot: Image.Image) -> Optional[str]:
        """
        Detect dialogue text from Pokemon Emerald dialogue regions only.
        First verifies dialogue box is visible to prevent false positives.
        
        Args:
            screenshot: PIL Image of the game screen
            
        Returns:
            Detected dialogue text or None if no text found
        """
        if not OCR_AVAILABLE:
            return None
            
        try:
            screenshot_np = np.array(screenshot)
            
            # STEP 1: Check if dialogue box is actually visible (unless bypassed)
            if not self.skip_dialogue_box_detection and not self.is_dialogue_box_visible(screenshot):
                logger.debug("No dialogue box detected - skipping OCR")
                return None
            
            # STEP 2: Primary dialogue box area (most common) - use tighter text coordinates
            dialogue_text = self._extract_text_from_region(
                screenshot_np, 
                self.OCR_TEXT_COORDS
            )
            
            if dialogue_text:
                validated = self._validate_and_clean_text(dialogue_text)
                if validated:
                    return validated
                
            # Method 2: Battle text area (different position)
            battle_text = self._extract_text_from_region(
                screenshot_np,
                self.BATTLE_TEXT_COORDS
            )
            
            if battle_text:
                validated = self._validate_and_clean_text(battle_text)
                if validated:
                    return validated
            
            # Method 3: Full frame scan (only if explicitly enabled - can pick up noise)
            if self.use_full_frame_scan:
                full_frame_text = self._extract_text_from_full_frame(screenshot)
                if full_frame_text:
                    validated = self._validate_and_clean_text(full_frame_text)
                    if validated:
                        return validated
                
            return None
            
        except Exception as e:
            logger.debug(f"OCR dialogue detection failed: {e}")
            return None
    
    def _extract_text_from_full_frame(self, screenshot: Image.Image) -> Optional[str]:
        """
        Extract text from the entire screenshot using OCR
        This is more comprehensive than region-specific detection
        """
        try:
            # Convert PIL to numpy array
            screenshot_np = np.array(screenshot)
            
            # Preprocess the entire frame for better OCR
            processed_frame = self._preprocess_full_frame_for_ocr(screenshot_np)
            
            # OCR configuration optimized for Pokemon text detection
            # Use different settings for full frame vs regions
            full_frame_config = r'--oem 3 --psm 6'  # Assume uniform block of text
            
            # Extract text from entire frame
            full_text = pytesseract.image_to_string(processed_frame, config=full_frame_config)
            
            # Clean and validate the text
            cleaned_text = self._clean_full_frame_text(full_text)
            
            if cleaned_text:
                return cleaned_text
                
            # If that fails, try with different PSM mode
            alt_config = r'--oem 3 --psm 11'  # Sparse text, find as much as possible
            alt_text = pytesseract.image_to_string(processed_frame, config=alt_config)
            alt_cleaned = self._clean_full_frame_text(alt_text)
            
            return alt_cleaned if alt_cleaned else None
            
        except Exception as e:
            logger.debug(f"Full frame OCR failed: {e}")
            return None
    
    def _preprocess_full_frame_for_ocr(self, image_np: np.ndarray) -> np.ndarray:
        """Preprocess entire frame using Pokemon-specific dialogue color matching"""
        # Ensure we have color information
        if len(image_np.shape) != 3:
            # Convert grayscale to color by duplicating channels
            image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
        
        # Scale up for better color detection precision
        scaled = cv2.resize(image_np, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        
        # Create mask for dialogue text colors across entire frame
        text_mask = self._create_dialogue_color_mask(scaled)
        
        # Apply color mask - black text on white background (better for OCR)
        binary = np.where(text_mask, 0, 255).astype(np.uint8)
        
        # Enhanced morphological operations for full frame
        # Close gaps and thicken text
        kernel_close = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)
        
        # Dilate to make text more readable
        kernel_dilate = np.ones((1, 1), np.uint8)
        cleaned = cv2.dilate(cleaned, kernel_dilate, iterations=1)
        
        return cleaned
    
    def _clean_full_frame_text(self, raw_text: str) -> Optional[str]:
        """Clean and validate text extracted from full frame"""
        if not raw_text:
            return None
        
        # Remove excessive whitespace and special characters
        lines = []
        for line in raw_text.split('\n'):
            # Clean each line
            cleaned_line = re.sub(r'\s+', ' ', line.strip())
            
            # Filter out lines that are likely noise
            if len(cleaned_line) >= 2:  # Minimum meaningful length
                # Check if line has reasonable character content
                alpha_ratio = sum(c.isalpha() for c in cleaned_line) / len(cleaned_line)
                if alpha_ratio >= 0.3:  # At least 30% alphabetic characters
                    lines.append(cleaned_line)
        
        if not lines:
            return None
        
        # Join lines and do final cleanup
        full_text = ' '.join(lines)
        
        # Remove common OCR artifacts for Pokemon games
        # These are characters commonly misread by OCR
        ocr_artifacts = [
            r'[|\\/_]',  # Common line artifacts
            r'^\W+',     # Leading non-word characters
            r'\W+$',     # Trailing non-word characters
        ]
        
        for artifact in ocr_artifacts:
            full_text = re.sub(artifact, ' ', full_text)
        
        # Final cleanup
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        
        # Validate final result
        if len(full_text) < 3:
            return None
            
        # Check for reasonable content (not just numbers/symbols)
        alpha_count = sum(c.isalpha() for c in full_text)
        if alpha_count < 3:  # Need at least 3 letters
            return None
        
        return full_text
    
    def detect_all_text_regions(self, screenshot: Image.Image) -> List[dict]:
        """
        Detect all text regions in the screenshot with their locations
        Useful for debugging and comprehensive text detection
        """
        if not OCR_AVAILABLE:
            return []
            
        try:
            # Convert to numpy array
            screenshot_np = np.array(screenshot)
            processed = self._preprocess_full_frame_for_ocr(screenshot_np)
            
            # Use pytesseract to get text with bounding boxes
            data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
            
            text_regions = []
            n_boxes = len(data['level'])
            
            for i in range(n_boxes):
                # Get confidence and text
                confidence = int(data['conf'][i])
                text = data['text'][i].strip()
                
                # Only include text with reasonable confidence and content
                if confidence > 30 and len(text) > 1:
                    # Get bounding box (scale back from 2x preprocessing)
                    x = data['left'][i] // 2  # Scale back from 2x
                    y = data['top'][i] // 2
                    w = data['width'][i] // 2
                    h = data['height'][i] // 2
                    
                    # Validate text content
                    alpha_ratio = sum(c.isalpha() for c in text) / len(text)
                    if alpha_ratio >= 0.3:  # At least 30% letters
                        text_regions.append({
                            'text': text,
                            'confidence': confidence,
                            'bbox': (x, y, w, h),
                            'area': w * h
                        })
            
            # Sort by confidence and area (larger, more confident regions first)
            text_regions.sort(key=lambda r: (r['confidence'], r['area']), reverse=True)
            
            return text_regions
            
        except Exception as e:
            logger.debug(f"Text region detection failed: {e}")
            return []
    
    def _extract_text_from_region(self, image_np: np.ndarray, coords: dict) -> str:
        """Extract text from a specific region of the image"""
        # Extract region of interest
        y1 = coords['y']
        y2 = y1 + coords['height']
        x1 = coords['x']
        x2 = x1 + coords['width']
        
        roi = image_np[y1:y2, x1:x2]
        
        # Preprocessing for better OCR accuracy
        roi = self._preprocess_for_ocr(roi)
        
        # OCR configuration optimized for Pokemon Emerald text
        custom_config = r'--oem 3 --psm 6'
        
        # Extract text
        text = pytesseract.image_to_string(roi, config=custom_config)
        return text.strip()
    
    def _preprocess_for_ocr(self, roi: np.ndarray) -> np.ndarray:
        """Preprocess image region using Pokemon-specific dialogue color matching"""
        # Keep original color information for color matching
        if len(roi.shape) != 3:
            # Convert grayscale back to color for processing (duplicate channels)
            roi = cv2.cvtColor(roi, cv2.COLOR_GRAY2RGB)
        
        # Scale up first for better color detection precision
        roi = cv2.resize(roi, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        
        # Create mask for dialogue text colors
        text_mask = self._create_dialogue_color_mask(roi)
        
        # Apply color mask to create clean binary image
        # Black text on white background (better for OCR)
        binary_roi = np.where(text_mask, 0, 255).astype(np.uint8)
        
        # Ensure we have a proper binary image (pure black and white only)
        binary_roi = np.where(binary_roi > 127, 255, 0).astype(np.uint8)
        
        # Enhanced morphological operations to thicken and connect text
        # Close gaps in letters
        kernel_close = np.ones((2, 2), np.uint8)
        binary_roi = cv2.morphologyEx(binary_roi, cv2.MORPH_CLOSE, kernel_close)
        
        # Dilate to make text thicker and more readable (balanced approach)
        kernel_dilate = np.ones((2, 2), np.uint8)
        binary_roi = cv2.dilate(binary_roi, kernel_dilate, iterations=2)
        
        # Remove small noise while preserving text
        kernel_open = np.ones((1, 1), np.uint8)
        binary_roi = cv2.morphologyEx(binary_roi, cv2.MORPH_OPEN, kernel_open)
        
        return binary_roi
    
    def _create_dialogue_color_mask(self, image: np.ndarray) -> np.ndarray:
        """Create binary mask for pixels matching Pokemon dialogue text colors"""
        if len(image.shape) != 3:
            return np.zeros(image.shape[:2], dtype=bool)
        
        mask = np.zeros(image.shape[:2], dtype=bool)
        matched_pixels_per_color = []
        
        # Check each dialogue color
        for i, target_color in enumerate(self.DIALOGUE_TEXT_COLORS):
            # Calculate color distance for all pixels
            color_diff = np.sqrt(np.sum((image - target_color) ** 2, axis=2))
            
            # Add pixels within tolerance to mask
            color_mask = (color_diff <= self.COLOR_TOLERANCE)
            mask |= color_mask
            
            # Debug information
            if self.debug_color_detection:
                matched_count = np.sum(color_mask)
                matched_pixels_per_color.append(matched_count)
        
        # Log color detection results for debugging
        if self.debug_color_detection and any(matched_pixels_per_color):
            total_matched = np.sum(mask)
            logger.debug(f"Color matching: {total_matched} pixels matched dialogue colors")
            for i, count in enumerate(matched_pixels_per_color):
                if count > 0:
                    color = self.DIALOGUE_TEXT_COLORS[i]
                    logger.debug(f"  Color {color}: {count} pixels")
        
        return mask
    
    def is_dialogue_box_visible(self, screenshot: Image.Image) -> bool:
        """
        Check if a dialogue box is actually visible by looking for green horizontal border lines.
        Searches for the characteristic green lines above and below the dialogue text.
        
        Args:
            screenshot: PIL Image of the game screen
            
        Returns:
            True if dialogue box is detected, False otherwise
        """
        if not screenshot:
            return False
        
        try:
            # Convert to numpy array
            image_np = np.array(screenshot)
            if len(image_np.shape) != 3:
                return False
            
            # Extract extended dialogue region to catch border lines
            coords = self.DIALOGUE_BOX_COORDS
            # Extend the search area to catch top and bottom borders
            extended_region = image_np[
                max(0, coords['y'] - 5):min(image_np.shape[0], coords['y'] + coords['height'] + 5),
                coords['x']:coords['x'] + coords['width']
            ]
            
            if extended_region.size == 0:
                return False
            
            # Look for horizontal border lines using actual dialogue border colors
            border_colors = [
                (66, 181, 132),   # Main teal border color from debug analysis
                (24, 165, 107),   # Secondary border color  
                (57, 140, 49),    # Darker border variant
                (0, 255, 156),    # Bright border accent
                (115, 198, 165)   # Light border variant
            ]
            border_tolerance = 20  # Tolerance for color matching
            
            # Check each row for horizontal border lines
            border_line_rows = []
            height, width = extended_region.shape[:2]
            
            for row_idx in range(height):
                row_pixels = extended_region[row_idx]
                
                # Count border color pixels in this row
                border_pixels_in_row = 0
                for pixel in row_pixels:
                    # Check if pixel matches any of the border colors
                    for border_color in border_colors:
                        color_diff = np.sqrt(np.sum((pixel - np.array(border_color)) ** 2))
                        if color_diff <= border_tolerance:
                            border_pixels_in_row += 1
                            break  # Don't double-count pixels
                
                # If significant portion of row has border colors, it's likely a border line
                border_percentage = border_pixels_in_row / width
                if border_percentage > 0.2:  # 20% of row width has border colors (lower threshold)
                    border_line_rows.append(row_idx)
            
            # VERY strict detection to avoid false positives from environment colors
            
            # Require many border lines for robust detection
            has_sufficient_border_lines = len(border_line_rows) >= 5  # Need at least 5 border lines
            
            # MUST have top AND bottom border lines (no exceptions for false positive prevention)
            has_top_and_bottom_lines = False
            if len(border_line_rows) >= 3:
                # Check if we have lines at different heights (top and bottom)
                min_line = min(border_line_rows)
                max_line = max(border_line_rows)
                if max_line - min_line > 15:  # Lines must be at least 15 pixels apart (very strict)
                    has_top_and_bottom_lines = True
            
            # Additional check: look for proper dialogue box pattern (rectangular border)
            has_rectangular_pattern = False
            if len(border_line_rows) >= 5:
                # Check if we have border lines spread across the dialogue region
                height_quarter = height // 4
                top_lines = [r for r in border_line_rows if r < height_quarter]
                middle_lines = [r for r in border_line_rows if height_quarter <= r <= 3 * height_quarter]
                bottom_lines = [r for r in border_line_rows if r > 3 * height_quarter]
                
                # Must have lines in top AND bottom, and some in middle for a proper box
                if len(top_lines) >= 2 and len(bottom_lines) >= 2 and len(middle_lines) >= 1:
                    has_rectangular_pattern = True
            
            # Extra check: ensure lines are actually horizontal (consistent across width)
            has_proper_horizontal_lines = False
            if len(border_line_rows) >= 3:
                # Check that border lines extend across significant width (not just scattered pixels)
                proper_lines = 0
                for row_idx in border_line_rows[:10]:  # Check first 10 lines
                    row_pixels = extended_region[row_idx]
                    border_pixels_in_row = 0
                    for pixel in row_pixels:
                        for border_color in border_colors:
                            color_diff = np.sqrt(np.sum((pixel - np.array(border_color)) ** 2))
                            if color_diff <= border_tolerance:
                                border_pixels_in_row += 1
                                break
                    
                    # Line must span at least 50% of width to be considered a proper horizontal line
                    if border_pixels_in_row / width > 0.5:
                        proper_lines += 1
                
                if proper_lines >= 3:  # Need at least 3 proper horizontal lines
                    has_proper_horizontal_lines = True
            
            # Log detection results
            if self.debug_color_detection:
                logger.debug(f"Border line detection: Found {len(border_line_rows)} border horizontal lines")
                logger.debug(f"Line rows: {border_line_rows[:5]}")  # Show first 5
                logger.debug(f"Has sufficient lines (≥5): {has_sufficient_border_lines}")
                logger.debug(f"Has top+bottom lines (≥15px apart): {has_top_and_bottom_lines}")
                logger.debug(f"Has rectangular pattern: {has_rectangular_pattern}")
                logger.debug(f"Has proper horizontal lines (≥50% width): {has_proper_horizontal_lines}")
            
            # Final check: look for actual dialogue box background (light/white area inside borders)
            has_dialogue_background = False
            if len(border_line_rows) >= 3:
                # Check middle area for dialogue background colors (light colors)
                middle_start = height // 4
                middle_end = 3 * height // 4
                middle_region = extended_region[middle_start:middle_end, width//4:3*width//4]
                
                if middle_region.size > 0:
                    # Look for light background colors typical of dialogue boxes
                    light_pixels = 0
                    total_pixels = middle_region.size // 3  # Divide by 3 for RGB
                    
                    for pixel in middle_region.reshape(-1, 3):
                        # Light colors: high brightness (sum of RGB > 400) or white-ish
                        brightness = np.sum(pixel)
                        if brightness > 400 or (pixel[0] > 200 and pixel[1] > 200 and pixel[2] > 200):
                            light_pixels += 1
                    
                    light_percentage = light_pixels / total_pixels
                    if light_percentage > 0.3:  # At least 30% of middle area should be light (dialogue background)
                        has_dialogue_background = True
            
            # Log all criteria
            if self.debug_color_detection:
                logger.debug(f"Has dialogue background (light area): {has_dialogue_background}")
            
            # Use simplified detection method to avoid false positives
            # Check for white background in center area
            center_h = extended_region.shape[0] // 2
            center_w = extended_region.shape[1] // 2
            margin = 20
            
            center_area = extended_region[
                max(0, center_h - margin):min(extended_region.shape[0], center_h + margin),
                max(0, center_w - margin):min(extended_region.shape[1], center_w + margin)
            ]
            
            if center_area.size > 0:
                # Count white/light pixels (dialogue background)
                light_mask = (center_area[:,:,0] > 200) & (center_area[:,:,1] > 200) & (center_area[:,:,2] > 200)
                light_percentage = np.sum(light_mask) / light_mask.size
                
                # Count text-like colors (dark gray)
                text_mask = ((center_area[:,:,0] > 80) & (center_area[:,:,0] < 130) & 
                            (center_area[:,:,1] > 80) & (center_area[:,:,1] < 130) &
                            (center_area[:,:,2] > 80) & (center_area[:,:,2] < 130))
                text_percentage = np.sum(text_mask) / text_mask.size
                
                # Simple, robust criteria
                is_visible = light_percentage > 0.3 and text_percentage > 0.02
                
                if self.debug_color_detection:
                    logger.debug(f"Simplified detection - Light bg: {light_percentage:.1%}, Text: {text_percentage:.1%}")
            else:
                is_visible = False
            
            if self.debug_color_detection:
                logger.debug(f"Dialogue box {'VISIBLE' if is_visible else 'NOT VISIBLE'} "
                           f"(found {len(border_line_rows)} border lines)")
            
            return is_visible
            
        except Exception as e:
            logger.debug(f"Dialogue box detection error: {e}")
            return False
    
    def enable_color_debug(self, enabled: bool = True):
        """Enable/disable color detection debugging"""
        self.debug_color_detection = enabled
        if enabled:
            logger.info("OCR color detection debugging enabled")
        else:
            logger.info("OCR color detection debugging disabled")
    
    def analyze_dialogue_colors(self, screenshot: Image.Image) -> dict:
        """
        Analyze a screenshot to find the actual colors used in the dialogue box.
        This helps fine-tune the DIALOGUE_TEXT_COLORS list.
        """
        if not screenshot:
            return {}
        
        # Convert to numpy array
        image_np = np.array(screenshot)
        if len(image_np.shape) != 3:
            return {}
        
        # Extract dialogue region
        coords = self.DIALOGUE_BOX_COORDS
        dialogue_region = image_np[
            coords['y']:coords['y'] + coords['height'],
            coords['x']:coords['x'] + coords['width']
        ]
        
        if dialogue_region.size == 0:
            return {}
        
        # Find unique colors and their frequencies
        pixels = dialogue_region.reshape(-1, 3)
        unique_colors, counts = np.unique(pixels, axis=0, return_counts=True)
        
        # Sort by frequency (most common first)
        sorted_indices = np.argsort(counts)[::-1]
        
        # Analyze the most common colors
        color_analysis = {
            'total_pixels': len(pixels),
            'unique_colors': len(unique_colors),
            'top_colors': []
        }
        
        # Show top 20 most common colors
        for i in range(min(20, len(unique_colors))):
            idx = sorted_indices[i]
            color = tuple(unique_colors[idx])
            count = counts[idx]
            percentage = (count / len(pixels)) * 100
            
            color_analysis['top_colors'].append({
                'rgb': color,
                'count': int(count),
                'percentage': round(percentage, 2)
            })
        
        return color_analysis
    
    def print_color_analysis(self, screenshot: Image.Image):
        """Print color analysis in a readable format"""
        analysis = self.analyze_dialogue_colors(screenshot)
        
        if not analysis:
            print("❌ Could not analyze colors")
            return
        
        print(f"\n🎨 DIALOGUE COLOR ANALYSIS")
        print(f"={'='*50}")
        print(f"Total pixels: {analysis['total_pixels']:,}")
        print(f"Unique colors: {analysis['unique_colors']:,}")
        print(f"\nTop Colors (most frequent first):")
        print(f"{'Rank':<4} {'RGB Color':<20} {'Count':<8} {'%':<6} {'Color Type':<15}")
        print(f"{'-'*70}")
        
        for i, color_info in enumerate(analysis['top_colors'][:15], 1):
            rgb = color_info['rgb']
            count = color_info['count']
            pct = color_info['percentage']
            
            # Classify the color
            if rgb[0] > 240 and rgb[1] > 240 and rgb[2] > 240:
                color_type = "Background"
            elif rgb[0] < 120 and rgb[1] < 120 and rgb[2] < 120:
                color_type = "Text/Shadow"
            elif abs(rgb[0] - rgb[1]) < 10 and abs(rgb[1] - rgb[2]) < 10:
                color_type = "Gray text"
            else:
                color_type = "Other"
            
            print(f"{i:<4} {str(rgb):<20} {count:<8} {pct:<6.1f} {color_type:<15}")
        
        print(f"\n💡 Suggested dialogue colors to add:")
        suggested = []
        for color_info in analysis['top_colors'][:10]:
            rgb = color_info['rgb']
            # Suggest colors that look like text (not pure white background)
            if rgb[0] < 200 and color_info['percentage'] > 0.5:
                suggested.append(rgb)
        
        for color in suggested[:5]:  # Show top 5 suggestions
            print(f"    {color},")
        
        print(f"{'='*50}")
    
    def update_dialogue_colors_from_analysis(self, screenshot: Image.Image, threshold_percentage: float = 1.0):
        """
        Update DIALOGUE_TEXT_COLORS based on analysis of actual screenshot.
        Only adds colors that appear frequently enough (above threshold_percentage).
        """
        analysis = self.analyze_dialogue_colors(screenshot)
        
        if not analysis:
            logger.warning("Could not analyze colors to update dialogue colors")
            return
        
        # Find colors that appear frequently and look like text
        new_colors = []
        for color_info in analysis['top_colors']:
            rgb = color_info['rgb']
            pct = color_info['percentage']
            
            # Only consider colors that:
            # 1. Appear frequently enough
            # 2. Are not pure white (background)
            # 3. Are not already in our color list
            if (pct >= threshold_percentage and 
                not (rgb[0] > 240 and rgb[1] > 240 and rgb[2] > 240) and
                rgb not in self.DIALOGUE_TEXT_COLORS):
                new_colors.append(rgb)
        
        if new_colors:
            logger.info(f"Adding {len(new_colors)} new dialogue colors from analysis")
            for color in new_colors[:5]:  # Limit to top 5 new colors
                logger.info(f"  Added color: {color}")
            
            # Add new colors to the existing list
            self.DIALOGUE_TEXT_COLORS.extend(new_colors[:5])
        else:
            logger.info("No new dialogue colors found to add")
    
    def analyze_dialogue_box_background(self, screenshot: Image.Image):
        """
        Analyze dialogue box region to find actual background colors.
        Useful for fine-tuning DIALOGUE_BOX_BACKGROUND_COLORS.
        """
        analysis = self.analyze_dialogue_colors(screenshot)
        
        if not analysis:
            print("❌ Could not analyze dialogue box background")
            return
        
        print(f"\n📦 DIALOGUE BOX BACKGROUND ANALYSIS")
        print(f"{'='*50}")
        print(f"Total pixels: {analysis['total_pixels']:,}")
        print(f"Unique colors: {analysis['unique_colors']:,}")
        print(f"\nTop Background Colors (most frequent first):")
        print(f"{'Rank':<4} {'RGB Color':<20} {'Count':<8} {'%':<6} {'Type':<15}")
        print(f"{'-'*70}")
        
        for i, color_info in enumerate(analysis['top_colors'][:15], 1):
            rgb = color_info['rgb']
            count = color_info['count']
            pct = color_info['percentage']
            
            # Classify as likely background vs text
            if pct > 10:  # Very common = likely background
                color_type = "Background"
            elif rgb[0] < 150 and rgb[1] < 150 and rgb[2] < 150:
                color_type = "Text/Shadow"
            else:
                color_type = "Other"
            
            print(f"{i:<4} {str(rgb):<20} {count:<8} {pct:<6.1f} {color_type:<15}")
        
        print(f"\n💡 Suggested background colors (>5% pixels):")
        for color_info in analysis['top_colors'][:10]:
            rgb = color_info['rgb']
            pct = color_info['percentage']
            # Suggest colors that are common and not text-like
            if pct > 5.0 and not (rgb[0] < 150 and rgb[1] < 150 and rgb[2] < 150):
                print(f"    {rgb},")
        
        print(f"{'='*50}")
    
    def test_dialogue_box_detection(self, screenshot: Image.Image):
        """Test dialogue box detection with detailed output for green line method"""
        print(f"\n🔍 DIALOGUE BOX DETECTION TEST (Green Line Method)")
        print(f"{'='*50}")
        
        # Enable debug mode for detailed output
        old_debug = self.debug_color_detection
        self.debug_color_detection = True
        
        is_visible = self.is_dialogue_box_visible(screenshot)
        
        # Get detailed green line analysis
        image_np = np.array(screenshot)
        coords = self.DIALOGUE_BOX_COORDS
        
        # Extended region for border detection
        extended_region = image_np[
            max(0, coords['y'] - 5):min(image_np.shape[0], coords['y'] + coords['height'] + 5),
            coords['x']:coords['x'] + coords['width']
        ]
        
        height, width = extended_region.shape[:2]
        green_border_color = (85, 204, 128)
        green_tolerance = 15
        
        print(f"Search region: {coords['x']},{coords['y']-5} {coords['width']}x{height+10}")
        print(f"Green border color: {green_border_color}")
        print(f"Green tolerance: ±{green_tolerance}")
        
        # Analyze each row
        green_line_rows = []
        for row_idx in range(height):
            row_pixels = extended_region[row_idx]
            
            green_pixels_in_row = 0
            for pixel in row_pixels:
                color_diff = np.sqrt(np.sum((pixel - green_border_color) ** 2))
                if color_diff <= green_tolerance:
                    green_pixels_in_row += 1
            
            green_percentage = green_pixels_in_row / width
            if green_percentage > 0.3:  # 30% threshold
                green_line_rows.append({
                    'row': row_idx,
                    'green_pixels': green_pixels_in_row,
                    'percentage': green_percentage * 100
                })
        
        print(f"Found {len(green_line_rows)} green horizontal lines:")
        for line_info in green_line_rows[:5]:  # Show first 5
            row = line_info['row']
            pixels = line_info['green_pixels']
            pct = line_info['percentage']
            print(f"  Row {row}: {pixels}/{width} pixels ({pct:.1f}% green)")
        
        print(f"\nResult: {'✅ DIALOGUE BOX VISIBLE' if is_visible else '❌ NOT VISIBLE'}")
        print(f"{'='*50}")
        
        # Restore debug setting
        self.debug_color_detection = old_debug
        
        return is_visible
    
    def _validate_and_clean_text(self, text: str) -> Optional[str]:
        """Validate and clean detected text"""
        if not text or len(text.strip()) < 3:
            return None
            
        # Clean up common OCR errors
        text = re.sub(r'\n+', ' ', text)  # Replace newlines with spaces
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        text = text.strip()
        
        # Filter out obviously wrong detections
        if len(text) < 3 or len(text) > 200:
            return None
            
        # Check for minimum alphabetic content (avoid detecting UI elements)
        alpha_ratio = sum(c.isalpha() for c in text) / len(text)
        if alpha_ratio < 0.5:
            return None
        
        # Comprehensive random letter filtering - catch ANY nonsense patterns
        if self._is_random_nonsense(text):
            logger.debug(f"OCR validation: Rejected as random nonsense: '{text[:50]}...'")
            return None
            
        return text
    
    def _is_random_nonsense(self, text: str) -> bool:
        """
        Comprehensive detection of random letter sequences and nonsense text.
        Catches any type of random letters that don't form meaningful dialogue.
        """
        if not text or len(text.strip()) < 3:
            return True
        
        text_lower = text.lower().strip()
        words = text_lower.split()
        
        if len(words) == 0:
            return True
        
        # Pattern 1: Excessive single/double character "words"
        short_words = [w for w in words if len(w) <= 2]
        if len(short_words) > len(words) * 0.6:  # More than 60% are very short
            return True
        
        # Pattern 2: Repetitive patterns (like "a a a a a")
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        for word, count in word_counts.items():
            if len(word) <= 2 and count >= 3:  # Short word repeated 3+ times
                return True
        
        # Pattern 3: Too many words (dialogue is usually concise)
        if len(words) > 30:
            return True
        
        # Pattern 4: Check for valid English-like words
        valid_words = 0
        dialogue_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'you', 'i', 'we', 'they', 'he', 'she', 'it', 'this', 'that', 'these', 'those',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'can', 'may', 'might', 'must',
            'get', 'got', 'give', 'take', 'go', 'come', 'see', 'look', 'want', 'need', 'know', 'think',
            'pokemon', 'trainer', 'battle', 'items', 'store', 'pc', 'computer', 'use', 'hello', 'hi'
        }
        
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum()).lower()
            if len(clean_word) >= 2:
                # Check if it's a known good word
                if clean_word in dialogue_words:
                    valid_words += 1
                # Check if it has reasonable letter patterns
                elif self._has_valid_letter_pattern(clean_word):
                    valid_words += 1
        
        # Need at least 30% valid words
        valid_ratio = valid_words / len(words) if len(words) > 0 else 0
        if valid_ratio < 0.3:
            return True
        
        # Pattern 5: Detect excessive mixed case (OCR noise pattern)
        mixed_case_words = 0
        for word in words:
            if len(word) >= 3:
                has_lower = any(c.islower() for c in word)
                has_upper = any(c.isupper() for c in word)
                if has_lower and has_upper and not word[0].isupper():  # Not normal capitalization
                    mixed_case_words += 1
        
        if mixed_case_words > len(words) * 0.4:  # More than 40% have weird capitalization
            return True
        
        return False
    
    def _has_valid_letter_pattern(self, word: str) -> bool:
        """Check if word has valid English-like letter patterns"""
        if len(word) < 2:
            return False
        
        # Must have at least one vowel (unless very short)
        vowels = 'aeiou'
        has_vowel = any(c in vowels for c in word.lower())
        if len(word) >= 3 and not has_vowel:
            return False
        
        # Check for reasonable consonant clusters
        consonants = 'bcdfghjklmnpqrstvwxyz'
        consonant_streak = 0
        max_consonant_streak = 0
        
        for char in word.lower():
            if char in consonants:
                consonant_streak += 1
                max_consonant_streak = max(max_consonant_streak, consonant_streak)
            else:
                consonant_streak = 0
        
        # Too many consonants in a row suggests OCR noise
        if max_consonant_streak > 4:
            return False
        
        # Check for excessive repeated characters
        repeated = 0
        for i in range(len(word) - 1):
            if word[i] == word[i + 1]:
                repeated += 1
        
        if repeated > len(word) * 0.4:  # More than 40% repeated chars
            return False
        
        return True
    
    def get_stable_dialogue_text(self, screenshot: Image.Image) -> Optional[str]:
        """
        Get dialogue text that has been stable across multiple frames.
        This helps avoid detecting transitional/partial text.
        """
        current_text = self.detect_dialogue_from_screenshot(screenshot)
        
        if current_text == self.last_detected_text:
            self.stable_text_count += 1
        else:
            self.stable_text_count = 0
            self.last_detected_text = current_text
        
        # Return text only if it's been stable for threshold frames
        if self.stable_text_count >= self.text_stability_threshold and current_text:
            return current_text
            
        return None
    

def create_ocr_detector() -> Optional[OCRDialogueDetector]:
    """Factory function to create OCR detector if available"""
    if OCR_AVAILABLE:
        return OCRDialogueDetector()
    else:
        logger.warning("OCR not available - install pytesseract and tesseract-ocr system package")
        return None