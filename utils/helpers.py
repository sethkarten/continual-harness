import time
import base64
from io import BytesIO
import cv2
from PIL import Image

def frame_to_base64(frame):
    """Convert PIL Image frame to base64 encoded PNG"""
    if hasattr(frame, 'convert'):  # It's a PIL Image
        # Resize the PIL Image to 640x480
        resized_frame = frame.resize((640, 480), Image.Resampling.NEAREST)
        buffered = BytesIO()
        resized_frame.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    elif hasattr(frame, 'shape'):  # It's a numpy array
        # Convert numpy array to PIL Image first
        resized_frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_NEAREST)
        img = Image.fromarray(resized_frame)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    else:
        raise ValueError(f"Unsupported frame type: {type(frame)}")

def add_text_update(text, category=None, socket_queue=None, text_updates=None):
    """Add text to the text updates list with optional category"""
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    
    if category:
        formatted_text = f"[{timestamp}] [{category}]: {text}"
    else:
        formatted_text = f"[{timestamp}] [DEBUG]: {text}"
    
    if text_updates is not None:
        text_updates.append(formatted_text)
        # Keep only the last 100 updates
        if len(text_updates) > 100:
            text_updates.pop(0)
    
    print(formatted_text)
    
    # Emit update via WebSocket
    if socket_queue is not None:
        socket_queue.put(('text_update', {'text': formatted_text}))
