import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

# Windows環境における文字エンコーディングエラー回避のため、UTF-8を強制設定
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr is not None:
    sys.stderr.reconfigure(encoding='utf-8')

from typing import List, Optional

import yfinance as yf
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

import ai_service
import auth
import backtest_engine
import fetch_nikkei225
import internal_ai
import predictor
from db import get_session, session_scope
from features import latest_feature_vector
from models import (
    BacktestResultRow,
    ChartDataRow,
    DocItemRow,
    FundamentalsRow,
    MacroNewsItemRow,
    NewsItemRow,
    SignalSummaryRow,
    StockMasterRow,
)


# --------- Schemas ---------
class StockMaster(BaseModel):
    code: str
    name_ja: str
    name_en: str
    sector: str

class SignalSummary(BaseModel):
    code: str
    short_score: int
    long_score: int
    final_score: int
    final_signal: str
    updated_at: str = ""

class RankingResponse(BaseModel):
    # 2026-07-21改訂: 元々はbottom_buy/bottom_sellも返していたが、
    # bottom_sell=top_buy・bottom_buy=top_sellと同一リストを別ラベルで
    # 表示していただけで、4つに分ける意味がなく「全部同じに見える」との
    # 指摘を受けて撤廃した。買い/売りTOP5の2種類のみを返す
    top_buy: List[SignalSummary]
    top_sell: List[SignalSummary]

class NewsInfo(BaseModel):
    title: str
    source: str
    url: str
    effect: str
    reason: str
    cls: str

class DocInfo(BaseModel):
    title: str
    type: str # TDnet, EDINET, IR
    url: str
    effect: str
    reason: str
    cls: str

class BacktestResult(BaseModel):
    code: str
    trades: int
    win_rate: float
    avg_return: float
    max_drawdown: float
    computed: bool = False  # 実データでの計算がまだ終わっていない場合はFalse（フロントで区別表示するため）

class ChartResponse(BaseModel):
    code: str
    labels: List[str]
    prices: List[Optional[float]]
    ma5: List[Optional[float]]
    ma25: List[Optional[float]]

class FundamentalsResponse(BaseModel):
    code: str
    per: Optional[float] = None
    pbr: Optional[float] = None
    dividend_yield: Optional[float] = None
    earnings_growth: Optional[float] = None
    computed: bool = False

# --------- Global State ---------
# 銘柄マスターは高速な一覧表示のためインメモリにも保持するが、
# 正本はDB（stock_master）。再起動時はDBから読み直す（REQUIREMENTS_v2.md 5.5）。
MASTER_STOCKS: List[StockMaster] = []
# コアスコア（テクニカル+ML）とニュース/開示分析（Gemini）は完全に別の巡回ループで
# 動くため、「処理中」フラグも別々に持つ（REQUIREMENTS_v2.md 2.2/2.3参照）。
_CORE_PROCESSING: set = set()
_NEWS_PROCESSING: set = set()
_BACKTEST_PROCESSING: set = set()

# 手動「最新化」ボタンでニュース/開示分析(Gemini)を強制更新する際のクールダウン。
# 連打や複数銘柄の閲覧で無料枠クォータを浪費しないための下限間隔（秒）。
MANUAL_NEWS_REFRESH_COOLDOWN_SECONDS = int(os.getenv("MANUAL_NEWS_REFRESH_COOLDOWN_SECONDS", "600"))


