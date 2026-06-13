#!/usr/bin/env node
/**
 * generate_brd_docx.js
 * Generates a BRD .docx that exactly matches the defined template structure.
 * Called by docx_generator.py as a subprocess.
 * 
 * Usage: node generate_brd_docx.js <input_json_path> <output_docx_path>
 * 
 * Input JSON shape:
 * {
 *   "project_name": "...",
 *   "version": "1.0",
 *   "date": "...",
 *   "prepared_by": "...",
 *   "stakeholders": [{ "name": "...", "email": "...", "role": "..." }],
 *   "sections": {
 *     "executive_summary": { "content": "...", "is_ai_assumed": false },
 *     "business_background": { "content": "...", "is_ai_assumed": false },
 *     ... (keyed by section_key)
 *   }
 * }
 */

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, LevelFormat,
  TabStopType, TabStopPosition, UnderlineType,
} = require("docx");

// ── BRD Template Definition ────────────────────────────────────────────────
// Exact structure from the user's template, in order.
const BRD_TEMPLATE = [
  {
    key: "executive_summary",
    number: "1",
    title: "Executive Summary",
    level: 1,
    stakeholders: ["Business Sponsor", "Product Owner"],
  },
  {
    key: "business_background",
    number: "2",
    title: "Business Background & Current State (As-Is)",
    level: 1,
    stakeholders: ["Business SMEs", "Process Analyst"],
  },
  {
    key: "business_objectives",
    number: "3",
    title: "Business Objectives & Success Criteria",
    level: 1,
    stakeholders: ["Sponsor", "Product Owner"],
  },
  {
    key: "scope_definition",
    number: "4",
    title: "Scope Definition",
    level: 1,
    stakeholders: ["Product Owner", "Business Analyst"],
  },
  {
    key: "in_scope",
    number: "4.1",
    title: "In Scope",
    level: 2,
    stakeholders: ["Business Analyst", "Product Owner"],
  },
  {
    key: "out_of_scope",
    number: "4.2",
    title: "Out of Scope",
    level: 2,
    stakeholders: ["Business Analyst", "Product Owner"],
  },
  {
    key: "future_state",
    number: "5",
    title: "Future State (To-Be Processes)",
    level: 1,
    stakeholders: ["Process Analyst", "Business SMEs"],
  },
  {
    key: "business_requirements",
    number: "6",
    title: "Business Requirements",
    level: 1,
    stakeholders: ["Business Analyst", "SMEs", "Product Owner"],
  },
  {
    key: "nfr",
    number: "7",
    title: "Non-Functional Requirements (NFRs)",
    level: 1,
    stakeholders: ["Solution Architect", "Tech Lead", "Security Officer", "QA Lead"],
  },
  {
    key: "nfr_performance",
    number: "7.1",
    title: "Performance",
    level: 2,
    stakeholders: ["Tech Lead", "QA Lead"],
  },
  {
    key: "nfr_scalability",
    number: "7.2",
    title: "Scalability",
    level: 2,
    stakeholders: ["Solution Architect", "Tech Lead"],
  },
  {
    key: "nfr_security",
    number: "7.3",
    title: "Security",
    level: 2,
    stakeholders: ["Security Architect / InfoSec"],
  },
  {
    key: "nfr_availability",
    number: "7.4",
    title: "Availability & Reliability",
    level: 2,
    stakeholders: ["Solution Architect", "Infrastructure/Cloud Team"],
  },
  {
    key: "nfr_usability",
    number: "7.5",
    title: "Usability",
    level: 2,
    stakeholders: ["UX/CX Team"],
  },
  {
    key: "nfr_data_quality",
    number: "7.6",
    title: "Data Quality & Integrity",
    level: 2,
    stakeholders: ["Data Architect"],
  },
  {
    key: "nfr_maintainability",
    number: "7.7",
    title: "Maintainability",
    level: 2,
    stakeholders: ["DevOps", "Operations"],
  },
  {
    key: "nfr_compliance",
    number: "7.8",
    title: "Compliance & Regulatory",
    level: 2,
    stakeholders: ["Compliance Officer", "Risk Officer"],
  },
  {
    key: "nfr_integration",
    number: "7.9",
    title: "Integration Requirements",
    level: 2,
    stakeholders: ["Solution Architect", "Integration Lead"],
  },
  {
    key: "nfr_disaster_recovery",
    number: "7.10",
    title: "Disaster Recovery",
    level: 2,
    stakeholders: ["Infrastructure/Cloud Team", "Solution Architect"],
  },
  {
    key: "assumptions_constraints",
    number: "8",
    title: "Assumptions & Constraints",
    level: 1,
    stakeholders: ["Project Manager", "Business Analyst"],
  },
  {
    key: "dependencies",
    number: "9",
    title: "Dependencies",
    level: 1,
    stakeholders: ["Project Manager", "Tech Lead"],
  },
  {
    key: "risks",
    number: "10",
    title: "Risks & Mitigation Plans",
    level: 1,
    stakeholders: ["Project Manager", "PMO", "BA"],
  },
  {
    key: "stakeholder_analysis",
    number: "11",
    title: "Stakeholder Analysis",
    level: 1,
    stakeholders: ["Project Manager", "Business Analyst"],
  },
  {
    key: "raci_matrix",
    number: "12",
    title: "RACI Matrix",
    level: 1,
    stakeholders: ["PMO", "Project Manager"],
  },
  {
    key: "glossary",
    number: "13",
    title: "Glossary & Definitions",
    level: 1,
    stakeholders: ["Business Analyst"],
  },
  {
    key: "appendices",
    number: "14",
    title: "Appendices",
    level: 1,
    stakeholders: ["Business Analyst"],
  },
];

