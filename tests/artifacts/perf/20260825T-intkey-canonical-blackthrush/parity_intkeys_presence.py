"""has_node / __contains__ parity vs LIVE networkx, INT keys on a REMAPPED store.

The widening lets an int key reach the value-keyed presence cache
(`exact_str_node_is_present`) that previously only exact `str` could enter. Two
risks follow, and both are NEGATIVE cases:

  1. STALENESS - a cached "present" answer must not survive the removal of that
     node. The cache is generation-guarded by nodes_seq; an int entry is a path
     that guard has never carried before.
  2. KEY COLLAPSE - Python hashes 1, 1.0 and True equal. The cache is keyed by
     the Python object, so if bool or float were admitted they could read an
     entry written for int 1. `node_key_can_use_index_lookaside` admits exact
     int and exact str only, and this asserts that the exclusion holds through
     the cache rather than trusting the gate.

Every answer is compared against networkx on a graph whose node indices have
been renumbered by removals, so the identity-int fast path cannot mask the
lookaside.
"""
import networkx as nx
import franken_networkx as fnx

failures = []
n_checks = 0


def check(name, got, want):
    global n_checks
    n_checks += 1
    if got != want:
        failures.append(f"{name}: fnx={got!r} nx={want!r}")


class MyInt(int):
    pass


PROBES = [0, 1, -1, 5, 7, 42, 399, 400, 12345, -12345,
          2**62, 2**63 - 1, -(2**63), 2**63, -(2**63) - 1,
          True, False, 1.0, 0.0, 5.0, "5", "1", "0", MyInt(7), MyInt(42),
          None, 3.5, -0.0]


def remapped(mod, cls, n=120):
    g = getattr(mod, cls)()
    g.add_nodes_from(range(n))
    g.add_edges_from((i, (i * 7 + 3) % n) for i in range(n))
    victims = list(range(0, n, 7))
    g.remove_nodes_from(victims)
    g.add_nodes_from(victims)
    g.add_edges_from((v, (v + 1) % n) for v in victims)
    return g


for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
    G, F = remapped(nx, cls), remapped(fnx, cls)
    check(f"{cls} node count", F.number_of_nodes(), G.number_of_nodes())
    check(f"{cls} node set", sorted(map(repr, F.nodes)), sorted(map(repr, G.nodes)))

    for p in PROBES:
        # `in` must never raise for an unhashable-free probe, and must agree
        for label, fn_f, fn_n in (
            ("in", lambda p=p: p in F, lambda p=p: p in G),
            ("has_node", lambda p=p: F.has_node(p), lambda p=p: G.has_node(p)),
        ):
            try:
                a = ("ok", fn_n())
            except Exception as exc:  # noqa: BLE001
                a = (type(exc).__name__, repr(exc.args))
            try:
                b = ("ok", fn_f())
            except Exception as exc:  # noqa: BLE001
                b = (type(exc).__name__, repr(exc.args))
            check(f"{cls} {label}({p!r}) on remapped store", b, a)

    # NEGATIVE CASE 1: a warm cached HIT must not survive removal of that node.
    for victim in (5, 42, 399, 1):
        if victim not in G:
            continue
        check(f"{cls} warm {victim!r} before removal", victim in F, victim in G)
        G.remove_node(victim)
        F.remove_node(victim)
        check(f"{cls} {victim!r} AFTER removal must be absent", victim in F, victim in G)
        check(f"{cls} has_node({victim!r}) AFTER removal", F.has_node(victim), G.has_node(victim))
        # and re-adding must flip it back
        G.add_node(victim)
        F.add_node(victim)
        check(f"{cls} {victim!r} AFTER re-add", victim in F, victim in G)

    # NEGATIVE CASE 2: the 1 / 1.0 / True collapse must survive the cache.
    # Warm the cache on int 1, then ask with the aliases; Python hashes them
    # equal, so a value-keyed cache that admitted them would answer from int 1.
    G2, F2 = getattr(nx, cls)(), getattr(fnx, cls)()
    G2.add_node(1)
    F2.add_node(1)
    check(f"{cls} warm int 1", 1 in F2, 1 in G2)
    for alias in (1, 1.0, True, MyInt(1)):
        check(f"{cls} alias {alias!r} after warming int 1", alias in F2, alias in G2)
        check(f"{cls} has_node alias {alias!r}", F2.has_node(alias), G2.has_node(alias))
    # the reverse: a graph holding only "1" must NOT answer True for int 1
    G3, F3 = getattr(nx, cls)(), getattr(fnx, cls)()
    G3.add_node("1")
    F3.add_node("1")
    check(f"{cls} warm str '1'", "1" in F3, "1" in G3)
    for probe in (1, 1.0, True, "1"):
        check(f"{cls} str-graph probe {probe!r}", probe in F3, probe in G3)

    # NEGATIVE CASE 3: absent ints must stay absent after unrelated mutation.
    G4, F4 = remapped(nx, cls, n=40), remapped(fnx, cls, n=40)
    check(f"{cls} absent 9999 warm", 9999 in F4, 9999 in G4)
    for g in (G4, F4):
        g.add_node(9999)
    check(f"{cls} 9999 after add", 9999 in F4, 9999 in G4)
    for g in (G4, F4):
        g.remove_node(9999)
    check(f"{cls} 9999 after remove", 9999 in F4, 9999 in G4)

# comparator self-test
_b = len(failures)
check("SELFTEST", 1, 2)
assert len(failures) == _b + 1, "check() cannot detect a mismatch!"
failures.pop()
n_checks -= 1

print(f"has_node/__contains__ int-key parity: {n_checks} checks, {len(failures)} failures")
for f in failures[:40]:
    print("  " + f)
