<template>
  <section class="page" data-module="driver">
    <header class="page-head">
      <div>
        <h2>司机资格管理</h2>
        <p class="page-desc">
          入档先核验驾驶证、从业资格证、任务结清证明；资格按
          待审核 → 审核中 → 可调度 → 停运 逐级流转，停运后再次变更需重新审核并生成新版本。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记驾驶人员</button>
        <button class="btn" type="button" @click="exportRows">导出司机清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value" :class="item.cls">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="keyword" placeholder="按司机编号或姓名检索" />
      </label>
      <label class="filter-item">
        <span>资格状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option v-for="s in qualStatuses" :key="s" :value="s">{{ s }}</option>
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
            <router-link v-if="column === '司机编号'" class="link" :to="`/driver/${row.id}`">
              {{ row[column] ?? '—' }}
            </router-link>
            <span v-else-if="column === '资格状态'" :class="['status-tag', statusClass(row[column])]">
              {{ row[column] ?? '—' }}
            </span>
            <span v-else>{{ row[column] ?? '—' }}</span>
          </td>
          <td class="row-actions">
            <template v-for="action in actionsFor(row)" :key="action.name">
              <button
                v-if="action.name === '资料核验'"
                class="link"
                type="button"
                @click="openVerify(row)"
              >资料核验</button>
              <button v-else class="link" type="button" @click="runAction(action.name, row)">
                {{ action.name }}
              </button>
            </template>
            <router-link class="link" :to="`/driver/${row.id}`">详情</router-link>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的司机，可先登记驾驶人员</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条司机档案</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记弹窗 -->
    <div v-if="createOpen" class="modal-mask" @click.self="createOpen = false">
      <div class="modal">
        <h3>登记驾驶人员</h3>
        <p class="modal-tip">登记后资格为「待审核 v1」，须核验三项材料后逐级流转。</p>
        <label v-for="f in createFields" :key="f" class="form-item">
          <span>{{ f }}<i v-if="requiredFields.includes(f)">*</i></span>
          <input v-model="createForm[f]" :placeholder="`请输入${f}`" />
        </label>
        <div class="modal-foot">
          <button class="btn" type="button" @click="createOpen = false">取消</button>
          <button class="btn primary" type="button" @click="submitCreate">提交登记</button>
        </div>
      </div>
    </div>

    <!-- 材料核验弹窗 -->
    <div v-if="verifyOpen" class="modal-mask" @click.self="verifyOpen = false">
      <div class="modal">
        <h3>核验入档材料 · {{ verifyTarget?.姓名 }}</h3>
        <p class="modal-tip">驾驶证、从业资格证、任务结清证明三项全部核验通过后进入审核中。</p>
        <label v-for="item in checkItems" :key="item" class="check-item">
          <input v-model="checks[item]" type="checkbox" />
          <span>{{ item }}核验通过</span>
        </label>
        <div v-if="verifyNote" class="modal-tip error-text">{{ verifyNote }}</div>
        <div class="modal-foot">
          <button class="btn" type="button" @click="verifyOpen = false">取消</button>
          <button class="btn primary" type="button" @click="submitVerify">提交核验</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null | Record<string, boolean>>

const ENDPOINT = '/api/driver'
const columns = [
  '司机编号', '姓名', '驾驶证号', '从业资格证', '所属车队',
  '资格版本', '资格状态', '审核结论', '任务结清',
]
const qualStatuses = ['待审核', '审核中', '可调度', '停运']
const checkItems = ['驾驶证', '从业资格证', '任务结清证明']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

const stats = ref([
  { label: '待审核', value: 0, cls: 's-pending' },
  { label: '审核中', value: 0, cls: 's-reviewing' },
  { label: '可调度', value: 0, cls: 's-ok' },
  { label: '停运', value: 0, cls: 's-stop' },
])

// 登记弹窗
const createFields = ['司机编号', '姓名', '驾驶证号', '从业资格证', '健康证有效期', '联系手机', '所属车队']
const requiredFields = ['司机编号', '姓名', '驾驶证号']
const createOpen = ref(false)
const createForm = reactive<Record<string, string>>({})

// 材料核验弹窗
const verifyOpen = ref(false)
const verifyTarget = ref<Row | null>(null)
const checks = reactive<Record<string, boolean>>({})
const verifyNote = ref('')

function statusClass(status: unknown): string {
  return {
    待审核: 's-pending',
    审核中: 's-reviewing',
    可调度: 's-ok',
    停运: 's-stop',
  }[String(status)] ?? ''
}

// 按当前资格状态给出允许的动作，顺序错误的动作不展示（后端仍会强校验）
function actionsFor(row: Row): { name: string }[] {
  switch (row['资格状态']) {
    case '待审核':
      return [{ name: '资料核验' }]
    case '审核中':
      return [{ name: '审核通过' }, { name: '审核驳回' }]
    case '可调度':
      return [{ name: '办理停运' }]
    case '停运':
      return [{ name: '重新审核' }]
    default:
      return []
  }
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createFields.forEach((f) => (createForm[f] = ''))
  createOpen.value = true
  errorMessage.value = ''
}

async function submitCreate() {
  errorMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const payload = await response.json()
    if (!payload.ok) throw new Error(payload.message)
    createOpen.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登记失败'
  }
}

function openVerify(row: Row) {
  verifyTarget.value = row
  verifyNote.value = ''
  const saved = (row['材料核验'] ?? {}) as Record<string, boolean>
  checkItems.forEach((item) => (checks[item] = Boolean(saved[item])))
  verifyOpen.value = true
}

async function submitVerify() {
  if (!verifyTarget.value) return
  verifyNote.value = ''
  try {
    const response = await request(`${ENDPOINT}/${verifyTarget.value.id}/verify`, {
      method: 'POST',
      body: JSON.stringify({ values: { checks: { ...checks } } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      verifyNote.value = payload.message
      await reload()
      return
    }
    verifyOpen.value = false
    await reload()
  } catch (error) {
    verifyNote.value = error instanceof Error ? error.message : '核验请求失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!payload.ok) throw new Error(payload.message)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '动作未生效'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const [filtered, all] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`).then((r) => r.json()),
      request(`${ENDPOINT}?size=200`).then((r) => r.json()),
    ])
    rows.value = filtered.items ?? []
    total.value = filtered.total ?? rows.value.length
    qualStatuses.forEach((s) => {
      const card = stats.value.find((item) => item.label === s)
      if (card) card.value = (all.items ?? []).filter((r: Row) => r['资格状态'] === s).length
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '司机列表读取失败'
  }
}

onMounted(reload)
</script>
