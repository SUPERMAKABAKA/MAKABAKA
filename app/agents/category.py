"""\u5546\u54c1\u54c1\u7c7b\u8bc6\u522b\u4e0e\u786e\u5b9a\u6027\u9009\u9879\u751f\u6210\uff08\u65e0 LLM\uff0c\u53ef\u79bb\u7ebf\uff09\u3002

\u4e3a Clarify_Agent \u63d0\u4f9b\u4e24\u7c7b\u80fd\u529b\uff1a
- ``detect_category``\uff1a\u4ece\u81ea\u7136\u8bed\u53e5\u4e2d\u5339\u914d\u5546\u54c1\u54c1\u7c7b\uff08\u5173\u952e\u8bcd\u8868\uff09\uff0c\u7528\u4e8e
  \u5224\u5b9a\u540c\u4e00\u4f1a\u8bdd\u5185\u662f\u5426\u201c\u6362\u4e86\u65b0\u54c1\u7c7b\u201d\u3002
- ``rule_options``\uff1a\u9884\u7b97/\u504f\u597d\u7684\u786e\u5b9a\u6027\u9009\u9879\u6863\u4f4d\uff0c\u4f5c\u4e3a LLM \u751f\u6210\u9009\u9879\u5931\u8d25\u65f6\u7684\u5175\u5e95\u3002
"""

from __future__ import annotations

from typing import Optional

__all__ = ["detect_category", "rule_options", "BUDGET_OPTIONS", "is_shopping_intent", "smalltalk_reply"]

# \u54c1\u7c7b\u5173\u952e\u8bcd\u8868\uff08\u82f1\u6587\u4e3a\u4e3b\uff0c\u517c\u5bb9\u5e38\u89c1\u4e2d\u6587\uff09\u3002\u952e\u4e3a\u89c4\u8303\u5316\u54c1\u7c7b\u540d\u3002
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "headphones": ("headphone", "headphones", "earbud", "earbuds", "earphone", "\u8033\u673a", "\u8033\u5854"),
    "laptop": ("laptop", "notebook", "ultrabook", "\u7b14\u8bb0\u672c", "\u7535\u8111"),
    "phone": ("phone", "smartphone", "iphone", "android", "\u624b\u673a"),
    "mouse": ("mouse", "\u9f20\u6807"),
    "keyboard": ("keyboard", "\u952e\u76d8"),
    "monitor": ("monitor", "display", "\u663e\u793a\u5668"),
    "camera": ("camera", "\u76f8\u673a", "\u5fae\u5355"),
    "watch": ("watch", "smartwatch", "\u624b\u8868", "\u624b\u73af"),
    "speaker": ("speaker", "soundbar", "\u97f3\u7bb1", "\u97f3\u54cd"),
    "tablet": ("tablet", "ipad", "\u5e73\u677f"),
    "shoes": ("shoes", "sneaker", "sneakers", "\u978b", "\u8dd1\u978b"),
    "chair": ("chair", "\u692d\u5b50", "\u5ea7\u6905"),
    "purifier": ("purifier", "\u51c0\u5316\u5668"),
    "massage": ("massage", "massager", "\u6309\u6469"),
}

# \u5404\u54c1\u7c7b\u7684\u504f\u597d\u9009\u9879\uff08\u786e\u5b9a\u6027\u5175\u5e95\uff09\u3002\u672a\u547d\u4e2d\u54c1\u7c7b\u65f6\u7528 _GENERIC_PREFS\u3002
_PREF_OPTIONS: dict[str, tuple[str, ...]] = {
    "headphones": ("Noise cancelling", "Sound quality", "Long battery", "Comfort/portability"),
    "laptop": ("Performance", "Lightweight", "Long battery", "Value for money"),
    "phone": ("Camera", "Battery life", "Performance", "Value for money"),
    "mouse": ("Ergonomics", "Precision", "Wireless", "Value for money"),
    "keyboard": ("Mechanical feel", "Quiet", "Wireless", "Compact"),
    "monitor": ("High resolution", "High refresh rate", "Color accuracy", "Value for money"),
    "camera": ("Image quality", "Portability", "Video features", "Value for money"),
    "watch": ("Health tracking", "Battery life", "Design", "Value for money"),
    "speaker": ("Sound quality", "Portability", "Bass", "Value for money"),
    "tablet": ("Screen quality", "Performance", "Portability", "Value for money"),
    "shoes": ("Comfort", "Durability", "Style", "Value for money"),
    "chair": ("Ergonomics", "Comfort", "Durability", "Value for money"),
    "purifier": ("Coverage area", "Quiet operation", "Filter quality", "Value for money"),
    "massage": ("Intensity", "Quiet operation", "Portability", "Value for money"),
}

