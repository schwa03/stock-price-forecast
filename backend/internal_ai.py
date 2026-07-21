# c:/Stock_Price_Forecast/backend/internal_ai.py

import random
from typing import Dict, List


def _evaluate_fact(category: str, fact_text: str) -> dict:
    """
    自社AIモック:
    抽出された事実から、スコア影響度（effect）、判断理由（reason）、ポジネガクラス（cls）を算出。
    ※本番環境では、ここに過去データによる機械学習モデル（XGBoost/LightGBM）を組み込みます。
    """
    # Gemini呼び出し自体が失敗した場合（クォータ超過等）の「事実」は、実際の分析結果ではないため、
    # 通常のキーワード/ランダム評価にかけず、意味のない点数がついて見えないようにする
    if category == "エラー":
        return {"effect": "0", "reason": "AI分析が利用できません", "cls": "neu"}

    # 簡易ルールベース ＋ ランダム（モック）のハイブリッド
    positive_keywords = ["上方修正", "増益", "買収", "自社株買い", "黒字", "提携", "好調", "新製品", "配当", "増配"]
    negative_keywords = ["下方修正", "減益", "赤字", "不祥事", "訴訟", "遅延", "延期", "売却", "解約", "悪化"]
    
    score = 0
    reason_prefix = ""
    
    # 1. ルールベース判定
    for pk in positive_keywords:
        if pk in fact_text:
            score += random.randint(3, 8)
            reason_prefix = "好感触な事実（社内AI判定）"
            break
            
    for nk in negative_keywords:
        if nk in fact_text:
            score -= random.randint(3, 8)
            reason_prefix = "懸念される事実（社内AI判定）"
            break
            
    # 2. キーワードがない場合はカテゴリベースの微細なランダム（MLモック）
    if score == 0:
        if category == "財務":
            score = random.randint(-4, 4)
            reason_prefix = "財務状況の統計予測"
        elif category == "マクロ":
            score = random.randint(-2, 2)
            reason_prefix = "マクロ環境の影響予測"
        elif category == "製品":
            score = random.randint(-1, 5)
            reason_prefix = "製品力の評価"
        else:
            score = random.randint(-3, 3)
            reason_prefix = "過去統計によるニュートラル判定"
            
    # スコアの丸めとクラス分け
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
