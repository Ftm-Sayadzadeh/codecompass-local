import type { EmbeddingState, ProviderName, ProviderState } from "./api/types";

const STORAGE_KEY = "codecompass.preferences.v1";

export const defaultEmbedding: EmbeddingState = {
  useBackendDefault: true,
  provider: "ollama",
  baseUrl: "",
  model: "",
  apiKey: "",
  timeoutSeconds: "",
  dimensions: "",
};

export const defaultLlm: ProviderState = {
  useBackendDefault: true,
  provider: "ollama",
  baseUrl: "",
  model: "",
  apiKey: "",
  timeoutSeconds: "",
};

export interface Preferences {
  embedding: EmbeddingState;
  llm: ProviderState;
  answerTokenBudget: string;
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function provider(value: unknown, fallback: ProviderName): ProviderName {
  return value === "ollama" || value === "openai_compatible" ? value : fallback;
}

function text(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

function numberText(value: unknown, fallback: string, min: number, max?: number, integer = false): string {
  if (value === "") return "";
  if (typeof value !== "string") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && (max === undefined || parsed <= max) && (!integer || Number.isInteger(parsed))
    ? value
    : fallback;
}

function providerState(value: unknown, fallback: ProviderState): ProviderState {
  const saved = record(value);
  return {
    useBackendDefault: typeof saved.useBackendDefault === "boolean" ? saved.useBackendDefault : fallback.useBackendDefault,
    provider: provider(saved.provider, fallback.provider),
    baseUrl: text(saved.baseUrl, fallback.baseUrl),
    model: text(saved.model, fallback.model),
    apiKey: "",
    timeoutSeconds: numberText(saved.timeoutSeconds, fallback.timeoutSeconds, 1, 600),
  };
}

export function loadPreferences(): Preferences {
  try {
    const saved = record(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}"));
    const embedding = providerState(saved.embedding, defaultEmbedding);
    const embeddingSaved = record(saved.embedding);
    return {
      embedding: { ...embedding, dimensions: numberText(embeddingSaved.dimensions, defaultEmbedding.dimensions, 1, undefined, true) },
      llm: providerState(saved.llm, defaultLlm),
      answerTokenBudget: numberText(saved.answerTokenBudget, "", 1, 8000, true),
    };
  } catch {
    return { embedding: defaultEmbedding, llm: defaultLlm, answerTokenBudget: "" };
  }
}

export function savePreferences(value: Preferences): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      embedding: {
        useBackendDefault: value.embedding.useBackendDefault,
        provider: value.embedding.provider,
        baseUrl: value.embedding.baseUrl,
        model: value.embedding.model,
        timeoutSeconds: value.embedding.timeoutSeconds,
        dimensions: value.embedding.dimensions,
      },
      llm: {
        useBackendDefault: value.llm.useBackendDefault,
        provider: value.llm.provider,
        baseUrl: value.llm.baseUrl,
        model: value.llm.model,
        timeoutSeconds: value.llm.timeoutSeconds,
      },
      answerTokenBudget: value.answerTokenBudget,
    }));
  } catch {
    // Storage can be unavailable; runtime settings still work in memory.
  }
}
