"""Installing private method shadows must not redo itself per assignment.

br-r37-c1-shwst. Which shadows an instance needs is decided entirely by two
booleans - is a node override present, is ANY private override present - plus the
class, and a live instance cannot change class. But a filtered view assigns THREE
private overrides at construction (adj, succ, pred) and every assignment re-ran
the whole install body, re-binding and re-storing an identical set of methods.
Measured at 21 ``install`` calls per MultiDiGraph view, of which 14 rebuilt what
the first seven had just made.

MEASURED, same-tree arms (scripts/make_python_arms.py, shared ELF, 46 diff lines
confined to __init__.py), each arm computing its own fnx-vs-networkx ratio
in-process, median with 10000-resample bootstrap CI, two passes with the arm
order reversed between them:

    workload                 HEAD baseline      with guard
    restricted_view ctor 200 0.2984 / 0.2942    0.3450 / 0.3538
    restricted_view ctor 800 0.2946 / 0.2969    0.3390 / 0.3527
    subgraph ctor 200        0.3185 / 0.3225    0.3746 / 0.3848
    subgraph ctor 800        0.3113 / 0.3152    0.3579 / 0.3664
    list(rv.nodes()) 800     0.9537 / 0.9670    0.9932 / 0.9931

WHAT THIS FILE PINS, and why the guard is not simply "already installed":

  * WIDENING. A later assignment can legitimately need MORE shadows - adding a
    node override after an adj override moves the state from (False, True) to
    (True, True) and genuinely requires has_node / number_of_nodes / order.
    A guard keyed on "previous is non-empty" would silently drop them, and every
    existing test would still pass because the first assignment installed a
    plausible-looking set.
  * A CALLER'S OWN METHOD IS NOT OURS TO RESTORE. If something replaced one of
    the shadows, the guard must fall through to ``install``, which has a per-name
    rule for that case.
  * THE SKIP ACTUALLY HAPPENS. Asserted by object identity of the recorded
    shadow dict: a redundant call must leave it alone, not rebuild an equal one.
    Without that, the lever could silently regress and only a benchmark would
    notice.
  * A COPY CAN NEVER SKIP AN INSTALL IT NEEDS. I assumed the ``_fnx_`` prefix
    kept this key out of copies; it does not, and the test below records what is
    actually true. What matters is narrower and is asserted directly: no copy
    may carry shadows bound to ANOTHER graph, and a copy without a shadow record
    cannot trip the guard at all, because the guard also requires a non-empty
    record. Both behaviours were confirmed IDENTICAL with and without this
    change by running the same probe under both arms.

NOT CLAIMED: ``DiGraph.reverse(copy=False)`` also assigns three overrides and is
NOT improved - measured 0.6314/0.6446 before and 0.6275/0.6147 after. It installs
ZERO shadows (nothing on that path is eligible), so the guard has nothing to
skip. That is asserted below too, so the claim stays honest if eligibility
changes.
"""

from __future__ import annotations

import copy
import pickle

import networkx as nx
import pytest

import franken_networkx as fnx

SHADOWS = "_fnx_private_node_method_shadows"
STATE = "_fnx_private_shadow_state"

DIRECTED = ["DiGraph", "MultiDiGraph"]
ALL = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls, n=20):
    g = getattr(lib, cls)()
    for i in range(n):
        g.add_edge("n%d" % i, "n%d" % ((i + 1) % n), w=i)
    return g


def _assign_adj(g):
    """Give the graph an assigned private adjacency, as networkx utilities do."""
    g._adj = {str(n): {} for n in g}


@pytest.mark.parametrize("cls", ALL)
def test_widening_the_state_installs_the_wider_set(cls):
    """THE bug a naive guard would introduce."""
    g = _build(fnx, cls)
    _assign_adj(g)
    after_adj = set(vars(g).get(SHADOWS) or {})
    assert vars(g).get(STATE) == (False, True)

    g._node = {str(n): {} for n in g}
    after_node = set(vars(g).get(SHADOWS) or {})
    assert vars(g).get(STATE) == (True, True)

    assert after_node >= after_adj, "widening lost a shadow it already had"
    for name in ("has_node", "number_of_nodes", "order"):
        assert name in after_node, f"{cls}: widening did not install {name}"


@pytest.mark.parametrize("cls", ALL)
def test_widened_shadows_actually_answer_from_the_assigned_store(cls):
    """Installed is not enough - the shadow must be the mapping-aware one."""
    g = _build(fnx, cls)
    x = _build(nx, cls)
    _assign_adj(g)
    extra = {str(n): {} for n in g}
    extra["only_in_assigned_store"] = {}
    g._node = extra
    x._node = dict(extra)
    assert g.has_node("only_in_assigned_store") == x.has_node("only_in_assigned_store")
    assert g.number_of_nodes() == x.number_of_nodes()
    assert g.order() == x.order()


