"""Evidence Evaluator：评估证据充分性（Sufficiency Check）。

基于多维评分判断是否继续研究：
- 证据数量
- 证据覆盖面（子任务覆盖）
- 平均置信度
- 引用可用性
"""
from __future__ import annotations

from app.models import Evidence


def evidence_score(evidence: list[Evidence]) -> float:
    """证据综合得分（0~1），用于 Sufficiency Check。"""
    if not evidence:
        return 0.0
    n = len(evidence)
    avg_confidence = sum(e.confidence for e in evidence) / n
    # 数量：5 条证据即达满分
    quantity = min(1.0, n / 5.0)
    # 有可用来源的比例
    with_source = sum(1 for e in evidence if e.source.url) / n
    score = 0.5 * avg_confidence + 0.3 * quantity + 0.2 * with_source
    return round(min(1.0, max(0.0, score)), 3)


def is_sufficient(
    evidence: list[Evidence],
    threshold: float = 0.6,
    min_evidence: int = 3,
    iteration: int = 0,
    max_iterations: int = 8,
) -> tuple[bool, float]:
    """判断证据是否足够。

    规则：
    - 达到最低证据数且综合得分达阈值 → sufficient
    - 达到最大迭代次数 → 强制结束（避免无限循环）
    - 证据极少（< min_evidence）→ 继续
    """
    score = evidence_score(evidence)
    if iteration >= max_iterations:
        return True, score
    if len(evidence) >= min_evidence and score >= threshold:
        return True, score
    return False, score
