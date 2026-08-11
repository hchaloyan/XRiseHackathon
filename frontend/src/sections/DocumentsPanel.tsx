import { useCallback, useRef, useState } from 'react'
import {
  AlertCircle,
  BookOpen,
  Download,
  FileText,
  Loader2,
  Trash2,
  Upload,
} from 'lucide-react'
import { api } from '../api/client'
import type { DocumentMeta } from '../api/types'
import SopViewer from '../components/SopViewer'
import { Button } from '../components/ui/Button'
import { Card, CardLabel } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'
import { useFetch } from '../lib/useFetch'

/**
 * Every document the assistant can answer from, in one place.
 *
 * Uploads are not a separate library sitting beside the SOPs — they are
 * chunked, embedded and cited by exactly the same machinery, so a manual added
 * here is searchable from the ask bar seconds later. That is the whole point of
 * the document registry behind it; this screen is just the door.
 *
 * Rejections are shown verbatim from the API. "This does not read like
 * manufacturing documentation" tells a supervisor what to do next; a red toast
 * saying "upload failed" does not.
 */

function readableSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function readableDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function DocumentsPanel() {
  const [reloadKey, setReloadKey] = useState(0)
  const { data, loading } = useFetch(api.documents, reloadKey)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [viewing, setViewing] = useState<DocumentMeta | null>(null)
  const [docText, setDocText] = useState<{ markdown: string; title: string } | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const refresh = () => setReloadKey((k) => k + 1)

  const send = useCallback(async (file: File) => {
    setUploading(true)
    setError(null)
    setNotice(null)
    try {
      const meta = await api.uploadDocument(file)
      setNotice(
        `${meta.docId} added — ${meta.chunks} sections indexed. You can ask about it now.`,
      )
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }, [])

  async function onView(doc: DocumentMeta) {
    setViewing(doc)
    setDocText(null)
    try {
      const full = await api.sop(doc.docId)
      setDocText({ markdown: full.markdown, title: full.title })
    } catch {
      setDocText({ markdown: '_This document could not be opened._', title: doc.title })
    }
  }

  async function onDelete(doc: DocumentMeta) {
    if (!confirm(`Remove ${doc.docId} and its indexed sections?`)) return
    try {
      await api.deleteDocument(doc.docId)
      setNotice(`${doc.docId} removed.`)
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove it.')
    }
  }

  if (viewing) {
    return (
      <Card size="lg">
        <SopViewer
          doc={
            docText
              ? {
                  docId: viewing.docId,
                  title: docText.title,
                  revision: viewing.revision,
                  department: viewing.department,
                  markdown: docText.markdown,
                }
              : null
          }
          section={null}
          loading={!docText}
          onBack={() => setViewing(null)}
        />
      </Card>
    )
  }

  const documents = data?.documents ?? []
  const uploads = documents.filter((d) => d.source === 'upload')
  const sops = documents.filter((d) => d.source === 'sop')
  const accepted = data?.acceptedFormats ?? ['.pdf', '.docx', '.md', '.txt', '.csv']

  return (
    <div className="space-y-4">
      <Card size="lg">
        <CardLabel>Add a document</CardLabel>

        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            const file = e.dataTransfer.files?.[0]
            if (file) void send(file)
          }}
          className={cn(
            'mt-3 flex flex-col items-center justify-center rounded-xl border border-dashed px-6 py-10 text-center transition-colors duration-150',
            dragging ? 'border-accent bg-white/[0.06]' : 'border-line bg-white/[0.02]',
          )}
        >
          {uploading ? (
            <Loader2 size={22} className="animate-spin text-accent" aria-hidden />
          ) : (
            <Upload size={22} className="text-faint" aria-hidden />
          )}
          <p className="mt-3 text-sm text-hi">
            {uploading ? 'Reading and indexing…' : 'Drop a file here'}
          </p>
          <p className="mt-1 text-[12px] text-faint">
            {accepted.join(' · ')} · up to {Math.round((data?.maxBytes ?? 15728640) / 1048576)} MB
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mt-4"
            disabled={uploading}
            onClick={() => fileInput.current?.click()}
          >
            Choose a file
          </Button>
          <input
            ref={fileInput}
            type="file"
            accept={accepted.join(',')}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void send(file)
              e.target.value = '' // re-selecting the same file must still fire
            }}
          />
        </div>

        {error && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-error/40 bg-error/10 p-3">
            <AlertCircle size={14} className="mt-0.5 shrink-0 text-error" aria-hidden />
            <p className="text-xs leading-relaxed text-hi">{error}</p>
          </div>
        )}
        {notice && !error && (
          <p className="mt-3 rounded-lg border border-line bg-white/[0.04] p-3 text-xs text-muted">
            {notice}
          </p>
        )}
      </Card>

      <DocumentTable
        label={`Uploaded (${uploads.length})`}
        documents={uploads}
        loading={loading}
        onView={onView}
        onDelete={onDelete}
        empty="Nothing uploaded yet. Anything you add here becomes searchable in the ask bar."
      />

      <DocumentTable
        label={`Standard operating procedures (${sops.length})`}
        documents={sops}
        loading={loading}
        onView={onView}
        empty="No SOPs found in data/sops."
      />
    </div>
  )
}

function DocumentTable({
  label,
  documents,
  loading,
  onView,
  onDelete,
  empty,
}: {
  label: string
  documents: DocumentMeta[]
  loading: boolean
  onView: (doc: DocumentMeta) => void
  onDelete?: (doc: DocumentMeta) => void
  empty: string
}) {
  return (
    <Card size="lg">
      <CardLabel>{label}</CardLabel>

      {loading ? (
        <div className="mt-4 space-y-2">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : documents.length === 0 ? (
        <p className="mt-4 text-xs text-muted">{empty}</p>
      ) : (
        <ul className="mt-3 divide-y divide-line">
          {documents.map((doc) => (
            <li key={doc.docId} className="flex items-center gap-3 py-2.5">
              <FileText size={13} className="shrink-0 text-accent" aria-hidden />

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="data-figure text-[12px] text-accent">{doc.docId}</span>
                  <span className="truncate text-xs text-hi">{doc.title}</span>
                </div>
                <div className="label-caps mt-0.5 text-faint">
                  {doc.format.replace('.', '')} · {readableSize(doc.sizeBytes)}
                  {doc.department && ` · ${doc.department}`}
                  {doc.chunks > 0 && ` · ${doc.chunks} sections indexed`}
                  {doc.uploadedAt && ` · ${readableDate(doc.uploadedAt)}`}
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={() => onView(doc)}
                  aria-label={`View ${doc.docId}`}
                  className="cursor-pointer rounded p-1.5 text-muted transition-colors duration-150 hover:bg-white/10 hover:text-hi"
                >
                  <BookOpen size={14} aria-hidden />
                </button>
                <a
                  href={api.documentDownloadUrl(doc.docId)}
                  aria-label={`Download ${doc.docId}`}
                  className="rounded p-1.5 text-muted transition-colors duration-150 hover:bg-white/10 hover:text-hi"
                >
                  <Download size={14} aria-hidden />
                </a>
                {onDelete && (
                  <button
                    type="button"
                    onClick={() => onDelete(doc)}
                    aria-label={`Remove ${doc.docId}`}
                    className="cursor-pointer rounded p-1.5 text-muted transition-colors duration-150 hover:bg-error/20 hover:text-error"
                  >
                    <Trash2 size={14} aria-hidden />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
