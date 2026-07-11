# Informe — retirar-chat-frontend

## Estado
Completado. Commit `58c3656` en rama `fabrica/retirar-chat-frontend` (worktree
`.worktrees/retirar-chat-frontend`). Solo commits locales, sin push/merge.

## Commit
`58c3656` — `refactor(frontend): retirar chat y settings del UI (web pública guest-only) [Track B]`

Archivos tocados:
- `frontend/src/App.tsx`
- `frontend/src/components/app-nav.tsx`
- `frontend/src/pages/Dashboard.tsx`

`git diff` en `src/` (backend): vacío, confirmado antes de commitear.

## Cambios
1. **App.tsx**: eliminadas las rutas `/chat` y `/settings`, el bloque
   `RequireAuth`/`Outlet` que las envolvía, y los imports de `Chat`, `Settings`
   y `RequireAuth`/`Outlet`. `AuthProvider` se mantiene porque `useAuth` sigue
   teniendo consumidores activos (`Login.tsx`, `app-nav.tsx`). El import y la
   ruta de `Login` no se tocan (fuera de alcance, lo cubre purga-auth-muerto).
2. **app-nav.tsx**: quitada la entrada "Settings" (NavLink a `/settings`) y el
   botón "Sign in" (navegaba a `/login`). Se mantiene el botón de logout,
   visible solo si `isFullUser` (caso de alguien con sesión completa ya
   iniciada por URL directa). Import de `IconSettings`/`IconLogin` eliminado
   (quedaban sin uso).
3. **Dashboard.tsx**: durante el grep de rutas colgantes (paso 3 del brief)
   apareció `passkey-prompt.tsx`, renderizado en `Dashboard.tsx` y con un botón
   que navegaba a `/settings` (ruta ya eliminada). Como no había ninguna
   entrada de nav apuntando ahí, era una superficie muerta/rota adicional del
   mismo tipo (guest-only, requiere full auth). Se retiró el uso de
   `<PasskeyPrompt />` y su import de `Dashboard.tsx`, sin borrar el
   componente (mismo criterio que Chat/Settings/Login: no borrar en masa,
   solo desconectar).

No se introdujeron componentes nuevos; solo se elimina superficie.

## Verificación (quality gate)
Se instaló `node_modules` en el worktree (no existía) vía `npm install` solo
para poder correr build/lint; el `package-lock.json` generado se borró antes
de commitear (el proyecto usa bun, hay un commit previo que retira ese
lockfile a propósito).

**Build** (`npm --prefix frontend run build`): verde.
```
> frontend@0.0.0 build
> tsc -b && vite build
...
✓ 13478 modules transformed.
dist/index.html                     0.46 kB │ gzip:   0.30 kB
dist/assets/index-D2uPjJiA.css     90.33 kB │ gzip:  14.73 kB
dist/assets/index-DMyam3-M.js   1,104.95 kB │ gzip: 335.20 kB
✓ built in 14.05s
```

**Lint** (`npm --prefix frontend run lint`): 20 errores, todos preexistentes
y ajenos al cambio (en `Timeline.tsx` y `Trending.tsx`, sobre memoización de
React Compiler y uso de refs durante render — nada relacionado con
chat/settings/nav). Confirmado corriendo lint con `git stash` (working tree
sin mis cambios): mismos 20 errores, mismos archivos. No se introdujo ningún
error nuevo con este cambio.

## Grep de referencias colgantes
`grep -rn "/chat\|/settings" src/` tras el cambio solo devuelve:
- `src/pages/Chat.tsx:150` (`apiStream('/api/chat', ...)`, código interno de
  la página Chat, no una ruta ni link — la página sigue existiendo sin
  consumidores, fuera de alcance).

No queda ningún `<Link>`/`navigate()`/redirect activo hacia `/chat` o
`/settings` en las páginas que quedan conectadas.

## Decisiones tomadas
- Mantener `AuthProvider` en `App.tsx` porque `useAuth` sigue en uso
  (Login, nav). Solo se retira `RequireAuth`.
- Mantener el botón de logout en el nav para el caso residual de un usuario
  con sesión completa ya autenticada (no rompe nada, y tocarlo más sería
  invadir el alcance de purga-auth-muerto).
- Retirar `PasskeyPrompt` de `Dashboard.tsx` por ser una superficie rota del
  mismo tipo (apunta a `/settings`), no mencionada explícitamente en el brief
  pero cubierta por el criterio de aceptación de "sin links/redirects rotos".
