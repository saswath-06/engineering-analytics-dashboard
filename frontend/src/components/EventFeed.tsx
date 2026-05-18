import { useQuery } from "@tanstack/react-query";
import { fetchModelInfo, type ModelInfo } from "../lib/api";

const EVENTS = [
  { type: "pr_opened",   actor: "alice",  repo: "org/api",         desc: "Opened PR #42 — Add rate limiting middleware",  age: "2m" },
  { type: "pr_approved", actor: "bob",    repo: "org/frontend",    desc: "Approved PR #38 — Migrate to new design system", age: "8m" },
  { type: "push",        actor: "carol",  repo: "org/api",         desc: "Pushed 2 commits to main",                       age: "15m" },
  { type: "pr_merged",   actor: "carol",  repo: "org/ml-pipeline", desc: "Merged PR #11 — Retrain pipeline v2",            age: "31m" },
  { type: "pr_changes",  actor: "dave",   repo: "org/api",         desc: "Requested changes on PR #40",                   age: "47m" },
];

const TYPE_ICON: Record<string, { icon: string; color: string; bg: string }> = {
  pr_opened:  { icon: "⊕", color: "#4f8ef7", bg: "#1a3a7a" },
  pr_approved:{ icon: "✓", color: "#34c472", bg: "#0e3321" },
  pr_merged:  { icon: "⊗", color: "#a78bfa", bg: "#2d1a4a" },
  pr_changes: { icon: "⊘", color: "#f0a429", bg: "#3d2700" },
  push:       { icon: "↑", color: "#8694ae", bg: "#1e2d47" },
};

function ModelCard({ info }: { info: ModelInfo }) {
  return (
    <div className="bg-raised rounded-lg border border-border p-3 mb-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-text">ML Model</span>
        <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-dim text-blue border border-blue/20">
          v{info.version}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-y-2.5 gap-x-4">
        {[
          { label: "Accuracy",    value: `${(info.accuracy * 100).toFixed(1)}%` },
          { label: "Estimators",  value: String(info.n_estimators) },
          { label: "Algorithm",   value: "GBC" },
          { label: "Trained",     value: info.training_date },
        ].map(({ label, value }) => (
          <div key={label}>
            <div className="text-xs text-subtle">{label}</div>
            <div className="text-sm font-mono text-text mt-0.5">{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EventRow({ e }: { e: typeof EVENTS[0] }) {
  const meta = TYPE_ICON[e.type] ?? TYPE_ICON.push;
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-border last:border-0">
      <div
        className="w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0 mt-0.5"
        style={{ background: meta.bg, color: meta.color }}
      >
        {meta.icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-text leading-snug truncate">{e.desc}</p>
        <p className="text-xs text-subtle mt-0.5">
          {e.actor} · {e.repo} · {e.age} ago
        </p>
      </div>
    </div>
  );
}

export default function EventFeed() {
  const { data: model, isLoading, isError } = useQuery({
    queryKey: ["model-info"],
    queryFn: fetchModelInfo,
  });

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden flex flex-col h-full">

      <div className="px-4 py-3 border-b border-border shrink-0">
        <h2 className="text-sm font-semibold text-text">Activity</h2>
        <p className="text-xs text-subtle mt-0.5">Live GitHub event stream</p>
      </div>

      <div className="px-4 py-3 overflow-y-auto flex-1">

        {/* ML model card */}
        {isLoading && (
          <div className="bg-raised rounded-lg border border-border p-3 mb-4 text-sm text-subtle">
            Loading model info…
          </div>
        )}
        {isError && (
          <div className="bg-raised rounded-lg border border-red/20 p-3 mb-4 text-xs text-red">
            ML service unreachable at :8003
          </div>
        )}
        {model && <ModelCard info={model} />}

        {/* Event list */}
        <div>
          {EVENTS.map((e, i) => <EventRow key={i} e={e} />)}
        </div>

        <p className="text-xs text-faint text-center py-3">
          Connect webhooks to see live events
        </p>
      </div>

    </div>
  );
}
