"""Systematic drop-in divergence hunt: fnx vs live networkx across the public f(G) surface.

No build and no worker needed - this exercises the installed extension against the
installed networkx 3.6.1, which is the incumbent users actually have.

Method, following the one that produced br-r37-c1-vbe1o's 368-cell sweep:
  * every public function callable as f(G), on four graph classes;
  * outcomes compared by VALUE, and exceptions by TYPE **and ARGS** - a type-only sweep
    reports false green, which cost a previous sweep its credibility;
  * a FRESH graph per call for both arms, because networkx mutates its input in at least
    one place (minimum_branching materialises `default` onto the caller's edges), and a
    reused graph makes later comparisons meaningless;
  * results normalised structurally so graph returns compare by nodes/edges rather than
    object identity.

Reports only DIVERGENCES. Anything it prints is a candidate drop-in defect, not a
performance row.
"""

import inspect
import math
import random
import signal
import sys

import networkx as nx

import franken_networkx as fnx

N = 14
BUDGET_S = 3.0


class Timeout(Exception):
    pass


signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(Timeout()))


def build(mod, cls, seed):
    rng = random.Random(seed)
    g = getattr(mod, cls)()
    labels = list(range(N))
    if seed % 2:
        rng.shuffle(labels)
    g.add_nodes_from(labels)
    for i in range(N):
        for _ in range(rng.choice([1, 2])):
            j = rng.randrange(N)
            if i != j:
                g.add_edge(labels[i], labels[j], weight=float(rng.randint(1, 5)))
    for node in g.nodes():
        g.nodes[node]["color"] = "r" if node % 2 else "b"
    return g


def norm(v, depth=0):
    if depth > 4:
        return "..."
    if isinstance(v, float):
        if math.isnan(v):
            return "nan"
        return round(v, 9)
    if isinstance(v, dict):
        return sorted((str(k), norm(x, depth + 1)) for k, x in v.items())
    if isinstance(v, (set, frozenset)):
        return sorted(map(str, v))
    if hasattr(v, "nodes") and hasattr(v, "edges"):
        return ("graph", sorted(map(str, v.nodes())), sorted(sorted(map(str, e)) for e in v.edges()))
    if isinstance(v, (list, tuple)):
        return [norm(x, depth + 1) for x in v]
    if hasattr(v, "__iter__") and not isinstance(v, str):
        # Do NOT swallow exceptions here. A lazy generator that raises on first
        # iteration must surface as a raise, not as ('ok', '?') - swallowing it made
        # this sweep report eager-vs-lazy guard differences as fnx "returning" where
        # networkx raised, which is the opposite of what is happening.
        return [norm(x, depth + 1) for x in list(v)[:200]]
    return v


def outcome(mod, name, cls, seed):
    signal.setitimer(signal.ITIMER_REAL, BUDGET_S)
    try:
        g = build(mod, cls, seed)
        return ("ok", norm(getattr(mod, name)(g)))
    except Timeout:
        return ("timeout",)
    except Exception as exc:  # noqa: BLE001 - the exception IS the observation
        return ("raise", type(exc).__name__, tuple(str(a) for a in exc.args))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def candidates():
    out = []
    for name in sorted(dir(nx)):
        if name.startswith("_"):
            continue
        f, g = getattr(nx, name, None), getattr(fnx, name, None)
        if not callable(f) or g is None or not callable(g):
            continue
        if inspect.isclass(f):
            continue
        try:
            sig = inspect.signature(f)
        except Exception:  # noqa: BLE001
            continue
        req = [
            p for p in sig.parameters.values()
            if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        if len(req) == 1:
            out.append(name)
    return out


def main():
    names = candidates()
    print(f"sweeping {len(names)} public f(G) functions x 4 classes x 3 seeds", file=sys.stderr)
    diverged = {}
    checked = 0
    for name in names:
        for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
            for seed in (0, 1, 2):
                checked += 1
                a = outcome(fnx, name, cls, seed)
                b = outcome(nx, name, cls, seed)
                if a[0] == "timeout" or b[0] == "timeout":
                    continue
                if a != b:
                    diverged.setdefault(name, []).append((cls, seed, a, b))
    print(f"\n{checked} comparisons, {len(diverged)} functions diverge\n")
    for name in sorted(diverged):
        rows = diverged[name]
        cls_seen = sorted({r[0] for r in rows})
        cls0, seed0, a, b = rows[0]
        print(f"=== {name}  ({len(rows)} cells: {', '.join(cls_seen)}) ===")
        print(f"    fnx: {str(a)[:150]}")
        print(f"    nx : {str(b)[:150]}")
    return diverged


if __name__ == "__main__":
    main()
