# c:/Stock_Price_Forecast/backend/predictor.py
"""
学習済みMLモデルの読み込みと推論（REQUIREMENTS_v2.md 2.2参照）。

Geminiに依存せず、学習済みモデルをローカルで読み込んで推論するだけなので
無料枠クォータの制約を受けない。モデルは train_model.py で事前に学習しておく。
"""

import json
import os

import lightgbm as lgb
import numpy as np
import pandas as pd

from features import FEATURE_NAMES

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model", "predictor.txt")
PERCENTILE_PATH = os.path.join(os.path.dirname(__file__), "model", "predictor_percentiles.json")

_model: lgb.Booster | None = None
_model_load_attempted = False
_percentile_data: dict | None = None
_percentile_load_attempted = False


def _load_model() -> lgb.Booster | None:
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    if os.path.exists(MODEL_PATH):
        try:
            _model = lgb.Booster(model_file=MODEL_PATH)
            print(f"[PREDICTOR] Loaded trained model from {MODEL_PATH}")
        except Exception as e:
            print(f"[PREDICTOR] Failed to load model: {e}")
            _model = None
    else:
        print(
            f"[PREDICTOR] No trained model found at {MODEL_PATH}. "
            "Run `python train_model.py` first. Falling back to a simple heuristic."
        )
    return _model


def is_model_trained() -> bool:
    return _load_model() is not None


def _load_percentiles() -> dict | None:
    """train_model.pyが検証用データへの予測から作成したパーセンタイル較正テーブルを読み込む。

    score_from_returnで絶対値ベースへのフォールバックが必要かどうかの判定にも使う。
    """
    global _percentile_data, _percentile_load_attempted
    if _percentile_load_attempted:
        return _percentile_data
    _percentile_load_attempted = True
    if os.path.exists(PERCENTILE_PATH):
        try:
            with open(PERCENTILE_PATH, encoding="utf-8") as f:
                _percentile_data = json.load(f)
        except Exception as e:
            print(f"[PREDICTOR] Failed to load percentile calibration: {e}")
            _percentile_data = None
    return _percentile_data


def predict_forward_return(feature_vector: dict) -> float:
    """学習済みモデルで将来（約1ヶ月先）のリターンを予測する。

    モデルが未学習の場合は、MA5からの乖離率をそのまま予測値の代用として使う
    フォールバック（学習前でもある程度意味のある挙動にするため）。
    """
    model = _load_model()
    if model is not None:
        x = pd.DataFrame([feature_vector])[FEATURE_NAMES]
        return float(model.predict(x)[0])
    return float(feature_vector.get("ma5_ratio", 0.0))


def score_from_return(predicted_return: float) -> int:
    """予測リターンを0-100スコアに変換する。

    2026-07-21改訂: 当初は+5%を満点・-5%を最低点とする絶対値ベースの線形マッピングだったが、
    実際のモデルで検証したところ、学習期間（直近3年）が全体的に上昇相場だったためモデルの予測が
    恒常的にプラス側へ偏り、「マイナスのリターン」を一度も予測しない銘柄が大半になっていた。
    結果、長期スコアが常に60点前後以上に張り付き、売り判定（45点以下）にほぼ到達できず、
    バックテストで「買ったきり一度も売りシグナルが出ない」という不自然な結果になっていた。
    このため、モデルの絶対的な予測値ではなく、train_model.pyが検証データへの予測から作成した
    パーセンタイル較正テーブルに対する相対順位でスコア化するよう変更した。モデルの予測全体に
    系統的な偏りがあっても、その中での相対的な強弱で買い/中立/売りが自然に分散する。
    較正テーブルがまだない（train_model.py未実行）場合は、従来の絶対値ベースにフォールバックする。
    """
    percentile_data = _load_percentiles()
    if percentile_data is None:
        score = 50 + (predicted_return / 0.05) * 50
        return max(0, min(100, round(score)))

    score = np.interp(
        predicted_return,
        percentile_data["percentile_values"],
        percentile_data["percentile_ranks"],
    )
    return max(0, min(100, round(float(score))))


def score_from_technicals(features: dict) -> int:
    """短期スコア: RSIをベースに、MACDヒストグラムの符号で微調整する単純なモメンタム指標。"""
    rsi = features["rsi14"]
    macd_adjustment = 5 if features["macd_hist"] > 0 else -5
    return max(0, min(100, round(rsi + macd_adjustment)))


def get_model() -> lgb.Booster | None:
    """読み込み済み（または未学習でNone）のモデルを取得する。backtest_engine.py等の外部から使う。"""
    return _load_model()


# 短期・長期スコアの合成と売買判定（REQUIREMENTS_v2.md 2.2: 50:50均等評価）。
# main.pyの本番スコアリングとbacktest_engine.pyの過去再現の両方から使い、
# ロジックが二重管理でずれないようにする。
BUY_THRESHOLD = 60
SELL_THRESHOLD = 45


def combine_scores(short_score: int, long_score: int) -> int:
    return round(short_score * 0.5 + long_score * 0.5)


def classify_signal(final_score: int) -> str:
    if final_score >= BUY_THRESHOLD:
        return "buy"
    if final_score <= SELL_THRESHOLD:
        return "sell"
    return "neutral"
