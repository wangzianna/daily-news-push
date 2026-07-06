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
2. 每个部分使用 3-6 条要点，优先写判断和影响，不要只复述标题。
3. 重要结论后可以用括号标注来源名称。
4. 不要编造未出现在资讯中的事实。
5. 保持精炼，适合通过飞书机器人推送。

资讯列表：
{items_as_context(items, timezone_name)}
"""


def fallback_summary(items: list[NewsItem], api_key_env: str = "DEEPSEEK_API_KEY") -> str:
    top_items = items[:8]
    lines = [
        "## 今日重点",
        *[f"- {item.title}（{item.source}）" for item in top_items[:5]],
        "",
        "## 行业动态",
        *[f"- {item.title}：{item.summary[:120]}" for item in items if item.category in {"商业", "行业"}][:5],
        "",
        "## AI / 科技",
        *[f"- {item.title}：{item.summary[:120]}" for item in items if item.category in {"AI", "技术", "科技"}][:5],
        "",
        "## 产品设计相关",
        *[f"- {item.title}：{item.summary[:120]}" for item in items if item.category in {"产品", "设计"}][:5],
        "",
        "## 值得关注的信号",
        f"- 未配置 {api_key_env}，已生成基础版摘要。建议配置大模型 API 以获得趋势判断。",
    ]
    return "\n".join(lines)
