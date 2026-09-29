<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">冷链物流温控管理平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向冷链运输的车辆调度、温控监测、冷库作业、签收回单、异常报警与冷链断链追溯的综合物流管理后台。</span>
        <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "发运单管理", path: "/shipment" }, { label: "温控监测", path: "/temp_monitor" }, { label: "车辆调度", path: "/vehicle" }, { label: "司机管理", path: "/driver" }, { label: "调度工作台", path: "/dispatch" }, { label: "冷库运营", path: "/cold_storage" }, { label: "装卸作业", path: "/loading" }, { label: "报警管理", path: "/alert" }, { label: "线路规划", path: "/route" }, { label: "制冷机组", path: "/reefer_unit" }, { label: "油料管理", path: "/fuel" }, { label: "签收回单", path: "/delivery" }, { label: "断链追溯", path: "/break_chain" }, { label: "月台管理", path: "/dock" }, { label: "包装管理", path: "/package" }, { label: "通行费用", path: "/toll" }, { label: "车辆消杀", path: "/sanitation" }, { label: "承运合同", path: "/contract" }, { label: "货运保险", path: "/insurance" }]
</script>
