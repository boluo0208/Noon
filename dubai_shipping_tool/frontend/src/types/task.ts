export type TaskStatus = 'PENDING' | 'RUNNING' | 'WAITING_LOGIN' | 'SUCCESS' | 'FAILED'

export interface TaskInfo {
  task_id: string
  task_type: string
  status: TaskStatus
  message: string
  started_at: number | null
  finished_at: number | null
  error_detail: string | null
}

export interface OrderRow {
  order_nr: string
  partner_sku: string
  target_shipped_at: string | null
}

export interface OrdersPreview {
  total: number
  page: number
  page_size: number
  data: OrderRow[]
}
