"""Prototype: a cheaper _multigraph_collapse_min_weight_bellman (br-r37-c1-mg7hw).

Measured shape of the current loop, per edge: TWO dict lookups of the same key
(_attrs[weight] then _attrs.get(weight, 1)), a Python function call
(_sp_weight_type_survives_the_f64_kernel), a tuple-membership test inside it, and up to
three isinstance() calls. The collapse costs 41,482,743 Ir/call at N=800 - 17,284 Ir per
edge, 19% of it in _PyEval_EvalFrameDefault.

The redundancy that makes this safe: the loop's final gate is
`type(_val) in (int, float, bool)`, and _val IS _attrs[weight] whenever the validation
branch ran. So ANY type that is not exactly int/float/bool delegates regardless of what the
exotic-Real branch decides - that branch can only reach `return None, True` or fall through
to a check that also returns `None, True`. Collapsing it changes no outcome.

FNX_VARIANT=orig|opt selects the arm. Both are run against the same graph and their
(delegate flag, edge count, per-pair minimums) are asserted equal before any timing.
"""

import math as _math
import numbers as _numbers
import os
import sys

import franken_networkx as fnx

N = int(os.environ.get("FNX_N", "800"))
REPS = int(os.environ.get("IR_REPS", "10"))
VARIANT = os.environ.get("FNX_VARIANT", "orig")

_sp_survives = fnx._sp_weight_type_survives_the_f64_kernel


def collapse_orig(G, weight):
    """Verbatim transcription of the shipped loop."""
    simple = fnx.DiGraph() if G.is_directed() else fnx.Graph()
    simple.add_nodes_from(G)
    best = {}
    for _u, _v, _k, _attrs in G.edges(keys=True, data=True):
        if isinstance(_attrs, dict) and weight in _attrs:
            _value = _attrs[weight]
            _vt = type(_value)
            if _vt is int:
                pass
            elif _vt is float:
                if _math.isnan(_value) or _math.isinf(_value):
                    return None, True
            elif not isinstance(_value, bool):
                if not isinstance(_value, _numbers.Real):
                    return None, True
                if isinstance(_value, float) and (
                    _math.isnan(_value) or _math.isinf(_value)
                ):
                    return None, True
        _val = _attrs.get(weight, 1)
        if not _sp_survives(_val):
            return None, True
        _pair = (_u, _v)
        _cur = best.get(_pair)
        if _cur is None or _val < _cur:
            best[_pair] = _val
    simple.add_edges_from((_u, _v, {weight: _w}) for (_u, _v), _w in best.items())
    return simple, False


def collapse_opt(G, weight):
    """One lookup, one type check, no per-edge call."""
    simple = fnx.DiGraph() if G.is_directed() else fnx.Graph()
    simple.add_nodes_from(G)
    best = {}
    best_get = best.get
    isnan = _math.isnan
    isinf = _math.isinf
    for _u, _v, _k, _attrs in G.edges(keys=True, data=True):
        if isinstance(_attrs, dict) and weight in _attrs:
            _val = _attrs[weight]
        else:
            _val = _attrs.get(weight, 1)
        _vt = type(_val)
        if _vt is float:
            if isnan(_val) or isinf(_val):
                return None, True
        elif _vt is not int and _vt is not bool:
            # Not exactly int/float/bool: the shipped loop's final gate delegates on
            # this whatever its exotic-Real branch concluded, so short-circuit there.
            return None, True
        _pair = (_u, _v)
        _cur = best_get(_pair)
        if _cur is None or _val < _cur:
            best[_pair] = _val
    simple.add_edges_from((_u, _v, {weight: _w}) for (_u, _v), _w in best.items())
    return simple, False


def build(n):
    import random

    rng = random.Random(7)
    g = fnx.MultiDiGraph()
    for i in range(n):
        for d in (1, 2, 3):
            g.add_edge(f"n{i}", f"n{(i + d) % n}", weight=float(rng.randint(1, 9)))
    return g


g = build(N)

# Equivalence gate: both arms must agree before either is timed.
so, do_ = collapse_orig(g, "weight")
sp, dp = collapse_opt(g, "weight")
assert do_ == dp, (do_, dp)
assert (so is None) == (sp is None)
if so is not None:
    a = sorted((u, v, d["weight"]) for u, v, d in so.edges(data=True))
    b = sorted((u, v, d["weight"]) for u, v, d in sp.edges(data=True))
    assert a == b, "collapsed graphs differ"
    assert sorted(so.nodes()) == sorted(sp.nodes())
print(f"variant {VARIANT} N {N} reps {REPS} edges {len(a)} equivalence OK", file=sys.stderr)

fn = collapse_orig if VARIANT == "orig" else collapse_opt
for _ in range(REPS):
    fn(g, "weight")
