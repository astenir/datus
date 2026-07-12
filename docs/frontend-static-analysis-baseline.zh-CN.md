# 前端静态分析基线

本文记录 `datus-web` 项目自有代码的静态分析现状、人工审阅结论和后续门禁迁移顺序。目标是先建立可信基线，再引入能够稳定阻止新问题的规则；本文不把生成组件或上游依赖中的实现习惯计入项目债务。

## 审计范围

本次重点审阅以下项目自有代码：

- `datus-web/src/features/`
- `datus-web/src/composables/`
- `datus-web/src/lib/`
- `datus-web/src/router/`
- `datus-web/src/types.ts` 和 `datus-web/src/types/`
- `datus-web/src/App.vue`、`datus-web/src/main.ts`
- `datus-web/vite.config.ts`

以下目录仍由 TypeScript 和生产构建覆盖，但不作为项目自有规则清零目标：

- `datus-web/src/components/ui/`：shadcn-vue 生成的通用 UI primitive。
- `datus-web/src/components/ai-elements/`：AI Elements 生成组件。
- `datus-web/src/types/openapi.ts`：根据 OpenAPI 契约生成的类型。
- `node_modules/` 和 `@datus/web-artifact-render`：外部依赖和上游包。

如果生成层暴露真实的类型错误、构建失败或安全问题，应通过生成源、版本升级或项目层适配处理，而不是为了让文本扫描归零而批量改写生成文件或上游源码。

## 当前工具链与覆盖

`datus-web` 已直接声明 ESLint、TypeScript ESLint、eslint-plugin-vue 及其 parser 等开发依赖，并提供本地 `lint` 脚本。现有质量检查包括：

| 检查 | 当前能力 | 主要边界 |
| --- | --- | --- |
| `npm run lint` | 对项目自有 Vue/TypeScript 代码运行类型感知的 ESLint flat config | 已加入 Web Quality 实体 job，在单元测试和浏览器依赖安装前执行 |
| `npm run build` | 先运行 `vue-tsc -b`，再构建生产资源 | 能发现类型、未使用局部变量/参数和构建集成问题；不能完整检查 Promise 使用、Vue 模板语义和生命周期策略 |
| `npm test` | 运行 Vitest 单元测试 | 覆盖业务工具、composable、API 适配和部分路由/安全契约；不是通用静态规则 |
| `npm run test:browser` | 编译并运行 Playwright 浏览器测试 | 覆盖真实浏览器中的 Renderer 集成；不扫描全部业务组件 |
| `npm run lint:typography` | 扫描 `src/features/` 和 `src/App.vue` 的字号 utility | 是窄范围设计规范检查，不替代 Vue/TypeScript lint |
| Web Quality workflow | 对相关前端变更运行 ESLint、测试、字号检查和构建 | 继续由路径 detector 控制实体 job，并通过稳定的 `Web quality gate` 汇总结果 |

应用 TypeScript 配置已经启用：

- `strict`
- `noUnusedLocals`
- `noUnusedParameters`
- `noFallthroughCasesInSwitch`
- `noUncheckedSideEffectImports`

`tsconfig.app.json` 的实际文件集合包含 `src/**/*.ts`、`src/**/*.tsx` 和 `src/**/*.vue`，因此项目自有代码、测试以及生成组件都在 Vue TypeScript 检查范围内。`vite.config.ts` 由 `tsconfig.node.json` 单独覆盖，浏览器测试由 `tsconfig.browser.json` 覆盖。

本次基线验证结果：

- Vue TypeScript project build 通过。
- ESLint 项目自有代码检查通过。
- 55 个 Vitest 文件、455 项单元测试通过。
- 4 项 Chromium Renderer 浏览器测试通过。
- Typography 扫描通过；两处 `text-base` 是现有规则要求人工确认的例外，不是失败。
- 生产构建通过。

## 代码规模和所有权边界

本次统计只计算 `.vue` 和 `.ts` 文件：

| 范围 | Vue 文件 | TypeScript 文件 | 其中测试文件 | 合计行数 |
| --- | ---: | ---: | ---: | ---: |
| `features`、`composables`、`lib`、`router` | 52 | 130 | 55 | 42,528 |
| `components/ui`、`components/ai-elements` | 561 | 116 | - | 19,004 |

生成组件有 677 个文件，数量明显高于项目核心代码。任何新静态规则都必须先限定所有权范围，否则规则结果会主要反映生成模板风格，而不是 Datus 业务代码风险。

## 扫描结果

对项目自有范围进行文本扫描并逐项查看上下文后，得到以下结果。

### 已满足的约束

