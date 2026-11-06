# Product Hunt｜潜界 AI 每日产品机会研究

[gamehack/producthunt](https://github.com/gamehack/producthunt) 是一个独立开源项目，只负责 Product Hunt 官方数据采集、AI 产品筛选、创业机会评分、证据研究、中文文章生成，以及向 Notion「08 · 潜界 AI｜产品猎人日报」交付经过完整回读验证的 READY 原稿。

**本项目由 GitHub Actions 执行，不部署到硅谷服务器。** 不需要常驻服务器、Docker、systemd 或服务器定时任务。

**它不是发布器。** 微信公众号和 CMS 草稿由独立的 [qjai-text-publisher](https://github.com/gamehack/qjai-text-publisher) 从 Notion 读取；本项目不含渠道 API、渠道凭证或渠道发送状态。

## 自动化数据流

`GitHub Actions（每天 09:00 UTC / 17:00 北京时间）`
→ `Product Hunt 官方 GraphQL API Top 20`
→ `AI 相关性筛选`
→ `创业机会评分`
→ `一方证据收集`
→ `中文文章生成`
→ `Notion 08 日期子页面`
→ `全文回读`
→ `SHA-256 READY 标记`

GitHub Actions 使用 GitHub-hosted runner 执行一次性任务。Runner 结束后自动销毁；同一 Product Hunt 日期的 SQLite 检查点和本地文章通过 GitHub Actions Cache 保留，以便同一天失败重试时续跑。失败时会尝试保存 7 天的恢复文件 artifact。不会将数据库或文章提交到 Git 仓库。

### 内容口径

- 每天获取最近一个已完成的 `America/Los_Angeles` 自然日快照；不以服务器日期代替 Product Hunt 日期。
- 只调用 Product Hunt 官方 API，不抓取 Product Hunt 页面。
- 厂商网站仅在 HTTPS、DNS/IP 公网校验、robots.txt 和响应大小限制均通过时读取；拒绝重定向。
- 区分 Product Hunt 上架自述、厂商官网自述与独立事实。未证实的定价、收入、客户数、转化率和市场份额必须标注未知，不得编造。
- AI 初筛分为核心 AI、AI 增强、AI 生态、非 AI 和不确定。机会评分由市场需求、变现可能、小团队可行性、AI 杠杆和差异化构成。
- 默认机会分数阈值为 60、研究数量上限为 5：超过阈值的产品多于 5 个时研究全部超过阈值者，否则研究总分前 5 名。
- 文章标题不带栏目名前缀，UTF-8 长度不超过 64 字节；正文来源链接必须来自已收集证据。

## Notion READY 合约

- 唯一允许写入的父页面：08 · 潜界 AI｜产品猎人日报
- Notion page ID：`4109e605-ccf8-81c4-accd-c19386b4a38d`
- 每日唯一键：`producthunt:YYYY-MM-DD`
- 日期子页标题：`YYYY-MM-DD｜文章标题`
- 写入时保存 Product Hunt 快照日期、原始标题、摘要、正文、研究来源及来源归因。
- 写入后验证父页面、标题、完整 Markdown 回读、无截断/未知块/警告；正文一致后才追加：
  `QJAI_PUBLISH_READY v=1 source_key=producthunt:YYYY-MM-DD content_sha256=<sha256>`
- 再次回读并验证 READY 行、source_key 和正文 SHA-256。任何步骤失败都使本期任务失败。
- 同周期已有页面时只读检查 READY 与正文哈希：有效则返回 `duplicate_ready`；缺失或被人工修改则报错并要求人工核对。绝不覆盖已有文章，也不把不完整页面冒充 READY。
- Notion 08 页面之外的目标 ID 会在发送请求前被拒绝。

## 渠道交付时序

| 北京时间 | 职责 | 项目 |
|---|---|---|
| 每日 17:00 | Product Hunt 采集、AI 研究、文章生成、Notion READY | GitHub Actions / 本仓库 |
| 每日 18:30 | 读取 Notion READY，分别创建微信和 CMS 草稿 | `qjai-text-publisher` |
| 每日 20:30 | 统一文章资产索引，仅维护索引和元数据 | ChatGPT 定时任务 |

本仓库没有公众号自动群发能力，也不会调用 CMS 写入接口。Notion READY 是下游发布器的唯一输入。

## GitHub Actions 配置

生产任务位于 `.github/workflows/daily.yml`：

- 定时：`0 9 * * *`（UTC），即北京时间每天 17:00。
- 手动触发：GitHub 仓库 → **Actions** → **Product Hunt Daily** → **Run workflow**。可填写 `snapshot_date`（Product Hunt 洛杉矶日期）；留空则使用最近一个已完成日期。
- 并发控制：同一仓库同一时刻只运行一个生产任务，不会因手动触发而取消正在运行的任务。
- 切换保护：定时任务默认关闭，只有 Repository Variable `PRODUCTHUNT_PRODUCTION_ENABLED=true` 才会执行；手动 `workflow_dispatch` 不受该开关影响，便于在旧项目仍运行时使用历史日期做联调。
- 超时：90 分钟。
- 最小权限：`contents: read`。
- 同日期重试：使用 GitHub Actions Cache 恢复 SQLite 检查点和文章文件。
- 失败恢复：尝试上传该日期的 JSON/Markdown artifact，保留 7 天。

GitHub 的 schedule 是 UTC 时区，可能因平台负载稍有延迟；17:00 是目标触发时间，不是严格实时 SLA。

### 必须配置的 Actions Secrets

进入 GitHub 仓库 **Settings → Secrets and variables → Actions → New repository secret**，配置：

| Secret 名称 | 内容 |
|---|---|
| `PRODUCT_HUNT_TOKEN` | Product Hunt 官方 API token |
| `PRODUCT_HUNT_COMMERCIAL_AUTHORIZED` | 必须为字符串 `true`，明确确认商业使用授权 |
| `OMNIROUTE_BASE_URL` | OmniRoute 的 OpenAI-compatible API Base URL |
| `OMNIROUTE_API_KEY` | OmniRoute API Key |
| `NOTION_API_KEY` | Notion Integration Secret，需有 08 页面读取和插入权限 |

Repository Variables：

| Variable 名称 | 默认值 |
|---|---|
| `PRODUCTHUNT_PRODUCTION_ENABLED` | 默认不设置或 `false`；完成新旧项目切换后再设置为 `true` |

生产模型固定使用已验证的 OmniRoute 路由 ID：`minimax-cn/MiniMax-M3`。不再从 Repository Variables 读取模型名，避免错误别名被覆盖。

**重要：** GitHub-hosted runner 不在你的 Docker 网络内。因此 `OMNIROUTE_BASE_URL` 必须是 runner 可通过公网 HTTPS 访问的地址；不能填写 `localhost`、Docker service 名称或仅服务器内网可达的地址。应继续使用强认证、TLS 和必要的访问控制，不要为了 Actions 而开放无认证 API。若现有 OmniRoute 只监听内网，需要先解决安全的外部 API 连通性，再启用定时任务。

Notion 父页面 ID 固定在 workflow 中，并由程序再次校验；生产任务强制开启 `NOTION_ENABLE_SYNC` 和 `NOTION_AUTOSYNC_AFTER_GENERATION`。密钥只放 GitHub Actions Secrets，不写入代码、日志或 artifact。

### 新旧项目切换顺序

1. 先配置 Secrets，保持 `PRODUCTHUNT_PRODUCTION_ENABLED` 为 `false` 或未设置，避免新旧两个 17:00 任务同时运行。
2. 在 Actions 手动触发 `snapshot_date=2026-10-30`，完成真实 Product Hunt API → OmniRoute → Notion READY 联调；该历史日期不会与旧项目当天的日报冲突。
3. 通过现有 `qjai-text-publisher` 对该日期执行只读 dry-run，确认能读取新项目写入的 READY 和 SHA-256；不发送微信/CMS 草稿。
4. 只有前三项验收通过后，停用旧 `qjai-intelligence` 的 17:00 定时器并删除旧项目；保留独立的 `qjai-text-publisher` 18:30 任务。
5. 最后将 GitHub Repository Variable `PRODUCTHUNT_PRODUCTION_ENABLED` 设置为 `true`，新项目从下一个 17:00 时段开始正式定时运行。

这一步只退役旧项目，不在服务器部署新项目。

## 配置与本地开发

复制 `.env.example` 为本地 `.env` 可进行人工调试。默认 Notion 写入开关为关闭，避免本地测试误写生产 Notion。

~~~bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
~~~

离线 CI 只运行单元测试，不访问真实 Product Hunt、OmniRoute 或 Notion。

## 本地生产命令

~~~bash
# 最近一个已完成的洛杉矶自然日
producthunt run

# 指定 Product Hunt 日期；会真实写入 Notion 08，谨慎使用
producthunt run --date 2026-11-05

# 仅在有明确恢复需求时，使用本地已校验产物补写 Notion
producthunt sync-notion --date 2026-11-05
~~~

生产 CLI 只接受官方 Product Hunt 来源，不提供 fixture/demo 运行入口。

## 恢复与幂等

- Notion 创建结果不明确时，下一次只读检查稳定日期前缀；若已有页面必须验证 READY 与哈希，不能盲目重试 POST。
- GitHub Actions Cache 按 Product Hunt 日期隔离，不复用其他日期或旧项目的 SQLite 检查点。
- 失败 workflow 会尝试保存恢复 artifact。下载后可在受控本地环境恢复 `output/YYYY-MM-DD/`，再运行 `sync-notion --date YYYY-MM-DD`；恢复前必须确认 JSON 与 Markdown 完全一致。
- 若 Notion 已创建不完整页面，程序会 fail closed，不会覆盖或擅自补 READY；必须人工核对并处理。

## 安全边界

- 不提交密钥、真实文章正文、数据库、模型请求日志或 Notion token。
- 不在本项目中加入微信/CMS 客户端或凭证。
- 外部产品数据和网页内容均为不可信输入，不能覆盖系统提示或触发工具。
- 不抓取 Product Hunt 网站；不绕过 robots.txt、登录或访问限制。
- OmniRoute 访问必须使用 HTTPS 与强认证；GitHub Actions Secrets 不得通过 echo 或调试日志输出。
- 不因一次 Notion 网络超时自动重试 POST；先核对是否已经创建页面。
