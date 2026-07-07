# PROJECT_CONTEXT

## 1. 项目目标

本项目是一个自动化资讯推送系统，目标是每天从可维护的 RSS 订阅源中抓取资讯，经过去重、质量过滤、排序和大模型总结后，生成中文结构化日报，并通过飞书机器人推送。

项目当前同时支持：

- 每日资讯日报：偏新闻精选和快速判断。
- 周末深度报告：围绕可配置主题做结构化综合分析，默认主题为“女性与个人成长”。
- HTML 阅读页：把日报和周报生成更适合阅读的衬线字体网页，再通过飞书卡片提供“阅读全文”按钮。

## 2. 已完成能力

### RSS 抓取与订阅源管理

- 使用 Python 实现 RSS 抓取。
- 订阅源不写死在代码或 `config.yaml` 中，统一维护在 `sources.yaml`。
- 支持两个订阅源分组：
  - `sources`：每日资讯源。
  - `weekly_report_sources`：周末深度报告主题源。
- 每个订阅源包含：
  - `id`
  - `name`
  - `url`
  - `category`
  - `language`
  - `enabled`
  - `weight`
  - `last_fetch_at`
- 每日任务只读取 `enabled: true` 的订阅源。
- 抓取成功后会更新对应订阅源的 `last_fetch_at`。

### 命令行管理能力

通过 `python -m daily_news sources ...` 管理订阅源：

- `list`：列出订阅源。
- `add`：添加订阅源。
- `delete`：删除订阅源。
- `edit`：编辑订阅源。
- `enable`：启用订阅源。
- `disable`：停用订阅源。
- `test`：测试某个订阅源能否正常抓取。

通过 `python -m daily_news ...` 执行任务：

- `run`：生成每日资讯日报。
- `weekly`：生成周末深度报告。
- `notify-daily`：推送最近一次日报 HTML 链接到飞书。
- `notify-weekly`：推送最近一次周报 HTML 链接到飞书。
- `notify-status`：推送 GitHub Actions 运行状态通知。

### 日报生成

- 抓取每条资讯的标题、来源、发布时间、链接、摘要。
- 对资讯进行 URL 去重。
- 按分类、质量分、订阅源权重、发布时间排序。
- 使用 DeepSeek API 生成结构化中文日报。
- 日报结构包括：
  - 今日重点
  - 行业动态
  - AI / 科技
  - 产品设计相关
  - 值得关注的信号
- 每个方向最多保留 4 条。
- 最终日报最多保留 16 条。
- 每条精选资讯保留原始链接。

### 高质量过滤规则

当前质量评分位于 `src/daily_news/quality.py`，规则包括：

- 优先：
  - 一手来源。
  - 机构来源。
  - 研究来源。
  - 深度报道、研究、报告、白皮书、调查、访谈等内容。
- 降权：
  - 营销软文。
  - 融资/商业通稿。
  - 标题党。
  - 转载/编译内容。
- 健康类内容会标注证据类型：
  - 医学机构
  - 研究论文
  - 政策报告
  - 媒体报道
  - 个人经验
- AI 类内容会标注内容类型：
  - 官方发布
  - 模型能力更新
  - 产品应用
  - 投融资/商业化
  - 风险与监管

### 周末深度报告

- 每周日生成一篇主题深度报告。
- 默认主题：女性与个人成长。
- 主题、关键词和候选源都可以在 `config.yaml` 中配置。
- 报告结构包括：
  - 本周关键变化
  - 重要数据/事件/报告
  - 判断趋势
  - 对个体、职场、健康、经济的影响概览
  - 值得继续关注的问题
  - 原文链接
- 周报不是碎片化新闻列表，而是基于一周材料做综合判断。

### HTML 阅读页

- 每日生成 HTML：`docs/daily/YYYY-MM-DD.html`。
- 每周生成 HTML：`docs/weekly/YYYY-Wxx.html`。
- 自动生成阅读首页：`docs/index.html`。
- HTML 使用传统书籍阅读感的衬线字体样式。
- 飞书卡片中提供“阅读全文”按钮，打开 GitHub Pages 上的 HTML 页面。
- 日报 HTML 默认保留最近 14 份。
- 周报 HTML 默认保留最近 8 份。

### 飞书推送

- 支持飞书 Webhook。
- 飞书推送使用 interactive card，不再只发送普通 Markdown 文本。
- 当前推送策略：
  - GitHub Actions 先生成 Markdown 和 HTML。
  - 提交 `docs` 到 GitHub。
  - 等待 60 秒，让 GitHub Pages 有时间发布。
  - 再推送飞书卡片。
