import { Activity, BarChart3, CheckCircle2, ChevronDown, ChevronUp, Gauge, Info, Snowflake } from "lucide-react";
import { useState } from "react";

import type { BenchmarkQaDetail, BenchmarkQuestion, ContextStrategyEvaluationResponse, EvaluationResponse, FinalThesisEvaluationResponse, MetricAggregate, ThesisQuality, ThesisRankMetrics } from "../api/types";
import { ErrorMessage } from "./ErrorMessage";

type Perspective = "all" | "fa" | "en" | "compare";
type ThesisSection = "overview" | "search" | "qa" | "documentation" | "reliability";

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

function hitPercent(metric: ThesisRankMetrics, key: "hit_at_1" | "hit_at_3" | "hit_at_5") {
  return `${(metric[key] / (metric.cases ?? metric.n ?? 1) * 100).toFixed(1)}%`;
}

function tenPointPercent(value: number | null | undefined) {
  return value == null ? "Unavailable" : `${(value * 10).toFixed(1)}%`;
}

function percentagePoints(value: number | null | undefined) {
  if (value == null) return "Unavailable";
  const points = value * 10;
  return `${points > 0 ? "+" : ""}${points.toFixed(1)} pp`;
}

function QualityRow({ name, quality }: { name: string; quality: ThesisQuality }) {
  return (
    <div className="thesis-table-row">
      <strong>{name}</strong><span data-label="Scored">{quality.scored_records}</span><span data-label="Correctness">{tenPointPercent(quality.correctness_0_10.mean)}</span>
      <span data-label="Groundedness">{tenPointPercent(quality.groundedness_0_10.mean)}</span><span data-label="Persian readability">{tenPointPercent(quality.persian_readability_0_10.mean)}</span><span data-label="Usefulness">{tenPointPercent(quality.usefulness_0_10.mean)}</span>
    </div>
  );
}

function QaRun({ run, models }: { run: BenchmarkQaDetail; models: FinalThesisEvaluationResponse["data"]["models"] }) {
  const persian = Boolean(run.answer && /[\u0600-\u06ff]/.test(run.answer));
  return (
    <details className={`qa-run ${run.execution_status}`}>
      <summary>
        <strong>{models.llms[run.llm_arm] ?? run.llm_arm}</strong>
        <span>{models.embeddings[run.embedding_arm] ?? run.embedding_arm}</span>
        <span>{run.execution_status}</span>
      </summary>
      <div className="qa-run-body">
        <div className="qa-score-strip">
          <span>Correctness <strong>{tenPointPercent(run.human_scores.correctness_0_10)}</strong></span>
          <span>Groundedness <strong>{tenPointPercent(run.human_scores.groundedness_0_10)}</strong></span>
          <span>Readability <strong>{tenPointPercent(run.human_scores.persian_readability_0_10)}</strong></span>
          <span>Usefulness <strong>{tenPointPercent(run.human_scores.usefulness_0_10)}</strong></span>
          <span>Hallucination <strong>{run.human_scores.hallucination ?? "Unavailable"}</strong></span>
        </div>
        <p className="qa-provenance">Execution: {run.execution_provenance.replaceAll("_", " ")}</p>
        {run.answer ? <div className="qa-run-answer" dir={persian ? "rtl" : "ltr"}>{run.answer}</div> : <p className="qa-unavailable">No usable answer was produced in this frozen run.</p>}
        {run.citations.length ? <div className="qa-run-citations"><strong>Retrieved evidence</strong>{run.citations.map((citation, index) => (
          <code key={`${citation.source_file}:${citation.start_line}:${index}`}>{citation.source_file}:{citation.start_line}-{citation.end_line} · {citation.qualified_symbol}</code>
        ))}</div> : null}
      </div>
    </details>
  );
}

function BenchmarkQuestions({ questions, qaDetails, models }: {
  questions: BenchmarkQuestion[] | undefined;
  qaDetails?: BenchmarkQaDetail[];
  models?: FinalThesisEvaluationResponse["data"]["models"];
}) {
  if (!questions?.length) return null;
  const displayed = qaDetails
    ? [...questions].sort((a, b) => Number(b.task === "qa") - Number(a.task === "qa"))
    : questions;
  const qaCount = questions.filter((item) => item.task === "qa").length;
  return (
    <details className="benchmark-questions">
      <summary>View {questions.length} benchmark questions{qaDetails ? <small>{qaCount} QA questions include evaluated answers</small> : null}</summary>
      <div className="benchmark-question-list">
        {displayed.map((item) => {
          const runs = qaDetails?.filter((run) => run.case_id === item.id) ?? [];
          return <article key={item.id}>
            <div><code>{item.id}</code><span>{item.repository}</span><span>{item.task}</span><span>{item.language.toUpperCase()}</span>{item.difficulty ? <span>{item.difficulty}</span> : null}{item.category ? <span>{item.category}</span> : null}</div>
            <p dir={item.language === "fa" ? "rtl" : "ltr"}>{item.question}</p>
            {models && runs.length ? <div className="qa-runs"><strong>{runs.length} evaluated configurations</strong>{runs.map((run) => <QaRun key={`${run.case_id}:${run.embedding_arm}:${run.llm_arm}`} run={run} models={models} />)}</div> : null}
          </article>;
        })}
      </div>
    </details>
  );
}

