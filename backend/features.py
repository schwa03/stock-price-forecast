# c:/Stock_Price_Forecast/backend/features.py
"""
テクニカル指標の計算（学習・推論の両方から共有される）。

Geminiに依存しないため無料枠クォータの制約を受けない（REQUIREMENTS_v2.md 2.1/2.2参照）。
pandas-ta等の外部ライブラリは使わず、pandasのrolling/ewm操作のみで計算する
（numba依存を避けるため。REQUIREMENTS_v2.md 1.1/1.2参照）。
"""

import pandas as pd

# 最も長い指標（MA75）を安定して計算するために必要な最小データ点数
MIN_HISTORY_LENGTH = 75

FEATURE_NAMES = [
    "ma5_ratio",
    "ma25_ratio",
    "ma75_ratio",
    "rsi14",
    "macd_hist",
    "bb_percent_b",
    "volume_change",
]


def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50.0)
    # avg_loss=0（窓内に下落日が皆無の強い上昇トレンド）の場合、上の式ではNaN経由で
    # 中立(50)に丸められてしまうが、理論上のRSIは100（最大の買われすぎ）が正しいため補正する。
    # avg_gainも0（値動きが全くない）の場合は中立50のままで問題ない
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    return rsi


def _macd_histogram(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def _bollinger_percent_b(close: pd.Series, length: int = 20, num_std: float = 2.0) -> pd.Series:
    mid = close.rolling(length).mean()
    std = close.rolling(length).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    band_width = (upper - lower).replace(0, pd.NA)
    return ((close - lower) / band_width).fillna(0.5)


def compute_feature_frame(close: pd.Series, volume: pd.Series) -> pd.DataFrame:
    """終値・出来高の時系列全体から、各時点の特徴量をまとめて計算する。

    学習時（過去の全時点から大量のサンプルを作る）・推論時（最新1行だけ使う）の両方で
    このDataFrameをそのまま使う。
    """
    ma5 = close.rolling(5).mean()
    ma25 = close.rolling(25).mean()
    ma75 = close.rolling(75).mean()
    volume_avg20 = volume.rolling(20).mean()

    df = pd.DataFrame({
        # 移動平均との乖離率（絶対価格ではなく比率にすることで銘柄間のスケール差を吸収する）
        "ma5_ratio": close / ma5 - 1,
        "ma25_ratio": close / ma25 - 1,
        "ma75_ratio": close / ma75 - 1,
        "rsi14": _rsi(close, 14),
        "macd_hist": _macd_histogram(close),
        "bb_percent_b": _bollinger_percent_b(close),
        "volume_change": volume / volume_avg20.replace(0, pd.NA) - 1,
    })
    return df


def latest_feature_vector(close: pd.Series, volume: pd.Series) -> dict | None:
    """推論用: 最新時点の特徴量を1件のdictとして返す。データが不足していればNone。"""
    if len(close) < MIN_HISTORY_LENGTH:
        return None
    frame = compute_feature_frame(close, volume)
    last_row = frame.iloc[-1]
    if last_row.isna().any():
        return None
    return {name: float(last_row[name]) for name in FEATURE_NAMES}
