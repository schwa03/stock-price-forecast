# 進捗管理ファイル

最終更新: 2026-07-16

## 現在のフェーズ

フェーズ1は公開完了済み。運用中に「Geminiの無料枠が1キー1日20リクエストしかない」ことが判明し、コアスコアの算出をML（LightGBM）中心に作り直した（フェーズ2の前倒し実施、ユーザー承認済み）。ローカルで学習パイプライン全体の動作確認済み、あとはVM側でpull・マイグレーション・初回学習の実行が必要。

## インフラ実環境の情報

Ampere A1（無料枠ARM）が東京リージョンで在庫切れのため、暫定的にAMD系無料枠（E2.1.Micro）で先行構築中。Ampereの在庫が確保でき次第、同じ手順でそちらに移行する（Dockerベースのため移行は容易）。

| 項目 | 値 |
|---|---|
| GitHubリポジトリ | `schwa03/stock-price-forecast`（Private） |
| Oracle Cloud VCN | `stock-app-vcn`（ap-tokyo-1、Public subnet: `public subnet-stock-app-vcn`） |
| 稼働中VM（暫定） | `stock-app-vm-micro`（VM.Standard.E2.1.Micro, 1/8 OCPU, 1GB RAM＋2GBスワップ） |
| VMの公開IP | `138.2.6.252` |
| DuckDNSホスト名 | `yuus-stock-app.duckdns.org` |
| SSH鍵（VMアクセス用） | `C:\Stock_Price_Forecast\keys\oracle-vm-key`（.gitignore対象） |
| Ampere用Stack（在庫待ち中） | Resource Managerのstack名 `stock-app-vm`。Applyを定期的にリトライ中 |
| GitHub Deploy Key | VM上で生成した`~/.ssh/github_deploy_key`をリポジトリのDeploy Keys（読み取り専用）に登録済み。VM側の`git pull`はこの鍵で認証（トークン不要に変更済み） |
| フロントエンドURL | `https://stock-price-forecast.kawagoe-ani2.workers.dev`（Cloudflare Workers静的アセット、Pagesではなく統合後のWorkers方式） |
| Cloudflareプロジェクト名 | `stock-price-forecast`（アカウント: kawagoe.ani2@gmail.com） |

**当日の主な学び（同じ問題を繰り返さないためのメモ）**:
- Cloudflare Tunnelの公開ホスト名には所有ドメインが必須と判明→DuckDNS＋Caddy＋自前認証の完全無料構成に変更済み（REQUIREMENTS_v2.md参照）
- Oracle Cloudの「その場でサブネットを新規作成」フローだとPublic IPv4のチェックボックスが押せない既知の不具合あり→先にNetworking単体でVCNウィザードを使うと回避できる
- `VM.Standard.A1.Flex`はap-tokyo-1（AD-1のみ）で在庫切れが頻発。Resource Managerで「Save as Stack」しておけばPlanをやり直さずApplyだけ再試行できる
- GitHubは2021年からgit push時のパスワード認証を廃止。Personal Access TokenかSSH鍵が必要
- Windowsの資格情報マネージャーに別GitHubアカウントの認証情報がキャッシュされていて403エラーになることがある
- `docker compose exec`は対象コンテナが再起動ループ中だと失敗する。マイグレーション等は`docker compose run --rm <service> <command>`（一時コンテナ）で実行するのが安全
- Geminiのモデル名は個別バージョン（例: `gemini-2.5-flash`）がユーザー種別によって突然廃止されることがある。`gemini-flash-latest`等のエイリアスを使うと安全
- Cloudflareの新規プロジェクト作成フローは「Pages」ではなく統合後の「Workers（静的アセット）」がデフォルトになっており、`frontend/wrangler.jsonc`（assets.directory等）が別途必要
- Windowsで生成した`package-lock.json`をコミットすると、Linux向けネイティブ依存（`@emnapi/*`等）が欠落しCloudflare/GitHub ActionsのLinuxビルドで`npm ci`が失敗する。lockfileはコミットせず`npm install`に委ねるのが安全（frontend/package-lock.jsonは.gitignore対象に変更、CIも`npm ci`→`npm install`に変更済み）

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
- [2026-07-15] **VM上での実デプロイに成功、バックエンドが本番稼働開始**。作業中に見つかった実際の不具合を修正:
  - `backend/requirements.txt`: `numpy==2.4.4`固定が`pandas-ta`（内部で`numba`使用）と衝突→`numpy>=2.2.6,<2.3`に緩和。`backtesting<0.4`という古い上限が現行の公開バージョン（0.6.5）と非互換→`<1.0`に緩和
  - `backend/ai_service.py`: 使用していたGeminiモデル名`gemini-2.5-flash`が新規ユーザー向けに廃止済みと判明→`gemini-flash-latest`（常に最新版を指すエイリアス）に変更
  - GitHubへのpushが最初「プレースホルダーURLのまま」「パスワード認証（廃止済み）」「別GitHubアカウントの資格情報キャッシュ」で3重に失敗。Personal Access Token→VM専用のGitHub Deploy Key（読み取り専用SSH鍵）方式に切り替えて解消
  - Oracle CloudのAmpere A1（無料枠ARM）が東京リージョンで在庫切れのため、暫定的にAMD無料枠（E2.1.Micro, 1GB RAM+2GBスワップ）で先行構築。Resource Managerの`stock-app-vm`スタックでApplyのリトライを継続中。在庫確保後、同じ手順でAmpereへ移行予定
  - `docker compose exec`でのAlembicマイグレーション実行が「backendコンテナが再起動ループ中で失敗」→`docker compose run --rm backend alembic upgrade head`（新規の一時コンテナ）に切り替えて解消
  - 動作確認済み: ルートエンドポイント・未認証時401・ログイン・認証済みAPI呼び出し（`/api/stocks`で223銘柄取得）まですべて成功
