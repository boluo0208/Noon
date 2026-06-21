<template>
  <div>
    <h2 style="margin-bottom: 20px">订单数据</h2>

    <el-card style="margin-bottom: 20px">
      <el-row :gutter="16" align="middle">
        <el-col :span="5">
          <el-select v-model="selectedWarehouseId" placeholder="选择仓库" style="width: 100%" @change="handleQuery">
            <el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" />
          </el-select>
        </el-col>
        <el-col :span="7">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索订单号、SKU或店铺号"
            clearable
            @keyup.enter="handleQuery"
          />
        </el-col>
        <el-col :span="8">
          <el-button type="primary" :loading="loading || refreshing" @click="handleQuery">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button :loading="loading || refreshing" @click="openPreview">查看表单</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card style="margin-bottom: 20px">
      <template #header>
        <span>数据状态</span>
      </template>
      <el-table :data="sourceStatuses" border size="small" empty-text="暂无订单来源">
        <el-table-column prop="store_id" label="店铺号" width="100" />
        <el-table-column prop="name" label="订单来源" min-width="240" />
        <el-table-column prop="row_count" label="订单数" width="100" />
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="!row.exists" type="danger">暂无</el-tag>
            <el-tag v-else-if="row.is_stale" type="warning">超过1小时</el-tag>
            <el-tag v-else type="success">正常</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-alert
        v-if="freshness?.has_update_gap"
        style="margin-top: 12px"
        type="warning"
        show-icon
        :closable="false"
        title="同仓库不同店铺订单更新时间相差超过1小时，建议重新查询。"
      />
    </el-card>

    <el-card>
      <template #header>
        <span>订单列表（共 {{ total }} 条）</span>
      </template>

      <el-table
        :data="orders"
        border
        v-loading="loading || refreshing"
        empty-text="暂无订单数据，请先查询或更新订单"
        style="width: 100%"
        :row-class-name="rowClassName"
      >
        <el-table-column prop="store_id" label="店铺号" width="110" />
        <el-table-column prop="source_name" label="订单来源" min-width="220" />
        <el-table-column prop="order_nr" label="订单号" min-width="180">
          <template #default="{ row }">
            <span>{{ row.order_nr }}</span>
            <el-tag v-if="isDuplicateOrder(row.order_nr)" size="small" style="margin-left: 8px">同单</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="partner_sku" label="SKU" min-width="150" />
        <el-table-column prop="target_shipped_at" label="最晚发货时间" min-width="210">
          <template #default="{ row }">{{ row.target_shipped_at || '-' }}</template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadOrders"
          @current-change="loadOrders"
        />
      </div>
    </el-card>

    <el-dialog v-model="previewVisible" title="订单表单预览" width="86%">
      <el-table :data="previewRows" border max-height="560" :row-class-name="rowClassName">
        <el-table-column prop="store_id" label="店铺号" width="110" />
        <el-table-column prop="source_name" label="订单来源" min-width="220" />
        <el-table-column prop="order_nr" label="订单号" min-width="180">
          <template #default="{ row }">
            <span>{{ row.order_nr }}</span>
            <el-tag v-if="isDuplicateOrder(row.order_nr)" size="small" style="margin-left: 8px">同单</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="partner_sku" label="SKU" min-width="150" />
        <el-table-column prop="target_shipped_at" label="最晚发货时间" min-width="210" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAccountsConfig,
  getTask,
  getWarehouseOrders,
  startDownloadOrders,
  type AccountsConfig,
  type OrderWarehouseResponse,
} from '@/api/index'

const warehouses = ref<AccountsConfig['warehouses']>([])
const selectedWarehouseId = ref('')
const orders = ref<any[]>([])
const previewRows = ref<any[]>([])
const sourceStatuses = ref<OrderWarehouseResponse['sources']>([])
const freshness = ref<OrderWarehouseResponse['freshness'] | null>(null)
const total = ref(0)
const loading = ref(false)
const refreshing = ref(false)
const previewVisible = ref(false)
const currentPage = ref(1)
const pageSize = ref(50)
const searchKeyword = ref('')

const staleSourceIds = computed(() =>
  sourceStatuses.value
    .filter((source) => !source.exists || source.is_stale || freshness.value?.has_update_gap)
    .map((source) => source.id),
)

