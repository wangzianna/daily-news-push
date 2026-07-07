# Daily News Push 全面提升计划

> 最后更新：2026-07-07  
> 状态：规划中 / 部分已实施

---

## 一、已完成的优化

### 1. 中文新闻源可见性修复
- **问题**：财新等中文源抓取成功但不出现在日报中
- **根因**：
  - `rsshub.app` 返回 403，改用 `rsshub.rssforever.com`
  - 质量评分偏向英文域名（一手来源白名单全是英文）
- **改动**：
  - `sources.yaml`：更新财新 URL，禁用失效的 finance/market 源
  - `quality.py`：`PRIMARY_SOURCE_DOMAINS` 加入 `36kr.com`, `caixin.com`
- **验证**：本地跑 `python -m daily_news run --no-push`，确认中文条目入选

### 2. 日报容量扩容
- **问题**：精选资讯 12 条太少，覆盖度不够
- **改动**：`config.yaml`
  - `max_items_per_direction_group`: 3 → 4
  - `max_items_total`: 12 → 16
- **影响**：`quality.py:apply_quality_rules` 默认值同步更新

### 3. 跨天去重
- **问题**：同一条新闻连续多天出现在日报中
- **方案**：解析前一天 HTML 报告，提取已发布的链接和标题，过滤掉重复项
- **改动**：
  - `report.py:load_published()`：解析 HTML，用正则提取 `<a href="...">` 和 `<strong>N. title</strong>` + `来源：source`
  - `runner.py:exclude_published()`：调用 `load_published()`，过滤 `items`
- **正则**：
  ```python
  _LINK_RE = re.compile(r'href="(https?://[^"]+)"')
  _ITEM_TITLE_RE = re.compile(r"<strong>\d+[.、]\s*([^<]+)</strong>")
  _SOURCE_META_RE = re.compile(r"来源：([^｜<]+)")
  ```
- **注意**：HTML 实体解码用 `html.unescape`，标题数字前缀不进入 capture group

### 4. 精选资讯渲染修复
- **问题**：精选资讯中所有条目挤在一起，没有分段
- **根因**：`html_report.py:markdown_to_book_html()` 只处理 `## ` 和 `# `，不处理 `### ` 和 `> `
- **改动**：
  - 支持 `### ` → `<h3>`（带 accent 色样式）
  - 支持 `> ` → `<blockquote>`（去掉深色背景，改为 accent 左边框）
- **验证**：`docs/daily/*.html` 每条资讯独立成块，标题 + 元信息 + 摘要 + 链接

### 5. 英文资讯翻译
- **问题**：精选资讯中英文标题/摘要没有翻译成中文
- **方案**：调用 DeepSeek 批量翻译英文条目
- **改动**：
  - `models.py`：`NewsItem` 增加 `language: str = "en"` 字段
  - `rss.py`：构造 `NewsItem` 时传入 `language=source.language`
  - `summarizer.py:translate_items()`：检测 `language=="en"` 或中文字符占比 <5% 的条目，发 JSON prompt 批量翻译 title + summary
  - `runner.py`：在 `apply_quality_rules` 之后、`generate_daily_summary` 之前调用
- **注意**：翻译失败时保留英文原文，不中断流程

### 6. 质量评分机制重设计
- **问题**：融资新闻和营销软文放在同一类降权，不合理
- **根因**：原始实现把 `FINANCING_KEYWORDS` 和 `MARKETING_KEYWORDS` 混在一起
- **方案**：从第一性原理重新设计评分体系
- **改动**：`quality.py` 完全重写
  - **正面信号**：
    - 来源可信度：一手来源（+35）、机构来源（+30）、研究来源（+35）
    - 内容深度：深度内容（+20）、原创/独家（+15）、数据驱动（+10）
  - **负面信号**：
    - 营销软文（-35）、标题党（-25）、转载/编译（-20）、公关稿（-5）
  - **分类（不降权）**：
    - `AI_FINANCING_KEYWORDS`：仅用于分类"投融资/商业化"，不影响评分
  - **新增关键词组**：
    - `DATA_KEYWORDS`：数据、统计、报告、指数、调研、data、statistics、index、report、survey
    - `EXCLUSIVE_KEYWORDS`：独家、首发、调查、深度报道、exclusive、investigation、scoop
    - `PR_KEYWORDS`：宣布、发布、推出、announce、launch、introduce、unveil
    - `AI_FINANCING_KEYWORDS`：融资、获投、投资、估值、a轮、b轮、c轮、series a/b、funding、raises、商业化、收入、营收、订阅
