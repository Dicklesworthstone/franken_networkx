"""Phase B: readwrite formats with TYPED attrs, cross-impl interop
(nx writes -> fnx reads + reverse). Value TYPES compared, not just keys."""
import io, tempfile, os
import networkx as nx
import franken_networkx as fnx

fails = []
def chk(name, a, b):
    if a != b: fails.append((name, str(a)[:130], str(b)[:130]))

def build(mod):
    g = mod.Graph()
    g.add_node(0, lbl="zero", w=1.5, flag=True, n=7)
    g.add_node(1, lbl="one")
    g.add_edge(0, 1, weight=2.5, name="e", active=False, cnt=3)
    g.add_edge(1, 2, weight=1)
    g.graph["gname"] = "T"; g.graph["gnum"] = 4
    return g

def rr(g):
    return repr((
        sorted((repr(n), sorted((k, repr(v), type(v).__name__) for k,v in g.nodes[n].items())) for n in g),
        sorted((repr(u), repr(v), sorted((k, repr(x), type(x).__name__) for k,x in d.items())) for u,v,d in g.edges(data=True)),
        sorted((k, repr(v)) for k,v in g.graph.items()),
    ))

tmp = tempfile.mkdtemp(dir="/data/tmp")
# graph6/sparse6: structure-only (no attrs) — round-trip + cross-impl
def struct_graph(mod):
    g = mod.Graph(); 
    for u,v in [(0,1),(1,2),(2,3),(3,0),(0,2),(4,1)]: g.add_edge(u,v)
    return g
for fmt, w, r in [
    ("graph6", lambda m,g,p: m.write_graph6(g,p), lambda m,p: m.read_graph6(p)),
    ("sparse6", lambda m,g,p: m.write_sparse6(g,p), lambda m,p: m.read_sparse6(p)),
]:
    for direction in ("nx->fnx","fnx->nx","fnx->fnx"):
        wm, rm = (nx,fnx) if direction=="nx->fnx" else (fnx,nx) if direction=="fnx->nx" else (fnx,fnx)
        p = os.path.join(tmp, f"{fmt}-{direction}.g6")
        try:
            w(wm, struct_graph(wm), p); got = sorted((repr(u),repr(v)) for u,v in r(rm,p).edges())
        except Exception as e: got = ('ERR', type(e).__name__, str(e)[:40])
        try:
            w(nx, struct_graph(nx), p+"r"); ref = sorted((repr(u),repr(v)) for u,v in r(nx,p+"r").edges())
        except Exception as e: ref = ('ERR', type(e).__name__, str(e)[:40])
        chk(f'{fmt} {direction}', got, ref)
# pajek / leda / gml / graphml typed-attr cross-impl
for fmt, w, r in [
    ("pajek", lambda m,g,p: m.write_pajek(g,p), lambda m,p: m.read_pajek(p)),
    ("gml", lambda m,g,p: m.write_gml(g,p), lambda m,p: m.read_gml(p)),
    ("graphml", lambda m,g,p: m.write_graphml(g,p), lambda m,p: m.read_graphml(p)),
]:
    for direction in ("nx->fnx","fnx->nx","fnx->fnx"):
        wm, rm = (nx,fnx) if direction=="nx->fnx" else (fnx,nx) if direction=="fnx->nx" else (fnx,fnx)
        p = os.path.join(tmp, f"{fmt}-{direction}.out")
        try:
            w(wm, build(wm), p); got = rr(r(rm,p))
        except Exception as e: got = ('ERR', type(e).__name__, str(e)[:45])
        try:
            w(nx, build(nx), p+"r"); ref = rr(r(nx,p+"r"))
        except Exception as e: ref = ('ERR', type(e).__name__, str(e)[:45])
        chk(f'{fmt} {direction}', got, ref)
print('READWRITE PROBE:', len(fails), 'divergences')
for n,a,b in fails:
    print(f'  {n}:')
    # first char diff
    for i in range(min(len(a),len(b))):
        if a[i]!=b[i]: print(f'    got ...{a[max(0,i-25):i+70]}'); print(f'    ref ...{b[max(0,i-25):i+70]}'); break
    else: print(f'    got={a[:110]}\n    ref={b[:110]}')