// ── Colours & Fonts ────────────────────────────────────────────────────────
const NAVY       = "1F3864";   // heading / title colour
const DARK_BLUE  = "2E5FAC";   // section heading colour
const MID_BLUE   = "4472C4";   // sub-heading colour
const LIGHT_BLUE = "D6E4F7";   // header row fill
const AMBER_BG   = "FFF3CD";   // AI assumption callout background
const AMBER_TEXT = "856404";   // AI assumption text colour
const GREY_LINE  = "BFBFBF";   // table / divider colour
const FONT       = "Calibri";
const CONTENT_W  = 9360;       // US Letter 8.5" − 1.25" × 2 margins = 6.5" = 9360 DXA

// ── Border helpers ─────────────────────────────────────────────────────────
const borderNone = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const borderThin = { style: BorderStyle.SINGLE, size: 4, color: GREY_LINE };
const borderMed  = { style: BorderStyle.SINGLE, size: 8, color: DARK_BLUE };
const cellBorders = { top: borderThin, bottom: borderThin, left: borderThin, right: borderThin };
const noBorders   = { top: borderNone, bottom: borderNone, left: borderNone, right: borderNone };

// ── Paragraph helpers ──────────────────────────────────────────────────────
function spacer(lines = 1) {
  return Array.from({ length: lines }, () =>
    new Paragraph({ children: [new TextRun("")], spacing: { before: 0, after: 0 } })
  );
}

function hr() {
  return new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GREY_LINE, space: 1 } },
    spacing: { before: 80, after: 80 },
    children: [],
  });
}

/** Parse simple markdown-ish text into TextRun children.
 *  Supports: **bold**, *italic*, `code`, and plain text.
 *  Italic + disclaimer prefix for AI assumed text. */
