export interface FormattedDateTime {
  time: string;
  date: string;
}

/**
 * Formats a raw timestamp or ISO string into a simplified, clear two-line format matching Image 4:
 * Line 1: Time e.g. "5:05 PM"
 * Line 2: Date e.g. "9/24/2026"
 */
export function formatDateTimeSimple(raw?: string | Date | null): FormattedDateTime {
  if (!raw) return { time: "—", date: "" };
  if (typeof raw === "string" && (raw === "الآن" || raw === "اليوم" || raw === "—")) {
    return { time: raw, date: "" };
  }

  try {
    const d = typeof raw === "string" ? new Date(raw) : raw;
    if (isNaN(d.getTime())) {
      return { time: String(raw), date: "" };
    }

    // Format time: "5:05 PM"
    const time = d.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });

    // Format date: "9/24/2026"
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const year = d.getFullYear();
    const date = `${month}/${day}/${year}`;

    return { time, date };
  } catch {
    return { time: String(raw), date: "" };
  }
}

/**
 * Single-line clean format: e.g. "5:05 PM — 9/24/2026"
 */
export function formatDateTimeInline(raw?: string | Date | null): string {
  const { time, date } = formatDateTimeSimple(raw);
  if (!date) return time;
  return `${time} — ${date}`;
}
