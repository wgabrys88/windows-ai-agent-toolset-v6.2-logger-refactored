# FILE: utils.py

from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# HTTP logging setup
# -----------------------------

_http_logger = None

def init_http_logger(log_file: Path) -> None:
    global _http_logger
    _http_logger = logging.getLogger('http_exchange')
    _http_logger.setLevel(logging.INFO)
    _http_logger.handlers.clear()
    handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(message)s'))
    _http_logger.addHandler(handler)
    _http_logger.propagate = False


# -----------------------------
# Common JSON payload helpers
# -----------------------------

def ok_payload(extra: Optional[Dict[str, Any]] = None) -> str:
    d: Dict[str, Any] = {"ok": True}
    if extra:
        d.update(extra)
    return json.dumps(d, ensure_ascii=True, separators=(",", ":"))


def err_payload(error_type: str, message: str) -> str:
    return json.dumps(
        {"ok": False, "error": {"type": error_type, "message": message}},
        ensure_ascii=True,
        separators=(",", ":"),
    )


def parse_args(arg_str: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Tool arguments may arrive as:
      - dict (already parsed)
      - JSON string
      - None
    Returns: (args_dict, err_json_string_or_None)
    """
    if arg_str is None:
        return {}, None
    if isinstance(arg_str, dict):
        return arg_str, None
    if not isinstance(arg_str, str):
        return None, err_payload("invalid_args", "arguments must be a dict or JSON string")

    try:
        val = json.loads(arg_str) if arg_str else {}
    except json.JSONDecodeError as e:
        return None, err_payload("invalid_json", f"arguments must be valid JSON: {e}")

    if not isinstance(val, dict):
        return None, err_payload("invalid_args", "arguments JSON must parse to an object")

    return val, None


# -----------------------------
# Box parsing (robust)
# -----------------------------

def parse_box(box: Any) -> Tuple[Optional[Tuple[float, float, float, float]], Optional[str]]:
    """
    Parse click/region targets in normalized 0-1000 coordinates.

    Accepted formats:
      - Point: [x, y]
      - Flat bbox: [x1, y1, x2, y2]
      - Legacy bbox: [[x1, y1], [x2, y2]]

    Returns: (x1, y1, x2, y2) clamped to [0,1000], or (None, err_json).
    """

    def clamp(v: float) -> float:
        return max(0.0, min(1000.0, v))

    try:
        # Point: [x, y]
        if (
            isinstance(box, list)
            and len(box) == 2
            and all(isinstance(v, (int, float)) for v in box)
        ):
            x, y = clamp(float(box[0])), clamp(float(box[1]))
            return (x, y, x, y), None  # zero-area bbox; center == point

        # Flat bbox: [x1, y1, x2, y2]
        if (
            isinstance(box, list)
            and len(box) == 4
            and all(isinstance(v, (int, float)) for v in box)
        ):
            x1, y1, x2, y2 = map(float, box)
            x1, y1, x2, y2 = clamp(x1), clamp(y1), clamp(x2), clamp(y2)
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            return (x1, y1, x2, y2), None

        # Legacy bbox: [[x1,y1],[x2,y2]]
        if not isinstance(box, list) or len(box) != 2:
            return None, err_payload(
                "invalid_box",
                "box must be [x,y], [x1,y1,x2,y2], or [[x1,y1],[x2,y2]]",
            )

        p1, p2 = box
        if (
            not (isinstance(p1, list) and isinstance(p2, list))
            or len(p1) != 2
            or len(p2) != 2
        ):
            return None, err_payload(
                "invalid_box",
                "box must be [x,y], [x1,y1,x2,y2], or [[x1,y1],[x2,y2]]",
            )

        x1, y1 = float(p1[0]), float(p1[1])
        x2, y2 = float(p2[0]), float(p2[1])

        x1, y1, x2, y2 = clamp(x1), clamp(y1), clamp(x2), clamp(y2)
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        return (x1, y1, x2, y2), None

    except (TypeError, ValueError) as e:
        return None, err_payload("invalid_box", f"coordinates must be numbers: {e}")


def box_center(x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


# -----------------------------
# Agent message hygiene
# -----------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    return _THINK_RE.sub("", text).strip()


def prune_old_screenshots(messages: List[Dict[str, Any]], keep_last: int) -> List[Dict[str, Any]]:
    idxs = []
    for i, m in enumerate(messages):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if not isinstance(c, list):
            continue
        if any(isinstance(p, dict) and p.get("type") == "image_url" for p in c):
            idxs.append(i)

    if len(idxs) <= keep_last:
        return messages

    for i in idxs[:-keep_last]:
        messages[i]["content"] = "captured image data (omitted)"
    return messages


def prune_old_thinks(messages: List[Dict[str, Any]], keep_last: int) -> List[Dict[str, Any]]:
    idxs = []
    for i, m in enumerate(messages):
        if m.get("role") != "assistant":
            continue
        c = m.get("content")
        if isinstance(c, str) and "<think>" in c and "</think>" in c:
            idxs.append(i)

    if len(idxs) <= keep_last:
        return messages

    for i in idxs[:-keep_last]:
        c = messages[i].get("content")
        if isinstance(c, str):
            messages[i]["content"] = _THINK_RE.sub("", c).strip()
    return messages


# -----------------------------
# Image data truncation (optional, for cleaner logs)
# -----------------------------

def summarize_data_image_url(url: str) -> str:
    if not isinstance(url, str) or not url.startswith("data:image/"):
        return url
    comma = url.find(",")
    if comma == -1:
        return url
    header = url[: comma + 1]
    payload = url[comma + 1:]
    if len(payload) < 100:
        return url
    sha = hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"{header}[b64 sha={sha} len={len(payload)}]"


def truncate_base64_images(obj: Any) -> Any:
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "url" and isinstance(v, str):
                obj[k] = summarize_data_image_url(v)
            else:
                truncate_base64_images(v)
    elif isinstance(obj, list):
        for it in obj:
            truncate_base64_images(it)
    return obj


# -----------------------------
# HTTP helper with logging
# -----------------------------

def post_json(payload: Dict[str, Any], endpoint: str, timeout: int) -> Dict[str, Any]:
    global _http_logger
    
    # Log request
    if _http_logger:
        _http_logger.info("=" * 80)
        _http_logger.info("REQUEST TO MODEL:")
        _http_logger.info("=" * 80)
        logged_payload = truncate_base64_images(json.loads(json.dumps(payload)))

        logged_payload["tools"] = "[TOOLS DEFINITIONS TRUNCATED FOR LOG READABILITY]"
        logged_payload["messages"][0]["content"] = "[SYSTEM PROMPT TRUNCATED FOR LOG READABILITY]"
        logged_payload["messages"][1]["content"] = "[INITIAL USER TASK PROMPT TRUNCATED FOR LOG READABILITY]"


        # # Compact & clean JSON dump (pretty base + remove useless brace/empty lines)
        json_str = json.dumps(logged_payload, indent=2, ensure_ascii=True)
        # clean_json = '\n'.join(
        #     line for line in json_str.splitlines()
        #     if line.rstrip() and not re.match(r'^\s*[\{\}\[\]],?\s*$', line.rstrip())
        # )

        # Two-pass cleanup (concise one-liner with multiple conditions)
        clean_json = '\n'.join(
            line for line in json_str.splitlines()
            if line.rstrip()  # skip empty/whitespace-only lines
            and not re.match(r'^\s*[{\}\[\]],?\s*$', line.rstrip())  # skip brace/bracket + optional comma lines
            and not re.match(r'^\s*,\s*$', line.rstrip())             # skip pure comma lines (if any)
        )


        _http_logger.info(clean_json)
        _http_logger.info("")  # blank line separator
    
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        response = json.loads(resp.read().decode("utf-8"))
    
    # Log response
    if _http_logger:
        _http_logger.info("=" * 80)
        _http_logger.info("RESPONSE FROM MODEL:")
        _http_logger.info("=" * 80)
        _http_logger.info(json.dumps(response, indent=2, ensure_ascii=True))
        _http_logger.info("\n")
    
    return response


# -----------------------------
# Env helpers (used in main.py)
# -----------------------------

def get_env_str(name: str, default: str) -> str:
    import os
    v = os.environ.get(name, "").strip()
    return v if v else default


def get_env_int(name: str, default: int) -> int:
    import os
    v = os.environ.get(name, "").strip()
    return default if not v else int(v)


def get_env_float(name: str, default: float) -> float:
    import os
    v = os.environ.get(name, "").strip()
    return default if not v else float(v)