function parseInline(text, forceItalic = false) {
  text = sanitise(text);
  const runs = [];
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) {
      runs.push(new TextRun({ text: text.slice(last, match.index), font: FONT, size: 22, italics: forceItalic }));
    }
    const raw = match[0];
    if (raw.startsWith("**")) {
      runs.push(new TextRun({ text: raw.slice(2, -2), bold: true, font: FONT, size: 22, italics: forceItalic }));
    } else if (raw.startsWith("*")) {
      runs.push(new TextRun({ text: raw.slice(1, -1), italics: true, font: FONT, size: 22 }));
    } else {
      runs.push(new TextRun({ text: raw.slice(1, -1), font: "Courier New", size: 20, italics: forceItalic }));
    }
    last = match.index + raw.length;
  }
  if (last < text.length) {
    runs.push(new TextRun({ text: text.slice(last), font: FONT, size: 22, italics: forceItalic }));
  }
  return runs.length ? runs : [new TextRun({ text, font: FONT, size: 22, italics: forceItalic })];
}

/** Convert markdown-ish content string into an array of Paragraph elements. */
function sanitise(str) {
  if (str === null || str === undefined) return "";
  // Strip XML-illegal control characters (keep \n, \t)
  return String(str).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "");
}

function contentToParagraphs(content, isAiAssumed, numbering) {
  content = sanitise(content);
  if (!content) return [new Paragraph({ children: [new TextRun("")] })];
  const paragraphs = [];
  const lines = content.split("\n");
  let inTable = false;
  let tableRows = [];

  function flushTable() {
    if (tableRows.length < 2) return; // need at least header + 1 data row
    const colCount = tableRows[0].length;
    const colW = Math.floor(CONTENT_W / colCount);
    const colWidths = Array(colCount).fill(colW);

    const rows = tableRows.map((cells, ri) => {
      const isHeader = ri === 0;
      return new TableRow({
        tableHeader: isHeader,
        children: cells.map((cell, ci) =>
          new TableCell({
            borders: cellBorders,
            width: { size: colWidths[ci], type: WidthType.DXA },
            shading: isHeader
              ? { fill: LIGHT_BLUE, type: ShadingType.CLEAR }
              : { fill: "FFFFFF", type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            verticalAlign: VerticalAlign.CENTER,
            children: [new Paragraph({
              children: [new TextRun({
                text: cell.trim(),
                bold: isHeader,
                font: FONT,
                size: 20,
              })],
            })],
          })
        ),
      });
    });

    paragraphs.push(
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: colWidths,
        rows,
      }),
      ...spacer(1)
    );
    tableRows = [];
    inTable = false;
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();

    // --- Markdown table rows (| col | col |)
    if (line.match(/^\s*\|/)) {
      if (!inTable) inTable = true;
      // Skip separator rows (|---|---|)
      if (line.match(/^\s*\|[\s\-|:]+\|\s*$/)) continue;
      const cells = line.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|");
      tableRows.push(cells);
      continue;
    } else if (inTable) {
      flushTable();
    }

    if (!line) {
      paragraphs.push(new Paragraph({ children: [new TextRun("")], spacing: { before: 60, after: 60 } }));
      continue;
    }

    // Heading 3
    if (line.startsWith("### ")) {
      paragraphs.push(new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun({ text: line.slice(4), font: FONT, size: 24, bold: true, color: MID_BLUE })],
        spacing: { before: 160, after: 80 },
      }));
      continue;
    }

    // Heading 2
    if (line.startsWith("## ")) {
      paragraphs.push(new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun({ text: line.slice(3), font: FONT, size: 26, bold: true, color: DARK_BLUE })],
        spacing: { before: 200, after: 100 },
      }));
      continue;
    }

    // Bullet list
    if (line.match(/^[-*]\s+/)) {
      paragraphs.push(new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: parseInline(line.replace(/^[-*]\s+/, "")),
        spacing: { before: 40, after: 40 },
      }));
      continue;
    }

    // Numbered list
    if (line.match(/^\d+\.\s/)) {
      paragraphs.push(new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: parseInline(line.replace(/^\d+\.\s/, "")),
        spacing: { before: 40, after: 40 },
      }));
      continue;
    }

    // Normal paragraph
    paragraphs.push(new Paragraph({
      children: parseInline(line),
      spacing: { before: 60, after: 60 },
    }));
  }

  if (inTable) flushTable();
  return paragraphs;
}