# --------- Master data (DB-backed) ---------
async def sync_master_data_from_json_to_db():
    """nikkei225.json の内容をDBのstock_masterへupsertする。"""
    json_path = os.path.join(os.path.dirname(__file__), "nikkei225.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        return

    async with session_scope() as session:
        for item in data:
            stmt = pg_insert(StockMasterRow).values(
                code=item["code"],
                name_ja=item["name_ja"],
                name_en=item.get("name_en", ""),
                sector=item.get("sector", ""),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[StockMasterRow.code],
                set_={
                    "name_ja": stmt.excluded.name_ja,
                    "name_en": stmt.excluded.name_en,
                    "sector": stmt.excluded.sector,
                },
            )
            await session.execute(stmt)
        await session.commit()


async def load_master_stocks_into_memory():
    """DBのstock_masterからMASTER_STOCKSを読み直す。"""
    global MASTER_STOCKS
    async with session_scope() as session:
        rows = (await session.execute(select(StockMasterRow))).scalars().all()
    MASTER_STOCKS = [
        StockMaster(code=r.code, name_ja=r.name_ja, name_en=r.name_en, sector=r.sector)
        for r in rows
    ]
    print(f"Loaded {len(MASTER_STOCKS)} stocks from DB.")


async def load_master_data():
    """起動時: DBが空ならnikkei225.jsonをシードとして投入し、DBから読み込む。"""
    async with session_scope() as session:
        existing = (await session.execute(select(StockMasterRow.code).limit(1))).first()
    if existing is None:
        try:
            await sync_master_data_from_json_to_db()
        except Exception as e:
            print(f"Warning: Failed to seed master data from nikkei225.json: {e}")
    await load_master_stocks_into_memory()


# --------- Background processing (DB-backed) ---------
def _jst_now_str() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


def _parse_jst(value: str) -> float:
    """時刻文字列をUnixタイムスタンプ化する。空・パース不能なら0.0（＝最優先扱い）を返す。"""
    if not value or value in ("推論中", "analyzing..."):
        return 0.0
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timestamp()
    except Exception:
        return 0.0


async def _mark_stock_as_errored(code: str):
    """コアスコア処理全体が失敗した銘柄を「error」状態でDBに記録する。

    これをしないと、失敗した銘柄はDBに一切書き込まれず、フロント側は
    「analyzing...」のプレースホルダーを永遠にポーリングし続け、
    失敗した事実がユーザーに一切伝わらないままになる。
    """
    try:
        async with session_scope() as session:
            summary_values = dict(
                short_score=0, long_score=0,
                final_score=0, final_signal="error", updated_at=_jst_now_str(),
            )
            stmt = pg_insert(SignalSummaryRow).values(code=code, **summary_values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[SignalSummaryRow.code],
                set_=summary_values,
            )
            await session.execute(stmt)
            await session.commit()
    except Exception as e:
        print(f"Failed to record error state for {code}:", e)


async def update_core_score(code: str, name_ja: str):
    """テクニカル指標＋MLモデルでスコアを算出する（Geminiに依存しない、REQUIREMENTS_v2.md 2.2参照）。

    Geminiのクォータ制約を一切受けないため、225銘柄全体を高速に巡回できる。
    """
    try:
        ticker = f"{code}.T"
        df = await asyncio.to_thread(yf.download, ticker, period="1y", interval="1d", progress=False)
        if df.empty:
            print(f"[CORE] {code}: yfinance returned no data")
            await _mark_stock_as_errored(code)
            return

        has_multiindex_columns = isinstance(df.columns, tuple) or hasattr(df.columns, 'levels')
        close = (df['Close'].iloc[:, 0] if has_multiindex_columns else df['Close']).dropna()
        volume = (df['Volume'].iloc[:, 0] if has_multiindex_columns else df['Volume']).dropna()

        chart_row = None
        if len(close) >= 5:
            ma5 = close.rolling(window=5).mean()
            ma25 = close.rolling(window=25).mean()
            labels = [d.strftime("%Y/%m/%d") for d in close.index]
            prices = [float(x) if not str(x).lower() == 'nan' else None for x in close.values]
            ma5_vals = [float(x) if not str(x).lower() == 'nan' else None for x in ma5.values]
            ma25_vals = [float(x) if not str(x).lower() == 'nan' else None for x in ma25.values]
            chart_row = {"labels": labels, "prices": prices, "ma5": ma5_vals, "ma25": ma25_vals}

        features = latest_feature_vector(close, volume)
        if features is None:
            # 上場間もない等で十分な履歴がない場合はニュートラル固定値にフォールバックする
            short_score, long_score = 50, 50
        else:
            short_score = predictor.score_from_technicals(features)
            predicted_return = predictor.predict_forward_return(features)
            long_score = predictor.score_from_return(predicted_return)

        # 投資スタイルは短期・長期を均等評価（REQUIREMENTS_v2.md 2.2/決定事項サマリー参照）。
        # バックテスト側（backtest_engine.py）と同じ関数を使い、ルールの再現性を担保する
        final_score = predictor.combine_scores(short_score, long_score)
        final_signal = predictor.classify_signal(final_score)

        # ファンダメンタルズ（PER/PBR/配当利回り/増益率）は画面表示専用の参考情報。
        # yfinanceでは「現在時点」の値しか取得できず過去に遡れないためML特徴量には
        # 使わない（REQUIREMENTS_v2.md 2.2参照）。取得失敗してもコアスコア自体は
        # 継続させたいので、独立したtry/exceptにする
        fundamentals_values = None
        try:
            info = await asyncio.to_thread(lambda: yf.Ticker(ticker).info)
            # yfinanceのdividendYieldは（バージョンにより挙動が変わってきた経緯があるが）
            # 実機検証の結果、既にパーセント表記（例: 2.36 = 2.36%）で返ることを確認済み。
            # 小数比率(0.0236)と誤解して100倍すると236%のような異常値になるため注意。
            fundamentals_values = dict(
                per=info.get("trailingPE"),
                pbr=info.get("priceToBook"),
                dividend_yield=info.get("dividendYield"),
                earnings_growth=info.get("earningsGrowth"),
                updated_at=_jst_now_str(),
            )
        except Exception as e:
            print(f"[CORE] {code}: fundamentals fetch failed: {e}")

        async with session_scope() as session:
            if chart_row is not None:
                stmt = pg_insert(ChartDataRow).values(stock_code=code, **chart_row)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[ChartDataRow.stock_code],
                    set_={k: getattr(stmt.excluded, k) for k in chart_row},
                )
                await session.execute(stmt)

            if fundamentals_values is not None:
                stmt = pg_insert(FundamentalsRow).values(stock_code=code, **fundamentals_values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[FundamentalsRow.stock_code],
                    set_=fundamentals_values,
                )
                await session.execute(stmt)

            summary_values = dict(
                short_score=short_score, long_score=long_score,
                final_score=final_score, final_signal=final_signal, updated_at=_jst_now_str(),
            )
            stmt = pg_insert(SignalSummaryRow).values(code=code, news_updated_at="", **summary_values)
            # news_updated_at は別の巡回ループ（Gemini側）が管理するため、ここでは更新しない
            stmt = stmt.on_conflict_do_update(
                index_elements=[SignalSummaryRow.code],
                set_=summary_values,
            )
            await session.execute(stmt)
            await session.commit()
    except Exception as e:
        print(f"update_core_score failed for {code}:", e)
        await _mark_stock_as_errored(code)
    finally:
        _CORE_PROCESSING.discard(code)


