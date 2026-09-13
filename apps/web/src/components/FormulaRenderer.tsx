import React, { useMemo } from "react";
import katex from "katex";
import { formatChemicalFormula } from "../utils/formulaUtils";

interface FormulaRendererProps {
  text: string;
  inline?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Converts chemical notation and unicode into clean LaTeX that KaTeX renders beautifully.
 * e.g. "FeO(s) + 2HCl(dil) → FeCl₂(aq) + H₂O(l)"
 */
function formatReactionCondition(raw: string): string {
  let c = raw.trim();
  // 400°C - 700°C or 50°C -> 400^\circ\text{C} - 700^\circ\text{C}
  c = c.replace(/(\d+)\s*°\s*([CFcf])/g, "$1^\\circ\\text{$2}");
  c = c.replace(/°/g, "^\\circ");
  // Wrap Arabic words in \text{...}
  c = c.replace(/([\u0600-\u06FF]+)/g, (m) => `\\text{${m}}`);
  // Format chemical formulas in condition e.g. H2SO4 -> \text{H}_2\text{SO}_4
  c = c.replace(/\b([A-Z][a-z]?)(\d+)/g, "$1_{$2}");
  return c;
}

function chemicalToLatex(chem: string): string {
  let expr = chem.trim();

  // If already wrapped in LaTeX delimiters, strip them
  if (expr.startsWith("$$") && expr.endsWith("$$")) expr = expr.slice(2, -2).trim();
  if (expr.startsWith("$") && expr.endsWith("$")) expr = expr.slice(1, -1).trim();
  if (expr.startsWith("\\[") && expr.endsWith("\\]")) expr = expr.slice(2, -2).trim();
  if (expr.startsWith("\\(") && expr.endsWith("\\)")) expr = expr.slice(2, -2).trim();

  // 1. Protect existing \xrightarrow[below]{above} or \xrightarrow{above}
  const protectedArrows: string[] = [];
  expr = expr.replace(/\\xrightarrow(?:\[([^\]]*)\])?\{([^}]*)\}/g, (_match, below, above) => {
    const cleanAbove = (above || "").replace(/\\quad/g, " ").trim();
    const cleanBelow = (below || "").replace(/\\quad/g, " ").trim();
    if (!cleanAbove && !cleanBelow) return "\\rightarrow ";
    const idx = protectedArrows.length;
    const formattedAbove = formatReactionCondition(cleanAbove);
    const formattedBelow = cleanBelow ? formatReactionCondition(cleanBelow) : "";
    const restored = formattedBelow
      ? `\\xrightarrow[${formattedBelow}]{${formattedAbove}}`
      : `\\xrightarrow{${formattedAbove}}`;
    protectedArrows.push(restored);
    return `__PROTECTED_ARROW_${idx}__`;
  });

  // 2. Convert unicode / text condition arrows:
  // e.g. ⎯⎯(400°C - 700°C)→ or —(400°C - 700°C) → or -(400°C - 700°C)->
  expr = expr.replace(/(?:⎯+|—+|-+)\s*\(([^)]+)\)\s*(?:→|->)/g, (_, cond) => {
    return ` \\xrightarrow{${formatReactionCondition(cond)}} `;
  });

  // e.g. → (condition) or -> (condition)
  expr = expr.replace(/(?:→|->)\s*\(([^)]+)\)/g, (_, cond) => {
    return ` \\xrightarrow{${formatReactionCondition(cond)}} `;
  });

  // e.g. (condition) ⎯→ or (condition) ->
  expr = expr.replace(/\(([^)]+)\)\s*(?:⎯+|—+|-+)*(?:→|->)/g, (_, cond) => {
    if (/^(?:s|aq|l|g|dil|conc)$/i.test(cond.trim())) return `(${cond}) \\rightarrow `;
    return ` \\xrightarrow{${formatReactionCondition(cond)}} `;
  });

  // 3. Convert remaining plain arrows
  expr = expr.replace(/\\xrightarrow\s*\{\s*(?:\\quad\s*)*\}/g, "\\rightarrow ");
  expr = expr.replace(/⎯+|—+|-->|->|→/g, "\\rightarrow ");
  expr = expr.replace(/⇌|<=>|<==>/g, "\\rightleftharpoons ");

  // 4. Restore protected arrows
  expr = expr.replace(/__PROTECTED_ARROW_(\d+)__/g, (_, i) => protectedArrows[parseInt(i, 10)]);

  // 5. Convert Unicode subscripts to LaTeX subscripts: ₂ -> _2
  expr = expr.replace(/[₀₁₂₃₄₅₆₇₈₉]/g, (ch) => {
    const map: Record<string, string> = {
      "₀": "_0", "₁": "_1", "₂": "_2", "₃": "_3", "₄": "_4",
      "₅": "_5", "₆": "_6", "₇": "_7", "₈": "_8", "₉": "_9",
    };
    return map[ch] || ch;
  });

  // 6. Convert Unicode superscripts & charges to LaTeX superscripts: ²⁺ -> ^{2+}
  expr = expr.replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+/g, (match) => {
    const map: Record<string, string> = {
      "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
      "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
      "⁺": "+", "⁻": "-",
    };
    const translated = match.split("").map((c) => map[c] || c).join("");
    return `^{${translated}}`;
  });

  // 7. Convert plain digits after element symbols or closing parentheses to subscripts: Fe2 -> Fe_2, (NO2)3 -> (NO_2)_3
  expr = expr.replace(/([A-Z][a-z]?|\))(\d+)(?![_^{0-9])/g, "$1_{$2}");

  // 8. Convert states: (s), (aq), (l), (g), (dil), (conc)
  expr = expr.replace(/_?\((\s*s|aq|l|g|dil|conc\s*)\)/gi, "\\text{($1)}");

  return expr;
}

