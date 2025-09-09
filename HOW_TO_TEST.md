# How to Test Agent Direct Web Interface

## Quick Test

Run the compatibility test:
```bash
python test_stream_compatibility.py
```

This verifies that all streaming endpoints work and are compatible with server/stream.html.

## Full Integration Test

### 1. Start Agent Direct
```bash
conda activate mgba
python agent_direct.py --agent-auto --backend gemini --model-name gemini-2.5-flash
```

### 2. Open Web Interface
Open your browser to: `http://localhost:8000` (default port)

Or for custom port: `http://localhost:8080` if you used `--port 8080`

**Both paths work:**
- `http://localhost:8000/` (main interface)
- `http://localhost:8000/server/stream.html` (compatibility path)

### 3. Verify Features

**Visual Stream:**
- [ ] Screenshot updates smoothly (30 FPS)
- [ ] Game responds to agent actions
- [ ] No lag or freezing

**Agent Data:**
- [ ] Agent status shows "thinking" when processing
- [ ] Last observation shows current game state analysis
- [ ] Last plan shows strategic thinking
- [ ] Last action shows button press and reasoning
- [ ] Step counter increments with each action

**Party Information:**
- [ ] Pokemon data shows correctly (name, HP, level, status)
- [ ] Healthy count shows 1/1 for healthy Torchic
- [ ] Status shows "OK" for healthy Pokemon

**Controls:**
- [ ] Press `M` to toggle Manual/Agent mode
- [ ] Press `O` to toggle Agent Auto on/off
- [ ] Press `SPACE` for manual agent step (when auto off)
- [ ] Arrow keys work in Manual mode

**WebSocket Data (Check Browser Dev Console):**
- [ ] Messages arrive at ~30 FPS
- [ ] Each message contains screenshot, player, game, party, agent data
- [ ] Agent observations and plans are visible in messages

### 4. Advanced Test - Agent Performance

Let the agent run for 2-3 minutes and verify:
- [ ] Button presses are spaced properly (not too fast/slow)
- [ ] Agent makes logical decisions
- [ ] No crashes or errors
- [ ] Memory usage stays reasonable

## Troubleshooting

**No WebSocket Messages:**
- Check browser console for connection errors
- Verify agent_direct is running on correct port
- Try refreshing the page

**Poor Performance:**
- Check terminal for error messages
- Ensure GPU/VRAM is sufficient for chosen model
- Try simpler model like gemini-2.5-flash

**Button Timing Issues:**
- Button presses should be 100ms hold + 250ms delay
- Check terminal output for button press logs
- Verify no "missed input" behavior in game

## Expected Results

✅ **Working correctly:**
- Smooth 30 FPS video stream
- Agent makes decisions every 2-3 seconds
- Complete data in WebSocket messages
- Responsive web interface controls

❌ **Needs fixing if:**
- Video is choppy or frozen
- Missing data fields in broadcasts
- Agent actions don't register in game
- Interface controls don't work