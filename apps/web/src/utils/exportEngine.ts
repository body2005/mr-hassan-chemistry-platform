import {
  Document,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
  AlignmentType,
  BorderStyle,
} from "docx";
import * as XLSX from "xlsx";

export interface ExportDataPayload {
  title: string;
  subtitle?: string;
  generatedDate?: string;
  headers: string[];
  rows: (string | number)[][];
  summaryStats?: Array<{ label: string; value: string | number }>;
}

/**
 * Generates and downloads a real Microsoft Word .docx (OOXML binary format) file,
 * 100% Right-To-Left (RTL) with the first column (اسم الطالب) at the far right.
 */
export async function exportToDocx(payload: ExportDataPayload, filename = "lms_report.docx") {
  const dateStr = payload.generatedDate || new Date().toLocaleDateString("ar-EG", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const docChildren: (Paragraph | Table)[] = [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      bidirectional: true,
      spacing: { after: 100 },
      children: [
        new TextRun({
          text: payload.title,
          bold: true,
          size: 32, // 16pt
          color: "2563EB",
          rightToLeft: true,
        }),
      ],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      bidirectional: true,
      spacing: { after: 200 },
      children: [
        new TextRun({
          text: `تاريخ التقرير: ${dateStr}`,
          bold: true,
          size: 24, // 12pt
          color: "000000",
          rightToLeft: true,
        }),
      ],
    }),
  ];

  if (payload.summaryStats && payload.summaryStats.length > 0) {
    payload.summaryStats.forEach((s) => {
      docChildren.push(
        new Paragraph({
          alignment: AlignmentType.RIGHT,
          bidirectional: true,
          spacing: { after: 60 },
          children: [
            new TextRun({
              text: `${s.label} : `,
              bold: true,
              size: 22,
              color: "000000",
              rightToLeft: true,
            }),
            new TextRun({
              text: `${s.value}`,
              bold: true,
              size: 22,
              color: "000000",
              rightToLeft: true,
            }),
          ],
        })
      );
    });

    // Add spacing after summary stats before the table
    docChildren.push(
      new Paragraph({
        spacing: { after: 120 },
        children: [],
      })
    );
  }

  // Build Document Table (Right-to-Left layout via visuallyRightToLeft)
  // Because visuallyRightToLeft is true, the 1st TableCell is placed at the FAR RIGHT!
  const headerRow = new TableRow({
    tableHeader: true,
    children: payload.headers.map(
      (h, idx) =>
        new TableCell({
          width: { size: Math.floor(100 / payload.headers.length), type: WidthType.PERCENTAGE },
          shading: { fill: "0F392B" },
          children: [
            new Paragraph({
              alignment: idx === 0 ? AlignmentType.RIGHT : AlignmentType.CENTER,
              bidirectional: true,
              children: [
                new TextRun({
                  text: String(h),
                  bold: true,
                  color: "FFFFFF",
                  rightToLeft: true,
                }),
              ],
            }),
          ],
        })
    ),
  });

  const dataRows = payload.rows.map(
    (row, rowIdx) =>
      new TableRow({
        children: row.map(
          (cell, cellIdx) =>
            new TableCell({
              width: { size: Math.floor(100 / payload.headers.length), type: WidthType.PERCENTAGE },
              shading: { fill: rowIdx % 2 === 0 ? "F8FAFC" : "FFFFFF" },
              children: [
                new Paragraph({
                  alignment: cellIdx === 0 ? AlignmentType.RIGHT : AlignmentType.CENTER,
                  bidirectional: true,
                  children: [
                    new TextRun({
                      text: String(cell ?? "—"),
                      bold: cellIdx === 0,
                      rightToLeft: true,
                    }),
                  ],
                }),
              ],
            })
        ),
      })
  );

  const table = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    visuallyRightToLeft: true,
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1, color: "CBD5E1" },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: "CBD5E1" },
      left: { style: BorderStyle.SINGLE, size: 1, color: "CBD5E1" },
      right: { style: BorderStyle.SINGLE, size: 1, color: "CBD5E1" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: "E2E8F0" },
      insideVertical: { style: BorderStyle.SINGLE, size: 1, color: "E2E8F0" },
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
 * Generates and downloads a genuine Microsoft Excel Workbook (.xlsx format)
 * with native 100% Right-To-Left display (RTL), placing Column A
 * on the far right with "اسم الطالب" as the first column and native Arabic typography.
 */
