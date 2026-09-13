import React, { useState, useRef, useEffect, useCallback } from "react";
import katex from "katex";
import {
  formatChemicalFormula,
} from "../utils/formulaUtils";
import {
  Trash2,
} from "lucide-react";

interface RichFormulaEditorProps {
  value: string;
  onChange: (newValue: string) => void;
  placeholder?: string;
  label?: string;
  minRows?: number;
}

/**
 * Converts a chemical formula/reaction into clean LaTeX for KaTeX rendering.
 */
function toKatexLatex(chem: string): string {
  let expr = chem.trim();
  if (expr.startsWith("$$") && expr.endsWith("$$")) expr = expr.slice(2, -2).trim();
  if (expr.startsWith("$") && expr.endsWith("$")) expr = expr.slice(1, -1).trim();
  if (expr.startsWith("\\[") && expr.endsWith("\\]")) expr = expr.slice(2, -2).trim();
  if (expr.startsWith("\\(") && expr.endsWith("\\)")) expr = expr.slice(2, -2).trim();

  // Convert reaction arrows
  expr = expr.replace(/\\xrightarrow\s*\{\s*\\quad\s*\\quad\s*\}|\\xrightarrow\s*\{[^}]*\}|→|->/g, "\\rightarrow ");
  expr = expr.replace(/⇌|<=>|<==>/g, "\\rightleftharpoons ");

  // Convert Unicode subscripts to LaTeX subscripts
  expr = expr.replace(/[₀₁₂₃₄₅₆₇₈₉]/g, (ch) => {
    const map: Record<string, string> = {
      "₀": "_0", "₁": "_1", "₂": "_2", "₃": "_3", "₄": "_4",
      "₅": "_5", "₆": "_6", "₇": "_7", "₈": "_8", "₉": "_9",
    };
    return map[ch] || ch;
  });

  // Convert Unicode superscripts & charges to LaTeX superscripts
  expr = expr.replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+/g, (match) => {
    const map: Record<string, string> = {
      "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
      "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
      "⁺": "+", "⁻": "-",
    };
    const translated = match.split("").map((c) => map[c] || c).join("");
    return `^{${translated}}`;
  });

  // Convert physical states safely: (s), (aq), (l), (g), (dil), (conc)
  expr = expr.replace(/_?\(\s*(s|aq|l|g|dil|conc)\s*\)/gi, "{\\text{($1)}}");

  return expr;
}

function renderKatexToString(latex: string, displayMode: boolean = false): string {
  try {
    const clean = toKatexLatex(latex);
    return katex.renderToString(clean, {
      displayMode,
      throwOnError: false,
      output: "html",
    });
  } catch {
    return latex;
  }
}

/**
 * Creates an HTML string containing rendered math nodes for a given plain text or formula string.
 */
function textToWysiwygHtml(rawText: string): string {
  if (!rawText) return "";

  // Split by block math $$...$$, inline math $...$, or standalone reaction lines
  const regex = /(\$\$[\s\S]*?\$\$|\$(?:\\\$|[^$\n])+\$)/g;
  let result = "";
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(rawText)) !== null) {
    if (match.index > last) {
      result += escapeAndFormatPlain(rawText.slice(last, match.index));
    }

    const rawMatch = match[0];
    const isBlock = rawMatch.startsWith("$$");
    const inner = isBlock ? rawMatch.slice(2, -2).trim() : rawMatch.slice(1, -1).trim();
    const formatted = formatChemicalFormula(inner);
    const katexHtml = renderKatexToString(formatted, isBlock);

    if (isBlock) {
      result += `<div class="wysiwyg-math-block" contenteditable="false" data-formula="${encodeURIComponent(formatted)}" dir="ltr" style="display:block;margin:8px 0;padding:8px 14px;background:#f8fafc;border:1.5px solid #cbd5e1;border-radius:8px;text-align:center;user-select:all;cursor:pointer;">${katexHtml}</div>`;
    } else {
      result += `<span class="wysiwyg-math-node" contenteditable="false" data-formula="${encodeURIComponent(formatted)}" dir="ltr" style="display:inline-block;margin:0 3px;padding:1px 6px;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:5px;vertical-align:middle;user-select:all;cursor:pointer;">${katexHtml}</span>`;
    }

    last = match.index + rawMatch.length;
  }

  if (last < rawText.length) {
    result += escapeAndFormatPlain(rawText.slice(last));
  }

  return result;
}