- [2026-07-16] **シークレットウィンドウでログイン後に`/api/stocks`が401になる不具合を修正**。原因はセッションCookie方式そのもの: フロントエンド（`*.workers.dev`）とバックエンド（`*.duckdns.org`）が別サイトのため、`SameSite=None; Secure`を正しく設定していてもブラウザのサードパーティCookieブロック機能によりCookieが保存/送信されなかった。Cookie方式をやめ、**Bearerトークン方式**に変更して解消:
  - `backend/auth.py`: `set_session_cookie`/`clear_session_cookie`を廃止。`/api/auth/login`はレスポンスボディで署名付きトークンを返却し、`require_auth`は`Authorization: Bearer <token>`ヘッダーを検証する方式に変更
  - `frontend/src/LoginScreen.tsx`: ログイン成功時にレスポンスの`token`を`localStorage`に保存
  - `frontend/src/App.tsx`: `axios.defaults.withCredentials`をやめ、axiosのリクエストインターセプターで全リクエストに`localStorage`のトークンを`Authorization`ヘッダーとして付与。ログアウト時・認証状態が無効だった場合は`localStorage`のトークンを削除
  - `backend/tests/test_auth.py`をトークン方式に合わせて更新（不正トークン拒否のテストケースを追加）。`backend`は9件・フロントの`lint`/`build`とも成功確認済み
  - `REQUIREMENTS_v2.md` 1節・1.1節の認証記載をBearerトークン方式に更新（ユーザー許可の範囲内、既存の認証セクションの記述更新）
  - [x] GitHubへcommit・push済み。VM側は私がSSH鍵（`keys/oracle-vm-key`）で直接接続し`git pull`・`docker compose up -d --build backend`を実行、本番反映・動作確認済み
  - [x] フロントエンドはCloudflare側がGitHubと直接連携しており、push契機で自動ビルド・自動デプロイされることを確認（Cloudflare Pagesの「Deployments」タブでpush後に自動的に新バージョンがTraffic 100%で公開されるのを確認。`wrangler login`や`CLOUDFLARE_API_TOKEN`は不要）
  - **学び**: `docker compose up -d --build backend`でbackendコンテナを再作成すると、Caddy側が持つ内部接続が古いコンテナを指したままになり502エラーになることがある。backend再デプロイ後は`docker compose restart caddy`も併せて実行するのが安全

## 保留中の意思決定事項

現時点でなし。各タスク着手時に、より詳細な意思決定が発生する可能性あり。

## 次にやること

フェーズ1（インフラ移行）のコード実装は完了。残るのは下記の手動作業（[手動]マーク）のみ。完了後、フェーズ2（予測ロジック刷新）に進む。

### フェーズ1: インフラ移行

- [x] Docker Compose / Dockerfile / requirements.txt / CI・CD雛形を作成
- [x] 自前認証（バックエンド・フロントエンド）を実装
- [x] インメモリキャッシュをDB読み書きに置き換え、lifespanハンドラへ移行
- [x] [手動] Oracle Cloud アカウント作成、VM作成（Ampereは在庫切れのため暫定でE2.1.Micro `stock-app-vm-micro`を使用。Ampere用Stackは在庫待ちでApply継続中）
- [x] [手動] VM基本セットアップ（Docker導入、スワップ2GB追加、80/443番ポート開放）
- [x] [手動] DuckDNSアカウント作成、ホスト名発行（`yuus-stock-app.duckdns.org`）、VMの公開IPと紐付け
- [x] [手動] VM上に本リポジトリを`git clone`（GitHub Deploy Key方式に変更、`/opt/stock-price-forecast`）
- [x] [手動] `.env`をVM上に作成
- [x] [手動] VM上でバックエンド・PostgreSQL・Caddyを`docker compose up -d --build`、`alembic upgrade head`でスキーマ適用。動作確認済み（ルート/401/ログイン/認証済みAPI呼び出しすべて成功）
- [x] [手動] Cloudflareにフロントエンドをデプロイ（Pagesではなく統合後のWorkers静的アセット方式。`frontend/wrangler.jsonc`を追加して対応。URL: `https://stock-price-forecast.kawagoe-ani2.workers.dev`）
- [x] [手動] `VITE_API_BASE_URL`をDuckDNSホスト名に、バックエンド側`.env`の`FRONTEND_ORIGIN`をWorkersのURLに設定
- [x] **エンドツーエンドの動作確認完了**（ブラウザから実際にログイン・アクセスできることを確認済み）
- [x] フロントエンドはCloudflareのGitHub連携により、push契機で自動デプロイされることを確認済み（追加設定不要）
- [x] バックエンドは、ローカルにある`keys/oracle-vm-key`を使い、Claude自身がSSHでVMへ接続し`git pull`＋`docker compose up -d --build backend`（＋`docker compose restart caddy`）を実行することで反映可能なことを確認済み（2026-07-16）。GitHub Actions経由のCD（Secrets設定）は必須ではなくなったため保留
- [ ] [手動・任意] GitHub Secrets（`VM_HOST`/`VM_USER`/`VM_SSH_KEY`）を設定しGitHub Actions経由のCDを有効化（上記の手動SSH運用で十分なため優先度低）
- [ ] [手動] UptimeRobotで死活監視を設定
- [ ] Ampereの在庫確保後、同じ手順でVMを移行し、DuckDNSのIPを向け先変更

