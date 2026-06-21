<template>
  <div>
    <h2 style="margin-bottom: 20px">在途库存数据</h2>

    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="8">
        <el-card>
          <template #header><span>SKU数量</span></template>
          <div class="metric">{{ total }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header><span>当前页在途件数</span></template>
          <div class="metric warning">{{ totalQuantity }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header><span>仓库</span></template>
          <el-select v-model="selectedWarehouseId" style="width: 100%" @change="searchInTransit">
            <el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" />
          </el-select>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-bottom: 20px">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-input v-model="searchKeyword" placeholder="搜索 SKU" clearable @keyup.enter="searchInTransit" />
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="searchInTransit">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card>
      <template #header><span>在途库存列表（共 {{ total }} 条）</span></template>
      <el-table :data="inTransit" border stripe v-loading="loading" empty-text="暂无在途库存数据，请先同步">
        <el-table-column prop="SKU" label="SKU" min-width="250" />
        <el-table-column prop="在途库存" label="在途库存" min-width="150" sortable />
      </el-table>

      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadInTransit"
          @current-change="loadInTransit"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getAccountsConfig, getInTransitPreview, type AccountsConfig } from '@/api/index'

interface InTransitRow {
  SKU: string
  在途库存: number
}

const warehouses = ref<AccountsConfig['warehouses']>([])
const selectedWarehouseId = ref('')
const inTransit = ref<InTransitRow[]>([])
const total = ref(0)
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(50)
const searchKeyword = ref('')

const totalQuantity = computed(() => inTransit.value.reduce((sum, row) => sum + row.在途库存, 0))

async function loadInTransit() {
  loading.value = true
  try {
    const { data } = await getInTransitPreview({
      page: currentPage.value,
      page_size: pageSize.value,
      keyword: searchKeyword.value,
      warehouse_id: selectedWarehouseId.value,
    })
    inTransit.value = data.data
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function searchInTransit() {
  currentPage.value = 1
  loadInTransit()
}

function resetSearch() {
  searchKeyword.value = ''
  currentPage.value = 1
  loadInTransit()
}

onMounted(async () => {
  const { data } = await getAccountsConfig()
  warehouses.value = data.warehouses
  selectedWarehouseId.value = data.default_warehouse_id
  await loadInTransit()
})
</script>

<style scoped>
.metric {
  font-size: 28px;
  font-weight: 700;
  color: #409eff;
}
.metric.warning {
  color: #e6a23c;
}
</style>
