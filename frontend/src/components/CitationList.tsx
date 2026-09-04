import { ExternalLink, Link2 } from "lucide-react";

export interface NavigationCitation {
  fileId: number;
  chunkId: string;
  qualifiedName: string | null;
  relativePath: string;
  startLine: number;
  endLine: number;
}

export function CitationList({ citations, onOpen }: { citations: NavigationCitation[]; onOpen: (citation: NavigationCitation) => void }) {
  if (!citations.length) return null;
  return (
    <section className="citations" aria-labelledby="citations-title">
      <h3 id="citations-title"><Link2 size={16} /> Sources</h3>
      <div className="citation-list">
        {citations.map((citation, index) => (
          <div className={`citation-row${index === 0 ? " primary" : ""}`} key={`${citation.chunkId}-${index}`}>
            <span className="rank">{index + 1}</span>
            <span className="citation-symbol">{citation.qualifiedName ?? "Source"}</span>
            <span className="citation-path" title={citation.relativePath}>{citation.relativePath}</span>
            <span className="line-badge">L{citation.startLine}–{citation.endLine}</span>
            <button className="text-button" type="button" onClick={() => onOpen(citation)}>
              Open code <ExternalLink size={14} />
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
