import axios from 'axios'
import router from '../router'
import { clearSession, getToken } from './auth'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (res) => res.data,
  async (err) => {
    if (err.response?.data instanceof Blob) {
      try {
        err.response.data = JSON.parse(await err.response.data.text())
      } catch {
        /* ignore */
      }
    }
    if (err.response?.status === 401) {
      clearSession()
      if (router.currentRoute.value.path !== '/login') router.push('/login')
    }
    const message = err.response?.data?.detail || err.message || '请求失败'
    return Promise.reject(new Error(typeof message === 'string' ? message : JSON.stringify(message)))
  },
)

export const login = (username, password) => http.post('/auth/login', { username, password })
export const extractPost = (url) => http.post('/posts/extract', { url })
export const writeBack = (payload) => http.post('/posts/write-back', payload)
export const fetchHistory = () => http.get('/posts/history')
export const downloadMediaZip = (shortcode, items) =>
  http.post('/media/zip', { shortcode, items }, { responseType: 'blob', timeout: 300000 })
export const health = () => http.get('/health')
