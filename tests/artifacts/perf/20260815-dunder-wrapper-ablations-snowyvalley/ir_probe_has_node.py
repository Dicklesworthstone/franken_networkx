"""Toggle-collect Ir profile for `G.has_node(n)` — where does the loss live?"""
import hashlib, os, random, sys
import franken_networkx as fnx
import franken_networkx._fnx as ext

REPS = int(os.environ.get("IR_REPS", "20000"))
rng = random.Random(11)
g = fnx.Graph()
names = [f"n{i}" for i in range(2000)]
g.add_nodes_from(names)
for _ in range(8000):
    g.add_edge(names[rng.randrange(2000)], names[rng.randrange(2000)])
probe = [names[random.Random(7).randrange(2000)] for _ in range(REPS)]
probe = [names[i % 2000] for i in range(REPS)]
with open(ext.__file__, "rb") as fh:
    print(f"elf_sha256 {hashlib.sha256(fh.read()).hexdigest()}", file=sys.stderr)
hits = sum(1 for n in probe if g.has_node(n))
print(f"hits {hits} reps {REPS}", file=sys.stderr)
assert hits == REPS
