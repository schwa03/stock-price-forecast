# 進捗管理ファイル

最終更新: 2026-07-21

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

## 完了事項（追加）

- [2026-07-21] **重大バグ修正**: ユーザーから「バックテストで一部銘柄の取引回数・勝率・平均損益・最大ドローダウンが全部ゼロ」との報告を受けて調査。VM上の実際の学習済みモデルを取得してローカルで複数銘柄を検証したところ、`backend_result`テーブルの223銘柄すべてで取引回数が0件（一部は最大ドローダウンのみ非ゼロ＝買ったままポジションが開きっぱなし、一部は完全にゼロ＝一度も買いシグナルが出ていない）という異常を確認。根本原因は、学習期間（直近3年）の日本株市場が全体的に上昇基調だったため、LightGBMモデルの予測リターンが恒常的にプラス側に偏り（検証した4銘柄すべてで予測リターンの最小値がプラス）、長期スコアが常に60点前後以上に張り付いて売り判定（45点以下）にほぼ到達できなくなっていたこと。
  - `backend/predictor.py`の`score_from_return`を、予測リターンの絶対値ベース（±5%で0-100点）から、`train_model.py`が検証データへの予測から作成したパーセンタイル較正テーブルに対する相対順位ベースに変更（較正データがなければ従来の絶対値ベースにフォールバック）
  - `backend/train_model.py`: 学習後、検証用データへの予測分布から5%刻みのパーセンタイル値を計算し`model/predictor_percentiles.json`として保存するよう追加
  - 対症療法（スコア変換方式の変更）を優先実施。根本原因である学習データの期間的偏りへの対応（学習期間の延長等）は将来の検討課題として残す
  - 合成データでの変換ロジック検証、backendテスト11件成功を確認済み。`REQUIREMENTS_v2.md` 2.2節、`FEATURES.md` 3.3/4節を更新
  - [x] VM側への反映＋`train_model.py`の再実行（新しいモデル+パーセンタイル較正データの生成）完了。再学習後の検証データ予測レンジは`min=-0.0223`とマイナス側も含むようになった
  - **さらに深刻な第2のバグを発見・修正**: スコア変換を直しても実機で取引回数が0のままだったため`backend/backtest_engine.py`を直接検証したところ、`_SignalStrategy.init()`で`self.signal = self.data.Signal`と`self.I()`を経由せずカスタム列を直接参照していたのが原因と判明。backtesting.pyは`self.I()`でラップした列だけを日次インデックスに合わせて切り詰めてくれる仕様で、素通しの列は`signal[-1]`が常に「データ全体の最終日」の値を返し続ける（＝実質、全期間を通じて単一の定数シグナルで判定してしまう）。`self.signal = self.I(lambda: self.data.Signal, name="signal")`に修正し、最小再現コードで動作を確認した上で反映。修正前は検証4銘柄すべてでbuy_calls=0だったが、修正後は7203:12回, 9984:39回, 8306:18回, 6758:30回など銘柄ごとに異なる妥当な取引回数が得られることを確認
  - この2つ目のバグの方が実質的な根本原因で、1つ目のスコア偏り修正だけでは解決しなかった。両方の修正が揃って初めて正常化した
