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

export interface ExportDataPayload {
  title: string;
  subtitle?: string;
  generatedDate?: string;
  headers: string[];
  rows: (string | number)[][];
  summaryStats?: Array<{ label: string; value: string | number }>;
}

/**
 * Helper to escape special XML characters.
 */
function sanitizeXml(str: string | number | undefined | null): string {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
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
            new TextRun({ text: `${s.label} : `, bold: true, size: 22, color: "000000", rightToLeft: true }),
            new TextRun({ text: `${s.value}`, bold: true, size: 22, color: "000000", rightToLeft: true }),
          ],
        })
      );
    });
    // Add spacing before table
    docChildren.push(
      new Paragraph({
        spacing: { after: 140 },
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
 * Generates and downloads a genuine Microsoft Excel Workbook (.xls format)
 * with native 100% Right-To-Left display (DisplayRightToLeft), placing Column A
 * on the far right with "اسم الطالب" as the first column.
 */
export function exportToExcel(payload: ExportDataPayload, filename = "lms_data.xls") {
  const dateStr = payload.generatedDate || new Date().toLocaleDateString("ar-EG", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const xmlRows: string[] = [];

  // Title Row
  xmlRows.push(`
    <Row ss:Height="30">
      <Cell ss:MergeAcross="${Math.max(0, payload.headers.length - 1)}" ss:StyleID="TitleStyle">
        <Data ss:Type="String">${sanitizeXml(payload.title)}</Data>
      </Cell>
    </Row>
  `);

  // Date Row
  xmlRows.push(`
    <Row ss:Height="24">
      <Cell ss:MergeAcross="${Math.max(0, payload.headers.length - 1)}" ss:StyleID="DateStyle">
        <Data ss:Type="String">${sanitizeXml(`تاريخ التقرير: ${dateStr}`)}</Data>
      </Cell>
    </Row>
  `);

  // Summary stats rows (each on its own line, right-aligned)
  if (payload.summaryStats && payload.summaryStats.length > 0) {
    payload.summaryStats.forEach((s) => {
      xmlRows.push(`
        <Row ss:Height="22">
          <Cell ss:MergeAcross="${Math.max(0, payload.headers.length - 1)}" ss:StyleID="SummaryRowStyle">
            <Data ss:Type="String">${sanitizeXml(`${s.label} : ${s.value}`)}</Data>
          </Cell>
        </Row>
      `);
    });
  }

  // Empty separator row
  xmlRows.push(`<Row ss:Height="12"/>`);

  // Table Headers Row (starts from Column A on the right)
  xmlRows.push(`
    <Row ss:Height="26">
      ${payload.headers
        .map(
          (h, i) => `
        <Cell ss:StyleID="${i === 0 ? "HeaderNameStyle" : "HeaderStyle"}">
          <Data ss:Type="String">${sanitizeXml(h)}</Data>
        </Cell>
      `
        )
        .join("")}
    </Row>
  `);

  // Data Rows
  payload.rows.forEach((row, rowIdx) => {
    const isAlt = rowIdx % 2 === 1;
    xmlRows.push(`
      <Row ss:Height="22">
        ${row
          .map((val, cellIdx) => {
            const isFirst = cellIdx === 0;
            const styleId = isFirst
              ? isAlt
                ? "NameCellAlt"
                : "NameCell"
              : isAlt
              ? "DataCellAlt"
              : "DataCell";
            const isNum = typeof val === "number";
            return `
          <Cell ss:StyleID="${styleId}">
            <Data ss:Type="${isNum ? "Number" : "String"}">${sanitizeXml(val ?? "—")}</Data>
          </Cell>
        `;
          })
          .join("")}
      </Row>
    `);
  });

  const xmlContent = `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <Styles>
  <Style ss:ID="Default" ss:Name="Normal">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Font ss:FontName="Segoe UI" ss:Size="11" ss:Color="#0F172A"/>
  </Style>
  <Style ss:ID="TitleStyle">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Font ss:FontName="Segoe UI" ss:Size="16" ss:Bold="1" ss:Color="#2563EB"/>
  </Style>
  <Style ss:ID="DateStyle">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Font ss:FontName="Segoe UI" ss:Size="12" ss:Bold="1" ss:Color="#000000"/>
  </Style>
  <Style ss:ID="SummaryRowStyle">
   <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Font ss:FontName="Segoe UI" ss:Size="11" ss:Bold="1" ss:Color="#000000"/>
  </Style>
  <Style ss:ID="HeaderStyle">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#0F392B"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#0F392B"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#0F392B"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#0F392B"/>
   </Borders>
   <Font ss:FontName="Segoe UI" ss:Size="11" ss:Bold="1" ss:Color="#FFFFFF"/>
   <Interior ss:Color="#0F392B" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="HeaderNameStyle">
   <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#0F392B"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#0F392B"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#0F392B"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#0F392B"/>
   </Borders>
   <Font ss:FontName="Segoe UI" ss:Size="11" ss:Bold="1" ss:Color="#FFFFFF"/>
   <Interior ss:Color="#0F392B" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="NameCell">
   <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
   </Borders>
   <Font ss:FontName="Segoe UI" ss:Size="11" ss:Bold="1" ss:Color="#0F172A"/>
  </Style>
  <Style ss:ID="NameCellAlt">
   <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
   </Borders>
   <Font ss:FontName="Segoe UI" ss:Size="11" ss:Bold="1" ss:Color="#0F172A"/>
   <Interior ss:Color="#F8FAFC" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="DataCell">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
   </Borders>
   <Font ss:FontName="Segoe UI" ss:Size="11" ss:Color="#1E293B"/>
  </Style>
  <Style ss:ID="DataCellAlt">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:ReadingOrder="RightToLeft"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
   </Borders>
   <Font ss:FontName="Segoe UI" ss:Size="11" ss:Color="#1E293B"/>
   <Interior ss:Color="#F8FAFC" ss:Pattern="Solid"/>
  </Style>
 </Styles>
 <Worksheet ss:Name="التقرير" ss:RightToLeft="1">
  <Table ss:DefaultColumnWidth="130" ss:DefaultRowHeight="22">
    ${xmlRows.join("")}
  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <DisplayRightToLeft/>
  </WorksheetOptions>
 </Worksheet>
</Workbook>`;

  const blob = new Blob([xmlContent], { type: "application/vnd.ms-excel;charset=utf-8;" });
  const actualFilename = filename.endsWith(".xls") ? filename : filename.replace(/\.csv$/, ".xls");
  triggerDownload(blob, actualFilename.endsWith(".xls") ? actualFilename : `${actualFilename}.xls`);
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
    }
    .summary-item {
      font-size: 14.5px;
      font-weight: 800;
      color: #000000;
      display: flex;
      align-items: center;
      gap: 6px;
      direction: rtl;
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
