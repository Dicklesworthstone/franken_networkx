import hashlib
import networkx as nx, franken_networkx as fnx
sha=hashlib.sha256(); mism=0
for n in range(0, 16):
    try:
        Gn=nx.binomial_tree(n); Gf=fnx.binomial_tree(n)
    except Exception as e:
        # both should agree on errors for large n
        try: fnx.binomial_tree(n); ef="ok"
        except Exception as e2: ef=type(e2).__name__
        try: nx.binomial_tree(n); en="ok"
        except Exception as e3: en=type(e3).__name__
        print(f"n={n}: nx[{en}] fx[{ef}]"); continue
    nn=list(Gn.nodes()); nf=list(Gf.nodes())
    en=list(Gn.edges()); ef=list(Gf.edges())
    if nn!=nf or en!=ef:
        mism+=1
        if mism<=3:
            print(f"n={n} MISMATCH nodes_eq={nn==nf} edges_eq={en==ef}")
            if nn!=nf: print(f"  nx_nodes={nn}\n  fx_nodes={nf}")
    sha.update(repr((n,nn,en)).encode())
print(f"orders 0-15: mismatches={mism}")
print(f"golden_sha256={sha.hexdigest()}")
