<template>
  <section class="page" data-module="driver-detail">
    <header class="page-head">
      <div>
        <h2>
          司机详情
          <router-link class="btn" to="/driver">返回列表</router-link>
        </h2>
        <p class="page-desc">
          档案、排班结果与停运记录均带资格版本快照；当前档案版本与记录版本不一致时会单独标出。
        </p>
      </div>
    </header>

    <div v-if="errorMessage" class="error-text">{{ errorMessage }}</div>

    <template v-if="detail">
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">当前资格状态</span>
          <strong class="stat-value" :class="statusClass(driver['资格状态'])">
            {{ driver['资格状态'] }}
          </strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">资格版本</span>
          <strong class="stat-value">{{ driver['资格版本'] }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">任务结清</span>
          <strong class="stat-value" :class="driver['任务结清'] ? 's-ok' : 's-stop'">
            {{ driver['任务结清'] ? '已结清' : '未结清' }}
          </strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">当前选中动作</span>
          <strong class="stat-value">{{ detail['当前锁定动作'] ?? '空闲' }}</strong>
        </article>
      </div>

      <div class="detail-grid">
        <article class="detail-card">
          <h3>司机档案</h3>
          <dl>
            <template v-for="f in profileFields" :key="f">
              <dt>{{ f }}</dt>
              <dd>{{ driver[f] ?? '—' }}</dd>
            </template>
            <dt>审核结论</dt>
            <dd>{{ driver['审核结论'] }}</dd>
          </dl>
          <h4>材料核验</h4>
          <ul class="check-list">
            <li v-for="item in checkItems" :key="item">
              <span :class="docChecks[item] ? 's-ok' : 's-stop'">
                {{ docChecks[item] ? '✓' : '✗' }} {{ item }}
              </span>
            </li>
          </ul>
        </article>

        <article class="detail-card">
          <h3>版本一致性核对</h3>
          <table class="data-table">
            <thead>
              <tr><th>记录类别</th><th>同版本（{{ driver['资格版本'] }}）</th><th>历史版本</th></tr>
            </thead>
            <tbody>
              <tr v-for="(v, k) in detail['版本一致性']" :key="k">
                <td>{{ categoryLabel(String(k)) }}</td>
                <td class="s-ok">{{ v['同版本'] }}</td>
                <td :class="v['跨版本'] ? 's-stop' : ''">{{ v['跨版本'] }}</td>
              </tr>
            </tbody>
          </table>
          <p class="modal-tip">跨版本记录为停运前历史落痕，不随新版本审核结论改写。</p>
        </article>
      </div>

      <article class="detail-card">
        <h3>调度名单记录</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>名单编号</th><th>资格版本</th><th>入名单时状态</th>
              <th>名单状态</th><th>选中动作</th><th>审核结论</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in detail['名单记录']" :key="String(r.id)">
              <td>{{ r['名单编号'] }}</td>
              <td :class="versionClass(r['资格版本'])">{{ r['资格版本'] }}</td>
              <td>{{ r['资格状态'] }}</td>
              <td>{{ r['名单状态'] }}</td>
              <td>{{ r['选中动作'] ?? '—' }}</td>
              <td>{{ r['审核结论'] }}</td>
            </tr>
            <tr v-if="!detail['名单记录'].length"><td colspan="6" class="empty-state">暂无名单记录</td></tr>
          </tbody>
        </table>
      </article>

      <article class="detail-card">
        <h3>排班结果</h3>
        <table class="data-table">
          <thead>
            <tr><th>排班编号</th><th>资格版本</th><th>调度动作</th><th>排班状态</th><th>审核结论</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in detail['排班结果']" :key="String(r.id)">
              <td>{{ r['排班编号'] }}</td>
              <td :class="versionClass(r['资格版本'])">{{ r['资格版本'] }}</td>
              <td>{{ r['调度动作'] }}</td>
              <td>{{ r['排班状态'] }}</td>
              <td>{{ r['审核结论'] }}</td>
            </tr>
            <tr v-if="!detail['排班结果'].length"><td colspan="5" class="empty-state">暂无排班结果</td></tr>
          </tbody>
        </table>
      </article>

      <article class="detail-card">
        <h3>停运记录</h3>
        <table class="data-table">
          <thead>
            <tr><th>停运编号</th><th>资格版本</th><th>停运时状态</th><th>停运原因</th><th>审核结论</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in detail['停运记录']" :key="String(r.id)">
              <td>{{ r['停运编号'] }}</td>
              <td :class="versionClass(r['资格版本'])">{{ r['资格版本'] }}</td>
              <td>{{ r['资格状态'] }}</td>
              <td>{{ r['停运原因'] }}</td>
              <td>{{ r['审核结论'] }}</td>
            </tr>
            <tr v-if="!detail['停运记录'].length"><td colspan="5" class="empty-state">暂无停运记录</td></tr>
          </tbody>
        </table>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null | Record<string, unknown>>
interface Detail {
  driver: Row
  名单记录: Row[]
  排班结果: Row[]
  停运记录: Row[]
  版本一致性: Record<string, { 同版本: number; 跨版本: number }>
  当前锁定动作: string | null
}

const route = useRoute()
const detail = ref<Detail | null>(null)
const errorMessage = ref('')

const profileFields = ['司机编号', '姓名', '驾驶证号', '从业资格证', '健康证有效期', '联系手机', '所属车队']
const checkItems = ['驾驶证', '从业资格证', '任务结清证明']

const driver = computed<Row>(() => detail.value?.driver ?? {})
const docChecks = computed<Record<string, boolean>>(
  () => (driver.value['材料核验'] ?? {}) as Record<string, boolean>,
)

function statusClass(status: unknown): string {
  return { 待审核: 's-pending', 审核中: 's-reviewing', 可调度: 's-ok', 停运: 's-stop' }[String(status)] ?? ''
}
function versionClass(v: unknown): string {
  return v === driver.value['资格版本'] ? 's-ok' : 's-stop'
}
function categoryLabel(k: string): string {
  return { 名单: '调度名单', 排班: '排班结果', 停运: '停运记录' }[k] ?? k
}

onMounted(async () => {
  try {
    const response = await request(`/api/driver/${String(route.params.id)}/detail`)
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: '司机详情读取失败' }))
      throw new Error(payload.detail ?? '司机详情读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '司机详情读取失败'
  }
})
</script>
