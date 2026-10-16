<template>
  <div class="login">
    <div class="brand">
      <div class="brand-inner">
        <div class="logo"><el-icon :size="28"><Grid /></el-icon></div>
        <h1>内容矩阵管理发布系统</h1>
        <p class="slogan">Instagram 文案一键抓取 · 秒级写回企业微信文档</p>
        <ul>
          <li><el-icon><Link /></el-icon>贴链接就行，零学习成本</li>
          <li><el-icon><DocumentCopy /></el-icon>文案不缺字、不乱码、格式不乱</li>
          <li><el-icon><ChatDotSquare /></el-icon>情绪识别 + 话题标签自动提取</li>
          <li><el-icon><Share /></el-icon>多人同时在文档同一行做二次创作</li>
        </ul>
      </div>
    </div>
    <div class="panel">
      <el-card class="login-card" shadow="never">
        <h2>欢迎登录</h2>
        <p class="sub">请使用运营账号登录系统</p>
        <el-form :model="form" label-position="top" size="large" @submit.prevent="submit">
          <el-form-item label="用户名">
            <el-input v-model.trim="form.username" placeholder="请输入用户名" autocomplete="username">
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" show-password placeholder="请输入密码"
                      autocomplete="current-password" @keyup.enter="submit">
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="alert" />
          <el-button type="primary" native-type="submit" :loading="loading" class="submit">登 录</el-button>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../api/http'
import { saveSession } from '../api/auth'

const router = useRouter()
const route = useRoute()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function submit() {
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await login(form.username, form.password)
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
.login { display: flex; min-height: 100vh; }
.brand {
  flex: 1.1; display: flex; align-items: center; justify-content: center; color: #fff;
  background: radial-gradient(circle at 20% 20%, rgba(255,255,255,0.12), transparent 40%),
              linear-gradient(135deg, #1f3bb3 0%, #3370ff 55%, #6d8dff 100%);
}
.brand-inner { max-width: 420px; padding: 40px; }
.logo {
  width: 56px; height: 56px; border-radius: 14px; display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,0.18); margin-bottom: 28px;
}
h1 { font-size: 30px; margin: 0 0 12px; letter-spacing: 1px; }
.slogan { opacity: 0.85; font-size: 15px; margin: 0 0 36px; }
ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 14px; font-size: 14px; }
li { display: flex; align-items: center; gap: 10px; opacity: 0.95; }
.panel { flex: 1; display: flex; align-items: center; justify-content: center; background: #fff; }
.login-card { width: 400px; border: none; }
h2 { margin: 0 0 6px; font-size: 24px; }
.sub { color: #8f959e; margin: 0 0 28px; font-size: 14px; }
.alert { margin-bottom: 16px; }
.submit { width: 100%; margin-top: 4px; }
@media (max-width: 900px) { .brand { display: none; } }
</style>
