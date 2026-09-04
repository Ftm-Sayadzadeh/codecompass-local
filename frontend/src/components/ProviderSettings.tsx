import { Eye, EyeOff, KeyRound, Settings2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { EmbeddingState, ProviderState } from "../api/types";

interface Props {
  open: boolean;
  embedding: EmbeddingState;
  llm: ProviderState;
  onEmbeddingChange: (value: EmbeddingState) => void;
  onLlmChange: (value: ProviderState) => void;
  onResetEmbedding: () => void;
  onResetLlm: () => void;
  onClose: () => void;
}

function ProviderFields<T extends ProviderState>({
  id,
  title,
  value,
  onChange,
  onReset,
  dimensions,
}: {
  id: string;
  title: string;
  value: T;
  onChange: (value: T) => void;
  onReset: () => void;
  dimensions?: boolean;
}) {
  const [showKey, setShowKey] = useState(false);
  const set = (patch: Partial<T>) => onChange({ ...value, ...patch });
  return (
    <section className="provider-section" aria-labelledby={`${id}-title`}>
      <div className="section-heading">
        <div>
          <span className="eyebrow">{id === "embedding" ? "Index and retrieval" : "Answer and documentation"}</span>
          <h3 id={`${id}-title`}>{title}</h3>
        </div>
        <Settings2 size={17} aria-hidden="true" />
      </div>

      <label className="check-row">
        <input
          type="checkbox"
          checked={value.useBackendDefault}
          onChange={(event) => set({ useBackendDefault: event.target.checked } as Partial<T>)}
        />
        Use backend defaults
      </label>

      <fieldset disabled={value.useBackendDefault} className="provider-fields">
        <label>
          Provider
          <select value={value.provider} onChange={(event) => set({ provider: event.target.value } as Partial<T>)}>
            <option value="ollama">Ollama</option>
            <option value="openai_compatible">OpenAI-compatible</option>
          </select>
        </label>
        <label>
          Base URL
          <input
            value={value.baseUrl}
            onChange={(event) => set({ baseUrl: event.target.value } as Partial<T>)}
            placeholder={value.provider === "ollama" ? "http://127.0.0.1:11434" : "https://provider.example/v1"}
            spellCheck={false}
          />
        </label>
        <label>
          Model
          <input
            value={value.model}
            onChange={(event) => set({ model: event.target.value } as Partial<T>)}
            placeholder="Custom model name"
            spellCheck={false}
          />
        </label>
        {value.provider === "openai_compatible" ? (
          <label>
            API key
            <div className="secret-input">
              <KeyRound size={15} aria-hidden="true" />
              <input
                type={showKey ? "text" : "password"}
                value={value.apiKey}
                onChange={(event) => set({ apiKey: event.target.value } as Partial<T>)}
                autoComplete="off"
                spellCheck={false}
              />
              <button type="button" className="icon-button" onClick={() => setShowKey((current) => !current)} aria-label={showKey ? "Hide API key" : "Show API key"} title={showKey ? "Hide API key" : "Show API key"}>
                {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {value.apiKey ? <button type="button" className="forget-key" onClick={() => set({ apiKey: "" } as Partial<T>)}>Clear key</button> : null}
          </label>
        ) : null}
        <details>
          <summary>Advanced</summary>
          <label>
            Timeout seconds
            <input type="number" min="1" max="600" value={value.timeoutSeconds} onChange={(event) => set({ timeoutSeconds: event.target.value } as Partial<T>)} placeholder="Backend default" />
          </label>
          {dimensions ? (
            <label>
              Embedding dimensions
              <input type="number" min="1" value={(value as unknown as EmbeddingState).dimensions} onChange={(event) => set({ dimensions: event.target.value } as unknown as Partial<T>)} placeholder="Backend default" />
            </label>
          ) : null}
        </details>
      </fieldset>
      <button className="reset-provider" type="button" onClick={onReset}>Reset to backend defaults</button>
    </section>
  );
}

export function ProviderSettings(props: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!props.open || !dialog.current) return;
    if (typeof dialog.current.showModal === "function") dialog.current.showModal();
    else dialog.current.setAttribute("open", "");
  }, [props.open]);
  if (!props.open) return null;
  return (
    <dialog
      className="settings-dialog"
      ref={dialog}
      aria-labelledby="provider-settings-title"
      onCancel={(event) => { event.preventDefault(); props.onClose(); }}
      onClick={(event) => { if (event.target === event.currentTarget) props.onClose(); }}
    >
      <header>
        <div className="settings-title">
          <Settings2 size={20} aria-hidden="true" />
          <div><span className="eyebrow">Runtime configuration</span><h2 id="provider-settings-title">Provider settings</h2></div>
        </div>
        <button className="icon-button" type="button" onClick={props.onClose} aria-label="Close provider settings" title="Close">
          <X size={19} />
        </button>
      </header>
      <div className="settings-grid">
        <ProviderFields id="embedding" title="Embedding provider" value={props.embedding} onChange={props.onEmbeddingChange} onReset={props.onResetEmbedding} dimensions />
        <ProviderFields id="llm" title="LLM provider" value={props.llm} onChange={props.onLlmChange} onReset={props.onResetLlm} />
      </div>
      <footer>
        <p className="privacy-note"><KeyRound size={15} /> Non-sensitive settings persist in this browser. API keys stay in memory and are forgotten on refresh.</p>
        <button className="primary-button" type="button" onClick={props.onClose}>Done</button>
      </footer>
    </dialog>
  );
}
