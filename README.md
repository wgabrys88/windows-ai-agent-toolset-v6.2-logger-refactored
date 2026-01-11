# README.md

## SYSTEM OVERVIEW

Autonomous Windows Desktop AI Agent with Vision and GUI Control. The system enables a multimodal LLM (Qwen3-VL) to observe screen state via screenshots and execute desktop automation tasks through tool-based function calling. Operates as a perceive-think-act loop with normalized coordinate system for cross-resolution compatibility.

## ARCHITECTURE

```
main.py
  |
  +-> agent.py (run_agent loop)
        |
        +-> scenarios.py (tool execution & task definitions)
        |     |
        |     +-> winapi.py (Windows API bindings)
        |
        +-> utils.py (HTTP, parsing, logging, message hygiene)
```

## COMPONENT ANALYSIS

### main.py
**Role:** Entry point and orchestrator.

**Responsibilities:**
- Parse command-line arguments (scenario selection)
- Initialize DPI awareness via winapi
- Load configuration from environment variables with defaults
- Create dump directory for screenshots
- Initialize HTTP exchange logger
- Invoke agent loop with selected scenario
- Handle top-level exceptions and logging

**Key Configuration:**
- LM Studio endpoint: `LMSTUDIO_ENDPOINT` (default: localhost:1234)
- Model: `LMSTUDIO_MODEL` (default: qwen3-vl-8b-instruct)
- Timeout: `LMSTUDIO_TIMEOUT` (default: 240s)
- Temperature: `LMSTUDIO_TEMPERATURE` (default: 0.6)
- Max tokens: `LMSTUDIO_MAX_TOKENS` (default: 2048)
- Image dimensions: `AGENT_IMAGE_W/H` (default: 1536x864)
- Screenshot retention: `AGENT_KEEP_LAST_SCREENSHOTS` (default: 2)
- Think tag retention: `AGENT_KEEP_LAST_THINKS` (default: 2)
- Max steps per task: `AGENT_MAX_STEPS` (default: 10)
- Step delay: `AGENT_STEP_DELAY` (default: 0.4s)

**Dependencies:** scenarios, utils, winapi, agent

---

### agent.py
**Role:** Core agent execution loop implementing perceive-think-act cycle.

**Algorithm:**
1. Initialize conversation with system prompt and task prompt
2. Capture initial screenshot via `observe_screen` tool
3. Enter loop (max_steps iterations):
   - Send messages + tools schema to LLM endpoint
   - Receive assistant message (with optional tool calls)
   - Prune old think tags from conversation history
   - If no tool calls: return final response
   - Enforce single tool call per step (reject extras)
   - Execute tool via scenarios.execute_tool()
   - Append tool response and optional user message (screenshots)
   - Prune old screenshots from conversation history
   - Sleep (step_delay)
4. Return stripped response (without think tags)

**Key Features:**
- Tool call rate limiting (1 per step prevents model spam)
- Conversation memory management (screenshot + think tag pruning)
- Separation of tool response (role=tool) and observation data (role=user with image)

**Dependencies:** scenarios, utils, time, json

---

### scenarios.py
**Role:** Tool execution engine and task definition repository.

**Tool Catalog:**
1. **observe_screen** - Capture screenshot, return as base64 PNG in user message
2. **click_element** - Click UI element using normalized coordinates (0-1000)
3. **type_text** - Type ASCII text into focused input field
4. **press_key** - Press keyboard key or combination (enter, tab, ctrl+c, etc.)
5. **scroll_at_position** - Scroll down at specified position

**Coordinate System:**
- Normalized 0-1000 range (x: 0=left, 1000=right; y: 0=top, 1000=bottom)
- Three accepted box formats:
  - Point: `[x, y]` (preferred for small targets)
  - Flat bbox: `[x1, y1, x2, y2]`
  - Legacy bbox: `[[x1, y1], [x2, y2]]`

**Tool Execution Flow:**
- Parse tool arguments (JSON string or dict)
- Validate inputs (label, box, text, key)
- Convert normalized coordinates to screen pixels via winapi
- Execute Windows API calls (mouse move, click, keyboard input)
- Add delays for UI responsiveness (80-120ms)
- Return JSON response: `{ok: true, ...}` or `{ok: false, error: {...}}`

**State Management:**
- Global `_screen_dimensions` dict tracks actual screen resolution
- Updated on each `observe_screen` call
- Used for coordinate translation in all action tools

