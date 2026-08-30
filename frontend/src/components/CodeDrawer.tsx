import Editor, { type OnMount } from "@monaco-editor/react";
import { Braces, X } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import type { editor } from "monaco-editor";

import type { SourceContent } from "../api/types";
import { ErrorMessage } from "./ErrorMessage";

export interface SourceSelection {
  content: SourceContent;
  startLine?: number;
  endLine?: number;
}

export function CodeDrawer({ selection, loading, error, onClose, onReindex }: {
  selection: SourceSelection | null;
  loading: boolean;
  error: unknown;
  onClose: () => void;
  onReindex: () => void;
}) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const decorationRef = useRef<editor.IEditorDecorationsCollection | null>(null);

  const reveal = useCallback(() => {
    const instance = editorRef.current;
    if (!instance || !selection) return;
    const start = selection.startLine ?? 1;
    const end = selection.endLine ?? start;
    decorationRef.current?.clear();
    decorationRef.current = instance.createDecorationsCollection(selection.startLine ? [{
      range: { startLineNumber: start, startColumn: 1, endLineNumber: end, endColumn: 1 },
      options: { isWholeLine: true, className: "citation-highlight", linesDecorationsClassName: "citation-gutter" },
    }] : []);
    instance.revealLineInCenter(start);
  }, [selection]);

  useEffect(reveal, [reveal]);
  const onMount: OnMount = (instance) => {
    editorRef.current = instance;
    reveal();
  };

  if (!selection && !loading && !error) return null;
  return (
    <aside className="code-drawer" aria-label="Source code viewer">
      <header>
        <div>
          <span className="eyebrow">Trusted indexed source</span>
          <h2><Braces size={18} /> {selection?.content.relative_path ?? "Source"}</h2>
        </div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="Close code viewer" title="Close code viewer"><X size={19} /></button>
      </header>
      {selection?.startLine ? <div className="code-location">Lines {selection.startLine}–{selection.endLine}</div> : null}
      {loading ? <div className="drawer-state">Loading source...</div> : null}
      {error ? <ErrorMessage error={error} onReindex={onReindex} /> : null}
      {selection ? (
        <Editor
          height="100%"
          language="python"
          path={selection.content.relative_path}
          value={selection.content.content}
          onMount={onMount}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 13,
            lineHeight: 21,
            padding: { top: 14, bottom: 14 },
            renderLineHighlight: "none",
            scrollBeyondLastLine: false,
            wordWrap: "off",
            automaticLayout: true,
            folding: true,
            glyphMargin: false,
            overviewRulerLanes: 0,
          }}
        />
      ) : null}
    </aside>
  );
}
