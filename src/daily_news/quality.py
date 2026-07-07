from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlsplit

from .models import NewsItem


CREDIBILITY_SCORES = {
    "primary": 35,
    "research": 35,
    "institution": 30,
    "media": 0,
}

CREDIBILITY_LABELS = {
    "primary": "一手来源",
    "research": "研究来源",
    "institution": "机构来源",
    "media": None,
}

DEPTH_KEYWORDS = (
    "研究",
    "报告",
    "白皮书",
    "调查",
    "深度",
    "复盘",
    "访谈",
    "analysis",
    "research",
    "report",
    "paper",
    "survey",
    "interview",
)

# 正面信号：数据驱动、原创调查、独家报道
DATA_KEYWORDS = (
    "数据",
    "统计",
    "报告",
    "指数",
    "调研",
    "data",
    "statistics",
    "index",
    "report",
    "survey",
)

EXCLUSIVE_KEYWORDS = (
    "独家",
    "首发",
    "调查",
    "深度报道",
    "exclusive",
    "investigation",
    "scoop",
)

# 企业公关稿：信息密度低，但不同于营销推广
PR_KEYWORDS = (
    "宣布",
    "发布",
    "推出",
    "announce",
    "launch",
    "introduce",
    " unveil",
)

MARKETING_KEYWORDS = (
    "限时",
    "福利",
    "重磅优惠",
    "免费领取",
    "报名",
    "课程",
    "训练营",
    "招商",
    "广告",
    "赞助",
    "sponsored",
    "webinar",
)

CLICKBAIT_PATTERNS = (
    r"震惊",
    r"炸裂",
    r"彻底变天",
    r"一文看懂",
    r"必看",
    r"火了",
    r"刷屏",
    r"不得不看",
    r"you won't believe",
    r"what happened next",
)

REPOST_KEYWORDS = ("转载", "转自", "编译", "来源：", "via ", "repost")

# AI 内容分类：投融资/商业化关键词（仅用于分类，不降权）
AI_FINANCING_KEYWORDS = (
    "融资",
    "获投",
    "投资",
    "估值",
    "a轮",
    "b轮",
    "c轮",
    "series a",
    "series b",
    "funding",
    "raises",
    "商业化",
    "收入",
    "营收",
    "订阅",
)

HEALTH_CATEGORIES = {"健康", "医疗", "医学", "生命科学", "health", "medical", "medicine"}
AI_CATEGORIES = {"AI", "人工智能", "科技", "技术", "ai", "technology", "tech"}


def apply_quality_rules(
    items: list[NewsItem],
    max_per_direction: int = 4,
    max_total: int = 16,
) -> list[NewsItem]:
    scored = [score_item(item) for item in items]
    grouped: dict[str, list[NewsItem]] = defaultdict(list)
    for item in scored:
        grouped[item.category].append(item)

    limited: list[NewsItem] = []
    for category in sorted(grouped):
        category_items = sorted(grouped[category], key=quality_sort_key)
        limited.extend(category_items[:max_per_direction])

    return sorted(limited, key=quality_sort_key)[:max_total]


def score_item(item: NewsItem) -> NewsItem:
    text = f"{item.title} {item.summary}".lower()
    domain = normalize_domain(item.link)
    labels: list[str] = []
    penalties: list[str] = []
    score = item.weight

    # 正面信号：来源可信度（基于 YAML 声明）
    credibility_score = CREDIBILITY_SCORES.get(item.credibility, 0)
    score += credibility_score
    credibility_label = CREDIBILITY_LABELS.get(item.credibility)
    if credibility_label:
        labels.append(credibility_label)

    # 正面信号：内容深度
    if contains_any(text, DEPTH_KEYWORDS):
        score += 20
        labels.append("深度内容")
    if contains_any(text, DATA_KEYWORDS):
        score += 10
        labels.append("数据驱动")
    if contains_any(text, EXCLUSIVE_KEYWORDS):
        score += 15
        labels.append("原创/独家")

    # 负面信号：内容质量
    if contains_any(text, MARKETING_KEYWORDS):
        score -= 35
        penalties.append("营销软文")
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in CLICKBAIT_PATTERNS):
        score -= 25
        penalties.append("标题党")
    if contains_any(text, REPOST_KEYWORDS):
        score -= 20
        penalties.append("转载/编译")
    if contains_any(text, PR_KEYWORDS):
        score -= 5
        penalties.append("公关稿")

    item.quality_score = score
    item.quality_labels = labels or ["常规资讯"]
    item.penalty_labels = penalties
    item.evidence_type = classify_health_evidence(item, domain, text)
    item.ai_type = classify_ai_type(item, domain, text)

    if item.published_at:
        now = datetime.now(item.published_at.tzinfo) if item.published_at.tzinfo else datetime.now()
        hours_old = (now - item.published_at).total_seconds() / 3600
        if hours_old <= 24:
            item.quality_score += 8
        elif hours_old <= 48:
            item.quality_score += 3
        elif hours_old > 72:
            item.quality_score -= 5
        if hours_old > 168:
            item.quality_score -= 20

    return item


def quality_sort_key(item: NewsItem) -> tuple[int, int, float]:
    return (
        -item.quality_score,
        -item.weight,
        -(item.published_at.timestamp() if item.published_at else 0),
    )


def classify_health_evidence(item: NewsItem, domain: str, text: str) -> str | None:
    category = item.category.lower()
    if category not in HEALTH_CATEGORIES and not contains_any(text, HEALTH_CATEGORIES):
        return None
    if item.credibility == "institution":
        return "医学机构"
    if item.credibility == "research" or contains_any(text, ("论文", "临床试验", "study", "trial", "journal")):
        return "研究论文"
    if contains_any(text, ("政策", "指南", "监管", "报告", "policy", "guideline")):
        return "政策报告"
    if contains_any(text, ("我", "亲历", "经验", "分享", "个人", "my experience")):
        return "个人经验"
    return "媒体报道"


def classify_ai_type(item: NewsItem, domain: str, text: str) -> str | None:
    category = item.category.lower()
    if category not in AI_CATEGORIES and not contains_any(text, AI_CATEGORIES):
        return None
    if item.credibility == "primary" or contains_any(text, ("发布", "上线", "release", "announces", "introduces")):
        return "官方发布"
    if contains_any(text, ("模型", "benchmark", "推理", "多模态", "上下文", "能力", "model")):
        return "模型能力更新"
    if contains_any(text, ("产品", "应用", "agent", "copilot", "workflow", "工具")):
        return "产品应用"
    if contains_any(text, AI_FINANCING_KEYWORDS):
        return "投融资/商业化"
    if contains_any(text, ("风险", "安全", "监管", "版权", "隐私", "合规", "regulation", "risk", "safety")):
        return "风险与监管"
    return "产品应用"


def normalize_domain(url: str) -> str:
    domain = urlsplit(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def contains_any(text: str, keywords: tuple[str, ...] | set[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)
