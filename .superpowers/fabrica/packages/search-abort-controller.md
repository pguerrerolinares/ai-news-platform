# Review-package — rama `fabrica/search-abort-controller`

> Lo ÚNICO que Paul necesita leer para gatear (spec §4.4.2). El veredicto de Paul
> se registra AQUÍ (spec §4.5): appendear al final `GATE: MERGED` o
> `GATE: RECHAZADA — <motivo/instrucciones>`. Merge en git = MERGED implícito;
> el rechazo EXIGE la línea.

## Qué se hizo
`Search.tsx` cancelaba nada: dos búsquedas rápidas podían llegar desordenadas y una
respuesta vieja pisaba resultados nuevos. Ahora cada búsqueda aborta la anterior
(patrón `abortRef` reusado de Chat.tsx; `apiGet` ya aceptaba `signal`), `AbortError`
se ignora sin ensuciar `error`/`results`, el `finally` solo apaga `loading` si el
controller sigue vigente, y se aborta on-unmount. 1 fichero, +13/-3.
Commit: `36c942e` — `fix(frontend): abort in-flight search requests to avoid stale results [Track A]`

## Spec aplicada
`.superpowers/fabrica/briefs/search-abort-controller.md` (item 3 del backlog
`.superpowers/fabrica/backlog-2026-07-11.md`)

## Base de stacking
origin/main (60d6ba9)

## Resultados de oráculo
- `npm --prefix frontend run build` → verde (ejecutor y padre, independientes; tsc + vite OK)
- `npm --prefix frontend run lint` → Search.tsx 0 errores; 10 errores PREEXISTENTES en ficheros no tocados, baseline idéntico verificado contra main por el ejecutor

## Reviews
- Self-review del ejecutor: sin findings.
- Review de rama (orquestador fable, diff completo): firma de `apiGet(path, params, signal)`
  verificada contra origin/main; guard `abortRef.current === controller` en finally correcto
  (evita apagar el loading de la búsqueda nueva). Sin findings. Diff trivial — no se gastó
  dispatch adicional de review adversarial (proporcionalidad al riesgo del diff).

## Verdicts del adjudicador
Ninguno — sin decisiones de diseño intra-rama (elección abortRef vs react-query estaba
pre-resuelta en el brief como reuse-first y el ejecutor la citó).

## Instrucción de merge
`git -C /home/paul/Documentos/proyectos/backend/ai-news-platform merge --no-ff fabrica/search-abort-controller` (sobre main actualizado)

<!-- GATE: (lo escribe Paul) -->
