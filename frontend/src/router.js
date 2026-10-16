import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from './api/auth'
import Login from './views/Login.vue'
import Workspace from './views/Workspace.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/', component: Workspace },
  ],
})

router.beforeEach((to) => {
  if (!to.meta.public && !getToken()) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.path === '/login' && getToken()) return '/'
  return true
})

export default router
