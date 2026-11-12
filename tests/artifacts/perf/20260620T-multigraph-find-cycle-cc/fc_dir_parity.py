import random, networkx as nx, franken_networkx as fnx
from networkx.exception import NetworkXNoCycle
fails=0; total=0; nc=0
for seed in range(3000):
    rnd=random.Random(seed); n=rnd.randrange(1,28)
    gn=nx.MultiDiGraph(); gf=fnx.MultiDiGraph()
    for i in range(n): gn.add_node(i); gf.add_node(i)
    for _ in range(rnd.randrange(0,40)):
        u,v=rnd.randrange(n),rnd.randrange(n)
        k=rnd.choice([None,'k',5])
        if k is None: gn.add_edge(u,v); gf.add_edge(u,v)
        else: gn.add_edge(u,v,key=k); gf.add_edge(u,v,key=k)
    total+=1
    try: rn=nx.find_cycle(gn)
    except NetworkXNoCycle: rn=None
    try: rf=fnx.find_cycle(gf)
    except NetworkXNoCycle: rf=None
    if rn is None and rf is None: nc+=1; continue
    if (rn is None)!=(rf is None) or rn!=rf:
        fails+=1
        if fails<=6: print("seed",seed,"\n nx ",rn,"\n fnx",rf)
print(f"directed MultiDiGraph find_cycle parity: {fails}/{total} fail ({nc} no-cycle agreed)")
