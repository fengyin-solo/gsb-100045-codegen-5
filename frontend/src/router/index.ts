import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
const Shipment = () => import('@/views/shipment/index.vue')
const TempMonitor = () => import('@/views/temp_monitor/index.vue')
const Vehicle = () => import('@/views/vehicle/index.vue')
const Driver = () => import('@/views/driver/index.vue')
const DriverDetail = () => import('@/views/driver/detail.vue')
const Dispatch = () => import('@/views/dispatch/index.vue')
const ColdStorage = () => import('@/views/cold_storage/index.vue')
const Loading = () => import('@/views/loading/index.vue')
const Alert = () => import('@/views/alert/index.vue')
const Route = () => import('@/views/route/index.vue')
const ReeferUnit = () => import('@/views/reefer_unit/index.vue')
const Fuel = () => import('@/views/fuel/index.vue')
const Delivery = () => import('@/views/delivery/index.vue')
const BreakChain = () => import('@/views/break_chain/index.vue')
const Dock = () => import('@/views/dock/index.vue')
const Package = () => import('@/views/package/index.vue')
const Toll = () => import('@/views/toll/index.vue')
const Sanitation = () => import('@/views/sanitation/index.vue')
const Contract = () => import('@/views/contract/index.vue')
const Insurance = () => import('@/views/insurance/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/shipment', name: 'shipment', component: Shipment },
    { path: '/temp_monitor', name: 'temp_monitor', component: TempMonitor },
    { path: '/vehicle', name: 'vehicle', component: Vehicle },
    { path: '/driver', name: 'driver', component: Driver },
    { path: '/driver/:id', name: 'driver-detail', component: DriverDetail },
    { path: '/dispatch', name: 'dispatch', component: Dispatch },
    { path: '/cold_storage', name: 'cold_storage', component: ColdStorage },
    { path: '/loading', name: 'loading', component: Loading },
    { path: '/alert', name: 'alert', component: Alert },
    { path: '/route', name: 'route', component: Route },
    { path: '/reefer_unit', name: 'reefer_unit', component: ReeferUnit },
    { path: '/fuel', name: 'fuel', component: Fuel },
    { path: '/delivery', name: 'delivery', component: Delivery },
    { path: '/break_chain', name: 'break_chain', component: BreakChain },
    { path: '/dock', name: 'dock', component: Dock },
    { path: '/package', name: 'package', component: Package },
    { path: '/toll', name: 'toll', component: Toll },
    { path: '/sanitation', name: 'sanitation', component: Sanitation },
    { path: '/contract', name: 'contract', component: Contract },
    { path: '/insurance', name: 'insurance', component: Insurance },
  ],
})

export default router
