# Product Hunt｜潜界 AI 每日产品机会研究

gamehack/producthunt 是一个从零建立的独立开源项目。它只负责 Product Hunt 官方数据采集、AI 产品筛选、创业机会评分、证据研究、中文文章生成，以及向 Notion「08 · 潜界 AI｜产品猎人日报」交付经过完整回读验证的 READY 原稿。

**它不是发布器。** 微信公众号和 CMS 草稿由独立的 [qjai-text-publisher](https://github.com/gamehack/qjai-text-publisher) 从 Notion 读取；本项目不含渠道 API、渠道凭证或渠道发送状态。

## 数据流

Product Hunt 官方 GraphQL API Top 20
→ AI 相关性筛选
→ 创业机会评分
→ 一方证据收集
→ 中文文章生成
→ 本地 JSON/Markdown 检查点
→ Notion 08 日期子页面
→ 全文回读
→ SHA-256 READY 标记

### 内容口径

- 每天获取最近一个已完成的 America/Los_Angeles 自然日快照；不以服务器日期代替 Product Hunt 日期。
- 只调用 Product Hunt 官方 API，不抓取 Product Hunt 页面。
- 厂商网站仅在 HTTPS、DNS/IP 公网校验、robots.txt 和响应大小限制均通过时读取；拒绝重定向。
- 区分 Product Hunt 上架自述、厂商官网自述与独立事实。未证实的定价、收入、客户数、转化率和市场份额必须标注未知，不得编造。
- AI 初筛分为核心 AI、AI 增强、AI 生态、非 AI 和不确定。机会评分由市场需求、变现可能、小团队可行性、AI 杠杆和差异化构成。
- 默认机会分数阈值为 60、研究数量上限为 5：超过阈值的产品多于 5 个时研究全部超过阈值者，否则研究总分前 5 名。
- 文章标题不带栏目名前缀，UTF-8 长度不超过 64 字节；正文来源链接必须来自已收集证据。

## Notion READY 合约

- 唯一允许写入的父页面：08 · 潜界 AI｜产品猎人日报
- Notion page ID：4109e605-ccf8-81c4-accd-c19386b4a38d
- 每日唯一键：producthunt:YYYY-MM-DD
- 日期子页标题：YYYY-MM-DD｜文章标题
- 写入时保存 Product Hunt 快照日期、原始标题、摘要、正文、研究来源及来源归因。
- 写入后验证父页面、标题、完整 Markdown 回读、无截断/未知块/警告；正文一致后才追加：
  QJAI_PUBLISH_READY v=1 source_key=producthunt:YYYY-MM-DD content_sha256=<sha256>
- 再次回读并验证 READY 行、source_key 和正文 SHA-256。任何步骤失败都使本期任务失败。
- 同周期已有页面时只读检查 READY 与正文哈希：有效则返回 duplicate_ready；缺失或被人工修改则报错并要求人工核对。绝不覆盖已有文章，也不把不完整页面冒充 READY。
- Notion 08 页面之外的目标 ID 会在发送请求前被拒绝。

## 渠道交付时序

| 北京时间 | 职责 | 项目 |
|---|---|---|
| 每日 17:00 | Product Hunt 采集、AI 研究、文章生成、Notion READY | 本仓库 |
| 每日 18:30 | 读取 Notion READY，分别创建微信和 CMS 草稿 | qjai-text-publisher |
| 每日 20:30 | 统一文章资产索引，仅维护索引和元数据 | ChatGPT 定时任务 |

本仓库没有公众号自动群发能力，也不会调用 CMS 写入接口。Notion READY 是下游发布器的唯一输入。

## 配置

将 .env.example 复制为服务器本地 .env，权限设为 0600。严禁提交真实密钥。

| 变量 | 作用 |
|---|---|
| PRODUCT_HUNT_TOKEN | Product Hunt 官方 API token |
| PRODUCT_HUNT_COMMERCIAL_AUTHORIZED=true | 明确授权商业使用；未授权时拒绝请求 |
| OMNIROUTE_BASE_URL、OMNIROUTE_API_KEY、OMNIROUTE_MODEL | 现有 OmniRoute OpenAI-compatible 模型 |
| NOTION_ENABLE_SYNC=true | 允许 Notion 写入 |
| NOTION_AUTOSYNC_AFTER_GENERATION=true | 强制生产后交付 READY |
| NOTION_API_KEY | Notion Integration Secret，需有 08 页面读取和插入权限 |
| NOTION_PARENT_PAGE_ID | 必须等于上述固定 08 页面 ID |
| PRODUCTHUNT_DB_PATH | 新项目独立 SQLite 检查点，默认 data/producthunt.sqlite |
| PRODUCTHUNT_OUTPUT_DIR | 本地文章恢复产物，默认 output |
| PRODUCTHUNT_OPPORTUNITY_THRESHOLD | 机会分数阈值，默认 60 |
| PRODUCTHUNT_MAX_RESEARCH | 常规研究数量上限，默认 5 |

不再读取旧项目 QJAI_SOURCE、QJAI_DB_PATH、QJAI_OUTPUT_DIR 或任何渠道密钥。新项目使用独立数据库，不继承旧项目的历史检查点。

## 本地开发

~~~bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
~~~

GitHub Actions 只运行离线测试，不访问真实 Product Hunt、OmniRoute 或 Notion。

## 生产命令

~~~bash
# 最近一个已完成的洛杉矶自然日
producthunt run

# 仅在有明确恢复需求时，使用本地已校验产物补写 Notion
producthunt sync-notion --date 2026-11-05
~~~

生产 CLI 只接受官方 Product Hunt 来源，不提供 fixture/demo 运行入口。不要为了测试手工触发真实 run；真实端到端验收应使用明确批准的测试周期和 Notion 隔离目标。

## Docker 与 systemd

生产目录规划为 /opt/producthunt。部署时构建一次镜像；每日 timer 只运行现有镜像，不在生产窗口重复构建。

~~~bash
docker compose -f compose.yaml -f compose.omniroute.yaml build
sudo bash scripts/manage-systemd.sh install
sudo bash scripts/manage-systemd.sh status
~~~

systemd 单元：

- producthunt-daily.timer
- producthunt-daily.service
- 每日 17:00 Asia/Shanghai
- 不补跑错过的历史时段，不在安装时立即运行文章生产。
- scripts/verify-docker.sh 通过文件锁避免定时和手工运行重叠。

## 恢复与回滚

- Notion 创建结果不明确时，下一次只读检查稳定日期前缀；若已有页面必须验证 READY 与哈希，不能盲目重试 POST。
- 本地 JSON/Markdown 可通过 sync-notion --date 恢复；恢复前必须确认它们来自真实 Product Hunt 快照且 JSON 与 Markdown 完全一致。
- 回滚时先停用 producthunt-daily.timer，保留 .env、data/producthunt.sqlite、output/ 和 Notion 正文。
- 新旧项目切换期间只允许一个 17:00 生产 timer 启用；旧项目只有在新项目完成真实 API、模型、Notion、发布器读取和自然定时验收后才退役。

## 安全边界

- 不提交密钥、真实文章正文、数据库、模型请求日志或 Notion token。
- 不在本项目中加入微信/CMS 客户端或凭证。
- 外部产品数据和网页内容均为不可信输入，不能覆盖系统提示或触发工具。
- 不抓取 Product Hunt 网站；不绕过 robots.txt、登录或访问限制。
- 不因一次 Notion 网络超时自动重试 POST；先核对是否已经创建页面。