- 未发现显式 `any`、`as any`、`@ts-ignore` 或 `@ts-expect-error`。
- 52 个项目自有 SFC 均使用 `<script setup lang="ts">`。
- `src/features/` 和 `App.vue` 未发现原生 `<button>`、组件 `<style>`、内联 `style` 或直接导入 `reka-ui`。
- 组件内未发现 `fetch` 或浏览器存储访问；唯一的 `fetch` 位于统一请求层 `src/lib/request.ts`。
- 未发现 `v-html`，也未发现同一元素同时使用 `v-if` 和 `v-for`。文本级复核得到 131 处 `v-for` 和 131 处 `:key`。
- 未发现 `console.log`、`console.debug`、`console.info` 或 `debugger`；现有 `console.error`、`console.warn` 用于失败诊断。
- 项目自有组件没有直接修改 props 的明显模式。

### 经复核可接受的模式

- `ChatCodeBlockCopyButton.vue`、`ChatActivityStatus.vue` 和 `useChatWorkspace.ts` 创建的 timer 会在重置或组件卸载时清理。
- `ArtifactViewerFrame.vue` 的 `message` listener 会在卸载时移除，同时终止旧的预览请求。
- `src/lib/chat.ts` 的超时 timer 和调用方 AbortSignal listener 位于 `finally` 中清理。
- 多数 fire-and-forget 调用使用显式 `void`，被调用的加载函数在内部捕获错误并更新 UI 状态。这是有意的调用边界，不应仅凭文本匹配判为未处理 Promise。
- `src/lib/role-permissions.ts` 中 Map 和树节点的非空断言紧跟在初始化分支之后，属于局部可证明不变量。后续可以消除断言，但当前没有证据表明它们会产生运行时缺陷。
- 外部依赖产生的构建 warning 不属于项目自有静态分析债务，不应通过修改 `node_modules` 或上游 Renderer 源码处理。

## 基线发现与处置状态

### 已处理：浏览器存储异常可能破坏启动或交互

相关位置：

- `datus-web/src/composables/useTheme.ts`
- `datus-web/src/composables/useChatSettings.ts`
- `datus-web/src/composables/useConnection.ts`

基线审计发现，`localStorage` 在禁用持久化、受限 iframe、隐私策略或存储配额异常时可能抛出异常。主题模块曾在模块初始化期间直接读取并写入 `localStorage`；该异常可能阻止应用启动。聊天设置和 API 地址的部分写入也曾缺少失败降级。

该项已通过 `datus-web/src/lib/local-storage.ts` 收口：读取失败回退默认值，写入失败只放弃持久化，不影响当前响应式状态。`useChatSettings.ts` 也会把反序列化结果先作为 `unknown`，再逐项验证字符串和布尔字段。

对应测试覆盖存储 API 不存在、属性访问抛错、读写操作抛错、损坏 JSON、错误字段类型，以及主题、聊天设置和 API 地址在持久化失败时继续工作的行为。

### 已处理：异步路由上下文可能发生旧结果覆盖新状态

相关位置：`datus-web/src/features/workspace/useWorkspaceRouting.ts`。

基线审计发现，`applyRouteWorkspaceContext()` 会先读取 datasource/database/schema 快照，再等待数据源切换，最后写入 database 和 schema。路由查询参数在等待期间再次变化时，多个调用可以并发执行；较早调用可能在较晚调用之后恢复并写回旧快照。

该项已通过 `datus-web/src/features/workspace/workspace-route-context.ts` 收口。每次应用都会取得单调递增的请求代号，只有最新请求可以在异步切换后写入 database 和 schema；路由/认证状态变化和组件卸载也会使未完成请求失效。确定性测试覆盖“第一次切换延迟、第二次切换先完成”的顺序，并确认旧调用不能覆盖最新上下文。

### 低风险：外部 JSON 边界仍有直接类型断言

相关位置包括：

- `datus-web/src/composables/useAuth.ts` 的开发用户配置。
- `datus-web/src/lib/role-permissions.ts` 的授权值解析。
- 泛型 API helper 对 `response.json()` 的返回类型断言。

TypeScript 的 `strict` 模式不会验证运行时 JSON。当前关键业务解析多数已经先落为 `unknown` 再缩窄，但上述边界仍依赖调用方或后端契约。开发用户配置的影响仅限开发模式；API 响应的系统性运行时校验应按风险逐个端点引入，不建议在静态分析迁移阶段一次性增加整套 schema 框架。

## TypeScript、专项脚本与 ESLint 的职责