**System Prompt:**
Defines agent capabilities, coordinate system, operating protocol (observe -> think -> act -> verify), and rules (one action per step, always verify actions).

**Scenarios:**
Predefined tasks with name and task_prompt. Current scenarios:
1. Grok AI conversation (never-ending investigation loop)
2. Open Windows Start Menu (with verification)
3. Open Start Menu + Notepad++ + document actions

**Dependencies:** utils, winapi, base64, os, time

---

### winapi.py
**Role:** Low-level Windows API bindings for screen capture and input simulation.

**API Coverage:**

**Display Management:**
- `init_dpi()` - Set DPI awareness context (per-monitor v2)
- `get_screen_size()` - Query primary monitor dimensions
- `norm_to_screen_px(xn, yn, w, h)` - Convert 0-1000 coords to pixels

**Screen Capture:**
- `capture_screenshot_png(target_w, target_h)` - Capture, scale, encode PNG
  - Uses GDI32 CreateDIBSection for direct pixel buffer access
  - StretchBlt with HALFTONE mode for high-quality scaling
  - Draws cursor overlay with hotspot alignment
  - BGRA to RGB conversion
  - Manual PNG encoding (IHDR + IDAT + IEND chunks, zlib compression)
  - Returns: (png_bytes, screen_w, screen_h)

**Mouse Control:**
- `move_mouse_to_pixel(x, y)` - Set cursor position
- `click_mouse()` - Left button down + up via SendInput
- `scroll_down(amount)` - Mouse wheel event (default 120 units)

**Keyboard Control:**
- `type_text(text)` - Unicode keyboard input via KEYEVENTF_UNICODE
- `press_key(key)` - Virtual key codes for special keys and combinations
  - Supported: enter, tab, escape, windows, ctrl, alt, shift, F4, letters
  - Combination format: "ctrl+c", "alt+f4", etc.

**Implementation Details:**
- ctypes-based bindings (user32.dll, gdi32.dll)
- Defensive wintypes attribute handling for incomplete Python builds
- Structure definitions: POINT, CURSORINFO, ICONINFO, BITMAPINFOHEADER, INPUT unions
- Error handling via return code checks and RuntimeError exceptions

**Dependencies:** ctypes, struct, time, zlib

---

### utils.py
**Role:** Shared utilities for HTTP communication, parsing, logging, and message hygiene.

**HTTP Logging:**
- `init_http_logger(log_file)` - Create dedicated logger for request/response pairs
- `post_json(payload, endpoint, timeout)` - POST JSON with logging
  - Logs sanitized request (truncates base64 images, tools schema, prompts)
  - Logs full response
  - Returns parsed JSON response dict

**JSON Helpers:**
- `ok_payload(extra)` - Success response: `{ok: true, ...}`
- `err_payload(error_type, message)` - Error response: `{ok: false, error: {...}}`
- `parse_args(arg_str)` - Parse tool arguments (dict, JSON string, or None)

**Box Parsing:**
- `parse_box(box)` - Unified parser for three coordinate formats
  - Point `[x, y]` -> `(x, y, x, y)` (zero-area bbox)
  - Flat `[x1, y1, x2, y2]` -> `(x1, y1, x2, y2)`
  - Legacy `[[x1, y1], [x2, y2]]` -> `(x1, y1, x2, y2)`
  - Clamps to 0-1000 range, swaps inverted coordinates
- `box_center(x1, y1, x2, y2)` - Compute center point

**Message Hygiene:**
- `strip_think(text)` - Remove `<think>...</think>` tags from final output
- `prune_old_screenshots(messages, keep_last)` - Remove old image_url content, keep N recent
- `prune_old_thinks(messages, keep_last)` - Strip think tags from old assistant messages
- Prevents conversation context overflow and token budget exhaustion

**Image Data Truncation (for logs):**
- `summarize_data_image_url(url)` - Replace base64 payload with SHA256 hash + length
- `truncate_base64_images(obj)` - Recursively sanitize data URLs in nested structures

**Environment Helpers:**
- `get_env_str(name, default)` - String variable with fallback
- `get_env_int(name, default)` - Integer variable with fallback
- `get_env_float(name, default)` - Float variable with fallback

**Dependencies:** hashlib, json, logging, re, urllib.request, pathlib

---

## DATA FLOW