function escapeAndFormatPlain(plain: string): string {
  // Convert standalone reaction lines like FeO(s) + 2HCl(dil) → FeCl2(aq) + H2O(l)
  const lines = plain.split("\n");
  return lines.map((line) => {
    const trimmed = line.trim();
    const isReaction = (
      (trimmed.includes("→") || trimmed.includes("⇌") || trimmed.includes("->")) &&
      /[A-Z][a-z]?/.test(trimmed) &&
      !/[أ-ي]/.test(trimmed)
    );

    if (isReaction) {
      const formatted = formatChemicalFormula(trimmed);
      const katexHtml = renderKatexToString(formatted, true);
      return `<div class="wysiwyg-math-block" contenteditable="false" data-formula="${encodeURIComponent(formatted)}" dir="ltr" style="display:block;margin:8px 0;padding:8px 14px;background:#f8fafc;border:1.5px solid #cbd5e1;border-radius:8px;text-align:center;user-select:all;cursor:pointer;">${katexHtml}</div>`;
    }

    // Escape basic HTML
    let escaped = line
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Format inline chemical formulas with subscripts: Fe3O4 -> Fe₃O₄
    escaped = formatChemicalFormula(escaped);

    return escaped;
  }).join("<br>");
}

/**
 * Serializes the contenteditable DOM back into clean, stable text format without raw delimiters.
 */
function wysiwygHtmlToText(container: HTMLElement): string {
  let output = "";

  function traverse(node: Node) {
    if (node.nodeType === Node.TEXT_NODE) {
      output += node.textContent || "";
      return;
    }

    if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement;

      // Check if it is a formula node
      if (el.hasAttribute("data-formula")) {
        const formula = decodeURIComponent(el.getAttribute("data-formula") || "");
        if (el.classList.contains("wysiwyg-math-block")) {
          output += `\n${formula}\n`;
        } else {
          output += ` ${formula} `;
        }
        return;
      }

      if (el.tagName === "BR") {
        output += "\n";
        return;
      }

      if (el.tagName === "DIV" || el.tagName === "P") {
        if (output && !output.endsWith("\n")) output += "\n";
        el.childNodes.forEach(traverse);
        if (!output.endsWith("\n")) output += "\n";
        return;
      }

      el.childNodes.forEach(traverse);
    }
  }

  container.childNodes.forEach(traverse);
  // Normalize whitespace
  return output.replace(/\n{3,}/g, "\n\n").trim();
}

