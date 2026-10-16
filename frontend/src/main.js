import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as Icons from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
for (const [name, component] of Object.entries(Icons)) app.component(name, component)
app.use(ElementPlus, { locale: zhCn }).use(router).mount('#app')
