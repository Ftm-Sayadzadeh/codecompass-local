import { FolderInput, LoaderCircle, RefreshCw } from "lucide-react";
import type { FormEvent } from "react";

import type { IndexResponse, Project } from "../api/types";
import { ErrorMessage } from "./ErrorMessage";

export function ProjectSetup({
  path,
  setPath,
  currentProject,
  indexing,
  result,
  error,
  onSubmit,
}: {
  path: string;
  setPath: (value: string) => void;
  currentProject: Project | null;
  indexing: boolean;
  result: IndexResponse | null;
  error: unknown;
  onSubmit: () => void;
}) {
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };
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
          <button className="primary-button" type="submit" disabled={indexing || !path.trim()}>
            {indexing ? <LoaderCircle className="spin" size={17} /> : currentProject ? <RefreshCw size={17} /> : <FolderInput size={17} />}
            {indexing ? "Indexing repository..." : currentProject ? "Index / Re-index" : "Index repository"}
          </button>
        </div>
      </form>
      {error ? <ErrorMessage error={error} /> : null}
      {result ? (
        <div className="index-result" role="status">
          <strong>{result.operation === "reindexed" ? "Repository re-indexed" : "Repository ready"}</strong>
          <span>{result.complete ? "Vector index verified" : "Index incomplete"}</span>
          <span>{result.embedding.provider} · {result.embedding.model}</span>
        </div>
      ) : null}
    </section>
  );
}
