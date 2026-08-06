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
    """No name networkx exposes as a function may be a module on fnx's side.

    br-r37-c1-0ouoj. The reference is NETWORKX, not a snapshot of fnx taken
    before the aliasing runs. A snapshot is order-dependent and silently
    vacuous: in a broad run another test has usually imported
    `franken_networkx.algorithms.<sub>` already, so a clobbered name is a module
    by the time the snapshot is taken, is excluded from it, and is never
    asserted on. Verified vacuous by re-introducing the dispersion clobber with
    the child module pre-imported — the snapshot form passed.

    networkx's own namespace cannot drift with our import order, so this form
    holds whatever ran first.
    """
    try:
        top = importlib.import_module(f"franken_networkx.{sub}")
    except ImportError:
        top = importlib.import_module(f"franken_networkx.algorithms.{sub}")

    try:
        reference = importlib.import_module(f"networkx.algorithms.{sub}")
    except ImportError:
        pytest.skip(f"no networkx.algorithms.{sub}")

    # Trigger the child-aliasing by importing the algorithms submodule.
    try:
        importlib.import_module(f"franken_networkx.algorithms.{sub}")
    except ImportError:
        pytest.skip(f"no algorithms.{sub}")

    clobbered = []
    for name in dir(reference):
        if name.startswith("_"):
            continue
        their_object = getattr(reference, name, None)
        if inspect.ismodule(their_object) or not callable(their_object):
            continue
        if inspect.ismodule(getattr(top, name, None)):
            clobbered.append(name)

    assert clobbered == [], (
        f"networkx exposes {clobbered} as callables, but franken_networkx.{sub} "
        f"has a child MODULE of that name — `fnx.{sub}.<name>(...)` raises "
        f"'module is not callable'"
    )


def test_known_at_risk_functions_stay_callable():
    # The two known function-vs-child-module collisions, post-import.
    import franken_networkx.algorithms.centrality  # noqa: F401
    import franken_networkx.algorithms.isomorphism  # noqa: F401
    assert callable(fnx.centrality.dispersion)
    assert callable(fnx.isomorphism.tree_isomorphism)
