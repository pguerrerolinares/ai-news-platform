# Baseline ANTES (MCP actual, 2026-09-15)

**Comando real usado** (corregido respecto al brief — ver "Concern" más abajo):

```bash
B=docs/superpowers/specs/2026-09-15-mcp-descubrimiento-baseline
cd /tmp/task0-isolated-run   # cwd aislado, sin CLAUDE.md ni KB accesible
claude -p "$(cat $B/p$i.txt)" --model sonnet --output-format stream-json --verbose \
  --strict-mcp-config --mcp-config $B/mcp-ainews.json \
  --allowedTools mcp__ainews \
  --disallowedTools Read Write Edit NotebookEdit Glob Grep Bash BashOutput KillBash WebFetch WebSearch Task TodoWrite ExitPlanMode SlashCommand ToolSearch Agent \
  > $B/before-$i.jsonl
```

| Prompt | Tool calls (por nombre) | tool_result chars | output_tokens | Enlaces en respuesta | Relevantes (R/total) |
|---|---|---|---|---|---|
| P1 | `mcp__ainews__search_news` ×1, `mcp__ainews__semantic_search` ×1 | 4348 | 4525 | ver lista P1 abajo | |
| P2 | `mcp__ainews__get_trending` ×1, `mcp__ainews__search_news` ×6, `mcp__ainews__semantic_search` ×1 | 13832 | 4668 | ver lista P2 abajo (sin URLs literales, solo nombres/ids) | |
| P3 | `mcp__ainews__search_news` ×2, `mcp__ainews__semantic_search` ×1 | 7880 | 5712 | ver lista P3 abajo (sin URLs literales, solo nombres/ids) | |

## Enlaces en la respuesta final — para etiquetar (R/N)

**P1** (5 links literales, en orden de aparición):
1. https://arxiv.org/abs/2606.25161 — TRUSTMEM
2. https://arxiv.org/abs/2605.19952 — Rethinking How to Remember
3. https://arxiv.org/abs/2605.07313 — When Stored Evidence Stops Being Usable
4. https://arxiv.org/abs/2608.11248 — EvoGraph-Mem
5. https://github.com/IAAR-Shanghai/Awesome-AI-Memory — repo índice

**P2** (sin URLs literales en la respuesta — cita nombres/proyectos, útil para juzgar relevancia igual):
1. `spec-kit` (GitHub, ancla del ecosistema)
2. `cc-sdd` (multi-runtime: Claude Code, Codex, Cursor, Copilot, Gemini CLI, Windsurf)
3. `sample-specship` (AWS, "Kiro Power")
4. `ospec`
5. `vibecode-pro-max-kit` (906 pts)
6. SDAD — "Spec-Driven Agentic Development for the AI-Native SDLC" (arXiv, agosto 2026, sin id citado en la respuesta)

**P3** (sin URLs literales — cita repos/papers por nombre o slug):
1. SCIP/LSIF (Sourcegraph)
2. `serena` (oraios)
3. Aider repo-map (tree-sitter + PageRank)
4. `codefuse-ai/CodeFuse-CGM` (NeurIPS 2025)
5. `vitali87/code-graph-rag` (~1984 pts)
6. arxiv 2603.06593 — Hierarchical Embedding Fusion for RAG Code Generation
7. arxiv 2607.25431 — CodeNib
8. `soulforge`, `tokensave`, `memtrace` (MCP servers, mencionados en bloque)

## Notas cualitativas

- **P1**: sí llegó a papers/repos concretos con URL verificable (arxiv.org/abs/... y un repo GitHub), citando explícitamente que usó `mcp__ainews__search_news` + `mcp__ainews__semantic_search` y advirtiendo la limitación real ("solo tengo título+resumen corto, no el paper completo — verifica el abstract").
- **P2**: sí pudo hablar de tendencia — usó `get_trending` + 6 `search_news` + 1 `semantic_search`, comparó dos ventanas de 6 meses por señales de "pts"/menciones y fue honesto sobre la limitación del proxy ("pts del feed es proxy de popularidad, no de adopción en producción"). No citó URLs literales, solo nombres de proyectos/repos.
- **P3**: cubrió el espacio con 6 categorías (LSP-based, grafo on-the-fly, grep sin estructura, KG vía LLM, RAG puro, "mismo problema que cge") y distinguió tracción-en-producción vs. tracción-de-stars vs. respaldo académico. Sin URLs literales, cita slugs de repo y arxiv-ids sueltos.
- Las tres respuestas mencionan explícitamente que el entorno de ejecución (`/tmp/task0-isolated-run`, sin Bash/Read/Grep) no tenía acceso a la KB de Paul ni a `exo` — señal correcta de que el aislamiento de tools funcionó (ver Concern).

## Concern: la primera ejecución (según el brief tal cual) estaba contaminada

El comando del brief (`--allowedTools mcp__ainews --disallowedTools WebSearch WebFetch Bash`, cwd = raíz del repo `ai-news-platform`, que en la práctica de este ejecutor coincidía con el cwd de la sesión) **no restringe** las tools por defecto `Read`/`Grep`/`Glob`/`ToolSearch`, que siguen auto-aprobadas. En la primera corrida (descartada, no queda en `before-*.jsonl`), P1 y P3 usaron `Read`/`Grep`/`Glob` y respondieron **citando notas de la KB local de Paul (wisdom-paul)** — papers ya destilados en `research/Radar 2026-09-15` — en vez de resultados reales del MCP `ainews`. Esto invalidaba la medición: no se estaba midiendo lo que el MCP puede recuperar, sino lo que el modelo ya sabía por acceso al filesystem local.

**Corrección aplicada** (documentada arriba, es la que generó los `before-*.jsonl` finales): (1) cwd aislado en `/tmp/task0-isolated-run` sin `CLAUDE.md` ni acceso a ningún repo/KB; (2) `--disallowedTools` explícito listando todas las tools built-in conocidas (`Read Write Edit NotebookEdit Glob Grep Bash BashOutput KillBash WebFetch WebSearch Task TodoWrite ExitPlanMode SlashCommand ToolSearch Agent`), dejando solo `mcp__ainews__*` disponible. Verificado: los 3 `before-*.jsonl` finales solo muestran tool_use de `mcp__ainews__*` (ver tabla), y las respuestas mencionan explícitamente no poder acceder a la KB/Bash.

Esto es relevante más allá de esta tarea: cualquier medición futura de "qué sabe el modelo solo con el MCP X" en este proyecto debe reproducir el aislamiento de cwd + disallow explícito de tools built-in, no solo `--allowedTools <mcp>`.
