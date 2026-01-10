# FILE: agent.py

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

import scenarios
import utils


def run_agent(
    system_prompt: str,
    task_prompt: str,
    tools_schema: List[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> str:
    endpoint = cfg["endpoint"]
    model_id = cfg["model_id"]
    timeout = cfg["timeout"]
    temperature = cfg["temperature"]
    max_tokens = cfg["max_tokens"]
    keep_last_screenshots = cfg["keep_last_screenshots"]
    keep_last_thinks = cfg.get("keep_last_thinks", 2)
    max_steps = cfg["max_steps"]
    step_delay = cfg["step_delay"]

    dump_cfg = {
        "dump_dir": cfg["dump_dir"],
        "dump_prefix": cfg["dump_prefix"],
        "dump_idx": cfg["dump_start"],
        "target_w": cfg["target_w"],
        "target_h": cfg["target_h"],
    }

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_prompt},
    ]

    # Initial screenshot
    tool_msg, user_msg = scenarios.execute_tool("observe_screen", None, "initial_observation", dump_cfg)
    messages.append(tool_msg)
    if user_msg is not None:
        messages.append(user_msg)
        messages = utils.prune_old_screenshots(messages, keep_last_screenshots)

    last_content = ""

    for _ in range(max_steps):
        resp = utils.post_json(
            {
                "model": model_id,
                "messages": messages,
                "tools": tools_schema,
                "tool_choice": "auto",
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            endpoint,
            timeout,
        )

        msg = resp["choices"][0]["message"]
        messages.append(msg)
        messages = utils.prune_old_thinks(messages, keep_last_thinks)

        if isinstance(msg.get("content"), str):
            last_content = msg["content"]

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return utils.strip_think(last_content)

        # Enforce single tool call per step (prevents model spamming tools)
        if len(tool_calls) > 1:
            for extra_tc in tool_calls[1:]:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": extra_tc["id"],
                        "name": extra_tc["function"]["name"],
                        "content": json.dumps({"ok": False, "error": "too_many_tool_calls"}),
                    }
                )
            tool_calls = tool_calls[:1]

        tc = tool_calls[0]
        name = tc["function"]["name"]
        arg_str = tc["function"].get("arguments")
        call_id = tc["id"]

        tool_msg, user_msg = scenarios.execute_tool(name, arg_str, call_id, dump_cfg)
        messages.append(tool_msg)

        if user_msg is not None:
            messages.append(user_msg)
            messages = utils.prune_old_screenshots(messages, keep_last_screenshots)

        time.sleep(step_delay)

    return utils.strip_think(last_content)
