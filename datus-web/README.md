# Datus Web

Datus Web 是 Datus 的新 Vue/Vite 前端。这个仓库使用 Vue 3、TypeScript、Tailwind CSS、shadcn-vue 和 AI Elements 构建面向 Datus 工作区的操作界面。

当前实现重点是保留旧 Datus 前端中有用的业务行为，同时使用新的组件体系和视觉规范，不直接复制旧前端的页面壳、样式系统或 UI primitive。

## 功能范围

- 工作区外壳、顶部栏、会话侧边栏、用户菜单和数据源连接测试
- 聊天界面、消息渲染、AI Elements 组合和用户交互块
- 数据目录、语义模型、知识构建、SQL 执行、MCP 服务/工具视图
- 报表和仪表盘入口
- Agent 管理入口
- 用户、角色和审计管理摘要

## 技术栈

- Vue 3 + Composition API
- TypeScript
- Vite
- Tailwind CSS 4
- shadcn-vue
- AI Elements
- Vitest
- Playwright

## 快速开始

安装依赖：

```bash
npm install
```

启动开发服务器：

```bash
npm run dev
```

默认开发服务器端口是 `5173`。如果端口已被占用，Vite 会自动尝试下一个可用端口。

## 后端配置

开发服务器会把 `/api` 和 `/health` 代理到后端。默认后端地址是：

```text
http://localhost:8000
```

可以通过 `VITE_DATUS_API_TARGET` 指定其他后端：

```bash
VITE_DATUS_API_TARGET=http://127.0.0.1:8001 npm run dev
```

## 子路径托管

生产环境如果把前端托管到子路径，例如 `https://example.com/datus/`，构建时需要指定 Vite base：

```bash
VITE_DATUS_WEB_BASE=/datus/ npm run build
```

建议只把前端放到子路径，API 仍保持站点根路径代理：

```text
/datus/   -> datus-web 静态文件
/api/...  -> datus-agent API
/health   -> datus-agent health
```

Nginx 示例：

```nginx
server {
    listen 80;
    server_name example.com;

    client_max_body_size 100m;

    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
        proxy_cache off;
        gzip off;
        add_header X-Accel-Buffering no always;
    }

    location = /datus {
        return 301 /datus/;
    }

    location /datus/assets/ {
        alias /srv/datus-web/dist/assets/;
        access_log off;
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    location /datus/ {
        alias /srv/datus-web/dist/;
        index index.html;
        try_files $uri $uri/ /datus/index.html;
    }
}
```

如果浏览器曾在页面里设置过 API 地址，`localStorage` 中的 `datus-api-base` 会优先于同源 `/api` 代理。部署后遇到前端请求指向旧地址时，先清理该项或在页面里改回空值。

本地环境变量请写入 `.env.local`，不要提交真实环境配置或凭据。只允许提交 `.env.example` 这类占位模板。

## 内网测试构建

需要为某个内网测试环境固定登录、API 和子路径配置时，创建本地文件 `.env.intranet.local`。该文件会被 `.gitignore` 忽略，不要提交：

```bash
VITE_DATUS_WEB_BASE=/datus/
VITE_DATUS_API_TARGET=https://api.example.internal/
VITE_AUTH_API_URL=https://passport.example.internal/user/detail
VITE_AUTH_LOGIN_URL=https://passport.example.internal/login.html
```

然后执行：

```bash
npm run build:intranet
```

`build:intranet` 会通过 Vite mode 读取 `.env.intranet.local`。如果前端和 API 由同一个 Nginx 站点代理，推荐把 `VITE_DATUS_API_TARGET` 留空，让浏览器请求同源 `/api`，由 Nginx 转发到后端；只有 API 与前端不同源且后端 CORS 已正确放行时，才把它设置成完整后端 origin。

## 自定义新会话开屏文案

新会话空态的欢迎标题和建议语句都从部署目录的文本文件读取（UTF-8），构建时 Vite 会把 `public/` 下的文件原样复制到 `dist/` 根目录（与 `index.html` 同级），因此部署后**直接编辑服务器上对应文件即可生效，无需重新构建**。

### 欢迎标题

`chat-welcome-title.txt`，取第一个非空行：

```
有什么我能帮你的吗？
```

- 文件不存在、读取失败或内容为空时，回退到内置默认标题（见 `src/features/chat/chat-welcome.ts`）。

### 建议语句

`chat-suggestions.txt`，每行一句：

```
帮我分析基金持仓的关键变化
列出当前数据源有哪些表
```

