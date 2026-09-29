<template>
  <section class="page" data-module="driver-detail">
    <header class="page-head">
      <div>
        <h2>司机详情</h2>
        <p class="page-desc">司机档案、资格信息、排班结果与停运记录一屏呈现，且反映同一资格版本。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回司机列表</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="driver">
      <div class="detail-grid">
        <article class="detail-card">
          <h3>档案信息</h3>
          <dl class="detail-list">
            <div v-for="item in profileItems" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value ?? '—' }}</dd>
            </div>
          </dl>
        </article>

        <article class="detail-card">
          <h3>资格信息</h3>
          <dl class="detail-list">
            <div>
              <dt>资格状态</dt>
              <dd><span :class="['badge', qualClass(driver.资格状态)]">{{ driver.资格状态 ?? '—' }}</span></dd>
            </div>
            <div>
              <dt>资格版本</dt>
              <dd>v{{ driver.资格版本 ?? 0 }}</dd>
            </div>
            <div>
              <dt>驾驶证核验</dt>
              <dd><span :class="['badge', driver.驾驶证核验 === '已核验' ? 'badge-ok' : 'badge-pending']">{{ driver.驾驶证核验 ?? '—' }}</span></dd>
            </div>
            <div>
              <dt>从业资格证核验</dt>
              <dd><span :class="['badge', driver.从业资格证核验 === '已核验' ? 'badge-ok' : 'badge-pending']">{{ driver.从业资格证核验 ?? '—' }}</span></dd>
            </div>
            <div>
              <dt>任务结清证明</dt>
              <dd><span :class="['badge', driver.任务结清证明 === '已结清' ? 'badge-ok' : 'badge-pending']">{{ driver.任务结清证明 ?? '—' }}</span></dd>
            </div>
            <div>
              <dt>最近审核时间</dt>
              <dd>{{ driver.最近审核时间 || '—' }}</dd>
            </div>
            <div class="full">
              <dt>审核结论</dt>
              <dd class="conclusion">{{ driver.审核结论 ?? '—' }}</dd>
            </div>
          </dl>
          <div class="detail-actions">
            <button
              v-if="driver.资格状态 === '待审核'"
              class="btn primary"
              type="button"
              @click="runAction('review')"
            >提交资格审核</button>
            <button
              v-if="driver.资格状态 === '可调度'"
              class="btn"
              type="button"
              @click="runAction('suspend')"
            >办理停运</button>
            <button
              v-if="driver.资格状态 === '停运'"
              class="btn primary"
              type="button"
              @click="runAction('reinstate')"
            >恢复调度</button>
          </div>
        </article>
      </div>

      <article class="detail-card">
        <h3>排班结果 <span class="version-tag">资格版本 v{{ driver.资格版本 ?? 0 }}</span></h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>调度编号</th>
              <th>线路编号</th>
              <th>车辆编号</th>
              <th>排班日期</th>
              <th>班次</th>
              <th>资格版本</th>
              <th>任务状态</th>
              <th>结清状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in dispatches" :key="String(row.id)">
              <td>{{ row.调度编号 }}</td>
              <td>{{ row.线路编号 }}</td>
              <td>{{ row.车辆编号 }}</td>
              <td>{{ row.排班日期 }}</td>
              <td>{{ row.班次 }}</td>
              <td>v{{ row.资格版本 }}</td>
              <td><span :class="['badge', taskClass(row.任务状态)]">{{ row.任务状态 }}</span></td>
              <td>{{ row.结清状态 }}</td>
            </tr>
            <tr v-if="!dispatches.length">
              <td colspan="8" class="empty-state">暂无排班记录</td>
            </tr>
          </tbody>
        </table>
      </article>

      <article class="detail-card">
        <h3>停运记录 <span class="version-tag">资格版本 v{{ driver.资格版本 ?? 0 }}</span></h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>停运编号</th>
              <th>停运原因</th>
              <th>停运时间</th>
              <th>资格版本</th>
              <th>状态</th>
              <th>恢复时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in suspensions" :key="String(row.id)">
              <td>{{ row.停运编号 }}</td>
              <td>{{ row.停运原因 }}</td>
              <td>{{ row.停运时间 }}</td>
              <td>v{{ row.资格版本 }}</td>
              <td><span :class="['badge', row.状态 === '停运中' ? 'badge-stop' : 'badge-ok']">{{ row.状态 }}</span></td>
              <td>{{ row.恢复时间 || '—' }}</td>
            </tr>
            <tr v-if="!suspensions.length">
              <td colspan="6" class="empty-state">暂无停运记录</td>
            </tr>
          </tbody>
        </table>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const route = useRoute()
const router = useRouter()
const driverId = Number(route.params.id)

const driver = ref<Row | null>(null)
const dispatches = ref<Row[]>([])
const suspensions = ref<Row[]>([])
const errorMessage = ref('')

const profileItems = computed(() => [
  { label: '司机编号', value: driver.value?.司机编号 },
  { label: '姓名', value: driver.value?.姓名 },
  { label: '驾驶证号', value: driver.value?.驾驶证号 },
  { label: '从业资格证', value: driver.value?.从业资格证 },
  { label: '健康证有效期', value: driver.value?.健康证有效期 },
  { label: '联系手机', value: driver.value?.联系手机 },
  { label: '所属车队', value: driver.value?.所属车队 },
  { label: '司机状态', value: driver.value?.司机状态 },
])

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

function goBack() {
  router.push('/driver')
}

async function runAction(action: string) {
  errorMessage.value = ''
  try {
    let response: Response
    if (action === 'review') {
      response = await request(`/api/driver/${driverId}/review`, { method: 'POST' })
    } else if (action === 'suspend') {
      const reason = window.prompt('请填写停运原因', '') || ''
      response = await request(`/api/driver/${driverId}/suspend`, {
        method: 'POST',
        body: JSON.stringify({ values: { reason } }),
      })
    } else {
      response = await request(`/api/driver/${driverId}/reinstate`, { method: 'POST' })
    }
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message || '动作未生效'
      return
    }
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  }
}

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`/api/driver/${driverId}/detail`)
    if (!response.ok) throw new Error('司机详情读取失败')
    const payload = await response.json()
    driver.value = payload.driver ?? null
    dispatches.value = payload.dispatches ?? []
    suspensions.value = payload.suspensions ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '司机详情读取失败'
  }
}

onMounted(load)
</script>

<style scoped>
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.detail-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.detail-card h3 {
  margin: 0 0 12px;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
  margin: 0;
}
.detail-list > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.detail-list .full {
  grid-column: 1 / -1;
}
.detail-list dt {
  font-size: 12px;
  color: #6b7280;
}
.detail-list dd {
  margin: 0;
  font-size: 14px;
}
.conclusion {
  color: #1a7f4b;
}
.detail-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
.version-tag {
  font-size: 12px;
  color: #a06a00;
  background: #fff6e0;
  padding: 2px 8px;
  border-radius: 10px;
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
.error-text {
  color: #b3261e;
}
.empty-state {
  text-align: center;
  color: #9ca3af;
  padding: 24px;
}
</style>
