"""Audit: importing an algorithms submodule must not clobber public functions.

The algorithms package aliases nx child modules under each fnx-overridden
submodule (``_alias_nx_child_modules``). That aliasing must NOT overwrite a
same-named public FUNCTION with a child MODULE -- e.g. ``fnx.centrality`` has a
``dispersion`` centrality function AND a ``dispersion.py`` child module, and
``fnx.isomorphism`` has ``tree_isomorphism``. Clobbering them breaks
``fnx.<sub>.<fn>(...)`` ("module not callable").

This sweeps every child-aliased member, imports its algorithms submodule (which
triggers the aliasing), and asserts no attribute that was a callable function
became a module. Guards br-r37-c1-0ouoj (centrality.dispersion) and
br-r37-c1-nhbni (isomorphism.tree_isomorphism) against regression for the whole
class.

No mocks: real fnx.
"""

from __future__ import annotations

import importlib
import inspect
import re

import pytest
import franken_networkx as fnx

# The child-aliased members, parsed from the algorithms package source.
_SRC = (
    importlib.import_module("franken_networkx.algorithms").__file__
)
with open(_SRC) as _f:
    _ALIASED = sorted(set(re.findall(
        r'_alias_nx_child_modules\(\s*"networkx\.algorithms\.(\w+)"', _f.read()
    )))


@pytest.mark.parametrize("sub", _ALIASED)
def test_importing_submodule_does_not_clobber_functions(sub):
    try:
        top = importlib.import_module(f"franken_networkx.{sub}")
    except ImportError:
        top = importlib.import_module(f"franken_networkx.algorithms.{sub}")

    # Snapshot which public attributes are callable functions (not modules).
    functions = {
        n for n in dir(top)
        if not n.startswith("_")
        and callable(getattr(top, n, None))
        and not inspect.ismodule(getattr(top, n, None))
    }

    # Trigger the child-aliasing by importing the algorithms submodule.
    try:
        importlib.import_module(f"franken_networkx.algorithms.{sub}")
    except ImportError:
        pytest.skip(f"no algorithms.{sub}")

    # No function may have been replaced by a module.
    for n in functions:
        assert not inspect.ismodule(getattr(top, n, None)), (
            f"{sub}.{n} was clobbered from a function into a module"
        )


def test_known_at_risk_functions_stay_callable():
    # The two known function-vs-child-module collisions, post-import.
    import franken_networkx.algorithms.centrality  # noqa: F401
    import franken_networkx.algorithms.isomorphism  # noqa: F401
    assert callable(fnx.centrality.dispersion)
    assert callable(fnx.isomorphism.tree_isomorphism)
