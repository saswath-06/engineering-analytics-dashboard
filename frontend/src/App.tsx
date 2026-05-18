import EventFeed from "./components/EventFeed";
import PRHealthTable from "./components/PRHealthTable";
import VelocityChart from "./components/VelocityChart";

export default function App() {
  return (
    <div className="min-h-screen bg-base text-text">

      {/* ── Nav ─────────────────────────────────────────────────────── */}
      <header className="border-b border-border bg-surface/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-[1480px] mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2.5">
              {/* Logo mark */}
              {/* PR health pulse icon */}
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <rect width="20" height="20" rx="5" fill="#4f8ef7" fillOpacity="0.12"/>
                <path
                  d="M2 10h3l2-4 2 8 2-6 2 3h5"
                  stroke="#4f8ef7"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span className="text-sm font-semibold text-text tracking-tight">
                Engineering Analytics
              </span>
            </div>
            <nav className="hidden md:flex items-center gap-1">
              {["Overview", "Pull Requests", "Authors", "Settings"].map((label, i) => (
                <button
                  key={label}
                  className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                    i === 0
                      ? "bg-raised text-text font-medium"
                      : "text-subtle hover:text-text hover:bg-raised/60"
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-green-dim border border-green/20">
              <span className="live-dot w-1.5 h-1.5 rounded-full bg-green block" />
              <span className="text-xs font-medium text-green">Live</span>
            </div>
            <div className="w-7 h-7 rounded-full bg-blue-dim flex items-center justify-center text-blue text-xs font-semibold">
              EL
            </div>
          </div>
        </div>
      </header>

      {/* ── Page ────────────────────────────────────────────────────── */}
      <main className="max-w-[1480px] mx-auto px-6 py-6 space-y-4">

        {/* Page title */}
        <div>
          <h1 className="text-lg font-semibold text-text">Overview</h1>
          <p className="text-sm text-subtle mt-0.5">
            Real-time pull request health and team velocity.
          </p>
        </div>

        <PRHealthTable />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <VelocityChart />
          </div>
          <EventFeed />
        </div>

      </main>
    </div>
  );
}
