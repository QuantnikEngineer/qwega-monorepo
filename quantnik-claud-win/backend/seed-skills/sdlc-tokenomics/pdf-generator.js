// pdf-generator.js
//
// Bundled with the sdlc-tokenomics skill. Reads a JSON payload from stdin
// (same shape as xlsx-generator.js) and writes a presentation-ready PDF to
// the path given as argv[2].
//
// Usage:
//   echo "$JSON" | NODE_PATH=/path/to/quantnik/backend/node_modules \
//                  node pdf-generator.js /absolute/output/path.pdf
//
// Uses pdfkit's bufferPages mode: content is rendered first, then we go back
// and paint a footer on every page in a second pass. Avoids the pageAdded
// listener trap (writing text inside that handler can cause continueOnNewPage
// to recurse).

const fs = require('fs');
const PDFDocument = require('pdfkit');

const out = process.argv[2];
if (!out) {
  console.error('usage: node pdf-generator.js <output-path.pdf>  (JSON via stdin)');
  process.exit(2);
}

const data = JSON.parse(fs.readFileSync(0, 'utf8'));

const C = {
  ink:      '#1a1a1a',
  text:     '#333333',
  muted:    '#666666',
  faint:    '#999999',
  rule:     '#cccccc',
  accent:   '#0b6b3a',
  accentBg: '#e8f3ec',
  rowAlt:   '#f6f7f6',
  totalBg:  '#dfeae3',
  caveatBg: '#fef7e6',
  caveatBd: '#e3b341',
};

const doc = new PDFDocument({
  size: 'A4',
  margins: { top: 50, bottom: 60, left: 50, right: 50 },
  bufferPages: true,
  info: {
    Title:    'SDLC Tokenomics — ' + (data.project || 'project'),
    Author:   'quantnik / sdlc-tokenomics',
    Subject:  'Phase-by-phase LLM cost mapping',
    Producer: 'quantnik sdlc-tokenomics skill',
  },
});

const stream = fs.createWriteStream(out);
doc.pipe(stream);

const PAGE_W = doc.page.width;
const M = doc.page.margins;
const CONTENT_W = PAGE_W - M.left - M.right;
const fmt$ = (v) => `$${(Number(v) || 0).toFixed(2)}`;
const fmtN = (v) => (Number(v) || 0).toLocaleString();

// =========================================================================
// PAGE 1: Header + Summary card + Phase mapping table
// =========================================================================

// Title bar accent
doc.fillColor(C.accent).rect(M.left, M.top, CONTENT_W, 4).fill();
doc.fillColor(C.ink).font('Helvetica-Bold').fontSize(20)
  .text('SDLC Tokenomics', M.left, M.top + 16, { lineBreak: false });
doc.fillColor(C.muted).font('Helvetica').fontSize(10.5)
  .text('Phase-by-phase LLM cost mapping for the 11-phase sdlc-orchestrator workflow',
    M.left, M.top + 42, { width: CONTENT_W - 160 });

// Right-aligned project + date
doc.fillColor(C.muted).font('Helvetica').fontSize(9)
  .text('PROJECT', PAGE_W - M.right - 140, M.top + 16,
    { width: 140, align: 'right', lineBreak: false, characterSpacing: 0.6 });
doc.fillColor(C.ink).font('Helvetica-Bold').fontSize(12)
  .text(data.project || '—', PAGE_W - M.right - 140, M.top + 28,
    { width: 140, align: 'right', lineBreak: false });
doc.fillColor(C.muted).font('Helvetica').fontSize(9)
  .text((data.generated_at || new Date().toISOString().slice(0, 10)).toString(),
    PAGE_W - M.right - 140, M.top + 44, { width: 140, align: 'right', lineBreak: false });

// Summary card
const cardY = M.top + 78;
const cardH = 88;
doc.fillColor(C.accentBg).rect(M.left, cardY, CONTENT_W, cardH).fill();

