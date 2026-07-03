'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  ask as apiAsk,
  askStream,
  createWorkspace,
  getWorkspace,
  listWorkspaces,
  uploadDataset,
  type DatasetSummary,
  type RunDetail,
  type WorkspaceListItem,
} from '@/lib/api'
import { Sidebar } from './components/Sidebar'
import { DatasetPanel } from './components/DatasetPanel'
import { AskPanel, type ConversationTurn } from './components/AskPanel'
import { RunHistoryPanel } from './components/RunHistoryPanel'
import { Stub } from './components/Stub'

function newTurnId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export default function Home() {
  const [workspaces, setWorkspaces] = useState<WorkspaceListItem[]>([])
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [dataset, setDataset] = useState<DatasetSummary | null>(null)

  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState<string | null>(null)
  const [turns, setTurns] = useState<ConversationTurn[]>([])
  const [historyRefresh, setHistoryRefresh] = useState(0)

  const refreshWorkspaces = useCallback(async () => {
    setLoadingWorkspaces(true)
    setListError(null)
    try {
      setWorkspaces(await listWorkspaces())
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'Failed to load workspaces.')
    } finally {
      setLoadingWorkspaces(false)
    }
  }, [])

  useEffect(() => {
    void refreshWorkspaces()
  }, [refreshWorkspaces])

  const openWorkspace = useCallback(async (id: string) => {
    setSelectedId(id)
    setDataset(null)
    setUploadError(null)
    setAskError(null)
    setTurns([])
    setHistoryRefresh((k) => k + 1)
    try {
      const detail = await getWorkspace(id)
      setDataset(detail.datasets[0] ?? null)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Failed to open workspace.')
    }
  }, [])

  async function handleCreate(name: string) {
    const created = await createWorkspace(name)
    await refreshWorkspaces()
    await openWorkspace(created.id)
  }

  async function handleUpload(file: File) {
    if (!selectedId) return
    setUploading(true)
    setUploadError(null)
    setTurns([])
    setAskError(null)
    try {
      const ds = await uploadDataset(selectedId, file)
      setDataset(ds)
      await refreshWorkspaces()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const patchTurn = useCallback((id: string, patch: Partial<ConversationTurn>) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)))
  }, [])

  const appendDelta = useCallback((id: string, text: string) => {
    setTurns((prev) =>
      prev.map((t) => (t.id === id ? { ...t, streamingText: t.streamingText + text } : t)),
    )
  }, [])

  async function handleAsk(question: string) {
    const q = question.trim()
    if (!selectedId || !q || asking) return

    const turnId = newTurnId()
    setTurns((prev) => [
      ...prev,
      { id: turnId, question: q, streamingText: '', result: null, status: 'streaming', error: null },
    ])
    setAsking(true)
    setAskError(null)

    const datasetId = dataset?.id ?? null

    try {
      // Preferred path: stream the answer progressively via SSE.
      await askStream(selectedId, q, datasetId, {
        onDelta: (text) => appendDelta(turnId, text),
        onFinal: (result) => patchTurn(turnId, { result, status: 'done' }),
      })
    } catch {
      // Any streaming failure/unsupported → transparently fall back to /ask,
      // which returns the same fully-enriched payload.
      try {
        const result = await apiAsk(selectedId, q, datasetId)
        patchTurn(turnId, { result, status: 'done', streamingText: '' })
      } catch (err2) {
        const message =
          err2 instanceof ApiError
            ? err2.message
            : err2 instanceof Error
              ? err2.message
              : 'The question could not be answered.'
        patchTurn(turnId, { status: 'error', error: message })
        setAskError(message)
      }
    } finally {
      setAsking(false)
      setHistoryRefresh((k) => k + 1)
    }
  }

  const openPastRun = useCallback((detail: RunDetail) => {
    setTurns((prev) => [
      ...prev,
      {
        id: newTurnId(),
        question: detail.question,
        streamingText: '',
        result: detail,
        status: 'done',
        error: null,
      },
    ])
  }, [])

  const selected = workspaces.find((w) => w.id === selectedId) ?? null

  return (
    <div className="flex h-screen">
      <Sidebar
        workspaces={workspaces}
        selectedId={selectedId}
        loading={loadingWorkspaces}
        onSelect={openWorkspace}
        onCreate={handleCreate}
      />

      <main className="flex-1 overflow-y-auto bg-gray-50 dark:bg-slate-950">
        <div className="mx-auto max-w-3xl px-8 py-10">
          {listError && (
            <div
              data-testid="list-error"
              className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
            >
              {listError}
            </div>
          )}

          {!selected ? (
            <EmptyState hasWorkspaces={workspaces.length > 0} />
          ) : (
            <div className="space-y-10">
              <header>
                <h1
                  className="text-xl font-semibold tracking-tight text-gray-900 dark:text-slate-100"
                  data-testid="workspace-title"
                >
                  {selected.name}
                </h1>
                <p className="text-sm text-gray-500 dark:text-slate-400">
                  Upload a CSV, then ask questions in plain English. Your data never leaves this
                  machine.
                </p>
              </header>

              <DatasetPanel
                dataset={dataset}
                uploading={uploading}
                error={uploadError}
                onUpload={handleUpload}
              />

              {dataset ? (
                <AskPanel
                  canAsk={!!dataset}
                  loading={asking}
                  error={askError}
                  turns={turns}
                  onAsk={handleAsk}
                />
              ) : (
                <p
                  data-testid="no-dataset-hint"
                  className="rounded-xl border border-dashed border-gray-300 bg-white px-4 py-6 text-center text-sm text-gray-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500"
                >
                  Upload a CSV to start asking questions.
                </p>
              )}

              {/* Run history — real Phase 2 panel */}
              <RunHistoryPanel
                workspaceId={selected.id}
                refreshKey={historyRefresh}
                onOpenRun={openPastRun}
              />

              {/* Column notes & business rules — Phase 3 */}
              <Stub title="Notes &amp; business rules" phase="Phase 3">
                Attach column definitions and rules (e.g. &ldquo;exclude written-off loans&rdquo;)
                that inform every analysis.
              </Stub>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function EmptyState({ hasWorkspaces }: { hasWorkspaces: boolean }) {
  return (
    <div data-testid="main-empty-state" className="mt-24 flex flex-col items-center text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-2xl dark:bg-blue-950/50">
        📊
      </div>
      <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">
        {hasWorkspaces ? 'Select a workspace' : 'Create a workspace to begin'}
      </h2>
      <p className="mt-1 max-w-sm text-sm text-gray-500 dark:text-slate-400">
        {hasWorkspaces
          ? 'Choose a workspace from the left, or create a new one.'
          : 'A workspace holds one dataset and the questions you ask about it. Click “New workspace” to start.'}
      </p>
    </div>
  )
}
