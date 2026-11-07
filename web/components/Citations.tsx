import type { Citation } from "@/lib/api";

export function Citations({ citations }: { citations: Citation[] }) {
  return (
    <div className="citations">
      {citations.map((c) => (
        <div className="citation" key={c.n}>
          <strong>[{c.n}]</strong>
          {c.label}
          {c.heading ? ` · ${c.heading}` : ""}
          <span className="snippet">{c.snippet}</span>
        </div>
      ))}
    </div>
  );
}
