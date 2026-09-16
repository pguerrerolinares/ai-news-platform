# Baseline DESPUÉS (MCP con descubrimiento, tools nuevas desplegadas en prod, 2026-09-16)

**Comando usado** — idéntico al de `before.md` (mismo modelo `sonnet`, mismos flags, mismo aislamiento de cwd). El único cambio de facto es que el servidor detrás de `mcp-ainews.json` (`https://pguerrero.me/ai-news/mcp`, mismo fichero de config sin tocar) ahora sirve las 5 tools nuevas en producción:

```bash
B=docs/superpowers/specs/2026-09-15-mcp-descubrimiento-baseline
mkdir -p /tmp/task0-isolated-run   # recreado; el cwd aislado de la corrida "antes" no sobrevivió entre sesiones
cd /tmp/task0-isolated-run
claude -p "$(cat $B/p$i.txt)" --model sonnet --output-format stream-json --verbose \
  --strict-mcp-config --mcp-config $B/mcp-ainews.json \
  --allowedTools mcp__ainews \
  --disallowedTools Read Write Edit NotebookEdit Glob Grep Bash BashOutput KillBash WebFetch WebSearch Task TodoWrite ExitPlanMode SlashCommand ToolSearch Agent \
  > $B/after-$i.jsonl
```

No se cambió ningún flag ni versión de modelo respecto al comando documentado en `before.md`. El `mcp-ainews.json` no se editó — apuntaba ya a la URL de prod desde la corrida "antes"; lo que cambió entre corridas es el código detrás de esa URL (deploy de las 5 tools nuevas), no la configuración del cliente.

| Prompt | Tool calls (por nombre) | tool_result chars | output_tokens | Enlaces en respuesta final | Relevantes (R/total) |
|---|---|---|---|---|---|
| P1 | `mcp__ainews__search` ×10, `mcp__ainews__get_item` ×6 | 21564 | 3989 | ver lista P1 abajo | |
| P2 | `mcp__ainews__topic_trend` ×2, `mcp__ainews__search` ×2, `mcp__ainews__get_top` ×1 | 23186 | 4880 | ver lista P2 abajo (sin URLs literales, solo nombres/ids) | |
| P3 | `mcp__ainews__search` ×5, `mcp__ainews__get_top` ×1 | 23751 | 7172 | ver lista P3 abajo (sin URLs literales, solo nombres/ids) | |

## Enlaces en la respuesta final — para etiquetar (R/N)

**P1** (6 links literales, en orden de aparición):
1. https://github.com/WujiangXu/A-mem — A-MEM: Agentic Memory for LLM Agents (NeurIPS 2025)
2. https://arxiv.org/abs/2502.12110 — paper de A-MEM
3. https://arxiv.org/abs/2606.07909 — MemToolAgent
4. https://github.com/HUST-AI-HYZ/MemoryAgentBench — MemoryAgentBench (ICLR 2026)
5. https://github.com/sachitrafa/YourMemory — YourMemory
6. https://github.com/mem0ai/mem0 — Mem0

**P2** (sin URLs literales en la respuesta — cita nombres/proyectos/ids, útil para juzgar relevancia igual):
1. `spec-kit` (GitHub, marzo 2026, ancla fundacional)
2. Kiro (AWS/Amazon Q) — metodología requirements→design→tasks nativa
3. `cc-sdd` (Claude Code, Codex, Cursor, Copilot, Gemini CLI, Windsurf)
4. SDAD — "Spec-Driven Agentic Development for the AI-Native SDLC" (arXiv 2608.20341, agosto 2026)
5. `sample-specship` (AWS, "Kiro Power", septiembre 2026)
6. `vibecode-pro-max-kit` (contraseñal de saturación de marketing, junio 2026)

**P3** (sin URLs literales — cita repos/papers por nombre o slug):
1. `Serena` (oraios, MCP wrapper sobre LSP)
2. Repo-map estilo Aider (ctags + PageRank, sin DB)
3. `code-graph-rag` (vitali87, tree-sitter + Neo4j)
4. `memtrace-public` (MCP-native, "zero LLM calls")
5. `Lat.md` / Agent Lattice (grafo como texto plano versionable en git)
6. `soulforge` (AST-surgery + grafo de co-change)
7. Sourcegraph SCIP / CodeQL
8. CodeNib (arXiv 2607.25431)
9. "Agentic Coding in the Wild: Characterizing GitHub Copilot Traces at Production Scale" (agosto 2026)

## Comparación antes/después por prompt

| Prompt | Tool calls (total) antes → después | tool_result chars antes → después | output_tokens antes → después |
|---|---|---|---|
| P1 | 2 → 16 | 4348 → 21564 | 4525 → 3989 |
| P2 | 8 → 5 | 13832 → 23186 | 4668 → 4880 |
| P3 | 3 → 6 | 7880 → 23751 | 5712 → 7172 |

## Lectura cualitativa

