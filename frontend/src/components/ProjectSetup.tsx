import { Check, Circle, FolderInput, LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import type { FormEvent } from "react";

import type { IndexJob, IndexJobState, Project } from "../api/types";
import { ErrorMessage } from "./ErrorMessage";

const stages: Array<{ state: Exclude<IndexJobState, "completed" | "failed">; label: string }> = [
  { state: "scanning", label: "Check source changes" },
  { state: "parsing", label: "Parse symbols" },
  { state: "chunking", label: "Build chunks" },
  { state: "preflight", label: "Provider preflight" },
  { state: "embedding", label: "Generate embeddings" },
  { state: "verifying", label: "Verify vectors" },
  { state: "activating", label: "Activate index" },
];

const counters: Array<[string, string]> = [
  ["files_discovered", "Files discovered"],
  ["files_unchanged", "Files unchanged"],
  ["files_added", "Files added"],
  ["files_modified", "Files modified"],
  ["files_deleted", "Files deleted"],
  ["files_parsed", "Files parsed"],
  ["symbols_extracted", "Symbols"],
  ["chunks_generated", "Chunks"],
  ["embeddings_completed", "Embeddings completed"],
  ["chunks_expected", "Expected vectors"],
  ["vectors_stored", "Stored vectors"],
  ["chunks_reused", "Chunks reused"],
  ["vectors_reused", "Vectors reused"],
  ["vectors_deleted", "Vectors removed"],
  ["embedding_retries", "Embedding retries"],
  ["compacted_embeddings", "Compacted embeddings"],
  ["largest_embedding_input_chars", "Largest input characters"],
];

export function ProjectSetup({
  path,
  setPath,
  currentProject,
  job,
  error,
  onSubmit,
}: {
  path: string;
  setPath: (value: string) => void;
  currentProject: Project | null;
  job: IndexJob | null;
  error: unknown;
  onSubmit: () => void;
}) {
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };
  const indexing = Boolean(job && job.state !== "completed" && job.state !== "failed");
  const currentStage = job?.state === "failed" ? job.error?.stage : job?.state;
  const observedStages = new Set(job?.observed_stages ?? (
    stages.some(({ state }) => state === currentStage)
      ? [currentStage as Exclude<IndexJobState, "completed" | "failed">]
      : []
  ));
  const visibleCounters = job ? counters.filter(([key]) => Object.hasOwn(job.counters, key)) : [];
  const noChanges = job?.result?.no_changes === true;
  const currentStageIndex = stages.findIndex(({ state }) => state === currentStage);
  const visibleStages = noChanges ? stages.filter(({ state }) => observedStages.has(state)) : stages;
  const embeddingsCompleted = job?.counters.embeddings_completed;
  const embeddingsExpected = job?.counters.chunks_expected;
  const hasEmbeddingProgress = currentStage === "embedding" && embeddingsExpected !== undefined && embeddingsExpected > 0;
  const embeddingProgress = hasEmbeddingProgress
    ? Math.min(100, ((embeddingsCompleted ?? 0) / embeddingsExpected) * 100)
    : 0;
  const summaryStats = job ? [
    ["Files", noChanges ? currentProject?.files : job.counters.files_parsed ?? job.counters.files_discovered],
    ["Symbols", noChanges ? currentProject?.symbols : job.counters.symbols_extracted],
    ["Chunks", noChanges ? currentProject?.chunks : job.counters.chunks_generated],
    ["Vectors", job.counters.vectors_stored ?? job.counters.embeddings_completed ?? job.counters.chunks_expected],
  ] as const : [];
  return (
    <section className="setup-band" aria-labelledby="repository-setup-title">
      <div className="setup-copy">
        <span className="eyebrow">Local Python repository</span>
        <h2 id="repository-setup-title">{currentProject ? "Index another repository or refresh the current source" : "Connect your first repository"}</h2>
        <p>Repository paths are used for this request only and are not stored by the browser.</p>
      </div>
      <form onSubmit={submit} className="setup-form">
        <label htmlFor="repository-path">Repository path</label>
        <div className="path-action">
          <div className="path-input">
            <FolderInput size={18} aria-hidden="true" />
            <input id="repository-path" value={path} onChange={(event) => setPath(event.target.value)} placeholder="<local-repository-path>" autoComplete="off" spellCheck={false} />
          </div>
          <button className="primary-button" type="submit" disabled={indexing || (!path.trim() && !currentProject)}>
            {indexing ? <LoaderCircle className="spin" size={17} /> : currentProject ? <RefreshCw size={17} /> : <FolderInput size={17} />}
            {indexing ? "Working..." : currentProject ? "Index / Re-index" : "Index repository"}
          </button>
        </div>
      </form>
      {error ? <ErrorMessage error={error} /> : null}
      {job ? (
        <div className="index-progress" aria-live="polite">
          <div className="index-progress-heading">
            <div>
              <strong>{noChanges ? "Repository already up to date" : job.state === "completed" ? "Repository ready" : job.state === "failed" ? "Indexing failed" : currentProject ? "Updating repository" : "Indexing repository"}</strong>
              <span>{noChanges ? "Existing verified index retained" : job.state === "completed" ? "Observed pipeline stages completed" : job.state === "failed" ? `Stopped during ${job.error?.stage ?? "indexing"}` : `${stages.find(({ state }) => state === currentStage)?.label ?? "Preparing index"}${currentStageIndex >= 0 ? ` · Stage ${currentStageIndex + 1} of ${stages.length}` : ""}`}</span>
              {indexing && currentProject?.vector_complete ? <span>Current verified index remains available during this update.</span> : null}
            </div>
            <span>Elapsed {job.elapsed_seconds.toFixed(1)}s</span>
          </div>
          {hasEmbeddingProgress ? (
            <div className="index-stage-progress">
              <div><span>Embedding progress</span><strong>{embeddingsCompleted ?? 0} / {embeddingsExpected}</strong></div>
              <div className="index-progress-track" role="progressbar" aria-label="Embedding progress" aria-valuemin={0} aria-valuemax={embeddingsExpected} aria-valuenow={embeddingsCompleted ?? 0}>
                <i style={{ width: `${embeddingProgress}%` }} />
              </div>
            </div>
          ) : null}
          <ol className="index-timeline" aria-label="Indexing progress">
            {visibleStages.map((stage) => {
              const current = currentStage === stage.state;
              const complete = observedStages.has(stage.state) && !current;
              return (
                <li className={complete ? "complete" : current ? "current" : "pending"} key={stage.state}>
                  {complete ? <Check size={15} /> : current && indexing ? <LoaderCircle className="spin" size={15} /> : current && job.state === "failed" ? <TriangleAlert size={15} /> : <Circle size={12} />}
                  <span>{stage.label}</span>
                </li>
              );
            })}
          </ol>
          <div className="index-stats" aria-label="Indexing counters">
            {summaryStats.map(([label, value]) => (
              <div key={label}><span>{label}</span><strong>{value ?? "—"}</strong></div>
            ))}
          </div>
          {visibleCounters.length ? (
            <details className="index-diagnostics">
              <summary>Technical details</summary>
              <div className="index-progress-meta">
                {visibleCounters.map(([key, label]) => <span key={key}>{label}: <strong>{job.counters[key]}</strong></span>)}
              </div>
            </details>
          ) : null}
          {job.state === "failed" && job.error ? (
            <div className="index-failure" role="alert">
              <strong>{job.error.message}</strong>
              <span>Failed during {job.error.stage}.</span>
              {job.previous_index_preserved === true ? <span>Previous index remains available.</span> : null}
              <button className="secondary-button" type="button" onClick={onSubmit}><RefreshCw size={16} /> Retry / Re-index</button>
            </div>
          ) : null}
        </div>
      ) : null}
      {job?.result && !noChanges ? (
        <div className="index-result" role="status">
          <strong>{job.result.no_changes ? "Repository is already up to date" : job.result.strategy === "incremental" ? "Incremental update complete" : job.result.operation === "reindexed" ? "Full re-index complete" : "Repository ready"}</strong>
          <span>{job.result.complete ? "Vector index verified" : "Index incomplete"}</span>
          <span>{job.result.embedding.provider} · {job.result.embedding.model}</span>
        </div>
      ) : null}
    </section>
  );
}