function FinalThesisView({ result }: { result: FinalThesisEvaluationResponse }) {
  const [section, setSection] = useState<ThesisSection>("overview");
  const { data } = result;
  const gemini2 = data.search.global.gemini_2.semantic;
  const qa = data.qa.quality.qa_by_llm;
  const documentation = data.documentation.quality.by_llm.glm;
  const execution = data.qa.execution.overall;

  return (
    <div className="evaluation-surface thesis-surface">
      <div className="evaluation-toolbar">
        <div className="benchmark-identity">
          <span className="frozen-badge"><Snowflake size={14} /> Frozen evaluation</span>
          <div><strong>Final thesis evaluation</strong><small>{data.design.repositories} repositories · {data.design.search_queries} search queries · {data.human_evaluation.records} human-review records</small></div>
        </div>
        <div className="segmented thesis-sections" aria-label="Final thesis evaluation section">
          {(["overview", "search", "qa", "documentation", "reliability"] as const).map((item) => (
            <button type="button" key={item} className={section === item ? "active" : ""} aria-pressed={section === item} onClick={() => setSection(item)}>{item === "qa" ? "QA" : item[0].toUpperCase() + item.slice(1)}</button>
          ))}
        </div>
      </div>

      {section === "overview" ? <>
        <div className="scientific-summary">
          <div><span>Gemini 2 semantic Top-3</span><strong>{hitPercent(gemini2, "hit_at_3")}</strong></div>
          <div><span>Usable QA outputs</span><strong>{execution.total - execution.final_failure}/{execution.total}</strong></div>
          <div><span>GLM Persian readability</span><strong>{tenPointPercent(qa.glm.persian_readability_0_10.mean)}</strong></div>
          <div><span>Human-scored outputs</span><strong>{data.human_evaluation.usable}/{data.human_evaluation.records}</strong></div>
        </div>
        <div className="thesis-overview">
          <section><h3>Controlled design</h3><p>Three repositories, three embedding arms, and two LLM arms were evaluated with frozen questions and fixed generation settings.</p></section>
          <section><h3>Measured finding</h3><p>Gemini 2 produced the strongest semantic retrieval, while GLM produced stronger QA quality and Persian readability than the local Qwen arm.</p></section>
          <section><h3>Availability rule</h3><p>Unavailable executions remain unavailable. They are never converted into zero-valued quality scores.</p></section>
        </div>
      </> : null}

      {section === "search" ? <section className="thesis-section">
        <div className="benchmark-heading"><div><h3>Search by embedding arm</h3><p>Global results across 36 frozen bilingual queries. Lexical retrieval is unchanged across arms.</p></div><CheckCircle2 size={18} /></div>
        <div className="thesis-table search-comparison">
          <div className="thesis-table-head"><span>Embedding</span><span>Semantic Top-1</span><span>Semantic Top-3</span><span>Semantic MRR</span><span>Hybrid Top-3</span><span>Hybrid MRR</span></div>
          {Object.entries(data.search.global).map(([name, methods]) => <div className="thesis-table-row" key={name}>
            <strong>{data.models.embeddings[name] ?? name}</strong><span data-label="Semantic Top-1">{hitPercent(methods.semantic, "hit_at_1")}</span><span data-label="Semantic Top-3">{hitPercent(methods.semantic, "hit_at_3")}</span><span data-label="Semantic MRR">{methods.semantic.mrr_at_10.toFixed(3)}</span><span data-label="Hybrid Top-3">{hitPercent(methods.hybrid, "hit_at_3")}</span><span data-label="Hybrid MRR">{methods.hybrid.mrr_at_10.toFixed(3)}</span>
          </div>)}
        </div>
      </section> : null}

      {section === "qa" ? <section className="thesis-section">
        <div className="benchmark-heading"><div><h3>Human-evaluated QA quality</h3><p>Only usable generated answers are scored.</p></div><CheckCircle2 size={18} /></div>
        <div className="thesis-table quality-comparison">
          <div className="thesis-table-head"><span>LLM</span><span>Scored</span><span>Correctness</span><span>Groundedness</span><span>Persian readability</span><span>Usefulness</span></div>
          {Object.entries(qa).map(([name, quality]) => <QualityRow key={name} name={data.models.llms[name] ?? name} quality={quality} />)}
        </div>
        <p className="measured-note">Paired GLM minus Qwen effect: {percentagePoints(data.qa.paired_effects.glm_minus_qwen.treatment_minus_control.correctness_0_10.mean)} correctness and {percentagePoints(data.qa.paired_effects.glm_minus_qwen.treatment_minus_control.persian_readability_0_10.mean)} Persian readability.</p>
      </section> : null}

      {section === "documentation" ? <section className="thesis-section">
        <div className="benchmark-heading"><div><h3>Persian function documentation</h3><p>Deterministic facts and verified citations remained outside the model output.</p></div><CheckCircle2 size={18} /></div>
        <div className="scientific-summary compact-summary">
          <div><span>GLM complete</span><strong>{data.documentation.execution.glm_complete}/9</strong></div>
          <div><span>Citation mismatches</span><strong>{data.documentation.execution.citation_identity_mismatches}</strong></div>
          <div><span>Groundedness</span><strong>{tenPointPercent(documentation.groundedness_0_10.mean)}</strong></div>
          <div><span>Persian readability</span><strong>{tenPointPercent(documentation.persian_readability_0_10.mean)}</strong></div>
        </div>
        <div className="availability-note"><strong>Qwen result in this frozen evaluation: unavailable</strong><span>All 9 benchmark executions failed at the local-provider HTTP path. This records execution availability, not Qwen documentation quality or the current product status.</span></div>
      </section> : null}

      {section === "reliability" ? <section className="thesis-section">
        <div className="benchmark-heading"><div><h3>QA execution reliability</h3><p>Original attempts and recovery attempts remain separately traceable.</p></div><Activity size={18} /></div>
        <div className="reliability-grid">
          <div><span>Initial success</span><strong>{execution.initial_success}</strong></div><div><span>Recovered · retry 1</span><strong>{execution.recovered_by_retry_1}</strong></div><div><span>Recovered · retry 2</span><strong>{execution.recovered_by_retry_2}</strong></div><div className="failure"><span>Final failure</span><strong>{execution.final_failure}</strong></div>
        </div>
        <p className="measured-note">Final usable QA answers: {execution.total - execution.final_failure}/{execution.total}. Documentation: {data.documentation.final_status.usable_documentation_outputs} usable and {data.documentation.final_status.unavailable_documentation_outputs} unavailable.</p>
      </section> : null}

      <BenchmarkQuestions questions={data.questions} qaDetails={data.qa_details} models={data.models} />
      <p className="evaluation-disclaimer"><Info size={14} /> Human-reviewed, fixed-dataset measurements. Missing executions are reported separately from measured quality.</p>
    </div>
  );
}

