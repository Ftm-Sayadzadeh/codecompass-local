import { Activity, BarChart3, CheckCircle2, ChevronDown, ChevronUp, Gauge, Info, Snowflake } from "lucide-react";
import { useState } from "react";

import type { EvaluationResponse, MetricAggregate } from "../api/types";
import { ErrorMessage } from "./ErrorMessage";

type Perspective = "all" | "fa" | "en" | "compare";

const methods = ["lexical", "semantic", "hybrid"] as const;

function percent(value: number | undefined) {
  return value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

function methodName(item: MetricAggregate) {
  return item.method ?? item.slice.method ?? "unknown";
}

function qualityMetrics(response: EvaluationResponse | null, perspective: Exclude<Perspective, "compare">) {
  return (response?.data.aggregates ?? []).filter((item) => perspective === "all"
    ? item.slice.kind === "global_micro"
    : item.slice.kind === "language" && item.slice.value === perspective);
}

function methodPerformance(response: EvaluationResponse | null) {
  return (response?.data.aggregates ?? []).filter((item) => item.slice.kind === "method");
}

function scoreWidth(value: number | undefined) {
  return `${Math.max(0, Math.min(100, (value ?? 0) * 100))}%`;
}

function MethodRows({ metrics }: { metrics: MetricAggregate[] }) {
  const best = metrics.reduce<MetricAggregate | null>((current, item) => !current || (item.mrr_at_10 ?? -1) > (current.mrr_at_10 ?? -1) ? item : current, null);
  return methods.map((method) => {
    const item = metrics.find((candidate) => methodName(candidate) === method);
    if (!item) return null;
    return (
      <div className={`metric-table-row method-${method}`} role="row" key={method}>
        <span className="method-label" role="cell"><i />{method}{methodName(best ?? item) === method ? <small>Best measured</small> : null}</span>
        <span className="metric-cell" role="cell" data-label="Top-1"><b>{percent(item.top_1)}</b><i><em style={{ width: scoreWidth(item.top_1) }} /></i></span>
        <span className="metric-cell" role="cell" data-label="Top-3"><b>{percent(item.top_3)}</b><i><em style={{ width: scoreWidth(item.top_3) }} /></i></span>
        <strong role="cell" data-label="MRR@10">{item.mrr_at_10?.toFixed(3) ?? "—"}</strong>
      </div>
    );
  });
}

function LanguageComparison({ label, metrics }: { label: string; metrics: MetricAggregate[] }) {
  return (
    <section className="language-comparison-column" aria-label={`${label} retrieval results`}>
      <header><strong>{label}</strong><span>{metrics.find((item) => methodName(item) === "hybrid")?.questions ?? "—"} questions</span></header>
      <div className="comparison-head"><span>Method</span><span>Top-1</span><span>Top-3</span><span>MRR</span></div>
      {methods.map((method) => {
        const item = metrics.find((candidate) => methodName(candidate) === method);
        if (!item) return null;
        return (
          <div className={`comparison-row method-${method}`} key={method}>
            <strong><i />{method}</strong>
            <span><b>{percent(item.top_1)}</b><i><em style={{ width: scoreWidth(item.top_1) }} /></i></span>
            <span><b>{percent(item.top_3)}</b><i><em style={{ width: scoreWidth(item.top_3) }} /></i></span>
            <b>{item.mrr_at_10?.toFixed(3) ?? "—"}</b>
          </div>
        );
      })}
    </section>
  );
}

export function EvaluationPanel({ summary, performance, loading, error }: {
  summary: EvaluationResponse | null;
  performance: EvaluationResponse | null;
  loading: boolean;
  error: unknown;
}) {
  const [expanded, setExpanded] = useState(false);
  const [perspective, setPerspective] = useState<Perspective>("all");
  const overall = qualityMetrics(summary, "all");
  const persian = qualityMetrics(summary, "fa");
  const english = qualityMetrics(summary, "en");
  const metrics = perspective === "compare" ? overall : qualityMetrics(summary, perspective);
  const hybrid = metrics.find((item) => methodName(item) === "hybrid");
  const persianHybrid = persian.find((item) => methodName(item) === "hybrid");
  const englishHybrid = english.find((item) => methodName(item) === "hybrid");
  const bestMethod = overall.reduce<MetricAggregate | null>((best, item) => !best || (item.mrr_at_10 ?? -1) > (best.mrr_at_10 ?? -1) ? item : best, null);
  const latency = methodPerformance(performance);
  const questions = summary?.data.benchmark?.questions ?? hybrid?.questions;
  const concepts = summary?.data.benchmark?.concepts;

  return (
    <section className="evaluation-band" aria-labelledby="evaluation-title">
      <header>
        <div><span className="eyebrow">Scientific evaluation</span><h2 id="evaluation-title"><BarChart3 size={19} /> Evaluation and performance</h2></div>
        <div className="evaluation-header-actions">
          <div className="evaluation-note"><Info size={15} /> Benchmark evaluation results — not per-answer confidence.</div>
          <button className="secondary-button evaluation-toggle" type="button" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}{expanded ? "Hide results" : "Show results"}
          </button>
        </div>
      </header>
      {expanded && loading ? <div className="evaluation-loading">Loading evaluation artifacts...</div> : null}
      {expanded && error ? <ErrorMessage error={error} /> : null}
      {expanded && summary && performance ? (
        <div className="evaluation-surface">
          <div className="evaluation-toolbar">
            <div className="benchmark-identity">
              <span className="frozen-badge"><Snowflake size={14} /> Frozen benchmark</span>
              <div><strong>Official bilingual benchmark</strong><small>{String(questions ?? "—")} questions · {String(concepts ?? "—")} concepts</small></div>
            </div>
            <div className="segmented evaluation-perspective" aria-label="Evaluation perspective">
              <button type="button" aria-label="Show overall evaluation" className={perspective === "all" ? "active" : ""} onClick={() => setPerspective("all")} aria-pressed={perspective === "all"}>Overall</button>
              <button type="button" aria-label="Show Persian evaluation" className={perspective === "fa" ? "active" : ""} onClick={() => setPerspective("fa")} aria-pressed={perspective === "fa"}>Persian</button>
              <button type="button" aria-label="Show English evaluation" className={perspective === "en" ? "active" : ""} onClick={() => setPerspective("en")} aria-pressed={perspective === "en"}>English</button>
              <button type="button" aria-label="Compare Persian and English evaluation" className={perspective === "compare" ? "active" : ""} onClick={() => setPerspective("compare")} aria-pressed={perspective === "compare"}>Compare</button>
            </div>
          </div>

          <div className="scientific-summary" aria-label="Scientific benchmark summary">
            <div><span>Best method</span><strong>{bestMethod ? methodName(bestMethod) : "—"}</strong></div>
            <div><span>Persian Top-3</span><strong>{percent(persianHybrid?.top_3)}</strong></div>
            <div><span>English Top-3</span><strong>{percent(englishHybrid?.top_3)}</strong></div>
            <div><span>Benchmark size</span><strong>{String(questions ?? "—")}</strong><small>questions</small></div>
          </div>

          {perspective === "compare" ? (
            <div className="language-comparison">
              <LanguageComparison label="Persian" metrics={persian} />
              <LanguageComparison label="English" metrics={english} />
            </div>
          ) : (
            <div className="evaluation-grid">
              <section className="benchmark-summary" aria-label="Retrieval quality">
                <div className="benchmark-heading"><div><h3>Retrieval quality</h3><p>Higher scores indicate stronger target ranking.</p></div><CheckCircle2 size={18} aria-label="Complete" /></div>
                <div className="metric-strip">
                  <div><span>Hybrid Top-1</span><strong>{percent(hybrid?.top_1)}</strong></div>
                  <div><span>Hybrid Top-3</span><strong>{percent(hybrid?.top_3)}</strong></div>
                  <div><span>Hybrid MRR@10</span><strong>{hybrid?.mrr_at_10?.toFixed(3) ?? "—"}</strong></div>
                </div>
                <div className="metric-table" role="table" aria-label="Retrieval method comparison">
                  <div className="metric-table-head" role="row"><span role="columnheader">Method</span><span role="columnheader">Top-1</span><span role="columnheader">Top-3</span><span role="columnheader">MRR@10</span></div>
                  <MethodRows metrics={metrics} />
                </div>
              </section>

              <section className="performance-summary" aria-label="Retrieval latency">
                <div className="benchmark-heading"><div><h3>Retrieval latency</h3><p>Recorded local benchmark measurements.</p></div><Gauge size={18} aria-hidden="true" /></div>
                <div className="latency-table">
                  <div className="latency-head"><span>Method</span><span>p50</span><span>p95</span><span>Samples</span></div>
                  {latency.map((item) => (
                    <div className={`latency-row method-${methodName(item)}`} key={methodName(item)}>
                      <span><Activity size={14} /> {methodName(item)}</span>
                      <strong data-label="p50">{item.latency_ms?.p50?.toFixed(1) ?? "—"} ms</strong>
                      <strong data-label="p95">{item.latency_ms?.p95?.toFixed(1) ?? "—"} ms</strong>
                      <strong data-label="Samples">{item.samples ?? item.latency_ms?.samples ?? "—"}</strong>
                    </div>
                  ))}
                </div>
                <p className="measurement-context">{performance.data.measurement_context}</p>
              </section>
            </div>
          )}
          <p className="evaluation-disclaimer"><Info size={14} /> Fixed-dataset measurements for system evaluation; they do not represent confidence or quality for an individual answer.</p>
        </div>
      ) : null}
    </section>
  );
}