async def update_news_and_docs(code: str, name_ja: str):
    """Gemini APIでニュース・開示情報の分析を行う。コアスコアの算出はブロックしない

    （REQUIREMENTS_v2.md 2.3参照）。無料枠クォータの制約により低頻度でしか回らない。
    """
    try:
        raw_news = await asyncio.to_thread(ai_service.fetch_recent_news, name_ja)
        if not raw_news:
            raw_news = [{"title": f"{name_ja}に関する直近のニュースはありません", "url": "#", "source": "API"}]
        facts_news = await asyncio.to_thread(ai_service.extract_news_facts, code, name_ja, raw_news)
        news_results = internal_ai.score_news_facts(facts_news, raw_news)

        facts_docs = await asyncio.to_thread(ai_service.extract_docs_facts, code, name_ja)
        docs_results = internal_ai.score_docs_facts(facts_docs)

        async with session_scope() as session:
            await session.execute(delete(NewsItemRow).where(NewsItemRow.stock_code == code))
            session.add_all([
                NewsItemRow(stock_code=code, title=n.get("title", ""), source=n.get("source", ""),
                            url=n.get("url", "#"), effect=str(n.get("effect", "0")),
                            reason=n.get("reason", ""), cls=n.get("cls", "neu"))
                for n in news_results
            ])

            await session.execute(delete(DocItemRow).where(DocItemRow.stock_code == code))
            session.add_all([
                DocItemRow(stock_code=code, title=d.get("title", ""), type=d.get("type", "EDINET"),
                           url=d.get("url", "#"), effect=str(d.get("effect", "0")),
                           reason=d.get("reason", ""), cls=d.get("cls", "neu"))
                for d in docs_results
            ])

            # コアスコアの行がまだ存在しない場合に備え、必要な列にはニュートラル既定値を用意しつつ、
            # 既に行がある場合は news_updated_at 以外の列を上書きしない（コアスコアを壊さないため）
            news_updated_at = _jst_now_str()
            stmt = pg_insert(SignalSummaryRow).values(
                code=code, short_score=50, long_score=50,
                final_score=50, final_signal="analyzing...", updated_at="",
                news_updated_at=news_updated_at,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[SignalSummaryRow.code],
                set_={"news_updated_at": stmt.excluded.news_updated_at},
            )
            await session.execute(stmt)
            await session.commit()
    except Exception as e:
        print(f"update_news_and_docs failed for {code}:", e)
    finally:
        _NEWS_PROCESSING.discard(code)


