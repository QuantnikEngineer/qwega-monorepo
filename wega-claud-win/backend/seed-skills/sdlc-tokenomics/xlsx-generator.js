// xlsx-generator.js
//
// Bundled with the sdlc-tokenomics skill. Invoked at runtime by the agent
// (see SKILL.md §7b). Reads a JSON payload from stdin and writes a 3-sheet
// Excel workbook to the path given as the first CLI argument.
//
// Usage (from inside the skill):
//   echo "$JSON" | NODE_PATH=/path/to/quantnik/backend/node_modules \
//                  node xlsx-generator.js /absolute/output/path.xlsx
//
// The exceljs dependency is satisfied via NODE_PATH — on a quantnik host this
// points at backend/node_modules/exceljs (added as a permanent dep so the
// install is once-only and cached across runs).

const fs = require('fs');
const ExcelJS = require('exceljs');

const out = process.argv[2];
if (!out) {
  console.error('usage: node xlsx-generator.js <output-path.xlsx>  (JSON via stdin)');
  process.exit(2);
}

const raw = fs.readFileSync(0, 'utf8'); // stdin
const data = JSON.parse(raw);

const wb = new ExcelJS.Workbook();
wb.creator = 'quantnik / sdlc-tokenomics';
wb.created = new Date();

// --- Sheet 1: Summary ------------------------------------------------------
const s1 = wb.addWorksheet('Summary');
s1.columns = [{ width: 30 }, { width: 56 }];
s1.addRow(['SDLC Tokenomics', '']).font = { bold: true, size: 14 };
s1.addRow([]);
s1.addRow(['Project',                    data.project || '']);
s1.addRow(['Source document',            data.document || '']);
const cChars = s1.addRow(['Document size (chars)', data.char_count || 0]);
cChars.getCell(2).numFmt = '#,##0';
const cTok = s1.addRow(['Document tokens (est.)', data.doc_input_tokens || 0]);
cTok.getCell(2).numFmt = '#,##0';
s1.addRow(['Complexity',                 data.complexity || '']);
s1.addRow(['Generated',                  data.generated_at || new Date().toISOString().slice(0, 16).replace('T', ' ')]);
const tot = s1.addRow(['Total estimated cost (USD)', data.total_cost || 0]);
tot.font = { bold: true };
tot.getCell(2).numFmt = '"$"#,##0.00';
s1.addRow([]);
const caveat = s1.addRow(['Caveat', 'Estimates are directional (±30%). Prices last refreshed Jan 2026. quantnik today executes only Claude — non-Claude picks are cost references, not immediate execution targets.']);
caveat.getCell(2).alignment = { wrapText: true, vertical: 'top' };
s1.getRow(caveat.number).height = 64;

// --- Sheet 2: Phase mapping ------------------------------------------------
const s2 = wb.addWorksheet('Phase mapping');
s2.columns = [
  { header: '#',                 width:  5 },
  { header: 'Phase',             width: 22 },
  { header: 'Recommended model', width: 24 },
  { header: 'Input tokens',      width: 14 },
  { header: 'Output tokens',     width: 14 },
  { header: 'Cost (USD)',        width: 12 },
  { header: 'Rationale',         width: 48 },
];
const h2 = s2.getRow(1);
h2.font = { bold: true };
h2.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFDDDDDD' } };
for (const p of (data.phases || [])) {
  const r = s2.addRow([
    p.phase_n,
    p.phase,
    p.model,
    p.input_tokens || 0,
    p.output_tokens || 0,
    p.cost || 0,
    p.rationale || '',
  ]);
  r.getCell(4).numFmt = '#,##0';
  r.getCell(5).numFmt = '#,##0';
  r.getCell(6).numFmt = '"$"#,##0.00';
  r.getCell(7).alignment = { wrapText: true, vertical: 'top' };
}
const tr = s2.addRow([
  '', 'TOTAL', '',
  data.total_input  || (data.phases || []).reduce((a, p) => a + (p.input_tokens  || 0), 0),
  data.total_output || (data.phases || []).reduce((a, p) => a + (p.output_tokens || 0), 0),
  data.total_cost   || (data.phases || []).reduce((a, p) => a + (p.cost          || 0), 0),
  '',
]);
tr.font = { bold: true };
tr.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFEEEEEE' } };
tr.getCell(4).numFmt = '#,##0';
tr.getCell(5).numFmt = '#,##0';
tr.getCell(6).numFmt = '"$"#,##0.00';

// --- Sheet 3: Model catalog ------------------------------------------------
const s3 = wb.addWorksheet('Model catalog');
s3.columns = [
  { header: 'Family',     width: 12 },
  { header: 'Model',      width: 32 },
  { header: '$/M input',  width: 12 },
  { header: '$/M output', width: 12 },
  { header: 'Best for',   width: 55 },
];
const h3 = s3.getRow(1);
h3.font = { bold: true };
h3.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFDDDDDD' } };
for (const m of (data.catalog || [])) {
  const r = s3.addRow([m.family, m.model, m.in, m.out, m.note]);
  r.getCell(3).numFmt = '"$"0.0000';
  r.getCell(4).numFmt = '"$"0.0000';
  r.getCell(5).alignment = { wrapText: true, vertical: 'top' };
}

wb.xlsx.writeFile(out).then(() => {
  const size = fs.statSync(out).size;
  console.log(`wrote ${out} · ${size} bytes`);
});