### Initialization Sequence
```
main.py
  -> winapi.init_dpi()
  -> utils.init_http_logger()
  -> agent.run_agent()
       -> scenarios.execute_tool("observe_screen")
            -> winapi.capture_screenshot_png()
            -> save to dumps/screen_NNNN.png
            -> return (tool_msg, user_msg_with_image)
```

### Agent Loop Iteration
```
agent.run_agent()
  -> utils.post_json(messages + tools_schema)
       -> HTTP POST to LM Studio endpoint
       -> log request (sanitized) and response
  -> receive assistant message (text + tool_calls)
  -> utils.prune_old_thinks()
  -> if tool_calls:
       -> scenarios.execute_tool(name, args, call_id)
            -> utils.parse_args()
            -> if click_element:
                 -> utils.parse_box()
                 -> winapi.norm_to_screen_px()
                 -> winapi.move_mouse_to_pixel()
                 -> winapi.click_mouse()
            -> if type_text:
                 -> winapi.type_text()
            -> if press_key:
                 -> winapi.press_key()
            -> if scroll_at_position:
                 -> winapi.norm_to_screen_px()
                 -> winapi.move_mouse_to_pixel()
                 -> winapi.scroll_down()
            -> if observe_screen:
                 -> winapi.capture_screenshot_png()
                 -> save PNG + return user_msg with base64
       -> append tool response
       -> utils.prune_old_screenshots()
       -> sleep(step_delay)
  -> else: return strip_think(last_content)
```

### Coordinate Translation Pipeline
```
LLM outputs normalized coords [0-1000]
  -> scenarios.execute_tool()
       -> utils.parse_box() [validate + clamp]
       -> utils.box_center() [compute center]
       -> winapi.norm_to_screen_px(cx, cy, screen_w, screen_h)
            -> x_pixel = (cx / 1000.0) * (screen_w - 1)
            -> y_pixel = (cy / 1000.0) * (screen_h - 1)
       -> winapi.move_mouse_to_pixel(x_pixel, y_pixel)
            -> user32.SetCursorPos()
```

---

## INTER-COMPONENT RELATIONSHIPS

### Dependency Graph
```
main.py
  |-> agent.py
  |     |-> scenarios.py
  |     |     |-> utils.py (parse_args, parse_box, ok_payload, err_payload)
  |     |     |-> winapi.py (all I/O functions)
  |     |-> utils.py (post_json, prune_*, strip_think)
  |-> utils.py (get_env_*, init_http_logger)
  |-> winapi.py (init_dpi)
  |-> scenarios.py (SYSTEM_PROMPT, TOOLS_SCHEMA, SCENARIOS)
```

### Communication Patterns

**Agent <-> LLM:**
- Protocol: OpenAI-compatible chat completions API
- Request: `{model, messages, tools, tool_choice, temperature, max_tokens}`
- Response: `{choices: [{message: {role, content, tool_calls}}]}`
- Transport: HTTP POST via utils.post_json()

**Agent <-> Scenarios:**
- Interface: `execute_tool(name, arg_str, call_id, dump_cfg) -> (tool_msg, user_msg)`
- tool_msg: JSON response from tool execution (role=tool)
- user_msg: Optional multimodal message with screenshot (role=user)

**Scenarios <-> WinAPI:**
- Interface: Direct function calls (no error codes, raises RuntimeError on failure)
- Input: Pixel coordinates, text strings, key names
- Output: PNG bytes, screen dimensions, void

**Utils <-> All Components:**
- Shared utility layer (no state, pure functions)
- Logging side effects isolated to _http_logger global

---

## TECHNICAL SPECIFICATIONS

### Coordinate System
- **Normalized Range:** 0-1000 (x and y axes)
- **Rationale:** Resolution-independent, integer-friendly, intuitive scale
- **Translation Formula:** `pixel = (normalized / 1000.0) * (dimension - 1)`
- **Clamping:** All inputs clamped to [0, 1000] before translation

### Screenshot Pipeline
- **Capture Method:** GDI32 BitBlt (screen DC -> memory DC)
- **Scaling:** StretchBlt with HALFTONE mode (high quality)
- **Color Format:** BGRA32 (Windows native) -> RGB24 (PNG)
- **Encoding:** Manual PNG construction (no PIL dependency)
  - Chunk sequence: IHDR (image header) -> IDAT (compressed pixel data) -> IEND
  - Compression: zlib level 6
