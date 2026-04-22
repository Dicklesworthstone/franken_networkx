"""Conformance tests: graph measures — fnx vs nx oracle."""

import inspect

import pytest
from conftest import assert_dicts_close


@pytest.mark.conformance
class TestMeasures:
    def test_average_neighbor_degree(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx),
            nx.average_neighbor_degree(G_nx),
            label="average_neighbor_degree",
        )

    def test_average_neighbor_degree_complete(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx),
            nx.average_neighbor_degree(G_nx),
            label="average_neighbor_degree_complete",
        )

    def test_average_neighbor_degree_signature_matches_networkx(self, fnx, nx):
        assert str(inspect.signature(fnx.average_neighbor_degree)) == str(
            inspect.signature(nx.average_neighbor_degree)
        )

    def test_average_neighbor_degree_directed_defaults_match_networkx(self, fnx, nx):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        edges = [(0, 1), (1, 2), (0, 2), (2, 3)]
        G_fnx.add_edges_from(edges)
        G_nx.add_edges_from(edges)
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx),
            nx.average_neighbor_degree(G_nx),
            label="average_neighbor_degree_directed_defaults",
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"source": "in"}, id="source-in"),
            pytest.param({"target": "in"}, id="target-in"),
            pytest.param({"source": "in", "target": "in"}, id="source-in-target-in"),
            pytest.param({"nodes": [0, 2]}, id="nodes-subset"),
        ],
    )
    def test_average_neighbor_degree_directed_variants_match_networkx(self, fnx, nx, kwargs):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        edges = [(0, 1), (1, 2), (0, 2), (2, 3)]
        G_fnx.add_edges_from(edges)
        G_nx.add_edges_from(edges)
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx, **kwargs),
            nx.average_neighbor_degree(G_nx, **kwargs),
            label=f"average_neighbor_degree_directed_variants_{kwargs}",
        )

    def test_average_neighbor_degree_weighted_matches_networkx(self, fnx, nx):
        G_fnx = fnx.path_graph(5)
        G_nx = nx.path_graph(5)
        for i, (u, v) in enumerate(G_fnx.edges()):
            G_fnx[u][v]["weight"] = i + 1
        for i, (u, v) in enumerate(G_nx.edges()):
            G_nx[u][v]["weight"] = i + 1
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx, weight="weight"),
            nx.average_neighbor_degree(G_nx, weight="weight"),
            label="average_neighbor_degree_weighted",
        )

    def test_average_neighbor_degree_backend_keyword_surface_matches_networkx(self, fnx, nx):
        G_fnx = fnx.path_graph(4)
        G_nx = nx.path_graph(4)

        for backend in (None, "networkx"):
            assert_dicts_close(
                fnx.average_neighbor_degree(G_fnx, backend=backend),
                nx.average_neighbor_degree(G_nx, backend=backend),
                label=f"average_neighbor_degree_backend_{backend}",
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.average_neighbor_degree(G_fnx, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.average_neighbor_degree(G_nx, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.average_neighbor_degree(G_fnx, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.average_neighbor_degree(G_nx, backend_kwargs={"x": 1})

    def test_average_neighbor_degree_invalid_mode_matches_networkx(self, fnx, nx):
        G_fnx = fnx.path_graph(4)
        G_nx = nx.path_graph(4)
        with pytest.raises((fnx.NetworkXError, nx.NetworkXError), match="only supported for directed graphs"):
            fnx.average_neighbor_degree(G_fnx, source="in")
        with pytest.raises(nx.NetworkXError, match="only supported for directed graphs"):
            nx.average_neighbor_degree(G_nx, source="in")
