import type {
  ApiErrorBody,
  AskResponse,
  DocumentationResponse,
  EmbeddingOverride,
  EmbeddingState,
  EvaluationResponse,
  IndexJob,
  IndexResponse,
  Project,
  ProviderOverride,
  ProviderState,
  RetrievalMethod,
  SearchResponse,
  SourceContent,
  SourceFile,
  SymbolItem,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
  });
  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // The UI deliberately does not render raw non-contract responses.
    }
    throw new ApiError(
      response.status,
      body?.error?.code ?? "request_failed",
      body?.error?.message ?? "The request could not be completed.",
      body?.error?.details ?? {},
    );
  }
  if (response.status === 204) return null as T;
  return (await response.json()) as T;
}

function compact<T extends Record<string, unknown>>(value: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined && item !== ""),
  ) as Partial<T>;
}

export function providerOverride(value: ProviderState): ProviderOverride | undefined {
  if (value.useBackendDefault) return undefined;
  return compact({
    provider: value.provider,
    base_url: value.baseUrl.trim() || undefined,
    model: value.model.trim() || undefined,
    api_key: value.apiKey || undefined,
    timeout_seconds: value.timeoutSeconds ? Number(value.timeoutSeconds) : undefined,
  });
}

export function embeddingOverride(value: EmbeddingState): EmbeddingOverride | undefined {
  const base = providerOverride(value);
  if (!base) return undefined;
  return compact({
    ...base,
    dimensions: value.dimensions ? Number(value.dimensions) : undefined,
  });
}

export const api = {
  projects: () => request<Project[]>("/projects"),
  project: (projectId: number) => request<Project>(`/projects/${projectId}`),
  index: (repositoryPath: string, embedding: EmbeddingOverride | undefined) =>
    request<IndexResponse>("/projects/index", {
      method: "POST",
      body: JSON.stringify(compact({ repository_path: repositoryPath, embedding })),
    }),
  startIndexJob: (
    target: { repositoryPath?: string; projectId?: number },
    embedding: EmbeddingOverride | undefined,
  ) =>
    request<IndexJob>("/projects/index-jobs", {
      method: "POST",
      body: JSON.stringify(compact({
        repository_path: target.repositoryPath,
        project_id: target.projectId,
        embedding,
      })),
    }),
  activeIndexJob: () => request<IndexJob | null>("/projects/index-jobs/active"),
  indexJob: (jobId: string) => request<IndexJob>(`/projects/index-jobs/${jobId}`),
  files: (projectId: number) => request<SourceFile[]>(`/projects/${projectId}/files`),
  symbols: (projectId: number) => request<SymbolItem[]>(`/projects/${projectId}/symbols`),
  source: (projectId: number, fileId: number) =>
    request<SourceContent>(`/projects/${projectId}/files/${fileId}/content`),
  search: (
    projectId: number,
    query: string,
    method: RetrievalMethod,
    limit: number,
    embedding: EmbeddingOverride | undefined,
  ) =>
    request<SearchResponse>(`/projects/${projectId}/search`, {
      method: "POST",
      body: JSON.stringify(compact({ query, method, limit, embedding })),
    }),
  ask: (
    projectId: number,
    question: string,
    method: RetrievalMethod,
    embedding: EmbeddingOverride | undefined,
    llm: ProviderOverride | undefined,
    maxTokens?: number,
  ) =>
    request<AskResponse>(`/projects/${projectId}/ask`, {
      method: "POST",
      body: JSON.stringify(compact({ question, method, max_tokens: maxTokens, embedding, llm })),
    }),
  documentation: (
    projectId: number,
    identifier: string | number,
    language: "en" | "fa",
    llm: ProviderOverride | undefined,
  ) =>
    request<DocumentationResponse>(`/projects/${projectId}/documentation`, {
      method: "POST",
      body: JSON.stringify(compact({ identifier, language, max_tokens: 2400, llm })),
    }),
  evaluation: () => request<EvaluationResponse>("/evaluation/summary"),
  performance: () => request<EvaluationResponse>("/evaluation/performance"),
};
