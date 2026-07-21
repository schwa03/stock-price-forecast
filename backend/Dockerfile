# Oracle Cloud Always Free VM用のバックエンドイメージ。
# 本命はAmpere/ARM(linux/arm64)だが、在庫状況により現在の本番はE2.1.Micro(amd64)で
# 稼働中（在庫確保後にARMへ移行予定）。python公式イメージは両アーキ対応済みで、
# CIでもarm64ビルドをQEMUで検証しているため、どちらでも動作する（REQUIREMENTS_v2.md 1.1/1.2参照）。
FROM python:3.12-slim AS base

WORKDIR /app

# LightGBMのコンパイル済みバイナリがOpenMPランタイム(libgomp.so.1)に依存するが、
# python:3.12-slimには含まれていないため明示的にインストールする
# （実際にVM上で "OSError: libgomp.so.1: cannot open shared object file" が発生し判明した）
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

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
