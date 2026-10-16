<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">
        <el-icon :size="22"><Grid /></el-icon>
        <span>内容矩阵管理</span>
      </div>
      <el-menu :default-active="active" class="menu" background-color="transparent" text-color="#a9aeb8"
               active-text-color="#fff" @select="active = $event">
        <el-menu-item index="extract"><el-icon><MagicStick /></el-icon><span>Instagram 文案抓取</span></el-menu-item>
        <el-menu-item index="history"><el-icon><Tickets /></el-icon><span>写回记录</span></el-menu-item>
      </el-menu>
      <div class="aside-footer">
        <el-tag :type="wecomConfigured ? 'success' : 'warning'" effect="dark" size="small" round>
          {{ wecomConfigured ? '企业微信已连接' : '企业微信未配置' }}
        </el-tag>
      </div>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="crumb">
          <span class="crumb-root">内容矩阵管理发布系统</span>
          <el-icon class="crumb-sep"><ArrowRight /></el-icon>
          <span>{{ active === 'extract' ? 'Instagram 文案抓取' : '写回记录' }}</span>
        </div>
        <el-dropdown @command="onUserCommand">
          <span class="user">
            <el-avatar :size="30" class="avatar">{{ username.slice(0, 1).toUpperCase() }}</el-avatar>
            <span>{{ username }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="main">
        <template v-if="active === 'extract'">
          <el-card class="input-card">
            <div class="input-title">
              <h3>粘贴 Instagram 帖子链接</h3>
              <span class="hint">支持 /p/、/reel/ 链接，回车即可抓取，几秒内文案出现在下方</span>
            </div>
            <div class="input-row">
              <el-input v-model.trim="url" size="large" clearable
                        placeholder="https://www.instagram.com/p/XXXXXXXX/" @keyup.enter="extract">
                <template #prefix><el-icon><Link /></el-icon></template>
              </el-input>
              <el-button type="primary" size="large" :loading="extracting" :disabled="!url" @click="extract">
                <el-icon v-if="!extracting"><MagicStick /></el-icon>&nbsp;抓取文案
              </el-button>
            </div>
          </el-card>

          <el-empty v-if="!post && !extracting" description="还没有抓取结果，粘贴链接开始吧" :image-size="120" class="empty" />

          <el-row v-if="post" :gutter="16" class="result">
            <el-col :span="16">
              <el-card>
                <template #header>
                  <div class="card-head">
                    <span>原始文案 <span class="count">{{ post.caption.length }} 字</span></span>
                    <el-space>
                      <el-button @click="copy"><el-icon><DocumentCopy /></el-icon>&nbsp;一键复制</el-button>
                      <el-button type="primary" :loading="writing" :disabled="!post.caption" @click="write">
                        <el-icon v-if="!writing"><Promotion /></el-icon>&nbsp;写回企业微信文档
                      </el-button>
                    </el-space>
                  </div>
                </template>
                <el-input v-model="post.caption" type="textarea" :autosize="{ minRows: 12, maxRows: 24 }"
                          class="caption" spellcheck="false" />
                <el-alert v-if="wroteUrl" type="success" show-icon :closable="false" class="alert">
                  <template #title>
                    已写入企业微信文档，<el-link type="primary" :href="wroteUrl" target="_blank">打开文档</el-link>
                  </template>
                </el-alert>
                <el-alert v-if="!wecomConfigured" type="warning" show-icon :closable="false" class="alert"
                          title="后端尚未配置企业微信参数，写回功能暂不可用（见 backend/.env.example）" />
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card header="帖子信息">
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item label="作者">
                    <el-link v-if="post.author" type="primary" :href="`https://www.instagram.com/${post.author}/`" target="_blank">@{{ post.author }}</el-link>
                    <span v-else class="muted">未识别</span>
                  </el-descriptions-item>
                  <el-descriptions-item label="情绪">
                    <el-tag :type="sentimentType(post.sentiment)" effect="light">{{ post.sentiment_label }}</el-tag>
                    <span class="muted score">分值 {{ post.sentiment_score }}</span>
                  </el-descriptions-item>
                  <el-descriptions-item label="链接">
                    <el-link type="primary" :href="post.url" target="_blank">{{ post.shortcode }}</el-link>
                  </el-descriptions-item>
                  <el-descriptions-item label="来源">{{ post.source }}</el-descriptions-item>
                </el-descriptions>
                <div class="section-title">话题标签 <span class="muted">{{ post.hashtags.length }}</span></div>
                <div v-if="post.hashtags.length" class="tags">
                  <el-tag v-for="t in post.hashtags" :key="t" size="small" round>#{{ t }}</el-tag>
                </div>
                <p v-else class="muted">无</p>
                <div class="section-title">提及账号 <span class="muted">{{ post.mentions.length }}</span></div>
                <div v-if="post.mentions.length" class="tags">
                  <el-tag v-for="m in post.mentions" :key="m" size="small" type="info" round>@{{ m }}</el-tag>
                </div>
                <p v-else class="muted">无</p>
              </el-card>
            </el-col>
          </el-row>
        </template>

        <el-card v-else>
          <template #header>
            <div class="card-head">
              <span>最近写回记录</span>
              <el-button :loading="loadingHistory" @click="loadHistory"><el-icon><Refresh /></el-icon>&nbsp;刷新</el-button>
            </div>
          </template>
          <el-table :data="history" v-loading="loadingHistory" stripe empty-text="暂无记录">
            <el-table-column prop="created_at" label="时间" width="170" />
            <el-table-column label="帖子" width="150">
              <template #default="{ row }">
                <el-link type="primary" :href="row.url" target="_blank">{{ row.shortcode || row.url }}</el-link>
              </template>
            </el-table-column>
            <el-table-column prop="author" label="作者" width="150" />
            <el-table-column prop="caption" label="文案" min-width="300" show-overflow-tooltip />
            <el-table-column label="情绪" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="sentimentTypeByLabel(row.sentiment_label)">{{ row.sentiment_label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="operator" label="提交人" width="110" />
          </el-table>
        </el-card>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { extractPost, fetchHistory, health, writeBack } from '../api/http'
import { clearSession, getUsername } from '../api/auth'

const router = useRouter()
const username = getUsername() || 'user'
const active = ref('extract')
const url = ref('')
const post = ref(null)
const extracting = ref(false)
const writing = ref(false)
const wroteUrl = ref('')
const history = ref([])
const loadingHistory = ref(false)
const wecomConfigured = ref(true)

const sentimentType = (s) => ({ positive: 'success', negative: 'danger' }[s] || 'info')
const sentimentTypeByLabel = (l) => ({ 积极: 'success', 消极: 'danger' }[l] || 'info')

async function extract() {
  if (!url.value) return
  extracting.value = true
  wroteUrl.value = ''
  post.value = null
  try {
    post.value = await extractPost(url.value)
    ElMessage.success('文案抓取成功')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    extracting.value = false
  }
}

async function copy() {
  try {
    await navigator.clipboard.writeText(post.value.caption)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = post.value.caption
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  ElMessage.success('文案已复制到剪贴板')
}

async function write() {
  writing.value = true
  wroteUrl.value = ''
  try {
    const res = await writeBack({
      url: post.value.url,
      shortcode: post.value.shortcode,
      author: post.value.author,
      caption: post.value.caption,
      sentiment_label: post.value.sentiment_label,
    })
    wroteUrl.value = res.doc_url || '#'
    ElMessage.success(res.message || '已写入企业微信文档')
    loadHistory()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    writing.value = false
  }
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    history.value = await fetchHistory()
  } catch {
    history.value = []
  } finally {
    loadingHistory.value = false
  }
}

function onUserCommand(cmd) {
  if (cmd === 'logout') {
    clearSession()
    router.push('/login')
  }
}

onMounted(async () => {
  loadHistory()
  try {
    const h = await health()
    wecomConfigured.value = !!h.wecom_configured
  } catch {
    /* ignore */
  }
})
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: var(--sidebar-bg); display: flex; flex-direction: column; }
.brand {
  height: 60px; display: flex; align-items: center; gap: 10px; padding: 0 20px;
  color: #fff; font-weight: 600; font-size: 16px; border-bottom: 1px solid rgba(255,255,255,0.08);
}
.menu { border-right: none; flex: 1; padding-top: 8px; }
.menu :deep(.el-menu-item) { margin: 4px 10px; border-radius: 8px; height: 44px; }
.menu :deep(.el-menu-item.is-active) { background: var(--el-color-primary); }
.menu :deep(.el-menu-item:hover) { background: rgba(255,255,255,0.08); }
.aside-footer { padding: 16px 20px; }
.header {
  height: 60px; background: #fff; display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid #e5e6eb; padding: 0 24px;
}
.crumb { display: flex; align-items: center; gap: 6px; font-size: 14px; }
.crumb-root, .crumb-sep { color: #8f959e; }
.user { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 14px; outline: none; }
.avatar { background: var(--el-color-primary); font-size: 14px; }
.main { padding: 20px 24px; overflow: auto; }
.input-card { margin-bottom: 16px; }
.input-title { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; }
.input-title h3 { margin: 0; font-size: 16px; }
.hint { color: #8f959e; font-size: 13px; }
.input-row { display: flex; gap: 12px; }
.empty { margin-top: 60px; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.count { color: #8f959e; font-weight: 400; font-size: 12px; margin-left: 6px; }
.caption :deep(textarea) { line-height: 1.7; font-size: 14px; }
.alert { margin-top: 14px; }
.section-title { font-weight: 600; font-size: 13px; margin: 18px 0 10px; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.muted { color: #8f959e; font-size: 12px; }
.score { margin-left: 8px; }
</style>
