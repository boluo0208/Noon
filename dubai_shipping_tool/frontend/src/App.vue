<template>
  <el-container style="min-height: 100vh">
    <el-aside width="200px" style="background: #304156">
      <div style="padding: 16px; color: #fff; font-size: 16px; font-weight: bold; text-align: center">
        迪拜仓发货工具
      </div>
      <el-menu
        :default-active="route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
      >
        <el-menu-item index="/dashboard">
          <span>控制台</span>
        </el-menu-item>
        <el-menu-item index="/orders">
          <span>订单数据</span>
        </el-menu-item>
        <el-menu-item index="/inventory">
          <span>库存数据</span>
        </el-menu-item>
        <el-menu-item index="/in-transit">
          <span>在途库存</span>
        </el-menu-item>
        <el-menu-item index="/priority">
          <span>优先处理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>
