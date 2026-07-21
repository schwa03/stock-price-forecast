# c:/Stock_Price_Forecast/backend/internal_ai.py

from typing import Dict, List

# 判定根拠一覧の「寄与度(pt)」表示専用のキーワード辞書。
# スコア計算(predictor.py)には一切使わない、あくまで補助表示の演出。
# 2026-07-21改訂: 従来はキーワード一致時にランダムな大きさを足していたが、
# 同じ入力でも表示のたびに数値が変わってしまい紛らわしいため、
# 一致したキーワード数に基づく決定的な計算に変更した。
POSITIVE_KEYWORDS = ["上方修正", "増益", "買収", "自社株買い", "黒字", "提携", "好調", "新製品", "配当", "増配"]
NEGATIVE_KEYWORDS = ["下方修正", "減益", "赤字", "不祥事", "訴訟", "遅延", "延期", "売却", "解約", "悪化"]
KEYWORD_WEIGHT = 4
MAX_EFFECT = 8


def _evaluate_fact(category: str, fact_text: str) -> dict:
    """
    抽出された事実から、判定根拠一覧に表示する寄与度（effect）・理由（reason）・
    ポジネガクラス（cls）を算出する。キーワード辞書による決定的なルールベースであり、
    予測スコア自体（predictor.py）には使わない補助表示専用。
    """
    # Gemini呼び出し自体が失敗した場合（クォータ超過等）の「事実」は、実際の分析結果ではないため、
    # 通常のキーワード評価にかけず、意味のない点数がついて見えないようにする
    if category == "エラー":
        return {"effect": "0", "reason": "AI分析が利用できません", "cls": "neu"}

    matched_positive = [kw for kw in POSITIVE_KEYWORDS if kw in fact_text]
    matched_negative = [kw for kw in NEGATIVE_KEYWORDS if kw in fact_text]
    score = max(-MAX_EFFECT, min(MAX_EFFECT, (len(matched_positive) - len(matched_negative)) * KEYWORD_WEIGHT))

    if matched_positive and not matched_negative:
        reason_prefix = f"好材料キーワードを検出（{matched_positive[0]}）"
    elif matched_negative and not matched_positive:
        reason_prefix = f"懸念材料キーワードを検出（{matched_negative[0]}）"
    elif matched_positive and matched_negative:
        reason_prefix = "好材料・懸念材料が混在"
    else:
        reason_prefix = "該当キーワードなし（中立判定）"

    if score > 0:
        cls_val = "pos"
        effect_str = f"+{score}"
    elif score < 0:
        cls_val = "neg"
        effect_str = str(score)
    else:
        cls_val = "neu"
        effect_str = "0"

    return {
        "effect": effect_str,
        "reason": reason_prefix,
        "cls": cls_val
    }

def score_news_facts(facts_list: List[Dict], original_news: List[Dict]) -> List[Dict]:
    """
    Geminiが抽出した事実リストに対し、社内AIが評価を下してフロントエンド向けのフォーマットに成形する
    """
    scored_news = []
    for i, fact_item in enumerate(facts_list):
        if fact_item.get("category") == "エラー":
            # AI分析自体が失敗した状態。フロント側で「システムの状態」として
            # 通常の分析結果と区別して表示できるよう source を "System" にする
            evaluation = _evaluate_fact("エラー", "")
            scored_news.append({
                "title": "AIによるニュース分析が利用できません",
                "source": "System",
                "url": "#",
                "effect": evaluation["effect"],
                "reason": fact_item.get("fact", "しばらく経ってから再度ご確認ください"),
                "cls": evaluation["cls"],
            })
            continue

        evaluation = _evaluate_fact(fact_item.get("category", "その他"), fact_item.get("fact", ""))

        # 元のニュースURLとマージ
        url = "#"
        source = "News"
        if original_news and i < len(original_news):
             url = original_news[i].get("url", "#")
             source = original_news[i].get("source", "News")

        scored_news.append({
            "title": fact_item.get("title", fact_item.get("fact", "ニュース要素")),
            "source": source,
            "url": url,
            "effect": evaluation["effect"],
            "reason": f"{evaluation['reason']}: {fact_item.get('fact', '')}"[:40] + "...", # 事実をベースに理由づけ
            "cls": evaluation["cls"]
        })
    return scored_news

def score_macro_facts(facts_list: List[Dict], original_news: List[Dict]) -> List[Dict]:
    """市場全体・マクロ・地政学ニュースの事実に対する社内評価（判定根拠の補助表示専用。

    スコア計算には使わない。REQUIREMENTS_v2.md 2.5参照）。
    """
    scored = []
    for i, fact_item in enumerate(facts_list):
        if fact_item.get("category") == "エラー":
            evaluation = _evaluate_fact("エラー", "")
            scored.append({
                "title": "AIによるマクロニュース分析が利用できません",
                "source": "System",
                "url": "#",
                "effect": evaluation["effect"],
                "reason": fact_item.get("fact", "しばらく経ってから再度ご確認ください"),
                "cls": evaluation["cls"],
            })
            continue

        evaluation = _evaluate_fact(fact_item.get("category", "その他"), fact_item.get("fact", ""))
        url, source = "#", "News"
        if original_news and i < len(original_news):
            url = original_news[i].get("url", "#")
            source = original_news[i].get("source", "News")

        scored.append({
            "title": fact_item.get("title", fact_item.get("fact", "マクロニュース")),
            "source": source,
            "url": url,
            "effect": evaluation["effect"],
            "reason": f"{evaluation['reason']}: {fact_item.get('fact', '')}"[:40] + "...",
            "cls": evaluation["cls"],
        })
    return scored


def score_docs_facts(facts_list: List[Dict]) -> List[Dict]:
    """
    Geminiが抽出した開示情報ファクトに対する社内モデル評価
    """
    scored_docs = []
    for fact_item in facts_list:
        if fact_item.get("type") == "エラー" or fact_item.get("category") == "エラー":
            evaluation = _evaluate_fact("エラー", "")
            scored_docs.append({
                "title": "AIによる開示情報分析が利用できません",
                "type": "System",
                "url": "#",
                "effect": evaluation["effect"],
                "reason": fact_item.get("fact", "しばらく経ってから再度ご確認ください"),
                "cls": evaluation["cls"],
            })
            continue

        evaluation = _evaluate_fact(fact_item.get("type", "マクロ"), fact_item.get("fact", ""))
        scored_docs.append({
            "title": fact_item.get("title", "開示資料分析"),
            "type": fact_item.get("type", "EDINET"),
            "url": "#",
            "effect": evaluation["effect"],
            "reason": f"長期予測AI: {fact_item.get('fact', '')}"[:40] + "...",
            "cls": evaluation["cls"]
        })
    return scored_docs