async def update_news_and_docs_batch(stocks: list[tuple[str, str]]):
    """自律巡回専用: 複数銘柄をまとめて2回（ニュース1回＋開示1回）のGemini呼び出しで処理する。

    1銘柄ごとに2回呼ぶ`update_news_and_docs`（手動「最新化」ボタン用に維持）だと
    225銘柄で450リクエストになり無料枠クォータをすぐ使い切ってしまうため、
    巡回処理はこちらのバッチ版のみを使う（REQUIREMENTS_v2.md 2.3参照、目安15銘柄/リクエスト）。
    """
    stock_news: dict[str, list[dict]] = {}
    for code, name_ja in stocks:
        try:
            raw_news = await asyncio.to_thread(ai_service.fetch_recent_news, name_ja)
        except Exception as e:
            print(f"[NEWS_CRAWLER] {code}: RSS fetch failed: {e}")
            raw_news = []
        if not raw_news:
            raw_news = [{"title": f"{name_ja}に関する直近のニュースはありません", "url": "#", "source": "API"}]
        stock_news[code] = raw_news

    news_batch_input = [{"code": code, "name_ja": name_ja, "news": stock_news[code]} for code, name_ja in stocks]
    facts_by_code = await asyncio.to_thread(ai_service.extract_news_facts_batch, news_batch_input)

    docs_batch_input = [{"code": code, "name_ja": name_ja} for code, name_ja in stocks]
    docs_facts_by_code = await asyncio.to_thread(ai_service.extract_docs_facts_batch, docs_batch_input)

    news_updated_at = _jst_now_str()
    try:
        async with session_scope() as session:
            for code, name_ja in stocks:
                news_results = internal_ai.score_news_facts(facts_by_code.get(code, []), stock_news.get(code, []))
                docs_results = internal_ai.score_docs_facts(docs_facts_by_code.get(code, []))

                await session.execute(delete(NewsItemRow).where(NewsItemRow.stock_code == code))
                session.add_all([
                    NewsItemRow(stock_code=code, title=n.get("title", ""), source=n.get("source", ""),
                                url=n.get("url", "#"), effect=str(n.get("effect", "0")),
                                reason=n.get("reason", ""), cls=n.get("cls", "neu"))
                    for n in news_results
                ])

                await session.execute(delete(DocItemRow).where(DocItemRow.stock_code == code))
                session.add_all([
                    DocItemRow(stock_code=code, title=d.get("title", ""), type=d.get("type", "EDINET"),
                               url=d.get("url", "#"), effect=str(d.get("effect", "0")),
                               reason=d.get("reason", ""), cls=d.get("cls", "neu"))
                    for d in docs_results
                ])

                stmt = pg_insert(SignalSummaryRow).values(
                    code=code, short_score=50, long_score=50,
                    final_score=50, final_signal="analyzing...", updated_at="",
                    news_updated_at=news_updated_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[SignalSummaryRow.code],
                    set_={"news_updated_at": stmt.excluded.news_updated_at},
                )
                await session.execute(stmt)
            await session.commit()
    except Exception as e:
        print("update_news_and_docs_batch failed:", e)
    finally:
        for code, _ in stocks:
            _NEWS_PROCESSING.discard(code)


async def update_macro_news():
    """個別銘柄に紐づかない市場全体・マクロ・地政学ニュースを収集・分析する。

    スコア計算には一切使わず、判定根拠の補助表示専用（REQUIREMENTS_v2.md 2.5参照、2026-07-21改訂）。
    全銘柄共通の単一リストのため、銘柄ごとの巡回とは別に低頻度で1回だけ実行すればよい。
    """
    try:
        raw_news = await asyncio.to_thread(ai_service.fetch_macro_news)
        if not raw_news:
            return
        facts = await asyncio.to_thread(ai_service.extract_macro_facts, raw_news)
        results = internal_ai.score_macro_facts(facts, raw_news)

        async with session_scope() as session:
            await session.execute(delete(MacroNewsItemRow))
            session.add_all([
                MacroNewsItemRow(title=n.get("title", ""), source=n.get("source", ""),
                                  url=n.get("url", "#"), effect=str(n.get("effect", "0")),
                                  reason=n.get("reason", ""), cls=n.get("cls", "neu"))
                for n in results
            ])
            await session.commit()
    except Exception as e:
        print("update_macro_news failed:", e)


async def update_backtest_result(code: str):
    """過去データに対し本番と同じスコアリングルールを再現し、実際の売買をシミュレートする。

    yfinanceでの5年分データ取得＋特徴量計算＋モデル推論をすべて含むため、
    コアスコア（数秒）と比べて1銘柄あたり数秒〜十数秒程度かかる。
    Geminiクォータには関係しないが、CPU負荷が高いため独立した低頻度ループで回す
    （REQUIREMENTS_v2.md 2.2/3.3参照）。
    """
    try:
        result = await asyncio.to_thread(backtest_engine.run_backtest, code)
        if result is None:
            print(f"[BACKTEST] {code}: insufficient data, skipped")
            return

        async with session_scope() as session:
            values = dict(
                trades=result["trades"], win_rate=result["win_rate"],
                avg_return=result["avg_return"], max_drawdown=result["max_drawdown"],
                updated_at=_jst_now_str(),
            )
            stmt = pg_insert(BacktestResultRow).values(stock_code=code, **values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[BacktestResultRow.stock_code],
                set_=values,
            )
            await session.execute(stmt)
            await session.commit()
    except Exception as e:
        print(f"update_backtest_result failed for {code}:", e)
    finally:
        _BACKTEST_PROCESSING.discard(code)


