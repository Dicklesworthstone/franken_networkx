"""br-r37-c1-cnwof — how many freshness tokens one edges(nbunch) call costs.

`list(G.edges([n]))` is 0.388x-0.607x against networkx across the four classes,
the worst Python-side primitive left. cProfile at 20000 calls attributes a
sixth of it to one helper being called FOUR times per call:

    _edge_list_freshness_token   80000 calls for 20000 ops   = 4 per op (DiGraph)
    getattr                     340002                       = 17 per op

Counted per class, the tokens are Graph 1, DiGraph 4, MultiGraph 4,
MultiDiGraph 5 — Graph takes the lazy per-row walk and the rest do not, so the
cheap path already exists and is simply gated to one class.

Each token reads two native revision counters and re-runs
`_has_networkx_private_storage`, so four tokens is eight PyO3 crossings plus
four private-storage probes for a single edges() call. The call sites are the
live-view wrapper, `_guarded_edge_list`, `__len__` and `__iter__` — `list()`
asks for a length hint and then iterates, and each step re-derives the token
the previous one just computed.

THIS FILE DOES NOT FIX THAT. It pins the count as a budget, because the
freshness machinery is subtle — br-r37-c1-af0ig's `graph or fallback` truthiness
bug lived here, where an emptied graph is falsy and `clear()` silently skipped
the refresh — and a reduction has to be shown not to cost a staleness bug.

The budget cuts both ways. If someone lands the reduction the test fails and
tells them to lower the number; if a change quietly adds a fifth token per call,
it fails too. Either way the cost stops being invisible.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

# Measured on ELF ecfc2d30... : tokens per `list(G.edges([n]))`, PER CLASS.
# Graph needs ONE because it takes the lazy per-row walk; the other three fall
# through to the materialise path and pay four or five. Graph is therefore the
# existence proof that one is enough, and the lever is to widen that walk beyond
# its `type(self._graph) is Graph` gate (the br-r37-c1-aq6jv /
# br-r37-c1-8qxi9 threshold, which is still Graph-only).
# Lower is better; these are ceilings, not targets.
TOKEN_BUDGET = {
    "Graph": 1,
    "DiGraph": 4,
    "MultiGraph": 4,
    "MultiDiGraph": 5,
}


def _build(lib, cls_name, order=200):
    graph = getattr(lib, cls_name)()
    for i in range(order):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}", weight=1.0)
    return graph


def _count_tokens(callable_):
    """Count `_edge_list_freshness_token` invocations during one call."""
    calls = []
    original = fnx._edge_list_freshness_token

    def counting(graph):
        calls.append(graph)
        return original(graph)

    fnx._edge_list_freshness_token = counting
    try:
        callable_()
    finally:
        fnx._edge_list_freshness_token = original
    return len(calls)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_single_node_nbunch_edges_stays_within_its_token_budget(cls_name):
    """The budget. Fails high on a regression, fails low on the fix."""
    budget = TOKEN_BUDGET[cls_name]
    graph = _build(fnx, cls_name)
    count = _count_tokens(lambda: list(graph.edges(["n1"])))
    assert count <= budget, (
        f"{cls_name}: {count} freshness tokens per edges([n]) call, budget is "
        f"{budget} — something added a token to a path that already had enough"
    )
    if count < budget:
        pytest.fail(
            f"{cls_name}: down to {count} tokens per call from {budget}. That is "
            f"the intended improvement — lower TOKEN_BUDGET[{cls_name!r}] to "
            f"{count} and bank the ratio."
        )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_counter_is_not_vacuous(cls_name):
    """A budget over a helper nobody calls would pass for the wrong reason."""
    graph = _build(fnx, cls_name)
    assert _count_tokens(lambda: list(graph.edges(["n1"]))) > 0


@pytest.mark.parametrize("cls_name", CLASSES)
def test_edges_nbunch_results_match_networkx(cls_name):
    """Whatever the token count, the answer is networkx's.

    A reduction that skipped a refresh would show up here as a stale read, so
    this is the assertion any future lever has to keep passing.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for nbunch in (["n1"], ["n1", "n2"], ["n0"], []):
        want = list(gnx.edges(nbunch))
        got = list(gfx.edges(nbunch))
        assert got == want, (cls_name, nbunch)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_view_still_refreshes_after_mutation(cls_name):
    """The contract the tokens exist for — br-r37-c1-af0ig.

    Any reduction in token count must not reintroduce the staleness this
    machinery was added to fix, including the `clear()` case where an emptied
    graph is falsy.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    view_nx, view_fx = gnx.edges(["n1"]), gfx.edges(["n1"])
    assert list(view_fx) == list(view_nx)
    for graph in (gnx, gfx):
        graph.add_edge("n1", "brand-new")
    assert list(view_fx) == list(view_nx), "view went stale after add_edge"
    for graph in (gnx, gfx):
        graph.remove_edge("n1", "brand-new")
    assert list(view_fx) == list(view_nx), "view went stale after remove_edge"
    # After clear() the frozen nbunch node is gone, and networkx raises from
    # `adjdict[n]` rather than yielding nothing. A first draft of this asserted
    # `== []` and failed on all four classes — my expectation was wrong, not the
    # product: both libraries raise KeyError, which is the br-r37-c1-2pia7
    # frozen-nbunch contract.
    for graph in (gnx, gfx):
        graph.clear()
    outcomes = []
    for view in (view_nx, view_fx):
        try:
            outcomes.append(("ok", list(view)))
        except Exception as exc:  # noqa: BLE001
            outcomes.append((type(exc).__name__,))
    assert outcomes[1] == outcomes[0], "clear() behaviour diverged"
    assert outcomes[0][0] == "KeyError"
