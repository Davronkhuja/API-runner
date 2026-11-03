import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './styles/fonts.css'
import './styles/tokens.css'
import './style.css'
import App from './App.vue'
import { initTheme } from './lib/theme'

initTheme()
createApp(App).use(createPinia()).mount('#app')