const duplicateOrderColorMap = computed(() => {
  const rows = [...orders.value, ...previewRows.value]
  const counts = new Map<string, number>()
  for (const row of rows) {
    const orderNo = String(row.order_nr || '')
    if (!orderNo) continue
    counts.set(orderNo, (counts.get(orderNo) || 0) + 1)
  }

  const colorMap = new Map<string, number>()
  let colorIndex = 0
  for (const [orderNo, count] of counts.entries()) {
    if (count > 1) {
      colorMap.set(orderNo, colorIndex % 5)
      colorIndex += 1
    }
  }
  return colorMap
})

function formatTime(value: number | null) {
  if (!value) return '-'
  return new Date(value * 1000).toLocaleString()
}

function isDuplicateOrder(orderNo: string) {
  return duplicateOrderColorMap.value.has(String(orderNo || ''))
}

function rowClassName({ row }: { row: any }) {
  const classes = []
  if (row.store_id === '442609') classes.push('store-two-row')
  const duplicateColor = duplicateOrderColorMap.value.get(String(row.order_nr || ''))
  if (duplicateColor !== undefined) classes.push(`duplicate-order-${duplicateColor}`)
  return classes.join(' ')
}

async function loadOrders(checkFreshness = false) {
  loading.value = true
  try {
    const { data } = await getWarehouseOrders({
      page: currentPage.value,
      page_size: pageSize.value,
      keyword: searchKeyword.value,
      warehouse_id: selectedWarehouseId.value,
    })
    orders.value = data.data
    total.value = data.total
    sourceStatuses.value = data.sources
    freshness.value = data.freshness

    if (checkFreshness && data.freshness.needs_refresh) {
      await confirmAndRefresh()
    }
  } finally {
    loading.value = false
  }
}

async function waitTask(taskId: string) {
  while (true) {
    await new Promise((resolve) => window.setTimeout(resolve, 2000))
    const { data } = await getTask(taskId)
    if (data.status === 'SUCCESS') return
    if (data.status === 'FAILED') throw new Error(data.error_detail || data.message || '任务失败')
  }
}

async function refreshStaleSources() {
  if (!staleSourceIds.value.length) return
  refreshing.value = true
  try {
    for (const sourceId of staleSourceIds.value) {
      const { data } = await startDownloadOrders(sourceId)
      await waitTask(data.task_id)
    }
    ElMessage.success('订单数据已更新')
    await loadOrders(false)
  } finally {
    refreshing.value = false
  }
}

async function confirmAndRefresh() {
  try {
    await ElMessageBox.confirm(
      '当前仓库的订单数据缺失、超过1小时，或店铺之间更新时间相差超过1小时。是否重新查询相关店铺订单？',
      '订单数据需要更新',
      { confirmButtonText: '重新查询', cancelButtonText: '先查看现有数据', type: 'warning' },
    )
    await refreshStaleSources()
  } catch {
    // User chose to view existing data.
  }
}

async function handleQuery() {
  currentPage.value = 1
  await loadOrders(true)
}

async function openPreview() {
  await loadOrders(true)
  const { data } = await getWarehouseOrders({
    page: 1,
    page_size: 500,
    keyword: searchKeyword.value,
    warehouse_id: selectedWarehouseId.value,
  })
  previewRows.value = data.data
  previewVisible.value = true
}

function resetSearch() {
  searchKeyword.value = ''
  currentPage.value = 1
  loadOrders(false)
}

onMounted(async () => {
  const { data } = await getAccountsConfig()
  warehouses.value = data.warehouses
  selectedWarehouseId.value = data.default_warehouse_id
  await loadOrders(false)
})
</script>

<style scoped>
:deep(.store-two-row) {
  background: #f7f7f7;
}
:deep(.duplicate-order-0) {
  --duplicate-color: #409eff;
  background: #ecf5ff !important;
}
:deep(.duplicate-order-1) {
  --duplicate-color: #67c23a;
  background: #f0f9eb !important;
}
:deep(.duplicate-order-2) {
  --duplicate-color: #e6a23c;
  background: #fdf6ec !important;
}
:deep(.duplicate-order-3) {
  --duplicate-color: #a855f7;
  background: #f5f3ff !important;
}
:deep(.duplicate-order-4) {
  --duplicate-color: #14b8a6;
  background: #ecfdf5 !important;
}
:deep(.duplicate-order-0 td:first-child),
:deep(.duplicate-order-1 td:first-child),
:deep(.duplicate-order-2 td:first-child),
:deep(.duplicate-order-3 td:first-child),
:deep(.duplicate-order-4 td:first-child) {
  border-left: 5px solid var(--duplicate-color) !important;
}
</style>
