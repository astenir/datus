import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

const absoluteUrlPattern = /^[a-zA-Z][a-zA-Z\d+\-.]*:/

function normalizeAppBase(value: string | undefined): string {
  const raw = value?.trim()
  if (!raw) return '/'

  const withLeadingSlash = raw.startsWith('/') || absoluteUrlPattern.test(raw) ? raw : `/${raw}`
  return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.DATUS_API_PROXY_TARGET
    ?? env.VITE_DATUS_API_TARGET
    ?? 'http://localhost:8000'
  const appBase = normalizeAppBase(env.VITE_DATUS_WEB_BASE)

  return {
    base: appBase,
    plugins: [vue(), tailwindcss()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined

            const normalizedId = id.split(path.sep).join('/')
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
  }
})
