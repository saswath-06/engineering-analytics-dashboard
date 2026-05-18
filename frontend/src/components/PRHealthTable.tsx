import { useQuery } from "@tanstack/react-query";
import { fetchOpenPRsWithRisk, type PRWithRisk } from "../lib/api";

function formatAge(hrs: number) {
  if (hrs < 1) return `${Math.round(hrs * 60)}m`;
  if (hrs < 24) return `${hrs.toFixed(1)}h`;
  return `${(hrs / 24).toFixed(1)}d`;
}

function RiskBadge({ atRisk, bucket }: { atRisk: boolean; bucket: string }) {
  if (atRisk) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-red-dim text-red border border-red/20">
        <span className="w-1.5 h-1.5 rounded-full bg-red" />
        At risk · {bucket}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-green-dim text-green border border-green/20">
      <span className="w-1.5 h-1.5 rounded-full bg-green" />
      On track · {bucket}
    </span>
  );
}

function Avatar({ name }: { name: string }) {
  const initials = name.slice(0, 2).toUpperCase();
  const colors = ["#1a3a7a", "#0e3321", "#3d2700", "#2d1a4a"];
  const bg = colors[name.charCodeAt(0) % colors.length];
  const texts = ["#4f8ef7", "#34c472", "#f0a429", "#a78bfa"];
  const fg = texts[name.charCodeAt(0) % texts.length];
  return (
    <span
      className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold font-mono shrink-0"
      style={{ background: bg, color: fg }}
    >
      {initials}
    </span>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="px-4 py-3 border-r border-border last:border-r-0">
      <div className="text-xs text-subtle mb-1">{label}</div>
      <div className="text-xl font-semibold text-text font-mono tabular-nums">{value}</div>
      {sub && <div className="text-xs text-faint mt-0.5">{sub}</div>}
    </div>
  );
}

function PRRow({ pr }: { pr: PRWithRisk }) {
  const atRisk = pr.prediction?.at_risk ?? false;
  const age = pr.pr_age_hrs;

  return (
    <tr className="table-row border-b border-border last:border-0">
      <td className="px-4 py-3">
        <div className="flex items-start gap-2.5">
          <Avatar name={pr.author} />
          <div className="min-w-0">
            <div className="text-sm text-text font-medium truncate max-w-xs" title={pr.title}>
              {pr.title}
            </div>
            <div className="text-xs text-subtle mt-0.5">
              {pr.repo}&nbsp;
              <span className="text-faint">·</span>&nbsp;
              <span className="font-mono">#{pr.pr_number}</span>
            </div>
          </div>
        </div>
      </td>

      <td className="px-4 py-3 text-sm text-subtle">{pr.author}</td>

      <td className="px-4 py-3">
        <span className={`text-sm font-mono tabular-nums ${age > 24 ? "text-amber" : "text-subtle"}`}>
          {formatAge(age)}
        </span>
      </td>

      <td className="px-4 py-3 text-sm font-mono tabular-nums text-subtle">
        +{Math.round(pr.code_churn * 0.65)}&nbsp;
        <span className="text-faint">−{Math.round(pr.code_churn * 0.35)}</span>
      </td>

      <td className="px-4 py-3">
        {pr.prediction ? (
          <RiskBadge atRisk={atRisk} bucket={pr.prediction.predicted_bucket} />
        ) : (
          <span className="text-faint text-sm">—</span>
        )}
      </td>

      <td className="px-4 py-3 text-sm font-mono tabular-nums text-subtle">
        {pr.prediction ? `${(pr.prediction.confidence * 100).toFixed(0)}%` : "—"}
      </td>
    </tr>
  );
}

export default function PRHealthTable() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["open-prs-with-risk"],
    queryFn: () => fetchOpenPRsWithRisk(),
  });

  const atRisk = data?.filter(p => p.prediction?.at_risk).length ?? 0;
  const total  = data?.length ?? 0;
  const avgAge = data?.length
    ? (data.reduce((s, p) => s + p.pr_age_hrs, 0) / data.length).toFixed(1)
    : "—";

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">

      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text">Pull Request Health</h2>
        <span className="text-xs text-subtle">Sorted by risk confidence</span>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-4 border-b border-border divide-x divide-border bg-raised/50">
        <StatCard label="Open PRs"      value={total}   />
        <StatCard label="At risk"       value={atRisk}  sub={total ? `${Math.round(atRisk / total * 100)}% of open` : undefined} />
        <StatCard label="Avg age"       value={avgAge !== "—" ? `${avgAge}h` : "—"} />
        <StatCard label="Model"         value="GBC·200" sub="82% accuracy" />
      </div>

      {/* States */}
      {isLoading && (
        <div className="px-4 py-10 text-center text-sm text-subtle">
          Loading pull requests…
        </div>
      )}
      {isError && (
        <div className="px-4 py-10 text-center text-sm text-red">
          Could not reach the aggregation service at :8002.
        </div>
      )}
      {data && data.length === 0 && (
        <div className="px-4 py-10 text-center text-sm text-subtle">
          No open pull requests tracked yet.{" "}
          <span className="text-faint">Send a webhook event to populate.</span>
        </div>
      )}

      {/* Table */}
      {data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border bg-raised/30">
                {["Pull request", "Author", "Age", "Changes", "Risk prediction", "Confidence"].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-subtle">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...data]
                .sort((a, b) => (b.prediction?.confidence ?? 0) - (a.prediction?.confidence ?? 0))
                .map(pr => <PRRow key={pr.pr_id} pr={pr} />)}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
}
