# Oracle Cloud Always Free（Ampere/ARM, linux/arm64）での動作を前提とした
# バックエンド用イメージ。python公式イメージはlinux/arm64のマルチアーキ対応済み。
FROM python:3.12-slim AS base

WORKDIR /app

# レイヤーキャッシュを効かせるため依存関係だけ先にコピー
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUTF8=1
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# uvicorn[standard]（uvloop等）は使わず素のasyncioループで起動する
# （REQUIREMENTS_v2.md 1.1 / 1.2 のARM互換性リスク低減方針に合わせる）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
