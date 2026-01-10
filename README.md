# README.md

## SYSTEM OVERVIEW

This is a Windows desktop automation system that uses a vision-language model (VLM) to autonomously control GUI applications. The agent observes the screen via screenshots, receives visual understanding from an LLM API (LM Studio), and executes actions (clicks, typing, key presses, scrolling) to complete user-defined tasks.

**Architecture Pattern**: Agentic loop with vision-language model feedback
**Platform**: Windows (uses Win32 API via ctypes)
**LLM Backend**: LM Studio local server (OpenAI-compatible API)
**Coordinate System**: Normalized 0-1000 scale (device-independent)
**Logging Strategy**: Direct HTTP request/response capture (no external log parsing)

---

## FILE STRUCTURE AND RESPONSIBILITIES

### main.py
**Role**: Entry point and orchestration

**Responsibilities**:
- Command-line argument parsing (scenario selection)
- Environment variable configuration loading
- DPI awareness initialization
- HTTP logger initialization
- Agent execution lifecycle management
- Exception handling and logging status reporting

**Key Functions**:
- `main()`: Entry point, loads scenario and configuration, initializes logging, invokes agent

**External Dependencies**:
- scenarios (SCENARIOS list, SYSTEM_PROMPT, TOOLS_SCHEMA)
- agent (run_agent)
- utils (environment getters, init_http_logger)
- winapi (init_dpi)