const colW = CONTENT_W / 4;
const cards = [
  { label: 'SOURCE DOCUMENT',  value: data.document || '—',                                                                  big: false },
  { label: 'SIZE',             value: `${fmtN(data.char_count)} chars\n~${fmtN(data.doc_input_tokens)} tokens`,              big: false },
  { label: 'COMPLEXITY',       value: ((data.complexity || '—').split('(')[0]).trim(),                                       big: false },
  { label: 'TOTAL EST. COST',  value: fmt$(data.total_cost),                                                                  big: true  },
];
cards.forEach((c, i) => {
  const x = M.left + 12 + i * colW;
  doc.fillColor(C.muted).font('Helvetica').fontSize(8.5)
    .text(c.label, x, cardY + 14, { width: colW - 16, lineBreak: false, characterSpacing: 0.6 });
  // Lock the value cell to the card body height with ellipsis. Without
  // height+ellipsis a long filename would wrap below the card boundary AND
  // advance doc.y unpredictably, cascading into auto-paginated blank pages.
  doc.fillColor(c.big ? C.accent : C.ink).font('Helvetica-Bold').fontSize(c.big ? 22 : 11)
    .text(String(c.value), x, cardY + 30, {
      width: colW - 16,
      height: cardH - 36,
      ellipsis: true,
      lineBreak: !c.big, // big = total cost = single short value; others may need 2 lines
    });
});

doc.y = cardY + cardH + 18;

// Section heading: Phase mapping
doc.fillColor(C.ink).font('Helvetica-Bold').fontSize(13)
  .text('Phase mapping', M.left, doc.y, { lineBreak: true });
doc.fillColor(C.muted).font('Helvetica').fontSize(9.5)
  .text('Recommended LLM per phase with estimated tokens and cost. Prices last refreshed January 2026.',
    M.left, doc.y + 2, { width: CONTENT_W });
doc.moveDown(0.6);

// Phase table — fixed widths, no wrapped columns, fixed row height. Every
// doc.text call uses lineBreak:false so pdfkit never auto-paginates.
// IMPORTANT: column widths must sum to exactly CONTENT_W (495 on A4 with
// 50px margins). Each cell allots (w - 16) for text after 8px padding on
// each side; verify the widest expected value fits at the rendered font
// size, especially for right-aligned numeric cells where overflow bleeds
// LEFT into the previous column.
const cols = [
  { h: '#',          align: 'right' },
  { h: 'Phase',      align: 'left'  },
  { h: 'Model',      align: 'left'  },
  { h: 'Input tok',  align: 'right' },
  { h: 'Output tok', align: 'right' },
  { h: 'Cost (USD)', align: 'right' },
];
//          #   Phase  Model  Input  Output  Cost  = CONTENT_W (495)
// # column needs 16px+ to fit two-digit phase numbers ("10", "11") without
// ellipsising — at 9.5pt Helvetica that means w-16 >= 14 → w >= 30.
const widths = [32,   108,    144,    68,     70,    73];
cols.forEach((c, i) => { c.w = widths[i]; });
const _sumW = widths.reduce((a, b) => a + b, 0);
if (_sumW !== Math.round(CONTENT_W)) {
  // Self-correct rather than render an off-by-one mis-aligned table.
  widths[widths.length - 1] += Math.round(CONTENT_W) - _sumW;
  cols[cols.length - 1].w = widths[widths.length - 1];
}

let tY = doc.y;
const headerH = 22;
const rowH = 22;
doc.fillColor(C.ink).rect(M.left, tY, CONTENT_W, headerH).fill();
let cx = M.left;
doc.fillColor('white').font('Helvetica-Bold').fontSize(9);
for (const c of cols) {
  doc.text(c.h, cx + 8, tY + 7, {
    width: c.w - 16, height: headerH - 8, align: c.align,
    lineBreak: false, ellipsis: true,
  });
  cx += c.w;
}
tY += headerH;

let sumIn = 0, sumOut = 0, sumCost = 0;
(data.phases || []).forEach((p, idx) => {
  const r = [
    String(p.phase_n),
    p.phase || '',
    p.model || '',
    fmtN(p.input_tokens),
    fmtN(p.output_tokens),
    fmt$(p.cost),
  ];
  if (idx % 2 === 0) {
    doc.fillColor(C.rowAlt).rect(M.left, tY, CONTENT_W, rowH).fill();
  }
  cx = M.left;
  doc.fillColor(C.text);
  cols.forEach((c, i) => {
    const isModel = i === 2;
    doc.font(isModel ? 'Helvetica-Bold' : 'Helvetica').fontSize(9.5);
    doc.text(r[i], cx + 8, tY + 7, {
      width: c.w - 16, height: rowH - 8, align: c.align,
      lineBreak: false, ellipsis: true,
    });
    cx += c.w;
  });
  sumIn   += Number(p.input_tokens)  || 0;
  sumOut  += Number(p.output_tokens) || 0;
  sumCost += Number(p.cost)          || 0;
  tY += rowH;
});

