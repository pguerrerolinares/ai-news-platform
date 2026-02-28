export const SOURCE_COLORS: Record<string, string> = {
  hackernews: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
  github: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
  arxiv: 'bg-red-500/10 text-red-500 border-red-500/20',
  reddit: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  rss: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  huggingface: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
}

export const TOPIC_LABELS: Record<string, string> = {
  models: 'Models',
  tools: 'Tools',
  papers: 'Papers',
  products: 'Products',
  open_source: 'Open Source',
  agents: 'Agents',
  regulation: 'Regulation',
}

export function formatTime(dateStr: string | null) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

export function safeUrl(url: string | null): string | null {
  if (!url) return null
  try {
    const u = new URL(url)
    return ['http:', 'https:'].includes(u.protocol) ? url : null
  } catch {
    return null
  }
}
