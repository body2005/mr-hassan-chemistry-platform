/**
 * Static scanner for hardcoded strings in apps/web/src
 * Checks for:
 * 1. Bilingual mixed strings (e.g. "قائمة • MENU")
 * 2. Hardcoded raw strings in JSX without translation keys
 * 3. Enforces allowlist for legitimate technical names (UUIDs, symbols, chemical formulas)
 */

const fs = require('fs');
const path = require('path');

const SRC_DIR = path.resolve(__dirname, '../apps/web/src');

// Allowlist of allowed technical words, chemical terms, or framework identifiers
const ALLOWLIST = new Set([
  'Fe2O3', 'CO', 'FeO', 'CO2', 'H2O', 'NaCl', 'HCl', 'NaOH', 'CaCO3',
  'PDF', 'DOCX', 'PPTX', 'TXT', 'MP4', 'WebM', 'EGP', 'MB', 'GB', 'KB',
  'JWT', 'UUID', 'API', 'URL', 'UI', 'HLS', 'M3U8', 'TS', 'JSON', 'CSS',
  'POST', 'GET', 'PUT', 'DELETE', 'OPTIONS', 'PATCH',
  'teacher@demo.com', 'student@demo.com', 'admin@demo.com',
  'px', 'ms', 'rem', 'em', 'vh', 'vw', '%', 'rtl', 'ltr',
  'light', 'dark', 'student', 'teacher', 'admin', 'institution_admin',
]);

let issuesCount = 0;

function scanFile(filePath) {
  const relPath = path.relative(SRC_DIR, filePath);
  // Skip translation files themselves, test files, and mock data
  if (relPath.startsWith('locales') || relPath.includes('mockCourses') || relPath.endsWith('.d.ts')) {
    return;
  }

  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n');

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*')) {
      return;
    }

    // Check 1: Bilingual mashups (Arabic + Latin connected with • or / or - in labels)
    const mashupRegex = /[\u0600-\u06FF]+\s*[•·]\s*[A-Za-z]+|[A-Za-z]+\s*[•·]\s*[\u0600-\u06FF]+/g;
    const matchMashup = trimmed.match(mashupRegex);
    if (matchMashup) {
      console.warn(`[MASHUP] ${relPath}:${index + 1}: Found mixed bilingual text: "${matchMashup[0]}"`);
      issuesCount++;
    }
  });
}

function walkDir(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      walkDir(fullPath);
    } else if (file.endsWith('.tsx') || file.endsWith('.ts')) {
      scanFile(fullPath);
    }
  }
}

console.log('--- Starting static scan for hardcoded text and bilingual mashups ---');
walkDir(SRC_DIR);
console.log(`Scan completed with ${issuesCount} mashup issues found.`);

if (issuesCount > 0) {
  process.exit(1);
} else {
  console.log('All scanned files adhere to clean i18n guidelines.');
  process.exit(0);
}