// TOTAL row
const totalH = 24;
doc.fillColor(C.totalBg).rect(M.left, tY, CONTENT_W, totalH).fill();
const totals = ['', 'TOTAL', '', fmtN(sumIn), fmtN(sumOut), fmt$(sumCost)];
cx = M.left;
doc.fillColor(C.ink).font('Helvetica-Bold').fontSize(10);
cols.forEach((c, i) => {
  doc.text(totals[i], cx + 8, tY + 8, {
    width: c.w - 16, height: totalH - 8, align: c.align,
    lineBreak: false, ellipsis: true,
  });
  cx += c.w;
});
tY += totalH;
doc.y = tY + 12;

// Cost-concentration callout
const sortedByCost = (data.phases || []).slice().sort((a, b) => (b.cost || 0) - (a.cost || 0));
const top3 = sortedByCost.slice(0, 3);
const top3Sum = top3.reduce((s, p) => s + (p.cost || 0), 0);
const top3Pct = sumCost > 0 ? Math.round(top3Sum / sumCost * 100) : 0;
const top3Names = top3.map((p) => p.phase).join(' · ');
doc.fillColor(C.muted).font('Helvetica-Oblique').fontSize(9.5)
  .text(`Top 3 phases — ${top3Names} — account for ${top3Pct}% of the total (${fmt$(top3Sum)} of ${fmt$(sumCost)}).`,
    M.left, doc.y, { width: CONTENT_W });

// =========================================================================
// PAGE 2: Recommendation + Caveats
// =========================================================================
doc.addPage();

doc.fillColor(C.ink).font('Helvetica-Bold').fontSize(14)
  .text('Recommendation', M.left, M.top, { lineBreak: true });
doc.moveDown(0.3);
doc.fillColor(C.text).font('Helvetica').fontSize(10.5);

const recoLines = (data.recommendation && data.recommendation.length) ? data.recommendation : [
  `Estimated end-to-end spend for this project is ${fmt$(sumCost)}, with the top 3 phases (${top3Names}) accounting for ~${top3Pct}% of the budget.`,
  'That concentration is intentional — those are the phases where model quality directly shapes the artifact downstream: BRD shape drives every later phase, Feature Dev determines the architecture the team inherits, and Test Cases set the coverage floor for QA.',
  'If budget is the binding constraint, the cheapest viable substitution is Phase 3 → Claude Sonnet 4.6 (modest architecture-quality penalty) and Phase 6 → Claude Sonnet 4.6 (slightly thinner edge-case coverage). Phases 8 and 10 are already at the cost floor with Gemini 2.0 Flash — don\'t downgrade further; Flash-8b introduces a quality cliff on structured outputs.',
];
recoLines.forEach((para) => {
  doc.text(para, { width: CONTENT_W, align: 'justify' });
  doc.moveDown(0.6);
});

// Cost-optimised alternative box
if (data.cost_optimised_total != null) {
  doc.moveDown(0.4);
  const optY = doc.y;
  const optH = 62;
  doc.fillColor(C.accentBg).rect(M.left, optY, CONTENT_W, optH).fill();
  doc.fillColor(C.accent).font('Helvetica-Bold').fontSize(11)
    .text('Cost-optimised alternative', M.left + 14, optY + 12, { lineBreak: false });
  const saved = sumCost - data.cost_optimised_total;
  const savedPct = sumCost > 0 ? Math.round(saved / sumCost * 100) : 0;
  doc.fillColor(C.text).font('Helvetica').fontSize(10)
    .text(`Push Phases 1, 3, 6 onto Claude Sonnet 4.6 instead of Opus → total falls to ~${fmt$(data.cost_optimised_total)} (saves ${fmt$(saved)}, ${savedPct}%). You accept slightly less polished BRD shape and shallower test edge cases.`,
      M.left + 14, optY + 30, { width: CONTENT_W - 28 });
  doc.y = optY + optH + 14;
}

