"""
Multi-agent coordination for investment Q&A.

Inspired by require_analys&user_responed.py LangGraph flow:
  START -> finance_analyst + user_perspective  (parallel-ish sequential)
        -> reviewer
        -> manager synthesis -> END

Uses local Ollama via ollama_client.chat (no hard dependency on langgraph).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ollama_client import chat as ollama_chat, ollama_reachable

logger = logging.getLogger(__name__)

ROLES = {
    "finance_analyst": {
        "name": "资深金融分析师",
        "system": (
            "你是资深金融分析师。基于用户问题与参考资料，用中文给出专业、结构化分析："
            "基本面、情绪/评级线索、风险点。数据不足时明确说明。末尾不需要免责声明。"
        ),
    },
    "user_advocate": {
        "name": "普通投资者视角",
        "system": (
            "你代表普通个人投资者。用通俗中文指出：看不懂的地方、最关心的收益风险、"
            "需要系统补充的信息。简洁分点。"
        ),
    },
    "reviewer": {
        "name": "需求与风险审核员",
        "system": (
            "你是审核员。对照金融常识与风险披露要求，审核前两份分析的遗漏、夸大、数据缺口，"
            "给出修正建议。用中文，分条列出。"
        ),
    },
    "manager": {
        "name": "经理综合",
        "system": (
            "你是项目经理。综合金融分析师、投资者视角、审核意见，输出最终答复："
            "1) 结论摘要 2) 关键依据 3) 主要风险 4) 后续可查的数据/操作提示。"
            "文末必须加：投资有风险，以上分析不构成投资建议。"
        ),
    },
}


def _safe_chat(system: str, user: str, max_chars: int = 2500) -> str:
    try:
        text = ollama_chat(user[:12000], system_prompt=system)
        return (text or "").strip()[:max_chars]
    except Exception as e:
        logger.warning("multi-agent llm step failed: %s", e)
        return f"[本步骤模型暂时不可用: {e}]"


def run_multi_agent(
    question: str,
    context: str = "",
    stock_code: str = "",
) -> dict[str, Any]:
    """
    Run coordinated multi-agent pipeline. Returns structured roles + final answer.
    """
    q = (question or "").strip()
    if not q:
        return {"status": "error", "message": "问题不能为空", "steps": []}

    reachable = ollama_reachable()
    header = f"用户问题：{q}\n"
    if stock_code:
        header += f"关注标的代码：{stock_code}\n"
    if context:
        header += f"\n参考资料：\n{context[:8000]}\n"

    steps: list[dict] = []
    status: dict[str, str] = {}

    # Step 1: finance analyst
    status["finance_analyst"] = "running"
    fa = _safe_chat(ROLES["finance_analyst"]["system"], header + "\n请输出专业分析。")
    steps.append({
        "role": "finance_analyst",
        "role_name": ROLES["finance_analyst"]["name"],
        "output": fa,
        "at": datetime.utcnow().isoformat() + "Z",
    })
    status["finance_analyst"] = "done"

    # Step 2: user advocate
    status["user_advocate"] = "running"
    ua = _safe_chat(
        ROLES["user_advocate"]["system"],
        header + f"\n金融分析师观点：\n{fa[:2000]}\n\n请从普通投资者角度补充。",
    )
    steps.append({
        "role": "user_advocate",
        "role_name": ROLES["user_advocate"]["name"],
        "output": ua,
        "at": datetime.utcnow().isoformat() + "Z",
    })
    status["user_advocate"] = "done"

    # Step 3: reviewer
    status["reviewer"] = "running"
    rev = _safe_chat(
        ROLES["reviewer"]["system"],
        header
        + f"\n【分析师】\n{fa[:1500]}\n\n【投资者】\n{ua[:1500]}\n\n请审核并指出问题。",
    )
    steps.append({
        "role": "reviewer",
        "role_name": ROLES["reviewer"]["name"],
        "output": rev,
        "at": datetime.utcnow().isoformat() + "Z",
    })
    status["reviewer"] = "done"

    # Step 4: manager synthesis
    status["manager"] = "running"
    final = _safe_chat(
        ROLES["manager"]["system"],
        header
        + f"\n【分析师】\n{fa[:1200]}\n\n【投资者】\n{ua[:800]}\n\n【审核】\n{rev[:1200]}\n\n请输出最终综合答复。",
        max_chars=4000,
    )
    steps.append({
        "role": "manager",
        "role_name": ROLES["manager"]["name"],
        "output": final,
        "at": datetime.utcnow().isoformat() + "Z",
    })
    status["manager"] = "done"

    return {
        "status": "ok",
        "question": q,
        "stock_code": stock_code or None,
        "ollama": reachable,
        "step_status": status,
        "steps": steps,
        "roles": [s["role_name"] for s in steps],
        "final_answer": final,
        "agent_count": len(steps),
    }