async def autonomous_core_crawler():
    """テクニカル+MLでコアスコアを高速に巡回更新するループ（Geminiクォータの影響を受けない）。"""
    # 長期投資中心・日次更新で十分という方針（REQUIREMENTS_v2.md 5.1/5.7）に対し、
    # 3秒間隔（225銘柄を約11分で一周）は過剰だったため30秒に緩和した
    # （225銘柄で約1.9時間の一周。それでも日次更新の要件を十分満たす）。
    sleep_duration = 30.0
    while True:
        if MASTER_STOCKS:
            async with session_scope() as session:
                summaries = {
                    r.code: r for r in (await session.execute(select(SignalSummaryRow))).scalars().all()
                }

            stock_queue = []
            for s in MASTER_STOCKS:
                if s.code in _CORE_PROCESSING:
                    continue
                summary = summaries.get(s.code)
                timestamp = _parse_jst(summary.updated_at) if summary else 0.0
                stock_queue.append((s, timestamp))

            if stock_queue:
                stock_queue.sort(key=lambda x: x[1])
                target_stock = stock_queue[0][0]
                _CORE_PROCESSING.add(target_stock.code)
                print(f"[CORE_CRAWLER] Auto-updating: {target_stock.code}")
                # 2026-07-21改訂: asyncio.create_task（fire-and-forget）だと、1件の処理が
                # sleep_durationより長くかかった場合に次々とタスクが積み上がり、非力なVM
                # （1/8 OCPU）でリソース枯渇を起こすリスクがあった。await で逐次実行することで
                # 「常に同時実行数は最大1」を保証する（一周の所要時間は伸びるが、日次更新で
                # 十分という方針には影響しない）。
                await update_core_score(target_stock.code, target_stock.name_ja)

        await asyncio.sleep(sleep_duration)


