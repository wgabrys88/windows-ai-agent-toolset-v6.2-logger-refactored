# FILE: scenarios.py

from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, Optional, Tuple

import utils
import winapi


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "observe_screen",
            "description": (
                "Captures the current screen state and returns it as an image. "
                "Use this to see applications, windows, UI elements, buttons, icons, and text. "
                "Call this at the start of each decision cycle and after actions to verify results."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": (
                "Clicks on a UI element using NORMALIZED coordinates (0-1000). "
                "Preferred: point click box=[x,y] (best for taskbar icons / small targets). "
                "Also supported: box=[x1,y1,x2,y2] or legacy box=[[x1,y1],[x2,y2]]."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "box": {
                        "description": (
                            "Click target in normalized 0-1000 coordinates. "
                            "Use [x,y] for a point click (recommended), "
                            "[x1,y1,x2,y2] for a bounding box, or legacy [[x1,y1],[x2,y2]]."
                        ),
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 4,
                                "maxItems": 4,
                            },
                            {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                                "minItems": 2,
                                "maxItems": 2,
                            },
                        ],
                    },
                },
                "required": ["label", "box"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": (
                "Types text into the currently focused input field. "
                "PREREQUISITE: Click the input field first to focus it. "
                "Only ASCII characters supported. Cannot press Enter (use press_key)."
            ),
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": (
                "Presses a keyboard key or combination. Examples: 'enter', 'tab', 'esc', "
                "'ctrl+l', 'alt+tab', 'alt+f4'."
            ),
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_at_position",
            "description": (
                "Scrolls down at a specific position. "
                "Optional target can be provided as box=[x,y], box=[x1,y1,x2,y2], or legacy [[x1,y1],[x2,y2]]. "
                "If no box is provided, scrolls at screen center (500,500)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "box": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                            {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                            {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                                "minItems": 2,
                                "maxItems": 2,
                            },
                        ]
                    }
                },
                "required": [],
            },
        },
    },
]


_screen_dimensions = {"width": 1920, "height": 1080}