| 问题类别 | 当前检查 | 后续建议 |
| --- | --- | --- |
| 类型不匹配、未使用局部变量/参数、错误导入 | TypeScript 已覆盖 | 保持现有严格配置 |
| 业务 UI 字号 | Typography 脚本已覆盖 | 保持专项脚本，不在 ESLint 中复制 |
| Renderer 浏览器集成 | Playwright 已覆盖 | 保持浏览器测试，不修改上游包换取 lint 通过 |
| Vue 模板合法性、props 变更、`v-for` key | ESLint 已覆盖项目自有代码 | 保持生成 primitive 排除边界 |
| 未显式处理的 Promise | ESLint 使用类型感知的 `no-floating-promises` | 允许显式 `void` 表达有意忽略，但调用方仍应确认内部错误收口 |
| TypeScript 抑制注释和显式 `any` | ESLint 已作为 error | 保留文本扫描作为轻量审计补充 |
| 浏览器存储异常、异步竞态、运行时 JSON 校验 | 通用 lint 只能提示局部模式 | 存储和竞态已通过测试修复；运行时 JSON 继续按边界风险逐步收紧 |

## 最小 ESLint 试运行配置

首批配置已经使用 ESLint flat config，并把扫描目标限定在项目自有代码。ESLint、TypeScript ESLint、`eslint-plugin-vue` 和 parser 都是直接开发依赖，不依赖锁文件中偶然出现的传递安装。

首批 error 规则包括：

- ESLint 推荐的基础正确性规则。
- `eslint-plugin-vue` 的 essential 规则。
- `vue/no-mutating-props`，启用 `shallowOnly`：禁止重写 prop，同时允许显式传入的 composable controller 修改内部 ref/form 状态。
- `vue/no-use-v-if-with-v-for`。
- `vue/require-v-for-key`。
- `vue/no-v-html`。
- `@typescript-eslint/no-explicit-any`。
- `@typescript-eslint/ban-ts-comment`。
- 类型感知的 `@typescript-eslint/no-floating-promises`，配置为允许显式 `void`。
- `@typescript-eslint/no-unused-vars`，统一允许 `_` 前缀表示有意忽略的参数或解构变量。
- `no-debugger`。
- `no-console`，仅允许 `warn` 和 `error`。

以下规则没有在第一批直接设为 error：

- `@typescript-eslint/no-non-null-assertion`：当前存在少量可证明的局部不变量，应先重构或记录例外。
- `@typescript-eslint/no-unsafe-*`：能够暴露 JSON 边界问题，但容易在 API 和测试代码中形成较大迁移面，应先以 warning 试运行并逐类收敛。
- 格式化、import 排序和风格偏好规则：不属于本阶段风险目标，批量启用会掩盖行为性问题并扩大 diff。

当前 lint 目标包括：

```text
src/features/**/*.{ts,vue}
src/composables/**/*.ts
src/lib/**/*.ts
src/router/**/*.ts
src/types.ts
src/types/**/*.ts
src/App.vue
src/main.ts
vite.config.ts
```

配置明确排除 `src/components/ui/**`、`src/components/ai-elements/**` 和 `src/types/openapi.ts`，测试文件保留在范围内。

首轮试运行得到 43 个命中，未使用 `--fix`，逐项审阅后的处理如下：

- 4 个异步调用补充显式 `void`。被调用函数已经在内部收口错误，因此只明确 fire-and-forget 意图，不改变运行行为。
- 2 个 `_` 前缀的有意忽略变量通过统一 `no-unused-vars` 约定处理。
- 37 个 composable controller 嵌套状态写入通过 `vue/no-mutating-props` 的 `shallowOnly` 模式处理；仍禁止直接重写 prop。

处理后 `npm run lint` 在项目自有范围零错误、零 warning。对三个排除目标做显式验证时，ESLint 均报告由 ignore pattern 排除。

## 门禁结论与迁移计划

`npm run lint` 已加入现有 Web Quality 的 `Tests and build` 实体 job，并在单元测试和 Chromium 安装前执行。workflow 仍由原有路径 detector 决定是否运行实体 job，required context 名称继续保持为 `Web quality gate`；纯文档变更仍走 `false/skipped` 的严格 gate 组合，不承担前端依赖安装成本。

建议按以下阶段推进：

1. 修复安全存储访问和路由上下文竞态，并补充确定性测试。该阶段已完成。
2. 引入只覆盖项目自有代码的最小 ESLint flat config，在本地试运行；不执行批量 `--fix`。该阶段已完成。
3. 对首轮结果逐项分类，修复真实问题，对生成层和合理模式使用目录级配置或最小规则选项。该阶段已完成。
4. 当首批规则在干净分支稳定通过后，把 `npm run lint` 加入现有 Web Quality 实体 job；保持 required context 名称 `Web quality gate` 不变。该阶段已完成。
5. 后续再评估 `no-unsafe-*`、无障碍和更严格 Vue 规则，每批单独迁移并验证，不把格式化债务与行为修复混在同一 PR。

当前路径已经修复基线确认的运行时风险，并由 Web Quality workflow 执行同一 `npm run lint`，让静态规则开始承担“防止回归”的职责，同时保持生成组件和上游 Renderer 的维护边界。后续规则增强应继续按第 5 阶段拆分为独立迁移，不在 CI 接入变更中扩展规则集。