- 文件不存在、读取失败时，回退到内置默认文案（见 `src/features/chat/chat-suggestions.ts`）；
- 文件存在但没有任何有效行时，不展示任何建议语句；
- 空行、重复行会被自动过滤。

两个文件修改后刷新页面即可生效（请求带 `no-cache`，不做浏览器缓存）。注意：文件必须保存为 UTF-8 编码（含中文时尤其重要），并确保 Web 服务器能直接访问这些静态文件（`try_files` 命中即可，无需额外配置）。

## 常用命令

```bash
npm run lint
npm test
npm run build
npm run build:intranet
npm run preview
npm run lint:typography
```

命令说明：

- `npm run lint`: 对项目自有 Vue/TypeScript 代码运行 ESLint
- `npm test`: 运行 Vitest 测试
- `npm run build`: 运行 `vue-tsc` 类型检查并构建生产包
- `npm run build:intranet`: 使用 `.env.intranet.local` 构建内网测试包
- `npm run preview`: 预览生产构建
- `npm run lint:typography`: 检查项目业务 UI 的字号规范

## API 契约同步

后端 OpenAPI 是接口契约的来源。添加、修改或调试 API 调用时，需要保持 `openapi.json` 和 `src/types/openapi.ts` 同步。

从默认后端同步：

```bash
npm run api:sync
```

从指定后端同步：

```bash
VITE_DATUS_API_TARGET=http://127.0.0.1:8001 npm run api:sync
```

如果 `openapi.json` 已经是目标契约，只需要重新生成类型：

```bash
npm run api:types
```

接口相关变更后建议运行：

```bash
npm run api:smoke
```

本地 `UserInfoBearerAuthProvider` 模式需要提供开发 Bearer token：

```bash
VITE_DEV_ACCESS_TOKEN=dev-alice-token npm run dev
DATUS_API_TOKEN=dev-alice-token npm run api:smoke
```

## 目录结构

```text
src/features/              # 项目业务 UI
src/features/workspace/    # 工作区外壳、顶部栏、侧边栏、用户菜单
src/features/chat/         # 聊天 UI、消息渲染、交互块
src/features/catalog/      # 数据目录
src/features/semantic/     # 语义模型、主题域、指标和参考 SQL 工作台
src/features/config/       # 运行配置、模型和数据源连接探测
src/features/knowledge/    # 业务知识库和平台文档构建
src/features/sql/          # SQL 执行面板
src/features/mcp/          # MCP 服务和工具视图
src/features/artifacts/    # 报表和仪表盘入口
src/features/admin/        # 用户、角色和审计管理
src/components/ui/         # shadcn-vue primitive
src/components/ai-elements/# AI Elements primitive
src/composables/           # 状态、side effects 和后端编排
src/lib/                   # API、协议解析、纯逻辑工具
src/types/                 # 共享类型和 OpenAPI 生成类型
scripts/                   # 项目脚本
```

业务 UI 应放在 `src/features/**`。不要为了业务样式修改 `src/components/ui/**` 或 `src/components/ai-elements/**` 中的 primitive；优先在 feature 层组合和覆盖。

## 开发规范

详细规则见 [AGENTS.md](./AGENTS.md)。

核心约束：

- Vue 单文件组件使用 `<script setup lang="ts">`
- 项目业务代码不使用 `any`
- 组件不直接调用 `fetch`
- 组件不直接访问浏览器存储
- API 调用放在 `src/lib/api/**`
- 状态和副作用优先由 composable 管理
- 业务 UI 使用 shadcn-vue 和 AI Elements，不引入平行组件体系
- 默认操作 UI 字号使用 `text-sm`

## 提交信息

提交信息采用 Conventional Commits 结构，并使用中文描述：

```text
<type>(<scope>): 中文描述
```

示例：

```text
style(workspace): 统一侧边栏字号
feat(chat): 新增交互块提交
fix(api): 归一化数据源测试响应
docs(agents): 补充提交信息规范
build(typography): 新增字号检查脚本
```

## 验证

非平凡变更完成前至少运行：

```bash
git diff --check
npm run lint
npm test
npm run build
```

项目规则审计：

```bash
npm run lint:typography
rg -n "\bany\b|as any|@ts-ignore|@ts-expect-error" src/features src/composables src/lib src/types.ts src/types src/App.vue src/main.ts vite.config.ts
rg -n "<button|<style|:style=|\sstyle=" src/features src/App.vue
rg -n "from ['\"]reka-ui|fetch\(" src/features src/composables src/lib src/types.ts src/types src/App.vue src/main.ts vite.config.ts
```

视觉或布局变更还应使用 Playwright 截图检查桌面视口。
