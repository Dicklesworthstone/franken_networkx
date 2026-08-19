"""size(weight) must keep networkx's TWO-LEVEL summation order, not just its total.

br-r37-c1-7pzs9. networkx computes

    sum(d for _, d in G.degree(weight=w)) / 2

which is a compensated sum per node, then a second compensated sum over those
per-node totals, then a halving. fnx currently uses that same formula for every
non-integer weight, and the open bead proposes replacing it with a native
scalar kernel.

The tempting kernel — walk the edges once and add up the weights — is WRONG.
Float addition is not associative, so a single pass rounds differently: across
2000 random graphs it disagrees with networkx for 7% of plain uniform(0,1)
weights and 30% of wide-range weights, and the first counterexample found was a
5-node graph where networkx gives 9999999999991874.0 and one pass gives
9999999999991872.0.

That kind of kernel would pass any test written with round numbers, because
integers and short decimals are exactly representable and only diverge once the
compensation has something to compensate. So this file uses deliberately
adversarial weights, and `test_the_fixtures_can_actually_catch_a_one_pass_kernel`
asserts the fixtures still have that property — without it, the rest of the file
could pass against a broken kernel and no one would know.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

# Magnitudes chosen so the compensation is load-bearing: a wide range, values
# far apart in exponent, and a few that are exact so the sum is not uniformly
# fuzzy.
WEIGHTS = [1e16, 1e-16, 0.1, 3.5, -1e6, 1e-8, 123456.789, -0.30000000000000004]


def _adversarial(lib, class_name, seed, n=14):
    rng = random.Random(seed)
    graph = getattr(lib, class_name)()
    for i in range(n):
        graph.add_node("n%d" % i)
    for _ in range(3 * n):
        u = "n%d" % rng.randrange(n)
        v = "n%d" % rng.randrange(n)
        graph.add_edge(u, v, weight=rng.choice(WEIGHTS))
    graph.add_edge("n0", "n0", weight=rng.choice(WEIGHTS))  # self-loop
    return graph


@pytest.mark.parametrize("class_name", CLASSES)
def test_size_is_bit_identical_to_networkx_on_adversarial_floats(class_name):
    for seed in range(40):
        got = _adversarial(fnx, class_name, seed).size(weight="weight")
        want = _adversarial(nx, class_name, seed).size(weight="weight")
        assert repr(got) == repr(want), (
            "%s seed %d: size(weight) diverged from networkx\n"
            "  fnx: %r\n  nx : %r" % (class_name, seed, got, want)
        )


@pytest.mark.parametrize("class_name", CLASSES)
def test_degree_totals_are_bit_identical_to_networkx(class_name):
    """The per-node level of the same sum, which any kernel must also preserve."""
    for seed in range(20):
        got = {str(k): repr(v) for k, v in _adversarial(fnx, class_name, seed).degree(weight="weight")}
        want = {str(k): repr(v) for k, v in _adversarial(nx, class_name, seed).degree(weight="weight")}
        assert got == want, "%s seed %d: per-node weighted degree diverged" % (class_name, seed)


@pytest.mark.parametrize("class_name", CLASSES)
def test_the_fixtures_can_actually_catch_a_one_pass_kernel(class_name):
    """Guard on the guard: prove these fixtures distinguish the wrong kernel.

    A one-pass edge sum is what a native size(weight) kernel would most naturally
    do. If no fixture here separates it from networkx's two-level sum, then the
    tests above are vacuous and would greenlight it.
    """
    def one_pass(graph):
        if graph.is_multigraph():
            return sum(d.get("weight", 1) for _, _, d in graph.edges(data=True))
        return sum(d.get("weight", 1) for _, _, d in graph.edges(data=True))

    separated = 0
    for seed in range(40):
        graph = _adversarial(nx, class_name, seed)
        if repr(one_pass(graph)) != repr(graph.size(weight="weight")):
            separated += 1
    assert separated > 0, (
        "%s: NO fixture distinguishes a one-pass edge sum from networkx's "
        "two-level sum, so the parity tests above cannot catch that kernel — "
        "make the weights more adversarial" % class_name
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_size_refusal_boundaries_match_networkx(class_name):
    """Inputs a native kernel must refuse rather than approximate.

    Each of these is a case where summing in Rust would either lose precision or
    change the type of the arithmetic. Whatever the kernel does — answer or
    decline to the exact formula — the result has to be networkx's, exceptions
    included.
    """
    cases = {
        "int total past 2**53": [("a", "b", 2**53 + 1), ("a", "c", 2**53 + 3)],
        "bool weight": [("a", "b", True), ("a", "c", 3), ("a", "d", 1.5)],
        "string weight": [("a", "b", 1.5), ("a", "c", "not a number")],
        "float and bignum": [("a", "b", 2**53 + 1), ("a", "c", 0.5)],
        "negative and zero": [("a", "b", -0.0), ("a", "c", 0.0), ("a", "d", -2.5)],
        "infinity": [("a", "b", float("inf")), ("a", "c", 1.5)],
    }
    for name, edges in cases.items():
        got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
        for graph in (got, want):
            graph.add_node("lonely")
            for u, v, w in edges:
                graph.add_edge(u, v, weight=w)

        def outcome(graph):
            try:
                value = graph.size(weight="weight")
                return ("ok", repr(value), type(value).__name__)
            except Exception as exc:
                return ("raise", type(exc).__name__, exc.args)

        assert outcome(got) == outcome(want), "%s: %s diverged" % (class_name, name)


@pytest.mark.parametrize("class_name", CLASSES)
def test_a_weightless_edge_contributes_int_one(class_name):
    """`dd.get(weight, 1)` — the default is the INT 1, even beside floats."""
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        graph.add_edge("a", "b", weight=2.5)
        graph.add_edge("a", "c")
        graph.add_edge("d", "e")
    assert repr(got.size(weight="weight")) == repr(want.size(weight="weight"))
