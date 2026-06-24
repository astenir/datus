# Datus Web

Datus Web 是 Datus 的新 Vue/Vite 前端。这个仓库使用 Vue 3、TypeScript、Tailwind CSS、shadcn-vue 和 AI Elements 构建面向 Datus 工作区的操作界面。

当前实现重点是保留旧 Datus 前端中有用的业务行为，同时使用新的组件体系和视觉规范，不直接复制旧前端的页面壳、样式系统或 UI primitive。

## 功能范围

- 工作区外壳、顶部栏、会话侧边栏、用户菜单和数据源连接测试
- 聊天界面、消息渲染、AI Elements 组合和用户交互块
- 数据目录、SQL 执行、MCP 服务/工具视图
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

本地环境变量请写入 `.env.local`，不要提交真实环境配置或凭据。只允许提交 `.env.example` 这类占位模板。

## 常用命令

```bash
npm test
npm run build
npm run preview
npm run lint:typography
```

命令说明：

- `npm test`: 运行 Vitest 测试
- `npm run build`: 运行 `vue-tsc` 类型检查并构建生产包
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

## 目录结构

```text
src/features/              # 项目业务 UI
src/features/workspace/    # 工作区外壳、顶部栏、侧边栏、用户菜单
src/features/chat/         # 聊天 UI、消息渲染、交互块
src/features/catalog/      # 数据目录
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