export const RichFormulaEditor: React.FC<RichFormulaEditorProps> = ({
  value,
  onChange,
  placeholder = "اكتب نص السؤال هنا، ويمكنك كتابة أو إدراج المعادلات الكيميائية والرياضية...",
  label,
  minRows = 3,
}) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [selectedNode, setSelectedNode] = useState<{ element: HTMLElement; formula: string } | null>(null);
  const lastEmittedValueRef = useRef<string>(value);
  const isInitializedRef = useRef(false);

  // Sync incoming value with editor content when changed externally or on mount
  useEffect(() => {
    if (editorRef.current && (!isInitializedRef.current || value !== lastEmittedValueRef.current)) {
      editorRef.current.innerHTML = textToWysiwygHtml(value);
      lastEmittedValueRef.current = value;
      isInitializedRef.current = true;
    }
  }, [value]);

  const handleInput = useCallback(() => {
    if (!editorRef.current) return;
    const text = wysiwygHtmlToText(editorRef.current);
    lastEmittedValueRef.current = text;
    onChange(text);
  }, [onChange]);

  /**
   * Automatic Chemical Formatting on Paste:
   * When teacher pastes chemical reactions, formulas or text (e.g. N2(g) + 3H2(g) <=> 2NH3(g) or Fe3O4),
   * it automatically converts to textbook unicode notation without errors.
   */
  const handlePaste = (e: React.ClipboardEvent<HTMLDivElement>) => {
    e.preventDefault();
    const text = e.clipboardData.getData("text/plain");
    if (!text) return;

    const formatted = formatChemicalFormula(text);

    // Use execCommand to preserve undo/redo history if supported
    const success = document.execCommand?.("insertText", false, formatted);
    if (!success) {
      const sel = window.getSelection();
      if (sel && sel.rangeCount > 0 && editorRef.current?.contains(sel.anchorNode)) {
        const range = sel.getRangeAt(0);
        range.deleteContents();
        const textNode = document.createTextNode(formatted);
        range.insertNode(textNode);
        range.setStartAfter(textNode);
        range.setEndAfter(textNode);
        sel.removeAllRanges();
        sel.addRange(range);
      } else if (editorRef.current) {
        editorRef.current.appendChild(document.createTextNode(formatted));
      }
    }
    handleInput();
  };

  const handleBlur = () => {
    setIsFocused(false);
    if (!editorRef.current) return;
    const currentText = wysiwygHtmlToText(editorRef.current);
    const converted = formatChemicalFormula(currentText);
    if (converted !== currentText) {
      editorRef.current.innerHTML = textToWysiwygHtml(converted);
      handleInput();
    }
  };

  const handleEditorClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    const formulaEl = target.closest("[data-formula]") as HTMLElement | null;
    if (formulaEl) {
      const formula = decodeURIComponent(formulaEl.getAttribute("data-formula") || "");
      setSelectedNode({ element: formulaEl, formula });
    } else {
      setSelectedNode(null);
    }
  };

  const deleteSelectedNode = () => {
    if (selectedNode?.element) {
      selectedNode.element.remove();
      setSelectedNode(null);
      handleInput();
    }
  };

  const minHeightPx = Math.max(minRows * 28, 80);

  return (
    <div
      className="rich-formula-editor"
      style={{
        border: isFocused ? "1.5px solid #059669" : "1.5px solid var(--border-color-strong, #cbd5e1)",
        borderRadius: "10px",
        background: "var(--bg-surface, #ffffff)",
        boxShadow: isFocused ? "0 0 0 3px rgba(5, 150, 105, 0.15)" : "0 1px 4px rgba(0,0,0,0.04)",
        transition: "border-color 0.15s ease, box-shadow 0.15s ease",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Editor Header */}
      {label && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "8px 14px",
            background: "var(--bg-surface-secondary, #f8fafc)",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          <span style={{ fontSize: "12.5px", fontWeight: 800, color: "#0f392b" }}>
            {label}
          </span>
          <span style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
            (تحويل تلقائي للصيغ والمعادلات كالكتاب المدرسي)
          </span>
        </div>
      )}

      {/* Selected Node Action Bar (appears if teacher clicks on an existing formula in editor) */}
      {selectedNode && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "4px 12px",
            background: "#ecfdf5",
            borderBottom: "1px solid #a7f3d0",
            fontSize: "12px",
            color: "#065f46",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontWeight: 800 }}>معادلة محددة:</span>
            <code style={{ background: "#ffffff", padding: "2px 6px", borderRadius: "4px", border: "1px solid #a7f3d0", fontWeight: 700 }}>
              {selectedNode.formula}
            </code>
          </div>
          <button
            type="button"
            onClick={deleteSelectedNode}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "2px 8px",
              borderRadius: "4px",
              border: "1px solid #ef4444",
              background: "#fee2e2",
              color: "#b91c1c",
              fontSize: "11px",
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            <Trash2 size={11} />
            <span>حذف المعادلة</span>
          </button>
        </div>
      )}

      {/* WYSIWYG ContentEditable Surface */}
      <div
        ref={editorRef}
        contentEditable
        onInput={handleInput}
        onPaste={handlePaste}
        onClick={handleEditorClick}
        onFocus={() => setIsFocused(true)}
        onBlur={handleBlur}
        dir="rtl"
        style={{
          minHeight: `${minHeightPx}px`,
          padding: "12px 14px",
          outline: "none",
          fontSize: "14px",
          lineHeight: "1.8",
          color: "var(--text-main, #0f172a)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          overflowY: "auto",
        }}
        data-placeholder={placeholder}
      />
    </div>
  );
};
