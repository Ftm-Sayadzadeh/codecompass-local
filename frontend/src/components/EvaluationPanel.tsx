import { Activity, BarChart3, CheckCircle2, Gauge, Info } from "lucide-react";

import type { EvaluationResponse, MetricAggregate } from "../api/types";
import { ErrorMessage } from "./ErrorMessage";

function percent(value: number | undefined) {
  return value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

function globalMetrics(response: EvaluationResponse | null) {
  return (response?.data.aggregates ?? []).filter((item) => item.slice.kind === "global_micro");
}

function methodPerformance(response: EvaluationResponse | null) {
  return (response?.data.aggregates ?? []).filter((item) => item.slice.kind === "method");
}

function methodName(item: MetricAggregate) {
  return item.method ?? item.slice.method ?? "unknown";
}

export function EvaluationPanel({ summary, performance, loading, error }: {
  summary: EvaluationResponse | null;
  performance: EvaluationResponse | null;
  loading: boolean;
  error: unknown;
}) {
  const metrics = globalMetrics(summary);
  const hybrid = metrics.find((item) => methodName(item) === "hybrid");
  const latency = methodPerformance(performance);
  const questions = summary?.data.benchmark?.questions;
  const concepts = summary?.data.benchmark?.concepts;

  return (
    <section className="evaluation-band" aria-labelledby="evaluation-title">
      <header>
        <div>
          <span className="eyebrow">Frozen scientific evidence</span>
          <h2 id="evaluation-title"><BarChart3 size={19} /> Evaluation and performance</h2>
        </div>
        <div className="evaluation-note"><Info size={15} /> Benchmark evaluation results — not per-answer confidence.</div>
      </header>
      {loading ? <div className="evaluation-loading">Loading evaluation artifacts...</div> : null}
      {error ? <ErrorMessage error={error} /> : null}
      {summary && performance ? (
        <div className="evaluation-grid">
          <section className="benchmark-summary">
            <div className="benchmark-heading">
              <div><h3>Official bilingual benchmark</h3><p>{String(questions ?? "—")} questions · {String(concepts ?? "—")} concepts</p></div>
              <CheckCircle2 size={19} aria-label="Complete" />
            </div>
            <div className="metric-strip">
              <div><span>Hybrid Top-1</span><strong>{percent(hybrid?.top_1)}</strong></div>
              <div><span>Hybrid Top-3</span><strong>{percent(hybrid?.top_3)}</strong></div>
              <div><span>MRR@10</span><strong>{hybrid?.mrr_at_10?.toFixed(3) ?? "—"}</strong></div>
            </div>
            <div className="method-bars" aria-label="Top-3 retrieval comparison">
              {metrics.map((item) => (
                <div className="method-bar" key={methodName(item)}>
                  <span>{methodName(item)}</span>
                  <div><i style={{ width: `${Math.max(0, Math.min(100, (item.top_3 ?? 0) * 100))}%` }} /></div>
                  <strong>{percent(item.top_3)}</strong>
                </div>
              ))}
            </div>
          </section>
          <section className="performance-summary">
            <div className="benchmark-heading">
              <div><h3>Retrieval latency</h3><p>Descriptive local benchmark measurements</p></div>
              <Gauge size={19} aria-hidden="true" />
            </div>
            <div className="latency-list">
              {latency.map((item) => (
                <div key={methodName(item)}>
                  <span><Activity size={15} /> {methodName(item)}</span>
                  <strong>{item.latency_ms?.p95?.toFixed(1) ?? "—"} ms</strong>
                  <small>p95 · n={item.samples ?? item.latency_ms?.samples ?? "—"}</small>
                </div>
              ))}
            </div>
            <p className="measurement-context">{performance.data.measurement_context}</p>
          </section>
        </div>
      ) : null}
    </section>
  );
}
