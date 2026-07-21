# c:/Stock_Price_Forecast/backend/backtest_engine.py
"""
過去の株価データに対し、本番と同じスコアリングロジック（predictor.py）を日次で
再現し、backtesting.pyで実際の売買をシミュレートする（REQUIREMENTS_v2.md 2章/3.3参照）。

1銘柄あたりの計算コスト（過去5年分の特徴量計算＋モデル推論）が高いため、
自律巡回処理（backend/main.pyのautonomous_backtest_crawler）からのみ呼び出す想定。
閲覧操作からのオンデマンド実行はしない（REQUIREMENTS_v2.md 5.1参照）。
"""

import pandas as pd
import yfinance as yf
from backtesting import Backtest, Strategy

import predictor
from features import FEATURE_NAMES, MIN_HISTORY_LENGTH, compute_feature_frame

HISTORY_PERIOD = "5y"


class _SignalStrategy(Strategy):
    """事前計算済みのSignal列（1=買い/-1=売り/0=何もしない）に従うだけの単純な執行ルール。

    スコアの計算自体はrun_backtest側で本番と同じpredictor.pyの関数を使って
    再現済みのため、ここでは「本番の最新化ロジックが過去に適用されていたら
    どうなっていたか」をそのまま執行するだけにしている。
    """

    def init(self):
        # self.I()を通さずself.data.Signalを直接参照すると、backtesting.pyの
        # 内部ループが列を日次インデックスに合わせて切り詰めてくれず、
        # signal[-1]が常に「データ全体の最終日」の値を返し続けてしまう
        # （＝実質1つの定数シグナルで全期間を判定してしまうバグになる）。
        # self.I()でラップすることで、他の組み込みOHLCV列と同様に
        # 「現在の日までのシグナル」として正しく日次インデックスされる。
        self.signal = self.I(lambda: self.data.Signal, name="signal")

    def next(self):
        if self.signal[-1] == 1 and not self.position:
            self.buy()
        elif self.signal[-1] == -1 and self.position:
            self.position.close()


def _extract_ohlcv(df: pd.DataFrame) -> dict[str, pd.Series]:
    """yfinanceのMultiIndex列（単一銘柄でも列がMultiIndexになる場合がある）を吸収する。"""
    has_multiindex_columns = isinstance(df.columns, tuple) or hasattr(df.columns, 'levels')
    return {
        name: (df[name].iloc[:, 0] if has_multiindex_columns else df[name]).dropna()
        for name in ("Open", "High", "Low", "Close", "Volume")
    }


def run_backtest(code: str) -> dict | None:
    """1銘柄分のバックテストを実行する。データ不足・実行失敗時はNoneを返す。"""
    ticker = f"{code}.T"
    df = yf.download(ticker, period=HISTORY_PERIOD, interval="1d", progress=False)
    if df.empty or len(df) < MIN_HISTORY_LENGTH + 30:
        return None

    ohlcv = _extract_ohlcv(df)
    close, volume = ohlcv["Close"], ohlcv["Volume"]

    feature_frame = compute_feature_frame(close, volume).dropna()
    if len(feature_frame) < 30:
        return None

    model = predictor.get_model()
    x = feature_frame[FEATURE_NAMES]
    predicted_returns = model.predict(x) if model is not None else x["ma5_ratio"].to_numpy()

    # 本番(main.py update_core_score)と全く同じ関数でスコア・シグナルを再現する
    signals = []
    for i, predicted_return in enumerate(predicted_returns):
        row = feature_frame.iloc[i]
        short_score = predictor.score_from_technicals(row.to_dict())
        long_score = predictor.score_from_return(float(predicted_return))
        final_score = predictor.combine_scores(short_score, long_score)
        final_signal = predictor.classify_signal(final_score)
        signals.append(1 if final_signal == "buy" else (-1 if final_signal == "sell" else 0))

    idx = feature_frame.index
    price_data = pd.DataFrame({
        "Open": ohlcv["Open"].reindex(idx),
        "High": ohlcv["High"].reindex(idx),
        "Low": ohlcv["Low"].reindex(idx),
        "Close": close.reindex(idx),
        "Volume": volume.reindex(idx),
        "Signal": signals,
    }).dropna()

    if len(price_data) < 30:
        return None

    try:
        bt = Backtest(price_data, _SignalStrategy, cash=1_000_000, commission=.001, exclusive_orders=True)
        stats = bt.run()
    except Exception as e:
        print(f"[BACKTEST] {code}: backtest execution failed: {e}")
        return None

    trades = int(stats["# Trades"])
    win_rate = float(stats["Win Rate [%]"]) if trades > 0 else 0.0
    avg_return = float(stats["Avg. Trade [%]"]) if trades > 0 else 0.0
    max_drawdown = float(stats["Max. Drawdown [%]"]) if pd.notna(stats["Max. Drawdown [%]"]) else 0.0

    return {
        "trades": trades,
        "win_rate": round(win_rate, 1),
        "avg_return": round(avg_return, 2),
        "max_drawdown": round(max_drawdown, 2),
    }
