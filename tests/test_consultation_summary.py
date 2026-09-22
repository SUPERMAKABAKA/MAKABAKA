"""ConsultationSummary 总结服务单元测试。

覆盖：
- MockLLM 下 ``summarize`` 返回非空字符串；
- ``llm=None`` 走规则回退，返回非空且不臆造未在输入中出现的价格/星级（Req 3.5）；
- LLM ``generate`` 抛异常时回退规则、不抛出（Req 3.4）。

使用进程内的假 LLM，绝不触达真实模型服务。
"""

import re

from app.agents.consultation_summary import ConsultationSummary
from app.interfaces.llm import MockLLM
from app.orchestrator.models import ProductRecommendation, ReviewSummary


def _rec(product_id="p1", title="示例耳机") -> ProductRecommendation:
    """构造一条不含价格/星级数值的推荐，便于校验规则回退不臆造数值。"""
    return ProductRecommendation(
        product_id=product_id,
        title=title,
        reason="与当前降噪与长续航的需求匹配。",
        product_url=f"https://example.test/dp/{product_id}",
        summary=ReviewSummary(
            positives=["降噪效果出色", "佩戴舒适"],
            negatives=["折叠结构不便携"],
        ),
        detail="主动降噪，长续航，支持多点连接。",
        # price/rating 故意留空：规则回退不应凭空造出数值。
    )


class BoomLLM:
    """generate 恒抛异常的假 LLM，用于验证回退不抛出。"""

    def generate(self, prompt, **kw):
        raise RuntimeError("boom: quota exceeded")


def test_summarize_with_mock_llm_returns_nonempty():
    """有 MockLLM 时，summarize 返回非空字符串。

    Validates: Requirements 3.1
    """
    summary = ConsultationSummary(MockLLM()).summarize(
        transcript="客服：这款耳机降噪出色，续航长，值得考虑。",
        recommendations=[_rec()],
    )
    assert isinstance(summary, str)
    assert summary.strip()


def test_rule_fallback_nonempty_and_no_fabricated_numbers():
    """llm=None 走规则回退：非空，且不臆造输入中不存在的价格/星级。

    Validates: Requirements 3.5
    """
    transcript = (
        "客服：这款耳机主动降噪表现好，佩戴舒适，续航够用。"
        "折叠结构不如上一代方便，其余整体满意。"
    )
    rec = _rec()
    summary = ConsultationSummary(llm=None).summarize(transcript, [rec])

    assert isinstance(summary, str)
    assert summary.strip()

    # 前提：recommendation 未提供 price/rating，输入自然语言字段也不含数字。
    textual_input = " ".join(
        [
            transcript,
            rec.title,
            rec.reason,
            rec.detail,
            *rec.summary.positives,
            *rec.summary.negatives,
        ]
    )
    assert rec.price is None and rec.rating is None
    assert not any(ch.isdigit() for ch in textual_input), "测试前提：输入文本不含数字"

    # 规则回退不应臆造价格/星级等事实性数值。列表序号（如 "1."）属于结构化
    # 排版，不是被臆造的事实；因此剥离行首序号后，正文不应再出现任何数字。
    body_without_ordinals = "\n".join(
        re.sub(r"^\s*\d+\.\s*", "", line) for line in summary.splitlines()
    )
    assert not any(ch.isdigit() for ch in body_without_ordinals), (
        "规则回退不应臆造输入中不存在的价格/星级等数值"
    )


def test_summarize_falls_back_when_llm_raises():
    """LLM.generate 抛异常时，summarize 不抛出并返回非空（规则回退）。

    Validates: Requirements 3.4, 5.3
    """
    summary = ConsultationSummary(BoomLLM()).summarize(
        transcript="客服：整体口碑不错，优点明显。",
        recommendations=[_rec()],
    )
    assert isinstance(summary, str)
    assert summary.strip()
