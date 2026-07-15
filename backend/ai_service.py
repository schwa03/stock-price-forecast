# c:/Stock_Price_Forecast/backend/ai_service.py

import json
import os
import threading
import time
import urllib.parse
from typing import Dict, List

import feedparser
from dotenv import load_dotenv

load_dotenv()

_API_KEYS = []
_CURRENT_KEY_INDEX = 0
_KEY_LOCK = threading.Lock()

def get_keys():
    global _API_KEYS
    if not _API_KEYS:
        raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
        _API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip() and "ここ" not in k]
    return _API_KEYS

def call_gemini_with_retry(prompt: str) -> str:
    from google import genai
    from google.genai import types
    
    keys = get_keys()
    if not keys:
         raise ValueError("AI連動オフ（APIキー未設定）")

    global _CURRENT_KEY_INDEX
    max_attempts = max(3, len(keys) * 2)
    last_error = None
    
    for attempt in range(max_attempts):
        with _KEY_LOCK:
            current_key = keys[_CURRENT_KEY_INDEX]
            _CURRENT_KEY_INDEX = (_CURRENT_KEY_INDEX + 1) % len(keys)
            
        try:
            client = genai.Client(api_key=current_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return response.text
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"[AI_SERVICE] 429 Quota Exceeded on key {current_key[:10]}... Rotating to next key.")
                time.sleep(1) # 短時間待機して次のキーへ
                continue
            else:
                print(f"[AI_SERVICE] Non-429 error: {error_msg}. Retrying.")
                time.sleep(2)
                continue
    raise last_error

def fetch_recent_news(keyword: str) -> List[Dict]:
    """Google News RSSから直近のニュースを取得"""
    safe_keyword = urllib.parse.quote(f"{keyword} 株")
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=ja&gl=JP&ceid=JP:ja"
    d = feedparser.parse(url)
    
    news_items = []
    for entry in d.entries[:5]:  # 直近5件を取得
        source_title = entry.source.title if hasattr(entry, 'source') else "News"
        news_items.append({
            "title": entry.title,
            "url": entry.link,
            "source": source_title
        })
    return news_items

def extract_news_facts(code: str, name_ja: str, news_list: List[Dict]) -> List[Dict]:
    """ニュースからファクト（事実）のみをAIで抽出する（点数評価はしない）"""
    if not get_keys():
        return [{"fact": "AI連動オフ", "category": "マクロ", "title": n["title"]} for n in news_list]

    prompt = f"""
    あなたはデータ抽出の専門AIです。
    以下のニュースは「{name_ja} ({code})」に関する直近のヘッドラインです。
    これらのニュースから、企業の業績、経営、マクロ環境、リスク等に関する「事実（ファクト）」を一切の主観や評価を交えずに抽出してください。
    重要度を判定して除外することなく、見つかったファクトはすべて出力してください。
    
    出力は必ず以下のJSON配列形式としてください:
    [
      {{
        "title": "もっとも関連する元のニュースのタイトル",
        "category": "財務, 経営, 製品, マクロ, その他 のいずれか",
        "fact": "抽出された事実（20文字程度の簡潔な文章）"
      }}
    ]

    ニュース:
    """
    for n in news_list:
        prompt += f"- {n['title']}\n"

    try:
        text = call_gemini_with_retry(prompt)
        return json.loads(text)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            fact_msg = "API利用制限超過（全APIキーの無料枠枯渇）"
        else:
            fact_msg = "AI推論エラー"
        print(f"[AI_SERVICE] News Extract Error: {error_msg}")
        return [{"fact": fact_msg, "category": "エラー", "title": n["title"]} for n in news_list]

def extract_docs_facts(code: str, name_ja: str) -> List[Dict]:
    """開示情報等から長期ファクトを抽出する（モックジェネレーター）"""
    if not get_keys():
        return [{"fact": "AI連動オフ", "title": "開示資料分析", "type": "EDINET"}]

    prompt = f"""
    あなたはデータ抽出の専門AIです。
    「{name_ja} ({code})」の直近の決算短信や有価証券報告書などの開示資料に基づく
    「想定される事実（ファクト）」を2点推測・抽出してください。
    出力は必ず以下のJSON配列形式としてください:
    [
      {{
        "title": "資料名（例: TDnet: 2024年度決算短信）",
        "type": "TDnet または EDINET",
        "fact": "抽出された事実（20文字程度の簡潔な文章）"
      }}
    ]
    """

    try:
        text = call_gemini_with_retry(prompt)
        return json.loads(text)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            fact_msg = "API利用制限超過（全APIキーの無料枠枯渇）"
        else:
            fact_msg = "AI推論エラー"
        print(f"[AI_SERVICE] Docs Extract Error: {error_msg}")
        return [{"fact": fact_msg, "title": "開示資料等", "type": "その他"}]