@pytest.mark.parametrize("cls", ALL)
def test_a_replaced_shadow_is_not_clobbered(cls):
    g = _build(fnx, cls)
    _assign_adj(g)

    def mine(*args, **kwargs):
        return "MINE"

    g.has_edge = mine
    g._succ = {str(n): {} for n in g}  # a further assignment re-enters the installer
    assert g.has_edge("n0", "n1") == "MINE", "the caller's own method was replaced"


@pytest.mark.parametrize("cls", ALL)
def test_a_redundant_install_does_not_rebuild(cls):
    """THE LEVER, as behaviour: identity of the recorded shadow dict."""
    g = _build(fnx, cls)
    _assign_adj(g)
    storage = vars(g)
    recorded = storage.get(SHADOWS)
    if not recorded:
        pytest.skip(f"{cls} installs no shadows on this path")
    bound_before = dict(recorded)

    fnx._install_private_method_shadows(g, storage)

    assert storage.get(SHADOWS) is recorded, (
        f"{cls}: a redundant install rebuilt the shadow record - the guard is gone"
    )
    for name, bound in bound_before.items():
        assert storage[name] is bound, f"{cls}: {name} was re-bound needlessly"


@pytest.mark.parametrize("cls", ALL)
def test_state_change_does_rebuild(cls):
    """The control for the test above: a real change must NOT be skipped."""
    g = _build(fnx, cls)
    _assign_adj(g)
    storage = vars(g)
    if not storage.get(SHADOWS):
        pytest.skip(f"{cls} installs no shadows on this path")
    before = storage.get(SHADOWS)
    g._node = {str(n): {} for n in g}
    assert storage.get(SHADOWS) is not before, "widening reused the old record"


@pytest.mark.parametrize("cls", ALL)
def test_a_copy_can_never_skip_an_install_it_needs(cls):
    """The guard must be unable to fire on a copy that lacks the shadows.

    I first asserted the state key does not survive a copy. That was wrong, and
    checking rather than assuming is the point: `copy()` carries the private
    override keys (including this one) but NOT the shadow record, while
    `deepcopy` carries the record with every method REBOUND to the copy. Both
    behaviours are identical with and without this guard - verified by running
    the same probe under both arms - so neither is something this lever
    introduced.

    What actually matters is the combination that would be dangerous: a copy
    inheriting a recorded state while its shadows are missing or bound to the
    ORIGINAL graph. The first cannot skip anything, because the guard also
    requires a non-empty record. The second would be a live bug, so it is
    asserted directly.
    """
    g = _build(fnx, cls)
    _assign_adj(g)
    assert STATE in vars(g)
    made_by = {
        "copy()": g.copy(),
        "copy.copy": copy.copy(g),
        "deepcopy": copy.deepcopy(g),
        "pickle": pickle.loads(pickle.dumps(g)),
    }
    for label, made in made_by.items():
        record = vars(made).get(SHADOWS) or {}
        for name, bound in record.items():
            owner = getattr(bound, "__self__", None)
            assert owner is made, (
                f"{cls}/{label}: shadow {name} is bound to another graph - the "
                "guard would keep it instead of re-installing"
            )
        if not record:
            # No record means the guard cannot fire, whatever the state says.
            assert vars(made).get(SHADOWS) in (None, {}), "unreachable"

    # And the copy still routes through its OWN assigned store afterwards.
    fresh = g.copy()
    fresh._adj = {"ZZ": {}}
    assert sorted(map(str, fresh._adj)) == ["ZZ"]


@pytest.mark.parametrize("cls", ALL)
def test_view_construction_matches_networkx(cls):
    """The guard must not change what a constructed view reports."""
    got, want = _build(fnx, cls), _build(nx, cls)
    hidden = [str(n) for n in list(got)[:4]]
    keep = [str(n) for n in list(got)[:10]]
    pairs = [
        (fnx.restricted_view(got, hidden, []), nx.restricted_view(want, hidden, [])),
        (got.subgraph(keep), want.subgraph(keep)),
    ]
    for fv, xv in pairs:
        assert len(fv) == len(xv)
        assert sorted(str(n) for n in fv) == sorted(str(n) for n in xv)
        assert fv.number_of_edges() == xv.number_of_edges()
        for probe in ("n0", "n5", "absent"):
            assert (probe in fv) == (probe in xv)


@pytest.mark.parametrize("cls", DIRECTED)
def test_reverse_view_installs_no_shadows(cls):
    """Pins the NOT-CLAIMED note: reverse has nothing for the guard to skip."""
    g = _build(fnx, cls)
    rv = g.reverse(copy=False)
    assert not (vars(rv).get(SHADOWS) or {}), (
        "reverse(copy=False) now installs shadows - re-measure it before "
        "citing the ledger row that says the guard does not help it"
    )