- **Cursor Overlay:** DrawIconEx with hotspot offset correction
- **Default Resolution:** 1536x864 (target dimensions)

### Input Simulation
- **Method:** SendInput API (hardware-independent, respects UIPI)
- **Mouse:** MOUSEINPUT structures with LEFTDOWN/LEFTUP/WHEEL flags
- **Keyboard:** 
  - Text: KEYEVENTF_UNICODE (UTF-16 code points)
  - Keys: Virtual key codes (VK_*) with down/up events
- **Timing:** 5ms delay between key events, 80-120ms after actions

### Conversation Management
- **Screenshot Retention:** Keep last N images, replace older with placeholder text
- **Think Tag Retention:** Keep last N assistant messages with tags, strip from older
- **Pruning Triggers:** After each tool response (screenshots), after each LLM response (thinks)
- **Memory Optimization:** Prevents token budget overflow in long-running tasks

### Error Handling
- **Tool Errors:** JSON error payloads with type + message
  - Types: missing_label, missing_box, invalid_box, invalid_args, invalid_json, empty_text, missing_key, invalid_key, unknown_tool, too_many_tool_calls
- **WinAPI Errors:** RuntimeError exceptions with descriptive messages
- **HTTP Errors:** Propagated urllib exceptions (timeout, connection errors)
- **Agent Loop:** Max steps limit prevents infinite loops

### Logging
- **HTTP Exchange Log:** Timestamped file (agent_run_YYYYMMDD_HHMMSS.log)
- **Log Contents:**
  - Sanitized requests (tools/prompts truncated, images summarized)
  - Full responses (including tool calls and content)
  - Clean JSON formatting (no empty/brace-only lines)
- **Screenshot Dump:** Sequential PNGs (screen_0001.png, screen_0002.png, ...)

---

## CONFIGURATION

### Environment Variables
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| LMSTUDIO_ENDPOINT | str | http://localhost:1234/v1/chat/completions | LLM API endpoint |
| LMSTUDIO_MODEL | str | qwen3-vl-8b-instruct | Model identifier |
| LMSTUDIO_TIMEOUT | int | 240 | HTTP timeout (seconds) |
| LMSTUDIO_TEMPERATURE | float | 0.6 | Sampling temperature |
| LMSTUDIO_MAX_TOKENS | int | 2048 | Max completion tokens |
| AGENT_IMAGE_W | int | 1536 | Screenshot width |
| AGENT_IMAGE_H | int | 864 | Screenshot height |
| AGENT_DUMP_DIR | str | dumps | Screenshot directory |
| AGENT_DUMP_PREFIX | str | screen_ | Screenshot filename prefix |
| AGENT_DUMP_START | int | 1 | Initial screenshot index |
| AGENT_KEEP_LAST_SCREENSHOTS | int | 2 | Screenshot retention count |
| AGENT_KEEP_LAST_THINKS | int | 2 | Think tag retention count |
| AGENT_MAX_STEPS | int | 10 | Max agent loop iterations |
| AGENT_STEP_DELAY | float | 0.4 | Delay between steps (seconds) |

### Hardcoded Constants
- DPI Awareness: PER_MONITOR_AWARE_V2
- Mouse wheel scroll: 120 units (negative = down)
- Key press delay: 5ms between down/up
- Action delays: 60-120ms (tool-specific)
- PNG compression: zlib level 6
- Think tag regex: `<think>.*?</think>` (DOTALL mode)

---

## USAGE

### Command Line
```bash
python main.py <scenario_num>
```
- scenario_num: 1-based index into scenarios.SCENARIOS list

### Example Execution
```bash
python main.py 2
```
Runs scenario 2: "Open start menu on Windows" (with verification loop)

### Output Artifacts
- **Console:** Final agent response (stripped of think tags)
- **Log File:** agent_run_YYYYMMDD_HHMMSS.log (full HTTP exchange)
- **Screenshots:** dumps/screen_NNNN.png (sequential captures)

---

## SYSTEM REQUIREMENTS

### Platform
- Windows 11 Pro 25H2 (tested configuration)
- Windows 10+ (likely compatible, untested)

### Python
- Version: 3.12.10 (tested)
- Standard library only (no external packages)

### LLM Backend
- LM Studio 0.3.37 (Build 1) or compatible OpenAI API server
- Model: Qwen3-VL series (multimodal vision-language model)
  - Tested: qwen3-vl-4b-instruct, qwen3-vl-8b-instruct
  - Note: Qwen2.5-VL and Qwen2-VL are incompatible (different architectures)