// Caveats section
doc.moveDown(0.6);
doc.fillColor(C.ink).font('Helvetica-Bold').fontSize(14)
  .text('Caveats', M.left, doc.y, { lineBreak: true });
doc.moveDown(0.3);

const caveats = (data.caveats && data.caveats.length) ? data.caveats : [
  '±30% directional. Real spend varies with retry loops, prompt-engineering overhead, mid-phase iteration, and tool-result content the agent re-reads as context.',
  'System-prompt overhead is not included. Per-phase input multipliers count only content tokens; the agent\'s system prompt + tool definitions add ~10-15k tokens per turn.',
  'quantnik\'s agent runtime is Claude-only today. Non-Claude picks can be costed but cannot yet be executed by the quantnik agent runtime.',
];

// Two-pass caveat box: pre-measure total height, paint background once,
// then render bullets on top.
const cvX = M.left;
const cvY = doc.y;
const cvPad = 12;
const cvBulletIndent = 26;
let cvBodyH = 0;
caveats.forEach((c) => {
  cvBodyH += doc.heightOfString(c, { width: CONTENT_W - cvBulletIndent - cvPad, align: 'justify' });
  cvBodyH += 6; // gap between bullets
});
const cvBoxH = cvBodyH + cvPad * 2;

doc.fillColor(C.caveatBg).rect(cvX, cvY, CONTENT_W, cvBoxH).fill();
doc.fillColor(C.caveatBd).rect(cvX, cvY, 3, cvBoxH).fill();

let cvCursorY = cvY + cvPad;
caveats.forEach((c) => {
  doc.fillColor(C.caveatBd).font('Helvetica-Bold').fontSize(10)
    .text('•', cvX + cvPad, cvCursorY, { lineBreak: false });
  doc.fillColor(C.text).font('Helvetica').fontSize(10)
    .text(c, cvX + cvBulletIndent, cvCursorY,
      { width: CONTENT_W - cvBulletIndent - cvPad, align: 'justify', lineBreak: true });
  cvCursorY = doc.y + 6;
});
doc.y = cvY + cvBoxH + 8;

// =========================================================================
// PAGE 3: Model catalog
// =========================================================================
doc.addPage();
doc.fillColor(C.ink).font('Helvetica-Bold').fontSize(14)
  .text('Model catalog — pricing reference', M.left, M.top, { lineBreak: true });
doc.fillColor(C.muted).font('Helvetica').fontSize(9.5)
  .text('USD per 1 million tokens. Last refreshed January 2026. Verify against vendor pages before committing budget.',
    M.left, doc.y + 2, { width: CONTENT_W });
doc.moveDown(0.6);

const catCols = [
  { h: 'Family',     align: 'left'  },
  { h: 'Model',      align: 'left'  },
  { h: '$/M input',  align: 'right' },
  { h: '$/M output', align: 'right' },
  { h: 'Best for',   align: 'left'  },
];
//             Family  Model  $/M in  $/M out  Best for  = CONTENT_W (495)
const catWidths = [62,    170,    72,     78,     113];
catCols.forEach((c, i) => { c.w = catWidths[i]; });
const _catSum = catWidths.reduce((a, b) => a + b, 0);
if (_catSum !== Math.round(CONTENT_W)) {
  catWidths[catWidths.length - 1] += Math.round(CONTENT_W) - _catSum;
  catCols[catCols.length - 1].w = catWidths[catWidths.length - 1];
}

let kY = doc.y;
const kHdrH = 20;
const kRowMin = 18;
const kPad = 5;
const kRowFontSize = 8.5;
const kLineHeight = 11; // 8.5pt × 1.3 line-height

doc.fillColor(C.ink).rect(M.left, kY, CONTENT_W, kHdrH).fill();
cx = M.left;
doc.fillColor('white').font('Helvetica-Bold').fontSize(9);
for (const c of catCols) {
  doc.text(c.h, cx + 8, kY + 6, {
    width: c.w - 16, height: kHdrH - 8, align: c.align,
    lineBreak: false, ellipsis: true,
  });
  cx += c.w;
}
kY += kHdrH;

const fmtPrice = (v) => v == null ? '' : (Number(v) < 0.1 ? `$${Number(v).toFixed(4)}` : `$${Number(v).toFixed(2)}`);
const bestForColW = catCols[4].w - 16;
const pageBottomY = doc.page.height - doc.page.margins.bottom;

