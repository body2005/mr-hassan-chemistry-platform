/**
 * Chemistry & Mathematical Formula Utilities
 * Provides Unicode conversions, smart chemical formula formatting,
 * and LaTeX delimiter normalization.
 */

export const SUB_DIGITS: Record<string, string> = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
  "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
};

export const REV_SUB_DIGITS: Record<string, string> = Object.fromEntries(
  Object.entries(SUB_DIGITS).map(([k, v]) => [v, k])
);

export const SUP_CHARS: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
  "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
  "+": "⁺", "-": "⁻", "(": "⁽", ")": "⁾",
};

export const REV_SUP_CHARS: Record<string, string> = Object.fromEntries(
  Object.entries(SUP_CHARS).map(([k, v]) => [v, k])
);

/**
 * Converts normal digits to Unicode subscripts (e.g. "2" -> "₂")
 */
export function toSubscript(text: string): string {
  return text.replace(/[0-9]/g, (ch) => SUB_DIGITS[ch] || ch);
}

/**
 * Converts normal digits & signs to Unicode superscripts (e.g. "2+" -> "²⁺")
 */
export function toSuperscript(text: string): string {
  return text.replace(/[0-9+-]/g, (ch) => SUP_CHARS[ch] || ch);
}

/**
 * Reverts Unicode subscripts back to standard digits
 */
export function fromSubscript(text: string): string {
  return text.replace(/[₀₁₂₃₄₅₆₇₈₉]/g, (ch) => REV_SUB_DIGITS[ch] || ch);
}

/**
 * Formats a plain chemical formula string into properly formatted textbook notation.
 * e.g.:
 * "H2O" -> "H₂O"
 * "Fe3O4" -> "Fe₃O₄"
 * "FeCl2" -> "FeCl₂"
 * "FeCl3" -> "FeCl₃"
 * "H2SO4" -> "H₂SO₄"
 * "Ca2+" -> "Ca²⁺"
 * "SO4^2-" -> "SO₄²⁻"
 * "Fe3O4 + 8HCl -> FeCl2 + 2FeCl3 + 4H2O" -> "Fe₃O₄ + 8HCl → FeCl₂ + 2FeCl₃ + 4H₂O"
 */
export function formatChemicalFormula(raw: string): string {
  if (!raw) return "";

  let text = raw;

  // 0. Clean raw LaTeX artifacts if copied from LaTeX source:
  // e.g. \text{N}_2 -> N_2, \Delta -> Δ, \rightleftharpoons -> ⇌
  text = text
    .replace(/\\Delta\b/g, "Δ")
    .replace(/\\rightleftharpoons\b/g, " ⇌ ")
    .replace(/\\rightarrow\b/g, " → ")
    .replace(/\\xrightarrow\s*\{[^}]*\}/g, " → ")
    .replace(/\\(?:text|mathrm|mathbf)\{([^}]+)\}/g, "$1")
    .replace(/[$]/g, "")
    .replace(/\\/g, "");

  // 1. Normalize arrows (equilibrium and irreversible)
  text = text.replace(/<==>|<=>/g, " ⇌ ");
  text = text.replace(/<->|==>|-->|->/g, " → ");

  // 2. Normalize reaction states like _(s), _{(s)}, (s), etc.
  text = text.replace(/_?\s*\(\s*(s|aq|l|g|dil|conc)\s*\)/gi, "($1)");

  // 3. Format Delta H: "Delta H", "delta H", "Δ H" -> "ΔH"
  text = text.replace(/\b(?:Delta|delta)\s*H\b/g, "ΔH");
  text = text.replace(/Δ\s*H/g, "ΔH");

  // 4. Format charge superscripts like ^2+, ^3+, ^-, ^+, 2+, 3+, 2-
  text = text.replace(/\^([0-9]*[+-])/g, (_, ch) => toSuperscript(ch));
  text = text.replace(/([A-Za-z)\]])([2-4]?[+-])(?=[\s,.)\]]|$)/g, (_, base, ch) => {
    return base + toSuperscript(ch);
  });

  // 5. Convert numbers immediately following chemical symbols or closing brackets into subscripts
  // Standard element tokens: Capital letter followed optionally by lowercase letter
  // Examples: Fe3 -> Fe₃, O4 -> O₄, Cl2 -> Cl₂, (SO4)3 -> (SO₄)₃, N2 -> N₂, H2 -> H₂, NH3 -> NH₃
  text = text.replace(/([A-Z][a-z]?|\))(\d+)/g, (_, symbol, digits) => {
    return symbol + toSubscript(digits);
  });

  // Clean up excessive whitespace around operators
  text = text.replace(/\s*([+→⇌=])\s*/g, " $1 ");
  text = text.replace(/\s{2,}/g, " ").trim();

  return text;
}

