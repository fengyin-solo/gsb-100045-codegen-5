<template>
  <section class="page" data-module="dispatch">
    <header class="page-head">
      <div>
        <h2>调度工作台</h2>
        <p class="page-desc">新增司机调度名单时，司机档案须先核验驾驶证、从业资格证与任务结清证明；资格状态按待审核到可调度逐级流转，审核结论回写到调度工作台、司机列表与详情。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate = !openCreate">加入调度名单</button>
        <button class="btn" type="button" @click="exportRows">导出调度名单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>

    <form v-if="openCreate" class="filter-bar dispatch-form" @submit.prevent="submitDispatch">
      <label class="filter-item">
        <span>调度司机</span>
        <select v-model="form.司机id" required>
          <option value="" disabled>选择司机</option>
          <option v-for="d in drivers" :key="String(d.id)" :value="d.id">
            {{ d.司机编号 }} · {{ d.姓名 }}（{{ d.资格状态 }} / v{{ d.资格版本 }} / {{ d.任务结清证明 }}）
          </option>
        </select>
      </label>
      <label class="filter-item">
        <span>线路编号</span>
        <input v-model="form.线路编号" placeholder="如 LINE-0001" />
      </label>
      <label class="filter-item">
        <span>车辆编号</span>
        <input v-model="form.车辆编号" placeholder="如 粤B12345" />
      </label>
      <label class="filter-item">
        <span>排班日期</span>
        <input v-model="form.排班日期" type="date" />
      </label>
      <label class="filter-item">
        <span>班次</span>
        <input v-model="form.班次" placeholder="早班 / 午班 / 晚班" />
      </label>
      <button class="btn primary" type="submit">提交调度</button>
      <button class="btn ghost" type="button" @click="openCreate = false">取消</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '资格状态'" :class="['badge', qualClass(row.资格状态)]">{{ row[column] ?? '—' }}</span>
            <span v-else-if="column === '任务状态'" :class="['badge', taskClass(row.任务状态)]">{{ row[column] ?? '—' }}</span>
            <span v-else>{{ row[column] ?? '—' }}</span>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无调度记录，可先加入调度名单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条调度记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-if="okMessage" class="ok-text">{{ okMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Driver = Record<string, string | number | null>

const ENDPOINT = '/api/dispatch'
const columns = ["调度编号", "司机编号", "司机姓名", "线路编号", "车辆编号", "排班日期", "班次", "资格版本", "资格状态", "审核结论", "任务状态", "结清状态"]
const actions = ["完成任务", "取消调度"]
const filterFields = ["调度编号", "司机编号", "司机姓名"]

const cards = ref<{ label: string; value: number }[]>([])
const drivers = ref<Driver[]>([])
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const okMessage = ref('')
const openCreate = ref(false)
const filters = ref<Record<string, string>>({})
const form = reactive<Record<string, string>>({
  司机id: '', 线路编号: '', 车辆编号: '', 排班日期: '', 班次: '',
})

function qualClass(value: unknown) {
  if (value === '可调度') return 'badge-ok'
  if (value === '停运') return 'badge-stop'
  return 'badge-pending'
}

function taskClass(value: unknown) {
  if (value === '已完成') return 'badge-ok'
  if (value === '已取消') return 'badge-stop'
  return 'badge-pending'
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function loadWorkbench() {
  try {
    const response = await request(`${ENDPOINT}/workbench`)
    if (!response.ok) throw new Error('调度工作台读取失败')
    const payload = await response.json()
    cards.value = payload.cards ?? []
    drivers.value = payload.drivers ?? []
  } catch {
    // 工作台卡片加载失败不阻塞列表
  }
}

async function submitDispatch() {
  errorMessage.value = ''
  okMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({
        values: {
          司机id: Number(form.司机id),
          线路编号: form.线路编号,
          车辆编号: form.车辆编号,
          排班日期: form.排班日期,
          班次: form.班次,
        },
      }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message || '调度未受理'
      return
    }
    okMessage.value = payload.message || '调度已受理'
    openCreate.value = false
    await Promise.all([reload(), loadWorkbench()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度提交失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  okMessage.value = ''
  const path = action === '完成任务' ? 'complete' : 'cancel'
  try {
    const response = await request(`${ENDPOINT}/${row.id}/${path}`, { method: 'POST' })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message || '调度动作未生效'
      return
    }
    okMessage.value = payload.message || '调度动作已生效'
    await Promise.all([reload(), loadWorkbench()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) throw new Error('调度名单读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度名单读取失败'
  }
}

onMounted(() => {
  void Promise.all([reload(), loadWorkbench()])
})
</script>

<style scoped>
.dispatch-form {
  align-items: flex-end;
  flex-wrap: wrap;
}
.dispatch-form .filter-item {
  min-width: 160px;
}
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
.badge-pending {
  background: #fff6e0;
  color: #a06a00;
}
.badge-stop {
  background: #fdeaea;
  color: #b3261e;
}
.ok-text {
  color: #1a7f4b;
}
</style>
