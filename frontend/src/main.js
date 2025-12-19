// 文件路径: src/main.js
import { createApp } from 'vue'
import App from './App.vue'

// 1. 引入 Element Plus 样式库
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// 2. 引入图标
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

const app = createApp(App)

// 3. 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)
app.mount('#app')