async def autonomous_news_crawler():
    """Gemini APIでニュース・開示情報を巡回更新するループ（動的レートリミット保護つき）。

    複数銘柄をまとめて1回のGemini呼び出しで処理するバッチ方式
    （REQUIREMENTS_v2.md 2.3参照、2026-07-21改訂）。
    """
    sleep_duration = 16.0
    while True:
        if MASTER_STOCKS:
            key_count = len(ai_service.get_keys())
            if key_count == 0:
                await asyncio.sleep(60)
                continue

            # 1日あたりの最大安全「バッチ」数。
            # 実際のGemini無料枠のクォータ上限は環境依存・モデル依存で変わりうるため
            # 環境変数で上書き可能にする（2026-07-15時点、gemini-3.5-flashの無料枠で
            # 実測した上限は「1キーあたり1日20リクエスト」だった。当初の想定=1500は誤り）。
            daily_quota_per_key = int(os.getenv("GEMINI_DAILY_REQUEST_QUOTA_PER_KEY", "20"))
            # 1バッチでニュース・開示情報の2回Gemini APIを消費する（銘柄数に関わらず一定）
            max_batches_per_day = key_count * max(1, daily_quota_per_key // 2)
            # 1バッチあたりの猶予時間（1日の秒数 86400 / 処理可能バッチ数）に 10% の安全バッファを掛ける
            safe_sleep_seconds = (86400 / max_batches_per_day) * 1.10
            sleep_duration = max(16.0, safe_sleep_seconds)

            async with session_scope() as session:
                summaries = {
                    r.code: r for r in (await session.execute(select(SignalSummaryRow))).scalars().all()
                }

            stock_queue = []
            for s in MASTER_STOCKS:
                if s.code in _NEWS_PROCESSING:
                    continue
                summary = summaries.get(s.code)
                timestamp = _parse_jst(summary.news_updated_at) if summary else 0.0
                stock_queue.append((s, timestamp))

            if stock_queue:
                stock_queue.sort(key=lambda x: x[1])
                batch = stock_queue[:ai_service.NEWS_BATCH_SIZE]
                target_stocks = [(s.code, s.name_ja) for s, _ in batch]
                for code, _ in target_stocks:
                    _NEWS_PROCESSING.add(code)
                print(f"[NEWS_CRAWLER] Auto-updating batch of {len(target_stocks)}: "
                      f"{[c for c, _ in target_stocks]} (Wait: {sleep_duration:.1f}s)")
                # 2026-07-21改訂: 同時実行数を最大1に保つためawaitで逐次実行する
                # （autonomous_core_crawler参照。理由も同様）
                await update_news_and_docs_batch(target_stocks)

        await asyncio.sleep(sleep_duration)


async def autonomous_macro_news_crawler():
    """市場全体・マクロ・地政学ニュースを低頻度で更新するループ。

    銘柄ごとの巡回とは異なり全銘柄共通の単一リストのため、頻繁に回す必要はない。
    Gemini呼び出しを1回消費するだけだが、銘柄別ニュース巡回と同じクォータを
    共有するため、控えめな頻度（2時間に1回）に留める。
    """
    while True:
        if ai_service.get_keys():
            print("[MACRO_NEWS_CRAWLER] Updating macro/geopolitical news...")
            await update_macro_news()
        await asyncio.sleep(7200.0)


async def autonomous_backtest_crawler():
    """本番と同じルールを過去データに適用し、実際のバックテスト結果を巡回更新するループ。

    1銘柄あたりのCPUコストが高い（5年分の特徴量計算＋モデル推論＋バックテスト実行）ため、
    コアスコアの巡回より長い間隔で回す（2026-07-21改訂: 30秒→60秒。同時実行数制限とあわせ、
    非力なVM（1/8 OCPU）でのリソース枯渇を避けるため）。
    """
    sleep_duration = 60.0
    while True:
        if MASTER_STOCKS:
            async with session_scope() as session:
                results = {
                    r.stock_code: r for r in (await session.execute(select(BacktestResultRow))).scalars().all()
                }

            stock_queue = []
            for s in MASTER_STOCKS:
                if s.code in _BACKTEST_PROCESSING:
                    continue
                result = results.get(s.code)
                timestamp = _parse_jst(result.updated_at) if result else 0.0
                stock_queue.append((s, timestamp))

            if stock_queue:
                stock_queue.sort(key=lambda x: x[1])
                target_stock = stock_queue[0][0]
                _BACKTEST_PROCESSING.add(target_stock.code)
                print(f"[BACKTEST_CRAWLER] Auto-updating: {target_stock.code}")
                # 2026-07-21改訂: 同時実行数を最大1に保つためawaitで逐次実行する
                # （autonomous_core_crawler参照。理由も同様。特にバックテストは最も重い処理のため重要）
                await update_backtest_result(target_stock.code)

        await asyncio.sleep(sleep_duration)


async def master_data_updater():
    """6時間ごとに225銘柄のリストを再取得し検証する"""
    while True:
        await asyncio.sleep(6 * 3600)  # 6 hours
        print("[UPDATER] Re-fetching Nikkei 225 Master Data...")
        try:
            await asyncio.to_thread(fetch_nikkei225.fetch_nikkei_225)
            await sync_master_data_from_json_to_db()
            await load_master_stocks_into_memory()
            print("[UPDATER] Master Data updated successfully.")
        except Exception as e:
            print("[UPDATER] Failed to update Master Data:", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_master_data()
    # 自律クローラータスクの起動（コアスコア・ニュース分析・バックテストは独立したループ。REQUIREMENTS_v2.md 2.2/2.3参照）
    core_crawler_task = asyncio.create_task(autonomous_core_crawler())
    news_crawler_task = asyncio.create_task(autonomous_news_crawler())
    backtest_crawler_task = asyncio.create_task(autonomous_backtest_crawler())
    macro_news_crawler_task = asyncio.create_task(autonomous_macro_news_crawler())
    updater_task = asyncio.create_task(master_data_updater())
    yield
    macro_news_crawler_task.cancel()
    core_crawler_task.cancel()
    news_crawler_task.cancel()
    backtest_crawler_task.cancel()
    updater_task.cancel()


app = FastAPI(title="Japan Stock Signal Platform API", lifespan=lifespan)

# --------- CORS ---------
# 本番ではフロント(Cloudflare Workers)とバック(DuckDNS)がオリジンが異なるため
# 明示的なオリジン指定が必須（ワイルドカード"*"は使えない）。認証はCookieではなく
# Authorizationヘッダーのトークン方式のため allow_credentials は必須ではないが、
# 害もないため維持する（2026-07-16改訂）。
_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra_origins = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Auth ---------
app.include_router(auth.router)
api = APIRouter(dependencies=[Depends(auth.require_auth)])

# --------- Endpoints ---------
@app.get("/")
def read_root():
    return {"message": "Japan Stock Signal API is running"}

@api.get("/api/stocks", response_model=List[StockMaster])
def get_stocks():
    return MASTER_STOCKS

@api.get("/api/stocks/{code}/summary", response_model=SignalSummary)
async def get_stock_summary(code: str, background_tasks: BackgroundTasks, session=Depends(get_session)):
    row = await session.get(SignalSummaryRow, code)
    if row and row.final_signal != "analyzing...":
        return SignalSummary(
            code=row.code, short_score=row.short_score, long_score=row.long_score,
            final_score=row.final_score,
            final_signal=row.final_signal, updated_at=row.updated_at,
        )

    stock = next((s for s in MASTER_STOCKS if s.code == code), None)
    name_ja = stock.name_ja if stock else "該当銘柄"

    # コアスコアはGeminiに依存しないため高速（数秒程度）。行が存在しない場合だけでなく、
    # 行はあってもfinal_signalが"analyzing..."のまま（ニュース巡回側の upsert が先に行を
    # 作った等）の場合も対象にする。そうしないと、低頻度なコアスコア巡回ループ
    # （autonomous_core_crawler）が偶然この銘柄に到達するまで、永遠に「分析中」が
    # 表示され続けてしまう（REQUIREMENTS_v2.md 5.3参照）。
    # ニュース/開示分析（Gemini）はここではトリガーせず、別ループの巡回のみに任せる
    # （クォータが極めて限られているため、閲覧操作から消費しないようにする。REQUIREMENTS_v2.md 5.1参照）
    if code not in _CORE_PROCESSING:
        _CORE_PROCESSING.add(code)
        background_tasks.add_task(update_core_score, code, name_ja)

    return SignalSummary(
        code=code, short_score=0, long_score=0,
        final_score=0, final_signal="analyzing...",
        updated_at="推論中"
    )

@api.post("/api/stocks/{code}/refresh", response_model=SignalSummary)
async def refresh_stock_summary(code: str, session=Depends(get_session)):
    """「最新化」ボタン専用: コアスコア（テクニカル+ML）とニュース/開示分析の両方をその場で再計算する。

    コアスコアはGeminiクォータの制約を受けないため常に即座に再計算する。
    ニュース/開示分析はGemini無料枠のクォータが極めて限られているため、直近で
    取得済み（MANUAL_NEWS_REFRESH_COOLDOWN_SECONDS以内）の場合は連打・複数銘柄閲覧による
    クォータ浪費を防ぐためスキップし、既に取得済みの最新結果をそのまま返す
    （REQUIREMENTS_v2.md 5.1/6.3参照、2026-07-18改訂）。
    """
    stock = next((s for s in MASTER_STOCKS if s.code == code), None)
    name_ja = stock.name_ja if stock else "該当銘柄"

    if code not in _CORE_PROCESSING:
        _CORE_PROCESSING.add(code)
        await update_core_score(code, name_ja)

    existing_row = await session.get(SignalSummaryRow, code)
    now_ts = _parse_jst(_jst_now_str())
    news_is_fresh = (
        existing_row is not None
        and (now_ts - _parse_jst(existing_row.news_updated_at)) < MANUAL_NEWS_REFRESH_COOLDOWN_SECONDS
    )
    if code not in _NEWS_PROCESSING and not news_is_fresh:
        _NEWS_PROCESSING.add(code)
        await update_news_and_docs(code, name_ja)
        if existing_row is not None:
            # update_news_and_docs は別セッションでコミットするため、
            # このセッションのIDマップに残る古いオブジェクトを明示的に最新化する
            await session.refresh(existing_row)

    row = existing_row
    if row:
        return SignalSummary(
            code=row.code, short_score=row.short_score, long_score=row.long_score,
            final_score=row.final_score,
            final_signal=row.final_signal, updated_at=row.updated_at,
        )
    return SignalSummary(
        code=code, short_score=0, long_score=0,
        final_score=0, final_signal="analyzing...",
        updated_at="推論中"
    )

@api.get("/api/stocks/{code}/news", response_model=List[NewsInfo])
async def get_stock_news(code: str, session=Depends(get_session)):
    rows = (await session.execute(
        select(NewsItemRow).where(NewsItemRow.stock_code == code)
    )).scalars().all()
    if rows:
        return [
            NewsInfo(title=r.title, source=r.source, url=r.url, effect=r.effect, reason=r.reason, cls=r.cls)
            for r in rows
        ]
    return [NewsInfo(
        title="AIがニュースを収集中・分析中です...", source="System", url="#",
        effect="0", reason="しばらく経ってから再度ご確認ください", cls="neu"
    )]

@api.get("/api/macro-news", response_model=List[NewsInfo])
async def get_macro_news(session=Depends(get_session)):
    """個別銘柄に紐づかない市場全体・マクロ・地政学ニュース（全銘柄共通、判定根拠の補助表示専用）。"""
    rows = (await session.execute(select(MacroNewsItemRow))).scalars().all()
    if rows:
        return [
            NewsInfo(title=r.title, source=r.source, url=r.url, effect=r.effect, reason=r.reason, cls=r.cls)
            for r in rows
        ]
    return [NewsInfo(
        title="マクロ・地政学ニュースを収集中です...", source="System", url="#",
        effect="0", reason="しばらく経ってから再度ご確認ください", cls="neu"
    )]

@api.get("/api/stocks/{code}/docs", response_model=List[DocInfo])
async def get_stock_docs(code: str, session=Depends(get_session)):
    rows = (await session.execute(
        select(DocItemRow).where(DocItemRow.stock_code == code)
    )).scalars().all()
    if rows:
        return [
            DocInfo(title=r.title, type=r.type, url=r.url, effect=r.effect, reason=r.reason, cls=r.cls)
            for r in rows
        ]
    return [DocInfo(
        title="AIが開示資料を収集中・分析中です...", type="System", url="#",
        effect="0", reason="しばらく経ってから再度ご確認ください", cls="neu"
    )]

@api.get("/api/stocks/{code}/chart", response_model=ChartResponse)
async def get_stock_chart(code: str, session=Depends(get_session)):
    row = await session.get(ChartDataRow, code)
    if row:
        return ChartResponse(code=code, labels=row.labels, prices=row.prices, ma5=row.ma5, ma25=row.ma25)
    return ChartResponse(code=code, labels=[], prices=[], ma5=[], ma25=[])

@api.get("/api/stocks/{code}/fundamentals", response_model=FundamentalsResponse)
async def get_stock_fundamentals(code: str, session=Depends(get_session)):
    row = await session.get(FundamentalsRow, code)
    if row:
        return FundamentalsResponse(
            code=code, per=row.per, pbr=row.pbr,
            dividend_yield=row.dividend_yield, earnings_growth=row.earnings_growth, computed=True,
        )
    return FundamentalsResponse(code=code, computed=False)

@api.get("/api/stocks/{code}/backtest", response_model=BacktestResult)
async def get_stock_backtest(code: str, session=Depends(get_session)):
    row = await session.get(BacktestResultRow, code)
    if row:
        return BacktestResult(
            code=code, trades=row.trades, win_rate=row.win_rate,
            avg_return=row.avg_return, max_drawdown=row.max_drawdown, computed=True,
        )
    # まだ巡回が到達していない銘柄（1銘柄あたりのバックテストは重いため、
    # コアスコアと違って閲覧操作からトリガーはしない。REQUIREMENTS_v2.md 5.1参照）
    return BacktestResult(code=code, trades=0, win_rate=0, avg_return=0, max_drawdown=0, computed=False)

# 短期・中期・長期タブの切り替え用。短期=テクニカル(short_score)、長期=ML予測リターン(long_score)、
# 中期=両者を50:50で合成したfinal_score（既存のブレンドスコアをそのまま「中期」の目安として使う。
# REQUIREMENTS_v2.md 2.2参照。新たに中期専用のモデルは持たない）
_RANKING_TERM_SCORE_KEY = {
    "short": lambda s: s.short_score,
    "medium": lambda s: s.final_score,
    "long": lambda s: s.long_score,
}


@api.get("/api/recommendations", response_model=RankingResponse)
async def get_recommendations(term: str = "medium", session=Depends(get_session)):
    rows = (await session.execute(
        select(SignalSummaryRow).where(SignalSummaryRow.final_signal != "analyzing...")
    )).scalars().all()
    valid_stocks = [
        SignalSummary(code=r.code, short_score=r.short_score, long_score=r.long_score,
                       final_score=r.final_score,
                       final_signal=r.final_signal, updated_at=r.updated_at)
        for r in rows
    ]

    score_key = _RANKING_TERM_SCORE_KEY.get(term, _RANKING_TERM_SCORE_KEY["medium"])

    # スコアで降順ソート
    sorted_stocks = sorted(valid_stocks, key=score_key, reverse=True)

    # 買うべきランキング（スコア上位）
    top_buy = sorted_stocks[:5]

    # 売るべきランキング（スコア下位）- ascending order
    top_sell = sorted(valid_stocks, key=score_key, reverse=False)[:5]

    return RankingResponse(top_buy=top_buy, top_sell=top_sell)

app.include_router(api)

if __name__ == "__main__":
    import uvicorn
    # uvicorn main:app --reload
    uvicorn.run(app, host="127.0.0.1", port=8000)
