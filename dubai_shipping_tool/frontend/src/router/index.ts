import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
  },
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('@/views/OrdersView.vue'),
  },
  {
    path: '/inventory',
    name: 'Inventory',
    component: () => import('@/views/InventoryView.vue'),
  },
  {
    path: '/priority',
    name: 'Priority',
    component: () => import('@/views/PriorityView.vue'),
  },
  {
    path: '/in-transit',
    name: 'InTransit',
    component: () => import('@/views/InTransitView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
