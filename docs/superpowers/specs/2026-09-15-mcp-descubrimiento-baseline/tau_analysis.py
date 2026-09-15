"""Analysis of tau-labels.tsv: what each counting option would deliver per query."""
from __future__ import annotations

import re
from collections import defaultdict

P = "/home/paul/Documentos/proyectos/backend/ai-news-platform/docs/superpowers/specs/2026-09-15-mcp-descubrimiento-baseline/tau-labels.tsv"
QUERIES = {
    0: "consolidating and invalidating long-term memory in LLM agents",
    1: "spec-driven development for AI coding agents",
    2: "code graph to give context to coding agents",
    3: "prompt injection defenses for tool-using agents",
    4: "evaluating retrieval quality in RAG systems",
}
rows = defaultdict(list)
for line in open(P):
    q, d, src, title, lab = line.rstrip("\n").split("\t")
    rows[int(q)].append((float(d), src, title, lab == "R"))
for q in rows:
    rows[q].sort()

def f1(sel_rel, sel_n, total_rel):
    if sel_n == 0 or total_rel == 0:
        return 0.0
    p = sel_rel / sel_n
    r = sel_rel / total_rel
    return 0 if p + r == 0 else 2 * p * r / (p + r)

print("=== 1. Opción A: precisión@K (dentro del top-40; K real sería >=180) ===")
for q, r in rows.items():
    tot = sum(x[3] for x in r)
    line = [f"q{q} R@40={tot:2d}"]
    for k in (10, 20, 40):
        rel = sum(x[3] for x in r[:k])
        line.append(f"P@{k}={rel/k:.2f}")
    # upper bound of precision at K=180 (6 monthly buckets) assuming no relevant beyond 40 (worst) / all beyond relevant (best)
    line.append(f"P@180 in [{tot/180:.2f}, {(tot+140)/180:.2f}]")
    print("  ".join(line))

print("\n=== 2. Bandas fijas: n seleccionados / relevantes por query dentro del top-40 (c = censurado: top-40 no llega) ===")
edges = [0.30, 0.35, 0.40, 0.45, 0.50]
hdr = "q   " + "  ".join(f"<{e:.2f}     " for e in edges)
print(hdr)
for q, r in rows.items():
    dmax = r[-1][0]
    cells = []
    for e in edges:
        sel = [x for x in r if x[0] < e]
        n, rel = len(sel), sum(x[3] for x in sel)
        c = "c" if e > dmax else " "
        cells.append(f"{n:2d}/{rel:2d}{c} p={rel/n if n else 0:.2f}")
    print(f"q{q}  " + "  ".join(cells))

print("\n=== 3. Opción B: tau = d_min + delta; F1 por query y mejor delta ===")
deltas = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16]
print("q    " + "  ".join(f"d={d:.2f}" for d in deltas) + "   best_delta")
best_deltas = []
for q, r in rows.items():
    tot = sum(x[3] for x in r)
    dmin = r[0][0]
    vals = []
    for dl in deltas:
        sel = [x for x in r if x[0] < dmin + dl]
        vals.append(f1(sum(x[3] for x in sel), len(sel), tot))
    # best delta on fine grid
    best = max(((f1(sum(x[3] for x in r if x[0] < dmin + dl), len([x for x in r if x[0] < dmin + dl]), tot), dl) for dl in [i/1000 for i in range(0, 200)]))
    best_deltas.append(best[1])
    print(f"q{q}  " + "  ".join(f"{v:.2f}  " for v in vals) + f"   {best[1]:.3f} (F1={best[0]:.2f})")
print(f"spread of best delta = {max(best_deltas)-min(best_deltas):.3f}  (same STOP rule: >0.10 refutes)")

print("\n=== 4. Percentil propio p0.1 (≈top-17) vs best tau del pre-check ===")
p01 = {0: 0.3106, 1: 0.3445, 2: 0.3896, 3: 0.4591, 4: 0.3896}
best_tau = {0: 0.3493, 1: 0.2990, 2: 0.3928, 3: 0.4897, 4: 0.4075}
for q in rows:
    print(f"q{q} p0.1={p01[q]:.3f} best_tau={best_tau[q]:.3f} diff={best_tau[q]-p01[q]:+.3f}")

print("\n=== 5. Keyword (solo título, cota inferior): ¿cuántos R del top-40 contienen los términos clave? ===")
kw = {
    0: [r"memor", r"agent"],
    1: [r"spec", r"driven"],
    2: [r"graph", r"code|coding"],
    3: [r"prompt injection|guardrail|injection|secur|firewall|safety|guard"],
    4: [r"rag|retrieval", r"eval|benchmark|test|metric|assess"],
}
for q, r in rows.items():
    rel = [x for x in r if x[3]]
    hit = [x for x in rel if all(re.search(p, x[2], re.I) for p in kw[q])]
    print(f"q{q} R={len(rel):2d} title-match(AND)={len(hit):2d}  patterns={kw[q]}")

print("\n=== 6. Distancia entre R y N vecinos en la zona mezclada (¿separable?) ===")
for q, r in rows.items():
    rel_d = [x[0] for x in r if x[3]]
    non_d = [x[0] for x in r if not x[3]]
    if rel_d and non_d:
        print(f"q{q} R:[{min(rel_d):.3f},{max(rel_d):.3f}] N:[{min(non_d):.3f},{max(non_d):.3f}]  first N at rank {next(i for i,x in enumerate(r) if not x[3])+1}")
