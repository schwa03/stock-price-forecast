# c:/Stock_Price_Forecast/backend/ai_service.py

import json
import os
import re
import threading
import time
import urllib.parse
from typing import Dict, List

import feedparser
from dotenv import load_dotenv

load_dotenv()


def _parse_json_lenient(text: str):
    """Geminiのレスポンスをできるだけ寛容にJSONとしてパースする。

    response_mime_type="application/json"を指定していても、稀に```json ... ```の
    コードフェンスで囲まれて返ってくることがあり、そのままjson.loadsすると構文エラーに
    なる（実際に本番ログで"Expecting ',' delimiter"等の構文エラーを確認済み）。
    まず素直にパースを試み、失敗したらコードフェンスを取り除いて再試行する。
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
            stripped = re.sub(r"\n?```$", "", stripped)
        return json.loads(stripped.strip())

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
                # 固定バージョンではなく "latest" エイリアスを使う。
                # 個別バージョンは新規ユーザー向けに順次廃止されるため（2026-07時点でgemini-2.5-flashは廃止済み）。
                model='gemini-flash-latest',
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
        return [{"fact": "AI連動オフ（APIキー未設定）", "category": "エラー", "title": "AI連動オフ"}]

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
        return _parse_json_lenient(text)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            fact_msg = "API利用制限超過（無料枠のクォータ上限に達しました。しばらくすると再試行されます）"
        else:
            fact_msg = "AI推論エラーが発生しました"
        print(f"[AI_SERVICE] News Extract Error: {error_msg}")
        # ニュース件数分の重複したエラーカードを出さないよう、1件のみ返す
        return [{"fact": fact_msg, "category": "エラー", "title": "AI分析エラー"}]

MACRO_QUERIES = ["日経平均 市場全体", "日本 金融政策 金利", "地政学リスク 日本経済"]


def fetch_macro_news() -> List[Dict]:
    """個別銘柄に紐づかない市場全体・マクロ経済・地政学リスクのニュースを収集する（REQUIREMENTS_v2.md 2.5参照）。"""
    news_items = []
    seen_urls = set()
    for query in MACRO_QUERIES:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=ja&gl=JP&ceid=JP:ja"
        d = feedparser.parse(url)
        for entry in d.entries[:3]:
            if entry.link in seen_urls:
                continue
            seen_urls.add(entry.link)
            source_title = entry.source.title if hasattr(entry, 'source') else "News"
            news_items.append({"title": entry.title, "url": entry.link, "source": source_title})
    return news_items


def extract_macro_facts(news_list: List[Dict]) -> List[Dict]:
    """市場全体・マクロ・地政学ニュースからファクトのみをAIで抽出する（点数評価はしない）。"""
    if not get_keys():
        return [{"fact": "AI連動オフ（APIキー未設定）", "category": "エラー", "title": "AI連動オフ"}]
    if not news_list:
        return []

    prompt = """
    あなたはデータ抽出の専門AIです。
    以下は日本株市場全体に関する直近のニュースヘッドラインです（特定の個別銘柄向けではありません）。
    これらのニュースから、市場全体・マクロ経済・地政学リスクに関する「事実（ファクト）」を
    一切の主観や評価を交えずに抽出してください。重要度で選別せず、見つかったファクトはすべて出力してください。

    出力は必ず以下のJSON配列形式としてください:
    [
      {
        "title": "もっとも関連する元のニュースのタイトル",
        "category": "金融政策, 為替, 地政学, 物価, その他 のいずれか",
        "fact": "抽出された事実（20文字程度の簡潔な文章）"
      }
    ]

    ニュース:
    """
    for n in news_list:
        prompt += f"- {n['title']}\n"

    try:
        text = call_gemini_with_retry(prompt)
        return _parse_json_lenient(text)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            fact_msg = "API利用制限超過（無料枠のクォータ上限に達しました。しばらくすると再試行されます）"
        else:
            fact_msg = "AI推論エラーが発生しました"
        print(f"[AI_SERVICE] Macro Extract Error: {error_msg}")
        return [{"fact": fact_msg, "category": "エラー", "title": "AI分析エラー"}]


def extract_docs_facts(code: str, name_ja: str) -> List[Dict]:
    """開示情報等から長期ファクトを抽出する（モックジェネレーター）"""
    if not get_keys():
        return [{"fact": "AI連動オフ（APIキー未設定）", "title": "AI連動オフ", "type": "エラー"}]

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
        return _parse_json_lenient(text)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            fact_msg = "API利用制限超過（無料枠のクォータ上限に達しました。しばらくすると再試行されます）"
        else:
            fact_msg = "AI推論エラーが発生しました"
        print(f"[AI_SERVICE] Docs Extract Error: {error_msg}")
        return [{"fact": fact_msg, "title": "AI分析エラー", "type": "エラー"}]


# 巡回処理からの銘柄別ニュース/開示分析は、1銘柄ごとに2回Geminiを呼ぶと
# 225銘柄で450リクエストになり無料枠クォータをすぐ使い切ってしまう。
# 複数銘柄をまとめて1回のリクエストで処理することでクォータ消費を抑える
# （REQUIREMENTS_v2.md 2.3参照。目安15銘柄/リクエスト）。
NEWS_BATCH_SIZE = 15


def extract_news_facts_batch(stocks: List[Dict]) -> Dict[str, List[Dict]]:
    """複数銘柄分のニュースファクトを1回のGemini呼び出しでまとめて抽出する。

    stocks: [{"code": str, "name_ja": str, "news": [{"title": str}, ...]}, ...]
    戻り値: {code: [fact, ...]}（該当銘柄の抽出に失敗/欠落していれば空リスト）
    """
    if not get_keys():
        return {s["code"]: [{"fact": "AI連動オフ（APIキー未設定）", "category": "エラー", "title": "AI連動オフ"}] for s in stocks}

    prompt = """
    あなたはデータ抽出の専門AIです。
    以下は複数銘柄それぞれに関する直近のニュースヘッドラインです。
    各銘柄について、企業の業績、経営、マクロ環境、リスク等に関する「事実（ファクト）」を
    一切の主観や評価を交えずに抽出してください。重要度で選別せず、見つかったファクトはすべて出力してください。

    出力は必ず、銘柄コードをキーとする以下のJSONオブジェクト形式としてください:
    {
      "銘柄コード": [
        {"title": "もっとも関連する元のニュースのタイトル", "category": "財務, 経営, 製品, マクロ, その他 のいずれか", "fact": "抽出された事実（20文字程度）"}
      ]
    }

    銘柄一覧:
    """
    for s in stocks:
        prompt += f"\n### {s['code']} ({s['name_ja']})\n"
        for n in s.get("news", []):
            prompt += f"- {n['title']}\n"

    try:
        text = call_gemini_with_retry(prompt)
        parsed = _parse_json_lenient(text)
        return {s["code"]: parsed.get(s["code"], []) for s in stocks}
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            fact_msg = "API利用制限超過（無料枠のクォータ上限に達しました。しばらくすると再試行されます）"
        else:
            fact_msg = "AI推論エラーが発生しました"
        print(f"[AI_SERVICE] Batch News Extract Error: {error_msg}")
        return {s["code"]: [{"fact": fact_msg, "category": "エラー", "title": "AI分析エラー"}] for s in stocks}


def extract_docs_facts_batch(stocks: List[Dict]) -> Dict[str, List[Dict]]:
    """複数銘柄分の開示情報ファクトを1回のGemini呼び出しでまとめて抽出する（モックジェネレーター）。

    stocks: [{"code": str, "name_ja": str}, ...]
    """
    if not get_keys():
        return {s["code"]: [{"fact": "AI連動オフ（APIキー未設定）", "title": "AI連動オフ", "type": "エラー"}] for s in stocks}

    prompt = """
    あなたはデータ抽出の専門AIです。
    以下の複数銘柄それぞれについて、直近の決算短信や有価証券報告書などの開示資料に基づく
    「想定される事実（ファクト）」を1〜2点推測・抽出してください。

    出力は必ず、銘柄コードをキーとする以下のJSONオブジェクト形式としてください:
    {
      "銘柄コード": [
        {"title": "資料名（例: TDnet: 2024年度決算短信）", "type": "TDnet または EDINET", "fact": "抽出された事実（20文字程度）"}
      ]
    }

    銘柄一覧:
    """
    for s in stocks:
        prompt += f"- {s['code']} ({s['name_ja']})\n"

    try:
        text = call_gemini_with_retry(prompt)
        parsed = _parse_json_lenient(text)
        return {s["code"]: parsed.get(s["code"], []) for s in stocks}
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            fact_msg = "API利用制限超過（無料枠のクォータ上限に達しました。しばらくすると再試行されます）"
        else:
            fact_msg = "AI推論エラーが発生しました"
        print(f"[AI_SERVICE] Batch Docs Extract Error: {error_msg}")
        return {s["code"]: [{"fact": fact_msg, "title": "AI分析エラー", "type": "エラー"}] for s in stocks}