function ContextStrategyView({ result }: { result: ContextStrategyEvaluationResponse }) {
  const comparisons = [
    ["Semantic vs Whole repository", result.data.comparisons.semantic_vs_whole_repo, "whole_mean"],
    ["Semantic vs Lexical", result.data.comparisons.semantic_vs_lexical, "lexical_mean"],
    ["Semantic vs Git Agent", result.data.comparisons.semantic_vs_git_agent, "agent_mean"],
  ] as const;
  const lexical = result.data.comparisons.semantic_vs_lexical.metrics.quality;
  const agent = result.data.comparisons.semantic_vs_git_agent.metrics.quality;
  const whole = result.data.comparisons.semantic_vs_whole_repo.metrics.quality;
  return (
    <div className="evaluation-surface thesis-surface">
      <div className="evaluation-toolbar">
        <div className="benchmark-identity">
          <span className="frozen-badge"><Snowflake size={14} /> Blind human evaluation</span>
          <div><strong>Repository context strategy</strong><small>{result.data.review.unique_responses} independently scored responses · {result.data.review.pairs_per_comparison} paired questions per comparison</small></div>
        </div>
      </div>
      <div className="experiment-purpose">
        <strong>Research question</strong>
        <span>Which way of supplying repository evidence to the same GLM gives the best balance of answer quality, cost, speed, and scalability?</span>
      </div>
      <div className="scientific-summary">
        <div><span>Embedding gain vs lexical</span><strong>{percentagePoints(lexical.delta)}</strong></div>
        <div><span>Semantic vs Agent</span><strong>{percentagePoints(agent.delta)}</strong><small>p = {agent.p_exact.toFixed(3)}</small></div>
        <div><span>Whole-repo advantage</span><strong>{percentagePoints(-whole.delta)}</strong><small>successful outputs only</small></div>
        <div><span>Missing human ratings</span><strong>{result.data.review.missing_ratings}</strong></div>
      </div>
      <section className="thesis-section">
        <div className="benchmark-heading"><div><h3>Human-scored answer quality</h3><p>Quality is the mean of fact coverage, correctness, groundedness, and completeness. Scores are displayed as percentages.</p></div><CheckCircle2 size={18} /></div>
        <div className="thesis-table quality-comparison">
          <div className="thesis-table-head"><span>Comparison</span><span>Semantic</span><span>Other method</span><span>Difference</span><span>95% CI</span><span>Exact p</span></div>
          {comparisons.map(([label, comparison, baseline]) => {
            const metric = comparison.metrics.quality;
            return <div className="thesis-table-row" key={label}>
              <strong>{label}</strong><span data-label="Semantic">{tenPointPercent(metric.semantic_mean)}</span><span data-label="Other method">{tenPointPercent(metric[baseline])}</span><span data-label="Difference">{percentagePoints(metric.delta)}</span><span data-label="95% CI">{percentagePoints(metric.ci95[0])} to {percentagePoints(metric.ci95[1])}</span><span data-label="Exact p">{metric.p_exact.toFixed(3)}</span>
            </div>;
          })}
        </div>
        <div className="experiment-findings" aria-label="Experiment questions and conclusions">
          <article>
            <strong>1 · Selected context or whole repository?</strong>
            <p><b>Question:</b> Is RAG-selected context more accurate than sending all source files directly to GLM?</p>
            <p><b>Conclusion:</b> Not on successful small-repository outputs: Whole Repository scored 99.6% versus 85.8% (p = 0.031). This does not prove Whole Repository is generally better: Semantic RAG used about 95% fewer prompt tokens, had lower median latency (16.0s vs 26.1s), and still ran when the large-repository input was unavailable.</p>
          </article>
          <article>
            <strong>2 · Does embedding add value?</strong>
            <p><b>Question:</b> Does semantic retrieval improve final answers beyond retrieval based only on lexical token overlap?</p>
            <p><b>Conclusion:</b> Yes in this benchmark. Semantic RAG scored 87.7% versus 45.2%, a significant +42.5 pp gain (95% CI +24.0 to +61.0; p = 0.004).</p>
          </article>
          <article>
            <strong>3 · Does a tool-using Git Agent help?</strong>
            <p><b>Question:</b> Does cloning the repository and letting OpenCode/GLM inspect it with tools produce better answers than Semantic RAG?</p>
            <p><b>Conclusion:</b> Better quality was not demonstrated: Semantic RAG scored 87.7% versus 78.3%, and the difference was not significant (p = 0.309). The Agent enabled dynamic large-repository access, but its median latency was 2.34× higher and its cost was about 8.5–10× higher.</p>
          </article>
        </div>
      </section>
      <p className="evaluation-disclaimer"><Info size={14} /> One independent reviewer scored anonymized outputs. Inter-rater agreement is unavailable.</p>
    </div>
  );
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

export function EvaluationPanel({ summary, performance, finalThesis, contextStrategy, loading, error }: {
  summary: EvaluationResponse | null;
  performance: EvaluationResponse | null;
  finalThesis: FinalThesisEvaluationResponse | null;
  contextStrategy: ContextStrategyEvaluationResponse | null;
  loading: boolean;
  error: unknown;
}) {
  const [expanded, setExpanded] = useState(false);
  const [dataset, setDataset] = useState<"official" | "thesis" | "context">("official");
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
      {expanded && summary && performance && finalThesis && contextStrategy ? <>
        <div className="segmented evaluation-datasets" aria-label="Evaluation dataset">
          <button type="button" className={dataset === "official" ? "active" : ""} aria-pressed={dataset === "official"} onClick={() => setDataset("official")}>Official retrieval</button>
          <button type="button" className={dataset === "thesis" ? "active" : ""} aria-pressed={dataset === "thesis"} onClick={() => setDataset("thesis")}>Final thesis evaluation</button>
          <button type="button" className={dataset === "context" ? "active" : ""} aria-pressed={dataset === "context"} onClick={() => setDataset("context")}>Context strategy experiment</button>
        </div>
        {dataset === "official" ? (
        <div className="evaluation-surface">
          <div className="evaluation-toolbar">
            <div className="benchmark-identity">
              <span className="frozen-badge"><Snowflake size={14} /> Frozen benchmark</span>
              <div><strong>Official bilingual retrieval benchmark</strong><small>{String(questions ?? "—")} questions · {String(concepts ?? "—")} concepts · Embedding: Nomic local</small></div>
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
          <BenchmarkQuestions questions={summary.data.questions} />
          <p className="evaluation-disclaimer"><Info size={14} /> Fixed-dataset measurements for system evaluation; they do not represent confidence or quality for an individual answer.</p>
        </div>
        ) : dataset === "thesis" ? <FinalThesisView result={finalThesis} /> : <ContextStrategyView result={contextStrategy} />}
      </> : null}
    </section>
  );
}
