import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Sun, Moon, Activity, RefreshCw, LogOut } from 'lucide-react';
import './index.css';
import axios from 'axios';
import LoginScreen from './LoginScreen';

// バックエンドとフロントは別サイト(別オリジン)のため、Cookieベースのセッションは
// ブラウザのサードパーティCookieブロックにより機能しない。そのためBearerトークン方式とし、
// localStorageに保存したトークンを全リクエストにAuthorizationヘッダーとして付与する
// （REQUIREMENTS_v2.md 1節/1.2節参照、2026-07-16改訂）。
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  type ChartOptions
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface RankingResponse {
  top_buy: SignalSummary[];
  bottom_buy: SignalSummary[];
  top_sell: SignalSummary[];
  bottom_sell: SignalSummary[];
}

interface StockMaster {
  code: string;
  name_ja: string;
  name_en: string;
  sector: string;
}

interface SignalSummary {
  code: string;
  short_score: number;
  long_score: number;
  risk_score: number;
  final_score: number;
  final_signal: string;
  updated_at?: string;
}

interface BacktestResult {
  code: string;
  trades: number;
  win_rate: number;
  avg_return: number;
  max_drawdown: number;
  computed: boolean;
}

interface ChartResponse {
  code: string;
  labels: string[];
  prices: (number | null)[];
  ma5: (number | null)[];
  ma25: (number | null)[];
}

interface NewsInfo {
  title: string;
  source: string;
  url: string;
  effect: string;
  reason: string;
  cls: string;
}