function renderKatexHtml(latex: string, displayMode: boolean): string {
  try {
    let clean = latex.trim();
    // Normalize \xrightarrow with empty/quad spaces
    clean = clean.replace(/\\xrightarrow\s*\{\s*(?:\\quad\s*)*\}/g, "\\rightarrow ");

    return katex.renderToString(clean, {
      displayMode,
      throwOnError: false,
      output: "html",
    });
  } catch {
    // If KaTeX rendering fails, return clean text without $ or $$ delimiters
    return latex.replace(/[$]/g, "").replace(/\\/g, "");
  }
}

interface InlineToken {
  type: "text" | "bold" | "inline-math" | "code";
  content: string;
  bold?: boolean;
}

/**
 * Parses inline string into text, bold, and math tokens.
 * Handles **$formula$**, $formula$, **bold**, etc. cleanly without stray asterisks or dollar signs.
 */
function parseInline(text: string): InlineToken[] {
  if (!text) return [];

  // Match:
  // 1. Bold math: **$...$** or **\(...\)**
  // 2. Inline math: $...$ or \(...\)
  // 3. Bold text: **...**
  // 4. Inline code: `...`
  const tokenRegex = /(\*\*\$(?:\\\$|[^$\n])+\$\*\*|\*\*\\\([\s\S]*?\\\)\*\*|\$(?:\\\$|[^$\n])+\$|\\\([\s\S]*?\\\)|(?<!\*)\*\*(?!\*)(.+?)(?<!\*)\*\*(?!\*)|`([^`]+)`)/g;

  const tokens: InlineToken[] = [];
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = tokenRegex.exec(text)) !== null) {
    if (m.index > last) {
      tokens.push({ type: "text", content: text.slice(last, m.index) });
    }

    const matched = m[0];
    if (matched.startsWith("**$") && matched.endsWith("$**")) {
      const inner = matched.slice(3, -3).trim();
      tokens.push({ type: "inline-math", content: inner, bold: true });
    } else if (matched.startsWith("**\\(") && matched.endsWith("\\)**")) {
      const inner = matched.slice(4, -4).trim();
      tokens.push({ type: "inline-math", content: inner, bold: true });
    } else if (matched.startsWith("$") && matched.endsWith("$")) {
      const inner = matched.slice(1, -1).trim();
      tokens.push({ type: "inline-math", content: inner });
    } else if (matched.startsWith("\\(") && matched.endsWith("\\)")) {
      const inner = matched.slice(2, -2).trim();
      tokens.push({ type: "inline-math", content: inner });
    } else if (matched.startsWith("**") && matched.endsWith("**")) {
      const inner = matched.slice(2, -2);
      tokens.push({ type: "bold", content: inner });
    } else if (matched.startsWith("`") && matched.endsWith("`")) {
      const inner = matched.slice(1, -1);
      if (inner.includes("→") || inner.includes("⇌") || /[₀₁₂₃₄₅₆₇₈₉]/.test(inner)) {
        tokens.push({ type: "inline-math", content: inner });
      } else {
        tokens.push({ type: "code", content: inner });
      }
    }

    last = m.index + matched.length;
  }

  if (last < text.length) {
    tokens.push({ type: "text", content: text.slice(last) });
  }

  return tokens;
}

interface BlockItem {
  type: "heading" | "divider" | "list-item" | "block-math" | "chemical-reaction" | "paragraph";
  level?: number;
  prefix?: string;
  content: string;
}

/**
 * Splits text into markdown blocks and mathematical equations.
 */
function parseBlocks(rawText: string): BlockItem[] {
  if (!rawText) return [];

  const blocks: BlockItem[] = [];

  // 1. Separate out any standalone block math: $$...$$ or \[...\]
  const blockMathRegex = /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\])/g;
  let lastIdx = 0;
  let m: RegExpExecArray | null;

  while ((m = blockMathRegex.exec(rawText)) !== null) {
    if (m.index > lastIdx) {
      const textPart = rawText.slice(lastIdx, m.index);
      addTextBlocks(textPart, blocks);
    }

    const rawMatch = m[0];
    const inner = rawMatch.startsWith("$$") ? rawMatch.slice(2, -2).trim() : rawMatch.slice(2, -2).trim();
    blocks.push({
      type: "block-math",
      content: inner,
    });

    lastIdx = m.index + rawMatch.length;
  }

  if (lastIdx < rawText.length) {
    const textPart = rawText.slice(lastIdx);
    addTextBlocks(textPart, blocks);
  }

  return blocks;
}

function addTextBlocks(textChunk: string, blocks: BlockItem[]) {
  const lines = textChunk.split("\n");

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) return;

    // Check for divider
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ type: "divider", content: "" });
      return;
    }

    // Check for markdown headers: #, ##, ###, ####
    const headerMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headerMatch) {
      blocks.push({
        type: "heading",
        level: headerMatch[1].length,
        content: headerMatch[2],
      });
      return;
    }

    // Check for standalone chemical reactions: e.g. FeO(s) + 2HCl(dil) → FeCl2(aq) + H2O(l)
    const isReaction = (
      (trimmed.includes("→") || trimmed.includes("⇌") || trimmed.includes("->")) &&
      /[A-Z][a-z]?/.test(trimmed) &&
      !/[أ-ي]/.test(trimmed)
    );

    if (isReaction) {
      blocks.push({
        type: "chemical-reaction",
        content: formatChemicalFormula(trimmed),
      });
      return;
    }

    // Check for bullet list item: * or -
    const bulletMatch = trimmed.match(/^[* -]\s+(.+)$/);
    if (bulletMatch) {
      blocks.push({
        type: "list-item",
        prefix: "•",
        content: bulletMatch[1],
      });
      return;
    }

    // Check for numbered list item: 1. or 1)
    const numMatch = trimmed.match(/^(\d+[.)])\s+(.+)$/);
    if (numMatch) {
      blocks.push({
        type: "list-item",
        prefix: numMatch[1],
        content: numMatch[2],
      });
      return;
    }

    // Standard paragraph
    blocks.push({
      type: "paragraph",
      content: trimmed,
    });
  });
}

export const FormulaRenderer: React.FC<FormulaRendererProps> = ({
  text,
  inline = false,
  className = "",
  style = {},
}) => {
  const blocks = useMemo(() => parseBlocks(text || ""), [text]);

  const renderInlineTokens = (content: string) => {
    const tokens = parseInline(content);
    return tokens.map((tok, idx) => {
      if (tok.type === "inline-math") {
        const isChem = /_\{?\(([a-zA-Z]+)\)\}?|\\rightarrow|[A-Z][a-z]?_\d|[₀₁₂₃₄₅₆₇₈₉]/.test(tok.content);
        const latex = isChem ? chemicalToLatex(tok.content) : tok.content;
        const html = renderKatexHtml(latex, false);

        return (
          <span
            key={idx}
            dir="ltr"
            className="formula-inline-math"
            style={{
              display: "inline-block",
              margin: "0 3px",
              verticalAlign: "middle",
              fontWeight: tok.bold ? 800 : "inherit",
            }}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        );
      }

      if (tok.type === "bold") {
        return (
          <strong key={idx} style={{ color: "var(--text-main, inherit)" }}>
            {renderInlineTokens(tok.content)}
          </strong>
        );
      }

      if (tok.type === "code") {
        return (
          <code
            key={idx}
            style={{
              background: "rgba(0,0,0,0.06)",
              padding: "2px 6px",
              borderRadius: "4px",
              fontSize: "12px",
              fontFamily: "monospace",
            }}
          >
            {tok.content}
          </code>
        );
      }

      return <span key={idx}>{tok.content}</span>;
    });
  };

  if (inline) {
    return (
      <span className={`formula-inline-wrapper ${className}`} style={{ ...style }}>
        {renderInlineTokens(text)}
      </span>
    );
  }

  return (
    <div
      className={`formula-rendered-container ${className}`}
      style={{
        lineHeight: "1.75",
        wordBreak: "break-word",
        color: "var(--text-main, inherit)",
        ...style,
      }}
    >
      {blocks.map((block, idx) => {
        if (block.type === "divider") {
          return (
            <hr
              key={idx}
              style={{
                border: "none",
                borderTop: "1px solid var(--border-color, #e2e8f0)",
                margin: "12px 0",
                opacity: 0.7,
              }}
            />
          );
        }

        if (block.type === "heading") {
          const fontSize = block.level === 1 ? "18px" : block.level === 2 ? "16px" : "15px";
          return (
            <div
              key={idx}
              style={{
                fontSize,
                fontWeight: 800,
                color: "var(--text-main, inherit)",
                margin: "12px 0 6px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              {renderInlineTokens(block.content)}
            </div>
          );
        }

        if (block.type === "block-math") {
          const latex = chemicalToLatex(block.content);
          const html = renderKatexHtml(latex, true);
          return (
            <div
              key={idx}
              dir="ltr"
              className="formula-block-math"
              style={{
                margin: "10px 0",
                padding: "10px 16px",
                background: "#ffffff",
                color: "#0f172a",
                borderRadius: "10px",
                border: "1px solid var(--border-color, #e2e8f0)",
                overflowX: "auto",
                textAlign: "center",
                boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
              }}
              dangerouslySetInnerHTML={{ __html: html }}
            />
          );
        }

        if (block.type === "chemical-reaction") {
          const latex = chemicalToLatex(block.content);
          const html = renderKatexHtml(latex, true);
          return (
            <div
              key={idx}
              dir="ltr"
              className="formula-chemical-reaction-block"
              style={{
                margin: "10px 0",
                padding: "10px 16px",
                background: "#ffffff",
                color: "#0f172a",
                borderRadius: "10px",
                border: "1.5px solid var(--border-accent, #cbd5e1)",
                overflowX: "auto",
                textAlign: "center",
                fontWeight: 600,
                boxShadow: "0 1px 4px rgba(0,0,0,0.03)",
              }}
              dangerouslySetInnerHTML={{ __html: html }}
            />
          );
        }

        if (block.type === "list-item") {
          return (
            <div
              key={idx}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "8px",
                margin: "4px 0",
                paddingInlineStart: "8px",
              }}
            >
              <span style={{ fontWeight: 800, color: "var(--primary-color, #059669)", flexShrink: 0 }}>
                {block.prefix}
              </span>
              <div style={{ flex: 1 }}>{renderInlineTokens(block.content)}</div>
            </div>
          );
        }

        // Standard paragraph
        return (
          <div key={idx} style={{ margin: "6px 0" }}>
            {renderInlineTokens(block.content)}
          </div>
        );
      })}
    </div>
  );
};
