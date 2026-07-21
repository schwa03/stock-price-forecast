# c:/Stock_Price_Forecast/backend/train_model.py
"""
コアスコア用MLモデルの学習スクリプト（REQUIREMENTS_v2.md 2.2参照）。

常時学習するのではなく、このスクリプトを手動またはスケジュール実行（例: 週1回）して
モデルファイル（model/predictor.txt）を再生成する。日々の巡回処理は学習済みモデルを
読み込んで推論するだけなので、Gemini同様の無料枠クォータ制約を受けない。

実行方法（VM上）:
    docker compose run --rm backend python train_model.py
"""

import json
import os
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd
import yfinance as yf

from features import FEATURE_NAMES, compute_feature_frame

# 長期投資中心の方針に合わせ、約1ヶ月（20営業日）先のリターンを予測対象にする
FORWARD_DAYS = 20
HISTORY_PERIOD = "3y"
MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
MODEL_PATH = os.path.join(MODEL_DIR, "predictor.txt")
PERCENTILE_PATH = os.path.join(MODEL_DIR, "predictor_percentiles.json")


def load_master_stock_codes() -> list[str]:
    json_path = os.path.join(os.path.dirname(__file__), "nikkei225.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [item["code"] for item in data]


def build_training_samples(code: str) -> pd.DataFrame | None:
    """1銘柄分の(特徴量, ラベル)サンプルを、過去の全時点について作る。"""
    ticker = f"{code}.T"
    try:
        df = yf.download(ticker, period=HISTORY_PERIOD, interval="1d", progress=False)
    except Exception as e:
        print(f"  [skip] {code}: yfinance download failed: {e}")
        return None
    if df.empty:
        print(f"  [skip] {code}: no data")
        return None

    has_multiindex_columns = isinstance(df.columns, tuple) or hasattr(df.columns, "levels")
    close = (df["Close"].iloc[:, 0] if has_multiindex_columns else df["Close"]).dropna()
    volume = (df["Volume"].iloc[:, 0] if has_multiindex_columns else df["Volume"]).dropna()
    if len(close) < 100:
        print(f"  [skip] {code}: insufficient history ({len(close)} rows)")
        return None

    features = compute_feature_frame(close, volume)
    forward_return = close.shift(-FORWARD_DAYS) / close - 1

    sample = features.copy()
    sample["label"] = forward_return
    sample = sample.dropna()
    return sample


def main():
    codes = load_master_stock_codes()
    print(f"Building training samples from {len(codes)} stocks (period={HISTORY_PERIOD})...")

    all_samples = []
    for i, code in enumerate(codes):
        sample = build_training_samples(code)
        if sample is not None and not sample.empty:
            all_samples.append(sample)
        if (i + 1) % 20 == 0:
            print(f"  ...{i + 1}/{len(codes)} stocks processed")

    if not all_samples:
        print("ERROR: no training samples were built. Aborting.")
        sys.exit(1)

    dataset = pd.concat(all_samples, ignore_index=True)
    print(f"Total training samples: {len(dataset)}")

    # 時系列データなのでシャッフルせず、末尾20%を検証用に分ける
    split_idx = int(len(dataset) * 0.8)
    train_df = dataset.iloc[:split_idx]
    valid_df = dataset.iloc[split_idx:]

    train_set = lgb.Dataset(train_df[FEATURE_NAMES], label=train_df["label"])
    valid_set = lgb.Dataset(valid_df[FEATURE_NAMES], label=valid_df["label"], reference=train_set)

    params = {
        "objective": "regression",
        "metric": "mae",
        "verbosity": -1,
        "num_leaves": 15,
        "learning_rate": 0.05,
        "min_data_in_leaf": 50,
    }

    booster = lgb.train(
        params,
        train_set,
        num_boost_round=500,
        valid_sets=[valid_set],
        callbacks=[lgb.early_stopping(stopping_rounds=30), lgb.log_evaluation(period=50)],
    )

    os.makedirs(MODEL_DIR, exist_ok=True)
    booster.save_model(MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    preds = booster.predict(valid_df[FEATURE_NAMES])
    mae = (preds - valid_df["label"]).abs().mean()
    print(f"Validation MAE (predicted vs actual {FORWARD_DAYS}-day return): {mae:.4f}")
    print(f"Validation prediction range: min={preds.min():.4f} max={preds.max():.4f} mean={preds.mean():.4f}")

    # 予測リターンを0-100スコアに変換する際の較正データ（predictor.score_from_return参照）。
    # 検証用データ（学習に使っていない、時系列で後ろ20%）への予測分布を使うことで、
    # モデルの予測に系統的な偏り（例: 学習期間が強気相場だったため予測が全体的にプラスに
    # 寄る）があっても、実運用時の推論と同じ条件でのパーセンタイルを較正できる。
    percentile_ranks = list(range(0, 101, 5))
    percentile_values = np.percentile(preds, percentile_ranks).tolist()
    with open(PERCENTILE_PATH, "w", encoding="utf-8") as f:
        json.dump({"percentile_ranks": percentile_ranks, "percentile_values": percentile_values}, f)
    print(f"Percentile calibration saved to {PERCENTILE_PATH}")


if __name__ == "__main__":
    main()