_GENERIC_PREFS: tuple[str, ...] = ("Top quality", "Best value", "Popular brand", "Highly rated")

# \u9884\u7b97\u6863\u4f4d\uff08\u4e0e\u54c1\u7c7b\u65e0\u5173\uff0c\u901a\u7528\uff09\u3002
BUDGET_OPTIONS: tuple[str, ...] = (
    "Under $50", "$50-200", "$200-500", "$500+", "No limit",
)


def detect_category(text: Optional[str]) -> Optional[str]:
    """\u4ece\u6587\u672c\u4e2d\u8bc6\u522b\u5546\u54c1\u54c1\u7c7b\uff1b\u547d\u4e2d\u8fd4\u56de\u89c4\u8303\u5316\u54c1\u7c7b\u540d\uff0c\u5426\u5219 ``None``\u3002"""
    if not text:
        return None
    low = text.lower()
    for category, words in _CATEGORY_KEYWORDS.items():
        for w in words:
            if w in low:
                return category
    return None


def rule_options(feature: str, category: Optional[str]) -> list[str]:
    """\u8fd4\u56de\u67d0\u7279\u5f81\u7684\u786e\u5b9a\u6027\u9009\u9879\u5175\u5e95\u3002

    - ``budget`` \u2192 \u56fa\u5b9a\u6863\u4f4d\uff1b
    - ``preferences`` \u2192 \u6309\u54c1\u7c7b\u7ed9\u9009\u9879\uff0c\u672a\u77e5\u54c1\u7c7b\u7ed9\u901a\u7528\u9879\uff1b
    - ``purpose`` \u2192 \u65e0\u56fa\u5b9a\u6863\u4f4d\uff0c\u8fd4\u56de\u7a7a\u5217\u8868\uff08\u7531\u7528\u6237\u81ea\u7531\u63cf\u8ff0\uff09\u3002
    """
    if feature == "budget":
        return list(BUDGET_OPTIONS)
    if feature == "preferences":
        return list(_PREF_OPTIONS.get(category or "", _GENERIC_PREFS))
    return []


# 购物意图关键词：出现任一即视为带购物意图（除品类词外的通用词）。
_SHOPPING_HINTS: tuple[str, ...] = (
    "buy", "recommend", "recommendation", "looking for", "need a", "need an",
    "want a", "want an", "want to buy", "budget", "cheap", "under $", "best",
    "price", "shopping", "purchase", "gift", "买", "推荐", "预算", "想要",
    "性价比", "适合", "需要",
)

# 常见闲聊/元问题提示词（“you are who”类对话）。
_SMALLTALK_HINTS: tuple[str, ...] = (
    "who are you", "what are you", "what can you do", "help", "hello", "hi ",
    "hey", "how are you", "your name", "what is this", "你是谁", "你能",
    "你好", "帮助", "这是什么", "怎么用",
)


def is_shopping_intent(text: Optional[str]) -> bool:
    """判断文本是否带购物意图。

    命中商品品类词、购物提示词或含数字（可能是预算）时视为购物意图。
    """
    if not text:
        return False
    low = text.lower()
    if detect_category(low) is not None:
        return True
    for h in _SHOPPING_HINTS:
        if h in low:
            return True
    # 含数字（常见于预算/型号）也往购物意图靠。
    if any(ch.isdigit() for ch in low):
        return True
    return False


def smalltalk_reply(text: Optional[str]) -> str:
    """为闲聊/元问题返回确定性英文回复（介绍 Nova 与用法）。"""
    return (
        "I'm Nova, your shopping assistant. Tell me what you're looking to buy "
        "(for example: \"noise cancelling headphones\" or \"a laptop for work\"), "
        "and I'll ask a couple of quick questions and then recommend products "
        "with reasons and real review highlights."
    )
