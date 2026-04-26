"""Per-tool permission policy: allow / ask / deny + path & prefix lists.

Stored at ``~/.openagentic/permissions.json``. The CLI's existing confirm-on-
write behavior is preserved as the default ("ask" for write/delete, "allow"
for read/run_command). Enterprises that need stricter sandboxing can flip
``run_command`` to "ask" or "deny" via the ``/permissions`` slash command and
whitelist specific safe prefixes.

Decision pipeline for each tool call:

    1. policy == "deny"          → REFUSED
    2. matches deny_paths/prefixes → REFUSED
    3. matches allow_paths/prefixes → ALLOWED (skip confirm)
    4. policy == "allow"         → ALLOWED (skip confirm)
    5. policy == "ask"           → fall through to existing confirm_fn
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# The four tools we gate. Memory tools / "done" don't touch the user's machine
# and stay outside the policy surface.
GATED_TOOLS = ("read_file", "run_command", "write_file", "delete_file")
POLICIES = ("allow", "ask", "deny")

# Defaults preserve today's UX: writes & deletes prompt; reads & shell are open.
# Users tighten at deployment time via /permissions.
_DEFAULT_POLICY = {
    "read_file": "allow",
    "run_command": "allow",
    "write_file": "ask",
    "delete_file": "ask",
}

# Privilege-escalation binaries that always require user confirmation, even
# when run_command policy=allow or the command sits inside an allow_prefixes
# whitelist. Token-matched (not prefix-matched) so `sudoku` / `surprise`
# don't false-positive against `sudo` / `su`.
ROOT_COMMAND_BINARIES = frozenset({"sudo", "doas", "pkexec", "su"})


def _is_root_command(cmd: str) -> bool:
    """True if *cmd*'s first shell token is a privilege-escalation binary."""
    stripped = cmd.lstrip()
    if not stripped:
        return False
    # First token = whatever comes before the first whitespace.
    first = stripped.split(None, 1)[0]
    return first in ROOT_COMMAND_BINARIES


@dataclass
class ToolPolicy:
    policy: str = "ask"
    # For file-path tools: absolute path prefixes.
    allow_paths: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=list)
    # For run_command: command-line prefixes.
    allow_prefixes: list[str] = field(default_factory=list)
    deny_prefixes: list[str] = field(default_factory=list)


@dataclass
class PermissionsConfig:
    tools: dict[str, ToolPolicy] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _config_path() -> Path:
    base = os.environ.get("OPENAGENTIC_PERMISSIONS_PATH")
    if base:
        return Path(base).expanduser().resolve()
    return Path.home() / ".openagentic" / "permissions.json"


def _build_default() -> PermissionsConfig:
    cfg = PermissionsConfig()
    for tool in GATED_TOOLS:
        cfg.tools[tool] = ToolPolicy(policy=_DEFAULT_POLICY[tool])
    return cfg


def load() -> PermissionsConfig:
    """Load config from disk, falling back to defaults on missing/corrupt file.

    Corrupt files are logged but NOT auto-overwritten — users can inspect and
    fix manually rather than silently losing their whitelist.
    """
    path = _config_path()
    if not path.is_file():
        return _build_default()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "permissions config unreadable (%s): %s — using defaults", path, exc,
        )
        return _build_default()

    cfg = _build_default()  # start from defaults so missing keys auto-fill
    tools_raw = raw.get("tools") or {}
    for tool in GATED_TOOLS:
        entry = tools_raw.get(tool) or {}
        policy = entry.get("policy")
        if policy not in POLICIES:
            policy = _DEFAULT_POLICY[tool]
        cfg.tools[tool] = ToolPolicy(
            policy=policy,
            allow_paths=list(entry.get("allow_paths") or []),
            deny_paths=list(entry.get("deny_paths") or []),
            allow_prefixes=list(entry.get("allow_prefixes") or []),
            deny_prefixes=list(entry.get("deny_prefixes") or []),
        )
    return cfg


def save(cfg: PermissionsConfig) -> Path:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tools": {k: asdict(v) for k, v in cfg.tools.items()}}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


# Decision codes returned by `decide` — strings keep the ReAct/tool layer
# free of importing this module's enum.
DECISION_ALLOW = "allow"
DECISION_DENY = "deny"
DECISION_ASK = "ask"


def _normalize_path(p: str) -> str:
    try:
        return str(Path(p).expanduser().resolve())
    except (OSError, RuntimeError):
        return p


def _path_match(target: str, candidates: list[str]) -> bool:
    """A path matches if it equals or sits beneath any candidate directory.

    We compare resolved absolute paths to avoid `..` / symlink trickery
    bypassing a deny rule.
    """
    norm_target = _normalize_path(target)
    for c in candidates:
        norm_c = _normalize_path(c)
        if norm_target == norm_c:
            return True
        # Treat candidate as a directory prefix
        if norm_target.startswith(norm_c.rstrip("/") + "/"):
            return True
    return False


def _prefix_match(cmd: str, prefixes: list[str]) -> bool:
    cmd_stripped = cmd.lstrip()
    return any(cmd_stripped.startswith(p) for p in prefixes)


def decide(
    tool: str,
    args: dict[str, Any],
    cfg: PermissionsConfig | None = None,
) -> tuple[str, str]:
    """Return (decision, reason). Decision is one of allow / deny / ask.

    `reason` is short user-facing copy explaining *why* — surfaced in the
    REFUSED tool result so the model can adapt rather than retry blindly.
    """
    if tool not in GATED_TOOLS:
        return DECISION_ALLOW, ""

    cfg = cfg or load()
    pol = cfg.tools.get(tool) or ToolPolicy(policy=_DEFAULT_POLICY[tool])

    if tool == "run_command":
        cmd = args.get("command", "") or ""
        if pol.deny_prefixes and _prefix_match(cmd, pol.deny_prefixes):
            return DECISION_DENY, "命中 deny_prefixes"
        # Root / privilege-escalation commands always require confirmation,
        # even if policy=allow or whitelisted — too dangerous to auto-run.
        if _is_root_command(cmd):
            return DECISION_ASK, "root 级命令强制确认"
        if pol.allow_prefixes and _prefix_match(cmd, pol.allow_prefixes):
            return DECISION_ALLOW, "命中 allow_prefixes"
    else:
        path = args.get("path", "") or ""
        if path:
            if pol.deny_paths and _path_match(path, pol.deny_paths):
                return DECISION_DENY, "命中 deny_paths"
            if pol.allow_paths and _path_match(path, pol.allow_paths):
                return DECISION_ALLOW, "命中 allow_paths"

    if pol.policy == "deny":
        return DECISION_DENY, "policy=deny"
    if pol.policy == "allow":
        return DECISION_ALLOW, "policy=allow"
    return DECISION_ASK, ""
