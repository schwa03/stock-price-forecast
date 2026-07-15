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
import fetch_nikkei225
import internal_ai
from db import get_session, session_scope
from models import ChartDataRow, DocItemRow, NewsItemRow, SignalSummaryRow, StockMasterRow


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
    risk_score: int
    final_score: int
    final_signal: str
    updated_at: str = ""

class RankingResponse(BaseModel):
    top_buy: List[SignalSummary]
    bottom_buy: List[SignalSummary]
    top_sell: List[SignalSummary]
    bottom_sell: List[SignalSummary]  # buy / neutral / sell

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

class ChartResponse(BaseModel):
    code: str
    labels: List[str]
    prices: List[Optional[float]]
    ma5: List[Optional[float]]
    ma25: List[Optional[float]]

# --------- Global State ---------
# 銘柄マスターは高速な一覧表示のためインメモリにも保持するが、
# 正本はDB（stock_master）。再起動時はDBから読み直す（REQUIREMENTS_v2.md 5.5）。
MASTER_STOCKS: List[StockMaster] = []
# 「処理中」フラグは一時的な状態でしかないため、これだけは引き続きインメモリで良い。
_PROCESSING: set = set()


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
async def process_stock_background(code: str, name_ja: str):
    """yfinance, News, Docs を処理し、結果をDBに保存する。"""
    try:
        short_score = 50
        chart_row = None

        # 1. Chart / Technicals（yfinanceはブロッキングI/OのためThreadに逃がす）
        try:
            ticker = f"{code}.T"
            df = await asyncio.to_thread(yf.download, ticker, period="6mo", interval="1d", progress=False)
            if not df.empty:
                has_multiindex_columns = isinstance(df.columns, tuple) or hasattr(df.columns, 'levels')
                close_col = df['Close'].iloc[:, 0] if has_multiindex_columns else df['Close']
                close_prices = close_col.dropna()
                if len(close_prices) >= 5:
                    ma5 = close_prices.rolling(window=5).mean()
                    ma25 = close_prices.rolling(window=25).mean()

                    labels = [d.strftime("%Y/%m/%d") for d in close_prices.index]
                    prices = [float(x) if not str(x).lower() == 'nan' else None for x in close_prices.values]
                    ma5_vals = [float(x) if not str(x).lower() == 'nan' else None for x in ma5.values]
                    ma25_vals = [float(x) if not str(x).lower() == 'nan' else None for x in ma25.values]

                    chart_row = {"labels": labels, "prices": prices, "ma5": ma5_vals, "ma25": ma25_vals}

                    last_price = close_prices.values[-1]
                    if last_price > ma5.values[-1]:
                        short_score = 75
                    else:
                        short_score = 40
        except Exception as e:
            print("Background yfinance error:", e)

        # 2. News Facts & Scoring（外部I/OはThreadに逃がす）
        raw_news = await asyncio.to_thread(ai_service.fetch_recent_news, name_ja)
        if not raw_news:
            raw_news = [{"title": f"{name_ja}に関する直近のニュースはありません", "url": "#", "source": "API"}]

        facts_news = await asyncio.to_thread(ai_service.extract_news_facts, code, name_ja, raw_news)
        news_results = internal_ai.score_news_facts(facts_news, raw_news)

        total_news_effect = 0
        for item in news_results:
            try:
                eff_str = str(item.get("effect", "0")).replace('+', '')
                total_news_effect += int(float(eff_str))
            except Exception:
                pass

        # 3. Docs Facts & Scoring
        facts_docs = await asyncio.to_thread(ai_service.extract_docs_facts, code, name_ja)
        docs_results = internal_ai.score_docs_facts(facts_docs)

        total_docs_effect = 0
        for d in docs_results:
            try:
                eff_str = str(d.get("effect", "0")).replace('+', '')
                total_docs_effect += int(float(eff_str))
            except Exception:
                pass

        # 4. Final Summary
        short_score = min(100, max(0, short_score + total_news_effect))
        long_score = min(100, max(0, 65 + total_docs_effect))
        final_score = int(short_score * 0.5 + long_score * 0.5)

        if final_score >= 60:
            final_signal = "buy"
        elif final_score <= 45:
            final_signal = "sell"
        else:
            final_signal = "neutral"

        jst_time = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")

        # 5. DBへ永続化（チャート・ニュース・開示・サマリー）
        async with session_scope() as session:
            if chart_row is not None:
                stmt = pg_insert(ChartDataRow).values(stock_code=code, **chart_row)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[ChartDataRow.stock_code],
                    set_={k: getattr(stmt.excluded, k) for k in chart_row},
                )
                await session.execute(stmt)

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

            summary_values = dict(
                short_score=short_score, long_score=long_score, risk_score=50,
                final_score=final_score, final_signal=final_signal, updated_at=jst_time,
            )
            stmt = pg_insert(SignalSummaryRow).values(code=code, **summary_values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[SignalSummaryRow.code],
                set_=summary_values,
            )
            await session.execute(stmt)

            await session.commit()
    finally:
        # 途中で例外が起きても _PROCESSING に残り続けないようにする
        # （元実装は正常終了時のみ解除しており、失敗時に銘柄が永久に再試行不能になるバグがあった）
        _PROCESSING.discard(code)


