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

`datus-web` 目前没有直接声明 ESLint 依赖，也没有 `lint` 脚本。现有质量检查包括：

| 检查 | 当前能力 | 主要边界 |
| --- | --- | --- |
| `npm run build` | 先运行 `vue-tsc -b`，再构建生产资源 | 能发现类型、未使用局部变量/参数和构建集成问题；不能完整检查 Promise 使用、Vue 模板语义和生命周期策略 |
| `npm test` | 运行 Vitest 单元测试 | 覆盖业务工具、composable、API 适配和部分路由/安全契约；不是通用静态规则 |
| `npm run test:browser` | 编译并运行 Playwright 浏览器测试 | 覆盖真实浏览器中的 Renderer 集成；不扫描全部业务组件 |
| `npm run lint:typography` | 扫描 `src/features/` 和 `src/App.vue` 的字号 utility | 是窄范围设计规范检查，不替代 Vue/TypeScript lint |
| Web Quality workflow | 对相关前端变更依次运行以上测试、字号检查和构建 | 当前没有执行 ESLint |

应用 TypeScript 配置已经启用：

- `strict`
- `noUnusedLocals`
- `noUnusedParameters`
- `noFallthroughCasesInSwitch`
- `noUncheckedSideEffectImports`

`tsconfig.app.json` 的实际文件集合包含 `src/**/*.ts`、`src/**/*.tsx` 和 `src/**/*.vue`，因此项目自有代码、测试以及生成组件都在 Vue TypeScript 检查范围内。`vite.config.ts` 由 `tsconfig.node.json` 单独覆盖，浏览器测试由 `tsconfig.browser.json` 覆盖。

本次基线验证结果：

- Vue TypeScript project build 通过。
- 51 个 Vitest 文件、442 项单元测试通过。
- 4 项 Chromium Renderer 浏览器测试通过。
- Typography 扫描通过；两处 `text-base` 是现有规则要求人工确认的例外，不是失败。
- 生产构建通过。

## 代码规模和所有权边界

本次统计只计算 `.vue` 和 `.ts` 文件：

| 范围 | Vue 文件 | TypeScript 文件 | 其中测试文件 | 合计行数 |
| --- | ---: | ---: | ---: | ---: |
| `features`、`composables`、`lib`、`router` | 52 | 124 | 51 | 42,123 |
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

## 已确认的风险

### 中风险：浏览器存储异常可能破坏启动或交互

相关位置：

- `datus-web/src/composables/useTheme.ts`
- `datus-web/src/composables/useChatSettings.ts`
- `datus-web/src/composables/useConnection.ts`

`localStorage` 在禁用持久化、受限 iframe、隐私策略或存储配额异常时可能抛出异常。当前主题模块在模块初始化期间直接读取并写入 `localStorage`；该异常可能阻止应用启动。聊天设置和 API 地址的部分写入也没有失败降级。

此外，`useChatSettings.ts` 将 `JSON.parse` 的结果直接作为设置对象使用，没有验证字段类型。损坏、手工修改或旧版本遗留的数据可能把非字符串/非布尔值带入响应式状态。

建议先提供小型安全存储 helper：读取失败回退默认值、写入失败只放弃持久化，并对反序列化结果做字段级校验。修复应补充存储读取异常、写入异常和错误数据形状测试。

### 中风险：异步路由上下文可能发生旧结果覆盖新状态

相关位置：`datus-web/src/features/workspace/useWorkspaceRouting.ts`。

`applyRouteWorkspaceContext()` 会先读取 datasource/database/schema 快照，再等待数据源切换，最后写入 database 和 schema。路由查询参数在等待期间再次变化时，多个调用可以并发执行；较早调用可能在较晚调用之后恢复并写回旧快照。现有 route-state 单元测试验证了查询参数解析和替换，但没有覆盖这种异步竞态。

建议引入单调递增的请求代号或 watcher cleanup/invalidation，只允许最新一次上下文应用写入状态，并增加“第一次切换延迟、第二次切换先完成”的确定性测试。

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
| Vue 模板合法性、props 变更、`v-for` key | 目前主要依赖审阅和编译 | 由 `eslint-plugin-vue` 稳定覆盖 |
| 未显式处理的 Promise | TypeScript 不完整覆盖 | 使用类型感知的 `no-floating-promises`，允许显式 `void` |
| TypeScript 抑制注释和显式 `any` | 当前靠规范和文本扫描 | 用 ESLint 防止回归 |
| 浏览器存储异常、异步竞态、运行时 JSON 校验 | 通用 lint 只能提示局部模式 | 需要小范围实现修复和确定性测试 |

## 建议的最小 ESLint 规则

首批配置应使用 ESLint flat config，并把扫描目标限定在项目自有代码。建议直接依赖 ESLint、TypeScript ESLint 和 `eslint-plugin-vue`，不要依赖锁文件中由其他包偶然带入的 parser。

首批 error 规则建议包括：

- ESLint 推荐的基础正确性规则。
- `eslint-plugin-vue` 的 essential 规则。
- `vue/no-mutating-props`。
- `vue/no-use-v-if-with-v-for`。
- `vue/require-v-for-key`。
- `vue/no-v-html`。
- `@typescript-eslint/no-explicit-any`。
- `@typescript-eslint/ban-ts-comment`。
- 类型感知的 `@typescript-eslint/no-floating-promises`，配置为允许显式 `void`。
- `no-debugger`。
- `no-console`，仅允许 `warn` 和 `error`。

以下规则不建议在第一批直接设为 error：

- `@typescript-eslint/no-non-null-assertion`：当前存在少量可证明的局部不变量，应先重构或记录例外。
- `@typescript-eslint/no-unsafe-*`：能够暴露 JSON 边界问题，但容易在 API 和测试代码中形成较大迁移面，应先以 warning 试运行并逐类收敛。
- 格式化、import 排序和风格偏好规则：不属于本阶段风险目标，批量启用会掩盖行为性问题并扩大 diff。

建议 lint 目标至少包括：

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

初期应排除 `src/components/ui/**`、`src/components/ai-elements/**` 和 `src/types/openapi.ts`。测试文件可以保留在范围内，但允许针对 mock 和 fixture 设置最小、明确的 overrides。

## 门禁结论与迁移计划

目前不建议立即把 ESLint 加入 required Web quality gate。原因不是现有代码错误很多，而是规则依赖和配置尚不存在，且已确认的两个主要风险需要测试与实现修复，不能由 lint 自动解决。

建议按以下阶段推进：

1. 修复安全存储访问和路由上下文竞态，并补充确定性测试。
2. 引入只覆盖项目自有代码的最小 ESLint flat config，在本地和 CI 中试运行；不执行批量 `--fix`。
3. 对首轮结果逐项分类，修复真实问题，对生成层、测试 fixture 和合理模式使用目录级配置或最小例外。
4. 当首批规则在干净分支稳定通过后，把 `npm run lint` 加入现有 Web Quality 实体 job；保持 required context 名称 `Web quality gate` 不变。
5. 后续再评估 `no-unsafe-*`、无障碍和更严格 Vue 规则，每批单独迁移并验证，不把格式化债务与行为修复混在同一 PR。

这一路径可以先解决已知运行时风险，再让静态规则承担“防止回归”的职责，同时保持生成组件和上游 Renderer 的维护边界。
