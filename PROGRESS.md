# 進捗管理ファイル

最終更新: 2026-07-15

## 現在のフェーズ

フェーズ1（インフラ移行）のうち、コード側で完結する部分はすべて実装・検証済み（下記変更履歴参照）。残るのはクラウドアカウント作成等の手動作業のみ（ユーザー側対応、下記チェックリストの[手動]項目）。

## 完了事項

- [2026-07-15] 既存アプリ（backend/frontend）の内容確認・現状把握
- [2026-07-15] 要件定義ドラフト v2 作成（インフラ構成・予測ロジック設計・開示データ方針）→ `REQUIREMENTS_v2.md`
- [2026-07-15] 機能一覧（技術スタックを含まないユーザー視点の機能リスト）作成 → `FEATURES.md`
- [2026-07-15] 作業ルール（要件定義・進捗ファイルの確認と更新を必須化）を `CLAUDE.md` に明文化
- [2026-07-15] 作業ルールに「要件定義ファイル更新時は事前に許可を取る」を追記
- [2026-07-15] 参照不要になった過去ファイル（`System_Detailed_Spec_JP.md` / `japan-stock-real-link-dashboard.html` / `方針(仮).docx`）を `archive/` フォルダへ移動
- [2026-07-15] 重複していた `FEATURE_LIST.md` を `FEATURES.md` に統合し、`archive/` へ移動
- [2026-07-15] `REQUIREMENTS_v2.md` にファイル構成（各ファイル・フォルダの役割）セクションを追記（ユーザー許可済み）
- [2026-07-15] 現行の要件・実装内容をレビューし、矛盾点7件を洗い出して `REQUIREMENTS_v2.md` 4節に記載（ユーザー許可済み）
- [2026-07-15] レビューで判明した課題への対処方針（オンデマンド評価の廃止、検索とフィルタの分離、キュー待ち表示、スケルトンUI、再起動をまたぐ永続化、AI障害時の劣化表示、バックテストの事前計算）を `REQUIREMENTS_v2.md` 5節として新設
- [2026-07-15] 5節の方針を `FEATURES.md` にも反映（文言調整・新規計画中項目の追加）
- [2026-07-15] 新たな確認事項 Q3（個別銘柄の手動即時再評価を許可するか）を `REQUIREMENTS_v2.md` 6節に追加
- [2026-07-15] Q1〜Q3をおすすめの方向性で決定し、`REQUIREMENTS_v2.md` 6節を「意思決定事項（解決済み）」に更新（自分専用+要認証+免責事項／フェーズ3段階／手動再評価は制限付き許可）（ユーザー許可済み）
- [2026-07-15] 新規要望を反映（ユーザー許可済み）:
  - チャート表示期間の切り替え（1年/6ヶ月/3ヶ月等）→ `REQUIREMENTS_v2.md` 2.6, `FEATURES.md` 3.1
  - 長期スコアへのニュース反映（時間減衰あり）→ `REQUIREMENTS_v2.md` 2.2
  - マクロ・地政学リスク／マクロ経済ニュースの分析追加 → `REQUIREMENTS_v2.md` 2.5, `FEATURES.md` 4/5
  - 投資スタイルを短期・長期均等評価（50:50）に変更（30:70から差し戻し）→ `REQUIREMENTS_v2.md` 2.2
  - 将来やりたい機能に優先度注記（通知・ML継続改善）→ `FEATURES.md` 10.1
- [2026-07-15] 詳細技術スタックを選定し `REQUIREMENTS_v2.md` 1.1 に追記（ユーザー許可済み）。主な選定: SQLAlchemy 2.0+Alembic, pandas-ta, LightGBM, backtesting.py, Cloudflare Access（認証）, Docker Compose, GitHub Actions, Ruff
- [2026-07-15] フェーズ1〜3の詳細タスクリストを `PROGRESS.md` に作成
- [2026-07-15] 技術スタックの互換性をWeb検証（ユーザー許可済み）。実害のある問題2件を発見し構成変更で解消:
  - Caddy+CloudflareプロキシでHTTP-01チャレンジが通らない問題 → Caddy廃止、Cloudflare Tunnelに変更
  - Cloudflare Accessの2サブドメイン構成でのCookie/CORS問題 → frontend/backendを単一オリジン化（Pages Functionsでプロキシ）、副次的に独自ドメイン購入も不要に
  - その他: LightGBMのARM対応は解決済みと確認、backtesting.pyのAGPLライセンスを記録、CIにarm64ビルド検証を追加
  - `REQUIREMENTS_v2.md` 1節・1.1節を更新、1.2節「技術スタック互換性の検証結果」を新設