async def autonomous_crawler():
    """動的レートリミット保護つきのAI推論自律ループ"""
    sleep_duration = 16.0
    while True:
        if MASTER_STOCKS:
            key_count = len(ai_service.get_keys())
            if key_count == 0:
                await asyncio.sleep(60)
                continue

            # 1日あたりの最大安全処理数 (1キー=1500回制限。1銘柄でニュースと開示の2回消費 = 750銘柄/日)
            max_stocks_per_day = key_count * 750
            # 1銘柄あたりの猶予時間（1日の秒数 86400 / 処理可能数）に 10% の安全バッファを掛ける
            safe_sleep_seconds = (86400 / max_stocks_per_day) * 1.10

            # 全225銘柄を1時間(3600秒)で1巡させるために必要な目標間隔: 3600 / 225 = 16秒
            # ただし、無料枠が少ない場合は無料枠保護（safe_sleep_seconds）を絶対優先とし、1時間以上の猶予を許容する
            sleep_duration = max(16.0, safe_sleep_seconds)

            async with session_scope() as session:
                summaries = {
                    r.code: r for r in (await session.execute(select(SignalSummaryRow))).scalars().all()
                }

            stock_queue = []
            for s in MASTER_STOCKS:
                # 処理中のステータスや「推論中」のものはキューから除外
                summary = summaries.get(s.code)
                if s.code in _PROCESSING or (summary and summary.final_signal == "analyzing..."):
                    continue

                # キャッシュが存在しない、または未更新の場合は一番古い（0.0：無限の過去）として扱う
                if summary is None or not summary.updated_at or summary.updated_at == "推論中":
                    stock_queue.append((s, 0.0))
                else:
                    try:
                        # 時間文字列(例: 2026-04-13 00:30:25) をパースしてUnixタイムスタンプ化
                        dt = datetime.strptime(summary.updated_at, "%Y-%m-%d %H:%M:%S")
                        stock_queue.append((s, dt.timestamp()))
                    except Exception:
                        stock_queue.append((s, 0.0))

            if stock_queue:
                # タイムスタンプが古い（数字が小さい）順にソート。未検索（0.0）が最優先に来る。
                stock_queue.sort(key=lambda x: x[1])
                target_stock = stock_queue[0][0]

                _PROCESSING.add(target_stock.code)
                print(f"[CRAWLER] Auto-updating: {target_stock.code} (Wait: {sleep_duration:.1f}s)")
                # コルーチンをイベントループのタスクとしてスケジュールする
                # （元実装は asyncio.to_thread(...) の戻り値をawaitもcreate_taskもしておらず、
                #   実際にはバックグラウンド処理が一切実行されないバグがあった）
                asyncio.create_task(process_stock_background(target_stock.code, target_stock.name_ja))

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
    # 自律クローラータスクの起動
    crawler_task = asyncio.create_task(autonomous_crawler())
    updater_task = asyncio.create_task(master_data_updater())
    yield
    crawler_task.cancel()
    updater_task.cancel()


app = FastAPI(title="Japan Stock Signal Platform API", lifespan=lifespan)

# --------- CORS ---------
# 本番ではフロント(Cloudflare Pages)とバック(DuckDNS)がオリジンが異なるため
# allow_credentials=True + 明示的なオリジン指定が必須（ワイルドカード"*"は使えない）。
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
    if row:
        return SignalSummary(
            code=row.code, short_score=row.short_score, long_score=row.long_score,
            risk_score=row.risk_score, final_score=row.final_score,
            final_signal=row.final_signal, updated_at=row.updated_at,
        )

    stock = next((s for s in MASTER_STOCKS if s.code == code), None)
    name_ja = stock.name_ja if stock else "該当銘柄"

    if code not in _PROCESSING:
        _PROCESSING.add(code)
        background_tasks.add_task(process_stock_background, code, name_ja)

    return SignalSummary(
        code=code, short_score=0, long_score=0,
        risk_score=0, final_score=0, final_signal="analyzing...",
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

@api.get("/api/stocks/{code}/backtest", response_model=BacktestResult)
def get_stock_backtest(code: str):
    return BacktestResult(
        code=code, trades=45, win_rate=65.5, avg_return=2.3, max_drawdown=-12.5
    )

@api.get("/api/recommendations", response_model=RankingResponse)
async def get_recommendations(session=Depends(get_session)):
    rows = (await session.execute(
        select(SignalSummaryRow).where(SignalSummaryRow.final_signal != "analyzing...")
    )).scalars().all()
    valid_stocks = [
        SignalSummary(code=r.code, short_score=r.short_score, long_score=r.long_score,
                       risk_score=r.risk_score, final_score=r.final_score,
                       final_signal=r.final_signal, updated_at=r.updated_at)
        for r in rows
    ]

    # スコアで降順ソート
    sorted_stocks = sorted(valid_stocks, key=lambda x: x.final_score, reverse=True)

    # 買うべきランキング（スコア上位）
    top_buy = sorted_stocks[:5]

    # 売るべきランキング（スコア下位）- ascending order
    top_sell = sorted(valid_stocks, key=lambda x: x.final_score, reverse=False)[:5]

    # ワースト評価（買うべきでない＝実質売るべき銘柄、売るべきでない＝実質買うべき銘柄と同義だが
    # フロントで使い分け可能にしている）
    bottom_buy = top_sell
    bottom_sell = top_buy

    return RankingResponse(
        top_buy=top_buy,
        bottom_buy=bottom_buy,
        top_sell=top_sell,
        bottom_sell=bottom_sell
    )

app.include_router(api)

if __name__ == "__main__":
    import uvicorn
    # uvicorn main:app --reload
    uvicorn.run(app, host="127.0.0.1", port=8000)
