import random, networkx as nx, franken_networkx as fnx
from networkx.exception import NetworkXNoCycle
fails=0; total=0; ncycle_match=0
for seed in range(2000):
    rnd=random.Random(seed)
    n=rnd.randrange(1,30)
    gn=nx.MultiGraph(); gf=fnx.MultiGraph()
    for i in range(n): gn.add_node(i); gf.add_node(i)
    for _ in range(rnd.randrange(0,40)):
        u,v=rnd.randrange(n),rnd.randrange(n)
        k=rnd.choice([None,'x',7])
        if k is None:
            gn.add_edge(u,v); gf.add_edge(u,v)
        else:
            gn.add_edge(u,v,key=k); gf.add_edge(u,v,key=k)
    total+=1
    try: rn=nx.find_cycle(gn); en=None
    except NetworkXNoCycle: rn=None; en=1
    try: rf=fnx.find_cycle(gf); ef=None
    except NetworkXNoCycle: rf=None; ef=1
    if en and ef: ncycle_match+=1; continue
    if (en is None) != (ef is None):
        fails+=1
        if fails<=6: print("RAISE-mismatch seed",seed,"nx",rn,"fnx",rf)
        continue
    if rn != rf:
        fails+=1
        if fails<=6: print("CYCLE-mismatch seed",seed,"\n nx ",rn,"\n fnx",rf)
print(f"undirected MultiGraph find_cycle parity: {fails}/{total} fail ({ncycle_match} no-cycle agreed)")
