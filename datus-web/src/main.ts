import { createApp } from 'vue'

import App from './App.vue'
import { createDatusRouter } from './router'
import './style.css'

const router = createDatusRouter()

createApp(App).use(router).mount('#app')
