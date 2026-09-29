<template>
  <section class="page" data-module="suspension">
    <header class="page-head">
      <div>
        <h2>停运记录</h2>
        <p class="page-desc">司机停运记录与档案保持同一资格版本；停运后再次变更须重新审核，审核结论回写调度工作台、司机列表与详情。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出停运记录</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="filters.状态">
          <option value="">全部</option>
          <option value="停运中">停运中</option>
          <option value="已恢复">已恢复</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '状态'" :class="['badge', row[column] === '停运中' ? 'badge-stop' : 'badge-ok']">{{ row[column] ?? '—' }}</span>
            <span v-else>{{ row[column] ?? '—' }}</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="empty-state">暂无停运记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条停运记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/suspension'
const columns = ["停运编号", "司机编号", "司机姓名", "停运原因", "停运时间", "资格版本", "状态", "恢复时间"]
const filterFields = ["停运编号", "司机编号", "司机姓名"]

const stats = ref<{ label: string; value: number }[]>([])
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) throw new Error('停运记录读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const active = rows.value.filter((r) => r.状态 === '停运中').length
    const recovered = rows.value.filter((r) => r.状态 === '已恢复').length
    stats.value = [
      { label: '停运中', value: active },
      { label: '已恢复', value: recovered },
    ]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '停运记录读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.6;
}
.badge-ok {
  background: #e6f7ee;
  color: #1a7f4b;
}
.badge-stop {
  background: #fdeaea;
  color: #b3261e;
}
.error-text {
  color: #b3261e;
}
.empty-state {
  text-align: center;
  color: #9ca3af;
  padding: 24px;
}
</style>