- **验证**：测试融资新闻得分不降，营销软文仍然降权

### 7. 全文抓取增强 LLM 上下文
- **问题**：RSS 摘要太薄，LLM 基于单句标题做推测，信息失真
- **方案**：抓取正文前 1200 字，作为 LLM 上下文
- **改动**：
  - `models.py`：`NewsItem` 增加 `full_text: str = ""`
  - `content.py`：新模块
    - `_ArticleTextExtractor(HTMLParser)`：跳过 script/style/nav/header/footer/aside，保留正文段落
    - `fetch_full_text(url)`：requests + HTMLParser 抽取纯文本
    - `extract_text_from_html(html)`：兜底方案
    - `enrich_items_with_full_text(items, max_length=1200)`：批量抓取，写入 `item.full_text`
  - `report.py:items_as_context()`：同时输出 `摘要` 和 `全文` 两列
  - `summarizer.py:build_prompt()`：指令 LLM 优先以"全文"为依据，仅在"全文"为空时用"摘要"，并标注"仅有摘要、未获取到全文"
  - `weekly.py:build_deep_report_prompt()`：同上
  - `runner.py`：在 `translate_items` 之后、`generate_daily_summary` 之前调用 `enrich_items_with_full_text`
- **配置**：`config.yaml` 可加 `full_text_max_length: 1200`（默认值）
- **验证**：HN 抓 3 篇，2 篇正文正常（600 字），1 篇招聘页只有 9 字 → fallback 标注

---

## 二、待实施的优化

### 8. 并发抓取 + trafilatura 替换
- **问题**：
  - RSS 抓取串行：20 源 × 20s 超时 = 最坏 400s
  - 全文抓取串行：16 条 × 10s 超时 = 最坏 160s
  - 全文抽取算法太朴素：IEEE 抓到"IEEE.org IEEE Xplore IEEE Standards IEEE Job Site More"这种导航残渣
- **方案**：
  1. **依赖**：`pip install trafilatura`
  2. **`rss.py`**：
     - 模块级 `requests.Session()` + `HTTPAdapter` 带 `urllib3.Retry(total=2, backoff_factor=0.5, status_forcelist=[429,502,503,504])`
     - `fetch_all_sources` 改用 `ThreadPoolExecutor(max_workers=8)`
     - `fetch_source` 用 `_session.get(...)` 替代 `requests.get(...)`
  3. **`content.py`**：
     - `fetch_full_text` 改用 `trafilatura.fetch_url(url)` + `trafilatura.extract(html, include_comments=False, include_tables=False, deduplicate=True, favor_precision=True)`
     - 失败时回退到现有 `extract_text_from_html`
     - `enrich_items_with_full_text` 改用 `ThreadPoolExecutor(max_workers=6)` + `per_domain_limit=2`（用 `collections.defaultdict(threading.Semaphore)`）
     - 超时从 10s 降到 8s
- **预期收益**：整条 pipeline 从 5-8 分钟压到 90 秒内；全文有效字数从 200-400 提到 800-1500

### 9. 合并翻译 + 摘要调用
- **问题**：`translate_items` 和 `generate_daily_summary` 各走一次 DeepSeek，token 消耗翻倍
- **方案**：
  - **方案 A（推荐）**：删除 `translate_items`，让 summary prompt 直接接受多语言输入，指令 LLM 在生成中文日报时"就地翻译"英文内容
    - `items_as_context` 保持英文原文
    - `build_prompt` 加指令："资讯可能混合中英文。生成日报时把英文内容直接翻译成中文表述，公司名/产品名/术语保留英文（OpenAI, GPT-5, HBM, benchmark 等）。"
  - **方案 B**：保留 `translate_items` 但只翻译标题（不翻摘要），token 消耗降低 ~80%
- **预期收益**：API 调用从 2 次/天 → 1 次/天；成本降低 10-50%

### 10. 跨源聚合 + 时间衰减
- **问题**：
  - The Verge 和 36kr 同一天报同一事件，会出现两条
  - 3 天前的 arxiv 论文分数高，会一直卡在第一（虽然跨天 dedup 能挡，但 dedup 只挡上一天）
