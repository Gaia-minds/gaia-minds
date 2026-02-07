#!/usr/bin/env python3
"""Import shim for environments where symlinks are not preserved.

Keeps `import agent_alignment` working by loading the canonical
`agent-alignment.py` module from disk.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


_IMPL_PATH = Path(__file__).with_name("agent-alignment.py")


def _load_impl() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gaia_agent_alignment_impl", _IMPL_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load alignment module from {_IMPL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()

# Re-export public API expected by agent-loop and tests.
for _name in dir(_IMPL):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_IMPL, _name)


if __name__ == "__main__":
    if hasattr(_IMPL, "_self_test"):
        raise SystemExit(_IMPL._self_test())
    raise SystemExit("Alignment module self-test entrypoint not found")