- 飞书卡片包含：
  - 摘要正文。
  - “阅读全文”按钮。
  - GitHub Actions 运行日志按钮。
  - 失败时推送异常提醒。

### GitHub Actions 自动化

- 每日任务：`.github/workflows/daily-news.yml`
  - 北京时间 08:07 自动运行。
  - 北京时间 08:27 兜底运行。
  - 手动运行 `workflow_dispatch` 时，即使当天 HTML 已存在，也会重新生成、提交并推送飞书。
- 周报任务：`.github/workflows/weekly-deep-report.yml`
  - 每周日北京时间 20:07 自动运行。
  - 每周日北京时间 20:27 兜底运行。
- GitHub Actions 权限：
  - `contents: write`，用于把生成的 HTML 提交回仓库。

## 3. 当前文件结构

```text
daily-news-push/
├── .github/
│   └── workflows/
│       ├── daily-news.yml
│       └── weekly-deep-report.yml
├── docs/
│   ├── index.html
│   ├── daily/
│   │   ├── 2026-07-06.html
│   │   └── 2026-07-07.html
│   └── weekly/
│       └── 2026-W27.html
├── src/
│   └── daily_news/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── dedupe.py
│       ├── feishu.py
│       ├── html_report.py
│       ├── models.py
│       ├── quality.py
│       ├── report.py
│       ├── rss.py
│       ├── runner.py
│       ├── sources.py
│       ├── summarizer.py
│       └── weekly.py
├── config.yaml
├── PROJECT_CONTEXT.md
├── README.md
├── requirements.txt
└── sources.yaml
```

说明：

- `reports/`：本地或 Actions 运行时生成 Markdown 日报，通常不提交。
- `weekly_reports/`：本地或 Actions 运行时生成 Markdown 周报，通常不提交。
- `docs/`：GitHub Pages 发布目录，需要提交。

## 4. 关键配置

### `config.yaml`

关键配置项：

- `app.timezone`: 当前为 `Asia/Shanghai`。
- `app.max_items_per_source`: 每个 RSS 源最多抓取条数。
- `app.max_items_per_direction_group`: 每个方向最多保留条数，当前为 `4`。
- `app.max_items_total`: 日报总量上限，当前为 `16`。
- `app.fetch_timeout_seconds`: 抓取和推送超时时间。
- `llm.provider`: 当前为 `deepseek`。
- `llm.base_url`: 当前为 `https://api.deepseek.com`。
- `llm.api_key_env`: 当前为 `DEEPSEEK_API_KEY`。
- `llm.model`: 当前为 `deepseek-v4-flash`。
- `report.html_output_dir`: 当前为 `docs`。
- `report.site_base_url`: 当前为 `https://wangzianna.github.io/daily-news-push/`。
- `report.keep_html`: 日报 HTML 保留数量，当前为 `14`。
- `weekly_report.topic`: 周报主题，当前为 `女性与个人成长`。
- `weekly_report.keywords`: 周报主题筛选关键词。
- `weekly_report.keep_html`: 周报 HTML 保留数量，当前为 `8`。
- `feishu.enabled`: 是否启用飞书推送。

### GitHub Secrets

密钥必须通过 GitHub Secrets 管理，不允许提交到仓库。

当前需要配置：

- `DEEPSEEK_API_KEY`
- `FEISHU_WEBHOOK_URL`

### GitHub Pages

HTML 阅读页依赖 GitHub Pages。

仓库 Pages 应配置为：

- Branch: `main`
- Folder: `/docs`

否则飞书里的“阅读全文”链接会出现 404。

### `sources.yaml`

每日资讯源在 `sources` 下维护。

周末深度报告资讯源在 `weekly_report_sources` 下维护。

新增或修改订阅源时优先使用 CLI，避免手写 YAML 出现缩进或字段遗漏问题。

## 5. 当前待办

### 去重质量仍需增强

当前去重主要基于规范化 URL，标题仅作为兜底。已知问题：

- 不同媒体转载同一议题但 URL 不同，仍可能重复进入日报。
- 相同事件的多篇相似报道可能反复出现。
- 分类维度不是语义议题维度，因此“同一议题跨分类重复”目前无法有效拦截。

后续建议：

- 增加标题 + 摘要的语义/关键词级 topic dedupe。
- 在质量评分后做相似议题折叠，优先保留一手来源、机构来源、研究来源或权重更高的来源。
- 增加“同一主题最多保留 1 条，重大主题最多 2 条”的规则。

