<template>
  <div>
    <h2 style="margin-bottom: 20px">控制台</h2>

    <el-card v-if="taskStore.currentTask" style="margin-bottom: 20px">
      <template #header><span>任务状态</span></template>
      <el-tag :type="statusTagType" size="large">{{ statusLabel }}</el-tag>
      <span style="margin-left: 12px; color: #606266; white-space: pre-line">{{ taskStore.currentTask.message }}</span>
      <el-alert
        v-if="taskStore.currentTask.status === 'FAILED'"
        style="margin-top: 16px"
        title="任务失败"
        type="error"
        :closable="false"
        show-icon
      >
        <template #default>
          <pre style="white-space: pre-wrap; margin: 0; font-size: 13px; max-height: 260px; overflow: auto">{{ taskStore.currentTask.error_detail }}</pre>
        </template>
      </el-alert>
    </el-card>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header><span>订单文件</span></template>
          <el-table :data="orderItems" border empty-text="暂无订单来源">
            <el-table-column prop="name" label="名称" min-width="240" />
            <el-table-column prop="store_id" label="店铺号" width="90" />
            <el-table-column prop="count" label="条数" width="80" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.count > 0" type="success">已存在</el-tag>
                <el-tag v-else type="info">暂无</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="primary" @click="viewOrders(row)">查看</el-button>
                <el-button link type="success" :loading="taskStore.isPolling" @click="taskStore.triggerDownload(row.id)">更新</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header><span>库存与在途库存</span></template>
          <el-table :data="stockItems" border empty-text="暂无仓库">
            <el-table-column prop="name" label="名称" min-width="220" />
            <el-table-column prop="typeLabel" label="类型" width="100" />
            <el-table-column prop="count" label="条数" width="80" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.count > 0" type="success">已存在</el-tag>
                <el-tag v-else type="info">暂无</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="primary" @click="viewStock(row)">查看</el-button>
                <el-button
                  link
                  type="success"
                  :loading="taskStore.isPolling"
                  @click="row.type === 'inventory' ? taskStore.triggerSyncInventory(row.warehouse_id) : taskStore.triggerSyncInTransit(row.warehouse_id)"
                >
                  同步
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="86%">
      <el-table :data="dialogRows" border max-height="560">
        <el-table-column v-for="column in dialogColumns" :key="column" :prop="column" :label="column" min-width="140" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useTaskStore } from '@/stores/task'
import {
  getAccountsConfig,
  getInTransitPreview,
  getInventoryPreview,
  getOrdersPreview,
  type AccountsConfig,
} from '@/api/index'

const taskStore = useTaskStore()
const accountsConfig = ref<AccountsConfig | null>(null)
const orderItems = ref<any[]>([])
const stockItems = ref<any[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogRows = ref<any[]>([])

const dialogColumns = computed(() => {
  const first = dialogRows.value[0]
  return first ? Object.keys(first) : []
})

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    PENDING: '等待中',
    RUNNING: '运行中',
    WAITING_LOGIN: '等待登录',
    SUCCESS: '成功',
    FAILED: '失败',
  }
  return map[taskStore.currentTask?.status || 'PENDING'] || taskStore.currentTask?.status || ''
})

const statusTagType = computed(() => {
  const map: Record<string, string> = {
    PENDING: 'info',
    RUNNING: 'warning',
    WAITING_LOGIN: 'warning',
    SUCCESS: 'success',
    FAILED: 'danger',
  }
  return map[taskStore.currentTask?.status || 'PENDING'] || 'info'
})

async function refreshFileStatus() {
  const config = accountsConfig.value
  if (!config) return

  const orderResults = await Promise.all(
    config.noon_accounts.map(async (source) => {
      try {
        const { data } = await getOrdersPreview({ page: 1, page_size: 1, account_id: source.id })
        return { ...source, count: data.total }
      } catch {
        return { ...source, count: 0 }
      }
    }),
  )
  orderItems.value = orderResults

  const stockResults: any[] = []
  for (const warehouse of config.warehouses) {
    try {
      const { data } = await getInventoryPreview({ page: 1, page_size: 1, warehouse_id: warehouse.id })
      stockResults.push({
        id: `${warehouse.id}-inventory`,
        warehouse_id: warehouse.id,
        type: 'inventory',
        typeLabel: '库存',
        name: `${warehouse.name}-库存`,
        count: data.total,
      })
    } catch {
      stockResults.push({ id: `${warehouse.id}-inventory`, warehouse_id: warehouse.id, type: 'inventory', typeLabel: '库存', name: `${warehouse.name}-库存`, count: 0 })
    }

    try {
      const { data } = await getInTransitPreview({ page: 1, page_size: 1, warehouse_id: warehouse.id })
      stockResults.push({
        id: `${warehouse.id}-in-transit`,
        warehouse_id: warehouse.id,
        type: 'in-transit',
        typeLabel: '在途',
        name: `${warehouse.name}-在途库存`,
        count: data.total,
      })
    } catch {
      stockResults.push({ id: `${warehouse.id}-in-transit`, warehouse_id: warehouse.id, type: 'in-transit', typeLabel: '在途', name: `${warehouse.name}-在途库存`, count: 0 })
    }
  }
  stockItems.value = stockResults
}

async function viewOrders(row: any) {
  const { data } = await getOrdersPreview({ page: 1, page_size: 500, account_id: row.id })
  dialogTitle.value = row.name
  dialogRows.value = data.data.map((item) => ({ 店铺号: row.store_id, ...item }))
  dialogVisible.value = true
}

async function viewStock(row: any) {
  if (row.type === 'inventory') {
    const { data } = await getInventoryPreview({ page: 1, page_size: 500, warehouse_id: row.warehouse_id })
    dialogRows.value = data.data
  } else {
    const { data } = await getInTransitPreview({ page: 1, page_size: 500, warehouse_id: row.warehouse_id })
    dialogRows.value = data.data
  }
  dialogTitle.value = row.name
  dialogVisible.value = true
}

onMounted(async () => {
  const { data } = await getAccountsConfig()
  accountsConfig.value = data
  await refreshFileStatus()
})

watch(
  () => taskStore.currentTask?.status,
  (status) => {
    if (status === 'SUCCESS') refreshFileStatus()
  },
)
</script>