/**
 * Normalizes text containing LaTeX or formula markup so it can be cleanly displayed.
 * Strips raw delimiters while keeping the formula content intact.
 */
export function normalizeFormulaText(text: string): string {
  if (!text) return "";

  let normalized = text;

  // 1. Convert LaTeX temperature / degrees: 400^\circ C or 400^\circ\text{C} -> 400°C
  normalized = normalized.replace(/\^\{?\\?circ\}?\s*\\?(?:text|mathrm)?\{?([CF])\}?/gi, "°$1");
  normalized = normalized.replace(/\^\{?\\?circ\}?/gi, "°");

  // 2. Strip \text{...}, text{...}, \mathrm{...}, \mathbf{...}
  normalized = normalized.replace(/\\?(?:text|mathrm|mathbf)\{([^}]+)\}/g, "$1");

  // 3. Convert \xrightarrow{condition} -> ⎯⎯(condition)→
  normalized = normalized.replace(/\\xrightarrow\s*\{([^}]*)\}/g, (_, condition) => {
    const cleanCond = condition
      .replace(/\\quad/g, " ")
      .replace(/\\?(?:text|mathrm)\{([^}]+)\}/g, "$1")
      .replace(/\^\{?\\?circ\}?/g, "°")
      .trim();
    return cleanCond ? ` ⎯⎯(${cleanCond})→ ` : " → ";
  });
  normalized = normalized.replace(/\\xrightarrow|\\rightarrow|\\to/g, " → ");
  normalized = normalized.replace(/\\rightleftharpoons|\\leftrightharpoons/g, " ⇌ ");

  // 4. Convert \times -> ×
  normalized = normalized.replace(/\\times/g, "×");

  // 5. Convert LaTeX chemical state syntax like FeO_{(s)} or FeO_(s) -> FeO(s)
  normalized = normalized.replace(/_\{?\(([a-zA-Z]+)\)\}?/g, "($1)");

  // 6. Convert LaTeX subscript syntax like Fe_3O_4 or H_2O -> Fe₃O₄ or H₂O
  normalized = normalized.replace(/_\{?(\d+)\}?/g, (_, digits) => toSubscript(digits));

  // 7. Strip dollar sign delimiters: $$...$$ or $...$
  normalized = normalized.replace(/\$\$([^$]+)\$\$/g, "$1");
  normalized = normalized.replace(/\$([^$]+)\$/g, "$1");

  // 8. Strip bracket delimiters: \[...\] or \(...\)
  normalized = normalized.replace(/\\\[([^\]]+)\\\]/g, "$1");
  normalized = normalized.replace(/\\\(([^)]+)\\\)/g, "$1");

  // 9. Strip leftover backslashes in front of Latin symbols
  normalized = normalized.replace(/\\([a-zA-Z]+)/g, "$1");

  // 10. Format chemical formulas with subscripts and clean spacing
  return formatChemicalFormula(normalized);
}

/**
 * Detects if a text fragment is likely a mathematical equation or chemical reaction.
 */
export function containsFormulaOrMath(text: string): boolean {
  if (!text) return false;
  return (
    text.includes("$") ||
    text.includes("\\(") ||
    text.includes("\\[") ||
    text.includes("→") ||
    text.includes("->") ||
    text.includes("⇌") ||
    text.includes("⎯") ||
    text.includes("°") ||
    text.includes("text{") ||
    text.includes("xrightarrow") ||
    /[₀₁₂₃₄₅₆₇₈₉]/.test(text) ||
    /[⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹]/.test(text) ||
    /\b(?:Fe|Cu|Na|Cl|SO|NO|CO|Ca|Mg|Al|Zn|Ag|Pb|HCl|HNO|H2SO4|NaOH|H2O|NH3)\b/.test(text)
  );
}
