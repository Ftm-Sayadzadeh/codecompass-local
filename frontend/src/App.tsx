import { Compass, Database, FolderCog, Menu, PanelLeftClose, Settings, ShieldCheck } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useState } from "react";

import { api, embeddingOverride, providerOverride } from "./api/client";
import type {
  AskResponse,
  DocumentationResponse,
  EmbeddingState,
  EvaluationResponse,
  IndexResponse,
  Project,
  ProviderState,
  RetrievalMethod,
  SearchResponse,
  SourceFile,
  SymbolItem,
} from "./api/types";
import type { SourceSelection } from "./components/CodeDrawer";
import type { NavigationCitation } from "./components/CitationList";
import { ErrorMessage } from "./components/ErrorMessage";
import { EvaluationPanel } from "./components/EvaluationPanel";
import { ProjectExplorer } from "./components/ProjectExplorer";
import { ProjectSetup } from "./components/ProjectSetup";
import { ProviderSettings } from "./components/ProviderSettings";
import { Workspace, type WorkspaceTab } from "./components/Workspace";

const defaultEmbedding: EmbeddingState = {
  useBackendDefault: true,
  provider: "ollama",
  baseUrl: "",
  model: "",
  apiKey: "",
  timeoutSeconds: "",
  dimensions: "",
};

const CodeDrawer = lazy(() => import("./components/CodeDrawer").then((module) => ({ default: module.CodeDrawer })));

const defaultLlm: ProviderState = {
  useBackendDefault: true,
  provider: "ollama",
  baseUrl: "",
  model: "",
  apiKey: "",
  timeoutSeconds: "",
};

interface RequestState<T> {
  result: T | null;
  loading: boolean;
  error: unknown;
}

