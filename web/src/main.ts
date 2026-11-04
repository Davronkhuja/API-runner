import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './styles/fonts.css'
import './styles/tokens.css'
import './style.css'
import App from './App.vue'
import { initTheme } from './lib/theme'
import { applyView } from './lib/view'

initTheme()
applyView()
createApp(App).use(createPinia()).mount('#app')
