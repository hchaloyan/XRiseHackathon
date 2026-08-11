import { useEffect, useRef } from 'react'
import { ArrowLeft, Loader2 } from 'lucide-react'
import type { SopDocument } from '../api/types'
import { Button } from './ui/Button'
import { SkeletonLines } from './ui/Skeleton'

/**
 * Renders one SOP inside the ask bar panel and scrolls to the section the
 * result came from.
 *
 * Not a modal and not a route (CLAUDE.md rule 7): it replaces the result list
 * in place, and Back returns to the same results. The demo never navigates
 * away from the single screen.
 *
 * The markdown renderer below is deliberately about forty lines rather than a
 * dependency. The corpus is hand-written and uses six constructs — headings,
 * ordered and unordered lists, bold, inline code, paragraphs — so a parser
 * that handles those is complete for this input, and adding react-markdown at
 * this point costs an install and a bundle for no visible gain.
 */

/** Stable id per heading, matched against the chunk's `section` metadata. */
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

/** Bold and inline code, the only inline markup the SOPs use. */
function inline(text: string, keyPrefix: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={key} className="font-medium text-hi">
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={key} className="data-figure rounded bg-white/[0.08] px-1 text-[11px]">
          {part.slice(1, -1)}
        </code>
      )
    }
    return <span key={key}>{part}</span>
  })
}

function renderMarkdown(markdown: string) {
  const blocks: React.ReactNode[] = []
  const lines = markdown.split('\n')
  let paragraph: string[] = []
  let list: { ordered: boolean; items: string[] } | null = null

  const flushParagraph = () => {
    if (!paragraph.length) return
    const text = paragraph.join(' ')
    blocks.push(
      <p key={`p-${blocks.length}`} className="mt-2 text-[12px] leading-relaxed text-muted">
        {inline(text, `p-${blocks.length}`)}
      </p>,
    )
    paragraph = []
  }

  const flushList = () => {
    if (!list) return
    const { ordered, items } = list
    const Tag = ordered ? 'ol' : 'ul'
    blocks.push(
      <Tag
        key={`l-${blocks.length}`}
        className={`mt-2 space-y-1 pl-5 text-[12px] leading-relaxed text-muted ${
          ordered ? 'list-decimal' : 'list-disc'
        }`}
      >
        {items.map((item, i) => (
          <li key={i}>{inline(item, `l-${blocks.length}-${i}`)}</li>
        ))}
      </Tag>,
    )
    list = null
  }

  for (const raw of lines) {
    const line = raw.trimEnd()

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      flushParagraph()
      flushList()
      const level = heading[1].length
      const text = heading[2].trim()
      blocks.push(
        <h3
          key={`h-${blocks.length}`}
          id={slugify(text)}
          className={
            level === 1
              ? 'mt-5 scroll-mt-3 border-b border-line pb-1 text-sm font-semibold text-hi first:mt-0'
              : 'mt-4 scroll-mt-3 text-[13px] font-medium text-hi'
          }
        >
          {text}
        </h3>,
      )
      continue
    }

    const ordered = /^\s*\d+\.\s+(.*)$/.exec(line)
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line)
    if (ordered || bullet) {
      flushParagraph()
      const isOrdered = Boolean(ordered)
      const item = (ordered ? ordered[1] : bullet![1]).trim()
      if (!list || list.ordered !== isOrdered) {
        flushList()
        list = { ordered: isOrdered, items: [] }
      }
      list.items.push(item)
      continue
    }

    if (!line.trim()) {
      flushParagraph()
      flushList()
      continue
    }

    flushList()
    paragraph.push(line.trim())
  }

  flushParagraph()
  flushList()
  return blocks
}

export default function SopViewer({
  doc,
  section,
  loading,
  onBack,
}: {
  doc: SopDocument | null
  /** Heading to scroll to, from the result's metadata. */
  section: string | null
  loading: boolean
  onBack: () => void
}) {
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!doc || !section) return
    // After paint: the headings do not exist until this render commits.
    const id = window.requestAnimationFrame(() => {
      const target = bodyRef.current?.querySelector(`#${CSS.escape(slugify(section))}`)
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
    return () => window.cancelAnimationFrame(id)
  }, [doc, section])

  return (
    <div className="pr-8">
      <div className="mb-3 flex items-start justify-between gap-3 border-b border-line pb-3">
        <div className="min-w-0">
          <p className="data-figure text-[12px] text-accent">{doc?.docId ?? '…'}</p>
          <h3 className="text-xs text-hi">{doc?.title ?? 'Loading document'}</h3>
          {doc && (
            <p className="mt-0.5 text-[11px] text-faint">
              Rev {doc.revision} · {doc.department}
              {section && <> · showing “{section}”</>}
            </p>
          )}
        </div>
        <Button type="button" size="sm" variant="outline" onClick={onBack} className="shrink-0">
          <ArrowLeft size={13} aria-hidden />
          Back
        </Button>
      </div>

      <div ref={bodyRef}>
        {loading || !doc ? (
          <div className="flex items-center gap-2 text-[12px] text-muted">
            <Loader2 size={13} className="animate-spin" aria-hidden />
            <SkeletonLines lines={4} />
          </div>
        ) : (
          renderMarkdown(doc.markdown)
        )}
      </div>
    </div>
  )
}
