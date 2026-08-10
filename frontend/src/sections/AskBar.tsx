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
 * survives both scrolling and screen changes. It floats as a self-contained
 * glass pill at 08dp — 12% white overlay — rather than a full-bleed strip, so
 * the page stays visible on both sides of it. Answers expand UPWARD above the
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
    <div className="fixed bottom-6 left-1/2 z-50 w-[min(100%-2rem,42rem)] -translate-x-1/2">
      {open && (
        <div className="glass-bar relative mb-2 max-h-[45vh] overflow-y-auto rounded-2xl border border-line p-4">
          {busy ? (
            <SkeletonLines lines={2} />
          ) : result?.outOfScope ? (
            /* The near-certain off-script moment, made to look deliberate. */
            <p className="flex items-center gap-2 pr-8 text-sm text-muted">
              <ArrowUp size={14} className="shrink-0 text-accent" aria-hidden />
              {result.answer}
            </p>
          ) : (
            <>
              <p className="pr-8 text-sm leading-relaxed text-hi">{result?.answer}</p>

              {result && result.citations.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {result.citations.map((c) => (
                    <li key={`${c.docId}${c.section}`} className="rounded-lg bg-white/[0.06] p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <FileText size={12} className="shrink-0 text-accent" aria-hidden />
                        <span className="data-figure text-[12px] text-accent">{c.docId}</span>
                        <span className="text-xs text-hi">{c.title}</span>
                        <span className="text-[12px] text-faint">
                          {c.section} · rev {c.revision}
                        </span>
                      </div>
                      <p className="mt-1.5 border-l border-line pl-3 text-[12px] leading-relaxed text-muted">
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
              className="absolute top-3 right-3 cursor-pointer rounded p-1.5 text-muted transition-colors duration-150 hover:bg-white/10 hover:text-hi focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
            >
              <X size={14} aria-hidden />
            </button>
          )}
        </div>
      )}

      {/* The pill itself. The whole thing lights on focus, so the input inside
          it carries no border or glow of its own. */}
      <form
        onSubmit={onSubmit}
        className="glass-bar flex items-center gap-2 rounded-2xl border border-line p-2 transition-[border-color,box-shadow] duration-200 focus-within:border-accent/50 focus-within:shadow-glow"
      >
        <label htmlFor="askbar" className="sr-only">
          Ask about SOPs, manuals, and audit documents
        </label>
        <div className="relative flex-1">
          <Search
            size={16}
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-faint"
          />
          <Input
            id="askbar"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about SOPs, manuals, and audit documents…"
            className="h-10 border-0 bg-transparent pl-9 focus-visible:shadow-none"
            autoComplete="off"
          />
        </div>
        <Button type="submit" size="sm" disabled={busy || !query.trim()} className="shrink-0">
          {busy ? <Loader2 size={14} className="animate-spin" aria-hidden /> : 'Ask'}
        </Button>
      </form>
    </div>
  )
}
