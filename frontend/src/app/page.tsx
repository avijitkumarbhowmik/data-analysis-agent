'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  ask as apiAsk,
  createWorkspace,
  getWorkspace,
  listWorkspaces,
  uploadDataset,
  type AskResult,
  type DatasetSummary,
  type WorkspaceListItem,
} from '@/lib/api'
import { Sidebar } from './components/Sidebar'
import { DatasetPanel } from './components/DatasetPanel'
import { AskPanel } from './components/AskPanel'
import { Stub } from './components/Stub'

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
  const [answer, setAnswer] = useState<AskResult | null>(null)

  const refreshWorkspaces = useCallback(async () => {
    setLoadingWorkspaces(true)
    setListError(null)
    try {
      const list = await listWorkspaces()
      setWorkspaces(list)
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
    setAnswer(null)
    try {
      const detail = await getWorkspace(id)
      // Phase 1: at most one dataset per workspace.
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
    setAnswer(null)
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

  async function handleAsk(question: string) {
    if (!selectedId) return
    setAsking(true)
    setAskError(null)
    setAnswer(null)
    try {
      const result = await apiAsk(selectedId, question, dataset?.id ?? null)
      setAnswer(result)
    } catch (err) {
      if (err instanceof ApiError) {
        setAskError(err.message)
      } else {
        setAskError(err instanceof Error ? err.message : 'The question could not be answered.')
      }
    } finally {
      setAsking(false)
    }
  }

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

      <main className="flex-1 overflow-y-auto bg-gray-50">
        <div className="mx-auto max-w-3xl px-6 py-8">
          {listError && (
            <div
              data-testid="list-error"
              className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {listError}
            </div>
          )}

          {!selected ? (
            <EmptyState hasWorkspaces={workspaces.length > 0} />
          ) : (
            <div className="space-y-8">
              <header>
                <h1 className="text-xl font-semibold tracking-tight text-gray-900" data-testid="workspace-title">
                  {selected.name}
                </h1>
                <p className="text-sm text-gray-500">
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
                  result={answer}
                  onAsk={handleAsk}
                />
              ) : (
                <p
                  data-testid="no-dataset-hint"
                  className="rounded-xl border border-dashed border-gray-300 bg-white px-4 py-6 text-center text-sm text-gray-400"
                >
                  Upload a CSV to start asking questions.
                </p>
              )}

              {/* Run history — Phase 2 */}
              <Stub title="Run history" phase="Phase 2">
                Past questions, their code, and results will be revisitable here.
              </Stub>

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
    <div
      data-testid="main-empty-state"
      className="mt-24 flex flex-col items-center text-center"
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-2xl">
        📊
      </div>
      <h2 className="text-lg font-semibold text-gray-900">
        {hasWorkspaces ? 'Select a workspace' : 'Create a workspace to begin'}
      </h2>
      <p className="mt-1 max-w-sm text-sm text-gray-500">
        {hasWorkspaces
          ? 'Choose a workspace from the left, or create a new one.'
          : 'A workspace holds one dataset and the questions you ask about it. Click “New workspace” to start.'}
      </p>
    </div>
  )
}
