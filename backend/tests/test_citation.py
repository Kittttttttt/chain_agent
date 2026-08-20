"""Citation 系统测试：Claim → Evidence → Source 映射与 unverified 标记。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.verifier import CitationVerifier  # noqa: E402
from app.models import Evidence, Source  # noqa: E402


def _evidence(url: str, claim: str, confidence: float = 0.9) -> Evidence:
    return Evidence(
        claim=claim,
        source=Source(url=url, title="title", source_type="web"),
        relevance=0.9,
        confidence=confidence,
    )


def test_verified_citation_maps_to_source():
    ev = [_evidence("https://example.com/a", "claim A")]
    report = "结论见[来源1]。"
    citations = CitationVerifier().verify(report, ev)
    assert len(citations) == 1
    assert citations[0].status == "verified"
    assert citations[0].source.url == "https://example.com/a"


def test_missing_ref_is_unverified():
    """报告引用了不存在的来源 → 必须标记 unverified，禁止编造。"""
    report = "结论见[来源5]。"
    citations = CitationVerifier().verify(report, [])
    assert len(citations) == 1
    assert citations[0].status == "unverified"
    assert citations[0].source.url == ""


def test_no_fabricated_sources():
    """验证器不得凭空创建真实来源。"""
    ev = [_evidence("https://example.com/a", "claim A")]
    citations = CitationVerifier().verify("无引用标记", ev)
    assert citations == []
