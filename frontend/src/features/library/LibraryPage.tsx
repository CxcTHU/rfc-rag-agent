import { useEffect, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { EmptyState, LoadingState, RetryState } from '@/components/states'
import { useAuth } from '@/features/auth/AuthContext'
import { listDocuments } from '@/features/library/api'
import { documentKeys } from '@/features/library/queryKeys'
import { isAuthApiError } from '@/lib/api/client'
import { cn } from '@/lib/utils'

export function LibraryPage() {
  const { token, user, expireSession } = useAuth()
  const [filter, setFilter] = useState('')
  const documentsQuery = useQuery({
    queryKey: documentKeys.list(user?.id || 0),
    queryFn: ({ signal }) => listDocuments(token as string, signal),
    enabled: Boolean(token && user),
    staleTime: 60_000,
  })

  useEffect(() => {
    if (documentsQuery.error && isAuthApiError(documentsQuery.error)) expireSession()
  }, [documentsQuery.error, expireSession])

  const documents = documentsQuery.data || []
  const normalizedFilter = filter.trim().toLowerCase()
  const filteredDocuments = normalizedFilter
    ? documents.filter((document) =>
        [document.title, document.file_name, document.status, document.source_type]
          .some((value) => (value || '').toLowerCase().includes(normalizedFilter)),
      )
    : documents
  const chunkTotal = documents.reduce((total, document) => total + Number(document.chunk_count || 0), 0)
  const imported = documents.filter((document) => document.status === 'imported').length
  const localFiles = documents.filter((document) => document.source_type === 'local_file').length

  return (
    <Panel className="corpus-panel">
      <PanelHeader className="table-toolbar">
        <div><h2>语料库</h2><p>浏览已入库论文和文档，支持直接打开原文。</p></div>
        <Input aria-label="筛选语料库" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="请输入" />
      </PanelHeader>
      {documentsQuery.isPending ? <LoadingState label="正在加载语料库..." /> : null}
      {documentsQuery.error ? (
        <RetryState title="语料库加载失败" error={documentsQuery.error} onRetry={() => void documentsQuery.refetch()} />
      ) : null}
      {documentsQuery.isSuccess ? (
        <>
          <div className="metrics-row">
            <Metric label="文档数" value={documents.length} />
            <Metric label="已导入" value={imported} />
            <Metric label="本地原文" value={localFiles} />
            <Metric label="Chunk 数" value={chunkTotal} />
          </div>
          {!documents.length ? (
            <EmptyState title="语料库为空" description="接口请求成功，但当前用户还没有可用文档。" />
          ) : null}
          {documents.length && !filteredDocuments.length ? (
            <EmptyState title="没有匹配的文档" description="请调整标题、文件名、状态或来源类型筛选词。" />
          ) : null}
          {filteredDocuments.length ? (
            <>
              <div className="section-title"><h3>论文文档</h3><span>{filteredDocuments.length} / {documents.length} 个文档</span></div>
              <DataTable
                className="corpus-table-wrap"
                columns={['标题', '文件 / 来源', '状态', 'Chunk 数', '操作']}
                rows={filteredDocuments.map((document) => [
                  document.open_url ? <a key="title" className="table-link" href={document.open_url} target="_blank" rel="noreferrer">{document.title}</a> : document.title,
                  document.file_name || document.source_type || '-',
                  document.status || '-',
                  String(document.chunk_count ?? '-'),
                  document.open_url
                    ? <a key="open" className="table-action-link" href={document.open_url} target="_blank" rel="noreferrer" aria-label={`打开原文：${document.title}`}><ExternalLink size={14} /><span>打开原文</span></a>
                    : <span key="missing" className="muted-text">无原文</span>,
                ])}
              />
            </>
          ) : null}
        </>
      ) : null}
    </Panel>
  )
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong></article>
}

function DataTable({ className, columns, rows }: { className?: string; columns: string[]; rows: ReactNode[][] }) {
  return (
    <div className={cn('data-table-wrap', className)}>
      <table className="data-table">
        <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={`row-${index}`}>{row.map((cell, cellIndex) => <td key={`cell-${index}-${cellIndex}`}>{cell}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}
