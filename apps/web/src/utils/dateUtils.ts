export interface FormattedDateTime {
  time: string;
  dayName: string;
  date: string;
}

/**
 * Formats a raw timestamp or ISO string into a simplified, clear format:
 * Line 1: Time e.g. "2:38 PM"
 * Line 2: Day Name e.g. "الخميس" (اسم اليوم فوق التاريخ)
 * Line 3: Date e.g. "9/24/2026"
 */
export function formatDateTimeSimple(raw?: string | Date | null): FormattedDateTime {
  if (!raw) return { time: "—", dayName: "", date: "" };
  if (typeof raw === "string" && (raw === "الآن" || raw === "اليوم" || raw === "—")) {
    const now = new Date();
    const dayName = now.toLocaleDateString("ar-EG", { weekday: "long" });
    const month = now.getMonth() + 1;
    const day = now.getDate();
    const year = now.getFullYear();
    const time = now.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
    return { time, dayName, date: `${month}/${day}/${year}` };
  }

  try {
    const d = typeof raw === "string" ? new Date(raw) : raw;
    if (isNaN(d.getTime())) {
      return { time: String(raw), dayName: "", date: "" };
    }

    // Format time: "2:38 PM"
    const time = d.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });

    // Format Arabic day name: e.g. "الخميس"
    const dayName = d.toLocaleDateString("ar-EG", { weekday: "long" });

    // Format date: "9/24/2026"
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const year = d.getFullYear();
    const date = `${month}/${day}/${year}`;

    return { time, dayName, date };
  } catch {
    return { time: String(raw), dayName: "", date: "" };
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
