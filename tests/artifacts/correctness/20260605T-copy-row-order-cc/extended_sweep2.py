import sys
sys.path.insert(0, "tests/python")
from test_mutation_sequence_metamorphic_parity import _drive
bad = []
for directed in (False, True):
    for multi in (False, True):
        for seed in range(1500):
            sf, sn = _drive(seed, directed, multi)
            if sf != sn:
                bad.append((directed, multi, seed))
print("extended metamorphic 4x1500:", "CLEAN" if not bad else bad[:10])
