# c:/Stock_Price_Forecast/backend/models.py
"""
DB永続化用のSQLAlchemyモデル（REQUIREMENTS_v2.md 5.5参照）。

main.pyの既存Pydanticスキーマ（StockMaster / SignalSummary / NewsInfo / DocInfo /
ChartResponse）に対応する永続化テーブル。
"""

from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class StockMasterRow(Base):
    __tablename__ = "stock_master"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name_ja: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str] = mapped_column(String(255), default="")
    sector: Mapped[str] = mapped_column(String(255), default="")


class SignalSummaryRow(Base):
    __tablename__ = "signal_summary"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    short_score: Mapped[int] = mapped_column(Integer)
    long_score: Mapped[int] = mapped_column(Integer)
    final_score: Mapped[int] = mapped_column(Integer)
    final_signal: Mapped[str] = mapped_column(String(16))
    # 既存フロントの `updated_at.split(' ')[1]` 前提を崩さないため、
    # フェーズ1では現行と同じ "YYYY-MM-DD HH:MM:SS" 文字列のまま保持する。
    # DateTime型への変更はフェーズ2以降、フロント側の表示ロジックと合わせて検討する。
    updated_at: Mapped[str] = mapped_column(String(32), default="")
    # コアスコア（テクニカル+ML）とニュース/開示分析（Gemini）は別々の巡回ループで
    # 更新するため、鮮度を別々に追跡する（REQUIREMENTS_v2.md 2.2/2.3参照）
    news_updated_at: Mapped[str] = mapped_column(String(32), default="")


class NewsItemRow(Base):
    __tablename__ = "news_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(1024))
    source: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048))
    effect: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(1024))
    cls: Mapped[str] = mapped_column(String(16))


class DocItemRow(Base):
    __tablename__ = "doc_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(1024))
    type: Mapped[str] = mapped_column(String(32))
    url: Mapped[str] = mapped_column(String(2048))
    effect: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(1024))
    cls: Mapped[str] = mapped_column(String(16))


class MacroNewsItemRow(Base):
    """個別銘柄に紐づかない市場全体・マクロ・地政学ニュース（REQUIREMENTS_v2.md 2.5参照）。

    stock_codeを持たない単一の共有リストとして全銘柄画面から参照される。
    """
    __tablename__ = "macro_news_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(1024))
    source: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048))
    effect: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(1024))
    cls: Mapped[str] = mapped_column(String(16))


class FundamentalsRow(Base):
    """PER・PBR・配当利回り・増収増益率（画面表示用の参考情報。REQUIREMENTS_v2.md 2.2参照）。

    現在時点の値しかyfinanceから無料で取得できず、過去時点ごとの値は遡れないため
    ML特徴量には組み込めない（学習データに未来情報が混入するリークになるため）。
    """
    __tablename__ = "fundamentals"

    stock_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    per: Mapped[float | None] = mapped_column(Float, nullable=True)
    pbr: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    earnings_growth: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[str] = mapped_column(String(32), default="")


class BacktestResultRow(Base):
    __tablename__ = "backtest_result"

    stock_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[str] = mapped_column(String(32), default="")


class ChartDataRow(Base):
    __tablename__ = "chart_data"

    stock_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    labels: Mapped[list] = mapped_column(JSONB)
    prices: Mapped[list] = mapped_column(JSONB)
    ma5: Mapped[list] = mapped_column(JSONB)
    ma25: Mapped[list] = mapped_column(JSONB)
