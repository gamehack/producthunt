# Product Hunt｜潜界 AI 每日产品机会研究

一个独立、开源、可长期运行的内容生产项目。只负责 Product Hunt 数据采集、AI 产品筛选、商业机会研究、中文文章生成，以及将最终文章写入 Notion「08 · 潜界 AI｜产品猎人日报」并完成 READY 校验。

**本项目不负责微信公众号或 CMS 发布。** 所有渠道草稿由独立的 [qjai-text-publisher](https://github.com/gamehack/qjai-text-publisher) 从 Notion 读取。

## 唯一生产链路

`Product Hunt 官方 API Top 20` → `AI 相关性筛选` → `创业机会评分` → `证据收集` → `中文研究文章` → `Notion 08 日期子页面` → `全文回读与 SHA-256 校验` → `QJAI_PUBLISH_READY`

- Product Hunt 快照日期使用 `America/Los_Angeles`，生产定时使用北京时间每天 17:00。
- 只读取 Product Hunt 官方 API；不抓取 Product Hunt 页面。
- 厂商网站仅在 HTTPS、robots.txt 允许、DNS/IP 安全校验通过时读取。
- AI 推断与厂商自述、Product Hunt 上架信息明确区分；不编造收入、客户数、定价或商业效果。
- Notion 是唯一权威原稿。写入或回读失败即生产失败。
- 日期唯一键为 `producthunt:YYYY-MM-DD`。已存在的文章只读核验，不覆盖、不重复创建。
- 只有正文完整回读一致并通过 READY 哈希校验，发布器才可读取。

## 渠道发布

每天北京时间 18:30，由 `qjai-text-publisher` 读取 Notion 08 的 READY 文章，分别创建微信公众号草稿和 CMS 草稿。本文仓库不持有微信/CMS 凭证、不实现渠道 API、不自动公开发布。

## 开发与部署

- Python 3.12、OpenAI Agents SDK、Pydantic、HTTPX、SQLite。
- 模型通过现有 OmniRoute OpenAI-compatible endpoint 调用。
- 所有密钥仅放服务器私有 `.env`，权限 0600。
- GitHub Actions 只执行离线单元测试，不访问真实 Product Hunt、模型或 Notion。
- 生产由 systemd timer 调用一次性 Docker 容器；部署与代码修改职责分离。

生产配置、命令、部署和恢复流程将在实现完成后补齐。
