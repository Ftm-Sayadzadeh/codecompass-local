export type ProviderName = "ollama" | "openai_compatible";
export type RetrievalMethod = "lexical" | "semantic" | "hybrid";

export interface ProviderState {
  useBackendDefault: boolean;
  provider: ProviderName;
  baseUrl: string;
  model: string;
  apiKey: string;
  timeoutSeconds: string;
}

export interface EmbeddingState extends ProviderState {
  dimensions: string;
}

export interface ProviderOverride {
  provider?: ProviderName;
  base_url?: string;
  model?: string;
  api_key?: string;
  timeout_seconds?: number;
}

export interface EmbeddingOverride extends ProviderOverride {
  dimensions?: number;
}

export interface Project {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
  files: number | null;
  symbols: number | null;
  chunks: number | null;
  vector_complete: boolean | null;
}

export interface SourceFile {
  id: number;
  relative_path: string;
  size_bytes: number;
  sha256: string;
  status: string;
}

export interface SourceContent {
  id: number;
  relative_path: string;
  sha256: string;
  content: string;
}

export interface SymbolItem {
  id: number;
  file_id: number;
  kind: string;
  name: string;
  qualified_name: string;
  is_async: boolean;
  start_line: number;
  end_line: number;
  parameters: string[];
  returns: string | null;
}

export interface Citation {
  file_id: number;
  symbol_id: number | null;
  chunk_id: string;
  source_file: string;
  symbol_name: string | null;
  qualified_name: string | null;
  start_line: number;
  end_line: number;
}

export interface SearchResult extends Citation {
  score: number;
  code: string;
  retrieval_method: string;
}

export interface SearchResponse {
  query: string;
  method: string;
  results: SearchResult[];
}

export interface AskResponse {
  question: string;
  answer: string;
  method: string;
  citations: Citation[];
  omitted_context_count: number;
  llm_model: string | null;
  llm_provider: string | null;
  finish_reason?: string | null;
}

export interface DocumentationCitation {
  project_id: number;
  project_name: string;
  file_id: number;
  symbol_id: number;
  chunk_id: string;
  qualified_name: string;
  relative_source_path: string;
  start_line: number;
  end_line: number;
  content_hash: string;
}

export interface DocumentationResponse {
  extracted: {
    citation: DocumentationCitation;
    symbol_type: string;
    signature: string;
    parameters: string[];
    return_annotation: string | null;
    is_async: boolean;
    source_file_hash: string;
  };
  generated: {
    summary: string;
    detailed_description: string;
    parameters: Array<{ name: string; description: string | null }>;
    return_value: string | null;
    raises: string[];
    side_effects: string[];
    dependencies: string[];
    notes: string[];
  };
  citations: DocumentationCitation[];
  generation: {
    schema_version: string;
    provider: string;
    model: string;
    language: "en" | "fa";
  };
}

export interface ResolutionCandidate {
  symbol_id: number;
  chunk_id: string;
  symbol_type: string;
  qualified_name: string;
  relative_source_path: string;
  start_line: number;
  end_line: number;
}

export interface IndexResponse {
  project_id: number;
  operation: "indexed" | "reindexed";
  strategy?: "full" | "incremental" | null;
  no_changes?: boolean | null;
  complete: boolean;
  structural_stats: Record<string, number>;
  vector_stats: Record<string, number | boolean | string[]>;
  embedding: { provider: string; model: string; dimensions: number | null };
}

export type IndexJobState =
  | "preflight"
  | "scanning"
  | "parsing"
  | "chunking"
  | "embedding"
  | "verifying"
  | "activating"
  | "completed"
  | "failed";

export interface IndexJob {
  id: string;
  state: IndexJobState;
  operation: "indexed" | "reindexed";
  project_id: number | null;
  counters: Record<string, number>;
  observed_stages?: Array<Exclude<IndexJobState, "completed" | "failed">>;
  started_at: string;
  updated_at: string;
  completed_at: string | null;
  elapsed_seconds: number;
  previous_index_preserved: boolean | null;
  result: IndexResponse | null;
  error: {
    code: string;
    message: string;
    stage: string;
    error_type?: string | null;
  } | null;
}

export interface MetricAggregate {
  slice: Record<string, string>;
  method?: string;
  questions?: number;
  samples?: number;
  top_1?: number;
  top_3?: number;
  mrr_at_10?: number;
  evidence_recall_at_3?: number;
  evidence_recall_at_10?: number;
  latency_ms?: {
    samples?: number;
    mean?: number;
    p50?: number;
    p95?: number;
    sequential_queries_per_second?: number;
  };
}

export interface EvaluationResponse {
  scope: "benchmark_evaluation";
  not_per_answer_confidence: true;
  artifact_sha256: string;
  data: {
    benchmark?: Record<string, unknown>;
    repositories?: Array<Record<string, unknown>>;
    aggregates?: MetricAggregate[];
    measurement_context?: string;
    ranking_consistency?: Record<string, unknown>;
  };
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}
