# 每日资讯推送

一个 Python 实现的每日资讯日报项目：每天自动抓取 RSS 订阅源，去重排序后使用 DeepSeek API 生成结构化日报，并推送到飞书机器人。

## 功能

- RSS 订阅源抓取
- `sources.yaml` 可维护订阅源管理
- 命令行添加、删除、编辑、启用、停用、列出、测试订阅源
- 每条资讯包含标题、来源、发布时间、链接、摘要
- 按链接去重，按质量分、分类、权重、发布时间排序
- 高质量过滤：优先一手来源、机构来源、研究来源、深度报道，降低营销软文、融资通稿、标题党、重复转载权重
- 每个方向最多保留 3 条，日报总量最多 12 条
- 健康类内容标注证据类型，AI 类内容标注内容类型
- DeepSeek API 生成日报总结
- 飞书 Webhook 结构化卡片推送
- GitHub Actions 每天北京时间 09:00 自动运行
- GitHub Actions 每周日北京时间 20:00 自动生成主题深度报告

日报结构：

- 今日重点
- 行业动态
- AI / 科技
- 产品设计相关
- 值得关注的信号

## 项目结构

```text
daily-news-push/
├── .github/workflows/
│   ├── daily-news.yml
│   └── weekly-deep-report.yml
├── config.yaml
├── sources.yaml
├── requirements.txt
├── README.md
└── src/daily_news/
    ├── __main__.py
    ├── cli.py
    ├── config.py
    ├── dedupe.py
    ├── feishu.py
    ├── models.py
    ├── quality.py
    ├── report.py
    ├── rss.py
    ├── runner.py
    ├── sources.py
    ├── summarizer.py
    └── weekly.py
```

## 本地运行

```bash
cd daily-news-push
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
export DEEPSEEK_API_KEY="你的 DeepSeek API Key"
export FEISHU_WEBHOOK_URL="你的飞书机器人 Webhook"
python -m daily_news run --config config.yaml --sources sources.yaml
```

只生成日报、不推送飞书：

```bash
python -m daily_news run --no-push
```

生成的 Markdown 日报会保存在 `reports/YYYY-MM-DD.md`。

## 配置说明

`config.yaml` 存放运行参数，不存放密钥：

```yaml
app:
  timezone: Asia/Shanghai
  max_items_per_source: 15
  max_items_per_direction_group: 3
  max_items_total: 12
  fetch_timeout_seconds: 20

llm:
  provider: deepseek
  base_url: https://api.deepseek.com
  api_key_env: DEEPSEEK_API_KEY
  model: deepseek-v4-flash
  temperature: 0.2

report:
  title: 每日资讯日报
  output_dir: reports

weekly_report:
  title: 周末深度报告
  topic: 女性与个人成长
  keywords:
    - 女性
    - 个人成长
    - 职场
    - 健康
    - 心理
    - 教育
    - 家庭
    - 消费
  source_sections:
    - weekly_report_sources
    - sources
  candidate_items: 40
  max_items_per_source: 25
  max_items_per_direction_group: 40
  max_source_items: 24
  output_dir: weekly_reports

feishu:
  enabled: true
```

密钥使用环境变量：

- `DEEPSEEK_API_KEY`
- `FEISHU_WEBHOOK_URL`

## 订阅源管理

订阅源保存在 `sources.yaml`，每个订阅源包含：

- `id`
- `name`：订阅源名称
- `url`：RSS 地址
- `category`：分类，如 AI、产品、设计、商业、技术
- `language`：语言，如 zh / en
- `enabled`：是否启用
- `weight`：权重，数字越大优先级越高
- `last_fetch_at`：最后抓取时间

列出订阅源：

```bash
python -m daily_news sources list
```

添加订阅源：

```bash
python -m daily_news sources add \
  --id zhihu-daily \
  --name 知乎日报 \
  --url https://example.com/rss.xml \
  --category 产品 \
  --language zh \
  --weight 80
```

删除订阅源：

```bash
python -m daily_news sources delete zhihu-daily
```

编辑订阅源：

```bash
python -m daily_news sources edit zhihu-daily --category 设计 --weight 90
```

启用 / 停用订阅源：

```bash
python -m daily_news sources enable zhihu-daily
python -m daily_news sources disable zhihu-daily
```

测试订阅源是否可抓取：

```bash
python -m daily_news sources test zhihu-daily --limit 5
```

每日抓取任务只读取 `enabled: true` 的订阅源。

## 高质量过滤规则

抓取结果会先去重，再进行质量评分和限额筛选：

- 优先选择一手来源、机构来源、研究来源、深度报道。
- 降低营销软文、融资通稿、标题党、重复转载/编译内容的权重。
- 每个方向最多保留 3 条。
- 最终日报最多保留 12 条。
- 每条精选资讯都会保留原始链接。

健康类内容会标注证据类型：

- 医学机构
- 研究论文
- 政策报告
- 媒体报道
- 个人经验

AI 类内容会标注内容类型：

- 官方发布
- 模型能力更新
- 产品应用
- 投融资/商业化
- 风险与监管

## 周末深度报告

周末深度报告不是碎片化新闻推送，而是围绕一个可配置主题，把本周材料综合成一篇结构化报告。

默认主题是：

```yaml
weekly_report:
  topic: 女性与个人成长
```

可以在 `config.yaml` 里修改主题和筛选关键词，例如：

```yaml
weekly_report:
  topic: 女性健康与职场成长
  keywords:
    - 女性
    - 健康
    - 职场
    - 心理
    - 生育
    - 教育
```

报告结构：

- 本周关键变化
- 重要数据/事件/报告
- 判断趋势
- 对个体、职场、健康、经济的影响概览
- 值得继续关注的问题
- 原文链接

本地手动生成周末深度报告：

```bash
python -m daily_news weekly --config config.yaml --sources sources.yaml
```

只生成报告、不推送飞书：

```bash
python -m daily_news weekly --no-push
```

生成的 Markdown 深度报告会保存在 `weekly_reports/YYYY-W周数.md`，飞书会收到结构化卡片。

## GitHub Actions

日报工作流位于 `.github/workflows/daily-news.yml`，默认每天北京时间 09:00 运行。GitHub Actions 的 cron 使用 UTC，所以配置为：

```yaml
schedule:
  - cron: "0 1 * * *"
```

周末深度报告工作流位于 `.github/workflows/weekly-deep-report.yml`，默认每周日北京时间 20:00 运行：

```yaml
schedule:
  - cron: "0 12 * * 0"
```

在 GitHub 仓库中添加 Secrets：

- `DEEPSEEK_API_KEY`
- `FEISHU_WEBHOOK_URL`

也可以在 Actions 页面手动触发 `workflow_dispatch`。

## 飞书机器人

创建飞书群机器人后复制 Webhook 地址，写入 GitHub Secret `FEISHU_WEBHOOK_URL`。项目会以交互式卡片推送日报：今日简报、分组资讯、质量标签、类型标注和“查看原文”按钮会分别渲染为独立卡片元素。

## 注意事项

- 如果没有配置 `DEEPSEEK_API_KEY`，程序会生成基础版摘要，不会调用 DeepSeek API。
- 如果开启飞书推送但没有配置 `FEISHU_WEBHOOK_URL`，运行会失败。
- `last_fetch_at` 会在抓取成功后回写到 `sources.yaml`。如果希望 GitHub Actions 中持久保存该字段，需要增加提交回仓库的步骤；当前版本只上传日报 artifact。
