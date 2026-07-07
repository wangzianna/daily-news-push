from __future__ import annotations

import os

from openai import OpenAI

from .models import NewsItem
from .report import REPORT_SECTIONS, items_as_context


def generate_daily_summary(
    items: list[NewsItem],
    api_key_env: str,
    base_url: str | None,
    model: str,
    temperature: float,
    timezone_name: str,
) -> str:
    if not items:
        return "\n".join([f"## {section}\n暂无可用资讯。" for section in REPORT_SECTIONS])

    api_key = os.environ.get(api_key_env)
    if not api_key:
        return fallback_summary(items, api_key_env)

    client = OpenAI(api_key=api_key, base_url=base_url)
    prompt = build_prompt(items, timezone_name)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": "你是专业的行业资讯分析师，擅长从 RSS 资讯中生成结构化中文日报。",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or fallback_summary(items, api_key_env)


def build_prompt(items: list[NewsItem], timezone_name: str) -> str:
    sections = "\n".join(f"- {section}" for section in REPORT_SECTIONS)
    return f"""请根据以下资讯生成一份中文结构化日报。

要求：
1. 必须包含以下五个二级标题：
{sections}
2. 每个部分最多 3 条要点，优先写判断和影响，不要只复述标题。
3. 重要结论后可以用括号标注来源名称。
4. 健康类内容必须注明证据类型；AI 类内容必须注明内容类型。
5. 不要编造未出现在资讯中的事实。
6. 保持精炼，适合通过飞书机器人推送。
7. 不要输出原始资讯清单，原始链接会由系统在下方单独展示。
8. 每条资讯会同时给出"摘要"（RSS 原文）和"全文"（从正文抓到的前 1200 字）。
   撰写时优先以"全文"为依据，只在"全文"为空时退回到"摘要"，
   并在结论后括号注明该条仅有摘要、未获取到全文。
9. 不要凭单句标题做推测，必须以资讯中能看到的文字为依据。

资讯列表：
{items_as_context(items, timezone_name)}
"""


def fallback_summary(items: list[NewsItem], api_key_env: str = "DEEPSEEK_API_KEY") -> str:
    top_items = items[:8]
    lines = [
        "## 今日重点",
        *[f"- {item.title}（{item.source}）" for item in top_items[:3]],
        "",
        "## 行业动态",
        *[f"- {item.title}：{item.summary[:120]}" for item in items if item.category in {"商业", "行业"}][:3],
        "",
        "## AI / 科技",
        *[
            f"- {item.title}（{item.ai_type or '未分类'}）：{item.summary[:120]}"
            for item in items
            if item.category in {"AI", "技术", "科技"}
        ][:3],
        "",
        "## 产品设计相关",
        *[f"- {item.title}：{item.summary[:120]}" for item in items if item.category in {"产品", "设计"}][:3],
        "",
        "## 值得关注的信号",
        f"- 未配置 {api_key_env}，已生成基础版摘要。建议配置大模型 API 以获得趋势判断。",
    ]
    return "\n".join(lines)


def translate_items(
    items: list[NewsItem],
    api_key_env: str,
    base_url: str | None,
    model: str,
    temperature: float,
) -> None:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        return

    english_items = [
        (index, item)
        for index, item in enumerate(items)
        if item.language == "en" or _is_english(item.title)
    ]
    if not english_items:
        return

    context_lines = [
        f"[{index}] TITLE: {item.title}\nSUMMARY: {item.summary or '无'}"
        for index, item in english_items
    ]
    prompt = f"""将以下英文资讯的标题和摘要翻译成中文。

翻译要求：
1. 标题翻译要准确、自然、简洁，适合日报阅读。
2. 摘要翻译要保留关键信息和数据，语句通顺。
3. 公司名、产品名、人名可以保留英文原文（如 OpenAI、GPT-5、Sam Altman）。
4. 专有名词和术语保持准确（如 HBM、benchmark、agent 等）。
5. 不要添加原文没有的信息，不要改写原意。

请严格按以下 JSON 格式输出，不要输出任何其他内容：
[{{"index": 序号, "title_zh": "中文标题", "summary_zh": "中文摘要"}}]

资讯列表：
{chr(10).join(context_lines)}
"""

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业的中英翻译，擅长将英文资讯准确自然地翻译成中文。请严格按 JSON 格式输出。",
                },
                {"role": "user", "content": prompt},
            ],
        )
        _apply_translations(items, english_items, response.choices[0].message.content or "")
    except Exception as exc:
        print(f"翻译失败，保留英文原文: {exc}")


def _apply_translations(
    items: list[NewsItem],
    english_items: list[tuple[int, NewsItem]],
    response_text: str,
) -> None:
    import json

    text = response_text.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start < 0 or end <= start:
        return
    try:
        translations = json.loads(text[start:end])
    except json.JSONDecodeError:
        return

    translation_map = {entry["index"]: entry for entry in translations if isinstance(entry, dict)}
    for index, item in english_items:
        entry = translation_map.get(index)
        if not entry:
            continue
        if entry.get("title_zh"):
            item.title = entry["title_zh"].strip()
        if entry.get("summary_zh"):
            item.summary = entry["summary_zh"].strip()


def _is_english(text: str) -> bool:
    if not text:
        return False
    chinese = sum(1 for c in text if "一" <= c <= "鿿")
    return chinese / len(text) < 0.05
