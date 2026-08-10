import { useState, type FormEvent } from 'react'
import { ChevronDown, FileText, Loader2, Search, Sparkles, X } from 'lucide-react'
import { api } from '../api/client'
import type { ExplainResponse, SearchResponse, SopResult } from '../api/types'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { SkeletonLines } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'

/**
 * Persistent ask bar -> POST /api/search, then POST /api/explain. Documents
 * only (CLAUDE.md rule 8).
 *
 * Two steps on purpose. Retrieval runs first and has no model in it, so SOP
 * sections appear almost instantly; the model is only invoked when the user
 * expands a section and asks for it. That keeps the slow, failure-prone part
 * opt-in, and it never blocks the first result.
 *
 * Fixed to the bottom of the viewport and rendered by the layout, so it
 * survives both scrolling and screen changes. It floats as a self-contained
 * glass pill at 08dp — 12% white overlay — rather than a full-bleed strip, so
 * the page stays visible on both sides of it. Results expand UPWARD above the
 * input, capped and scrollable, so a long list never pushes the input off
 * screen.
 *
 * No intent routing lives here or anywhere else on the client. Queries the
 * corpus cannot answer come back with zero results and a `fallbackMessage` set
 * by the backend's similarity floor, rather than a wrong answer.
 */
export default function AskBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SopResult[] | null>(null)
  const [kind, setKind] = useState<SearchResponse['kind'] | null>(null)
  const [reply, setReply] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [fallback, setFallback] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<ExplainResponse | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  const [explaining, setExplaining] = useState(false)

  // Two, not three: the backend's floor is two characters so that "hi" and
  // "yo" reach the conversational shell.
  const canSubmit = query.trim().length >= 2 && !searching

  /** Shared by the form and the suggestion chips. */
  async function runSearch(raw: string) {
    const q = raw.trim()
    if (q.length < 2) return

    setSearching(true)
    setExplanation(null)
    setExpandedId(null)
    setFallback(null)
    setReply(null)
    setSuggestions([])
    try {
      const data = await api.search(q)
      setResults(data.results)
      setKind(data.kind)
      setReply(data.reply)
      setSuggestions(data.suggestions ?? [])
      setFallback(data.fallbackMessage)
    } catch (err) {
      console.error('[askbar] search failed:', err)
      setResults([])
      setKind('off_topic')
      setFallback('Search is unavailable right now.')
    } finally {
      setSearching(false)
    }
  }

  function onSearch(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    void runSearch(query)
  }

  /** Chips put their text in the box first, so the query the user "asked" is
   *  the one /api/explain later receives. */
  function onSuggestion(text: string) {
    setQuery(text)
    void runSearch(text)
  }

  async function onExplain(sopIds: string[]) {
    setExplaining(true)
    try {
      setExplanation(await api.explain(query.trim(), sopIds))
    } catch (err) {
      console.error('[askbar] explain failed:', err)
    } finally {
      setExplaining(false)
    }
  }

  function dismiss() {
    setResults(null)
    setKind(null)
    setReply(null)
    setSuggestions([])
    setFallback(null)
    setExplanation(null)
    setExpandedId(null)
  }

  const open = searching || results !== null

  return (
    <div className="fixed bottom-6 left-1/2 z-50 w-[min(100%-2rem,42rem)] -translate-x-1/2">
      {open && (
        <div className="glass-bar relative mb-2 max-h-[45vh] overflow-y-auto rounded-2xl border border-line p-4">
          {searching ? (
            <SkeletonLines lines={2} />
          ) : (
            <>
              {results && results.length > 0 && (
                <ul className="space-y-2 pr-8">
                  {results.map((r) => (
                    <li key={r.id} className="overflow-hidden rounded-lg bg-white/[0.06]">
                      <button
                        type="button"
                        onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                        aria-expanded={expandedId === r.id}
                        className="flex w-full cursor-pointer items-start justify-between gap-3 p-3 text-left transition-colors duration-150 hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                      >
                        <span className="min-w-0">
                          <span className="flex flex-wrap items-center gap-2">
                            <FileText size={12} className="shrink-0 text-accent" aria-hidden />
                            <span className="data-figure text-[12px] text-accent">{r.docId}</span>
                            <span className="text-xs text-hi">{r.title}</span>
                          </span>
                          <span className="mt-0.5 block text-[12px] text-faint">{r.section}</span>
                        </span>
                        <ChevronDown
                          size={14}
                          aria-hidden
                          className={cn(
                            'mt-0.5 shrink-0 transition-transform duration-200',
                            expandedId === r.id ? 'rotate-180 text-accent' : 'text-faint',
                          )}
                        />
                      </button>

                      {expandedId === r.id && (
                        <div className="border-t border-line p-3">
                          <p className="text-[12px] leading-relaxed whitespace-pre-line text-muted">
                            {r.content}
                          </p>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => onExplain([r.id])}
                            disabled={explaining}
                            className="mt-3"
                          >
                            {explaining ? (
                              <Loader2 size={13} className="animate-spin" aria-hidden />
                            ) : (
                              <Sparkles size={13} aria-hidden />
                            )}
                            Explain step by step
                          </Button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              {/* Generated. Sources always render; everything above them may be
                  null if the model failed, and the SOP text is unaffected. */}
              {explanation && (
                <div className="mt-3 rounded-r-lg border-l-2 border-accent bg-white/[0.05] p-4 shadow-glow">
                  {explanation.explanation ? (
                    <>
                      <p className="text-sm leading-relaxed text-hi">{explanation.explanation}</p>

                      {explanation.steps && (
                        <ol className="mt-3 space-y-1.5">
                          {explanation.steps.map((step, i) => (
                            <li key={i} className="flex gap-2.5 text-xs leading-relaxed">
                              <span className="data-figure shrink-0 text-accent">{i + 1}.</span>
                              <span>
                                <span className="text-hi">{step.action}</span>
                                <span className="text-muted"> — {step.why}</span>
                              </span>
                            </li>
                          ))}
                        </ol>
                      )}

                      {explanation.commonMistake && (
                        <p className="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-muted">
                          <span className="text-error">Common mistake: </span>
                          {explanation.commonMistake}
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-muted">
                      Explanation unavailable. The SOP text above is unchanged.
                    </p>
                  )}

                  <p className="mt-3 text-[12px] text-faint">
                    Sources: {explanation.sources.join(', ')}
                    {explanation.estimatedMinutes !== null && (
                      <> · est. {explanation.estimatedMinutes} min</>
                    )}
                  </p>
                </div>
              )}

              {/* Conversational turn — a greeting or "what can you do".
                  Matched by regex server-side, so this costs no model call
                  and returns in about a millisecond. */}
              {kind === 'conversation' && reply && (
                <p className="pr-8 text-sm leading-relaxed text-hi">{reply}</p>
              )}

              {/* Spec 7.1 redirect, an empty corpus, or an unreachable API. */}
              {kind !== 'conversation' && results?.length === 0 && (
                <p className="pr-8 text-sm text-muted">
                  {fallback ?? 'No SOPs found. Try different keywords.'}
                </p>
              )}

              {/* Every chip is drawn from the indexed corpus, so each one is
                  guaranteed to return sections. This is the recovery path
                  when someone asks something the SOPs cannot answer. */}
              {suggestions.length > 0 && (
                <div className="mt-3 pr-8">
                  <p className="label-caps mb-2">Try asking</p>
                  <ul className="flex flex-wrap gap-1.5">
                    {suggestions.map((s) => (
                      <li key={s}>
                        <button
                          type="button"
                          onClick={() => onSuggestion(s)}
                          disabled={searching}
                          className="cursor-pointer rounded-full border border-line bg-white/[0.06] px-3 py-1 text-[12px] text-muted transition-colors duration-150 hover:bg-white/10 hover:text-hi focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:opacity-50"
                        >
                          {s}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {results && (
            <button
              type="button"
              onClick={dismiss}
              aria-label="Dismiss results"
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
        onSubmit={onSearch}
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
            placeholder="Ask about SOPs, procedures, troubleshooting…"
            className="h-10 border-0 bg-transparent pl-9 focus-visible:shadow-none"
            autoComplete="off"
          />
        </div>
        <Button type="submit" size="sm" disabled={!canSubmit} className="shrink-0">
          {searching ? <Loader2 size={14} className="animate-spin" aria-hidden /> : 'Ask'}
        </Button>
      </form>
    </div>
  )
}
