<template>
  <div class="login-page">
    <form class="card login-card" @submit.prevent="submit">
      <h1>内容矩阵管理发布系统</h1>
      <p class="muted">Instagram 文案抓取 · 写回企业微信文档</p>
      <label>
        用户名
        <input v-model.trim="username" autocomplete="username" required />
      </label>
      <label>
        密码
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="primary" type="submit" :disabled="loading">{{ loading ? '登录中…' : '登录' }}</button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../api/http'
import { saveSession } from '../api/auth'

const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const data = await login(username.value, password.value)
    saveSession(data.access_token, data.username)
    router.push(route.query.redirect || '/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.login-card { width: 380px; display: flex; flex-direction: column; gap: 14px; }
h1 { font-size: 20px; margin: 0; }
label { display: flex; flex-direction: column; gap: 6px; font-size: 14px; }
</style>
