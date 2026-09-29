<template>
  <section class="page" data-module="driver">
    <header class="page-head">
      <div>
        <h2>司机管理</h2>
        <p class="page-desc">维护驾驶人员资格档案：新增司机先建立待审核档案，核验驾驶证、从业资格证与任务结清证明后逐级流转到可调度；停运后再次变更须重新审核，审核结论回写调度工作台、司机列表与详情。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate = !openCreate">登记驾驶人员</button>
        <button class="btn" type="button" @click="exportRows">导出司机清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="openCreate" class="filter-bar dispatch-form" @submit.prevent="submitCreate">
      <label class="filter-item">
        <span>司机编号</span>
        <input v-model="form.司机编号" placeholder="如 DRIV-0005" required />
      </label>
      <label class="filter-item">
        <span>姓名</span>
        <input v-model="form.姓名" placeholder="司机姓名" required />
      </label>
      <label class="filter-item">
        <span>驾驶证号</span>
        <input v-model="form.驾驶证号" placeholder="驾驶证号" required />
      </label>
      <label class="filter-item">
        <span>从业资格证</span>
        <input v-model="form.从业资格证" placeholder="从业资格证号" />
      </label>
      <label class="filter-item">
        <span>联系手机</span>
        <input v-model="form.联系手机" placeholder="联系手机" />
      </label>
      <label class="filter-item">
        <span>所属车队</span>
        <input v-model="form.所属车队" placeholder="如 冷链一队" />
      </label>
      <button class="btn primary" type="submit">提交登记</button>
      <button class="btn ghost" type="button" @click="openCreate = false">取消</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>资格状态</span>
        <select v-model="filters.资格状态">
          <option value="">全部</option>
          <option v-for="q in qualificationStatuses" :key="q" :value="q">{{ q }}</option>
        </select>
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
            <span v-if="column === '资格状态'" :class="['badge', qualClass(row[column])]">{{ row[column] ?? '—' }}</span>
            <span v-else-if="column === '任务结清证明'" :class="['badge', row[column] === '已结清' ? 'badge-ok' : 'badge-pending']">{{ row[column] ?? '—' }}</span>
            <span v-else>{{ row[column] ?? '—' }}</span>
          </td>
          <td class="row-actions">
            <RouterLink class="link" :to="`/driver/${row.id}`">详情</RouterLink>
            <button
              v-if="row.资格状态 === '待审核'"
              class="link"
              type="button"
              @click="runAction('review', row)"
            >提交审核</button>
            <button
              v-if="row.资格状态 === '可调度'"
              class="link"
              type="button"
              @click="runAction('suspend', row)"
            >办理停运</button>
            <button
              v-if="row.资格状态 === '停运'"
              class="link"
              type="button"
              @click="runAction('reinstate', row)"
            >恢复调度</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无司机数据，可先登记驾驶人员</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条司机记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-if="okMessage" class="ok-text">{{ okMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/driver'
const columns = ["司机编号", "姓名", "驾驶证号", "从业资格证", "所属车队", "资格状态", "资格版本", "驾驶证核验", "从业资格证核验", "任务结清证明", "审核结论"]
const qualificationStatuses = ["待审核", "可调度", "停运"]
const filterFields = ["司机编号", "姓名"]

const stats = ref<{ label: string; value: number }[]>([])
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const okMessage = ref('')
const openCreate = ref(false)
const filters = ref<Record<string, string>>({})
const form = reactive<Record<string, string>>({
  司机编号: '', 姓名: '', 驾驶证号: '', 从业资格证: '', 联系手机: '', 所属车队: '',
})

function qualClass(value: unknown) {
  if (value === '可调度') return 'badge-ok'
  if (value === '停运') return 'badge-stop'
  return 'badge-pending'
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function submitCreate() {
  errorMessage.value = ''
  okMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...form } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message || '登记失败'
      return
    }
    okMessage.value = payload.message || '驾驶人员已登记'
    openCreate.value = false
    Object.keys(form).forEach((key) => { form[key] = '' })
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  okMessage.value = ''
  try {
    let response: Response
    if (action === 'review') {
      response = await request(`${ENDPOINT}/${row.id}/review`, { method: 'POST' })
    } else if (action === 'suspend') {
      const reason = window.prompt('请填写停运原因', '') || ''
      response = await request(`${ENDPOINT}/${row.id}/suspend`, {
        method: 'POST',
        body: JSON.stringify({ values: { reason } }),
      })
    } else {
      response = await request(`${ENDPOINT}/${row.id}/reinstate`, { method: 'POST' })
    }
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message || '动作未生效'
      return
    }
    okMessage.value = payload.message || '动作已生效'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) throw new Error('司机列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const ready = rows.value.filter((r) => r.资格状态 === '可调度').length
    const pending = rows.value.filter((r) => r.资格状态 === '待审核').length
    const suspended = rows.value.filter((r) => r.资格状态 === '停运').length
    stats.value = [
      { label: '可调度司机', value: ready },
      { label: '待审核司机', value: pending },
      { label: '停运司机', value: suspended },
    ]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '司机列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.dispatch-form {
  align-items: flex-end;
  flex-wrap: wrap;
}
.dispatch-form .filter-item {
  min-width: 150px;
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
