import { BookOpen, Braces, FileCode2, Files, Folder, Search } from "lucide-react";
import { useMemo, useState } from "react";

import type { SourceFile, SymbolItem } from "../api/types";

interface FileTreeNode {
  name: string;
  path: string;
  folders: Map<string, FileTreeNode>;
  files: SourceFile[];
}

function fileTree(files: SourceFile[]): FileTreeNode {
  const root: FileTreeNode = { name: "", path: "", folders: new Map(), files: [] };
  for (const file of files) {
    const parts = file.relative_path.replaceAll("\\", "/").split("/");
    let node = root;
    for (const name of parts.slice(0, -1)) {
      const path = node.path ? `${node.path}/${name}` : name;
      if (!node.folders.has(name)) node.folders.set(name, { name, path, folders: new Map(), files: [] });
      node = node.folders.get(name)!;
    }
    node.files.push(file);
  }
  return root;
}

function FileTree({ node, selectedFileId, onOpenFile, expanded }: {
  node: FileTreeNode;
  selectedFileId: number | null;
  onOpenFile: (file: SourceFile) => void;
  expanded: boolean;
}) {
  return <>
    {[...node.folders.values()].sort((a, b) => a.name.localeCompare(b.name)).map((folder) => (
      <details className="folder-node" key={`${folder.path}:${expanded}`} open={expanded || undefined}>
        <summary><Folder size={16} aria-hidden="true" /><span>{folder.name}</span></summary>
        <div className="folder-children">
          <FileTree node={folder} selectedFileId={selectedFileId} onOpenFile={onOpenFile} expanded={expanded} />
        </div>
      </details>
    ))}
    {[...node.files].sort((a, b) => a.relative_path.localeCompare(b.relative_path)).map((file) => (
      <button
        className={`explorer-row file-row${selectedFileId === file.id ? " selected" : ""}`}
        type="button"
        key={file.id}
        onClick={() => onOpenFile(file)}
        aria-current={selectedFileId === file.id ? "true" : undefined}
        aria-label={file.relative_path}
        title={file.relative_path}
      >
        <FileCode2 size={16} aria-hidden="true" />
        <span>{file.relative_path.replaceAll("\\", "/").split("/").at(-1)}</span>
      </button>
    ))}
  </>;
}

export function ProjectExplorer({
  files,
  symbols,
  selectedFileId,
  onOpenFile,
  onOpenSymbol,
  onDocumentSymbol,
}: {
  files: SourceFile[];
  symbols: SymbolItem[];
  selectedFileId: number | null;
  onOpenFile: (file: SourceFile) => void;
  onOpenSymbol: (symbol: SymbolItem) => void;
  onDocumentSymbol: (symbol: SymbolItem) => void;
}) {
  const [tab, setTab] = useState<"files" | "symbols">("files");
  const [filter, setFilter] = useState("");
  const query = filter.trim().toLowerCase();
  const shownFiles = useMemo(
    () => files.filter((file) => !query || file.relative_path.toLowerCase().includes(query)),
    [files, query],
  );
  const shownSymbols = useMemo(
    () => symbols.filter((symbol) => !query || symbol.qualified_name.toLowerCase().includes(query)),
    [symbols, query],
  );
  const shownFileTree = useMemo(() => fileTree(shownFiles), [shownFiles]);

  return (
    <aside className="explorer" aria-label="Project explorer">
      <div className="tab-list compact-tabs" role="tablist" aria-label="Explorer view">
        <button type="button" role="tab" aria-selected={tab === "files"} className={tab === "files" ? "active" : ""} onClick={() => { setTab("files"); setFilter(""); }}>
          <Files size={17} /> Files
        </button>
        <button type="button" role="tab" aria-selected={tab === "symbols"} className={tab === "symbols" ? "active" : ""} onClick={() => { setTab("symbols"); setFilter(""); }}>
          <Braces size={17} /> Symbols
        </button>
      </div>
      <label className="explorer-search">
        <span className="sr-only">Search {tab}</span>
        <Search size={16} aria-hidden="true" />
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder={`Search ${tab}...`} />
      </label>
      <div className="explorer-list">
        {tab === "files" ? <FileTree node={shownFileTree} selectedFileId={selectedFileId} onOpenFile={onOpenFile} expanded={Boolean(query)} /> : shownSymbols.map((symbol) => (
          <div className="symbol-row" key={symbol.id}>
            <button type="button" onClick={() => onOpenSymbol(symbol)} title={`Open ${symbol.qualified_name}`}>
              <Braces size={15} aria-hidden="true" />
              <span><strong>{symbol.name}</strong><small>{symbol.qualified_name}</small></span>
            </button>
            <button className="icon-button" type="button" onClick={() => onDocumentSymbol(symbol)} aria-label={`Document ${symbol.qualified_name}`} title="Generate documentation">
              <BookOpen size={15} />
            </button>
          </div>
        ))}
        {((tab === "files" && !shownFiles.length) || (tab === "symbols" && !shownSymbols.length)) ? (
          <p className="empty-compact">No matching {tab}.</p>
        ) : null}
      </div>
    </aside>
  );
}