/** Amber disclaimer callout for AI-assumed sections. */
function aiDisclaimerParagraph() {
  return new Paragraph({
    border: {
      top:    { style: BorderStyle.SINGLE, size: 4, color: "FFC107", space: 4 },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "FFC107", space: 4 },
      left:   { style: BorderStyle.THICK,  size: 12, color: "FFC107", space: 4 },
      right:  { style: BorderStyle.NONE },
    },
    shading: { fill: AMBER_BG, type: ShadingType.CLEAR },
    spacing: { before: 80, after: 120 },
    indent: { left: 200, right: 200 },
    children: [
      new TextRun({ text: "⚠ AI-Generated Content — ", bold: true, italics: true, font: FONT, size: 20, color: AMBER_TEXT }),
      new TextRun({
        text: "The content in this section was generated based on AI assumptions as no source data was available. "
            + "Please review, validate, and update this section with accurate information before final sign-off.",
        italics: true, font: FONT, size: 20, color: AMBER_TEXT,
      }),
    ],
  });
}

/** Build the stakeholder tag line below a heading. */
function stakeholderTagLine(stakeholders, sessionStakeholders) {
  // Map template stakeholder role names → actual names if available
  const resolved = stakeholders.map((role) => {
    const match = sessionStakeholders.find(
      (s) => s.role && s.role.toLowerCase().includes(role.toLowerCase().split("/")[0].trim().toLowerCase())
    );
    return match ? `${match.name} (${role})` : role;
  });

  return new Paragraph({
    spacing: { before: 0, after: 120 },
    children: [
      new TextRun({ text: "Stakeholders: ", bold: true, italics: true, font: FONT, size: 18, color: "666666" }),
      new TextRun({ text: resolved.join(", "), italics: true, font: FONT, size: 18, color: "666666" }),
    ],
  });
}

// ── Cover Page ─────────────────────────────────────────────────────────────
function buildCoverPage(data) {
  return [
    ...spacer(4),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 240 },
      children: [new TextRun({ text: "BUSINESS REQUIREMENTS DOCUMENT", bold: true, font: FONT, size: 56, color: NAVY })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      border: { bottom: { style: BorderStyle.THICK, size: 12, color: DARK_BLUE, space: 4 } },
      spacing: { before: 0, after: 360 },
      children: [new TextRun({ text: "(BRD)", bold: true, font: FONT, size: 36, color: DARK_BLUE })],
    }),
    ...spacer(2),
    // Project name box
    new Table({
      width: { size: CONTENT_W, type: WidthType.DXA },
      columnWidths: [2400, CONTENT_W - 2400],
      rows: [
        tableMetaRow("Project Name", data.project_name || ""),
        tableMetaRow("Version",      data.version     || "1.0"),
        tableMetaRow("Date",         data.date        || new Date().toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" })),
        tableMetaRow("Prepared By",  data.prepared_by || "BRD Agent"),
        tableMetaRow("Status",       data.status      || "Draft"),
      ],
    }),
    ...spacer(2),
    new Paragraph({ pageBreakBefore: true, children: [new TextRun("")] }),
  ];
}

function tableMetaRow(label, value) {
  return new TableRow({
    children: [
      new TableCell({
        borders: cellBorders,
        width: { size: 2400, type: WidthType.DXA },
        shading: { fill: LIGHT_BLUE, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 160, right: 160 },
        children: [new Paragraph({ children: [new TextRun({ text: label, bold: true, font: FONT, size: 22 })] })],
      }),
      new TableCell({
        borders: cellBorders,
        width: { size: CONTENT_W - 2400, type: WidthType.DXA },
        shading: { fill: "FFFFFF", type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 160, right: 160 },
        children: [new Paragraph({ children: [new TextRun({ text: value, font: FONT, size: 22 })] })],
      }),
    ],
  });
}

