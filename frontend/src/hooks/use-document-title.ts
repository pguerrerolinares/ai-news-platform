import { useEffect } from 'react'

const SITE_TITLE = 'AI News'

/** Sets document.title to "`page` · AI News" for the lifetime of the calling component. */
export function useDocumentTitle(page: string): void {
  useEffect(() => {
    document.title = page ? `${page} · ${SITE_TITLE}` : SITE_TITLE
  }, [page])
}