- **方案**：
  1. **新文件 `cluster.py`**：
     - 依赖：`pip install rapidfuzz`
     - `cluster_by_title(items, threshold=80)`：按 `item.language` 分桶，用 `rapidfuzz.fuzz.token_set_ratio` 做贪心聚类
     - `pick_representative(cluster)`：选 `quality_score` 最高的作为代表，其他丢弃；或合并 source 名字做"多方报道"标记
  2. **`quality.py` 改动**：
     - `score_item` 末尾加 recency decay：
       ```python
       if item.published_at:
           hours_old = (now - item.published_at).total_seconds() / 3600
           if hours_old <= 24: score += 8
           elif hours_old <= 48: score += 3
           elif hours_old > 72: score -= 5
           if hours_old > 168: score -= 20  # 一周前的基本淘汰
       ```
  3. **`runner.py` 改动**：
     - pipeline 顺序：`dedupe_items` (URL 精确) → `apply_quality_rules`（内含 recency + cluster）→ `exclude_published` → `translate/enrich` → summary
- **预期收益**：报告不再重复；旧新闻自动淘汰

### 11. 中文源扩充
- **问题**：17+ 英文源 vs 3 个中文源（还禁用了 1 个），中国 AI/产品/经济一手信息基本抓不到
- **方案**：`sources.yaml` 追加 8 个中文源
  ```yaml
  - id: jiqizhixin_zh
    name: 机器之心
    url: https://www.jiqizhixin.com/rss
    category: ai
    language: zh
    enabled: true
    weight: 9

  - id: qbitai_zh
    name: 量子位
    url: https://www.qbitai.com/feed
    category: ai
    language: zh
    enabled: true
    weight: 8

  - id: geekpark_zh
    name: 极客公园
    url: https://www.geekpark.net/rss
    category: product_tech
    language: zh
    enabled: true
    weight: 7

  - id: huxiu_zh
    name: 虎嗅网
    url: https://www.huxiu.com/rss/0.xml
    category: economy
    language: zh
    enabled: true
    weight: 8

  - id: sspai_zh
    name: 少数派
    url: https://sspai.com/feed
    category: product_tech
    language: zh
    enabled: true
    weight: 6

  - id: bytedance_tech_zh
    name: 字节跳动技术团队
    url: https://rsshub.rssforever.com/juejin/user/307518987381192/original-posts
    category: ai
    language: zh
    enabled: true
    weight: 8

  - id: infoq_cn
    name: InfoQ 中文
    url: https://feed.infoq.cn/
    category: product_tech
    language: zh
    enabled: true
    weight: 7

  - id: chinaz_ai
    name: 站长之家 - AI
    url: https://rsshub.rssforever.com/chinaz/ainews
    category: ai
    language: zh
    enabled: true
    weight: 6
  ```
- **验证**：每个源单独跑 `python -m daily_news sources test <id> --limit 3`，RSS 失效的立即 `enabled: false`

### 12. 一手来源白名单移到 YAML
- **问题**：`quality.py:PRIMARY_SOURCE_DOMAINS` 是硬编码常量，加个源就要改代码
- **方案**：
  - `sources.yaml` 每个源加字段 `credibility: primary|research|institution|media`
  - `models.py:Source` 增加 `credibility: str = "media"`
  - `quality.py:score_item` 读取 `item.source_credibility` 而不是查 domain 集合
- **预期收益**：调优时改 YAML 不用改代码；"是谁"和"值多少分"绑在一起

### 13. 错误阈值告警
- **问题**：单条源失败会静默进 errors dict，但没有告警阈值。rsshub 挂了一周，只能通过报告变薄察觉
- **方案**：
  - `runner.py`：判断错误率 >30% 或者关键源（weight ≥ 9）全挂 → 单独走一次 Feishu 告警
  - `sources.yaml`：记录 `consecutive_failures` 字段，连续失败 3 天自动 disable 并告警
- **实现**：`SourceStore` 增加 `increment_failure_count(source_id)` 和 `reset_failure_count(source_id)`

### 14. dry-run / 调试模式
- **问题**：每次要看质量评分效果，必须完整跑一遍
- **方案**：
  - `cli.py` 增加 `daily-news debug --input reports/2026-07-06.md --show-scores`：只走评分和排序，输出每条的 score/labels/penalties
  - `daily-news debug --source openai_news`：只抓一个源，打印原始摘要+全文抽取结果+评分

### 15. LLM token 计数
- **问题**：完全不知道每天烧多少 token
- **方案**：
  - `summarizer.py`：从 `response.usage` 拿 `prompt_tokens / completion_tokens`
  - 写进 `reports/{date}.md` 尾部（或者单独 `metrics/` 目录）
- **用途**：回答"上下文加了全文，成本涨了多少"这种问题

