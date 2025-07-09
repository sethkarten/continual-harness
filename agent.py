import httpx
import numpy as np
import base64
import io
import time
import logging
from collections import deque
from PIL import Image
from utils.vlm import VLM
from utils.state_formatter import format_state_summary, format_state_for_debug, get_party_health_summary
from utils.anticheat import AntiCheatTracker
from agent.perception import perception_step
from agent.memory import memory_step
from agent.planning import planning_step
from agent.action import action_step

# Set up main agent logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



SERVER_URL = "http://127.0.0.1:8000"

def base64_to_frame(base64_str):
    if not base64_str:
        return None
    image_data = base64.b64decode(base64_str)
    image = Image.open(io.BytesIO(image_data))
    return np.array(image)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Single-process Pokemon Emerald Agent (FastAPI mode)")
    parser.add_argument("--model-name", type=str, default="o4-mini", help="VLM model name")
    parser.add_argument("--backend", type=str, default="auto", 
                       choices=["auto", "openai", "openrouter", "local", "gemini", "ollama"],
                       help="VLM backend type (auto, openai, openrouter, local, gemini, ollama)")
    parser.add_argument("--vlm-port", type=int, default=11434, help="Port for VLM server (Ollama backend only)")
    parser.add_argument("--device", type=str, default="auto", help="Device for local models (auto, cpu, cuda)")
    parser.add_argument("--load-in-4bit", action="store_true", default=True, help="Use 4-bit quantization for local models")
    parser.add_argument("--debug-state", action="store_true", help="Enable detailed state debugging")
    args = parser.parse_args()

    logger.info("="*60)
    logger.info("STARTING POKEMON EMERALD AGENT")
    logger.info("="*60)
    logger.info(f"Using VLM model: {args.model_name}")
    logger.info(f"Backend: {args.backend}")
    if args.backend == "ollama":
        logger.info(f"Ollama port: {args.vlm_port}")
    elif args.backend == "local":
        logger.info(f"Device: {args.device}, 4-bit quantization: {args.load_in_4bit}")
    logger.info(f"Debug state logging: {args.debug_state}")
    logger.info("Make sure server/app.py is running first!")
    logger.info("Press Ctrl+C to stop")
    
    # Initialize anti-cheat tracker
    anticheat_tracker = AntiCheatTracker()
    anticheat_tracker.initialize_submission_log(args.model_name)

    # Initialize VLM with selected backend
    vlm_kwargs = {}
    if args.backend == "local":
        vlm_kwargs.update({
            "device": args.device,
            "load_in_4bit": args.load_in_4bit
        })
    
    vlm = VLM(
        model_name=args.model_name, 
        backend=args.backend, 
        port=args.vlm_port,
        **vlm_kwargs
    )
    memory_context = "Game just started. No observations yet."
    current_plan = None
    recent_actions = deque(maxlen=10)
    observation_buffer = []
    step = 0
    last_action = None
    slow_thinking_needed = True

    # Create httpx client for HTTP requests
    with httpx.Client(timeout=10.0) as client:
        while True:
            logger.info(f"\n{'='*20} STEP {step} {'='*20}")
            
            # Record start time for decision timing
            decision_start_time = time.time()
            
            # 1. Get comprehensive state from server
            try:
                resp = client.get(f"{SERVER_URL}/state")
                if resp.status_code != 200:
                    logger.error(f"Failed to get game state: HTTP {resp.status_code}")
                    time.sleep(1)
                    continue
                state_data = resp.json()
                
                # Create state hash for integrity verification
                state_hash = anticheat_tracker.create_state_hash(state_data)
                
                # Log state summary using utility
                state_summary = format_state_summary(state_data)
                logger.info(f"[AGENT-STEP-{step}] STATE: {state_summary}")
                logger.info(f"[AGENT-STEP-{step}] STATE_HASH: {state_hash}")
                
                # Log detailed debug info if requested
                if args.debug_state:
                    debug_info = format_state_for_debug(state_data)
                    logger.debug(f"[AGENT-STEP-{step}] DEBUG STATE:\n{debug_info}")
                
                # Extract frame from visual data
                frame = None
                if 'visual' in state_data and 'screenshot_base64' in state_data['visual']:
                    frame = base64_to_frame(state_data['visual']['screenshot_base64'])
                elif 'screenshot_base64' in state_data:  # Fallback compatibility
                    frame = base64_to_frame(state_data['screenshot_base64'])
                    
            except Exception as e:
                logger.error(f"Error getting game state: {e}")
                time.sleep(1)
                continue

            # 2. Perception with comprehensive state
            logger.info(f"[STEP-{step}] Starting PERCEPTION...")
            observation, slow_thinking = perception_step(frame, state_data, vlm)
            logger.info(f"[STEP-{step}] PERCEPTION COMPLETE")
            print(f"[{step}] Observation: {observation}")
            observation_buffer.append({"frame_id": step, "observation": observation, "state": state_data})

            # 3. Memory (update if slow thinking or buffer large)
            if slow_thinking or len(observation_buffer) > 5:
                logger.info(f"[STEP-{step}] Starting MEMORY UPDATE...")
                memory_context = memory_step(memory_context, current_plan, recent_actions, observation_buffer, vlm)
                logger.info(f"[STEP-{step}] MEMORY UPDATE COMPLETE")
                print(f"[{step}] Memory updated: {memory_context[:500]}..." if len(memory_context) > 500 else f"[{step}] Memory updated: {memory_context}")
                observation_buffer = []
                slow_thinking_needed = True
            else:
                slow_thinking_needed = False

            # 4. Planning with comprehensive state
            logger.info(f"[STEP-{step}] Starting PLANNING...")
            current_plan = planning_step(memory_context, current_plan, slow_thinking_needed, state_data, vlm)
            logger.info(f"[STEP-{step}] PLANNING COMPLETE")
            print(f"[{step}] Plan: {current_plan}")

            # 5. Action with comprehensive state
            logger.info(f"[STEP-{step}] Starting ACTION DECISION...")
            action = action_step(memory_context, current_plan, observation, frame, state_data, recent_actions, vlm)
            logger.info(f"[STEP-{step}] ACTION DECISION COMPLETE")
            print(f"[{step}] Action: {action}")
            
            # Calculate decision time
            decision_time = time.time() - decision_start_time
            
            # Log to submission file for anticheat verification
            anticheat_tracker.log_submission_data(step, state_data, action, decision_time, state_hash)
            
            # If action is not a list, make it a list for backward compatibility
            if not isinstance(action, list):
                actions_to_send = [action]
            else:
                actions_to_send = action
            for act in actions_to_send:
                recent_actions.append(act)
                try:
                    action_data = {"buttons": [act] if act else []}
                    resp = client.post(f"{SERVER_URL}/action", json=action_data)
                    
                    # Check if the request was successful
                    if resp.status_code == 200:
                        logger.info(f"[STEP-{step}] Action {act} sent successfully")
                        print(f"Action {act} sent successfully")
                    else:
                        logger.error(f"Failed to send action {act}. Status code: {resp.status_code}")
                        print(f"Failed to send action {act}. Status code: {resp.status_code}")
                        print(f"Response: {resp.text}")
                        
                except httpx.RequestError as e:
                    logger.error(f"Error sending action {act}: {e}")
                    print(f"Error sending action {act}: {e}")
                time.sleep(0.1)  # Small delay between actions

            step += 1
            logger.info(f"[STEP-{step-1}] STEP COMPLETE - Decision time: {decision_time:.3f}s\n")
            # time.sleep(0.5)  # Slow down for demo/debug

if __name__ == "__main__":
    main() 