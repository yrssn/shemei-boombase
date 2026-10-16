<template>
  <div class="page">
    <header class="topbar">
      <div>
        <strong>内容矩阵管理发布系统</strong>
        <span class="muted"> · Instagram 文案抓取</span>
      </div>
      <div class="user">
        <span class="muted">{{ username }}</span>
        <button @click="logout">退出</button>
      </div>
    </header>

    <main class="content">
      <section class="card">
        <h2>1. 粘贴 Instagram 帖子链接</h2>
        <form class="row" @submit.prevent="extract">
          <input
            v-model.trim="url"
            placeholder="https://www.instagram.com/p/XXXXXXXX/ 或 /reel/XXXXXXXX/"
            autofocus
          />
          <button class="primary" type="submit" :disabled="extracting || !url">
            {{ extracting ? '抓取中…' : '抓取文案' }}
          </button>
        </form>
        <p v-if="extractError" class="error">{{ extractError }}</p>
        <p v-else class="muted">粘贴链接后回车即可，几秒内文案会出现在下方。</p>
      </section>

      <section v-if="post" class="card">
        <div class="result-head">
          <h2>2. 文案结果</h2>
          <div>
            <span class="tag" v-if="post.author">@{{ post.author }}</span>
            <span class="tag" :class="post.sentiment">情绪：{{ post.sentiment_label }}（{{ post.sentiment_score }}）</span>
          </div>
        </div>
        <textarea v-model="post.caption" rows="10" spellcheck="false"></textarea>
        <div v-if="post.hashtags.length" class="tags">
          <span class="tag" v-for="t in post.hashtags" :key="t">#{{ t }}</span>
        </div>
        <div class="actions">
          <button @click="copy">{{ copied ? '已复制 ✓' : '一键复制文案' }}</button>
          <button class="primary" :disabled="writing || !post.caption" @click="write">
            {{ writing ? '写入中…' : '写回企业微信文档' }}
          </button>
          <a v-if="wroteUrl" :href="wroteUrl" target="_blank" rel="noopener" class="success">已写入，打开文档 ↗</a>
          <span v-if="writeError" class="error">{{ writeError }}</span>
        </div>
        <p v-if="!wecomConfigured" class="muted">后端尚未配置企业微信参数，写回功能暂不可用（见 backend/.env.example）。</p>
      </section>

      <section class="card">
        <div class="result-head">
          <h2>3. 最近写回记录</h2>
          <button @click="loadHistory">刷新</button>
        </div>
        <table v-if="history.length">
          <thead>
            <tr><th>时间</th><th>链接</th><th>作者</th><th>文案</th><th>情绪</th><th>提交人</th></tr>
          </thead>
          <tbody>
            <tr v-for="h in history" :key="h.id">
              <td class="nowrap">{{ h.created_at }}</td>
              <td><a :href="h.url" target="_blank" rel="noopener">{{ h.shortcode || h.url }}</a></td>
              <td>{{ h.author }}</td>
              <td class="caption-cell" :title="h.caption">{{ h.caption }}</td>
              <td>{{ h.sentiment_label }}</td>
              <td>{{ h.operator }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">暂无记录。</p>
      </section>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { extractPost, fetchHistory, health, writeBack } from '../api/http'
import { clearSession, getUsername } from '../api/auth'

const router = useRouter()
const username = getUsername()
const url = ref('')
const post = ref(null)
const extracting = ref(false)
const extractError = ref('')
const writing = ref(false)
const writeError = ref('')
const wroteUrl = ref('')
const copied = ref(false)
const history = ref([])
const wecomConfigured = ref(true)

async function extract() {
  extracting.value = true
  extractError.value = ''
  writeError.value = ''
  wroteUrl.value = ''
  post.value = null
  try {
    post.value = await extractPost(url.value)
  } catch (e) {
    extractError.value = e.message
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
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

async function write() {
  writing.value = true
  writeError.value = ''
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
    await loadHistory()
  } catch (e) {
    writeError.value = e.message
  } finally {
    writing.value = false
  }
}

async function loadHistory() {
  try {
    history.value = await fetchHistory()
  } catch {
    history.value = []
  }
}

function logout() {
  clearSession()
  router.push('/login')
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
.page { min-height: 100vh; }
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 32px; background: #fff; border-bottom: 1px solid var(--border);
}
.user { display: flex; gap: 12px; align-items: center; }
.content { max-width: 960px; margin: 24px auto; padding: 0 16px; display: flex; flex-direction: column; gap: 16px; }
h2 { font-size: 16px; margin: 0 0 12px; }
.row { display: flex; gap: 10px; }
.result-head { display: flex; justify-content: space-between; align-items: flex-start; }
textarea { resize: vertical; line-height: 1.6; white-space: pre-wrap; }
.tags { margin-top: 10px; }
.actions { display: flex; gap: 10px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
th { color: var(--muted); font-weight: 500; }
.nowrap { white-space: nowrap; }
.caption-cell { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