- [2026-07-15] `PROGRESS.md` フェーズ1タスクを新構成（Cloudflare Tunnel／Pages Functions／独自ドメイン不要）に合わせて更新、手動作業に[手動]マークを追加
- [2026-07-15] Cloudflare Tunnelの公開ホスト名にも所有ドメイン（zone）が必須と判明し、前回の「独自ドメイン不要」という結論を訂正（ユーザー許可済み）。ユーザーの意向（ドメイン購入コストも避けたい、外部無料サーバーで完結させたい）を踏まえ、**DuckDNS＋Caddy＋自前認証の完全無料構成に最終変更**:
  - `REQUIREMENTS_v2.md` 1節・1.1節・1.2節を修正（Cloudflare Access/Tunnel関連の記載を置き換え）
  - `docker-compose.yml`: cloudflaredサービスをcaddyサービスに置き換え、`APP_PASSWORD`/`SESSION_SECRET`/`DUCKDNS_HOSTNAME`を追加
  - `Caddyfile` を新規作成（DuckDNSホスト名でのリバースプロキシ設定）
  - `.env.example` を更新（Cloudflare Tunnel関連の変数を削除、DuckDNS/認証関連の変数を追加）
  - `backend/requirements.txt` に `itsdangerous`（自前セッション認証用）を追加
- [2026-07-15] バックエンドのフェーズ1スキャフォールディングを作成し、既存venvで動作確認済み:
  - `backend/requirements.txt`（既存インストール済みバージョン＋新規依存を整理）
  - `backend/Dockerfile`（python:3.12-slim、arm64対応、uvicorn[standard]は使わない方針を反映）
  - `backend/pyproject.toml`（pytest/ruff設定）
  - `backend/tests/test_main.py`（スモークテスト。`pytest`実行し1件パス確認済み）
  - `.github/workflows/ci.yml`（backend lint+test、frontend lint+build、arm64 Dockerビルド検証の3ジョブ）
  - `.gitignore`（venv/.env等を除外。`nikkei225.json`は起動時フォールバック用に意図的にコミット対象のまま）
- [2026-07-15] フェーズ1のコード実装分をすべて完了（ユーザーから「設計の揺れがない部分は全部進めてよい」との指示を受けて実施）:
  - `backend/auth.py`: 自前セッション認証（`itsdangerous`署名付きCookie、`/api/auth/login`・`/logout`・`/status`）を実装。`backend/tests/test_auth.py`で4件のテストがパスすることを確認済み
  - `backend/db.py`: 非同期SQLAlchemyエンジン・セッション層（DATABASE_URL未設定でもimportが壊れない遅延初期化）
  - `backend/models.py`: `stock_master` / `signal_summary` / `news_item` / `doc_item` / `chart_data` の5テーブルを定義
  - `backend/alembic/`: 初期マイグレーション（`23932e3a65a8_initial_schema.py`）を作成。ローカルにPostgreSQLがないため手書きし、`alembic history`でリビジョングラフの整合性を確認済み（実DBへの適用はVM構築後に実施が必要）
  - `backend/main.py`: `_CACHE`等5つのインメモリ辞書をすべてDB読み書きに置き換え、`@app.on_event`をFastAPI lifespanハンドラに移行、CORSをクロスオリジンCookie対応（`allow_credentials`+明示オリジン+`FRONTEND_ORIGIN`環境変数）に変更、全データエンドポイントを`Depends(auth.require_auth)`で保護。あわせて実装済みコードの潜在バグ2件を修正（`asyncio.to_thread(...)`の戻り値を未awaitで実質何も実行されていなかった巡回処理／`load_master_data`が未定義関数を呼んでいた6時間ごとの銘柄マスター更新）
  - `frontend/src/LoginScreen.tsx` を新規作成、`App.tsx`にログイン状態チェック・ログイン画面・ログアウトボタンを追加。`axios.defaults.withCredentials = true`を設定
  - ついでにRuff/ESLintを既存コード全体に適用しCIが最初からグリーンになる状態に整備（`ai_service.py`/`fetch_nikkei225.py`/`main.py`/`App.tsx`の軽微なスタイル・型修正、壊れていたローカルの`chart.js`インストールを再インストールで修復）
  - `backend`・`frontend`とも `ruff check .` / `pytest` / `npm run lint` / `npm run build` がすべて成功することを確認済み
