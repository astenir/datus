# Web chatbot 用户指南

## 概览

Datus Web chatbot 提供一个易用的网页界面，用于与 Datus AI 助手交互。它通过 FastAPI 服务端托管 React 前端组件（`@datus/web-chatbot`），面向自然语言转 SQL 的场景，用户无需掌握命令行即可完成对话式分析。

## 快速开始

### 启动网页界面

**指定数据源**：
```bash
datus --web --datasource <your_datasource>
```

**使用自定义配置**：
```bash
datus --web --config path/to/agent.yml --datasource snowflake
```

**自定义端口与主机**：
```bash
datus --web --port 8080 --host 0.0.0.0
```

浏览器将自动打开 `http://localhost:8501`（或你指定的端口）。

![Web Chatbot Interface](../assets/web_chatbot_interface.png)

## 核心功能

### 1. 交互式对话界面

**自然语言提问**：

直接输入问题，AI 会生成并执行 SQL。

**示例**：
```
Show me total revenue by product category for the last month
```

助手将会：

1. 理解你的问题
2. 生成相应的 SQL 查询
3. 以语法高亮的形式展示 SQL
4. 给出 AI 的解释说明

### 2. Subagent 支持

在网页界面中直接访问面向不同任务的专用 subagent。

**可用 subagent**：

可用列表来自内置 subagent 以及当前数据库下 `agent.agentic_nodes` 中定义的自定义条目。常见示例包括：

- `gen_sql`
- `gen_report`
- `gen_semantic_model`
- `gen_metrics`
- `gen_dashboard`
- `scheduler`

**使用方式**：

1. 打开主聊天页面
2. 切换到需要的 subagent
3. 与专用助手对话

**直达 URL**：

你可以收藏 subagent 的 URL 便于快速访问：

```
http://localhost:8501/?subagent=gen_metrics
http://localhost:8501/?subagent=gen_semantic_model
http://localhost:8501/?subagent=finance_report
```

也可以通过 CLI 直接启动到某个 subagent：

```bash
datus --web --datasource production --subagent finance_report
```

### 3. 会话管理

**查看会话历史**：

侧边栏显示最近的会话信息，包括：

- 会话名称
- 创建时间

**加载历史会话**：

1. 在侧边栏找到目标会话
2. 点击对应的会话名称
3. 即可进入会话详情，查看历史消息或者你可以继续进行对话

**会话分享**：

每个会话都有唯一可分享的链接：

```
http://localhost:8501?session=abc123def456...
```

### 4. 成功案例归档（Success Story）

**标记有效查询**：

当 AI 生成的 SQL 工作良好时：

1. 先审阅生成的 SQL
2. 点击 "Save to success story" 按钮
3. 后端从该次 `execute_sql` / `read_query` 的会话历史中恢复真实数据源
4. 查询会保存到 `{agent.home}/benchmark/{datasource}/{subagent}/success_story.csv`

页面 URL 或当前选择的数据源不会决定保存目录。例如一次 SQL 实际在 `ccks_fund` 上执行，即使页面当前显示
`datus_enterprise`，仍会保存到 `{agent.home}/benchmark/ccks_fund/{subagent}/success_story.csv`。如果历史中没有明确的
数据源，或开始/完成事件记录的数据源冲突，保存会失败，不会回退到默认数据源。

保存根目录由当前配置的 `agent.home` 决定；可以在 `agent.yml` 中设置 `agent.home`，或用 `--config` 选择另一份配置。

![Save Generated SQL](../assets/geneated_sql_save.png)

**CSV 格式**：

```csv
question,sql,datasource_id,source_id,session_id,session_link,subagent_name,timestamp
"Show revenue by category",SELECT ...,ccks_fund,ss_...,abc123...,http://localhost:8501?session=...,chat,2025-01-15T02:30:00Z
```

返回给前端的是相对于 benchmark 目录的 `storage_key`（例如
`ccks_fund/chat/success_story.csv`），不会暴露服务器绝对路径。

旧版 CSV 不会被自动移动或删除。确认旧文件中的所有记录都属于同一个数据源后，可以显式复制迁移：

```bash
datus-agent migrate-success-stories \
  --source ~/.datus/benchmark/chat/success_story.csv \
  --datasource ccks_fund \
  --subagent chat
```

迁移按 `source_id` 去重，可以重复执行；源文件保持不变。如果新版 CSV 已声明其他 `datasource_id`，迁移会被拒绝。
这些文件可以作为 semantic model 或 metrics 知识库构建的 `success_story` 输入；新格式文件的数据源必须与构建请求的
`datasource_id` 一致。

## 总结

Datus Web chatbot 提供：

- **易用的界面**：无需命令行知识
- **Subagent 直达**：按任务启用专用助手
- **会话管理**：保存、加载与分享对话
- **成功归档**：标记并收集有效查询
- **一键分享**：复制会话链接
- **可视化执行**：逐步展示 SQL 生成过程
- **多数据源支持**：便捷切换数据库
