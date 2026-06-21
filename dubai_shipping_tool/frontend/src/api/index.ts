import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export interface WarehouseConfig {
  id: string
  name: string
  market: string
  erp_account_id: string
  erp_warehouse_name: string
}

export interface NoonSource {
  id: string
  name: string
  market: string
  warehouse_id: string
  noon_account_id: string
  store_id: string
  project_id: string
  email: string
  noon_warehouse_name: string
  noon_warehouse_code: string
  has_pending_url: boolean
}

export interface AccountsConfig {
  default_noon_account_id: string
  default_warehouse_id: string
  warehouses: WarehouseConfig[]
  noon_login_accounts: Array<{ id: string; name: string; email: string; has_email: boolean }>
  noon_accounts: NoonSource[]
  erp_accounts: Array<{ id: string; name: string; username: string; has_password: boolean }>
}

export interface OrderWarehouseResponse {
  warehouse: WarehouseConfig
  sources: Array<{
    id: string
    name: string
    store_id: string
    project_id: string
    warehouse_id: string
    exists: boolean
    updated_at: number | null
    age_seconds: number | null
    is_stale: boolean
    size: number
    row_count: number
    error?: string
  }>
  freshness: {
    fresh_seconds: number
    has_missing: boolean
    has_stale: boolean
    max_update_gap_seconds: number
    has_update_gap: boolean
    needs_refresh: boolean
  }
  total: number
  page: number
  page_size: number
  data: any[]
}

export function getAccountsConfig() {
  return api.get<AccountsConfig>('/accounts')
}

export function startDownloadOrders(accountId?: string) {
  return api.post<{ task_id: string; task_type: string; status: string; message: string }>('/tasks/download-orders', {
    account_id: accountId || null,
  })
}

export function getTask(taskId: string) {
  return api.get<{
    task_id: string
    task_type: string
    status: string
    message: string
    started_at: number | null
    finished_at: number | null
    error_detail: string | null
  }>(`/tasks/${taskId}`)
}

export function continueTask(taskId: string) {
  return api.post<{ status: string; message: string }>(`/tasks/${taskId}/continue`)
}

export function getOrdersPreview(params: { page?: number; page_size?: number; keyword?: string; account_id?: string } = {}) {
  return api.get<{ total: number; page: number; page_size: number; data: any[] }>('/data/orders/preview', { params })
}

export function getWarehouseOrders(params: { page?: number; page_size?: number; keyword?: string; warehouse_id?: string } = {}) {
  return api.get<OrderWarehouseResponse>('/data/orders/warehouse', { params })
}

export function getOrdersFileUrl(accountId?: string) {
  return accountId ? `/api/files/orders/latest?account_id=${encodeURIComponent(accountId)}` : '/api/files/orders/latest'
}

export function startSyncInventory(warehouseId?: string) {
  return api.post<{ task_id: string; task_type: string; status: string; message: string }>('/tasks/sync-inventory', {
    warehouse_id: warehouseId || null,
  })
}

export function getInventoryPreview(params: { page?: number; page_size?: number; keyword?: string; warehouse_id?: string } = {}) {
  return api.get<{ total: number; page: number; page_size: number; data: { SKU: string; 当前库存: number }[] }>('/data/inventory/preview', { params })
}

export function getInventoryFileUrl(warehouseId?: string) {
  return warehouseId ? `/api/files/inventory/latest?warehouse_id=${encodeURIComponent(warehouseId)}` : '/api/files/inventory/latest'
}

export function startSyncInTransit(warehouseId?: string) {
  return api.post<{ task_id: string; task_type: string; status: string; message: string }>('/tasks/sync-in-transit', {
    warehouse_id: warehouseId || null,
  })
}

export function getInTransitPreview(params: { page?: number; page_size?: number; keyword?: string; warehouse_id?: string } = {}) {
  return api.get<{ total: number; page: number; page_size: number; data: { SKU: string; 在途库存: number }[] }>('/data/in-transit/preview', { params })
}

export function getInTransitFileUrl(warehouseId?: string) {
  return warehouseId ? `/api/files/in-transit/latest?warehouse_id=${encodeURIComponent(warehouseId)}` : '/api/files/in-transit/latest'
}

export function getPriorityResults(params: { keyword?: string; status?: string; warehouse_id?: string } = {}) {
  return api.get<{
    total: number
    data: Record<string, any>[]
    stats: { selected: number; waiting_transit: number; shortage: number; no_stock: number; total_skus: number }
  }>('/results/priority', { params })
}