### フェーズ2: 予測ロジック刷新

**2026-07-15、コアスコアのMLxV6化を前倒しで実施**（きっかけ: Geminiの無料枠クォータが1キー1日20リクエストしかなく、スコア算出がGeminiに依存する設計だと225銘柄を回すのに3週間以上かかると判明。ユーザー承認のもと、コアスコアをGeminiから完全に独立させた）。

- [x] テクニカル指標（MA5/25/75比率・RSI14・MACDヒストグラム・ボリンジャーバンド%b・出来高変化率）を`backend/features.py`にpandasのみで自前実装（pandas-taは不採用、理由はREQUIREMENTS_v2.md 1.1/1.2参照）
- [x] `backend/train_model.py`: yfinanceの過去データ（3年分、20営業日先リターンを予測対象）からLightGBM回帰モデルを学習するスクリプトを実装。ローカル（Python 3.11検証環境）で5銘柄の小規模データを使いパイプライン全体（学習→保存→読み込み→推論）の動作を確認済み
- [x] `backend/predictor.py`: 学習済みモデルの読み込みと推論。モデル未学習時はヒューリスティックにフォールバックする設計（動作確認済み）
- [x] `backend/main.py`を大幅刷新: コアスコア算出（`update_core_score`、yfinance+ML、Geminiに依存しない）とニュース/開示分析（`update_news_and_docs`、Gemini）を完全に独立した2つの巡回ループに分離。前者は高速（3秒間隔）、後者は低頻度（クォータ保護）で並行稼働する
- [x] `signal_summary`テーブルに`news_updated_at`列を追加（コアスコアとニュース分析の鮮度を別々に管理するため）。マイグレーション作成済み
- [x] `internal_ai.py`のランダムスコアリングをコアスコアの経路から排除（ニュース/開示の補助表示には引き続き使用。完全排除は別途検討）
- [ ] [手動] VM側で`git pull`・`alembic upgrade head`・初回`python train_model.py`の実行（このセッションの成果をデプロイする）
- [ ] マクロ・地政学ニュース収集（市場全体向けクエリ）と補助表示への反映を実装
- [ ] Gemini呼び出しのバッチ化（複数銘柄まとめて1リクエスト。現状は1銘柄2リクエストのまま、量的な改善余地あり）
- [ ] ファンダメンタルズ指標（PER・PBR・配当利回り・増収増益率）の画面表示（yfinance取得。ML特徴量への組み込みは点在時点データの入手方法が見つかり次第）
- [ ] ニュース感情の長期スコアへの時間減衰反映ロジック（補助表示側での検討に変更）
- [ ] backtesting.pyで実バックテストエンジンを実装し、巡回処理内での事前計算に組み込む
- [ ] チャート表示期間切り替え対応（既にyfinance取得を6ヶ月→1年に拡張済み。フロント側のUI切り替えは未実装）
- [ ] 未評価銘柄のキュー待ち表示を実装
- [ ] ポーリング間隔を見直し（3秒→30秒以上、15秒→数分単位）
- [ ] スケルトンUIを実装
- [ ] 手動即時再評価（確認ダイアログ＋レート制限）を実装
- [ ] 投資助言ではない旨の免責事項をすべての判定画面に表示
- [x] AI/API障害時の劣化表示を実装（コアスコア処理失敗時に"error"状態をDBに記録しフロントに表示。前セッションで対応済み）

### フェーズ3: 開示情報の実データ連携

- [ ] EDINET API v2アカウント登録・APIキー取得
- [ ] EDINET開示書類メタデータ取得を実装
- [ ] TDnetスクレイピングを実装（レート制限・エラーハンドリング込み）
- [ ] 取得失敗時のフォールバック（EDINETのみで運用）を実装
- [ ] 開示イベント種別ごとの重み付けルールを実装

## 変更履歴

- 2026-07-15: `PROGRESS.md` / `CLAUDE.md` 新規作成（作業ルールの明文化、初回進捗記録）