export function exportToExcel(payload: ExportDataPayload, filename = "lms_data.xlsx") {
  const dateStr = payload.generatedDate || new Date().toLocaleDateString("ar-EG", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const sheetData: (string | number)[][] = [
    [payload.title],
    [`تاريخ التقرير: ${dateStr}`],
    [],
  ];

  if (payload.summaryStats && payload.summaryStats.length > 0) {
    payload.summaryStats.forEach((s) => {
      sheetData.push([`${s.label} : ${s.value}`]);
    });
    sheetData.push([]);
  }

  sheetData.push(payload.headers);
  payload.rows.forEach((row) => {
    sheetData.push(row.map((cell) => (cell ?? "—")));
  });

  const ws = XLSX.utils.aoa_to_sheet(sheetData);
  ws["!views"] = [{ RTL: true }];
  ws["!cols"] = payload.headers.map((h, i) => ({
    wch: i === 0 ? 25 : Math.max(String(h).length + 6, 16),
  }));

  const wb = XLSX.utils.book_new();
  const cleanSheetName = (payload.title || "التقرير")
    .replace(/[\\/?*[\]]/g, "")
    .slice(0, 31)
    .trim() || "التقرير";
  XLSX.utils.book_append_sheet(wb, ws, cleanSheetName);

  const wbout = XLSX.write(wb, { bookType: "xlsx", type: "array" });
  const blob = new Blob([wbout], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const actualFilename = filename.replace(/\.xls[x]?$/, "") + ".xlsx";
  triggerDownload(blob, actualFilename);
}

/**
 * Generates and downloads a CSV spreadsheet file with UTF-8 BOM,
 * retaining the exact table order starting from the rightmost column (اسم الطالب).
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
 * Opens a styled printable window for native high-resolution PDF saving/printing,
 * 100% Right-To-Left (RTL) with the first column (اسم الطالب) at the far right.
 */
export function exportToPrintPdf(payload: ExportDataPayload, filename = "") {
  const printWindow = window.open("", "_blank");
  if (!printWindow) return;

  const dateStr = payload.generatedDate || new Date().toLocaleDateString("ar-EG", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const html = `<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
  <meta charset="utf-8">
  <title>${filename || payload.title}</title>
  <style>
    @page {
      size: A4 landscape;
      margin: 10mm 12mm;
    }
    * {
      box-sizing: border-box;
      direction: rtl;
    }
    body {
      font-family: 'Cairo', 'Segoe UI', Tahoma, Arial, sans-serif;
      margin: 0;
      padding: 24px;
      color: #0f172a;
      direction: rtl;
      text-align: right;
      background: #ffffff;
    }
    .header {
      text-align: center;
      margin-bottom: 22px;
      direction: rtl;
    }
    .header h1 {
      margin: 0 0 8px;
      color: #2563eb;
      font-size: 22px;
      font-weight: 800;
    }
    .header h2 {
      margin: 0;
      color: #000000;
      font-size: 17px;
      font-weight: 900;
    }
    .summary-list {
      margin: 0 0 20px 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
      direction: rtl;
      text-align: right;
      align-items: flex-start;
      justify-content: flex-start;
    }
    .summary-item {
      font-size: 14.5px;
      font-weight: 800;
      color: #000000;
      display: flex;
      align-items: center;
      gap: 6px;
      direction: rtl;
      text-align: right;
      justify-content: flex-start;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 12px;
      direction: rtl;
      table-layout: auto;
    }
    th {
      background: #0f392b;
      color: #ffffff;
      padding: 10px 8px;
      border: 1px solid #0f392b;
      font-weight: 800;
      text-align: center;
      font-size: 12px;
      direction: rtl;
    }
    th:first-child {
      text-align: right;
      padding-right: 14px;
    }
    td {
      padding: 8px 8px;
      border: 1px solid #cbd5e1;
      text-align: center;
      color: #1e293b;
      direction: rtl;
    }
    td:first-child {
      text-align: right;
      font-weight: 700;
      padding-right: 14px;
      color: #0f172a;
    }
    tr:nth-child(even) {
      background: #f8fafc;
    }
    .footer {
      margin-top: 24px;
      text-align: center;
      color: #94a3b8;
      font-size: 11px;
      border-top: 1px solid #e2e8f0;
      padding-top: 10px;
      direction: rtl;
    }
    @media print {
      body { margin: 0; padding: 0; direction: rtl; }
      button { display: none; }
      thead { display: table-header-group; }
      tr { page-break-inside: avoid; }
      table { direction: rtl; }
    }
  </style>
</head>
<body dir="rtl">
  <div class="header">
    <h1>${payload.title}</h1>
    <h2>تاريخ التقرير: ${dateStr}</h2>
  </div>

  ${
    payload.summaryStats && payload.summaryStats.length > 0
      ? `
    <div class="summary-list">
      ${payload.summaryStats
        .map(
          (s) => `
        <div class="summary-item">
          <span>${s.label} : </span>
          <span style="font-weight: 900;">${s.value}</span>
        </div>
      `
        )
        .join("")}
    </div>
  `
      : ""
  }

  <table dir="rtl">
    <thead>
      <tr>
        ${payload.headers.map((h, i) => `<th style="${i === 0 ? 'text-align: right;' : 'text-align: center;'}">${h}</th>`).join("")}
      </tr>
    </thead>
    <tbody>
      ${payload.rows
        .map(
          (row) => `
        <tr>
          ${row.map((val, i) => `<td style="${i === 0 ? 'text-align: right; font-weight: 700;' : 'text-align: center;'}">${val ?? "—"}</td>`).join("")}
        </tr>
      `
        )
        .join("")}
    </tbody>
  </table>

  <div class="footer">
    منصة التعلم الذكية • تقرير رسمي معتمد وموثق
  </div>

  <script>
    window.onload = function() {
      window.print();
    }
  </script>
</body>
</html>`;

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
