'use client'

import { useState } from 'react'
import type { WorkspaceListItem } from '@/lib/api'

interface SidebarProps {
  workspaces: WorkspaceListItem[]
  selectedId: string | null
  loading: boolean
  onSelect: (id: string) => void
  onCreate: (name: string) => Promise<void>
}

export function Sidebar({ workspaces, selectedId, loading, onSelect, onCreate }: SidebarProps) {
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-gray-200 bg-white">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-4">
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-gray-900">Data Analysis Agent</h1>
          <p className="text-[11px] text-gray-400">Private · runs on your machine</p>
        </div>
      </div>

      <div className="px-4 py-3">
        <button
          type="button"
          data-testid="new-workspace-button"
          onClick={() => setModalOpen(true)}
          className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700"
        >
          + New workspace
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-4">
        <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
          Workspaces
        </p>

        {loading && (
          <div data-testid="workspaces-loading" className="space-y-1 px-2 py-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded-lg bg-gray-100" />
            ))}
          </div>
        )}

        {!loading && workspaces.length === 0 && (
          <p
            data-testid="workspaces-empty"
            className="px-2 py-6 text-center text-xs text-gray-400"
          >
            Create a workspace to begin.
          </p>
        )}

        <ul data-testid="workspace-list" className="space-y-1">
          {workspaces.map((ws) => {
            const active = ws.id === selectedId
            return (
              <li key={ws.id}>
                <button
                  type="button"
                  data-testid="workspace-item"
                  data-workspace-name={ws.name}
                  onClick={() => onSelect(ws.id)}
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
                    active
                      ? 'bg-blue-50 font-medium text-blue-700'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <span className="truncate">{ws.name}</span>
                  <span className="ml-2 shrink-0 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">
                    {ws.dataset_count} {ws.dataset_count === 1 ? 'file' : 'files'}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </div>

      {modalOpen && (
        <NewWorkspaceModal
          onClose={() => setModalOpen(false)}
          onCreate={onCreate}
        />
      )}
    </aside>
  )
}

function NewWorkspaceModal({
  onClose,
  onCreate,
}: {
  onClose: () => void
  onCreate: (name: string) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Please enter a workspace name.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await onCreate(trimmed)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create workspace.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Create workspace"
      data-testid="new-workspace-modal"
    >
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"
      >
        <h2 className="text-base font-semibold text-gray-900">New workspace</h2>
        <p className="mt-1 text-xs text-gray-500">
          Give it a name, e.g. &ldquo;Q2 loan book&rdquo;.
        </p>
        <input
          autoFocus
          data-testid="workspace-name-input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Q2 loan book"
          disabled={submitting}
          className="mt-4 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        {error && (
          <p data-testid="workspace-modal-error" className="mt-2 text-xs text-red-600">
            {error}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            data-testid="workspace-create-submit"
            disabled={submitting || !name.trim()}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? 'Creating…' : 'Create'}
          </button>
        </div>
      </form>
    </div>
  )
}
