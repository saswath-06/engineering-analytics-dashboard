const AGGREGATION = "/api/aggregation";
const ML = "/api/ml";

export interface OpenPR {
  pr_id: number;
  pr_number: number;
  repo: string;
  author: string;
  title: string;
  created_at: string;
  pr_age_hrs: number;
  code_churn: number;
  review_rounds: number;
  review_assignment_lag_hrs: number | null;
}

export interface PRPrediction {
  at_risk: boolean;
  predicted_bucket: string;
  confidence: number;
  threshold_used: number;
}

export interface PRWithRisk extends OpenPR {
  prediction: PRPrediction | null;
}

export interface AuthorMetrics {
  author: string;
  prs_opened_7d: number;
  prs_merged_7d: number;
  avg_review_lag_hrs: number | null;
  open_prs: { pr_id: number; pr_number: number; title: string; repo: string }[];
}

export interface RepoMetrics {
  repo: string;
  open_pr_count: number;
  throughput_7d: number;
  avg_merge_time_hrs: number | null;
}

export interface ModelInfo {
  version: string;
  training_date: string;
  accuracy: number;
  n_estimators: number;
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function fetchOpenPRs(repo?: string): Promise<OpenPR[]> {
  const url = repo
    ? `${AGGREGATION}/prs/open?repo=${encodeURIComponent(repo)}`
    : `${AGGREGATION}/prs/open`;
  return fetchJson<OpenPR[]>(url);
}

export async function predictPR(pr: OpenPR): Promise<PRPrediction> {
  return fetchJson<PRPrediction>(`${ML}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      review_assignment_lag_hrs: pr.review_assignment_lag_hrs ?? 0,
      code_churn: pr.code_churn,
      author_velocity_7d: 3,
      reviewer_load: 2,
      hour_of_day: new Date(pr.created_at).getHours(),
      pr_age_hrs: pr.pr_age_hrs,
      num_review_rounds: pr.review_rounds,
    }),
  });
}

export async function fetchOpenPRsWithRisk(repo?: string): Promise<PRWithRisk[]> {
  const prs = await fetchOpenPRs(repo);
  return Promise.all(
    prs.map(async (pr) => {
      try {
        const prediction = await predictPR(pr);
        return { ...pr, prediction };
      } catch {
        return { ...pr, prediction: null };
      }
    })
  );
}

export async function fetchAuthorMetrics(login: string): Promise<AuthorMetrics> {
  return fetchJson<AuthorMetrics>(`${AGGREGATION}/metrics/author/${login}`);
}

export async function fetchRepoMetrics(repo: string): Promise<RepoMetrics> {
  return fetchJson<RepoMetrics>(`${AGGREGATION}/metrics/repo/${encodeURIComponent(repo)}`);
}

export async function fetchModelInfo(): Promise<ModelInfo> {
  return fetchJson<ModelInfo>(`${ML}/model/info`);
}