- [2026-07-21] LightGBMモデルの定期再学習を自動化。VM上に`cron`パッケージをインストールし、`/etc/cron.d/stock-model-retrain`に毎週日曜18:00 UTC（=月曜3:00 JST）に`docker compose run --rm backend python train_model.py`を実行するジョブを登録（ログは`/var/log/stock-model-retrain.log`）。REQUIREMENTS_v2.md 2.2「週1回程度でモデルファイルを再生成」の方針通り
- [2026-07-21] `internal_ai.py`の判定根拠一覧「寄与度(pt)」表示からランダム要素を排除。従来はキーワード一致時に`random.randint`で大きさを足しており同じ事実でも表示のたびに数値が変わっていたが、一致したキーワード数に基づく決定的な計算（±4pt/件、最大±8pt）に変更。スコア計算自体（predictor.py）には元々使っていないため挙動に影響なし。`FEATURES.md` 4節を更新
- [2026-07-21] スマートフォン等の小さい画面でのレイアウト崩れを修正。チャート＋バックテスト、ニュース＋開示の2カラムグリッドがインラインstyleの固定`minmax(320px/350px, ...)`を持ち、狭い画面幅でメディアクエリでの上書きができず横スクロールが発生していたため、`chart-backtest-grid`/`news-docs-grid`のCSSクラスに切り出し、700px以下で1カラム表示に強制。ヘッダーの折り返し・`body { overflow-x: hidden }`も追加。`FEATURES.md` 8節を更新
- [2026-07-18] 「最新化」ボタンを押しても表示が変わらない（巡回が追いついていない銘柄だとニュース・開示情報が古いまま）という問題に対応。ユーザーの要望「更新ボタンを押せば確実に最新情報が反映されるようにしてほしい」を受け、`backend/main.py`の`/api/stocks/{code}/refresh`をコアスコアだけでなくニュース・開示分析（Gemini）も同時に再計算するよう変更:
  - コアスコアは従来通り常に即座に再計算
  - ニュース・開示分析は、同一銘柄が直近10分以内に取得済みならスキップ（連打・複数銘柄閲覧によるGeminiクォータ浪費を防止）、10分より前なら押すたびに再取得
  - 当初の要件定義（6.3節）では「今すぐ再評価」を別操作・確認ダイアログ付き・6時間レート制限としていたが、6時間だと「最新化ボタンを押しても反映されない」という今回の問題がそのまま残るため、ユーザー許可のもと「最新化」ボタンへの統合・10分レート制限・確認ダイアログなしに変更。`REQUIREMENTS_v2.md` 決定事項サマリー・6.3節、`FEATURES.md` 3節を更新済み
  - backendテスト9件・フロントlint/buildとも成功確認済み
- [2026-07-18] ユーザーからの複数の指摘・要望に対応:
  - **バックテストが全銘柄同じ数値だった件**: 環境要因ではなく、`/backtest`が固定ダミー値を返す仮実装だったことが原因と判明。実データ化を実施:
    - `backend/predictor.py`にスコア合成・売買判定の共通関数（`combine_scores`/`classify_signal`/`get_model`）を新設し、`backend/main.py`の本番スコアリングと新設の`backend/backtest_engine.py`の両方から同じ関数を使うようにして、バックテストが本番ルールと乖離しないようにした
    - `backend/backtest_engine.py`（新規）: 過去5年分のyfinanceデータに対し日次で特徴量・スコア・シグナルを再現し、`backtesting.py`で実際の売買をシミュレート
    - `backend/models.py`に`BacktestResultRow`（`backtest_result`テーブル）を追加、マイグレーション`2acd878b1839`を作成
    - `backend/main.py`に`autonomous_backtest_crawler`（低頻度・CPU負荷を考慮し30秒間隔）を新設し、コアスコア/ニュースとは独立した3本目の巡回ループとして常時実行
    - `/api/stocks/{code}/backtest`をDB読み取りに変更。巡回未到達の銘柄向けに`computed: false`を返し、フロントで「計算中」と区別表示
    - `backend/tests/test_backtest_engine.py`を追加（データ不足時にNoneを返すことを検証）。backendテストは計13件に増加、全件成功確認済み
  - **テーマ切り替えでのフリーズ・黒背景に黒文字の件**: 原因を特定。Chart.jsはCanvas描画のためCSSの`var(--tm)`等がカスケード解決されず、無効な色として無視され既定の黒で描画されていた（テーマを切り替えても直らない理由もこれで説明がつく）。`frontend/src/App.tsx`に`CHART_THEME_COLORS`（テーマごとの実色をJS側に複製）を追加し解消。あわせて`chartOptions`/`chartPayload`を`useMemo`化し、無関係な再レンダー（ポーリング等）のたびにChart.jsインスタンスが作り直される負荷を軽減
  - **チャート表示期間の切り替え（1年/6ヶ月/3ヶ月）**: `frontend/src/App.tsx`に期間切り替えボタンを追加。バックエンドは元々1年分を保持しているため、切り替え時に新規データ取得は発生させず、既取得データを日付でクライアント側で絞り込むだけで実現（`REQUIREMENTS_v2.md` 2.6の方針通り）
  - スコアレンジ（0-100 vs -100〜100）の質問には0-100維持を推奨として回答（コード変更なし）。点数表示の見せ方は「また今度」とのことで保留
  - `FEATURES.md` 3.1/3.3を更新済み。`REQUIREMENTS_v2.md` 2.6は元々この方針で書かれていたため変更不要
  - [x] VM側で`git pull`・`alembic upgrade head`（`backtest_result`テーブル作成）・backend再ビルド・Caddy再起動まで完了。バックテストクローラーが実際に稼働し、DBに実データ（勝率・最大ドローダウン等）が書き込まれ始めていることを確認済み
