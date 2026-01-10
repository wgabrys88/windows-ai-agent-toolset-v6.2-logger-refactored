# FILE: main.py

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import scenarios
import utils
import winapi
from agent import run_agent


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: python main.py <scenario_num>")

    scenario_num = int(sys.argv[1])

    winapi.init_dpi()

    if scenario_num < 1 or scenario_num > len(scenarios.SCENARIOS):
        sys.exit("Invalid scenario")

    sc = scenarios.SCENARIOS[scenario_num - 1]
    task_prompt = str(sc.get("task_prompt", "")).strip()
    if not task_prompt:
        sys.exit("Invalid scenario prompt")

    cfg = {
        "endpoint": utils.get_env_str("LMSTUDIO_ENDPOINT", "http://localhost:1234/v1/chat/completions"),
        "model_id": utils.get_env_str("LMSTUDIO_MODEL", "qwen3-vl-4b-instruct"),
        "timeout": utils.get_env_int("LMSTUDIO_TIMEOUT", 240),
        "temperature": utils.get_env_float("LMSTUDIO_TEMPERATURE", 0.4),
        "max_tokens": utils.get_env_int("LMSTUDIO_MAX_TOKENS", 2048),
        "target_w": utils.get_env_int("AGENT_IMAGE_W", 1536),
        "target_h": utils.get_env_int("AGENT_IMAGE_H", 864),
        "dump_dir": utils.get_env_str("AGENT_DUMP_DIR", "dumps"),
        "dump_prefix": utils.get_env_str("AGENT_DUMP_PREFIX", "screen_"),
        "dump_start": utils.get_env_int("AGENT_DUMP_START", 1),
        "keep_last_screenshots": utils.get_env_int("AGENT_KEEP_LAST_SCREENSHOTS", 2),
        "keep_last_thinks": utils.get_env_int("AGENT_KEEP_LAST_THINKS", 2),
        "max_steps": utils.get_env_int("AGENT_MAX_STEPS", 200),
        "step_delay": utils.get_env_float("AGENT_STEP_DELAY", 0.4),
    }

    os.makedirs(cfg["dump_dir"], exist_ok=True)

    # Initialize HTTP logging
    out_dir = Path(__file__).resolve().parent
    log_file = out_dir / f"agent_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    utils.init_http_logger(log_file)
    print(f"Logging to: {log_file}")

    try:
        out = run_agent(scenarios.SYSTEM_PROMPT, task_prompt, scenarios.TOOLS_SCHEMA, cfg)
        if out:
            print(out)
        print(f"\nComplete log saved to: {log_file}")

    except Exception as e:
        print(f"\nException occurred: {e}", file=sys.stderr)
        print(f"Partial log saved to: {log_file}")
        raise


if __name__ == "__main__":
    main()