// ── Stakeholder Summary Table ──────────────────────────────────────────────
function buildStakeholderTable(stakeholders) {
  if (!stakeholders || stakeholders.length === 0) return [];
  const colWidths = [2800, 3400, 3160];
  const headerRow = new TableRow({
    tableHeader: true,
    children: ["Name", "Role", "Email"].map((text, i) =>
      new TableCell({
        borders: cellBorders,
        width: { size: colWidths[i], type: WidthType.DXA },
        shading: { fill: LIGHT_BLUE, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text, bold: true, font: FONT, size: 22 })] })],
      })
    ),
  });
  const dataRows = stakeholders.map((s) =>
    new TableRow({
      children: [s.name || "", s.role || "", s.email || ""].map((val, i) =>
        new TableCell({
          borders: cellBorders,
          width: { size: colWidths[i], type: WidthType.DXA },
          shading: { fill: "FFFFFF", type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: val, font: FONT, size: 22 })] })],
        })
      ),
    })
  );

  return [
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      children: [new TextRun({ text: "Document Stakeholders", bold: true, font: FONT, size: 32, color: DARK_BLUE })],
      spacing: { before: 240, after: 160 },
    }),
    new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: colWidths, rows: [headerRow, ...dataRows] }),
    ...spacer(1),
    new Paragraph({ pageBreakBefore: true, children: [new TextRun("")] }),
  ];
}

// ── Section Builder ────────────────────────────────────────────────────────
function buildSection(templateDef, sectionData, sessionStakeholders, numbering) {
  const isAiAssumed = sectionData ? sectionData.is_ai_assumed === true : true;
  const content     = sectionData ? (sectionData.content || "") : "";
  const isMissing   = !sectionData || !content.trim();

  const headingLevel = templateDef.level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2;
  const headingSize  = templateDef.level === 1 ? 32 : 26;
  const headingColor = templateDef.level === 1 ? DARK_BLUE : MID_BLUE;
  const headingTitle = `${templateDef.number}. ${templateDef.title}`;

  const elements = [];

  // Section heading
  elements.push(new Paragraph({
    heading: headingLevel,
    children: [new TextRun({ text: headingTitle, bold: true, font: FONT, size: headingSize, color: headingColor })],
    spacing: { before: templateDef.level === 1 ? 360 : 200, after: 80 },
    ...(templateDef.level === 1 && templateDef.number !== "4.1" && templateDef.number !== "4.2"
      ? { pageBreakBefore: templateDef.number !== "1" && templateDef.number !== "4" }
      : {}),
  }));

  // Stakeholder tag line
  elements.push(stakeholderTagLine(templateDef.stakeholders, sessionStakeholders || []));

  // Thin separator
  elements.push(hr());

  // AI disclaimer only at top when section has NO content
  if (isMissing) {
    elements.push(aiDisclaimerParagraph());
  }

  // Content
  if (isMissing) {
    elements.push(new Paragraph({
      children: [new TextRun({
        text: `[No source data was provided for this section. AI-generated placeholder content will appear here upon BRD generation.]`,
        italics: true, font: FONT, size: 22, color: AMBER_TEXT,
      })],
    }));
  } else {
    elements.push(...contentToParagraphs(content, isAiAssumed, numbering));
    // Disclaimer at BOTTOM when content exists but is AI-assumed
    if (isAiAssumed) {
      elements.push(aiDisclaimerParagraph());
    }
  }

  elements.push(...spacer(1));
  return elements;
}