- [2026-07-15] `.github/workflows/cd.yml` を新規作成（CI成功後にSSHでVMへデプロイ。YAML構文を検証済み）。`docker-compose.yml`/`.env.example`に`ENV=production`・`FRONTEND_ORIGIN`を追加（本番のクロスオリジンCookieに必須）

## 保留中の意思決定事項

現時点でなし。各タスク着手時に、より詳細な意思決定が発生する可能性あり。

## 次にやること

フェーズ1（インフラ移行）のコード実装は完了。残るのは下記の手動作業（[手動]マーク）のみ。完了後、フェーズ2（予測ロジック刷新）に進む。

### フェーズ1: インフラ移行

- [x] Docker Compose / Dockerfile / requirements.txt / CI・CD雛形を作成
- [x] 自前認証（バックエンド・フロントエンド）を実装
- [x] インメモリキャッシュをDB読み書きに置き換え、lifespanハンドラへ移行
- [ ] [手動] Oracle Cloud アカウント作成、Always Free Ampere（ARM）VM作成（リージョン・キャパシティ確保）
- [ ] [手動] VM基本セットアップ（OS更新、ファイアウォール、SSH鍵認証のみ許可、80/443番ポートのみ開放）
- [ ] [手動] Docker / Docker Compose をVMに導入
- [ ] [手動] DuckDNSアカウント作成、ホスト名発行、VMの公開IPと紐付け
- [ ] [手動] VM上に本リポジトリを`git clone`（配置先は`/opt/stock-price-forecast`を想定。変更する場合は`.github/workflows/cd.yml`のパスも合わせて修正）
- [ ] [手動] `.env`をVM上に作成（`.env.example`参照。`APP_PASSWORD`・`SESSION_SECRET`を発行）
- [ ] [手動] Cloudflare Pagesにフロントエンドをデプロイ（Gitリポジトリ連携、自動ビルド確認。ドメイン不要、`*.pages.dev`で運用）
- [ ] [手動] Cloudflare Pages側の環境変数`VITE_API_BASE_URL`をDuckDNSホスト名（Caddy経由）に、バックエンド側`FRONTEND_ORIGIN`をPagesのURLに設定
- [ ] [手動] VM上でバックエンド・PostgreSQL・Caddyを`docker compose up -d --build`、`alembic upgrade head`でスキーマ適用、再起動時の自動復旧を確認
- [ ] [手動] GitHub Secrets（`VM_HOST`/`VM_USER`/`VM_SSH_KEY`）を設定しCDを有効化
- [ ] [手動] UptimeRobotで死活監視を設定

### フェーズ2: 予測ロジック刷新

- [ ] pandas-taでテクニカル指標（RSI・MACD・ボリンジャーバンド・出来高変化率）を実装
- [ ] yfinanceからファンダメンタルズ指標（PER・PBR・配当利回り・増収増益率）を取得する実装
- [ ] `internal_ai.py`のランダムスコアリングをルールベース実装に置き換え
- [ ] ニュース感情の長期スコアへの時間減衰反映ロジックを実装
- [ ] マクロ・地政学ニュース収集（市場全体向けクエリ）と横断スコア反映を実装
- [ ] `predict_score(features) → score` インターフェースを実装（将来のML差し替えに備える）
- [ ] 特徴量の時系列をDBに保存する仕組みを実装
- [ ] backtesting.pyで実バックテストエンジンを実装し、巡回処理内での事前計算に組み込む
- [ ] チャート表示期間切り替え対応（1年分データの事前保存＋範囲切り替え）
- [ ] オンデマンド評価を廃止し、`/summary`系エンドポイントをDB読み取り専用に変更
- [ ] 未評価銘柄のキュー待ち表示を実装
- [ ] ポーリング間隔を見直し（3秒→30秒以上、15秒→数分単位）
- [ ] スケルトンUIを実装
- [ ] AI/API障害時の劣化表示を実装
- [ ] 手動即時再評価（確認ダイアログ＋レート制限）を実装
- [ ] 投資助言ではない旨の免責事項をすべての判定画面に表示

### フェーズ3: 開示情報の実データ連携

- [ ] EDINET API v2アカウント登録・APIキー取得
- [ ] EDINET開示書類メタデータ取得を実装
- [ ] TDnetスクレイピングを実装（レート制限・エラーハンドリング込み）
- [ ] 取得失敗時のフォールバック（EDINETのみで運用）を実装
- [ ] 開示イベント種別ごとの重み付けルールを実装

## 変更履歴

- 2026-07-15: `PROGRESS.md` / `CLAUDE.md` 新規作成（作業ルールの明文化、初回進捗記録）
