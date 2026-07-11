import { useState, type ReactNode } from 'react'
import { Maximize2, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export function MarkdownAnswerTable({
  header,
  rows,
  tableKey,
  renderCellContent,
}: {
  header: string[]
  rows: string[][]
  tableKey: string
  renderCellContent: (cell: string, keyPrefix: string) => ReactNode
}) {
  const [expanded, setExpanded] = useState(false)
  const columnCount = header.length
  const rowCount = rows.length
  const isWide = columnCount >= 6
  const isLarge = rowCount >= 8 || columnCount >= 8
  const tableClassName = cn('markdown-table', 'is-compact', isWide && 'is-wide', isLarge && 'is-large')

  const renderCell = (cell: string, keyPrefix: string) => (
    <span className={cn(isLongTokenTableCell(cell) && 'markdown-table-cell-long-token')}>
      {renderCellContent(cell, keyPrefix)}
    </span>
  )

  const renderTableElement = (keyScope: string) => (
    <table className={tableClassName}>
      <thead>
        <tr>{header.map((cell, index) => (
          <th className={cn(isNumericLikeTableCell(cell) && 'is-numeric')} key={`${keyScope}-h-${index}`}>
            {renderCell(cell, `${keyScope}-h-${index}`)}
          </th>
        ))}</tr>
      </thead>
      <tbody>{rows.map((row, rowIndex) => (
        <tr key={`${keyScope}-r-${rowIndex}`}>{header.map((_, cellIndex) => {
          const cell = row[cellIndex] || ''
          return (
            <td className={cn(isNumericLikeTableCell(cell) && 'is-numeric')} key={`${keyScope}-r-${rowIndex}-c-${cellIndex}`}>
              {renderCell(cell, `${keyScope}-r-${rowIndex}-c-${cellIndex}`)}
            </td>
          )
        })}</tr>
      ))}</tbody>
    </table>
  )

  return (
    <>
      <div className={cn('markdown-table-shell', isWide && 'is-wide', isLarge && 'is-large')}>
        <div className="markdown-table-toolbar">
          {isWide ? <span>横向滚动查看</span> : null}
          {isLarge ? (
            <button type="button" onClick={() => setExpanded(true)} aria-label="展开表格">
              <Maximize2 aria-hidden="true" size={14} />展开
            </button>
          ) : null}
        </div>
        <div className="markdown-table-wrap">{renderTableElement(tableKey)}</div>
      </div>
      {expanded ? (
        <div className="markdown-table-modal" role="dialog" aria-modal="true" aria-label="展开表格">
          <div className="markdown-table-modal-panel">
            <div className="markdown-table-modal-header">
              <strong>展开表格</strong>
              <button type="button" onClick={() => setExpanded(false)} aria-label="关闭展开表格"><X aria-hidden="true" size={16} /></button>
            </div>
            <div className="markdown-table-modal-body">{renderTableElement(`${tableKey}-expanded`)}</div>
          </div>
        </div>
      ) : null}
    </>
  )
}

function isNumericLikeTableCell(cell: string) {
  const normalized = cell.replace(/[\s,，%％/／·.-]/g, '')
  if (!normalized) return false
  const numericCharacters = normalized.match(/[0-9０-９.．×xX+\-－~～]/g)?.length || 0
  return numericCharacters / normalized.length >= 0.58
}

function isLongTokenTableCell(cell: string) {
  return /[A-Za-z0-9/_-]{16,}/.test(cell)
}
