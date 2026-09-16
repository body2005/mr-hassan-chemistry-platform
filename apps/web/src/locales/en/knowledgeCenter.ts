export const knowledgeCenterEn = {
  title: "AI Educational Knowledge Center",
  subtitle: "Manage curriculum textbooks, worksheets and notes that the AI uses to provide explanations, answer questions and generate assessments.",
  uploadZoneTitle: "Upload Knowledge Sources & Curriculum Textbooks",
  uploadZoneDesc: "Choose one or multiple books. Original files are preserved and pages/text are indexed (PDF, Word, PowerPoint, TXT).",
  chooseFilesBtn: "Select Textbooks or Documents to Upload",
  uploadingState: "Saving and staging files...",
  uploadProgressText: "Uploading files: {loaded} MB of {total} MB ({percent}%)",
  indexingState: "Indexing: {file} ({percent}%)...",
  uploadedSourcesCount: "Curriculum Uploaded Sources ({count})",
  loadingSources: "Loading knowledge sources...",
  noSourcesYet: "No educational sources uploaded for this course yet. Upload textbooks or PDFs to power the smart AI tutor.",
  cancelUploadTitle: "Cancel Indexing (keeps file on server)",

  // Table Columns (Notice: No Images/Figures column!)
  colFilename: "Source Name & File",
  colSize: "Size",
  colStatus: "Status & Progress",
  colUnits: "Indexed Units",
  colActions: "Actions",

  // Statuses
  statusIndexed: "Indexed",
  statusProcessing: "Indexing...",
  statusQueued: "Queued...",
  statusFailed: "Indexing Failed",
  unitWord: "units",

  // Actions
  actionPreview: "Preview Document",
  actionDownload: "Download Original File",
  actionDelete: "Delete Source",
  deleteConfirmTitle: "Knowledge Source - Delete",
  deleteConfirmMessage: "Are you sure you want to delete this source and all its indexed units? This action cannot be undone.",

  // Inspection Modal (Clean Document Reader)
  modalTitle: "Document Reader Preview: {file}",
  docFormat: "Document Format: {format}",
  pageWord: "Page",
  pageOfTotal: "of {total}",
  prevPage: "Previous",
  nextPage: "Next",
  zoomIn: "Zoom In (+)",
  zoomOut: "Zoom Out (-)",
  zoomFit: "Fit Width",
  zoomReset: "100%",
  preparingPage: "Rendering high-resolution page view...",
  pageReadyNotice: "Page rendered successfully",

  // Test Grounding Panel
  groundingTestTitle: "AI Grounding Test & Source Verification",
  groundingTestDesc: "Enter any question to test AI answer faithfulness and ensure citations directly reference uploaded sources.",
  groundingPlaceholder: "e.g., Explain ionic bonding or enter a formula like: Fe2O3 + CO -> 2FeO + CO2",
  askBtn: "Test Question",
  groundedAnswerTitle: "Grounded Answer (Referencing Curriculum):",
  refusalNotice: "Out of Curriculum Scope:",
};
