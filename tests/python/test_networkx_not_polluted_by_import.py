"""br-r37-c1-azq59 — importing franken_networkx must not pollute networkx.

fnx mirrors networkx by star-importing its submodules and registering proxy
modules into ``sys.modules``. All of that machinery points one way, and if any
of it leaked backwards a user with both libraries imported would find networkx
quietly changed underneath them — the worst possible failure for a drop-in
replacement, because the symptom appears in code that never mentions fnx.

THE MEASUREMENT HAS TO HAPPEN IN A SUBPROCESS. By the time pytest collects this
file franken_networkx is already imported, so an in-process "before" snapshot
would be taken after the fact and pass vacuously. The sweep below therefore
runs a child interpreter that snapshots networkx BEFORE importing fnx, imports
fnx and every one of its submodules, snapshots again, and diffs by IDENTITY.

RESULT ON HEAD: exactly one name moves, in the three places it is exported, and
it is a deliberate documented shim. Everything else — 4500-odd attributes and
every ``sys.modules['networkx.*']`` entry — is untouched. That one exception is
allowlisted BY NAME and then pinned hard by
``test_the_one_allowed_patch_is_transparent_to_pure_networkx_callers``, so it
cannot quietly grow into a behavioural change.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import textwrap

import networkx as nx
import pytest

import franken_networkx  # noqa: F401 - the subject; also proves import works

# br-r37-c1-sg4dw patches nx.scale_free_graph so an fnx multidigraph may be
# passed as initial_graph. nx decorates it @_dispatchable(graphs=None), so the
# dispatcher never sees that argument and the body's isinstance guard rejects
# an fnx graph. The patch is applied to all three export paths.
ALLOWED_REBINDINGS = {
    ("networkx", "scale_free_graph"),
    ("networkx.generators", "scale_free_graph"),
    ("networkx.generators.directed", "scale_free_graph"),
}

_CHILD = textwrap.dedent(
    """
    import importlib, json, pkgutil, sys
    import networkx as nx

    def snapshot():
        out = {}
        for modname, mod in list(sys.modules.items()):
            if mod is None:
                continue
            if modname != "networkx" and not modname.startswith("networkx."):
                continue
            for attr in dir(mod):
                if attr.startswith("_"):
                    continue
                try:
                    out[modname + "|" + attr] = id(getattr(mod, attr))
                except Exception:
                    pass
        return out

    # Load networkx broadly first, so the baseline is wide rather than lazy.
    for info in pkgutil.iter_modules(nx.__path__):
        if info.name not in ("tests", "conftest"):
            try:
                importlib.import_module("networkx." + info.name)
            except Exception:
                pass

    before = snapshot()
    modules_before = {k: id(v) for k, v in sys.modules.items()
                      if k == "networkx" or k.startswith("networkx.")}

    import franken_networkx as fnx
    loaded = 0
    for pkg, path in (("franken_networkx", fnx.__path__),
                      ("franken_networkx.algorithms", fnx.algorithms.__path__)):
        for info in pkgutil.iter_modules(path):
            if info.name.startswith("_") or info.name == "tests":
                continue
            try:
                importlib.import_module(pkg + "." + info.name)
                loaded += 1
            except Exception:
                pass

    after = snapshot()
    modules_after = {k: id(v) for k, v in sys.modules.items()
                     if k == "networkx" or k.startswith("networkx.")}

    # networkx must still compute, with its own graph classes.
    g = nx.karate_club_graph()
    computed = {
        "cliques": len(list(nx.find_cliques(g))),
        "node_connectivity": nx.node_connectivity(g),
        "pagerank_max": round(max(nx.pagerank(g).values()), 9),
        "graph_class": type(g).__module__,
        "dispersion_callable": callable(nx.algorithms.centrality.dispersion),
    }

    print("@@RESULT@@" + json.dumps({
        "attributes_scanned": len(before),
        "submodules_imported": loaded,
        "rebound": sorted(k for k in before if k in after and before[k] != after[k]),
        "removed": sorted(k for k in before if k not in after),
        "hijacked_modules": sorted(k for k in modules_before
                                   if modules_after.get(k) != modules_before[k]),
        "computed": computed,
    }))
    """
)


@pytest.fixture(scope="module")
def coexistence():
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD],
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode == 0, f"child failed:\n{proc.stdout}\n{proc.stderr}"
    marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("@@RESULT@@")]
    assert marker, f"no result from child:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(marker[-1][len("@@RESULT@@") :])


def test_the_sweep_is_not_vacuous(coexistence):
    """A snapshot of nothing would pass this whole file for the wrong reason."""
    assert coexistence["attributes_scanned"] >= 3000, coexistence["attributes_scanned"]
    assert coexistence["submodules_imported"] >= 50, coexistence["submodules_imported"]


def test_importing_fnx_rebinds_no_unexpected_networkx_attribute(coexistence):
    """The core guard: identity of every public nx attribute is preserved."""
    rebound = {tuple(key.split("|", 1)) for key in coexistence["rebound"]}
    unexpected = rebound - ALLOWED_REBINDINGS
    assert not unexpected, (
        "importing franken_networkx rebound networkx attributes that are not on "
        f"the allowlist: {sorted(unexpected)}"
    )


def test_importing_fnx_removes_no_networkx_attribute(coexistence):
    assert coexistence["removed"] == [], coexistence["removed"]


def test_no_networkx_submodule_is_replaced_in_sys_modules(coexistence):
    """fnx registers proxies under franken_networkx.*; never over networkx.*."""
    assert coexistence["hijacked_modules"] == [], coexistence["hijacked_modules"]


def test_networkx_still_computes_with_its_own_classes(coexistence):
    """Identity-preservation is necessary but not sufficient — nx must still work."""
    computed = coexistence["computed"]
    reference = nx.karate_club_graph()
    assert computed["cliques"] == len(list(nx.find_cliques(reference)))
    assert computed["node_connectivity"] == nx.node_connectivity(reference)
    assert computed["pagerank_max"] == round(max(nx.pagerank(reference).values()), 9)
    assert computed["graph_class"] == "networkx.classes.graph"
    assert computed["dispersion_callable"], (
        "nx.algorithms.centrality.dispersion stopped being callable — the "
        "clobber class leaked into networkx itself"
    )


def test_the_allowlist_does_not_grow_silently(coexistence):
    """The allowlist may shrink, never grow, without someone editing this line."""
    assert len(ALLOWED_REBINDINGS) == 3
    assert {name for _mod, name in ALLOWED_REBINDINGS} == {"scale_free_graph"}


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 1234])
def test_the_one_allowed_patch_is_transparent_to_pure_networkx_callers(seed):
    """The exception is allowed because it changes IDENTITY and nothing else.

    A user who never touches fnx must get bit-identical graphs from
    nx.scale_free_graph. If this ever diverges, the allowlist entry above stops
    being a benign identity change and becomes real pollution.
    """
    patched = nx.scale_free_graph
    original = patched.__wrapped__
    assert original is not patched, "patch not applied — this test proves nothing"
    got = patched(60, seed=seed)
    want = original(60, seed=seed)
    assert sorted(got.edges()) == sorted(want.edges())
    assert sorted(got.nodes()) == sorted(want.nodes())
    assert type(got) is type(want)


def test_the_allowed_patch_preserves_the_networkx_function_contract():
    """Signature, identity metadata, dispatch attributes and the error contract."""
    patched = nx.scale_free_graph
    original = patched.__wrapped__
    assert inspect.signature(patched) == inspect.signature(original)
    assert patched.__name__ == original.__name__ == "scale_free_graph"
    assert patched.__module__ == "networkx.generators.directed"
    assert patched.__doc__ == original.__doc__
    for attr in ("orig_func", "name", "backends"):
        assert hasattr(patched, attr), f"dispatch attribute {attr} lost"
    # networkx's own rejection of a non-MultiDiGraph initial_graph must survive.
    with pytest.raises(nx.NetworkXError, match="initial_graph must be a MultiDiGraph"):
        nx.scale_free_graph(10, initial_graph=nx.path_graph(3))


def test_all_three_export_paths_got_the_same_patch():
    """Patching one path and not another would be worse than patching none.

    A user's behaviour would then depend on which import spelling they used.
    """
    assert (
        nx.scale_free_graph
        is nx.generators.scale_free_graph
        is nx.generators.directed.scale_free_graph
    )
