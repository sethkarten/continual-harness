import copy
import logging
import time
import httpx
import numpy as np
from PIL import Image

from utils.vlm import VLM
from utils.state_formatter import format_state_summary
from utils.anticheat import AntiCheatTracker
from utils.llm_logger import get_llm_logger

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

SERVER_URL = "http://127.0.0.1:8000"

def base64_to_frame(base64_str):
    """Convert base64 string to numpy array frame."""
    if not base64_str:
        return None
    import base64
    import io
    image_data = base64.b64decode(base64_str)
    image = Image.open(io.BytesIO(image_data))
    return np.array(image)

SYSTEM_PROMPT = """You are playing Pokemon Emerald. You can see the game screen and control the game by executing emulator commands.

Your goal is to play through Pokemon Emerald and eventually defeat the Elite Four. Make decisions based on what you see on the screen.

Before each action, explain your reasoning briefly, then use the emulator tool to execute your chosen commands.

The conversation history may occasionally be summarized to save context space. If you see a message labeled "CONVERSATION HISTORY SUMMARY", this contains the key information about your progress so far. Use this information to maintain continuity in your gameplay."""

SUMMARY_PROMPT = """I need you to create a detailed summary of our conversation history up to this point. This summary will replace the full conversation history to manage the context window.

Please include:
1. Key game events and milestones you've reached
2. Important decisions you've made
3. Current objectives or goals you're working toward
4. Your current location and Pokémon team status
5. Any strategies or plans you've mentioned

The summary should be comprehensive enough that you can continue gameplay without losing important context about what has happened so far."""


