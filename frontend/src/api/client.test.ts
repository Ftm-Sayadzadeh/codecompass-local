import { describe, expect, it } from "vitest";

import { embeddingOverride, providerOverride } from "./client";

describe("provider request configuration", () => {
  it("keeps backend defaults empty and embedding/LLM overrides independent", () => {
    expect(providerOverride({
      useBackendDefault: true,
      provider: "ollama",
      baseUrl: "",
      model: "",
      apiKey: "",
      timeoutSeconds: "",
    })).toBeUndefined();

    const embedding = embeddingOverride({
      useBackendDefault: false,
      provider: "ollama",
      baseUrl: "http://embedding.internal",
      model: "embed-model",
      apiKey: "",
      timeoutSeconds: "45",
      dimensions: "768",
    });
    const llm = providerOverride({
      useBackendDefault: false,
      provider: "openai_compatible",
      baseUrl: "https://llm.example/v1",
      model: "chat-model",
      apiKey: "DUMMY_FRONTEND_TEST_KEY",
      timeoutSeconds: "90",
    });

    expect(embedding).toEqual({
      provider: "ollama",
      base_url: "http://embedding.internal",
      model: "embed-model",
      timeout_seconds: 45,
      dimensions: 768,
    });
    expect(llm).toEqual({
      provider: "openai_compatible",
      base_url: "https://llm.example/v1",
      model: "chat-model",
      api_key: "DUMMY_FRONTEND_TEST_KEY",
      timeout_seconds: 90,
    });
  });
});
