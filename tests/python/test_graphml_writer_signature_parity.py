"""Parity for write_graphml_xml / write_graphml_lxml signatures.

Self-review found the two GraphML writer aliases were missing
``infer_numeric_types`` in slot #5, even though the canonical
``write_graphml`` shipped with the kwarg already. Drop-in callers
hit ``TypeError: got an unexpected keyword argument
'infer_numeric_types'``. Aligned both wrappers to forward the kwarg
through to the core writer.
"""

from __future__ import annotations

import inspect
import pathlib
import tempfile

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
@pytest.mark.parametrize("fn_name", ["write_graphml_xml", "write_graphml_lxml"])
def test_writer_signatures_match_networkx(fn_name):
    fnx_sig = inspect.signature(getattr(fnx, fn_name))
    nx_sig = inspect.signature(getattr(nx, fn_name))
    fnx_params = list(fnx_sig.parameters.keys())
    nx_params = [
        k for k, v in nx_sig.parameters.items()
        if k not in ("backend", "backend_kwargs")
    ]
    assert fnx_params == nx_params
    # Confirm infer_numeric_types is at the documented position
    assert "infer_numeric_types" in fnx_params
    assert fnx_sig.parameters["infer_numeric_types"].default is False


@needs_nx
@pytest.mark.parametrize("fn_name", ["write_graphml_xml", "write_graphml_lxml"])
def test_writer_accepts_infer_numeric_types(fn_name):
    G = fnx.karate_club_graph()
    fn = getattr(fnx, fn_name)
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "g.graphml"
        # Must not raise on the kwarg
        try:
            fn(G, str(p), infer_numeric_types=True)
        except ImportError:
            # write_graphml_lxml may need lxml; skip in that case
            if "lxml" in fn_name:
                pytest.skip("lxml not available")
            raise
        # File should exist and be non-empty
        assert p.exists() and p.stat().st_size > 0


@needs_nx
def test_write_graphml_xml_positional_call_matches_networkx():
    """Positional call ordering must match nx so positional usage is
    identical."""
    G = fnx.karate_club_graph()
    with tempfile.TemporaryDirectory() as td:
        p1 = pathlib.Path(td) / "f.graphml"
        # Positional: G, path, encoding, prettyprint, infer_numeric_types
        fnx.write_graphml_xml(G, str(p1), "utf-8", True, False)
        assert p1.exists()
