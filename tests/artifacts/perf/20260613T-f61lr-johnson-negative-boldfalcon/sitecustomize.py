from __future__ import annotations

import importlib.util
import os
import sys


_EXTENSION_PATH = os.environ.get("FNX_EXTENSION_PATH")
if _EXTENSION_PATH and "franken_networkx._fnx" not in sys.modules:
    _SPEC = importlib.util.spec_from_file_location("franken_networkx._fnx", _EXTENSION_PATH)
    if _SPEC is None or _SPEC.loader is None:
        raise RuntimeError(f"cannot load FNX extension from {_EXTENSION_PATH}")
    _MODULE = importlib.util.module_from_spec(_SPEC)
    sys.modules["franken_networkx._fnx"] = _MODULE
    _SPEC.loader.exec_module(_MODULE)