// ── Header / Footer ────────────────────────────────────────────────────────
function buildHeader(projectName) {
  return {
    default: new Header({
      children: [
        new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GREY_LINE, space: 4 } },
          tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
          children: [
            new TextRun({ text: "Business Requirements Document — ", font: FONT, size: 18, color: "666666" }),
            new TextRun({ text: projectName, bold: true, font: FONT, size: 18, color: "666666" }),
            new TextRun({ text: "\t", font: FONT, size: 18 }),
            new TextRun({ text: "CONFIDENTIAL", font: FONT, size: 18, color: "CC0000", bold: true }),
          ],
        }),
      ],
    }),
  };
}

function buildFooter() {
  return {
    default: new Footer({
      children: [
        new Paragraph({
          border: { top: { style: BorderStyle.SINGLE, size: 6, color: GREY_LINE, space: 4 } },
          tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
          children: [
            new TextRun({ text: "BRD Agent — AI-Assisted Document", font: FONT, size: 16, color: "999999" }),
            new TextRun({ text: "\tPage ", font: FONT, size: 16, color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "999999" }),
          ],
        }),
      ],
    }),
  };
}

// ── Main ───────────────────────────────────────────────────────────────────
async function main() {
  const [,, inputPath, outputPath] = process.argv;
  if (!inputPath || !outputPath) {
    console.error("Usage: node generate_brd_docx.js <input.json> <output.docx>");
    process.exit(1);
  }

  let data;
  try {
    const raw = fs.readFileSync(inputPath, "utf8");
    data = JSON.parse(raw);
  } catch (parseErr) {
    console.error("Failed to parse input JSON:", parseErr.message);
    process.exit(1);
  }
  const sections        = data.sections || {};
  const sessionStakeholders = data.stakeholders || [];

  const numbering = {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
      {
        reference: "numbers",
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
    ],
  };

  // Build all document children
  const children = [
    ...buildCoverPage(data),
    ...buildStakeholderTable(sessionStakeholders),
  ];

  for (const tmpl of BRD_TEMPLATE) {
    const sectionData = sections[tmpl.key];
    children.push(...buildSection(tmpl, sectionData, sessionStakeholders, numbering));
  }

  const doc = new Document({
    numbering,
    styles: {
      default: {
        document: { run: { font: FONT, size: 22 } },
      },
      paragraphStyles: [
        {
          id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run:       { size: 32, bold: true, font: FONT, color: DARK_BLUE },
          paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 },
        },
        {
          id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run:       { size: 26, bold: true, font: FONT, color: MID_BLUE },
          paragraph: { spacing: { before: 240, after: 80 }, outlineLevel: 1 },
        },
        {
          id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run:       { size: 24, bold: true, font: FONT, color: MID_BLUE },
          paragraph: { spacing: { before: 160, after: 60 }, outlineLevel: 2 },
        },
      ],
    },
    sections: [{
      properties: {
        page: {
          size:   { width: 12240, height: 15840 },
          margin: { top: 1008, bottom: 1008, left: 1260, right: 1260 },
        },
      },
      headers: buildHeader(data.project_name || ""),
      footers: buildFooter(),
      children,
    }],
  });

  let buffer;
  try {
    buffer = await Packer.toBuffer(doc);
  } catch (packErr) {
    console.error("Packer.toBuffer failed:", packErr);
    process.exit(1);
  }

  if (!buffer || buffer.length < 1000) {
    console.error(`Generated buffer is too small (${buffer ? buffer.length : 0} bytes) — document is likely corrupt.`);
    process.exit(1);
  }

  fs.writeFileSync(outputPath, buffer);

  // Verify the written file is a valid ZIP (docx must start with PK\x03\x04)
  const written = fs.readFileSync(outputPath);
  if (written[0] !== 0x50 || written[1] !== 0x4B) {
    fs.unlinkSync(outputPath);
    console.error("Written file is not a valid ZIP/docx — deleted.");
    process.exit(1);
  }

  console.log(`BRD written to: ${outputPath} (${buffer.length} bytes)`);
}

main().catch((err) => { console.error("Fatal error in main():", err.stack || err); process.exit(1); });