def execute_tool(
    tool_name: str,
    arg_str: Any,
    call_id: str,
    dump_cfg: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Executes a tool call and returns:
      - tool_message (role=tool)
      - optional user_message (role=user) with image for observe_screen
    """
    global _screen_dimensions

    if tool_name == "observe_screen":
        png_bytes, screen_w, screen_h = winapi.capture_screenshot_png(
            dump_cfg["target_w"], dump_cfg["target_h"]
        )
        _screen_dimensions["width"] = screen_w
        _screen_dimensions["height"] = screen_h

        os.makedirs(dump_cfg["dump_dir"], exist_ok=True)
        fn = os.path.join(
            dump_cfg["dump_dir"],
            f"{dump_cfg['dump_prefix']}{dump_cfg['dump_idx']:04d}.png",
        )
        with open(fn, "wb") as f:
            f.write(png_bytes)
        dump_cfg["dump_idx"] += 1

        b64 = base64.b64encode(png_bytes).decode("ascii")

        tool_msg = {
            "role": "tool",
            "tool_call_id": call_id,
            "name": tool_name,
            "content": utils.ok_payload(
                {
                    "file": fn,
                    "screen_width": screen_w,
                    "screen_height": screen_h,
                    "message": (
                        "Screenshot captured. Use normalized coordinates (0-1000). "
                        "Prefer point clicks: box=[x,y]."
                    ),
                }
            ),
        }

        user_msg = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Current screen state. Identify UI elements and provide click targets in normalized "
                        "0-1000 coordinates. Prefer point clicks box=[x,y] for small targets (taskbar icons)."
                    ),
                },
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
            ],
        }
        return tool_msg, user_msg

    if tool_name == "click_element":
        args, err = utils.parse_args(arg_str)
        if err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None

        label = str(args.get("label", "")).strip()
        box = args.get("box")

        if not label:
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "name": tool_name,
                "content": utils.err_payload("missing_label", "label required"),
            }, None
        if box is None:
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "name": tool_name,
                "content": utils.err_payload("missing_box", "box required"),
            }, None

        bbox, box_err = utils.parse_box(box)
        if box_err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": box_err}, None

        x1, y1, x2, y2 = bbox
        cx, cy = utils.box_center(x1, y1, x2, y2)

        px, py = winapi.norm_to_screen_px(cx, cy, _screen_dimensions["width"], _screen_dimensions["height"])
        winapi.move_mouse_to_pixel(px, py)
        time.sleep(0.08)
        winapi.click_mouse()
        time.sleep(0.12)

        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": tool_name,
            "content": utils.ok_payload(
                {
                    "clicked": label,
                    "box_normalized": [[x1, y1], [x2, y2]],
                    "click_position": [cx, cy],
                    "message": f"Clicked '{label}' at ({cx:.1f},{cy:.1f}). Use observe_screen to verify.",
                }
            ),
        }, None

    if tool_name == "type_text":
        args, err = utils.parse_args(arg_str)
        if err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None

        text = str(args.get("text", ""))
        text_ascii = text.encode("ascii", "ignore").decode("ascii")
        if not text_ascii:
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "name": tool_name,
                "content": utils.err_payload("empty_text", "text empty or no ASCII chars"),
            }, None

        winapi.type_text(text_ascii)
        time.sleep(0.08)

        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": tool_name,
            "content": utils.ok_payload(
                {"typed": text_ascii, "chars": len(text_ascii), "message": "Typed text. Use observe_screen to verify."}
            ),
        }, None

    if tool_name == "press_key":
        args, err = utils.parse_args(arg_str)
        if err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None

        key = str(args.get("key", "")).strip().lower()
        if not key:
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "name": tool_name,
                "content": utils.err_payload("missing_key", "key required"),
            }, None

        try:
            winapi.press_key(key)
            time.sleep(0.08)
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "name": tool_name,
                "content": utils.ok_payload({"key": key, "message": f"Pressed '{key}'. Use observe_screen to verify."}),
            }, None
        except ValueError as e:
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "name": tool_name,
                "content": utils.err_payload("invalid_key", str(e)),
            }, None

    if tool_name == "scroll_at_position":
        args, err = utils.parse_args(arg_str)
        if err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None

        box = args.get("box")
        if box is not None:
            bbox, box_err = utils.parse_box(box)
            if box_err:
                return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": box_err}, None
            cx, cy = utils.box_center(*bbox)
        else:
            cx, cy = 500.0, 500.0

        px, py = winapi.norm_to_screen_px(cx, cy, _screen_dimensions["width"], _screen_dimensions["height"])
        winapi.move_mouse_to_pixel(px, py)
        time.sleep(0.06)
        winapi.scroll_down()
        time.sleep(0.08)

        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": tool_name,
            "content": utils.ok_payload({"message": f"Scrolled down at ({cx:.1f},{cy:.1f}). Use observe_screen to verify."}),
        }, None

    return {
        "role": "tool",
        "tool_call_id": call_id,
        "name": tool_name,
        "content": utils.err_payload("unknown_tool", f"Unknown tool: {tool_name}"),
    }, None


SYSTEM_PROMPT = """You are an autonomous AI agent with vision and control over a Windows desktop. Complete user tasks through observation and interaction with the GUI.

## Capabilities
- observe_screen() - See current screen state
- click_element(label, box) - Click UI elements
- type_text(text) - Type into focused fields
- press_key(key) - Press keys/combinations
- scroll_at_position(box) - Scroll at position

## Coordinate System: NORMALIZED (0-1000)
- X: 0 (left) to 1000 (right)
- Y: 0 (top) to 1000 (bottom)
- Center: (500, 500)

### Click target formats (ALL VALID)
- Point: box=[x,y]  (PREFERRED, especially for taskbar icons / small targets)
- Flat bbox: box=[x1,y1,x2,y2]
- Legacy bbox: box=[[x1,y1],[x2,y2]]

## Operating Protocol
1. OBSERVE: observe_screen()
2. Think privately.
3. ACT: Execute ONE tool with normalized coordinates.
4. VERIFY: observe_screen() after actions.

## Rules
- Always use 0-1000 coordinates (NOT pixels).
- Prefer point clicks box=[x,y].
- Click before typing.
- One action per step.
Begin by observing the screen."""


SCENARIOS = [
    {"name": "Open YouTube", "task_prompt": "Use the GRROK ai that is open in chrome browser windows to initialize a conversation about wgabrys88 github projects and make sure to not stop the conversation, depending on the grok response you may want to open a link that grok provides to wgabrys88 github project, then analyze the repo and back to grok again to further explanations on the things you saw, this is a never-ending task, there is always more to learn from grok, begin the investigation."},
]