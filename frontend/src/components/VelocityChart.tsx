import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Cell,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchAuthorMetrics, type AuthorMetrics } from "../lib/api";

const DEMO_AUTHORS = ["alice", "bob", "carol", "dave", "eve"];

interface VelocityPoint { author: string; opened: number; merged: number; }

function useTeamVelocity() {
  return useQuery<VelocityPoint[]>({
    queryKey: ["team-velocity"],
    queryFn: async () => {
      const results = await Promise.allSettled(DEMO_AUTHORS.map(fetchAuthorMetrics));
      return results
        .map((r, i): VelocityPoint => {
          if (r.status === "fulfilled") {
            const m = r.value as AuthorMetrics;
            return { author: m.author, opened: m.prs_opened_7d, merged: m.prs_merged_7d };
          }
          return { author: DEMO_AUTHORS[i], opened: 0, merged: 0 };
        })
        .filter(d => d.opened > 0 || d.merged > 0);
    },
  });
}

const ChartTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-raised border border-border rounded-lg px-3 py-2.5 text-xs shadow-xl font-sans">
      <div className="font-medium text-text mb-2">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-6">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm" style={{ background: p.fill }} />
            <span className="text-subtle">{p.name}</span>
          </div>
          <span className="font-mono text-text tabular-nums font-medium">{p.value}</span>
        </div>
      ))}
    </div>
  );
};

export default function VelocityChart() {
  const { data, isLoading, isError } = useTeamVelocity();

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden h-full">

      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-text">Author Velocity</h2>
          <p className="text-xs text-subtle mt-0.5">PRs opened vs. merged · rolling 7-day window</p>
        </div>
        <div className="flex items-center gap-4 text-xs text-subtle">
          {[
            { label: "Opened", color: "#4f8ef7" },
            { label: "Merged", color: "#34c472" },
          ].map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color, opacity: 0.85 }} />
              {label}
            </div>
          ))}
        </div>
      </div>

      <div className="px-4 pt-4 pb-3">
        {isLoading && (
          <div className="h-48 flex items-center justify-center text-sm text-subtle">
            Loading velocity data…
          </div>
        )}
        {isError && (
          <div className="h-48 flex items-center justify-center text-sm text-red">
            Could not reach the aggregation service at :8002.
          </div>
        )}
        {data && data.length === 0 && (
          <div className="h-48 flex items-center justify-center text-sm text-subtle">
            No author data available yet.
          </div>
        )}

        {data && data.length > 0 && (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data} barCategoryGap="38%" barGap={3}>
              <CartesianGrid vertical={false} stroke="#1e2d47" strokeDasharray="0" />
              <XAxis
                dataKey="author"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 12, fill: "#8694ae", fontFamily: "Plus Jakarta Sans" }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
                tick={{ fontSize: 12, fill: "#8694ae", fontFamily: "Plus Jakarta Sans" }}
                width={28}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(79,142,247,0.04)", radius: 4 }} />
              <Bar dataKey="opened" name="Opened" radius={[3, 3, 0, 0]}>
                {(data ?? []).map((_, i) => <Cell key={i} fill="#4f8ef7" fillOpacity={0.85} />)}
              </Bar>
              <Bar dataKey="merged" name="Merged" radius={[3, 3, 0, 0]}>
                {(data ?? []).map((_, i) => <Cell key={i} fill="#34c472" fillOpacity={0.85} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
