'use client'

import { useRef, useState } from 'react'
import type { DatasetSummary } from '@/lib/api'
import { Stub, StubButton } from './Stub'

interface DatasetPanelProps {
  dataset: DatasetSummary | null
  uploading: boolean
  error: string | null
  onUpload: (file: File) => void
}

export function DatasetPanel({ dataset, uploading, error, onUpload }: DatasetPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function pick(file: File | undefined) {
    if (file) onUpload(file)
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900">Dataset</h2>
        <div className="flex items-center gap-2">
          <StubButton label="Excel sheet picker" phase="Phase 3" />
          <StubButton label="Add file / join" phase="Phase 3" />
        </div>
      </div>

      {/* Upload dropzone */}
      <label
        data-testid="upload-dropzone"
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          pick(e.dataTransfer.files?.[0])
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
          dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 bg-white hover:border-gray-400'
        } ${uploading ? 'pointer-events-none opacity-60' : ''}`}
      >
        <input
          ref={inputRef}
          data-testid="file-input"
          type="file"
          accept=".csv,text/csv"
          disabled={uploading}
          onChange={(e) => pick(e.target.files?.[0])}
          className="sr-only"
        />
        {uploading ? (
          <span data-testid="upload-loading" className="text-sm text-gray-500">
            Uploading &amp; profiling…
          </span>
        ) : (
          <>
            <span className="text-sm font-medium text-gray-700">
              Drop a CSV here, or click to choose
            </span>
            <span className="mt-1 text-xs text-gray-400">
              One CSV per workspace in Phase 1. Data stays on your machine.
            </span>
          </>
        )}
      </label>

      {error && (
        <div
          data-testid="upload-error"
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {dataset && <SchemaPreview dataset={dataset} />}
    </section>
  )
}

function SchemaPreview({ dataset }: { dataset: DatasetSummary }) {
  const pii = dataset.pii_columns ?? []
  return (
    <div data-testid="schema-preview" className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-gray-900" data-testid="dataset-filename">
            {dataset.filename}
          </p>
          <p className="text-xs text-gray-500">
            <span data-testid="dataset-row-count">{dataset.row_count.toLocaleString()}</span> rows ·{' '}
            {dataset.column_count} columns
          </p>
        </div>
        {pii.length > 0 && (
          <span
            data-testid="pii-badge"
            className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-medium text-amber-800"
            title="These columns are masked before anything is sent to the model."
          >
            PII masked: {pii.join(', ')}
          </span>
        )}
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-xs" data-testid="schema-table">
          <thead>
            <tr className="border-b border-gray-100 text-gray-400">
              <th className="py-1.5 pr-4 font-medium">Column</th>
              <th className="py-1.5 pr-4 font-medium">Type</th>
              <th className="py-1.5 font-medium">Notes</th>
            </tr>
          </thead>
          <tbody>
            {dataset.schema.map((col) => (
              <tr key={col.name} className="border-b border-gray-50 last:border-0">
                <td className="py-1.5 pr-4 font-mono text-gray-800" data-testid="schema-col-name">
                  {col.name}
                  {pii.includes(col.name) && (
                    <span className="ml-1.5 rounded bg-amber-50 px-1 py-0.5 text-[9px] font-semibold uppercase text-amber-700">
                      PII
                    </span>
                  )}
                </td>
                <td className="py-1.5 pr-4 font-mono text-gray-500">{col.dtype}</td>
                <td className="py-1.5 text-gray-400">
                  <StubInlineNote />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3">
        <Stub title="Data-quality checks" phase="Phase 2" compact>
          Nulls, duplicates, and outlier flags will appear here.
        </Stub>
      </div>
    </div>
  )
}

// Per-column notes are a Phase 3 feature — shown as a muted placeholder.
function StubInlineNote() {
  return (
    <span
      data-testid="stub-column-note"
      title="Column notes — Phase 3, coming soon"
      className="text-[10px] italic text-gray-300"
    >
      notes — Phase 3
    </span>
  )
}
