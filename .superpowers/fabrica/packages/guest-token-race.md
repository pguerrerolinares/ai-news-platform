# Review-package — rama `fabrica/guest-token-race`

> Veredicto de Paul AQUÍ: appendear `GATE: MERGED` o `GATE: RECHAZADA — <motivo>`.

## Qué se hizo
Tres arreglos en la capa de auth del frontend (2 ficheros, `api.ts` + `auth.ts`):
1. Single-flight: `ensureToken()` y `refreshAccessToken()` memoizan una promise
   in-flight a nivel de módulo — N requests concurrentes sin token comparten UN
   POST `/api/auth/guest` (antes: N).
2. DRY: nuevo `storeGuestToken()` en auth.ts con `STORAGE_KEYS`; fuera las claves
   crudas de localStorage duplicadas en api.ts.
3. Eliminados los `window.location.replace('/login')` (ignoraban el base path
   `/ai-news` → 404 en prod; login descontinuado). Un 401 no recuperable ahora
   lanza `ApiError('Session expired')`; un fallo del fetch de guest token ya no se
   traga en silencio, se propaga al caller.
Commit: `98c2126` — `fix(frontend): single-flight guest token fetch + shared storage keys [Track B]`

## Spec aplicada
`.superpowers/fabrica/briefs/guest-token-race.md` (item 4 del backlog 2026-07-11;
semántica del redirect y del single-flight fijadas tras blindspot pass)

## Base de stacking
origin/main (60d6ba9)

## Resultados de oráculo
- `npm --prefix frontend run build` → verde (ejecutor con bun install; padre con build independiente)
- `npm --prefix frontend run lint` → 10 errores preexistentes en ficheros no tocados (baseline verificado con git stash por el ejecutor)
- Evidencia single-flight: harness con fetch/localStorage mockeados → 3 `apiGet()` concurrentes ⇒ 1 solo fetch de guest token (PASS)

## Reviews
- Self-review del ejecutor: sin findings.
- Review de rama (orquestador fable): verificado que el retry de 401 para guests
  (re-`ensureToken()` + reintento) queda intacto; la semántica de `ensureToken` con
  refresh token presente se preserva; el single-flight limpia en finally (sin promise
  envenenada). bun es el package manager legítimo del proyecto (bun.lock tracked en main).

## Verdicts del adjudicador
Ninguno — decisiones pre-resueltas en el brief.

## Instrucción de merge
`git -C /home/paul/Documentos/proyectos/backend/ai-news-platform merge --no-ff fabrica/guest-token-race`

<!-- GATE: (lo escribe Paul) -->