### 中国本土视角仍需增强

当前已加入部分中文来源，但筛选逻辑还没有系统性地偏好中国本土信号。

后续建议：

- 增加中国来源和中国议题的加权规则。
- 对 `language: zh`、中国机构域名、中国市场/监管/职场/消费等关键词给予适度加分。
- 在日报 prompt 中明确要求补充中国语境：对中国市场、监管、职场、消费、产品落地的影响。
- 如果材料不足，应明确写“本土信号不足”，不要编造。

### 周报手动运行逻辑可继续优化

日报工作流已支持手动运行时绕过“当天 HTML 已存在”的跳过逻辑。周报目前仍是“本周 HTML 已存在则跳过”。如果需要反复调试周报，也应给周报加入类似日报的 `workflow_dispatch` 绕过逻辑。

### HTML 排版可继续细化

当前 HTML 已改为衬线阅读版，但仍可继续优化：

- 移动端信息密度。
- 标题层级。
- 链接列表样式。
- 日报和周报是否需要不同版式。
- 是否需要生成更像文章排版的摘要，而不是 Markdown 结构直接转换。

### 订阅源可用性需要持续检查

部分 RSS 地址依赖第三方服务或网站自身 feed，可能不稳定。新增来源后应使用：

```bash
python -m daily_news sources test <source_id>
```

确认能抓取再提交。

## 6. 后续修改时必须遵守的规则

### 密钥与安全

- 不要把 API Key、Webhook、Token 写入代码、`config.yaml`、`sources.yaml`、README 或任何提交文件。
- 只通过 GitHub Secrets 或本地环境变量读取密钥。
- 本地运行时使用：

```bash
export DEEPSEEK_API_KEY="..."
export FEISHU_WEBHOOK_URL="..."
```

### 订阅源规则

- 不要把订阅源写死在 Python 代码里。
- 不要重新把订阅源迁回 `config.yaml`。
- 日常维护订阅源优先用 CLI。
- 每个订阅源必须包含完整字段。
- 每日抓取必须只读取 `enabled: true` 的来源。

### 输出与保留规则

- Markdown 报告输出到 `reports/` 或 `weekly_reports/`，默认不作为长期归档提交。
- HTML 报告输出到 `docs/daily/` 和 `docs/weekly/`，用于 GitHub Pages，需要提交。
- 必须保留自动清理逻辑，避免 HTML 越积越多。
- 修改 HTML 路径或站点路径时，必须同步检查：
  - `config.yaml` 的 `site_base_url`
  - `src/daily_news/runner.py` 的 URL 拼接逻辑
  - `.github/workflows/*.yml` 的 artifact 和 commit 路径
  - GitHub Pages 设置

### 飞书推送规则

- 飞书应优先推送结构化卡片和“阅读全文”链接，不要退回纯 Markdown 长文本。
- 如果 Actions 生成 HTML 后马上推送飞书，应保留等待时间，避免 Pages 尚未发布导致 404。
- 失败通知要保留运行日志链接，方便排查。

### LLM 规则

- 当前使用 DeepSeek 的 OpenAI-compatible API，通过 `openai` Python SDK 调用。
- 修改模型提供商或模型名时，优先只改 `config.yaml`，不要把模型参数散落到代码里。
- Prompt 必须要求“不编造未出现在资讯中的事实”。
- 健康类内容必须保留证据类型标注。
- AI 类内容必须保留内容类型标注。

### GitHub Actions 规则

- 定时任务使用 UTC cron，但注释必须写明对应北京时间。
- 不建议使用整点第 0 分钟触发，GitHub Actions 容易延迟或丢任务。
- 每日任务当前目标是北京时间 8 点后推送，保留 08:27 兜底。
- 修改 workflow 后必须检查手动运行和定时运行两种路径。

### 代码修改规则

- 保持 Python 标准库 + 当前依赖优先，不要轻易引入重依赖。
- 如果新增依赖，必须更新 `requirements.txt` 和 README。
- 修改核心逻辑后至少运行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/daily-news-pycache python3 -m compileall src
PYTHONPATH=src python3 -m daily_news --help
python3 -c "import yaml; yaml.safe_load(open('sources.yaml', encoding='utf-8')); print('sources.yaml ok')"
```

- 不要删除用户新增的订阅源。
- 不要回滚不属于当前任务的改动。

### 当前远端仓库

GitHub 远端：

```text
git@github.com:wangzianna/daily-news-push.git
```

本地项目目录：

```text
/Users/apple/sandbox/daily-news-push
```
