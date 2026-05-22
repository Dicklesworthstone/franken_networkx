"""Drawing functions — thin delegation layer to NetworkX/matplotlib."""

from franken_networkx.drawing.nx_pylab import (
    display,
    draw,
    draw_bipartite,
    draw_circular,
    draw_forceatlas2,
    draw_kamada_kawai,
    draw_networkx,
    draw_networkx_edge_labels,
    draw_networkx_edges,
    draw_networkx_labels,
    draw_networkx_nodes,
    draw_planar,
    draw_random,
    draw_shell,
    draw_spectral,
    draw_spring,
    generate_network_text,
    to_latex,
    to_latex_raw,
    write_latex,
    write_network_text,
)
from franken_networkx.drawing.layout import (
    arf_layout,
    bfs_layout,
    bipartite_layout,
    circular_layout,
    forceatlas2_layout,
    fruchterman_reingold_layout,
    kamada_kawai_layout,
    multipartite_layout,
    planar_layout,
    random_layout,
    rescale_layout_dict,
    shell_layout,
    spiral_layout,
    spectral_layout,
    spring_layout,
)

__all__ = [
    "draw",
    "display",
    "draw_bipartite",
    "draw_circular",
    "draw_forceatlas2",
    "draw_kamada_kawai",
    "draw_networkx",
    "draw_networkx_edge_labels",
    "draw_networkx_edges",
    "draw_networkx_labels",
    "draw_networkx_nodes",
    "draw_planar",
    "draw_random",
    "draw_shell",
    "draw_spectral",
    "draw_spring",
    "generate_network_text",
    "to_latex",
    "to_latex_raw",
    "write_latex",
    "write_network_text",
    "arf_layout",
    "bfs_layout",
    "bipartite_layout",
    "circular_layout",
    "forceatlas2_layout",
    "fruchterman_reingold_layout",
    "kamada_kawai_layout",
    "multipartite_layout",
    "planar_layout",
    "random_layout",
    "rescale_layout_dict",
    "shell_layout",
    "spiral_layout",
    "spectral_layout",
    "spring_layout",
]


def _install_drawing_child_aliases():
    import importlib
    import pkgutil
    import sys
    import networkx.drawing as _src

    native_children = {"layout", "nx_pylab"}
    for info in pkgutil.iter_modules(_src.__path__):
        name = info.name
        if name in native_children or name == "tests" or name.startswith("_"):
            continue
        alias = f"{__name__}.{name}"
        if alias in sys.modules:
            continue
        module = importlib.import_module(f"networkx.drawing.{name}")
        sys.modules[alias] = module
        globals()[name] = module


_install_drawing_child_aliases()