### 16. Pipeline 抽象
- **问题**：`runner.py` 里 daily / weekly 两条 pipeline 重复度高（200 行）
- **方案**：
  - 抽一个 `Pipeline` 类，配置驱动（每步是否启用、参数）
  - 以后加"月度报告"、"事件专题"直接组配置

### 17. 状态和配置分离
- **问题**：`sources.yaml` 里记 `last_fetch_at`，每次跑都改，git 冲突频繁（已经中招 3 次）
- **方案**：
  - `sources.yaml` 只放静态配置进 git
  - `.state/sources.json` 放动态状态（`last_fetch_at`、`consecutive_failures`）走 `.gitignore` 或单独分支
  - 或者放到 GitHub Actions 的 cache 里，跨 run 恢复

---

## 三、建议实施顺序

按 ROI 排序：

1. **并发抓取 + trafilatura 替换**（#8）→ 1-2 小时，立刻提速 + 质量提升
2. **合并翻译 + 摘要调用**（#9）→ 30 分钟，省一半 API 成本
3. **跨源聚合 + 时间衰减**（#10）→ 1 小时，报告不再重复
4. **中文源扩充**（#11）→ 30 分钟改 YAML，覆盖度直接翻倍
5. **状态和配置分离**（#17）→ 30 分钟，少踩 git 冲突
6. **一手来源白名单移到 YAML**（#12）→ 30 分钟，调优更方便
7. **错误阈值告警**（#13）→ 1 小时，源挂了一周能立刻察觉
8. **dry-run / 调试模式**（#14）→ 1 小时，开发调试更方便
9. **LLM token 计数**（#15）→ 30 分钟，成本透明
10. **Pipeline 抽象**（#16）→ 2-3 小时，长期维护更干净

前 5 项做完，日报质量和成本都能明显换代。

---

## 四、技术栈依赖

当前依赖：
```
feedparser
requests
PyYAML
openai
```

新增依赖（按实施顺序）：
```
trafilatura          # #8 正文抽取
rapidfuzz            # #10 跨源聚合
```

---

## 五、验证清单

每次实施后跑以下检查：

1. **本地端到端**：
   ```bash
   python -m daily_news run --no-push
   ls reports/
   ls docs/daily/
   ```
   确认生成了 markdown 和 HTML，HTML 能正常打开

2. **质量评分检查**：
   - 中文源（财新、36kr）是否入选？
   - 营销软文是否被降权？
   - 融资新闻是否被保留？

3. **跨天去重检查**：
   - 连续两天跑 `run --no-push`，第二天的报告是否和第一天完全不同？

4. **全文抽取检查**：
   - 随机挑 3 条精选资讯，HTML 报告里的"全文"字段是否有意义？
   - 有没有抓到导航残渣？

5. **翻译检查**：
   - 英文资讯的标题和摘要是否翻译成中文？
   - 翻译失败时是否保留英文原文？

6. **性能检查**：
   - 整条 pipeline 耗时多少秒？（目标 < 2 分钟）
   - DeepSeek API 调用几次？token 消耗多少？

7. **Git 冲突检查**：
   - `git pull` 是否有冲突？
   - `sources.yaml` 是否被 GitHub Actions 自动修改？

---

## 六、风险与回退

### 风险 1：trafilatura 抓取失败率高
- **回退**：保留现有 `extract_text_from_html` 作为 fallback
- **监控**：记录 trafo 成功率，低于 50% 时告警

### 风险 2：并发抓取被封 IP
- **缓解**：`per_domain_limit=2` 控制单域名并发
- **回退**：降回串行抓取

### 风险 3：中文源 RSS 失效
- **缓解**：每个源加 `enabled` 字段，失效的立即 disable
- **监控**：连续 3 天抓取失败自动 disable

### 风险 4：合并翻译后 LLM 输出质量下降
- **回退**：恢复 `translate_items` 单独调用
- **监控**：人工抽查 10 天日报，对比翻译质量

---

## 七、后续扩展方向

1. **事件专题报告**：比如"OpenAI 发布会专题"，聚合过去 7 天所有相关报道
2. **月度深度分析**：基于过去 30 天的日报，生成趋势报告
3. **多语言支持**：现在只翻译英文到中文，未来可能需要支持日文、韩文
4. **用户画像**：根据阅读偏好调整推荐权重
5. **反馈闭环**：飞书机器人收集"有用/无用"反馈，用于优化质量评分

---

**下一步**：从 #8（并发抓取 + trafilatura）开始实施。
