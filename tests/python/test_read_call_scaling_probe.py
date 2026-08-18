"""The read-side scaling probe must detect a planted defect and survive a bad op.

br-r37-c1-9iro1 / br-r37-c1-6tuw8. ``scripts/read_call_scaling_probe.py`` is
a committed instrument that other agents will act on, so its own failure modes
need pinning. It has already produced one real finding (unweighted
``dict(G.degree())`` walking every node on both multigraph classes) and THREE
false ones from allocator noise, all disproved by hand. Both halves of that
record are what these tests protect.

WHAT IS PINNED:

  * A PLANTED O(parent) READ IS DETECTED. The probe is pointed at a deliberately
    defective callable whose cost tracks the graph size; it must report a ratio
    near the size ratio. Without this, "0 findings" across a sweep means nothing -
    a probe that can no longer see is indistinguishable from a clean codebase,
    which is the exact failure its own in-tool control note warns about.
  * A CLEAN READ IS NOT flagged, so the detector is not simply always-on.
  * AN UNSUPPORTED OPERATION IS REPORTED, NOT FATAL. A raise inside one thunk
    used to abort the whole class - a crash on ``common_neighbors`` for DiGraph
    cost an entire sweep's results before it was fixed.
  * THE MULTIPLICITY AXIS HOLDS THE NODE COUNT FIXED for multigraphs, which is
    the entire point of that axis: it isolates edge-set growth from node growth.
    If it ever starts adding nodes, every "flat" it reports is meaningless.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Locate the probe from the PACKAGE, not from this file's path. During the
# 2026-08 build freeze the whole test tree is routinely copied elsewhere and run
# from there (the in-tree conftest refuses to run against a stale .so), and a
# parents[2] walk from __file__ resolves to the wrong root in that setup.
import franken_networkx as _fnx_pkg

REPO = Path(_fnx_pkg.__file__).resolve().parents[2]
PROBE = REPO / "scripts" / "read_call_scaling_probe.py"


def _load():
    spec = importlib.util.spec_from_file_location("read_call_scaling_probe", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load()


def _defective_read(graph):
    """A read whose cost tracks the parent, in Python. The planted defect."""

    def call():
        return sum(1 for _ in graph)

    return call


def _clean_read(graph):
    """A read that does not touch the parent's size."""
    nodes = list(graph)

    def call():
        return nodes[0]

    return call


def test_a_planted_o_parent_read_is_detected():
    small = probe.build("Graph", 100)
    large = probe.build("Graph", 400)
    a = probe.total_calls(_defective_read(small), 5)
    b = probe.total_calls(_defective_read(large), 5)
    ratio = b / max(a, 1)
    assert ratio > 2.0, (
        f"the probe failed to see a planted O(parent) read (ratio {ratio:.2f}); "
        "every '0 finding(s)' it has ever reported is now suspect"
    )
    assert 2.5 < ratio < 5.5, f"ratio {ratio:.2f} should be near the 4x size ratio"


def test_a_clean_read_is_not_flagged():
    small = probe.build("Graph", 100)
    large = probe.build("Graph", 400)
    a = probe.total_calls(_clean_read(small), 5)
    b = probe.total_calls(_clean_read(large), 5)
    assert b / max(a, 1) < 1.3, "a constant-cost read must read flat"


@pytest.mark.parametrize("measure", ["total_calls", "total_allocations"])
def test_an_unsupported_operation_is_reported_not_fatal(measure):
    """A raise in one thunk must not abort the sweep."""

    def boom():
        raise NotImplementedError("not implemented for this class")

    with pytest.raises(probe.Unsupported):
        getattr(probe, measure)(boom, 3)


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_the_multiplicity_axis_holds_the_node_count_fixed(cls):
    small = probe.build(cls, 200, axis="multiplicity")
    large = probe.build(cls, 800, axis="multiplicity")
    assert len(small) == len(large), (
        "the multiplicity axis must grow only the edge set; if the node count "
        "moves, it is measuring the same thing as the nodes axis"
    )
    assert large.number_of_edges() > small.number_of_edges()


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_the_nodes_axis_actually_grows_nodes(cls):
    small = probe.build(cls, 200, axis="nodes")
    large = probe.build(cls, 800, axis="nodes")
    assert len(large) > len(small)


def test_the_control_sets_are_disjointly_purposed():
    """Positive controls are for the call metric; result-scaling for allocations."""
    assert probe.CONTROLS, "the probe needs at least one positive control"
    assert probe.NATIVE_SCAN_EXHIBITS, "the native-scan caveat exhibit is required"
    # dict(G.degree()) is the caveat exhibit AND legitimately allocates O(N)
    assert probe.NATIVE_SCAN_EXHIBITS <= probe.RESULT_SCALES_WITH_PARENT
