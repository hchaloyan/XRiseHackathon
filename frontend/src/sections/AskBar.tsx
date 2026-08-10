import { useState, type FormEvent } from 'react'
import { ArrowUp, FileText, Loader2, Search, X } from 'lucide-react'
import { api } from '../api/client'
import type { SearchResponse } from '../api/types'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { SkeletonLines } from '../components/ui/Skeleton'

/**
 * Persistent ask bar -> POST /api/search. Documents only (CLAUDE.md rule 8).
 *
 * Fixed to the bottom of the viewport and rendered by the layout, so it
 * survives both scrolling and screen changes. Answers expand UPWARD above the
 * input, capped and scrollable, so a long citation list never pushes the
 * input off screen.
 *
 * No intent routing lives here or anywhere else on the client. Queries the
 * index cannot answer come back with `outOfScope` set by the backend's
 * similarity floor, and get the fixed redirect string from spec 7.1 rather
 * than a wrong answer.
 */
export default function AskBar() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q || busy) return
    setBusy(true)
    setResult(null)
    try {
      setResult(await api.search(q))
    } finally {
      setBusy(false)
    }
  }

  const open = busy || result !== null

  return (
    <div className="fixed inset-x-0 bottom-0 z-50">
      {/* Content scrolling under the bar fades out rather than being sliced. */}
      <div className="pointer-events-none h-16 bg-gradient-to-t from-void to-transparent" />

      <div className="bg-void/80 pb-6 backdrop-blur-sm">
        <div className="mx-auto max-w-7xl px-6">
          <div className="card-glass overflow-hidden shadow-lift">
            {open && (
              <div className="relative max-h-[45vh] overflow-y-auto border-b border-white/5 p-4">
                {busy ? (
                  <SkeletonLines lines={2} />
                ) : result?.outOfScope ? (
                  /* The near-certain off-script moment, made to look deliberate. */
                  <p className="flex items-center gap-2 pr-8 text-sm text-muted">
                    <ArrowUp size={14} className="shrink-0 text-btc" aria-hidden />
                    {result.answer}
                  </p>
                ) : (
                  <>
                    <p className="pr-8 text-sm leading-relaxed text-white/85">{result?.answer}</p>

                    {result && result.citations.length > 0 && (
                      <ul className="mt-4 space-y-2">
                        {result.citations.map((c) => (
                          <li
                            key={`${c.docId}${c.section}`}
                            className="rounded-xl border border-white/5 bg-white/[0.02] p-3 transition-colors duration-300 hover:border-btc/30"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <FileText size={12} className="shrink-0 text-btc" aria-hidden />
                              <span className="font-mono text-[11px] text-btc">{c.docId}</span>
                              <span className="text-xs text-white/80">{c.title}</span>
                              <span className="font-mono text-[10px] text-muted">
                                {c.section} · rev {c.revision}
                              </span>
                            </div>
                            <p className="mt-1.5 border-l border-white/10 pl-3 text-[11px] leading-relaxed text-muted italic">
                              {c.excerpt}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}

                {result && (
                  <button
                    type="button"
                    onClick={() => setResult(null)}
                    aria-label="Dismiss answer"
                    className="absolute top-3 right-3 cursor-pointer rounded-lg p-1.5 text-muted transition-colors duration-200 hover:bg-white/10 hover:text-white focus-visible:ring-2 focus-visible:ring-btc focus-visible:outline-none"
                  >
                    <X size={14} aria-hidden />
                  </button>
                )}
              </div>
            )}

            <form onSubmit={onSubmit} className="flex items-center gap-3 px-4">
              <Search size={16} className="shrink-0 text-muted" aria-hidden />
              <label htmlFor="askbar" className="sr-only">
                Ask about SOPs, manuals, and audit documents
              </label>
              <Input
                id="askbar"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask about SOPs, manuals, and audit documents…"
                className="border-b-0 bg-transparent px-0 focus-visible:shadow-none"
                autoComplete="off"
              />
              <Button type="submit" size="sm" disabled={busy || !query.trim()} className="shrink-0">
                {busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : 'Ask'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
