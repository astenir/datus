import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const apiTarget = process.env.VITE_DATUS_API_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined

          const normalizedId = id.split(path.sep).join('/')
          if (normalizedId.includes('/node_modules/markdown-it/')
            || normalizedId.includes('/node_modules/vue-stream-markdown/')) return 'vendor-markdown'
          if (normalizedId.includes('/node_modules/@lucide/vue/')) return 'vendor-icons'
          if (normalizedId.includes('/node_modules/reka-ui/')) return 'vendor-ui'
          if (normalizedId.includes('/node_modules/@vueuse/')) return 'vendor-vueuse'
          if (normalizedId.includes('/node_modules/vue-stick-to-bottom/')) return 'vendor-scroll'
          if (normalizedId.includes('/node_modules/vue/')
            || normalizedId.includes('/node_modules/@vue/')
            || normalizedId.includes('/node_modules/vue-router/')) return 'vendor-vue'
          return undefined
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/health': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
