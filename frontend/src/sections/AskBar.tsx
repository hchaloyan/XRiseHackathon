import { useState, type FormEvent } from 'react'
import { BarChart3, BookOpen, ChevronDown, FileText, Loader2, Search, X } from 'lucide-react'
import { api } from '../api/client'
import type { SearchResponse, SopDocument, SopResult } from '../api/types'
import SopViewer from '../components/SopViewer'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { SkeletonLines } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'
import { useDay } from '../lib/day'

/**
 * Persistent ask bar -> POST /api/search. Documents only (CLAUDE.md rule 8).
 *
 * No model runs on this path at all. Retrieval returns the matching sections,
 * and "View in SOP-00X" opens the source document from disk. An earlier
 * "Explain step by step" button re-summarised text already on screen, which
 * cost 3 seconds and added nothing.
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
  const { setDay } = useDay()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SopResult[] | null>(null)
  const [kind, setKind] = useState<SearchResponse['kind'] | null>(null)
  const [reply, setReply] = useState<string | null>(null)
  const [disclaimer, setDisclaimer] = useState<string | null>(null)
  const [metricDay, setMetricDay] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [fallback, setFallback] = useState<string | null>(null)
  // The last query that actually returned sections. Sent as context so a
  // fragment like "what about the 500T?" can be resolved against it. Only
  // successful queries are remembered — carrying a miss forward would drag a
  // dead end into the next question.
  const [lastAnswered, setLastAnswered] = useState<string | null>(null)
  const [resolvedFrom, setResolvedFrom] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)

  // In-app document view. `viewing` holds the section to scroll to; the
  // document itself is cached so reopening the same SOP is instant.
  const [viewing, setViewing] = useState<{ docId: string; section: string } | null>(null)
  const [doc, setDoc] = useState<SopDocument | null>(null)
  const [loadingDoc, setLoadingDoc] = useState(false)

  // Two, not three: the backend's floor is two characters so that "hi" and
  // "yo" reach the conversational shell.
  const canSubmit = query.trim().length >= 2 && !searching

  /** Shared by the form and the suggestion chips. */
  async function runSearch(raw: string) {
    const q = raw.trim()
    if (q.length < 2) return

    setSearching(true)
    setExpandedId(null)
    setFallback(null)
    setReply(null)
    setDisclaimer(null)
    setMetricDay(null)
    setSuggestions([])
    setResolvedFrom(null)
    try {
      const data = await api.search(q, lastAnswered)
      setResults(data.results)
      setKind(data.kind)
      setReply(data.reply)
      setDisclaimer(data.disclaimer)
      setMetricDay(data.kind === 'metric' && !data.metricIsCurrent ? data.metricDay : null)
      setSuggestions(data.suggestions ?? [])
      setResolvedFrom(data.resolvedFrom)
      setFallback(data.fallbackMessage)
      if (data.kind === 'results') setLastAnswered(q)
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

  /** Chips put their text in the box, so the input reflects what was asked. */
  function onSuggestion(text: string) {
    setQuery(text)
    void runSearch(text)
  }

  async function onView(docId: string, section: string) {
    setViewing({ docId, section })
    if (doc?.docId === docId) return // already loaded; the effect re-scrolls
    setLoadingDoc(true)
    setDoc(null)
    try {
      setDoc(await api.sop(docId))
    } catch (err) {
      console.error('[askbar] document load failed:', err)
      setViewing(null)
    } finally {
      setLoadingDoc(false)
    }
  }

  function dismiss() {
    setResults(null)
    setKind(null)
    setReply(null)
    setDisclaimer(null)
    setMetricDay(null)
    setSuggestions([])
    setFallback(null)
    setExpandedId(null)
    setViewing(null)
    setResolvedFrom(null)
    // Dismissing ends the thread: the next question starts clean rather than
    // being read as a follow-up to something no longer on screen.
    setLastAnswered(null)
  }

  const open = searching || results !== null || viewing !== null

  return (
    <div className="fixed bottom-6 left-1/2 z-50 w-[min(100%-2rem,42rem)] -translate-x-1/2">
      {open && (
        <div className="glass-bar relative mb-2 max-h-[45vh] overflow-y-auto rounded-2xl border border-line p-4">
          {viewing ? (
            <SopViewer
              doc={doc}
              section={viewing.section}
              loading={loadingDoc}
              onBack={() => setViewing(null)}
            />
          ) : searching ? (
            <SkeletonLines lines={2} />
          ) : (
            <>
              {/* Say so when a fragment was resolved against the previous
                  question, rather than appearing to answer it by magic. */}
              {resolvedFrom && results && results.length > 0 && (
                <p className="mb-2 pr-8 text-[12px] text-faint">
                  Following up on “{resolvedFrom}”
                </p>
              )}

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
                        {/* Document id and section on one line. Summarising a
                            single SOP returns several of its sections, and
                            repeating the document title on every row said
                            nothing — the section is the part that differs. */}
                        <span className="flex min-w-0 flex-wrap items-center gap-2">
                          <FileText size={12} className="shrink-0 text-accent" aria-hidden />
                          <span className="data-figure text-[12px] text-accent">{r.docId}</span>
                          <span className="text-xs text-hi">{r.section}</span>
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
                          {/* The section text is already on screen above, so
                              re-explaining it added a slow model call for no
                              new information. Opening the source document is
                              the thing a supervisor actually wants next. */}
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => onView(r.docId, r.section)}
                            disabled={loadingDoc}
                            className="mt-3"
                          >
                            {loadingDoc ? (
                              <Loader2 size={13} className="animate-spin" aria-hidden />
                            ) : (
                              <BookOpen size={13} aria-hidden />
                            )}
                            View in {r.docId}
                          </Button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              {/* Conversational turn — a greeting or "what can you do".
                  Matched by regex server-side, so this costs no model call
                  and returns in about a millisecond. */}
              {kind === 'conversation' && reply && (
                <p className="pr-8 text-sm leading-relaxed text-hi">{reply}</p>
              )}

              {/* A figure from the plant's own data. Computed in pandas, so
                  this is an answer rather than a redirect — and it carries the
                  day, because "yesterday's OEE" is meaningless without it. */}
              {kind === 'metric' && reply && (
                <div className="mr-8 rounded-r-lg border-l-2 border-accent bg-white/[0.05] p-4">
                  <p className="text-sm leading-relaxed text-hi">{reply}</p>
                  {metricDay && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="mt-3"
                      onClick={() => {
                        setDay(metricDay)
                        dismiss()
                      }}
                    >
                      <BarChart3 size={13} aria-hidden />
                      Show the {metricDay} briefing
                    </Button>
                  )}
                </div>
              )}

              {/* General knowledge — the SOPs do not cover this. The
                  disclaimer is not decoration: without it a model's general
                  answer reads as plant procedure. Dashed border and no accent
                  glow, so it never looks as authoritative as a real citation. */}
              {kind === 'general' && reply && (
                <div className="mr-8 rounded-lg border border-dashed border-line bg-white/[0.03] p-3">
                  <p className="label-caps mb-1.5 text-faint">
                    {disclaimer ?? 'Not from your SOPs — general guidance.'}
                  </p>
                  <p className="text-sm leading-relaxed text-muted">{reply}</p>
                </div>
              )}

              {/* Spec 7.1 redirect, an empty corpus, or an unreachable API. */}
              {kind !== 'conversation' &&
                kind !== 'general' &&
                kind !== 'metric' &&
                results?.length === 0 && (
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