- [2026-07-18] 「他に修正していない箇所はありますか？」の質問を受け、残っていたバックログを順番に対応:
  - **ポーリング間隔の見直し**: `backend/main.py`の`autonomous_core_crawler`のsleep_durationを3秒→30秒に変更（225銘柄一周が約11分→約1.9時間。長期投資中心・日次更新で十分という方針に対して3秒は過剰だった）。`frontend/src/App.tsx`のランキング再取得間隔を15秒→3分（180000ms）に変更
  - **未評価銘柄の「analyzing...」が巡回待ちで永遠に続く問題**: `/api/stocks/{code}/summary`の判定を「行が存在するか」から「final_signalがanalyzing...でないか」に変更。これにより、ニュース巡回側が先に行を作ってしまった等の理由でコアスコア未計算のまま行だけ存在するケースでも、その場でコアスコア計算を即座にトリガーするようになった（コアスコアはGeminiクォータの制約を受けず数秒〜数十秒で完了するため、遅い巡回ループの順番待ちを回避できる）。あわせてフロントの「AI分析中...」表示に「通常数秒〜数十秒で完了します」を追記
  - **投資助言ではない旨の免責事項**: ヘッダー直下に常時表示するバナーを追加（`REQUIREMENTS_v2.md` 6.1）
  - **スケルトンUI**: ランキング一覧・KPIカード（最終判定/短期/長期スコア）・チャート・バックテスト・ニュース/開示カードの初回読み込み中表示を、プレーンテキストからシマーアニメーション付きのプレースホルダーに置き換え
  - `FEATURES.md` 3節・8節・9節を実装済みに更新（9節は元々実装済みだったのに計画中のままだった記載漏れも合わせて修正）
  - backendテスト11件・フロントlint/buildとも成功確認済み
  - [ ] [手動] VM側への反映が必要（未実施）

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
- [x] [手動] UptimeRobotで死活監視を設定（2026-07-21完了。バックエンドのルートエンドポイント`https://yuus-stock-app.duckdns.org/`を5分間隔で監視、ダウン時にメール通知）
- [ ] Ampereの在庫確保後、同じ手順でVMを移行し、DuckDNSのIPを向け先変更

### フェーズ2: 予測ロジック刷新

**2026-07-15、コアスコアのMLxV6化を前倒しで実施**（きっかけ: Geminiの無料枠クォータが1キー1日20リクエストしかなく、スコア算出がGeminiに依存する設計だと225銘柄を回すのに3週間以上かかると判明。ユーザー承認のもと、コアスコアをGeminiから完全に独立させた）。

- [x] テクニカル指標（MA5/25/75比率・RSI14・MACDヒストグラム・ボリンジャーバンド%b・出来高変化率）を`backend/features.py`にpandasのみで自前実装（pandas-taは不採用、理由はREQUIREMENTS_v2.md 1.1/1.2参照）
- [x] `backend/train_model.py`: yfinanceの過去データ（3年分、20営業日先リターンを予測対象）からLightGBM回帰モデルを学習するスクリプトを実装。ローカル（Python 3.11検証環境）で5銘柄の小規模データを使いパイプライン全体（学習→保存→読み込み→推論）の動作を確認済み
- [x] `backend/predictor.py`: 学習済みモデルの読み込みと推論。モデル未学習時はヒューリスティックにフォールバックする設計（動作確認済み）
- [x] `backend/main.py`を大幅刷新: コアスコア算出（`update_core_score`、yfinance+ML、Geminiに依存しない）とニュース/開示分析（`update_news_and_docs`、Gemini）を完全に独立した2つの巡回ループに分離。前者は高速（3秒間隔）、後者は低頻度（クォータ保護）で並行稼働する
- [x] `signal_summary`テーブルに`news_updated_at`列を追加（コアスコアとニュース分析の鮮度を別々に管理するため）。マイグレーション作成済み
- [x] `internal_ai.py`のランダムスコアリングをコアスコアの経路から排除（ニュース/開示の補助表示には引き続き使用。完全排除は別途検討）
- [x] [手動] VM側で`git pull`・`alembic upgrade head`・初回`python train_model.py`の実行（完了済み。`backend/model/predictor.txt`が存在し、ログで`[PREDICTOR] Loaded trained model`を確認済み）
- [x] マクロ・地政学ニュース収集（市場全体向けクエリ）と補助表示への反映を実装（2026-07-21完了。`backend/ai_service.py`のfetch_macro_news/extract_macro_facts、`macro_news_item`テーブル、`autonomous_macro_news_crawler`（2時間毎）、`/api/macro-news`エンドポイント、フロントに「市場全体・マクロ要因」カードを追加）
- [x] Gemini呼び出しのバッチ化（2026-07-21完了。`ai_service.extract_news_facts_batch`/`extract_docs_facts_batch`で最大15銘柄/リクエストにまとめ、`main.update_news_and_docs_batch`＋`autonomous_news_crawler`を巡回専用に刷新。1銘柄2リクエスト×225銘柄=450リクエストから、15銘柄あたり2リクエストに削減。手動「最新化」ボタン（`update_news_and_docs`、1銘柄ずつ）はレスポンス性重視のため従来のまま維持）
- [x] ファンダメンタルズ指標（PER・PBR・配当利回り・増収増益率）の画面表示（2026-07-21完了。`update_core_score`内でyfinanceの`.info`を取得し`fundamentals`テーブルへ保存、`/api/stocks/{code}/fundamentals`、フロントにカードを追加。ML特徴量への組み込みは引き続き見送り＝リーク問題が解決するまで参考表示のみ）
  - **バグ修正**: VM実機で配当利回りが236%という異常値になっているのを発見。yfinanceの`dividendYield`は小数比率(0.0236)ではなく既にパーセント表記(2.36)で返ることが判明し、コード側で誤って100倍していたのが原因。実機ログで実際の値を確認した上で修正済み