const idle = <T,>(): RequestState<T> => ({ result: null, loading: false, error: null });

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<SourceFile[]>([]);
  const [symbols, setSymbols] = useState<SymbolItem[]>([]);
  const [repositoryPath, setRepositoryPath] = useState("");
  const [projectLoading, setProjectLoading] = useState(true);
  const [projectError, setProjectError] = useState<unknown>(null);
  const [indexState, setIndexState] = useState<RequestState<IndexResponse>>(idle);
  const [embedding, setEmbedding] = useState(defaultEmbedding);
  const [llm, setLlm] = useState(defaultLlm);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [explorerOpen, setExplorerOpen] = useState(() => window.innerWidth > 900);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("ask");
  const [askState, setAskState] = useState<RequestState<AskResponse>>(idle);
  const [searchState, setSearchState] = useState<RequestState<SearchResponse>>(idle);
  const [documentationState, setDocumentationState] = useState<RequestState<DocumentationResponse>>(idle);
  const [documentationPreset, setDocumentationPreset] = useState<string | number | null>(null);
  const [source, setSource] = useState<SourceSelection | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState<unknown>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [performance, setPerformance] = useState<EvaluationResponse | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState(true);
  const [evaluationError, setEvaluationError] = useState<unknown>(null);

  const resetWorkspace = useCallback(() => {
    setAskState(idle());
    setSearchState(idle());
    setDocumentationState(idle());
    setDocumentationPreset(null);
    setSource(null);
    setSourceError(null);
  }, []);

  const loadProject = useCallback(async (projectId: number) => {
    setProjectLoading(true);
    setProjectError(null);
    resetWorkspace();
    try {
      const [detail, projectFiles, projectSymbols] = await Promise.all([
        api.project(projectId),
        api.files(projectId),
        api.symbols(projectId),
      ]);
      setProject(detail);
      setFiles(projectFiles);
      setSymbols(projectSymbols);
    } catch (error) {
      setProjectError(error);
      setProject(null);
      setFiles([]);
      setSymbols([]);
    } finally {
      setProjectLoading(false);
    }
  }, [resetWorkspace]);

  useEffect(() => {
    let active = true;
    void api.projects().then((items) => {
      if (!active) return;
      setProjects(items);
      setSetupOpen(items.length === 0);
      if (items[0]) void loadProject(items[0].id);
      else setProjectLoading(false);
    }).catch((error) => {
      if (active) { setProjectError(error); setProjectLoading(false); }
    });
    void Promise.all([api.evaluation(), api.performance()]).then(([summary, measured]) => {
      if (active) { setEvaluation(summary); setPerformance(measured); }
    }).catch((error) => { if (active) setEvaluationError(error); }).finally(() => { if (active) setEvaluationLoading(false); });
    return () => { active = false; };
  }, [loadProject]);

  const refreshProjects = async (projectId: number) => {
    const items = await api.projects();
    setProjects(items);
    await loadProject(projectId);
  };

  const indexRepository = async () => {
    if (!repositoryPath.trim()) return;
    setIndexState({ result: null, loading: true, error: null });
    try {
      const result = await api.index(repositoryPath.trim(), embeddingOverride(embedding));
      setIndexState({ result, loading: false, error: null });
      await refreshProjects(result.project_id);
      setSetupOpen(false);
    } catch (error) {
      setIndexState({ result: null, loading: false, error });
    }
  };

  const reindex = () => setSetupOpen(true);

  const openSource = async (fileId: number, startLine?: number, endLine?: number) => {
    if (!project) return;
    setSource(null);
    setSourceError(null);
    setSourceLoading(true);
    try {
      const content = await api.source(project.id, fileId);
      setSource({ content, startLine, endLine });
    } catch (error) {
      setSourceError(error);
    } finally {
      setSourceLoading(false);
    }
  };

  const openCitation = (citation: NavigationCitation) => void openSource(citation.fileId, citation.startLine, citation.endLine);

  const ask = async (question: string, method: RetrievalMethod, maxTokens?: number) => {
    if (!project) return;
    setAskState({ result: null, loading: true, error: null });
    try {
      const result = await api.ask(project.id, question, method, embeddingOverride(embedding), providerOverride(llm), maxTokens);
      setAskState({ result, loading: false, error: null });
    } catch (error) {
      setAskState({ result: null, loading: false, error });
    }
  };

  const search = async (query: string, method: RetrievalMethod, limit: number) => {
    if (!project) return;
    setSearchState({ result: null, loading: true, error: null });
    try {
      const result = await api.search(project.id, query, method, limit, embeddingOverride(embedding));
      setSearchState({ result, loading: false, error: null });
    } catch (error) {
      setSearchState({ result: null, loading: false, error });
    }
  };

  const documentSymbol = async (identifier: string | number, language: "en" | "fa") => {
    if (!project) return;
    setDocumentationPreset(identifier);
    setDocumentationState({ result: null, loading: true, error: null });
    try {
      const result = await api.documentation(project.id, identifier, language, providerOverride(llm));
      setDocumentationState({ result, loading: false, error: null });
    } catch (error) {
      setDocumentationState({ result: null, loading: false, error });
    }
  };

  const chooseDocumentation = (symbol: SymbolItem) => {
    setDocumentationPreset(symbol.id);
    setWorkspaceTab("documentation");
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#workspace" aria-label="CodeCompass workspace"><Compass size={25} /><strong>CodeCompass</strong></a>
        <div className="project-switcher">
          <Database size={16} aria-hidden="true" />
          <label className="sr-only" htmlFor="project-select">Current project</label>
          <select id="project-select" value={project?.id ?? ""} disabled={!projects.length || projectLoading} onChange={(event) => void loadProject(Number(event.target.value))}>
            {!projects.length ? <option value="">No indexed projects</option> : null}
            {projects.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
          </select>
        </div>
        <span className={`status-badge ${project?.vector_complete ? "ready" : "idle"}`}><i />{projectLoading ? "Loading" : project?.vector_complete ? "Ready" : project ? "Needs attention" : "No project"}</span>
        <div className="top-actions">
          <button className="secondary-button mobile-explorer-toggle" type="button" onClick={() => setExplorerOpen((current) => !current)}><Menu size={17} /> Explorer</button>
          <button className="secondary-button" type="button" onClick={() => setSetupOpen((current) => !current)}><FolderCog size={17} /> Repository</button>
          <button className="secondary-button" type="button" onClick={() => setSettingsOpen(true)}><Settings size={17} /> Provider settings</button>
        </div>
      </header>

      {setupOpen ? <ProjectSetup path={repositoryPath} setPath={setRepositoryPath} currentProject={project} indexing={indexState.loading} result={indexState.result} error={indexState.error} onSubmit={indexRepository} /> : null}
      {projectError ? <div className="global-error"><ErrorMessage error={projectError} onReindex={reindex} /></div> : null}

      <div className={`main-layout ${source || sourceLoading || sourceError ? "with-code" : ""} ${explorerOpen ? "" : "explorer-closed"}`} id="workspace">
        {project && explorerOpen ? <ProjectExplorer files={files} symbols={symbols} onOpenFile={(file) => void openSource(file.id)} onOpenSymbol={(symbol) => void openSource(symbol.file_id, symbol.start_line, symbol.end_line)} onDocumentSymbol={chooseDocumentation} /> : null}
        {project ? (
          <Workspace
            tab={workspaceTab}
            setTab={setWorkspaceTab}
            ask={askState}
            search={searchState}
            documentation={{ ...documentationState, preset: documentationPreset }}
            onAsk={ask}
            onSearch={search}
            onDocument={documentSymbol}
            onOpenCitation={openCitation}
            onReindex={reindex}
          />
        ) : !projectLoading ? (
          <main className="no-project">
            <Compass size={38} />
            <h1>Start with a local Python repository</h1>
            <button className="primary-button" type="button" onClick={() => setSetupOpen(true)}><FolderCog size={17} /> Open repository setup</button>
          </main>
        ) : <main className="no-project"><span className="spinner-large" /><p>Loading workspace...</p></main>}
        {source || sourceLoading || sourceError ? (
          <Suspense fallback={<aside className="code-drawer"><div className="drawer-state">Loading code viewer...</div></aside>}>
            <CodeDrawer selection={source} loading={sourceLoading} error={sourceError} onClose={() => { setSource(null); setSourceError(null); }} onReindex={reindex} />
          </Suspense>
        ) : null}
      </div>

      {project ? (
        <section className="project-facts" aria-label="Repository status">
          <span><strong>{project.files ?? "—"}</strong> Files</span>
          <span><strong>{project.symbols ?? "—"}</strong> Symbols</span>
          <span><strong>{project.chunks ?? "—"}</strong> Chunks</span>
          <span><ShieldCheck size={16} /><strong>{project.vector_complete ? "Verified" : "Incomplete"}</strong> Vector index</span>
          {!explorerOpen ? <button className="icon-button" type="button" onClick={() => setExplorerOpen(true)} title="Open explorer" aria-label="Open explorer"><PanelLeftClose size={17} /></button> : null}
        </section>
      ) : null}

      <EvaluationPanel summary={evaluation} performance={performance} loading={evaluationLoading} error={evaluationError} />
      <ProviderSettings open={settingsOpen} embedding={embedding} llm={llm} onEmbeddingChange={setEmbedding} onLlmChange={setLlm} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
