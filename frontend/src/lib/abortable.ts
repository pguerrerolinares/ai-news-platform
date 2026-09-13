/**
 * Tracks the AbortController for the latest of a series of requests (e.g. a
 * search box firing on every keystroke), so a caller can cancel the previous
 * in-flight one when a newer request starts. Shared by Search.tsx and
 * Discover.tsx, which both need this exact "abort the stale request" pattern.
 */
export function createAbortSwitch() {
  let current: AbortController | null = null

  return {
    /** Aborts any previous in-flight request tracked here and returns a signal for the new one. */
    next(): AbortSignal {
      current?.abort()
      const controller = new AbortController()
      current = controller
      return controller.signal
    },
    /** Aborts the current in-flight request, if any (e.g. on unmount). */
    abort(): void {
      current?.abort()
    },
  }
}
