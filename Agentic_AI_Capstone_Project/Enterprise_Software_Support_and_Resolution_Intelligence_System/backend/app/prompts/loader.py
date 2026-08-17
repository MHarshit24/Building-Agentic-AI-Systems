"""
app/prompts/loader.py

§32.4's promotion mechanism, built for real: "promotion is a one-line
config change (ACTIVE_PROMPT_VERSION in config.py), not a code rewrite —
so rollback to v(n) if v(n+1) regresses any SLO is equally a one-line
revert." Before this module existed, every node hardcoded a direct
import of its own _v1 module (e.g. `from app.prompts.reflect_v1 import
build_prompt`) at the top of the file — a static, import-time binding
that promotion could never actually switch without editing source.

get_build_prompt(agent_name) resolves "<agent_name>_<version>" into the
real module and returns its build_prompt function, reading
active_prompt_version fresh via get_settings() each call (cheap —
lru_cache'd) rather than caching the resolved function at import time,
so a version bump takes effect on the next process start with no other
change — the same "no source-code edit needed" property calibrated_
thresholds.json's override already has.

Deliberately NOT called at each node's module import time (that would
just move the static binding from "hardcoded _v1" to "hardcoded whatever
version was active when the process started importing modules," which
happens to be the same thing in practice but is fragile if import order
or lazy imports ever change) — every node calls this inside its own node
function body instead, at actual invocation time.
"""

from __future__ import annotations

import importlib
from typing import Callable

from app.config import get_settings


def get_build_prompt(agent_name: str) -> Callable:
    """agent_name: the prompt file's own stem before the version suffix
    (e.g. "classify" for classify_v1.py/classify_v2.py). Raises
    ModuleNotFoundError if active_prompt_version names a version that
    doesn't exist for this agent — a real, actionable failure (a bad
    promotion) rather than silently falling back to some other version."""
    version = get_settings().active_prompt_version
    module = importlib.import_module(f"app.prompts.{agent_name}_{version}")
    return module.build_prompt
