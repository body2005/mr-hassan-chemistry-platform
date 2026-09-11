import {
  Document,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
  HeadingLevel,
  AlignmentType,
  BorderStyle,
} from "docx";

export interface ExportDataPayload {
  title: string;
  subtitle?: string;
  generatedDate?: string;
  headers: string[];
  rows: (string | number)[][];
  summaryStats?: Array<{ label: string; value: string | number }>;
}

/**
 * Generates and downloads a real Microsoft Word .docx (OOXML binary format) file.
 */
export async function exportToDocx(payload: ExportDataPayload, filename = "lms_report.docx") {
  const dateStr = payload.generatedDate || new Date().toLocaleDateString("ar-EG", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const docChildren: any[] = [
    new Paragraph({
      text: payload.title,
      heading: HeadingLevel.HEADING_1,
      alignment: AlignmentType.CENTER,
      spacing: { after: 120 },
    }),
  ];

  if (payload.subtitle) {
    docChildren.push(
      new Paragraph({
        text: payload.subtitle,
        alignment: AlignmentType.CENTER,
        spacing: { after: 160 },
        children: [
          new TextRun({
            text: ` | تاريخ التقرير: ${dateStr}`,
            italics: true,
            color: "666666",
          }),
        ],
      })
    );
  }

  if (payload.summaryStats && payload.summaryStats.length > 0) {
    const statRuns: TextRun[] = [];
    payload.summaryStats.forEach((s) => {
      statRuns.push(
        new TextRun({ text: `• ${s.label}: `, bold: true }),
        new TextRun({ text: `${s.value}   ` })
      );
    });
    docChildren.push(
      new Paragraph({
        children: statRuns,
        spacing: { after: 200 },
      })
    );
  }

  // Build Document Table
  const headerRow = new TableRow({
    tableHeader: true,
    children: payload.headers.map(
      (h) =>
        new TableCell({
          width: { size: Math.floor(100 / payload.headers.length), type: WidthType.PERCENTAGE },
          shading: { fill: "164F40" },
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({
                  text: String(h),
                  bold: true,
                  color: "FFFFFF",
                }),
              ],
            }),
          ],
        })
    ),
  });

  const dataRows = payload.rows.map(
    (row, idx) =>
      new TableRow({
        children: row.map(
          (cell) =>
            new TableCell({
              width: { size: Math.floor(100 / payload.headers.length), type: WidthType.PERCENTAGE },
              shading: { fill: idx % 2 === 0 ? "F9FAFB" : "FFFFFF" },
              children: [
                new Paragraph({
                  alignment: AlignmentType.CENTER,
                  children: [new TextRun({ text: String(cell ?? "") })],
                }),
              ],
            })
        ),
      })
  );

  const table = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1, color: "D1D5DB" },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: "D1D5DB" },
      left: { style: BorderStyle.SINGLE, size: 1, color: "D1D5DB" },
      right: { style: BorderStyle.SINGLE, size: 1, color: "D1D5DB" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: "E5E7EB" },
      insideVertical: { style: BorderStyle.SINGLE, size: 1, color: "E5E7EB" },
    },
    rows: [headerRow, ...dataRows],
  });

  docChildren.push(table);

  const doc = new Document({
    sections: [
      {
        properties: {},
        children: docChildren,
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  triggerDownload(blob, filename.endsWith(".docx") ? filename : `${filename}.docx`);
}

/**
 * Generates and downloads a CSV / Excel compatible spreadsheet file with UTF-8 BOM.
 */
export function exportToCsv(payload: ExportDataPayload, filename = "lms_data.csv") {
  const csvRows: string[] = [];

  // Header line
  csvRows.push(payload.headers.map((h) => `"${String(h).replace(/"/g, '""')}"`).join(","));

  // Data rows
  payload.rows.forEach((row) => {
    csvRows.push(row.map((val) => `"${String(val ?? "").replace(/"/g, '""')}"`).join(","));
  });

  const csvContent = "\uFEFF" + csvRows.join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  triggerDownload(blob, filename.endsWith(".csv") ? filename : `${filename}.csv`);
}

/**
 * Opens a styled printable window for native high-resolution PDF saving/printing.
 */
export function exportToPrintPdf(payload: ExportDataPayload) {
  const printWindow = window.open("", "_blank");
  if (!printWindow) return;

  const dateStr = payload.generatedDate || new Date().toLocaleDateString("ar-EG", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const html = `
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
      <meta charset="utf-8">
      <title>${payload.title}</title>
      <style>
        body {
          font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif;
          margin: 30px;
          color: #1e293b;
          direction: rtl;
        }
        .header {
          text-align: center;
          border-bottom: 2px solid #0f392b;
          padding-bottom: 16px;
          margin-bottom: 24px;
        }
        .header h1 {
          margin: 0 0 6px;
          color: #0f392b;
          font-size: 24px;
        }
        .header p {
          margin: 0;
          color: #64748b;
          font-size: 13px;
        }
        .summary-box {
          background: #f8fafc;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 12px 18px;
          margin-bottom: 20px;
          display: flex;
          gap: 20px;
          flex-wrap: wrap;
        }
        .stat-item strong {
          color: #0f392b;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          margin-top: 10px;
          font-size: 13px;
        }
        th {
          background: #0f392b;
          color: white;
          padding: 10px 12px;
          border: 1px solid #0f392b;
          font-weight: bold;
        }
        td {
          padding: 9px 12px;
          border: 1px solid #cbd5e1;
          text-align: center;
        }
        tr:nth-child(even) {
          background: #f8fafc;
        }
        .footer {
          margin-top: 30px;
          text-align: center;
          color: #94a3b8;
          font-size: 11px;
          border-top: 1px solid #e2e8f0;
          padding-top: 10px;
        }
        @media print {
          body { margin: 15mm; }
          button { display: none; }
        }
      </style>
    </head>
    <body>
      <div class="header">
        <h1>${payload.title}</h1>
        <p>${payload.subtitle || ""} • صُدر في: ${dateStr}</p>
      </div>

      ${
        payload.summaryStats && payload.summaryStats.length > 0
          ? `
        <div class="summary-box">
          ${payload.summaryStats
            .map(
              (s) => `
            <div class="stat-item">
              <span>${s.label}: </span>
              <strong>${s.value}</strong>
            </div>
          `
            )
            .join("")}
        </div>
      `
          : ""
      }

      <table>
        <thead>
          <tr>
            ${payload.headers.map((h) => `<th>${h}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${payload.rows
            .map(
              (row) => `
            <tr>
              ${row.map((val) => `<td>${val ?? "—"}</td>`).join("")}
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>

      <div class="footer">
        منصة التعلم الذكية • تقرير رسمي معتمد
      </div>

      <script>
        window.onload = function() {
          window.print();
        }
      </script>
    </body>
    </html>
  `;

  printWindow.document.write(html);
  printWindow.document.close();
}

function triggerDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.style.display = "none";
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}
