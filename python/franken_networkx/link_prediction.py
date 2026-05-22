"""FrankenNetworkX link prediction algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_link_prediction = _importlib.import_module("networkx.algorithms.link_prediction")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_link_prediction,
        "__all__",
        (
            "resource_allocation_index",
            "jaccard_coefficient",
            "adamic_adar_index",
            "preferential_attachment",
            "cn_soundarajan_hopcroft",
            "ra_index_soundarajan_hopcroft",
            "within_inter_cluster",
            "common_neighbor_centrality",
        ),
    )
)


def resource_allocation_index(G, ebunch=None, *, backend=None, **backend_kwargs):
    """Compute the resource allocation index for node pairs."""
    _fnx._validate_backend_dispatch_keywords(
        "resource_allocation_index", backend, backend_kwargs
    )
    return _fnx.resource_allocation_index(G, ebunch=ebunch)


def jaccard_coefficient(G, ebunch=None, *, backend=None, **backend_kwargs):
    """Compute the Jaccard coefficient for node pairs."""
    _fnx._validate_backend_dispatch_keywords(
        "jaccard_coefficient", backend, backend_kwargs
    )
    return _fnx.jaccard_coefficient(G, ebunch=ebunch)


def adamic_adar_index(G, ebunch=None, *, backend=None, **backend_kwargs):
    """Compute the Adamic-Adar index for node pairs."""
    _fnx._validate_backend_dispatch_keywords(
        "adamic_adar_index", backend, backend_kwargs
    )
    return _fnx.adamic_adar_index(G, ebunch=ebunch)


def preferential_attachment(G, ebunch=None, *, backend=None, **backend_kwargs):
    """Compute preferential attachment scores for node pairs."""
    _fnx._validate_backend_dispatch_keywords(
        "preferential_attachment", backend, backend_kwargs
    )
    return _fnx.preferential_attachment(G, ebunch=ebunch)


def cn_soundarajan_hopcroft(
    G, ebunch=None, community="community", *, backend=None, **backend_kwargs
):
    """Compute common-neighbor scores using community information."""
    _fnx._validate_backend_dispatch_keywords(
        "cn_soundarajan_hopcroft", backend, backend_kwargs
    )
    return _fnx.cn_soundarajan_hopcroft(
        G, ebunch=ebunch, community=community
    )


def ra_index_soundarajan_hopcroft(
    G, ebunch=None, community="community", *, backend=None, **backend_kwargs
):
    """Compute resource-allocation scores using community information."""
    _fnx._validate_backend_dispatch_keywords(
        "ra_index_soundarajan_hopcroft", backend, backend_kwargs
    )
    return _fnx.ra_index_soundarajan_hopcroft(
        G, ebunch=ebunch, community=community
    )


def within_inter_cluster(
    G,
    ebunch=None,
    delta=0.001,
    community="community",
    *,
    backend=None,
    **backend_kwargs,
):
    """Compute within/inter-cluster common-neighbor scores."""
    _fnx._validate_backend_dispatch_keywords(
        "within_inter_cluster", backend, backend_kwargs
    )
    return _fnx.within_inter_cluster(
        G, ebunch=ebunch, delta=delta, community=community
    )


def common_neighbor_centrality(
    G, ebunch=None, alpha=0.8, *, backend=None, **backend_kwargs
):
    """Compute common-neighbor centrality scores for node pairs."""
    _fnx._validate_backend_dispatch_keywords(
        "common_neighbor_centrality", backend, backend_kwargs
    )
    return _fnx.common_neighbor_centrality(G, ebunch=ebunch, alpha=alpha)


def __getattr__(name):
    try:
        return getattr(_nx_link_prediction, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_link_prediction) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