class HersheyVLMAgent:
    def __init__(self, model_name="o4-mini", backend="auto", max_history=60, load_state=None, **vlm_kwargs):
        """Initialize the Hershey VLM agent.

        Args:
            model_name: VLM model name
            backend: VLM backend type (auto, openai, openrouter, local, gemini, ollama)
            max_history: Maximum number of messages in history before summarization
            load_state: State file to load
            **vlm_kwargs: Additional VLM initialization parameters
        """
        self.vlm = VLM(model_name=model_name, backend=backend, **vlm_kwargs)
        self.running = True
        self.message_history = [{"role": "user", "content": "You may now begin playing."}]
        self.max_history = max_history
        
        # Initialize anti-cheat tracker
        self.anticheat_tracker = AntiCheatTracker()
        self.anticheat_tracker.initialize_submission_log(model_name)
        
        # Initialize LLM logger
        self.llm_logger = get_llm_logger()
        
        # Load state if specified
        if load_state:
            logger.info(f"Loading saved state from {load_state}")
            self.load_state(load_state)

    def run(self, num_steps=1):
        """Main agent loop.

        Args:
            num_steps: Number of steps to run for
        """
        logger.info(f"Starting Hershey VLM agent loop for {num_steps} steps")

        steps_completed = 0
        while self.running and steps_completed < num_steps:
            try:
                # Record start time for decision timing
                decision_start_time = time.time()
                
                # Get current game state using existing pattern from agent.py
                try:
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.get(f"{SERVER_URL}/state")
                        if resp.status_code != 200:
                            logger.error(f"Failed to get game state: HTTP {resp.status_code}")
                            time.sleep(1)
                            continue
                        state_data = resp.json()
                        
                        # Create state hash for integrity verification
                        state_hash = self.anticheat_tracker.create_state_hash(state_data)
                        
                        # Log state snapshot
                        self.llm_logger.log_state_snapshot(state_data, steps_completed)
                        
                        # Log state summary using existing utility
                        state_summary = format_state_summary(state_data)
                        logger.info(f"[AGENT-STEP-{steps_completed}] STATE: {state_summary}")
                        logger.info(f"[AGENT-STEP-{steps_completed}] STATE_HASH: {state_hash}")
                        
                except Exception as e:
                    logger.error(f"Error getting game state: {e}")
                    time.sleep(1)
                    continue

                # Get current screenshot using existing pattern from agent.py
                frame = None
                if 'visual' in state_data and 'screenshot_base64' in state_data['visual']:
                    frame = base64_to_frame(state_data['visual']['screenshot_base64'])
                elif 'screenshot_base64' in state_data:  # Fallback compatibility
                    frame = base64_to_frame(state_data['screenshot_base64'])

                # Create the prompt for VLM
                state_context = f"""
                Current Game State:
                {state_summary}
                
                Available Actions:
                - Press Game Boy Advance buttons: A, B, START, SELECT, UP, DOWN, LEFT, RIGHT, L, R
                
                Current screenshot is available for visual analysis.
                """

                try:
                    if frame is not None:
                        # Use visual query with image
                        prompt = f"{SYSTEM_PROMPT}\n\n{state_context}\n\nBased on the current game state and visual information, what should you do next? Explain your reasoning and then execute the appropriate action."
                        response = self.vlm.get_query(frame, prompt, "HERSHEY_VLM_AGENT")
                    else:
                        # Use text-only query
                        prompt = f"{SYSTEM_PROMPT}\n\n{state_context}\n\nBased on the current game state, what should you do next? Explain your reasoning and then execute the appropriate action."
                        response = self.vlm.get_text_query(prompt, "HERSHEY_VLM_AGENT")
                except Exception as e:
                    logger.error(f"Error getting VLM response: {e}")
                    response = "I encountered an error processing the game state. I'll proceed with a basic action: press 'A' to continue."

                # Parse the response to extract reasoning and actions
                # Look for specific action patterns in the response
                valid_buttons = ['A', 'B', 'START', 'SELECT', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'L', 'R']
                buttons_to_press = []
                
                # Look for specific action patterns
                response_upper = response.upper()
                
                # Common action patterns to look for
                action_patterns = [
                    'PRESS A', 'PRESS B', 'PRESS START', 'PRESS SELECT',
                    'PRESS UP', 'PRESS DOWN', 'PRESS LEFT', 'PRESS RIGHT',
                    'PRESS L', 'PRESS R',
                    'ACTION: A', 'ACTION: B', 'ACTION: START', 'ACTION: SELECT',
                    'ACTION: UP', 'ACTION: DOWN', 'ACTION: LEFT', 'ACTION: RIGHT',
                    'ACTION: L', 'ACTION: R',
                    'BUTTON: A', 'BUTTON: B', 'BUTTON: START', 'BUTTON: SELECT',
                    'BUTTON: UP', 'BUTTON: DOWN', 'BUTTON: LEFT', 'BUTTON: RIGHT',
                    'BUTTON: L', 'BUTTON: R',
                    '> A', '> B', '> START', '> SELECT',
                    '> UP', '> DOWN', '> LEFT', '> RIGHT',
                    '> L', '> R'
                ]
                
                # First try to find specific action patterns
                for pattern in action_patterns:
                    if pattern in response_upper:
                        # Extract the button from the pattern
                        button = pattern.split()[-1]  # Get the last word (the button)
                        if button in valid_buttons:
                            buttons_to_press = [button]
                            break
                
                # If no specific pattern found, look for the most likely action
                if not buttons_to_press:
                    # Look for button names in context of action words
                    action_words = ['PRESS', 'ACTION', 'BUTTON', 'MOVE', 'GO', 'USE']
                    for word in action_words:
                        for button in valid_buttons:
                            if f'{word} {button}' in response_upper:
                                buttons_to_press = [button]
                                break
                        if buttons_to_press:
                            break
                
                # If still no action found, look for the first button mentioned in reasoning
                if not buttons_to_press:
                    # Split response into sentences and look for button mentions
                    sentences = response_upper.split('.')
                    for sentence in sentences:
                        for button in valid_buttons:
                            if button in sentence and any(word in sentence for word in ['PRESS', 'ACTION', 'BUTTON', 'MOVE', 'GO', 'USE']):
                                buttons_to_press = [button]
                                break
                        if buttons_to_press:
                            break
                
                # If no buttons found, default to 'A'
                if not buttons_to_press:
                    buttons_to_press = ['A']

                # Add assistant message to history
                assistant_content = [
                    {"type": "text", "text": response}
                ]
                
                self.message_history.append(
                    {"role": "assistant", "content": assistant_content}
                )
                
                # Execute the action using existing pattern from agent.py
                try:
                    with httpx.Client(timeout=10.0) as client:
                        action_data = {"buttons": buttons_to_press}
                        resp = client.post(f"{SERVER_URL}/action", json=action_data)
                        
                        if resp.status_code == 200:
                            logger.info(f"[STEP-{steps_completed}] Action {buttons_to_press} sent successfully")
                        else:
                            logger.error(f"Failed to send action. Status code: {resp.status_code}")
                except Exception as e:
                    logger.error(f"Error sending action: {e}")

                # Calculate decision time
                decision_time = time.time() - decision_start_time
                
                # Log to submission file for anticheat verification
                self.anticheat_tracker.log_submission_data(steps_completed, state_data, buttons_to_press, decision_time, state_hash)
                
                # Log the action
                action_str = ', '.join(buttons_to_press)
                self.llm_logger.log_action(action_str, steps_completed, f"Based on reasoning: {response}")
                
                # Add tool result to message history
                tool_result_content = [
                    {"type": "text", "text": f"Executed actions: {', '.join(buttons_to_press)}"},
                    {"type": "text", "text": f"Reasoning: {response}"}
                ]
                
                self.message_history.append(
                    {"role": "user", "content": tool_result_content}
                )

                # Check if we need to summarize the history
                if len(self.message_history) >= self.max_history:
                    self.summarize_history()

                # Update server's agent step count using existing pattern from agent.py
                try:
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(f"{SERVER_URL}/agent_step")
                        if resp.status_code == 200:
                            logger.info(f"[STEP-{steps_completed}] Agent step count updated on server")
                        else:
                            logger.warning(f"Failed to update agent step count. Status: {resp.status_code}")
                except Exception as e:
                    logger.warning(f"Error updating agent step count: {e}")

                steps_completed += 1
                logger.info(f"Completed step {steps_completed}/{num_steps}")
                
                # Log step completion
                self.llm_logger.log_step_end(steps_completed-1, "hershey_vlm_agent", decision_time, f"Action: {buttons_to_press}, Reasoning: {response}")

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, stopping")
                self.running = False
            except Exception as e:
                logger.error(f"Error in agent loop: {e}")
                raise e

        return steps_completed

    def summarize_history(self):
        """Generate a summary of the conversation history and replace the history with just the summary."""
        logger.info(f"[Agent] Generating conversation summary...")
        
        # Get current state for the summary
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{SERVER_URL}/state")
                if resp.status_code == 200:
                    state_data = resp.json()
                    state_summary = format_state_summary(state_data)
                else:
                    state_summary = "Unable to get current state"
        except Exception as e:
            logger.error(f"Error getting state for summary: {e}")
            state_summary = "Unable to get current state"

        # Get summary from VLM
        summary_prompt = f"{SYSTEM_PROMPT}\n\n{SUMMARY_PROMPT}"
        summary_text = self.vlm.get_text_query(summary_prompt, "HERSHEY_VLM_SUMMARY")
        
        logger.info(f"[Agent] Game Progress Summary:")
        logger.info(f"{summary_text}")
        
        # Replace message history with just the summary
        self.message_history = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"CONVERSATION HISTORY SUMMARY (representing {self.max_history} previous messages): {summary_text}"
                    },
                    {
                        "type": "text",
                        "text": f"\n\nCurrent game state: {state_summary}"
                    },
                    {
                        "type": "text",
                        "text": "You were just asked to summarize your playthrough so far, which is the summary you see above. You may now continue playing by selecting your next action."
                    },
                ]
            }
        ]
        
        logger.info(f"[Agent] Message history condensed into summary.")

    def load_state(self, filename):
        """Load a saved state."""
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(f"{SERVER_URL}/load_state", params={"filename": filename})
                if resp.status_code == 200:
                    logger.info(f"Successfully loaded state from {filename}")
                else:
                    logger.error(f"Failed to load state: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error loading state: {e}")

    def stop(self):
        """Stop the agent."""
        self.running = False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hershey VLM Agent for Pokemon Emerald")
    parser.add_argument("--model-name", type=str, default="o4-mini", help="VLM model name")
    parser.add_argument("--backend", type=str, default="auto", 
                       choices=["auto", "openai", "openrouter", "local", "gemini", "ollama"],
                       help="VLM backend type (auto, openai, openrouter, local, gemini, ollama)")
    parser.add_argument("--vlm-port", type=int, default=11434, help="Port for VLM server (Ollama backend only)")
    parser.add_argument("--device", type=str, default="auto", help="Device for local models (auto, cpu, cuda)")
    parser.add_argument("--load-in-4bit", action="store_true", default=True, help="Use 4-bit quantization for local models")
    parser.add_argument("--max-history", type=int, default=60, help="Maximum message history before summarization")
    parser.add_argument("--load-state", type=str, help="State file to load")
    parser.add_argument("--steps", type=int, default=1000, help="Number of steps to run")
    args = parser.parse_args()

    logger.info("="*60)
    logger.info("STARTING HERSHEY VLM AGENT")
    logger.info("="*60)
    logger.info(f"Using VLM model: {args.model_name}")
    logger.info(f"Backend: {args.backend}")
    if args.backend == "ollama":
        logger.info(f"Ollama port: {args.vlm_port}")
    elif args.backend == "local":
        logger.info(f"Device: {args.device}, 4-bit quantization: {args.load_in_4bit}")
    logger.info(f"Max history: {args.max_history}")
    logger.info(f"Steps to run: {args.steps}")
    logger.info("Make sure server/app.py is running first!")
    logger.info("Press Ctrl+C to stop")
    
    # Initialize VLM with selected backend using existing pattern from agent.py
    vlm_kwargs = {}
    if args.backend == "local":
        vlm_kwargs.update({
            "device": args.device,
            "load_in_4bit": args.load_in_4bit
        })
    elif args.backend == "ollama":
        vlm_kwargs.update({
            "port": args.vlm_port
        })
    
    # Create and run agent
    agent = HersheyVLMAgent(
        model_name=args.model_name,
        backend=args.backend,
        max_history=args.max_history,
        load_state=args.load_state,
        **vlm_kwargs
    )

    try:
        steps_completed = agent.run(num_steps=args.steps)
        logger.info(f"Agent completed {steps_completed} steps")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, stopping")
    finally:
        agent.stop()


if __name__ == "__main__":
    main() 