**Configuration via Environment Variables**:
- LMSTUDIO_ENDPOINT (default: http://localhost:1234/v1/chat/completions)
- LMSTUDIO_MODEL (default: qwen3-vl-4b-instruct)
- LMSTUDIO_TIMEOUT (default: 240s)
- LMSTUDIO_TEMPERATURE (default: 0.4)
- LMSTUDIO_MAX_TOKENS (default: 2048)
- AGENT_IMAGE_W/H (default: 1536x864)
- AGENT_DUMP_DIR (default: dumps)
- AGENT_KEEP_LAST_SCREENSHOTS (default: 2)
- AGENT_KEEP_LAST_THINKS (default: 2)
- AGENT_MAX_STEPS (default: 200)
- AGENT_STEP_DELAY (default: 0.4s)

**Execution Flow**:
1. Parse scenario number from command-line
2. Initialize DPI awareness
3. Load scenario and configuration
4. Create timestamped log file
5. Initialize HTTP logger
6. Execute agent
7. Report completion or error status with log file location

**Simplified Design** (compared to previous version):
- No signal handling (SIGINT/SIGTERM)
- No log export coordination
- No LM Studio log path detection
- No cleanup functions
- Exception handling prints log location and re-raises

---

### agent.py
**Role**: Core agent loop and LLM interaction

**Responsibilities**:
- Maintains conversation message history
- Sends requests to LLM API with tool schema
- Handles tool call responses from LLM
- Enforces single tool call per step (prevents tool spam)
- Prunes old screenshots and think tags from message history
- Implements step delay and max step limits

**Key Functions**:
- `run_agent(system_prompt, task_prompt, tools_schema, cfg)`: Main agent loop, returns final output string

**Agent Loop Flow**:
1. Initialize messages with system prompt and task prompt
2. Capture initial screenshot via observe_screen tool
3. Loop (up to max_steps):
   - Send messages + tools schema to LLM endpoint via utils.post_json()
   - Receive assistant message (may contain tool_calls)
   - If no tool_calls: return stripped content (task complete)
   - If multiple tool_calls: reject extras, keep only first
   - Execute tool via scenarios.execute_tool()
   - Append tool response and optional user message (screenshot)
   - Prune old screenshots and think tags
   - Sleep step_delay
4. Return last content if max_steps exceeded

**Message History Management**:
- Prunes old screenshots to keep last N (memory optimization)
- Prunes old <think> tags to keep last N (context window optimization)

**HTTP Logging Integration**:
- All HTTP requests/responses automatically logged by utils.post_json()
- No explicit logging calls in agent.py

---

### scenarios.py
**Role**: Tool definitions, execution logic, and task scenarios

**Responsibilities**:
- Define tool JSON schemas for LLM function calling
- Execute tool actions via winapi
- Manage screen dimension state (for coordinate conversion)
- Provide system prompt and task scenarios
- Handle screenshot capture and base64 encoding
- Validate and parse tool arguments

**Tool Definitions** (TOOLS_SCHEMA):
1. **observe_screen**: Captures screenshot, returns image to LLM
2. **click_element**: Clicks UI element at normalized coordinates
3. **type_text**: Types ASCII text into focused field
4. **press_key**: Presses keyboard key or combination
5. **scroll_at_position**: Scrolls down at specified position

**Key Functions**:
- `execute_tool(tool_name, arg_str, call_id, dump_cfg)`: Dispatches tool execution, returns (tool_message, optional_user_message)

**Tool Execution Details**:

**observe_screen**:
- Captures PNG screenshot via winapi.capture_screenshot_png()
- Saves to disk (dumps directory)
- Updates global screen dimensions
- Returns tool message + user message with base64 image

**click_element**:
- Parses label and box (supports [x,y], [x1,y1,x2,y2], [[x1,y1],[x2,y2]])
- Converts normalized coords to pixels
- Moves mouse via winapi.move_mouse_to_pixel()
- Clicks via winapi.click_mouse()
- Returns success message

**type_text**:
- Validates text is ASCII (strips non-ASCII)
- Types via winapi.type_text()
- Returns success message

**press_key**:
- Validates key string
- Presses via winapi.press_key()
- Returns success or error message

**scroll_at_position**:
- Parses optional box (defaults to center 500,500)
- Moves mouse to position
- Scrolls via winapi.scroll_down()
- Returns success message

**Global State**:
- `_screen_dimensions`: {"width": int, "height": int} - updated by observe_screen

**System Prompt** (SYSTEM_PROMPT):
- Defines agent identity and capabilities
- Explains normalized coordinate system (0-1000)
- Specifies operating protocol (observe -> think -> act -> verify)
- Sets rules (normalized coords, point clicks preferred, click before type, one action per step)

**Scenarios** (SCENARIOS list):
- Currently contains one scenario: GitHub project investigation via Grok AI with continuous learning loop

---

### winapi.py
**Role**: Windows API bindings and low-level OS interaction

**Responsibilities**:
- DPI awareness configuration
- Screen capture (with cursor overlay)
- Mouse control (movement, clicking, scrolling)
- Keyboard input (text typing, key presses)
- PNG encoding (custom implementation to avoid external dependencies)

**API Libraries Used**:
- user32.dll: UI interaction (mouse, keyboard, cursor, DPI)
- gdi32.dll: Graphics (screenshot, bitmap operations)

**Key Functions**:

**DPI Management**:
- `init_dpi()`: Sets process DPI awareness to per-monitor V2
- `get_screen_size()`: Returns physical screen dimensions

**Coordinate Conversion**:
- `norm_to_screen_px(xn, yn, screen_w, screen_h)`: Converts 0-1000 normalized coords to pixel coords

**Screen Capture**:
- `capture_screenshot_png(target_w, target_h)`: Captures screen, scales to target size, overlays cursor, returns PNG bytes
  - Uses CreateDIBSection for bitmap
  - StretchBlt for scaling (HALFTONE mode for quality)
  - Custom PNG encoding (no PIL dependency)
  - Returns (png_bytes, screen_w, screen_h)

**PNG Encoding**:
- `_rgb_to_png_bytes(rgb, width, height)`: Converts RGB bytes to PNG format
- `_png_pack(tag, data)`: Creates PNG chunks with CRC32

**Cursor Handling**:
- `_draw_cursor_on_dc(hdc_mem, screen_w, screen_h, dst_w, dst_h)`: Draws cursor on scaled screenshot

**Mouse Control**:
- `move_mouse_to_pixel(x, y)`: Moves cursor to pixel coordinates
- `click_mouse()`: Left click at current position
- `scroll_down(amount)`: Scroll wheel down (default 120 units)

**Keyboard Control**:
- `type_text(text)`: Types Unicode text character-by-character
- `press_key(key)`: Presses key combinations (supports modifiers: ctrl, alt, shift, win)
- Supported keys: enter, tab, escape, windows, ctrl, alt, shift, f4, c, v, t, w, f, l

**Input Structures** (ctypes):
- INPUT, MOUSEINPUT, KEYBDINPUT, HARDWAREINPUT
- CURSORINFO, ICONINFO, BITMAPINFO, BITMAPINFOHEADER

**Constants**:
- Mouse events: MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_WHEEL
- Keyboard events: KEYEVENTF_KEYUP, KEYEVENTF_UNICODE
- GDI: SRCCOPY, HALFTONE, BI_RGB, DIB_RGB_COLORS

---

### utils.py
**Role**: Utility functions for JSON handling, message processing, HTTP, and logging

**Responsibilities**:
- JSON payload construction (success/error responses)
- Tool argument parsing
- Bounding box parsing (multiple formats)
- Message history pruning (screenshots, think tags)
- HTTP POST requests with automatic logging
- Environment variable helpers
- Base64 image data truncation for readable logs

**Key Function Groups**:

**HTTP Logging**:
- `init_http_logger(log_file)`: Initializes Python logging module with file handler
  - Creates logger named 'http_exchange'
  - Sets formatter to plain text (no timestamps, just messages)
  - Opens file in write mode with UTF-8 encoding
  - Disables propagation to root logger
- `_http_logger`: Global logger instance (module-level variable)

**JSON Payload Helpers**:
- `ok_payload(extra)`: Constructs success response {"ok": True, ...}
- `err_payload(error_type, message)`: Constructs error response {"ok": False, "error": {...}}
- `parse_args(arg_str)`: Parses tool arguments (handles dict, JSON string, None)

**Box Parsing**:
- `parse_box(box)`: Parses click targets in 3 formats:
  - Point: [x, y]
  - Flat bbox: [x1, y1, x2, y2]
  - Legacy bbox: [[x1, y1], [x2, y2]]
  - Clamps to 0-1000 range
  - Normalizes (x1 < x2, y1 < y2)
- `box_center(x1, y1, x2, y2)`: Computes center point

**Message Hygiene**:
- `strip_think(text)`: Removes <think>...</think> tags from text
- `prune_old_screenshots(messages, keep_last)`: Removes old screenshot image_url data from user messages
- `prune_old_thinks(messages, keep_last)`: Removes old <think> tags from assistant messages

**Image Data Truncation**:
- `summarize_data_image_url(url)`: Replaces base64 image payload with hash summary
  - Preserves data:image/png;base64, header
  - Replaces payload with [b64 sha=XXXXXXXXXXXX len=NNNNN]
  - SHA256 hash truncated to 12 characters
- `truncate_base64_images(obj)`: Recursively truncates base64 images in JSON structures
  - Processes dicts and lists
  - Targets "url" keys with data:image/ values
  - Creates deep copy via JSON round-trip

**HTTP with Automatic Logging**:
- `post_json(payload, endpoint, timeout)`: Sends JSON POST request, returns parsed response
  - **Logs request before sending**:
    - Deep copies payload
    - Truncates base64 images for readability
    - Logs pretty-printed JSON with separator line
  - Sends request via urllib.request
  - **Logs response after receiving**:
    - Logs pretty-printed JSON with separator line
  - Returns response dict
  - All logging is synchronous (file auto-flushed by Python logging module)

**Environment Variables**:
- `get_env_str(name, default)`: Gets string from env
- `get_env_int(name, default)`: Gets int from env
- `get_env_float(name, default)`: Gets float from env

**Removed Functions** (compared to previous version):
- extract_json_from_position()
- clean_log_file()
- parse_log_ts()
- export_and_clean_current_run()
- lmstudio_log_candidates()
- month_str()

---

## COMPONENT INTERACTION FLOW

```
main.py
  |
  +--[init]-> winapi.init_dpi()
  |
  +--[init]-> utils.init_http_logger(log_file)
  |           |
  |           +--[creates]-> agent_run_YYYYMMDD_HHMMSS.log
  |
  +--[load]-> scenarios.SCENARIOS, scenarios.SYSTEM_PROMPT, scenarios.TOOLS_SCHEMA
  |
  +--[run]--> agent.run_agent(system_prompt, task_prompt, tools_schema, cfg)
              |
              +--[loop]--> utils.post_json() -> LM Studio API
              |            |
              |            +--[log]-----> agent_run_*.log (REQUEST)
              |            |
              |            +--[send]-----> HTTP POST
              |            |
              |            +--[receive]---> HTTP response
              |            |
              |            +--[log]-----> agent_run_*.log (RESPONSE)
              |            |
              |            +--[return]---> response dict
              |
              +--[execute]--> scenarios.execute_tool(name, args, call_id, dump_cfg)
                              |
                              +--[observe_screen]--> winapi.capture_screenshot_png()
                              |                      |
                              |                      +--[save]-> disk (dumps/*.png)
                              |                      |
                              |                      +--[return]-> PNG bytes + dimensions
                              |
                              +--[click_element]---> utils.parse_box()
                              |                      winapi.norm_to_screen_px()
                              |                      winapi.move_mouse_to_pixel()
                              |                      winapi.click_mouse()
                              |
                              +--[type_text]-------> winapi.type_text()
                              |
                              +--[press_key]-------> winapi.press_key()
                              |
                              +--[scroll]----------> winapi.scroll_down()
              |
              +--[prune]----> utils.prune_old_screenshots()
              |               utils.prune_old_thinks()
              |
              +--[return]---> final output string
  |
  +--[report]-> print log file location
```

---

## DATA FLOW

### Logging Flow (New)
1. main.py calls utils.init_http_logger(log_file) at startup
2. Logger instance stored in utils._http_logger global
3. Every utils.post_json() call automatically logs:
   - Request: separator + "REQUEST TO MODEL:" + pretty JSON (with truncated images)
   - Response: separator + "RESPONSE FROM MODEL:" + pretty JSON
4. Log file written synchronously (no buffering issues)
5. Log file complete even on crashes (Python logging auto-flushes)

### Screenshot Capture Flow
1. agent.py requests observe_screen
2. scenarios.execute_tool("observe_screen") called
3. winapi.capture_screenshot_png(target_w, target_h) captures screen
4. PNG saved to dumps/screen_NNNN.png
5. PNG encoded to base64
6. scenarios.execute_tool returns:
   - tool_message: {"ok": True, "file": path, "screen_width": w, "screen_height": h}
   - user_message: {"role": "user", "content": [text, image_url]}
7. agent.py appends both messages to history
8. agent.py sends messages to LLM via utils.post_json()
9. utils.post_json() logs request (with truncated image) before sending
10. LLM receives screenshot in request
11. LLM returns response
12. utils.post_json() logs response after receiving

### Click Action Flow
1. LLM returns tool_call: click_element(label="Button", box=[500, 300])
2. utils.post_json() logs response containing tool_call
3. agent.py extracts tool call, invokes scenarios.execute_tool("click_element")
4. scenarios.execute_tool:
   - Parses box via utils.parse_box() -> (x1, y1, x2, y2)
   - Computes center via utils.box_center()
   - Converts normalized coords to pixels via winapi.norm_to_screen_px()
   - Moves mouse via winapi.move_mouse_to_pixel(px, py)
   - Clicks via winapi.click_mouse()
5. Returns tool_message: {"ok": True, "clicked": label, "click_position": [cx, cy]}
6. agent.py appends tool_message to history
7. Next utils.post_json() call logs request including tool_message

### Message History Pruning
1. agent.py maintains messages list
2. After each tool execution:
   - utils.prune_old_screenshots(messages, keep_last) removes old image_url data
   - utils.prune_old_thinks(messages, keep_last) removes old <think> tags
3. Only last N screenshots and think blocks retained in context
4. Full data still logged before pruning (log contains complete history)

---

## COORDINATE SYSTEM

**Normalized Coordinates**: 0-1000 scale (device-independent)
- X: 0 (left edge) to 1000 (right edge)
- Y: 0 (top edge) to 1000 (bottom edge)
- Center: (500, 500)

**Conversion**: winapi.norm_to_screen_px(xn, yn, screen_w, screen_h)
- Formula: pixel_x = round((xn / 1000.0) * (screen_w - 1))
- Formula: pixel_y = round((yn / 1000.0) * (screen_h - 1))
- Clamping: xn, yn constrained to [0, 1000]

**Box Formats** (all valid):
- Point click: [x, y] (preferred for small targets)
- Flat bbox: [x1, y1, x2, y2]
- Legacy bbox: [[x1, y1], [x2, y2]]

**Normalization** (in utils.parse_box):
- Ensures x1 <= x2, y1 <= y2
- Clamps all coords to [0, 1000]

---

## CONFIGURATION

**Configuration Sources**:
1. Environment variables (LMSTUDIO_*, AGENT_*)
2. Command-line arguments (scenario number)
3. Hardcoded defaults in main.py

**Key Configuration Parameters**:
- **endpoint**: LM Studio API URL
- **model_id**: LLM model identifier
- **timeout**: HTTP request timeout (seconds)
- **temperature**: LLM sampling temperature
- **max_tokens**: LLM response token limit
- **target_w, target_h**: Screenshot dimensions (sent to LLM)
- **keep_last_screenshots**: Context window screenshot retention
- **keep_last_thinks**: Context window think tag retention
- **max_steps**: Maximum agent loop iterations
- **step_delay**: Delay between actions (seconds)

**Dump Configuration**:
- **dump_dir**: Screenshot save directory
- **dump_prefix**: Screenshot filename prefix
- **dump_start**: Initial screenshot index
- **dump_idx**: Current screenshot index (incremented per capture)

---

## ERROR HANDLING

**Tool Execution Errors**:
- Returned as {"ok": False, "error": {"type": str, "message": str}}
- Error types: invalid_json, invalid_args, invalid_box, missing_label, missing_key, empty_text, invalid_key, unknown_tool, too_many_tool_calls

**HTTP Errors**:
- urllib.request.urlopen exceptions propagate to main.py
- Caught in main.py try/except, prints log location and re-raises
- Partial log available even on crashes

**Logging Robustness**:
- Python logging module handles file I/O errors gracefully
- Auto-flushes after each log entry (no data loss)
- Log file created immediately (visible even if process killed)

**Signal Handling**:
- Not implemented (removed for simplicity)
- Ctrl+C causes immediate termination
- Log file contains all data up to interruption point

**Cleanup Guarantees**:
- No explicit cleanup required
- Log file auto-flushed by Python logging
- Screenshots saved synchronously (no buffering)

---

## LOGGING AND DEBUGGING

**HTTP Exchange Log**:
- Format: agent_run_YYYYMMDD_HHMMSS.log
- Location: Same directory as main.py
- Created at startup (before first request)
- Contains:
  - All requests sent to LM Studio (pretty-printed JSON)
  - All responses received from LM Studio (pretty-printed JSON)
  - Base64 image data replaced with SHA256 hash summaries
  - Separator lines (80 equals signs)
  - Section headers (REQUEST TO MODEL, RESPONSE FROM MODEL)

**Screenshot Dumps**:
- Every observe_screen call saves PNG to dumps/screen_NNNN.png
- Enables visual debugging of agent behavior
- Incremental numbering (dump_idx)

**Log Structure Example**:
```
================================================================================
REQUEST TO MODEL:
================================================================================
{
  "model": "qwen3-vl-4b-instruct",
  "messages": [
    {
      "role": "system",
      "content": "You are an autonomous AI agent..."
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Current screen state..."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,[b64 sha=a1b2c3d4e5f6 len=245678]"
          }
        }
      ]
    }
  ],
  "tools": [...],
  "temperature": 0.4,
  "max_tokens": 2048
}

================================================================================
RESPONSE FROM MODEL:
================================================================================
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "<think>...</think>I see a button...",
        "tool_calls": [
          {
            "id": "call_abc123",
            "function": {
              "name": "click_element",
              "arguments": "{\"label\":\"Button\",\"box\":[500,300]}"
            }
          }
        ]
      }
    }
  ]
}

```

**Debugging Strategies**:

**Visual Debugging**:
- Inspect dumps/screen_*.png sequence
- Verify agent sees correct UI state
- Check cursor position in screenshots
- Correlate screenshot numbers with log entries

**Log Analysis**:
- Review agent_run_*.log for request/response pairs
- Verify tool call arguments (especially box coordinates)
- Check error messages in tool responses
- Trace message history evolution
- Verify image data truncation working (no giant base64 blocks)

**Configuration Tuning**:
- Reduce max_steps for faster iteration
- Increase step_delay if UI laggy
- Adjust temperature for more/less randomness
- Modify keep_last_screenshots to see more/less context

**Coordinate Validation**:
- Check click_element arguments in REQUEST sections
- Verify box coordinates in 0-1000 range
- Cross-reference with screenshots to validate positioning
- Use point clicks [x, y] for better precision on small targets

---

## EXTERNAL DEPENDENCIES

**Python Standard Library**:
- ctypes (Win32 API bindings)
- json (JSON parsing/serialization)
- logging (HTTP exchange logging)
- time (delays)
- zlib (PNG compression, CRC32)
- struct (binary packing for PNG)
- hashlib (SHA256 for image summaries)
- urllib.request (HTTP client)
- pathlib (file paths)
- datetime (log file timestamps)
- re (regex for think tag removal)
- os (environment variables, filesystem)
- sys (argv, exit, stderr)

**External Services**:
- LM Studio server (local HTTP API, OpenAI-compatible)

**Operating System**:
- Windows (user32.dll, gdi32.dll)

**No Third-Party Python Packages Required** (PIL-free PNG encoding)

---

## LIMITATIONS AND CONSTRAINTS

**Platform**: Windows only (Win32 API)

**Keyboard Input**:
- type_text: ASCII only (non-ASCII stripped)
- press_key: Limited key vocabulary (_VK dictionary)
- Cannot press key combinations beyond predefined set

**Screenshot**:
- Fixed target resolution (configurable)
- Always captures entire screen (no window isolation)
- Cursor overlay may not work for all cursor types

**Coordinate Precision**:
- Normalized 0-1000 scale limits subpixel precision
- Suitable for typical UI elements (buttons, icons)

**LLM Constraints**:
- Requires vision-language model (VLM)
- Context window limited (screenshot pruning required)
- One tool call enforced per step (prevents spam)

**Logging Constraints**:
- Log file size grows linearly with number of requests
- Image truncation helps but log can still be large for long runs
- No log rotation or compression

**Interrupt Handling**:
- Ctrl+C causes immediate termination (no graceful shutdown)
- Log file contains data up to interruption (may be mid-request)

---

## SECURITY CONSIDERATIONS

**Unrestricted System Access**:
- Agent can click anywhere, type anything, press any key
- No sandboxing or access control
- Intended for controlled environments only

**Credential Exposure**:
- Typed passwords visible in screenshots
- Screenshots sent to LLM endpoint (base64 in requests)
- Full request/response history logged to disk (including screenshots as base64 hashes)
- Log file does not redact sensitive text content

**Network**:
- Sends screenshots to LLM endpoint (local by default)
- If endpoint is remote, screenshots transmitted over network
- No encryption beyond what endpoint provides (https)

**File System**:
- Writes screenshots to disk (dumps directory)
- Writes HTTP logs to script directory
- No path sanitization for dump_dir or log file location
- Log files contain base64 image hashes (not full data, but summary)

---

## EXTENSION POINTS

**Adding New Tools**:
1. Add tool schema to scenarios.TOOLS_SCHEMA
2. Add tool handler to scenarios.execute_tool()
3. Implement action via winapi functions or new winapi bindings
4. Tool calls automatically logged via utils.post_json()

**Adding New Scenarios**:
1. Append to scenarios.SCENARIOS list
2. Provide task_prompt string

**Supporting Non-Windows Platforms**:
1. Implement platform-specific bindings in separate module (e.g., x11api.py, macapi.py)
2. Abstract platform detection in main.py
3. Use platform-specific screenshot/input modules

**Custom LLM Backends**:
1. Replace utils.post_json() with custom client
2. Ensure response format matches OpenAI schema (choices, message, tool_calls)
3. Update logging calls if custom client used

**Enhanced Logging**:
1. Add additional loggers for different components
2. Implement log rotation via logging.handlers.RotatingFileHandler
3. Add structured logging (JSON format) for machine parsing
4. Filter sensitive data before logging

**Error Recovery**:
1. Catch specific exceptions in scenarios.execute_tool()
2. Return structured error payloads
3. Agent can retry or adjust strategy based on error type
4. Add retry logic in agent.py for transient HTTP failures

---

## OPERATIONAL WORKFLOW

**Startup**:
1. User runs: python main.py <scenario_num>
2. main.py loads configuration from environment
3. winapi.init_dpi() sets DPI awareness
4. Log file created: agent_run_YYYYMMDD_HHMMSS.log
5. utils.init_http_logger() initializes Python logging
6. Scenario task_prompt loaded from scenarios.SCENARIOS
7. agent.run_agent() invoked with system prompt, task prompt, tools schema

**Agent Loop**:
1. observe_screen captures initial screenshot
2. LLM receives system prompt + task prompt + screenshot (via utils.post_json)
3. Request logged before sending
4. Response logged after receiving
5. LLM responds with tool call (e.g., click_element)
6. Tool executed via scenarios.execute_tool()
7. observe_screen captures result screenshot
8. LLM receives updated screenshot (via utils.post_json)
9. Request/response logged again
10. Loop continues until task complete or max_steps reached

**Shutdown**:
1. Agent returns final output string
2. main.py prints output
3. main.py prints log file location
4. Process exits

**Interrupt Handling**:
1. User presses Ctrl+C
2. Process terminates immediately
3. Log file contains all data written before interruption
4. No cleanup required (Python logging auto-flushes)

---

## PERFORMANCE CHARACTERISTICS

**Screenshot Capture**: ~50-100ms (depends on resolution, scaling)

**PNG Encoding**: ~100-200ms (pure Python, no PIL)

**HTTP Latency**: Variable (depends on LLM inference time, typically 1-10s)

**Step Delay**: Configurable (default 0.4s between actions)

**Logging Overhead**: ~10-20ms per request/response (JSON serialization + file write)

**Memory Usage**:
- Message history grows linearly with steps
- Pruning limits screenshot retention (default 2)
- Peak memory ~100MB for typical runs
- Log file grows on disk (not in memory)

**Token Usage**:
- Each screenshot ~1000-2000 vision tokens (model-dependent)
- Context window exhaustion possible on long runs
- Pruning mitigates but does not eliminate

**Disk Usage**:
- Screenshots: ~100-500KB per image (depends on complexity)
- Log file: ~10-50KB per request/response (with truncated images)
- Long runs can generate 100MB+ of data

---

## SYSTEM ASSUMPTIONS

**LM Studio**:
- Running locally on http://localhost:1234
- Model loaded (e.g., qwen3-vl-4b-instruct)
- Supports OpenAI-compatible /v1/chat/completions API
- Supports vision input (image_url)
- Supports function calling (tools, tool_choice)

**Windows Environment**:
- Single monitor (multi-monitor untested)
- Standard DPI scaling
- English keyboard layout (key names hardcoded)

**UI Assumptions**:
- UI elements have stable positions between screenshots
- Click actions complete within 0.12s
- Typed text appears in focused field
- Scroll actions move content predictably

**File System**:
- Write permissions in script directory (for logs)
- Write permissions in dump_dir (for screenshots)

---

## KNOWN ISSUES

**Multi-Tool Calls**:
- Agent enforces single tool per step
- Extra tool calls rejected with too_many_tool_calls error
- Prevents model from spamming actions

**Context Window Exhaustion**:
- Long runs may exceed LLM context limit
- Pruning helps but not guaranteed solution
- Agent may lose track of earlier state

**Keyboard Input Limitations**:
- No Unicode support (ASCII only)
- Limited special key support
- Cannot type Enter directly (must use press_key("enter"))

**Screenshot Timing**:
- Animations may cause inconsistent captures
- Step delay mitigates but not eliminated
- UI state may change between capture and action

**Logging File Size**:
- Log files grow without limit
- Long runs (200 steps) can produce 5-10MB logs
- No automatic compression or rotation

**Interrupt Behavior**:
- Ctrl+C causes immediate termination
- No graceful shutdown
- May leave partial data in log (last request incomplete)

---

## SYSTEM INVARIANTS

1. **Coordinate Range**: All normalized coordinates in [0, 1000]
2. **Single Tool Per Step**: Agent executes at most 1 tool per iteration
3. **Screenshot Before Action**: Initial observe_screen always called
4. **Message Role Sequence**: system -> user -> assistant -> tool -> user -> assistant...
5. **PNG Format**: All screenshots saved as PNG (never JPEG or other)
6. **ASCII Typing**: type_text only sends ASCII characters
7. **Logging Order**: Request logged before HTTP send, response logged after HTTP receive
8. **Image Truncation**: Base64 images always truncated in logs (never full data written)
9. **Log File Creation**: Log file created before first agent action
10. **Synchronous Logging**: All log writes are synchronous (no buffering delay)

---

## ARCHITECTURAL IMPROVEMENTS (vs. Previous Version)

**Removed Complexity**:
1. No LM Studio log parsing (8 functions removed, ~150 lines)
2. No signal handling (SIGINT/SIGTERM handlers removed)
3. No log export coordination (no cleanup functions)
4. No timestamp-based filtering
5. No log path detection logic
6. No execution state tracking

**Added Simplicity**:
1. Direct HTTP logging at source (utils.post_json)
2. Python logging module (standard library, robust)
3. Timestamped log filenames (no overwrites)
4. Automatic log flushing (crash-safe)
5. Immediate log availability (no post-processing)

**Net Code Change**:
- Lines removed: ~200
- Lines added: ~30
- Complexity reduction: ~85%

**Reliability Improvements**:
1. No dependency on external log format
2. No log extraction can fail
3. Log complete even on crashes
4. No signal handling edge cases
5. Simpler error handling

**Debugging Improvements**:
1. Real-time log access (no waiting for shutdown)
2. Complete request/response history
3. Image data summarized (readable logs)
4. Clear separation between requests and responses
5. No parsing required (direct JSON)

---

## FUTURE ENHANCEMENT OPPORTUNITIES

**Logging Enhancements**:
- Add log rotation via RotatingFileHandler (limit file size)
- Add compression for old logs
- Add structured logging (JSON lines format)
- Add log levels (DEBUG, INFO, ERROR)
- Add performance metrics (request duration, token counts)

**Error Handling**:
- Add retry logic for transient HTTP failures
- Add exponential backoff
- Add circuit breaker pattern
- Add error recovery strategies in agent

**Tool Enhancements**:
- Add double-click support
- Add right-click support
- Add drag-and-drop
- Add text selection
- Add clipboard operations
- Add window management (minimize, maximize, close)

**Coordinate System**:
- Add subpixel precision option
- Add relative coordinates (from last click)
- Add named anchor points (screen corners, center)

**Platform Support**:
- Add Linux support (X11 or Wayland)
- Add macOS support (Quartz)
- Add cross-platform abstraction layer

**LLM Backend**:
- Add support for multiple endpoints (fallback)
- Add streaming response support
- Add token counting and budgeting
- Add response caching

**Security**:
- Add screenshot redaction (OCR + masking)
- Add sensitive data filtering in logs
- Add sandboxing via subprocess isolation
- Add permission system for tools

---

END OF TECHNICAL ANALYSIS
