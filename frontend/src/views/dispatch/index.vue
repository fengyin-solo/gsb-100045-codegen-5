<template>
  <section class="page" data-module="dispatch">
    <header class="page-head">
      <div>
        <h2>调度工作台</h2>
        <p class="page-desc">
          只有先通过资格审核且任务已结清的司机才能加入名单并被排班；同一司机被两个调度动作
          同时选中时，只接受先到的一项。名单与排班都绑定资格版本，审核结论实时回写。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openAdd">新增调度名单</button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">待排班</span>
        <strong class="stat-value s-reviewing">{{ rosterStats.waiting }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已排班（选中中）</span>
        <strong class="stat-value s-ok">{{ rosterStats.scheduled }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">随资格停运</span>
        <strong class="stat-value s-stop">{{ rosterStats.suspended }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">停运记录</span>
        <strong class="stat-value">{{ suspensions.length }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="keyword" placeholder="按司机编号或姓名检索" />
      </label>
      <label class="filter-item">
        <span>名单状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option value="待排班">待排班</option>
          <option value="已排班">已排班</option>
          <option value="随资格停运">随资格停运</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <h3 class="block-title">调度名单（审核结论回写处）</h3>
    <table class="data-table">
      <thead>
        <tr>
          <th>名单编号</th><th>司机编号</th><th>姓名</th><th>资格版本</th>
          <th>资格状态</th><th>名单状态</th><th>选中动作</th><th>审核结论</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in roster" :key="String(row.id)">
          <td>{{ row['名单编号'] }}</td>
          <td>
            <router-link class="link" :to="`/driver/${row['司机ID']}`">{{ row['司机编号'] }}</router-link>
          </td>
          <td>{{ row['姓名'] }}</td>
          <td>{{ row['资格版本'] }}</td>
          <td><span class="status-tag" :class="statusClass(row['资格状态'])">{{ row['资格状态'] }}</span></td>
          <td>{{ row['名单状态'] }}</td>
          <td>{{ row['选中动作'] ?? '—' }}</td>
          <td>{{ row['审核结论'] }}</td>
          <td class="row-actions">
            <button
              v-if="row['名单状态'] === '待排班'"
              class="link"
              type="button"
              @click="openSchedule(row)"
            >排班选中</button>
            <span v-else-if="row['名单状态'] === '随资格停运'" class="s-stop">需重新审核</span>
            <span v-else>—</span>
          </td>
        </tr>
        <tr v-if="!roster.length">
          <td colspan="9" class="empty-state">名单为空，请先从「可调度」司机中新增</td>
        </tr>
      </tbody>
    </table>

    <div class="workbench-grid">
      <article class="detail-card">
        <h3 class="block-title">排班结果</h3>
        <table class="data-table">
          <thead>
            <tr><th>排班编号</th><th>姓名</th><th>资格版本</th><th>调度动作</th><th>排班状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in schedules" :key="String(row.id)">
              <td>{{ row['排班编号'] }}</td>
              <td>{{ row['姓名'] }}</td>
              <td>{{ row['资格版本'] }}</td>
              <td>{{ row['调度动作'] }}</td>
              <td :class="row['排班状态'] === '已锁定' ? 's-ok' : ''">{{ row['排班状态'] }}</td>
              <td>
                <button
                  v-if="row['排班状态'] === '已锁定'"
                  class="link"
                  type="button"
                  @click="release(row)"
                >任务结清并释放</button>
                <span v-else>—</span>
              </td>
            </tr>
            <tr v-if="!schedules.length"><td colspan="6" class="empty-state">暂无排班结果</td></tr>
          </tbody>
        </table>

        <h4>并发选中演练（同一司机两个动作）</h4>
        <p class="modal-tip">
          在下面填同一司机与两个动作名称后提交，系统只接受先通过审核且任务已结清的一项。
        </p>
        <div class="race-box">
          <label><span>司机ID</span><input v-model="raceDriverId" placeholder="如 1" /></label>
          <label><span>动作一</span><input v-model="raceTaskA" placeholder="如 早班冷链配送" /></label>
          <label><span>动作二</span><input v-model="raceTaskB" placeholder="如 晚班干线运输" /></label>
          <button class="btn primary" type="button" @click="runRace">同时提交两项</button>
        </div>
        <ul v-if="raceResults.length" class="race-result">
          <li v-for="(line, i) in raceResults" :key="i" :class="line.ok ? 's-ok' : 's-stop'">
            {{ line.ok ? '✓ 受理' : '✗ 拒绝' }}：{{ line.message }}
          </li>
        </ul>
      </article>

      <article class="detail-card">
        <h3 class="block-title">停运记录（绑定停运时资格版本）</h3>
        <table class="data-table">
          <thead>
            <tr><th>停运编号</th><th>姓名</th><th>资格版本</th><th>停运原因</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in suspensions" :key="String(row.id)">
              <td>{{ row['停运编号'] }}</td>
              <td>
                <router-link class="link" :to="`/driver/${row['司机ID']}`">{{ row['姓名'] }}</router-link>
              </td>
              <td class="s-stop">{{ row['资格版本'] }}</td>
              <td>{{ row['停运原因'] }}</td>
            </tr>
            <tr v-if="!suspensions.length"><td colspan="4" class="empty-state">暂无停运记录</td></tr>
          </tbody>
        </table>
      </article>
    </div>

    <footer class="page-foot">
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 新增名单：选择可调度司机 -->
    <div v-if="addOpen" class="modal-mask" @click.self="addOpen = false">
      <div class="modal">
        <h3>新增司机调度名单</h3>
        <p class="modal-tip">仅列出「可调度」司机；未审核、未结清或停运司机不会出现。</p>
        <table class="data-table">
          <thead>
            <tr><th>司机编号</th><th>姓名</th><th>资格版本</th><th>任务结清</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in dispatchableDrivers" :key="String(d.id)">
              <td>{{ d['司机编号'] }}</td>
              <td>{{ d['姓名'] }}</td>
              <td>{{ d['资格版本'] }}</td>
              <td :class="d['任务结清'] ? 's-ok' : 's-stop'">{{ d['任务结清'] ? '已结清' : '未结清' }}</td>
              <td><button class="link" type="button" @click="addRoster(d)">加入名单</button></td>
            </tr>
            <tr v-if="!dispatchableDrivers.length">
              <td colspan="5" class="empty-state">暂无可调度司机，请先到司机资格管理完成审核</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-foot">
          <button class="btn" type="button" @click="addOpen = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 排班弹窗 -->
    <div v-if="scheduleTarget" class="modal-mask" @click.self="scheduleTarget = null">
      <div class="modal">
        <h3>排班选中 · {{ scheduleTarget['姓名'] }}（{{ scheduleTarget['资格版本'] }}）</h3>
        <p class="modal-tip">提交后该司机被此动作独占，其他调度动作将被拒绝，直到任务结清并释放。</p>
        <label class="form-item">
          <span>调度动作<i>*</i></span>
          <input v-model="scheduleAction" placeholder="如：早班冷链配送" />
        </label>
        <div class="modal-foot">
          <button class="btn" type="button" @click="scheduleTarget = null">取消</button>
          <button class="btn primary" type="button" @click="submitSchedule">确认选中</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const roster = ref<Row[]>([])
const schedules = ref<Row[]>([])
const suspensions = ref<Row[]>([])
const allDrivers = ref<Row[]>([])
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

const addOpen = ref(false)
const scheduleTarget = ref<Row | null>(null)
const scheduleAction = ref('')

const raceDriverId = ref('1')
const raceTaskA = ref('早班冷链配送')
const raceTaskB = ref('晚班干线运输')
const raceResults = ref<{ ok: boolean; message: string }[]>([])

const dispatchableDrivers = computed(() =>
  allDrivers.value.filter((d) => d['资格状态'] === '可调度' && d['任务结清']),
)

const rosterStats = computed(() => ({
  waiting: roster.value.filter((r) => r['名单状态'] === '待排班').length,
  scheduled: roster.value.filter((r) => r['名单状态'] === '已排班').length,
  suspended: roster.value.filter((r) => r['名单状态'] === '随资格停运').length,
}))

function statusClass(status: unknown): string {
  return { 待审核: 's-pending', 审核中: 's-reviewing', 可调度: 's-ok', 停运: 's-stop' }[String(status)] ?? ''
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function openAdd() {
  errorMessage.value = ''
  addOpen.value = true
}

async function addRoster(driver: Row) {
  errorMessage.value = ''
  const response = await request('/api/dispatch/roster', {
    method: 'POST',
    body: JSON.stringify({ 司机ID: driver.id }),
  })
  const payload = await response.json()
  if (!payload.ok) {
    errorMessage.value = payload.message
    return
  }
  await reload()
}

function openSchedule(row: Row) {
  scheduleTarget.value = row
  scheduleAction.value = ''
  errorMessage.value = ''
}

async function submitSchedule() {
  if (!scheduleTarget.value) return
  const action = scheduleAction.value.trim()
  if (!action) {
    errorMessage.value = '请填写调度动作名称'
    return
  }
  const response = await request('/api/dispatch/schedules', {
    method: 'POST',
    body: JSON.stringify({
      司机ID: scheduleTarget.value['司机ID'],
      任务名称: action,
      名单ID: scheduleTarget.value.id,
    }),
  })
  const payload = await response.json()
  if (!payload.ok) {
    errorMessage.value = payload.message
    return
  }
  scheduleTarget.value = null
  await reload()
}

async function release(row: Row) {
  const response = await request(`/api/dispatch/schedules/${String(row.id)}/release`, {
    method: 'POST',
  })
  const payload = await response.json()
  if (!payload.ok) errorMessage.value = payload.message
  await reload()
}

async function runRace() {
  errorMessage.value = ''
  raceResults.value = []
  const driverId = Number(raceDriverId.value)
  if (!driverId || !raceTaskA.value.trim() || !raceTaskB.value.trim()) {
    errorMessage.value = '请填写司机ID和两个动作名称'
    return
  }
  const payload = {
    items: [
      { 司机ID: driverId, 任务名称: raceTaskA.value.trim() },
      { 司机ID: driverId, 任务名称: raceTaskB.value.trim() },
    ],
  }
  const response = await request('/api/dispatch/schedules/batch', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  const data = await response.json()
  raceResults.value = [
    ...data.accepted.map((x: { 结果: string }) => ({ ok: true, message: x.结果 })),
    ...data.rejected.map((x: { 原因: string }) => ({ ok: false, message: x.原因 })),
  ]
  await reload()
}

async function reload() {
  errorMessage.value = ''
  try {
    const query = new URLSearchParams()
    if (keyword.value) query.set('keyword', keyword.value)
    if (statusFilter.value) query.set('status', statusFilter.value)
    const [rosterRes, scheduleRes, suspensionRes, driverRes] = await Promise.all([
      request(`/api/dispatch/roster?${query.toString()}`).then((r) => r.json()),
      request('/api/dispatch/schedules').then((r) => r.json()),
      request('/api/dispatch/suspensions').then((r) => r.json()),
      request('/api/driver?size=200').then((r) => r.json()),
    ])
    roster.value = rosterRes.items ?? []
    schedules.value = scheduleRes.items ?? []
    suspensions.value = suspensionRes.items ?? []
    allDrivers.value = driverRes.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度工作台数据读取失败'
  }
}

onMounted(reload)
</script>
