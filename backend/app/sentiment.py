"""轻量情绪判断：基于词典与 emoji 的打分，无需外部依赖。"""
import re

POSITIVE = {
    "love", "loved", "amazing", "awesome", "beautiful", "best", "happy", "great", "wonderful",
    "excited", "perfect", "thank", "thanks", "grateful", "blessed", "fun", "enjoy", "favorite",
    "stunning", "incredible", "fantastic", "good", "nice", "cute", "win", "congrats", "yay",
    "喜欢", "爱", "开心", "幸福", "美", "棒", "赞", "感谢", "期待", "完美", "太好了", "好看", "推荐",
}
NEGATIVE = {
    "hate", "sad", "angry", "worst", "bad", "terrible", "awful", "ugly", "cry", "tired", "sick",
    "disappointed", "sorry", "fail", "pain", "hurt", "broken", "lost", "miss", "rip", "stress",
    "难过", "伤心", "生气", "糟糕", "差", "失望", "讨厌", "累", "痛", "哭", "后悔", "烂",
}
POS_EMOJI = "😀😁😂🤣😊😍🥰😘😎🤩🥳👍👏🙌❤️💕💖✨🔥🎉🌟💯"
NEG_EMOJI = "😢😭😞😔😡🤬😠💔👎😩😫🥺😤"


def analyze(text: str) -> tuple[str, str, float]:
    lowered = text.lower()
    words = re.findall(r"[a-z']+", lowered)
    pos = sum(1 for w in words if w in POSITIVE)
    neg = sum(1 for w in words if w in NEGATIVE)
    for term in POSITIVE:
        if not term.isascii() and term in text:
            pos += 1
    for term in NEGATIVE:
        if not term.isascii() and term in text:
            neg += 1
    pos += sum(1 for ch in text if ch in POS_EMOJI)
    neg += sum(1 for ch in text if ch in NEG_EMOJI)
    total = pos + neg
    score = 0.0 if total == 0 else round((pos - neg) / total, 2)
    if score > 0.2:
        return "positive", "积极", score
    if score < -0.2:
        return "negative", "消极", score
    return "neutral", "中性", score
