import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TaskInfo, TaskStatus } from '@/types/task'
import { startDownloadOrders, startSyncInventory, startSyncInTransit, getTask, continueTask } from '@/api/index'

export const useTaskStore = defineStore('task', () => {
  const currentTask = ref<TaskInfo | null>(null)
  const isPolling = ref(false)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  function startPolling(taskId: string) {
    isPolling.value = true
    pollTimer = setInterval(async () => {
      try {
        const { data } = await getTask(taskId)
        currentTask.value = {
          ...data,
          status: data.status as TaskStatus,
        }
        if (['SUCCESS', 'FAILED'].includes(data.status)) {
          stopPolling()
        }
      } catch {
        stopPolling()
      }
    }, 2000)
  }

  function stopPolling() {
    isPolling.value = false
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function triggerDownload(accountId?: string) {
    const { data } = await startDownloadOrders(accountId)
    currentTask.value = {
      task_id: data.task_id,
      task_type: data.task_type,
      status: data.status as TaskStatus,
      message: data.message,
      started_at: null,
      finished_at: null,
      error_detail: null,
    }
    startPolling(data.task_id)
  }

  async function triggerSyncInventory(warehouseId?: string) {
    const { data } = await startSyncInventory(warehouseId)
    currentTask.value = {
      task_id: data.task_id,
      task_type: data.task_type,
      status: data.status as TaskStatus,
      message: data.message,
      started_at: null,
      finished_at: null,
      error_detail: null,
    }
    startPolling(data.task_id)
  }

  async function triggerSyncInTransit(warehouseId?: string) {
    const { data } = await startSyncInTransit(warehouseId)
    currentTask.value = {
      task_id: data.task_id,
      task_type: data.task_type,
      status: data.status as TaskStatus,
      message: data.message,
      started_at: null,
      finished_at: null,
      error_detail: null,
    }
    startPolling(data.task_id)
  }

  async function triggerContinue() {
    if (!currentTask.value) return
    await continueTask(currentTask.value.task_id)
  }

  return {
    currentTask,
    isPolling,
    triggerDownload,
    triggerSyncInventory,
    triggerSyncInTransit,
    triggerContinue,
    startPolling,
    stopPolling,
  }
})