### Hardware
- Display: 1080p (1920x1080) with 125% Windows scaling (tested)
- Arbitrary resolutions supported (normalized coordinates)

---

## LIMITATIONS

### Tool Constraints
- **type_text:** ASCII only (non-ASCII stripped)
- **press_key:** Limited key vocabulary (see _VK dict in winapi.py)
- **click_element:** Single display only (primary monitor)
- **observe_screen:** Cursor overlay may obscure small UI elements

### Agent Constraints
- Single tool call per step (enforced, excess calls rejected)
- No parallel action execution
- No rollback/undo mechanism
- Max steps limit (configurable, default 10)

### Vision Constraints
- Screenshot resolution fixed (default 1536x864)
- No OCR (relies on LLM vision capabilities)
- No element detection (LLM must infer coordinates from pixels)

### API Constraints
- OpenAI-compatible format required (tools field, tool_calls response)
- No streaming support
- Synchronous HTTP only

---

## SECURITY CONSIDERATIONS

### Risks
- **Unrestricted Desktop Access:** Agent can control mouse/keyboard, execute any GUI action
- **No Sandboxing:** Direct Windows API calls, no isolation
- **Arbitrary Tool Execution:** LLM determines all actions (potential for unintended behavior)
- **Screenshot Leakage:** Captures all visible content (passwords, sensitive data)

### Mitigations
- Run in controlled environment (VM, dedicated machine)
- Review scenario task_prompts before execution
- Monitor log files for unexpected tool calls
- Use max_steps limit to prevent runaway loops
- No network tool access (current tool set is local only)

---

## EXTENSION POINTS

### Adding New Tools
1. Define tool schema in scenarios.TOOLS_SCHEMA
2. Add execution logic in scenarios.execute_tool()
3. Implement primitive operations in winapi.py (if needed)
4. Update SYSTEM_PROMPT with tool documentation

### Custom Scenarios
1. Append dict to scenarios.SCENARIOS list: `{name, task_prompt}`
2. Run via `python main.py <new_index>`

### Alternative LLM Backends
- Replace utils.post_json() with custom HTTP client
- Ensure response format matches OpenAI structure
- Verify tool calling support (function definitions + tool_calls response)

### Multi-Monitor Support
- Extend winapi.get_screen_size() to enumerate displays
- Add monitor selection parameter to capture/click functions
- Update coordinate translation to account for display offsets

---

## DEBUGGING

### HTTP Exchange
- Check `agent_run_*.log` for full request/response pairs
- Verify tool schema transmission (truncated in log, full in actual request)
- Inspect assistant tool_calls format and arguments

### Screenshot Validation
- Review `dumps/screen_*.png` files for actual captured content
- Verify cursor position in overlay
- Check scaling quality (HALFTONE mode)

### Coordinate Issues
- Print normalized coordinates before translation (add logging in scenarios.py)
- Verify screen dimensions reported by observe_screen
- Test with known UI element positions (e.g., Start button at ~10-20, 1000)

### Tool Execution Failures
- Check tool response content field for error payloads
- Verify Windows API return codes (RuntimeError exceptions)
- Ensure focused window for type_text (click input field first)

---

## ARCHITECTURE NOTES

### Design Decisions
- **Normalized Coordinates:** Resolution-independent targeting (single prompt works across displays)
- **Tool Call Limiting:** Prevents model from spamming multiple actions (common failure mode)
- **Screenshot Pruning:** Token budget management for long tasks (keeps context window finite)
- **Manual PNG Encoding:** Avoids PIL/Pillow dependency (pure ctypes + stdlib)
- **Separate Tool/User Messages:** Tool responses are JSON metadata, observations are multimodal content

### Trade-offs
- **Performance vs Quality:** HALFTONE scaling (slower) for better image quality
- **Flexibility vs Safety:** Full desktop access (powerful) with no sandboxing (dangerous)
- **Memory vs History:** Aggressive pruning (small context) limits long-term memory

### Future Improvements
- Element detection model (output bounding boxes, reduce coordinate inference burden)
- Action replay/undo stack
- Multi-monitor support
- Streaming HTTP for faster response times
- Persistent memory across runs (vector DB for task history)

---

END OF TECHNICAL ANALYSIS REPORT
