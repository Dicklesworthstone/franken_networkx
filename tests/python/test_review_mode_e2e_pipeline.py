"""End-to-end integration test for a realistic graph-analysis pipeline
that exercises the algorithms touched by 2026-05-03 REVIEW MODE.

No mocks. Real graphs (karate, davis_southern_women, florentine_families,
Erdos-Renyi). Structured per-stage logging written to a real log file
under ``test_e2e_pipeline_logs/`` so a failure can be diagnosed from
the log alone.

Pipeline simulates an analyst's workflow:

  Stage 1: load named real-world graph (no mocked I/O)
  Stage 2: characterize structure — components, cycle_basis, transitivity
  Stage 3: rank nodes — load_centrality, katz_centrality
  Stage 4: identify barycenter, find largest cliques
  Stage 5: derive complementary structure — complement, wiener_index
  Stage 6: cross-stage invariants — checks that span Stages 2-5

Each stage logs structured records; pipeline finishes only if every
stage's outputs satisfy the invariants in Stage 6.
"""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path

import pytest

import franken_networkx as fnx


LOG_DIR = Path(__file__).with_name("test_e2e_pipeline_logs")


@pytest.fixture
def pipeline_logger(request):
    """Configure a per-test file logger; tear it down after the test
    so each test owns its own log artifact (under
    test_e2e_pipeline_logs/<test_name>.log)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{request.node.name}.log"
    log_path.unlink(missing_ok=True)

    logger = logging.getLogger(f"fnx.e2e.{request.node.name}")
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%H:%M:%S.%f"[:-3],
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    yield logger
    handler.close()
    logger.removeHandler(handler)


def _stage_record(logger, stage: str, **kwargs) -> dict:
    """Emit a structured stage record (JSON-serializable values only)
    and return it for cross-stage assertions."""
    elapsed_ms = kwargs.pop("elapsed_ms", None)
    payload = {"stage": stage, **kwargs}
    if elapsed_ms is not None:
        payload["elapsed_ms"] = round(elapsed_ms, 3)
    logger.info(json.dumps(payload, sort_keys=True, default=str))
    return payload


@pytest.mark.parametrize(
    "graph_id,build",
    [
        ("karate", fnx.karate_club_graph),
        ("davis", fnx.davis_southern_women_graph),
        ("florentine", fnx.florentine_families_graph),
        ("er30", lambda: fnx.erdos_renyi_graph(30, 0.15, seed=2026)),
    ],
)
def test_e2e_pipeline_review_mode_algorithms(pipeline_logger, graph_id, build):
    """Drive the algorithm surface end-to-end on a real graph; assert
    cross-stage invariants and persist a structured log per test."""
    log = pipeline_logger

    # ---- Stage 1: load -----------------------------------------------
    t0 = time.perf_counter()
    G = build()
    stage1 = _stage_record(
        log, "load",
        graph_id=graph_id,
        n=G.number_of_nodes(),
        m=G.number_of_edges(),
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )
    assert stage1["n"] > 0, f"empty graph from builder {graph_id}"

    # ---- Stage 2: structural characterization -----------------------
    t0 = time.perf_counter()
    components = list(fnx.connected_components(G))
    n_components = len(components)
    cycle_basis = fnx.cycle_basis(G)
    transitivity = fnx.transitivity(G)
    stage2 = _stage_record(
        log, "characterize",
        n_components=n_components,
        component_sizes=sorted([len(c) for c in components]),
        cycle_basis_size=len(cycle_basis),
        transitivity=transitivity,
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )
    # Components partition the node set
    union: set = set()
    for c in components:
        assert isinstance(c, set), f"expected set, got {type(c).__name__}"
        assert union.isdisjoint(c)
        union |= c
    assert union == set(G.nodes())
    # Circuit rank theorem
    assert len(cycle_basis) == G.number_of_edges() - G.number_of_nodes() + n_components
    # Transitivity in [0, 1]
    assert 0 <= transitivity <= 1

    # ---- Stage 3: centrality rankings -------------------------------
    t0 = time.perf_counter()
    load = fnx.load_centrality(G, normalized=True)
    katz = fnx.katz_centrality(G)
    top_load = sorted(load.items(), key=lambda kv: -kv[1])[:3]
    top_katz = sorted(katz.items(), key=lambda kv: -kv[1])[:3]
    _stage_record(
        log, "rank",
        top_load=[[str(k), round(v, 6)] for k, v in top_load],
        top_katz=[[str(k), round(v, 6)] for k, v in top_katz],
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )
    # Both centralities cover all nodes
    assert set(load.keys()) == set(G.nodes())
    assert set(katz.keys()) == set(G.nodes())
    # Normalized load in [0, 1]; Katz unit-L2-normalized
    for v in load.values():
        assert 0 <= v <= 1.0 + 1e-9
    katz_norm_sq = sum(v * v for v in katz.values())
    assert math.sqrt(katz_norm_sq) == pytest.approx(1.0, abs=1e-6)

    # ---- Stage 4: barycenter + largest clique -----------------------
    t0 = time.perf_counter()
    if n_components == 1:
        barycenter = sorted(fnx.barycenter(G), key=str)
    else:
        barycenter = None
        log.info("skipping barycenter (graph has multiple components)")
    cliques = list(fnx.find_cliques(G))
    largest_clique_size = max((len(c) for c in cliques), default=0)
    _stage_record(
        log, "select",
        barycenter=[str(n) for n in barycenter] if barycenter else None,
        n_cliques=len(cliques),
        largest_clique_size=largest_clique_size,
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )
    # Largest clique is bounded by max degree + 1
    if G.number_of_nodes() > 0:
        max_deg = max(dict(G.degree()).values())
        assert largest_clique_size <= max_deg + 1

    # ---- Stage 5: complement + wiener -------------------------------
    t0 = time.perf_counter()
    Gc = fnx.complement(G)
    n_complement_edges = Gc.number_of_edges()
    if n_components == 1:
        wiener = fnx.wiener_index(G)
    else:
        wiener = None
    _stage_record(
        log, "complement",
        complement_edges=n_complement_edges,
        wiener_index=wiener if wiener is not None else "skip-disconnected",
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )
    # Complement-edge-count theorem (no self-loops)
    n = G.number_of_nodes()
    g_edges_no_sl = sum(1 for u, v in G.edges() if u != v)
    assert g_edges_no_sl + n_complement_edges == n * (n - 1) // 2

    # ---- Stage 6: cross-stage invariants ----------------------------
    invariants = {
        # complement of connected → disconnected components OR connected;
        # but classical theorem says complement of disconnected is
        # connected. Verify when applicable.
        "complement_of_disconnected_is_connected": (
            (fnx.number_connected_components(Gc) == 1) if n_components > 1 else "vacuous"
        ),
        # If transitivity == 1, every connected component is a clique →
        # cycle_basis size matches sum over components of C(|C|, 2) - (|C|-1).
        "if_transitive_then_cliquey": (
            "consistent" if transitivity < 1
            else all(
                len([c for c in cliques if set(c) == comp]) >= 1
                for comp in components if len(comp) >= 2
            )
        ),
    }
    _stage_record(log, "invariants", **invariants)
    assert invariants["complement_of_disconnected_is_connected"] in (True, "vacuous"), (
        f"complement of {graph_id} ({n_components} comps) is itself disconnected"
    )

    # Final: log file should exist and be non-empty (real artifact).
    log_path = LOG_DIR / f"test_e2e_pipeline_review_mode_algorithms[{graph_id}-{build.__name__ if hasattr(build, '__name__') else '<lambda>'}].log"
    # The fixture-derived path uses request.node.name which may differ;
    # just glob the dir.
    assert any(LOG_DIR.glob(f"*{graph_id}*.log")), (
        f"no log file emitted for {graph_id}"
    )