- [x] ニュース感情の長期スコアへの時間減衰反映ロジック（2026-07-21: 実装しない方針に決定。理由は上記マクロニュースと同じ「コアスコアのGemini非依存」原則との矛盾。`REQUIREMENTS_v2.md`決定事項サマリーを修正し、判定根拠の補助表示（実装済み）のみで対応することを明記）
- [x] backtesting.pyで実バックテストエンジンを実装し、巡回処理内での事前計算に組み込む（2026-07-18完了。`backend/backtest_engine.py`＋`autonomous_backtest_crawler`）
- [x] チャート表示期間切り替え対応（2026-07-18完了。1年/6ヶ月/3ヶ月のボタンをフロントに追加、既取得データの絞り込みのみで新規取得なし）
- [x] 未評価銘柄のキュー待ち表示を実装（2026-07-18対応。コアスコア側は「巡回待ちの概算時間」ではなく、analyzing状態なら常にその場で即座に計算をトリガーする方式で解決（数秒〜数十秒で完了するため）。バックテストは「計算中」の明示表示で対応）
- [x] ポーリング間隔を見直し（3秒→30秒以上、15秒→数分単位）（2026-07-18完了）
- [x] スケルトンUIを実装（2026-07-18完了）
- [x] 手動即時再評価（レート制限付き）を実装（2026-07-18完了。当初案の別ダイアログ方式ではなく既存の「最新化」ボタンに統合。詳細は上記「完了事項（追加）」参照）
- [x] 投資助言ではない旨の免責事項をすべての判定画面に表示（2026-07-18完了）
- [x] AI/API障害時の劣化表示を実装（コアスコア処理失敗時に"error"状態をDBに記録しフロントに表示。前セッションで対応済み）

### フェーズ3: 開示情報の実データ連携

- [保留] EDINET API v2アカウント登録・APIキー取得（2026-07-21: ユーザーが登録を試みたが、電話番号のSMS確認コード入力後に画面が真っ白になり進めない不具合に遭遇。Chrome/シークレットウィンドウ/複数ブラウザすべてで再現するため、EDINET側サイトの一時的な不具合の可能性が高いと判断し保留。時間を置いて再挑戦するか、EDINETのサポート窓口稼働時間帯に再度試すことを推奨。それまでフェーズ3全体を保留とする）
- [ ] EDINET開示書類メタデータ取得を実装
- [ ] TDnetスクレイピングを実装（レート制限・エラーハンドリング込み）
- [ ] 取得失敗時のフォールバック（EDINETのみで運用）を実装
- [ ] 開示イベント種別ごとの重み付けルールを実装

## 変更履歴

- 2026-07-15: `PROGRESS.md` / `CLAUDE.md` 新規作成（作業ルールの明文化、初回進捗記録）
