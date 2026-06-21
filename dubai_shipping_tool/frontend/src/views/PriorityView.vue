<template>
  <div>
    <h2 style="margin-bottom: 20px">优先处理</h2>

    <!-- 数据准备中 -->
    <el-card v-if="preparing" style="margin-bottom: 20px">
      <template #header>
        <span>数据准备中</span>
      </template>

      <el-steps :active="prepareStep" finish-status="success" process-status="process" align-center>
        <el-step title="检查数据" />
        <el-step title="下载订单" />
        <el-step title="同步库存" />
        <el-step title="在途库存" />
        <el-step title="计算分配" />
      </el-steps>

      <div style="margin-top: 16px; text-align: center">
        <el-tag :type="prepareTagType" size="large">{{ prepareMessage }}</el-tag>

        <div v-if="prepareStatus === 'WAITING_LOGIN'" style="margin-top: 12px">
          <el-alert
            title="需要手动登录 Noon"
            type="warning"
            description="Edge 浏览器已打开 Noon 登录页。请在浏览器中登录，登录完成后程序会自动继续。"
            show-icon
            :closable="false"
          />
        </div>

        <div v-if="prepareStatus === 'FAILED'" style="margin-top: 12px">
          <el-alert
            title="数据获取失败"
            type="error"
            :description="prepareError"
            show-icon
            :closable="false"
          />
          <el-button type="primary" style="margin-top: 12px" @click="startPrepare">重试</el-button>
        </div>

        <div v-if="prepareStatus === 'SUCCESS'" style="margin-top: 12px">
          <el-alert
            title="数据准备完成"
            type="success"
            show-icon
            :closable="false"
          />
        </div>
      </div>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="5">
        <el-card>
          <template #header><span>建议发货</span></template>
          <div style="font-size: 28px; font-weight: bold; color: #67C23A">{{ stats.selected }}</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card>
          <template #header><span>等待在途</span></template>
          <div style="font-size: 28px; font-weight: bold; color: #409EFF">{{ stats.waiting_transit }}</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card>
          <template #header><span>库存不足</span></template>
          <div style="font-size: 28px; font-weight: bold; color: #E6A23C">{{ stats.shortage }}</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card>
          <template #header><span>无库存</span></template>
          <div style="font-size: 28px; font-weight: bold; color: #F56C6C">{{ stats.no_stock }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card>
          <template #header><span>涉及 SKU</span></template>
          <div style="font-size: 28px; font-weight: bold; color: #409EFF">{{ stats.total_skus }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选栏 -->
    <el-card style="margin-bottom: 20px">
      <el-row :gutter="16" align="middle">
        <el-col :span="4">
          <el-select v-model="selectedWarehouseId" placeholder="仓库" @change="loadResults">
            <el-option
              v-for="warehouse in warehouses"
              :key="warehouse.id"
              :label="warehouse.name"
              :value="warehouse.id"
            />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索订单号或 SKU"
            clearable
            @keyup.enter="smartQuery"
          />
        </el-col>
        <el-col :span="4">
          <el-select v-model="statusFilter" placeholder="状态筛选" clearable @change="loadResults">
            <el-option label="建议发货" value="建议发货" />
            <el-option label="等待在途" value="等待在途" />
            <el-option label="库存不足" value="库存不足" />
            <el-option label="无库存" value="无库存" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="smartQuery" :loading="preparing">
            查询
          </el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 结果表格 -->
    <el-card>
      <template #header>
        <span>处理结果（共 {{ total }} 条）</span>
      </template>

      <el-table
        :data="results"
        border
        stripe
        v-loading="loading"
        empty-text="点击「查询」获取数据"
        style="width: 100%"
        :row-class-name="rowClassName"
      >
        <el-table-column prop="订单号" label="订单号" min-width="180" fixed />
        <el-table-column prop="SKU" label="SKU" min-width="150" />
        <el-table-column prop="库存" label="库存" width="80" />
        <el-table-column prop="出单数" label="出单数" width="80" />
        <el-table-column prop="在途库存" label="在途库存" width="100" />
        <el-table-column prop="现货+在途" label="现货+在途" width="110" />
        <el-table-column prop="缺口" label="缺口" width="80" />
        <el-table-column prop="最晚处理时间" label="最晚处理时间" min-width="180" sortable />
        <el-table-column prop="状态" label="状态" width="110" fixed="right">
          <template #default="{ row }">
            <el-tag
              :type="statusTagType(row['状态'])"
              size="default"
            >
              {{ row['状态'] }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  getPriorityResults,
  getAccountsConfig,
  getOrdersPreview,
  getInventoryPreview,
  startDownloadOrders,
  startSyncInventory,
  startSyncInTransit,
  getTask,
} from '@/api/index'

interface PriorityRow {
  订单号: string
  SKU: string
  库存: number
  出单数: number
  在途库存: number
  '现货+在途': number
  缺口: number
  最晚处理时间: string | null
  状态: string
}

const results = ref<PriorityRow[]>([])
const total = ref(0)
const loading = ref(false)
const searchKeyword = ref('')
const statusFilter = ref('')
const selectedWarehouseId = ref('')
const warehouses = ref<Array<{ id: string; name: string }>>([])

const stats = ref({ selected: 0, waiting_transit: 0, shortage: 0, no_stock: 0, total_skus: 0 })

// ---- 自动准备数据 ----
const preparing = ref(false)
const prepareStep = ref(0)
const prepareMessage = ref('')
const prepareStatus = ref('')      // PENDING | RUNNING | WAITING_LOGIN | SUCCESS | FAILED
const prepareError = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

const prepareTagType = computed(() => {
  const map: Record<string, string> = {
    PENDING: 'info',
    RUNNING: 'warning',
    WAITING_LOGIN: 'warning',
    SUCCESS: 'success',
    FAILED: 'danger',
  }
  return map[prepareStatus.value] || 'info'
})

function statusTagType(status: string) {
  const map: Record<string, string> = {
    '建议发货': 'success',
    '等待在途': 'primary',
    '库存不足': 'warning',
    '无库存': 'danger',
  }
  return map[status] || 'info'
}

function rowClassName({ row }: { row: PriorityRow }) {
  if (row['状态'] === '建议发货') return 'priority-row-selected'
  if (row['状态'] === '等待在途') return 'priority-row-waiting-transit'
  if (row['状态'] === '库存不足') return 'priority-row-shortage'
  return ''
}

async function loadResults() {
  loading.value = true
  try {
    const { data } = await getPriorityResults({
      keyword: searchKeyword.value,
      status: statusFilter.value,
      warehouse_id: selectedWarehouseId.value,
    })
    results.value = data.data as PriorityRow[]
    total.value = data.total
    stats.value = data.stats
  } catch {
    results.value = []
    total.value = 0
    stats.value = { selected: 0, waiting_transit: 0, shortage: 0, no_stock: 0, total_skus: 0 }
  } finally {
    loading.value = false
  }
}

/** 查询：有缓存直接展示，没数据自动下载 */
async function smartQuery() {
  try {
    const { data } = await getPriorityResults({
      keyword: searchKeyword.value,
      status: statusFilter.value,
      warehouse_id: selectedWarehouseId.value,
    })
    if (data.total > 0) {
      results.value = data.data as PriorityRow[]
      total.value = data.total
      stats.value = data.stats
      return
    }
  } catch { }

  await startPrepare()
}

/** 自动准备数据流程 */
async function startPrepare() {
  preparing.value = true
  prepareStep.value = 0
  prepareMessage.value = '正在检查数据...'
  prepareStatus.value = 'RUNNING'
  prepareError.value = ''

  // 1. 检查哪些数据缺失
  let ordersExist = false
  let inventoryExist = false
  try {
    const o = await getOrdersPreview({ page: 1, page_size: 1 })
    ordersExist = o.data.total > 0
  } catch { ordersExist = false }
  try {
    const i = await getInventoryPreview({ page: 1, page_size: 1 })
    inventoryExist = i.data.total > 0
  } catch { inventoryExist = false }

  // 2. 如果订单缺失，先下载
  if (!ordersExist) {
    prepareStep.value = 1
    prepareMessage.value = '正在启动 Noon 订单下载...'
    await runTask('download-orders', () => startDownloadOrders())
  }

  // 3. 如果库存缺失，同步
  if (!inventoryExist) {
    prepareStep.value = 2
    prepareMessage.value = '正在启动 ERP 库存同步...'
    await runTask('sync-inventory', () => startSyncInventory(selectedWarehouseId.value))
  }

  // 4. 同步在途库存（用同一 ERP 登录态）
  prepareStep.value = 3
  prepareMessage.value = '正在同步在途库存...'
  try {
    await runTask('sync-in-transit', () => startSyncInTransit(selectedWarehouseId.value))
  } catch {
    // 在途库存同步失败不阻塞主流程，继续展示结果
    console.warn('在途库存同步失败，跳过')
  }

  // 5. 加载结果
  prepareStep.value = 4
  prepareMessage.value = '正在计算分配结果...'
  await loadResults()
  prepareStatus.value = 'SUCCESS'
  prepareMessage.value = '数据准备完成'

  // 2 秒后收起准备面板
  setTimeout(() => {
    preparing.value = false
  }, 2000)
}

/** 运行一个后台任务并轮询直到完成 */
async function runTask(
  taskType: string,
  trigger: () => Promise<{ data: { task_id: string } }>,
): Promise<void> {
  try {
    const { data } = await trigger()
    const taskId = data.task_id

    return new Promise((resolve, reject) => {
      pollTimer = setInterval(async () => {
        try {
          const { data: taskData } = await getTask(taskId)
          prepareMessage.value = taskData.message
          prepareStatus.value = taskData.status

          if (taskData.status === 'WAITING_LOGIN') {
            // 登录等待中，不做额外操作，继续轮询
          }

          if (taskData.status === 'SUCCESS') {
            clearInterval(pollTimer!)
            pollTimer = null
            resolve()
          }

          if (taskData.status === 'FAILED') {
            clearInterval(pollTimer!)
            pollTimer = null
            prepareError.value = taskData.error_detail || '未知错误'
            reject(new Error(taskData.error_detail || '任务失败'))
          }
        } catch (err) {
          clearInterval(pollTimer!)
          pollTimer = null
          prepareError.value = '轮询任务状态失败'
          reject(err)
        }
      }, 2000)
    })
  } catch (err: any) {
    prepareError.value = err?.message || '启动任务失败'
    prepareStatus.value = 'FAILED'
    throw err
  }
}

function resetFilter() {
  searchKeyword.value = ''
  statusFilter.value = ''
  startPrepare()
}

onMounted(async () => {
  // 页面加载时尝试加载已有数据
  try {
    const accounts = await getAccountsConfig()
    warehouses.value = accounts.data.warehouses
    selectedWarehouseId.value = accounts.data.default_warehouse_id
    const { data } = await getPriorityResults({ keyword: '', status: '', warehouse_id: selectedWarehouseId.value })
    if (data.total > 0) {
      results.value = data.data as PriorityRow[]
      total.value = data.total
      stats.value = data.stats
    }
  } catch {
    // 没有数据，等用户点击查询
  }
})
</script>

<style scoped>
:deep(.priority-row-selected) {
  background-color: #f0f9eb !important;
}
:deep(.priority-row-shortage) {
  background-color: #fdf6ec !important;
}
:deep(.priority-row-waiting-transit) {
  background-color: #ecf5ff !important;
}
</style>