- **P1**: sí llegó a papers/repos relevantes con enlace verificable (6 links: A-MEM/NeurIPS 2025, MemToolAgent, MemoryAgentBench/ICLR 2026, YourMemory, Mem0). Con las tools nuevas usó `search` para descubrir y `get_item` ×6 para traer el detalle completo de cada candidato antes de citarlo — un patrón de "listar → profundizar" que no existía antes (antes solo tenía `search_news`/`semantic_search`, sin forma de pedir el ítem completo). El set de papers citados es distinto al de la corrida "antes" (TRUSTMEM, Rethinking How to Remember, etc. no aparecen aquí) — coherente con que el corpus/ranking del feed sigue moviéndose día a día, no necesariamente con un cambio de calidad.
- **P2**: sí pudo responder la de tendencia con datos, y de forma más rigurosa que antes — usó `topic_trend` (tool nueva) ×2 para traer una serie mensual explícita (marzo→septiembre 2026, items/mes y % de share del corpus, con threshold de similitud declarado) en vez de comparar "pts" de dos ventanas de 6 meses como hacía la corrida "antes". La conclusión matiza correctamente "no sube en volumen bruto, sí en consolidación institucional" — un juicio más fino que el "sí sube" de antes, y respaldado por una tabla cuantitativa reproducible.
- **P3**: usó `get_top` (tool nueva) además de `search`, pero no `get_item` ni `find_similar`. Cobertura similar en amplitud a la corrida "antes" (7 enfoques vs 6 categorías), con algunas entradas nuevas en el radar (`Lat.md`/Agent Lattice, el paper "Agentic Coding in the Wild") y mantiene el mismo estilo sin URLs literales, solo slugs/arxiv-ids.
- Ninguna de las 3 corridas usó `find_similar` — la tool de "ampliar desde un ítem conocido" quedó sin ejercitar en estos prompts; sería la candidata más obvia a forzar con un cuarto prompt si se quiere validar esa tool específicamente.
- Las tres respuestas siguen citando correctamente la limitación de aislamiento (sin acceso a Bash/KB), señal de que el `--disallowedTools` sigue funcionando igual que en la corrida "antes".

## Verificación: solo `mcp__ainews__*` en las corridas after

Comando usado (mismo patrón que en `before.md`, uno por archivo):

```bash
python3 -c "
import json
names=set()
with open('after-N.jsonl') as f:
    for line in f:
        line=line.strip()
        if not line: continue
        d=json.loads(line)
        content=d.get('message',{}).get('content',[])
        if isinstance(content, list):
            for c in content:
                if isinstance(c,dict) and c.get('type')=='tool_use':
                    names.add(c.get('name'))
print(sorted(names))
"
```

Resultado:
- `after-1.jsonl`: `['mcp__ainews__get_item', 'mcp__ainews__search']`
- `after-2.jsonl`: `['mcp__ainews__get_top', 'mcp__ainews__search', 'mcp__ainews__topic_trend']`
- `after-3.jsonl`: `['mcp__ainews__get_top', 'mcp__ainews__search']`

Ningún tool_use fuera del namespace `mcp__ainews__*` en ninguna de las 3 corridas — aislamiento verificado, igual que en la corrida "antes".

## Relevancia antes vs después (etiquetado ciego)

| Corrida | P1 | P2 | P3 | TOTAL |
|---|---|---|---|---|
| before | 5/5 | 3/6 | 6/8 | **14/19 (74%)** |
| after | 4/6 | 4/6 | 4/9 | **12/21 (57%)** |

**Método**: se extrajeron todos los enlaces/menciones de las respuestas finales de `before.md` y `after.md` (40 filas), se barajaron con `random.Random(11)` y se etiquetaron R/N por un agente que solo vio `links-blind.tsv` + los prompts, sin saber de qué corrida venía cada fila ni ver los jsonl. La clave corrida↔fila se unió después. Ficheros de trabajo en `.superpowers/sdd/links-{blind,labeled,key}.tsv` (no versionados).

**Lectura honesta**: la superficie nueva NO mejora la relevancia de los enlaces citados en esta muestra — baja de 74% a 57%. El agente cita más (21 vs 19) y acierta menos en proporción; solo P2 (tendencia) mejora (3/6 → 4/6), que es justo donde `topic_trend` aporta datos que antes no existían. El cambio de comportamiento sí es el buscado (P1 usa `get_item` 6 veces para profundizar; P2 responde con una serie mensual cuantitativa en vez de "pts"), pero eso no se traduce en mejor precisión de las citas.

**Limitaciones**: muestra mínima (3 prompts, ~20 enlaces por corrida; una diferencia de 2-3 enlaces mueve el porcentaje ~10 puntos), un solo etiquetador LLM juzgando por título/URL, corpus distinto entre corridas (el feed cambió en 1 día: el set de papers de P1 no se repite), y `find_similar` sin ejercitar por el agente en ninguna corrida. No es evidencia suficiente para afirmar que la superficie empeora; sí para no afirmar que mejora.

**Qué observar**: repetir la medición con más prompts (8-10) y con el corpus estabilizado antes de sacar conclusiones; y vigilar si el agente cita de más al tener `get_item` barato.