interface DocInfo {
  title: string;
  type: string;
  url: string;
  effect: string;
  reason: string;
  cls: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// Chart.jsはCanvas描画のため、CSSのカスケード外にあるvar()を解決できない
// (index.cssのCSS変数をそのまま渡すと無効な色として無視され、既定の黒で描画される)。
// そのためテーマごとの実際の色をここに複製して使う（値はindex.cssの--tm/--dvと合わせること）。
const CHART_THEME_COLORS: Record<string, { tick: string; grid: string }> = {
  dark: { tick: '#8d8a85', grid: '#292826' },
  light: { tick: '#75736d', grid: '#dcd9d5' },
};

const CHART_PERIODS = [
  { key: '3m', label: '3ヶ月', days: 90 },
  { key: '6m', label: '6ヶ月', days: 182 },
  { key: '1y', label: '1年', days: 366 },
] as const;
type ChartPeriod = typeof CHART_PERIODS[number]['key'];

function SkeletonBlock({ width = '100%', height = '1rem' }: { width?: string; height?: string }) {
  return <div className="skeleton" style={{ width, height }} />;
}

function DashboardView({ onSelect }: { onSelect: (c: string) => void }) {
  const [ranking, setRanking] = useState<RankingResponse | null>(null);

  useEffect(() => {
    axios.get(`${API_BASE}/api/recommendations`).then(res => setRanking(res.data)).catch(console.error);
    // ランキングは巡回処理が数十秒〜数時間かけて更新するものなので、15秒間隔の
    // ポーリングは過剰だった。数分単位に緩和する（長期投資中心の方針、REQUIREMENTS_v2.md 5.1参照）
    const timer = setInterval(() => {
      axios.get(`${API_BASE}/api/recommendations`).then(res => setRanking(res.data)).catch(console.error);
    }, 180000);
    return () => clearInterval(timer);
  }, []);

  if (!ranking) {
    return (
      <div style={{ flex: 1, padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s4)' }}>
        <SkeletonBlock width="280px" height="1.8rem" />
        <div style={{ display: 'flex', gap: 'var(--s4)', flexWrap: 'wrap' }}>
          {[0, 1, 2, 3].map(i => (
            <div key={i} className="card" style={{ flex: 1, minWidth: '300px', padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
              <SkeletonBlock width="60%" height="1.2rem" />
              {[0, 1, 2, 3, 4].map(j => <SkeletonBlock key={j} height="2.2rem" />)}
            </div>
          ))}
        </div>
      </div>
    );
  }

  const renderList = (title: string, list: SignalSummary[]) => (
    <div className="card" style={{flex: 1, minWidth: '300px'}}>
      <h3 style={{marginBottom: 'var(--s3)', fontSize: 'var(--lg)'}}>{title}</h3>
      {list.length === 0 && <div style={{color:'var(--tm)'}}>データ収集中...</div>}
      <div style={{display: 'flex', flexDirection: 'column', gap: 'var(--s2)'}}>
        {list.map(s => (
          <div key={s.code} style={{display:'flex', justifyContent:'space-between', padding:'var(--s2)', background:'var(--bg)', borderRadius:'var(--radius)', cursor:'pointer', border: '1px solid transparent'}} 
               onClick={() => onSelect(s.code)}
               onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--text)'}
               onMouseLeave={(e) => e.currentTarget.style.borderColor = 'transparent'}>
            <div>
              <span style={{fontWeight:'bold', marginRight:'var(--s2)'}}>{s.code}</span>
              <span className={`pill ${s.final_signal==='buy'?'p-ok':s.final_signal==='sell'?'p-er':'p-gd'}`}>{s.final_signal.toUpperCase()}</span>
            </div>
            <div style={{display: 'flex', gap: 'var(--s2)', alignItems: 'center'}}>
              {s.updated_at && <span style={{fontSize: 'var(--xs)', color: 'var(--tm)'}}>{s.updated_at.split(' ')[1]}</span>}
              <span style={{fontWeight:'bold'}}>{s.final_score} pt</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div style={{ flex: 1, padding: 'var(--s5)', overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      <h1 style={{fontSize: 'var(--xl)', marginBottom: 'var(--s2)'}}>AI推奨・市場ランキング</h1>
      <p style={{color: 'var(--tm)', marginBottom: 'var(--s5)'}}>内部AI＋Geminiのハイブリッド推論により、現在裏側で自動巡回・更新中の最新ランキングです。</p>
      
      <div style={{display: 'flex', gap: 'var(--s4)', flexWrap: 'wrap', marginBottom: 'var(--s4)'}}>
        {renderList("📈 買うべき銘柄 5選", ranking.top_buy)}
        {renderList("📉 売るべきでない銘柄 5選 (反発期待)", ranking.bottom_sell)}
      </div>
      <div style={{display: 'flex', gap: 'var(--s4)', flexWrap: 'wrap'}}>
        {renderList("📉 売るべき銘柄 5選", ranking.top_sell)}
        {renderList("🛑 買うべきでない銘柄 5選 (高リスク)", ranking.bottom_buy)}
      </div>
    </div>
  );
}

function AuthenticatedApp({ onLogout }: { onLogout: () => void }) {
  const [theme, setTheme] = useState('dark');
  const [chartPeriod, setChartPeriod] = useState<ChartPeriod>('1y');
  const [stocks, setStocks] = useState<StockMaster[]>([]);
  const [search, setSearch] = useState('');
  
  // Selected state
  const [current, setCurrent] = useState<StockMaster | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const mainRef = useRef<HTMLElement>(null);
  
  // Data states
  const [summary, setSummary] = useState<SignalSummary | null>(null);
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [chartData, setChartData] = useState<ChartResponse | null>(null);
  const [newsList, setNewsList] = useState<NewsInfo[]>([]);
  const [docList, setDocList] = useState<DocInfo[]>([]);

  // Toggle Theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(t => t === 'dark' ? 'light' : 'dark');
  };

  // Fetch initial stocks
  useEffect(() => {
    axios.get(`${API_BASE}/api/stocks`)
      .then(res => {
        setStocks(res.data);
        if(res.data.length > 0) setCurrent(res.data[0]);
      })
      .catch(err => {
        console.error("API Fetch Error:", err);
        setErrorMsg(err.message + " - Backend API might not be running or CORS error.");
      });
  }, []);

  // Data fetching logic（現在の状態を再取得するのみ。状態のリセットは行わない）
  // Promise.allでまとめて待てるようにし、「最新化」ボタンの読み込み中表示に使う
  const fetchData = useCallback(async () => {
    if(!current) return;
    await Promise.all([
      axios.get(`${API_BASE}/api/stocks/${current.code}/summary`).then(res => setSummary(res.data)).catch(console.error),
      axios.get(`${API_BASE}/api/stocks/${current.code}/backtest`).then(res => setBacktest(res.data)).catch(console.error),
      axios.get(`${API_BASE}/api/stocks/${current.code}/chart`).then(res => setChartData(res.data)).catch(console.error),
      axios.get(`${API_BASE}/api/stocks/${current.code}/news`).then(res => setNewsList(res.data)).catch(console.error),
      axios.get(`${API_BASE}/api/stocks/${current.code}/docs`).then(res => setDocList(res.data)).catch(console.error),
    ]);
  }, [current]);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const handleManualRefresh = async () => {
    if (!current) return;
    setIsRefreshing(true);
    try {
      // バックエンド側でコアスコア（テクニカル+ML）とニュース/開示分析(Gemini)の両方を
      // その場で再計算してから応答する（ニュース側は直近取得済みならクールダウンでスキップされる）。
      // その後にfetchDataで画面表示分をまとめて再取得する
      await axios.post(`${API_BASE}/api/stocks/${current.code}/refresh`).catch(console.error);
      await fetchData();
    } finally {
      setIsRefreshing(false);
    }
  };

  // 銘柄切り替え時は、選択とリセットをイベントハンドラ側で同時に行う
  // （Effect内で直接setStateを呼ぶとカスケードレンダリングになるため避ける）
  const selectStock = (s: StockMaster) => {
    setCurrent(s);
    setSummary(null); setBacktest(null); setChartData(null); setNewsList([]); setDocList([]);
    // 画面が狭い（サイドバーと詳細が縦積みになる）場合、銘柄選択後に詳細側まで
    // 自動スクロールする。デスクトップ幅では両方見えているため何もしない。
    if (window.matchMedia('(max-width: 1000px)').matches) {
      mainRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  // 選択銘柄が変わったら取得
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Polling logic when AI is analyzing
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    if (summary && summary.final_signal === 'analyzing...') {
      timer = setTimeout(() => {
        fetchData();
      }, 3000);
    }
    return () => clearTimeout(timer);
  }, [summary, fetchData]);

  const filteredStocks = stocks.filter(s => 
    s.name_ja.includes(search) || s.code.includes(search) || s.name_en.toLowerCase().includes(search.toLowerCase())
  );

  // Configuration for Chart.js（テーマ切り替え・不要な再レンダーのたびに作り直さないようメモ化）
  const chartOptions: ChartOptions<'line'> = useMemo(() => {
    const colors = CHART_THEME_COLORS[theme] ?? CHART_THEME_COLORS.dark;
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as const, intersect: false },
      plugins: { legend: { labels: { color: colors.tick } } },
      scales: {
        x: { ticks: { color: colors.tick, maxTicksLimit: 14 }, grid: { color: colors.grid } },
        y: { ticks: { color: colors.tick }, grid: { color: colors.grid } }
      }
    };
  }, [theme]);

  // 表示期間の切り替えは、既に取得済みの1年分データを絞り込むだけで完結させる
  // （切り替えのたびに新規データ取得は発生させない。REQUIREMENTS_v2.md 2.6参照）
  const chartPayload = useMemo(() => {
    if (!chartData) return null;
    const periodDays = CHART_PERIODS.find(p => p.key === chartPeriod)?.days ?? 366;
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - periodDays);
    let sliceFrom = chartData.labels.findIndex(l => new Date(l.replace(/\//g, '-')) >= cutoff);
    if (sliceFrom === -1) sliceFrom = 0;

    return {
      labels: chartData.labels.slice(sliceFrom),
      datasets: [
        { label: '株価', data: chartData.prices.slice(sliceFrom), borderColor: '#4f98a3', borderWidth: 2, pointRadius: 0, tension: .25 },
        { label: 'MA5', data: chartData.ma5.slice(sliceFrom), borderColor: '#e8af34', borderWidth: 1.4, borderDash: [2, 2], pointRadius: 0, tension: .25 },
        { label: 'MA25', data: chartData.ma25.slice(sliceFrom), borderColor: '#73a7d8', borderWidth: 1.4, borderDash: [5, 5], pointRadius: 0, tension: .25 }
      ]
    };
  }, [chartData, chartPeriod]);

  return (
    <div className="app">
      {/* Header */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--s3) var(--s6)', borderBottom: '1px solid var(--dv)', background: 'color-mix(in oklab, var(--bg) 88%, transparent)', backdropFilter: 'blur(10px)', position: 'sticky', top: 0, zIndex: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', fontWeight: 800 }}>
          <Activity size={30} color="var(--pr)" />
          <div>
            <div>日本株 売買シグナル基盤</div>
            <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: '.2rem' }}>AI推論・半自動運用ダッシュボード</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--s3)' }}>
          <button onClick={toggleTheme} className="btn" style={{display: 'flex', gap: '8px', alignItems:'center'}}>
            {theme === 'dark' ? <Sun size={18}/> : <Moon size={18}/>}
            テーマ切替
          </button>
          <button onClick={onLogout} className="btn" style={{display: 'flex', gap: '8px', alignItems:'center'}}>
            <LogOut size={18}/>
            ログアウト
          </button>
        </div>
      </header>

      {/* 投資助言業規制のリスクを避けるための免責事項（REQUIREMENTS_v2.md 6.1参照）。
          全画面（ランキング・個別銘柄いずれも）で常に表示する */}
      <div style={{ padding: '.5rem var(--s6)', background: 'color-mix(in oklab, var(--gd) 12%, var(--bg))', borderBottom: '1px solid var(--dv)', fontSize: 'var(--xs)', color: 'var(--tm)', textAlign: 'center' }}>
        本サービスが表示するスコア・判定・分析結果は投資助言ではありません。将来の成果を保証するものでもありません。投資に関する最終判断はご自身の責任で行ってください。
      </div>

      <div className="layout">
        {/* Sidebar */}
        <aside className="sidebar" style={{ padding: 'var(--s6)', borderRight: '1px solid var(--dv)', background: 'var(--sf)', overflowY: 'auto' }}>
          <div style={{ fontSize: 'var(--xs)', color: 'var(--tf)', textTransform: 'uppercase', letterSpacing: '.08em', fontWeight: 800, marginBottom: 'var(--s3)' }}>日経225 銘柄</div>
          <input 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: '100%', padding: '.85rem .95rem', border: '1px solid var(--bd)', borderRadius: 'var(--r1)', background: 'var(--sf2)', color: 'var(--tx)', fontFamily: 'var(--font)' }} 
            placeholder="銘柄名・コード" 
          />
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)', marginTop: 'var(--s4)' }}>
            {filteredStocks.map(s => (
              <div 
                key={s.code}
                onClick={() => selectStock(s)}
                style={{
                  padding: 'var(--s3)', border: '1px solid transparent', borderRadius: 'var(--r1)', cursor: 'pointer',
                  borderColor: current?.code === s.code ? 'color-mix(in oklab,var(--pr) 30%, var(--bd))' : 'transparent',
                  background: current?.code === s.code ? 'color-mix(in oklab,var(--pr) 9%, var(--sf2))' : 'var(--sf2)'
                }}
              >
                <div style={{ fontWeight: 800, fontSize: 'var(--sm)' }}>{s.name_ja}</div>
                <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: '.2rem' }}>{s.code} · {s.sector}</div>
              </div>
            ))}
          </div>
        </aside>

        {/* Main */}
        <main ref={mainRef} className="main" style={{ overflowY: 'auto' }}>
          {current ? (
            <>
              <section style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--s4)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <div>
                  <h1 style={{ fontSize: 'var(--xl)', lineHeight: 1.1, letterSpacing: '-.03em' }}>{current.name_ja}</h1>
                  <div style={{ fontSize: 'var(--sm)', color: 'var(--tm)', marginTop: 'var(--s2)' }}>{current.code} · {current.sector}</div>
                </div>
                <div style={{ display: 'flex', gap: 'var(--s3)' }}>
                  {summary && summary.final_signal !== 'analyzing...' && summary.updated_at && (
                     <div style={{display:'flex', alignItems:'center', color:'var(--tm)', fontSize:'var(--sm)'}}>
                       最終更新: {summary.updated_at}
                     </div>
                  )}
                  {summary?.final_signal === 'analyzing...' && <div style={{display:'flex', alignItems:'center', color:'var(--tm)', fontSize:'var(--sm)'}}>AI分析中...（通常数秒〜数十秒で完了します）</div>}
                  {summary?.final_signal === 'error' && <div style={{display:'flex', alignItems:'center', color:'var(--er, #d64545)', fontSize:'var(--sm)'}}>分析に失敗しました（自動的に再試行されます）</div>}
                  <button onClick={handleManualRefresh} disabled={isRefreshing} className="btn" style={{display: 'flex', gap: '8px', alignItems:'center', opacity: isRefreshing ? 0.7 : 1}}>
                    <RefreshCw size={18} className={isRefreshing ? 'spin' : ''} />
                    {isRefreshing ? '更新中...' : '最新化'}
                  </button>
                </div>
              </section>

              {/* KPIs (Signal Board) */}
              <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--s4)' }}>
                <div className="card" style={{ padding: 'var(--s5)' }}>
                  <div style={{ fontSize: 'var(--xs)', textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--tf)', fontWeight: 800 }}>最終判定</div>
                  {summary ? (
                    <>
                      <div className="mono" style={{ font: '700 var(--xl)/1.1 var(--mono)', marginTop: 'var(--s2)' }}>
                        {summary.final_signal === 'error' ? 'エラー' : `${summary.final_score} pt`}
                      </div>
                      <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: 'var(--s2)' }}>
                        {summary.final_signal === 'error'
                          ? <span className="pill p-er">取得失敗</span>
                          : <span className={`pill ${summary.final_signal==='buy'?'p-ok':summary.final_signal==='sell'?'p-er':'p-gd'}`}>{summary.final_signal.toUpperCase()}</span>}
                      </div>
                    </>
                  ) : (
                    <div style={{ marginTop: 'var(--s2)', display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
                      <SkeletonBlock height="1.8rem" width="70%" />
                      <SkeletonBlock height="1.2rem" width="45%" />
                    </div>
                  )}
                </div>

                <div className="card" style={{ padding: 'var(--s5)' }}>
                  <div style={{ fontSize: 'var(--xs)', textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--tf)', fontWeight: 800 }}>短期スコア / AI</div>
                  {summary ? (
                    <div className="mono" style={{ font: '700 var(--xl)/1.1 var(--mono)', marginTop: 'var(--s2)' }}>{summary.short_score} pt</div>
                  ) : (
                    <div style={{ marginTop: 'var(--s2)' }}><SkeletonBlock height="1.8rem" width="50%" /></div>
                  )}
                  <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: 'var(--s2)' }}>チャート + ニュース</div>
                </div>

                <div className="card" style={{ padding: 'var(--s5)' }}>
                  <div style={{ fontSize: 'var(--xs)', textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--tf)', fontWeight: 800 }}>長期スコア / AI</div>
                  {summary ? (
                    <div className="mono" style={{ font: '700 var(--xl)/1.1 var(--mono)', marginTop: 'var(--s2)' }}>{summary.long_score} pt</div>
                  ) : (
                    <div style={{ marginTop: 'var(--s2)' }}><SkeletonBlock height="1.8rem" width="50%" /></div>
                  )}
                  <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: 'var(--s2)' }}>TDnet + EDINET + IR</div>
                </div>
              </section>

              {/* Chart & Backtest Grid */}
              <section style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.6fr) minmax(320px, 0.95fr)', gap: 'var(--s4)' }}>
                {/* 実際の株価チャート (yfinanceからの実データ) */}
                <article className="card">
                  <div style={{ padding: 'var(--s5)', borderBottom: '1px solid var(--dv)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--s2)' }}>
                    <div>
                      <div style={{ fontSize: 'var(--base)', fontWeight: 800 }}>テクニカルチャート</div>
                      <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: '.2rem' }}>実際の株価推移 (yfinance)</div>
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--s1)', background: 'var(--bg)', padding: '.2rem', borderRadius: 'var(--r1)' }}>
                      {CHART_PERIODS.map(p => (
                        <button
                          key={p.key}
                          onClick={() => setChartPeriod(p.key)}
                          className="btn"
                          style={{
                            padding: '.35rem .7rem', fontSize: 'var(--xs)', border: 'none',
                            background: chartPeriod === p.key ? 'var(--pr)' : 'transparent',
                            color: chartPeriod === p.key ? 'var(--inv)' : 'var(--tm)',
                          }}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div style={{ padding: 'var(--s5)', height: '350px' }}>
                    {chartPayload ? <Line data={chartPayload} options={chartOptions} /> : <SkeletonBlock height="100%" />}
                  </div>
                </article>

                <article className="card">
                  <div style={{ padding: 'var(--s5)', borderBottom: '1px solid var(--dv)' }}>
                    <div style={{ fontSize: 'var(--base)', fontWeight: 800 }}>バックテスト結果</div>
                    <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: '.2rem' }}>過去5年分、本番と同じ判定ルールを再現</div>
                  </div>

                  {backtest && backtest.computed ? (
                    <div style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 'var(--s2)', borderBottom: '1px solid var(--dv)' }}>
                        <span style={{ fontSize: 'var(--sm)', color: 'var(--tm)' }}>総取引回数</span>
                        <span className="mono" style={{ fontWeight: 800 }}>{backtest.trades} 回</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 'var(--s2)', borderBottom: '1px solid var(--dv)' }}>
                        <span style={{ fontSize: 'var(--sm)', color: 'var(--tm)' }}>勝率</span>
                        <span className="mono" style={{ fontWeight: 800 }}>{backtest.win_rate}%</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 'var(--s2)', borderBottom: '1px solid var(--dv)' }}>
                        <span style={{ fontSize: 'var(--sm)', color: 'var(--tm)' }}>平均損益</span>
                        <span className={`mono ${backtest.avg_return > 0 ? 'pos' : 'neg'}`} style={{ fontWeight: 800 }}>{backtest.avg_return}%</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 'var(--s2)' }}>
                        <span style={{ fontSize: 'var(--sm)', color: 'var(--tm)' }}>最大ドローダウン</span>
                        <span className="mono neg" style={{ fontWeight: 800 }}>{backtest.max_drawdown}%</span>
                      </div>
                    </div>
                  ) : backtest ? (
                    <div style={{ padding: 'var(--s5)', color: 'var(--tm)' }}>
                      巡回処理がまだこの銘柄に到達していません（計算中）。しばらくしてから再度ご確認ください。
                    </div>
                  ) : (
                    <div style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                      {[0, 1, 2, 3].map(i => <SkeletonBlock key={i} height="1.4rem" />)}
                    </div>
                  )}
                </article>
              </section>

              {/* News & Documents (Bottom Cards) */}
              <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: 'var(--s4)' }}>
                <article className="card">
                  <div style={{ padding: 'var(--s5)', borderBottom: '1px solid var(--dv)' }}>
                    <div style={{ fontSize: 'var(--base)', fontWeight: 800 }}>ニュース寄与度 (AI推論)</div>
                    <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: '.2rem' }}>個別記事の要約とセンチメント</div>
                  </div>
                  <div style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                    {!summary && newsList.length === 0 && [0, 1, 2].map(i => <SkeletonBlock key={i} height="4.5rem" />)}
                    {newsList.map((n, i) => (
                      n.source === 'System' ? (
                        <div key={i} style={{ padding: 'var(--s4)', border: '1px dashed var(--dv)', borderRadius: 'var(--r1)', color: 'var(--tm)' }}>
                          <div style={{ fontSize: 'var(--sm)', fontWeight: 700 }}>{n.title}</div>
                          <div style={{ fontSize: 'var(--xs)', marginTop: '.22rem' }}>{n.reason}</div>
                        </div>
                      ) : (
                      <div key={i} style={{ padding: 'var(--s4)', border: '1px solid var(--dv)', borderRadius: 'var(--r1)', background: 'var(--sfo)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--s3)', alignItems: 'flex-start' }}>
                          <div>
                            <div style={{ fontSize: 'var(--sm)', fontWeight: 800 }}>{n.title}</div>
                            <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: '.22rem' }}>{n.reason}</div>
                            <div style={{ fontSize: 'var(--xs)', marginTop: '.5rem' }}><a href={n.url} target="_blank" rel="noreferrer">AIによるソース元の確認 ↗</a></div>
                          </div>
                          <div className={`mono ${n.cls==='pos'?'pos':n.cls==='neg'?'neg':'neu'}`} style={{ fontWeight: 800 }}>{n.effect}pt</div>
                        </div>
                        <div style={{ marginTop: 'var(--s2)', display: 'flex', alignItems: 'center', gap: 'var(--s2)', flexWrap: 'wrap' }}>
                          <span className={`pill ${n.cls==='pos'?'p-ok':n.cls==='neg'?'p-er':'p-gd'}`}>{n.source}</span>
                          <span className="pill p-gd">短期寄与</span>
                        </div>
                      </div>
                      )
                    ))}
                  </div>
                </article>

                <article className="card">
                  <div style={{ padding: 'var(--s5)', borderBottom: '1px solid var(--dv)' }}>
                    <div style={{ fontSize: 'var(--base)', fontWeight: 800 }}>TDnet / EDINET 開示 (AI推論)</div>
                    <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: '.2rem' }}>開示資料ごとの長期インパクト評価</div>
                  </div>
                  <div style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                    {!summary && docList.length === 0 && [0, 1, 2].map(i => <SkeletonBlock key={i} height="4.5rem" />)}
                    {docList.map((d, i) => (
                      d.type === 'System' ? (
                        <div key={i} style={{ padding: 'var(--s4)', border: '1px dashed var(--dv)', borderRadius: 'var(--r1)', color: 'var(--tm)' }}>
                          <div style={{ fontSize: 'var(--sm)', fontWeight: 700 }}>{d.title}</div>
                          <div style={{ fontSize: 'var(--xs)', marginTop: '.22rem' }}>{d.reason}</div>
                        </div>
                      ) : (
                      <div key={i} style={{ padding: 'var(--s4)', border: '1px solid var(--dv)', borderRadius: 'var(--r1)', background: 'var(--sfo)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--s3)', alignItems: 'flex-start' }}>
                          <div>
                            <div style={{ fontSize: 'var(--sm)', fontWeight: 800 }}>{d.title}</div>
                            <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)', marginTop: '.22rem' }}>{d.reason}</div>
                            <div style={{ fontSize: 'var(--xs)', marginTop: '.5rem' }}><a href={d.url} target="_blank" rel="noreferrer">{d.type}原本を開く ↗</a></div>
                          </div>
                          <div className={`mono ${d.cls==='pos'?'pos':d.cls==='neg'?'neg':'neu'}`} style={{ fontWeight: 800 }}>{d.effect}pt</div>
                        </div>
                        <div style={{ marginTop: 'var(--s2)', display: 'flex', alignItems: 'center', gap: 'var(--s2)', flexWrap: 'wrap' }}>
                          <span className="pill p-gd">{d.type}</span>
                          <span className="pill p-ok">長期寄与</span>
                        </div>
                      </div>
                      )
                    ))}
                  </div>
                </article>
              </section>

            </>
          ) : (
            <div style={{ padding: '0', flex: 1, display: 'flex', flexDirection: 'column' }}>
              {errorMsg ? (
                <div style={{ padding: 'var(--s6)', color: 'var(--er)' }}>
                  <h2 style={{ marginBottom: '1rem' }}>バックエンド接続エラー</h2>
                  <p>{errorMsg}</p>
                </div>
              ) : (
                <DashboardView onSelect={(code) => {
                  const target = stocks.find(s => s.code === code);
                  if (target) selectStock(target);
                }} />
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

type AuthState = 'checking' | 'authenticated' | 'unauthenticated';

function App() {
  const [authState, setAuthState] = useState<AuthState>('checking');

  useEffect(() => {
    axios.get(`${API_BASE}/api/auth/status`)
      .then(res => {
        if (!res.data.authenticated) localStorage.removeItem('authToken');
        setAuthState(res.data.authenticated ? 'authenticated' : 'unauthenticated');
      })
      .catch(() => setAuthState('unauthenticated'));
  }, []);

  const handleLogout = () => {
    axios.post(`${API_BASE}/api/auth/logout`).finally(() => {
      localStorage.removeItem('authToken');
      setAuthState('unauthenticated');
    });
  };

  if (authState === 'checking') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)', color: 'var(--tm)' }}>
        Loading...
      </div>
    );
  }

  if (authState === 'unauthenticated') {
    return <LoginScreen onSuccess={() => setAuthState('authenticated')} />;
  }

  return <AuthenticatedApp onLogout={handleLogout} />;
}

export default App;