(data.catalog || []).forEach((m, idx) => {
  // Pre-measure the wrapped "Best for" text — that's the only column that
  // wraps; others use lineBreak:false. Row height = max(measured + 2*pad,
  // kRowMin) so short notes don't waste space.
  doc.font('Helvetica').fontSize(kRowFontSize);
  const noteH = doc.heightOfString(m.note || '', { width: bestForColW, lineGap: 1 });
  const rowH = Math.max(Math.ceil(noteH) + kPad * 2, kRowMin);

  // Manual pagination guard: if this row would cross the page boundary,
  // start a new page and re-render a header band so the catalog stays
  // readable on overflow. Belt-and-braces — with current data this won't
  // trip, but keeps the generator robust against larger catalogs.
  if (kY + rowH > pageBottomY) {
    doc.addPage();
    kY = doc.page.margins.top;
    doc.fillColor(C.ink).rect(M.left, kY, CONTENT_W, kHdrH).fill();
    let cxh = M.left;
    doc.fillColor('white').font('Helvetica-Bold').fontSize(9);
    for (const c of catCols) {
      doc.text(c.h, cxh + 8, kY + 6, {
        width: c.w - 16, height: kHdrH - 8, align: c.align,
        lineBreak: false, ellipsis: true,
      });
      cxh += c.w;
    }
    kY += kHdrH;
  }

  if (idx % 2 === 0) {
    doc.fillColor(C.rowAlt).rect(M.left, kY, CONTENT_W, rowH).fill();
  }
  const row = [m.family || '', m.model || '', fmtPrice(m.in), fmtPrice(m.out), m.note || ''];
  cx = M.left;
  doc.fillColor(C.text);
  catCols.forEach((c, i) => {
    const isBestFor = i === 4;
    const isModel = i === 1;
    doc.font(isModel ? 'Helvetica-Bold' : 'Helvetica').fontSize(kRowFontSize);
    if (isBestFor) {
      // Wrap the "Best for" cell. Constrained by width + the row's
      // computed height so pdfkit clips rather than auto-paginates.
      doc.text(row[i], cx + 8, kY + kPad, {
        width: c.w - 16,
        height: rowH - kPad,
        align: c.align,
        lineBreak: true,
        lineGap: 1,
      });
    } else {
      // Numeric / short cells: top-aligned single line.
      doc.text(row[i], cx + 8, kY + kPad, {
        width: c.w - 16, height: rowH - kPad, align: c.align,
        lineBreak: false, ellipsis: true,
      });
    }
    cx += c.w;
  });
  kY += rowH;
});

// =========================================================================
// Footer pass — bufferPages mode lets us go back and paint footers
// without triggering pageAdded recursion. CRITICAL: footer y must be ABOVE
// the page's bottom margin (page.height - margins.bottom). Writing text at
// y below that boundary causes pdfkit to auto-page, creating phantom blank
// pages and a bogus high "Page N of M" total. Position the footer baseline
// 18px above the margin boundary so the rendered 8pt text (~10px tall)
// finishes well inside printable area.
// =========================================================================
const range = doc.bufferedPageRange();
const footerY = doc.page.height - doc.page.margins.bottom - 18;
const ruleY   = footerY - 8;
for (let i = range.start; i < range.start + range.count; i++) {
  doc.switchToPage(i);
  doc.strokeColor(C.rule).lineWidth(0.5)
    .moveTo(M.left, ruleY).lineTo(PAGE_W - M.right, ruleY).stroke();
  doc.fillColor(C.faint).font('Helvetica').fontSize(8);
  doc.text(`Generated by quantnik · sdlc-tokenomics · ${data.generated_at || new Date().toISOString().slice(0, 10)}`,
    M.left, footerY, { width: CONTENT_W, height: 12, align: 'left', lineBreak: false });
  doc.text(`Page ${i + 1 - range.start} of ${range.count}`, M.left, footerY,
    { width: CONTENT_W, height: 12, align: 'right', lineBreak: false });
}

doc.end();

stream.on('finish', () => {
  const size = fs.statSync(out).size;
  console.log(`wrote ${out} · ${size} bytes · ${range.count} pages`);
});
stream.on('error', (e) => {
  console.error('stream error:', e.message);
  process.exit(1);
});
