import { Document, Paragraph, TextRun, AlignmentType, Packer } from 'docx';
import { saveAs } from 'file-saver';

// Document generation options interface
export interface DocumentGenerationOptions {
  contentType: 'case' | 'scenario' | 'scripts';
  format: 'docx' | 'html' | 'markdown';
  includeMetadata: boolean;
  styling: 'professional' | 'minimal' | 'detailed';
}

// MIME type mapping
export const getMimeType = (format: string): string => {
  const mimeTypes: { [key: string]: string } = {
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'pdf': 'application/pdf',
    'html': 'text/html',
    'markdown': 'text/markdown',
    'rtf': 'application/rtf',
    'txt': 'text/plain'
  };
  return mimeTypes[format] || 'text/plain';
};

// Generate filename based on content type with specific naming convention
export const getDocumentFilename = (contentType: string, format: string): string => {
  const fileNameMapping: { [key: string]: string } = {
    'scripts': 'FunctionalTest_scripts',
    'script': 'FunctionalTest_scripts',
    'scenario': 'FunctionalTest_scenarios',
    'scenarios': 'FunctionalTest_scenarios',
    'case': 'FunctionalTest_test_cases',
    'cases': 'FunctionalTest_test_cases'
  };
  console.log('Generating filename for contentType:', contentType, 'and format:', format);
  const baseName = fileNameMapping[contentType] || `FunctionalTest_${contentType}`;
  return `${baseName}.${format}`;
};

// Professional document templates
export const getDocumentTemplate = (contentType: string) => {
  const templates = {
    'scripts': {
      title: 'AUTOMATED TEST SCRIPTS',
      subtitle: 'Executable Test Automation Scripts',
      sections: ['Script Name', 'Framework', 'Test Steps', 'Assertions', 'Test Data'],
      styling: 'technical'
    },
    'script': {
      title: 'AUTOMATED TEST SCRIPTS',
      subtitle: 'Executable Test Automation Scripts',
      sections: ['Script Name', 'Framework', 'Test Steps', 'Assertions', 'Test Data'],
      styling: 'technical'
    },
    'case': {
      title: 'FUNCTIONAL TEST CASES',
      subtitle: 'Comprehensive Test Case Documentation',
      sections: ['Test Case ID', 'Description', 'Preconditions', 'Test Steps', 'Expected Results', 'Priority'],
      styling: 'detailed'
    },
    'cases': {
      title: 'FUNCTIONAL TEST CASES',
      subtitle: 'Comprehensive Test Case Documentation',
      sections: ['Test Case ID', 'Description', 'Preconditions', 'Test Steps', 'Expected Results', 'Priority'],
      styling: 'detailed'
    },
    'scenario': {
      title: 'FUNCTIONAL TEST SCENARIOS',
      subtitle: 'Business Process Test Scenarios',
      sections: ['Scenario ID', 'Description', 'Given/When/Then', 'Acceptance Criteria'],
      styling: 'professional'
    },
    'scenarios': {
      title: 'FUNCTIONAL TEST SCENARIOS',
      subtitle: 'Business Process Test Scenarios',
      sections: ['Scenario ID', 'Description', 'Given/When/Then', 'Acceptance Criteria'],
      styling: 'professional'
    },
  };
  
  return templates[contentType as keyof typeof templates] || templates['case'];
};

// Enhanced content cleaning - inspired by document_storage.py
export const cleanTestContent = (content: string, contentType: string): string => {
  if (!content) return content;

  let cleanContent = content;

  // Remove conversational phrases at the beginning (from document_storage.py pattern)
  const conversationalPhrases = [
    /^I'll help you.*?\./gi,
    /^Here are.*?:/gi,
    /^Based on.*?:/gi,
    /^I've generated.*?:/gi,
    /^Below are.*?:/gi,
    /^I've created.*?:/gi,
    /^These.*?cover.*?\./gi,
    /^Let me.*?\./gi,
    /^I can.*?\./gi,
    /^Here's.*?:/gi,
    /^The following.*?:/gi,
    /^I have.*?:/gi,
    /^Please find.*?:/gi,
    /^I will.*?\./gi,
    /^This.*?includes.*?\./gi,
    /^Note:.*?\./gi,
    /^Sure.*?\./gi,
    /^Certainly.*?\./gi,
    /^Of course.*?\./gi,
    /^Absolutely.*?\./gi,
  ];
  
  conversationalPhrases.forEach(phrase => {
    cleanContent = cleanContent.replace(phrase, '');
  });

  // Remove trailing instructional content (from document_storage.py pattern)
  const trailingPhrases = [
    /These test.*?ensure.*?\./gi,
    /This covers.*?\./gi,
    /Please review.*?\./gi,
    /Let me know.*?\./gi,
    /If you need.*?\./gi,
    /Feel free.*?\./gi,
    /This script includes.*?\./gi,
    /Customize the selectors.*?\./gi,
    /Remember to.*?\./gi,
    /Make sure to.*?\./gi,
  ];
  
  trailingPhrases.forEach(phrase => {
    cleanContent = cleanContent.replace(phrase, '');
  });

  // Clean up extra whitespace and empty lines while preserving structure
  cleanContent = cleanContent
    .replace(/\n\s*\n\s*\n/g, '\n\n') // Reduce multiple empty lines to double
    .replace(/^\s+|\s+$/g, '') // Trim start and end
    .replace(/[ \t]+/g, ' ') // Replace multiple spaces/tabs with single space
    .replace(/\n[ \t]+/g, '\n') // Remove leading spaces on lines
    .replace(/[ \t]+\n/g, '\n'); // Remove trailing spaces on lines

  return cleanContent.trim();
};

// Parse test content into structured sections - Enhanced for agent responses
export const parseTestContent = (content: string, contentType: string) => {
  const lines = content.split('\n').map(line => line.trim()).filter(line => line);
  const sections: { [key: string]: string[] } = {};
  let currentSection = 'general';
  let currentTestCase: { [key: string]: string } = {};
  const testCases: Array<{ [key: string]: string }> = [];

  lines.forEach(line => {
    // Clean up markdown formatting for processing
    const cleanLine = line.replace(/\*\*/g, '').replace(/^-\s*/, '');
    
    // Detect test case/scenario headers with markdown formatting
    if (contentType === 'case' && /^-?\s*\*?\*?(Test Case|TC)-?\s*\d+/i.test(line)) {
      if (Object.keys(currentTestCase).length > 0) {
        testCases.push({ ...currentTestCase });
      }
      currentTestCase = { title: cleanLine };
      currentSection = 'title';
    } else if (contentType === 'scenario' && /^-?\s*\*?\*?(Test Scenario|Scenario|SC)-?\s*\d+/i.test(line)) {
      if (Object.keys(currentTestCase).length > 0) {
        testCases.push({ ...currentTestCase });
      }
      currentTestCase = { title: cleanLine };
      currentSection = 'title';
    } else if (contentType === 'scripts' && /^-?\s*\*?\*?(Test Script|Script)-?\s*\d+/i.test(line)) {
      if (Object.keys(currentTestCase).length > 0) {
        testCases.push({ ...currentTestCase });
      }
      currentTestCase = { title: cleanLine };
      currentSection = 'title';
    }
    // Detect section headers with markdown formatting (agent response format)
    else if (/^-?\s*\*\*(Test Case ID|Test Case Name|Test Case Description|Description|Test Description|Scenario Description)\*\*:/i.test(line)) {
      currentSection = 'description';
      const content = line.replace(/^-?\s*\*\*[^:]+\*\*:\s*/i, '');
      currentTestCase[currentSection] = content;
    } else if (/^-?\s*\*\*(Expected Result|Expected|Result|Expected Results)\*\*:/i.test(line)) {
      currentSection = 'expected';
      const content = line.replace(/^-?\s*\*\*[^:]+\*\*:\s*/i, '');
      currentTestCase[currentSection] = content;
    } else if (/^-?\s*\*\*(Steps|Test Steps|Execution Steps)\*\*:/i.test(line)) {
      currentSection = 'steps';
      const content = line.replace(/^-?\s*\*\*[^:]+\*\*:\s*/i, '');
      currentTestCase[currentSection] = content;
    } else if (/^-?\s*\*\*(Precondition|Prerequisites|Setup)\*\*:/i.test(line)) {
      currentSection = 'precondition';
      const content = line.replace(/^-?\s*\*\*[^:]+\*\*:\s*/i, '');
      currentTestCase[currentSection] = content;
    } else if (/^-?\s*\*\*(Priority|Test Priority)\*\*:/i.test(line)) {
      currentSection = 'priority';
      const content = line.replace(/^-?\s*\*\*[^:]+\*\*:\s*/i, '');
      currentTestCase[currentSection] = content;
    } else if (/^-?\s*\*\*(Given|When|Then)\*\*:/i.test(line)) {
      const sectionName = line.toLowerCase().match(/\*\*(given|when|then)\*\*/i)?.[1] || 'given';
      currentSection = sectionName;
      const content = line.replace(/^-?\s*\*\*[^:]+\*\*:\s*/i, '');
      currentTestCase[currentSection] = content;
    } 
    // Handle legacy format without markdown
    else if (/^(Description|Test Description|Scenario Description):/i.test(line)) {
      currentSection = 'description';
      currentTestCase[currentSection] = line.replace(/^[^:]+:\s*/i, '');
    } else if (/^(Expected Result|Expected|Result):/i.test(line)) {
      currentSection = 'expected';
      currentTestCase[currentSection] = line.replace(/^[^:]+:\s*/i, '');
    } else if (/^(Steps|Test Steps|Execution Steps):/i.test(line)) {
      currentSection = 'steps';
      currentTestCase[currentSection] = line.replace(/^[^:]+:\s*/i, '');
    } else if (/^(Precondition|Prerequisites|Setup):/i.test(line)) {
      currentSection = 'precondition';
      currentTestCase[currentSection] = line.replace(/^[^:]+:\s*/i, '');
    } else if (/^(Priority|Test Priority):/i.test(line)) {
      currentSection = 'priority';
      currentTestCase[currentSection] = line.replace(/^[^:]+:\s*/i, '');
    } else if (/^(Given|When|Then):/i.test(line)) {
      const sectionName = line.toLowerCase().split(':')[0];
      currentSection = sectionName;
      currentTestCase[currentSection] = line.replace(/^[^:]+:\s*/i, '');
    } else {
      // Continue current section, handling numbered lists and bullet points
      const cleanedLine = line.replace(/^-\s*/, '').replace(/\*\*/g, '');
      if (currentTestCase[currentSection]) {
        currentTestCase[currentSection] += '\n' + cleanedLine;
      } else {
        currentTestCase[currentSection] = cleanedLine;
      }
    }
  });

  // Add the last test case
  if (Object.keys(currentTestCase).length > 0) {
    testCases.push(currentTestCase);
  }

  return { sections, testCases };
};

// Create professional DOCX document with simpler approach for better compatibility
export const createProfessionalDocument = async (
  content: string,
  options: DocumentGenerationOptions
): Promise<void> => {
  try {
    const template = getDocumentTemplate(options.contentType);
    const cleanedContent = cleanTestContent(content, options.contentType);
    
    // Create a simpler document structure for better Word compatibility
    const children: Paragraph[] = [];
    
    // Add title
    children.push(
      new Paragraph({
        children: [
          new TextRun({
            text: template.title,
            bold: true,
            size: 16,
          })
        ],
        alignment: AlignmentType.CENTER,
        spacing: { after: 400 }
      })
    );
    
    // Add subtitle
    children.push(
      new Paragraph({
        children: [
          new TextRun({
            text: template.subtitle,
            size: 12,
          })
        ],
        alignment: AlignmentType.CENTER,
        spacing: { after: 400 }
      })
    );
    
    // // Add metadata if enabled
    // if (options.includeMetadata) {
    //   children.push(
    //     new Paragraph({
    //       children: [
    //         new TextRun({
    //           text: `Generated: ${new Date().toLocaleDateString()}`,
    //           size: 12,
    //         })
    //       ],
    //       spacing: { after: 300 }
    //     })
    //   );
    // }
    
    // Add content with proper parsing and formatting
    const lines = cleanedContent.split('\n').filter(line => line.trim());
    
    lines.forEach(line => {
      const trimmedLine = line.trim();
      if (trimmedLine) {
        // Check for different types of content and apply appropriate formatting
        let fontSize = 12; // Default content size
        let isBold = false;
        let spacingBefore = 200;
        let spacingAfter = 100;
        let textColor = '000000'; // Default black color
        
        // Main headings (Test Case ID, Test Case Name, etc.) - Largest
        if (/^-\s*\*\*(Test Case|Test Scenario|Test Script|Scenario)\s*(ID|Name|Description|Steps|Results?)?\*\*:/i.test(trimmedLine)) {
          fontSize = 16;
          isBold = true;
          spacingBefore = 400;
          spacingAfter = 200;
          textColor = '2c5aa0'; // Blue
        }
        // Sub-headings and section headers - Large
        else if (/^(Test Case|Test Scenario|Test Script|\*\*Expected Results?\*\*:|\*\*Test Steps\*\*:)/i.test(trimmedLine)) {
          fontSize = 14;
          isBold = true;
          spacingBefore = 350;
          spacingAfter = 150;
          textColor = '2c5aa0'; // Blue
        }
        // Test case identifiers (TC-001, etc.) - Medium-large, BLACK
        else if (/^(TC-|TS-|SC-)\d+/i.test(trimmedLine)) {
          fontSize = 14;
          isBold = true;
          spacingBefore = 300;
          spacingAfter = 150;
          textColor = '000000'; // Black
        }
        // Numbered steps - Medium
        else if (/^\s*\d+\.\s/.test(trimmedLine)) {
          fontSize = 12;
          isBold = false;
          spacingBefore = 150;
          spacingAfter = 100;
          textColor = '000000'; // Black
        }
        // Bullet points - Regular
        else if (/^[-•]\s/.test(trimmedLine)) {
          fontSize = 12;
          isBold = false;
          spacingBefore = 100;
          spacingAfter = 50;
          textColor = '000000'; // Black
        }
        // Regular content - Smallest
        else {
          fontSize = 12;
          isBold = false;
          spacingBefore = 100;
          spacingAfter = 50;
          textColor = '000000'; // Black
        }
        
        // Clean up markdown formatting
        let cleanText = trimmedLine
          .replace(/^-\s*\*\*(.*?)\*\*:/g, '$1:') // Remove markdown bold from headings
          .replace(/\*\*(.*?)\*\*/g, '$1') // Remove all markdown bold
          .replace(/^\s*-\s*/, ''); // Remove leading dashes
        
        children.push(
          new Paragraph({
            children: [
              new TextRun({
                text: cleanText,
                bold: isBold,
                size: fontSize,
                color: textColor,
              })
            ],
            spacing: { 
              before: spacingBefore, 
              after: spacingAfter 
            }
          })
        );
      }
    });
    
    // Create simple document
    const doc = new Document({
      sections: [{
        children: children
      }]
    });

    // Generate document
    const buffer = await Packer.toBuffer(doc);
    
    // Create blob with proper array buffer conversion
    const uint8Array = new Uint8Array(buffer);
    const blob = new Blob([uint8Array], { 
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    });
    
    const filename = getDocumentFilename(options.contentType, 'docx');
    
    saveAs(blob, filename);
    
  } catch (error) {
    console.error('Error generating DOCX:', error);
    // Fallback to HTML if DOCX generation fails
    alert('DOCX generation failed. Downloading as HTML instead.');
    downloadHTMLDocument(content, options);
  }
};

// Enhanced HTML generation
export const createHTMLDocument = (content: string, options: DocumentGenerationOptions): string => {
  const template = getDocumentTemplate(options.contentType);
  const cleanedContent = cleanTestContent(content, options.contentType);
  const parsedContent = parseTestContent(cleanedContent, options.contentType);
  
  const css = `
    <style>
      body { 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
        max-width: 800px; 
        margin: 0 auto; 
        padding: 20px; 
        line-height: 1.6;
        font-size: 14px;
      }
      .header { 
        text-align: center; 
        border-bottom: 2px solid #333; 
        padding-bottom: 20px; 
        margin-bottom: 30px;
      }
      .title { 
        font-size: 20px; 
        font-weight: bold; 
        color: #2c5aa0; 
        margin-bottom: 10px;
      }
      .subtitle { 
        font-size: 14px; 
        color: #666; 
      }
      .test-case { 
        border: 1px solid #ddd; 
        border-radius: 8px; 
        padding: 20px; 
        margin-bottom: 20px; 
        background: #f9f9f9;
      }
      .test-title { 
        font-size: 22px; 
        font-weight: bold; 
        color: #333; 
        margin-bottom: 15px;
      }
      .test-identifier {
        font-size: 22px;
        font-weight: bold;
        color: #333;
        margin: 15px 0 10px 0;
      }
      .main-heading {
        font-size: 26px;
        font-weight: bold;
        color: #2c5aa0;
        margin: 15px 0 10px 0;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 5px;
      }
      .sub-heading {
        font-size: 24px;
        font-weight: bold;
        color: #2c5aa0;
        margin: 12px 0 8px 0;
      }
      .section { 
        margin-bottom: 12px;
        font-size: 20px;
        line-height: 1.5;
      }
      .section-label { 
        font-weight: bold; 
        color: #2c5aa0;
        font-size: 24px;
      }
      .content-text {
        font-size: 20px;
        color: #4a5568;
        margin: 5px 0;
      }
      .step-item {
        font-size: 20px;
        margin: 5px 0;
        padding-left: 10px;
        color: #4a5568;
      }
      .metadata { 
        background: #f0f0f0; 
        padding: 15px; 
        border-radius: 5px; 
        margin-bottom: 20px;
        font-size: 20px;
      }
    </style>
  `;

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>${template.title}</title>
      ${css}
    </head>
    <body>
      <div class="header">
        <div class="title">${template.title}</div>
        <div class="subtitle">${template.subtitle}</div>
      </div>
      
    //   ${options.includeMetadata ? `
    //     <div class="metadata">
    //       <strong>Generated Date:</strong> ${new Date().toLocaleDateString()}<br>
    //       <strong>Document Type:</strong> ${template.title}
    //     </div>
    //   ` : ''}
      
      ${parsedContent.testCases.map((testCase, index) => `
        <div class="test-case">
          <div class="test-title">${testCase.title || `${options.contentType.toUpperCase()} ${index + 1}`}</div>
          ${Object.entries(testCase)
            .filter(([key]) => key !== 'title')
            .map(([key, value]) => {
              const formattedValue = value.split('\n').map(line => {
                const trimmedLine = line.trim();
                if (!trimmedLine) return '';
                
                if (/^\d+\.\s/.test(trimmedLine)) {
                  return `<div class="step-item">${trimmedLine}</div>`;
                } else if (/^[-•]\s/.test(trimmedLine)) {
                  return `<div class="step-item">${trimmedLine}</div>`;
                } else {
                  return `<div class="content-text">${trimmedLine}</div>`;
                }
              }).join('');
              
              return `
                <div class="section">
                  <div class="section-label">${key.charAt(0).toUpperCase() + key.slice(1)}:</div>
                  ${formattedValue || `<div class="content-text">${value}</div>`}
                </div>
              `;
            }).join('')}
        </div>
      `).join('')}
    </body>
    </html>
  `;

  return html;
};

// Download HTML document
export const downloadHTMLDocument = (content: string, options: DocumentGenerationOptions): void => {
  const htmlContent = createHTMLDocument(content, options);
  const blob = new Blob([htmlContent], { type: getMimeType('html') });
  const filename = getDocumentFilename(options.contentType, 'html');
  console.log('Downloading HTML document:', filename);
  saveAs(blob, filename);
};

// Enhanced RTF generation as fallback for Word compatibility
export const createWordCompatibleDocument = (content: string, options: DocumentGenerationOptions, returnBlob?: boolean): Blob | void => {
  const template = getDocumentTemplate(options.contentType);
  console.log('Creating Word-compatible document for:', options.contentType);
  console.log('template:', template);
  const cleanedContent = cleanTestContent(content, options.contentType);
  
  // Create RTF with enhanced formatting and color support
  let rtf = '{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0\\froman Times New Roman;}{\\f1\\fswiss Arial;}{\\f2\\fswiss Calibri;}}';
  
  // Add color table: Black, Blue, Dark Blue, Gray
  rtf += '{\\colortbl;\\red0\\green0\\blue0;\\red0\\green100\\blue200;\\red0\\green70\\blue150;\\red80\\green80\\blue80;}';
  
  // Add main title - medium, bold, blue, centered
  rtf += '\\pard\\qc\\f2\\fs20\\b\\cf2 ' + template.title + '\\cf1\\b0\\par\\par';
  
  // Add subtitle - small, bold, gray, centered
  rtf += '\\pard\\qc\\f2\\fs20\\b\\cf4 ' + template.subtitle + '\\cf1\\b0\\par\\par';
  
 
  
  // Process content
  const lines = cleanedContent.split('\n').filter(line => line.trim());
  
  lines.forEach(line => {
    const trimmedLine = line.trim();
    if (trimmedLine) {
      // Clean up markdown formatting
      let cleanText = trimmedLine
        .replace(/^-\s*\*\*(.*?)\*\*:/g, '$1:') // Remove markdown bold from headings
        .replace(/\*\*(.*?)\*\*/g, '$1') // Remove all markdown bold
        .replace(/^\s*-\s*/, ''); // Remove leading dashes
      
      // Main section headers (Test Case ID, Test Case Name, etc.) - 24pt Blue, bold
      if (/^(Test Case ID|Test Case Name|Test Case Description|Test Steps|Expected Results?):/i.test(cleanText)) {
        rtf += '\\pard\\ql\\f2\\fs28\\b\\cf1 ' + cleanText.replace(/[{}\\]/g, '\\$&') + '\\cf1\\b0\\par\\par';
      }
      // Sub-headers (Expected Results, Test Steps without markdown) - 26pt Blue, bold
      else if (/^(Expected Results|Test Steps|Given|When|Then):/i.test(cleanText)) {
        rtf += '\\pard\\ql\\f2\\fs26\\b\\cf1 ' + cleanText.replace(/[{}\\]/g, '\\$&') + '\\cf1\\b0\\par\\par';
        // '\\cf1\\b0\\par\\par'
      }
      // Test identifiers - 24pt BLACK, bold 
      else if (/^(TC-|TS-|SC-)/i.test(cleanText)) {
        rtf += '\\pard\\ql\\f2\\fs20\\b\\cf1 ' + cleanText.replace(/[{}\\]/g, '\\$&') +'\\cf1\\b0\\par\\par';
      }
      // Numbered steps - 20pt BLACK
      else if (/^\d+\.\s/.test(cleanText)) {
        rtf += '\\pard\\ql\\f1\\fs20 ' + cleanText.replace(/[{}\\]/g, '\\$&') + '\\par';
      }
      // Bullet points - 20pt BLACK, indented
      else if (/^[-•]\s/.test(cleanText)) {
        rtf += '\\pard\\li720\\ql\\f1\\fs20 ' + cleanText.replace(/[{}\\]/g, '\\$&') + '\\par';
      }
      // Regular content - 20pt BLACK
      else {
        rtf += '\\pard\\ql\\f1\\fs20 ' + cleanText.replace(/[{}\\]/g, '\\$&') + '\\par';
      }
    } else {
      // Empty line
      rtf += '\\par';
    }
  });
  
  rtf += '}';
  
  // Create blob
  const blob = new Blob([rtf], { type: 'application/msword' });
  
  if (returnBlob) {
    return blob;
  } else {
    // Download as RTF with .doc extension for Word compatibility
    const filename = getDocumentFilename(options.contentType, 'doc');
    console.log('Downloading Word-compatible document:', filename);
    saveAs(blob, filename);
  }
};

// Download Markdown document
export const downloadMarkdownDocument = (content: string, options: DocumentGenerationOptions): void => {
  const template = getDocumentTemplate(options.contentType);
  const cleanedContent = cleanTestContent(content, options.contentType);
  const parsedContent = parseTestContent(cleanedContent, options.contentType);
  
  let markdown = `# ${template.title}\n\n`;
  markdown += `*${template.subtitle}*\n\n`;
  
  if (options.includeMetadata) {
    markdown += `## Document Information\n\n`;
    markdown += `- **Generated Date:** ${new Date().toLocaleDateString()}\n`;
    markdown += `- **Document Type:** ${template.title}\n\n`;
  }
  
  parsedContent.testCases.forEach((testCase, index) => {
    markdown += `## ${testCase.title || `${options.contentType.toUpperCase()} ${index + 1}`}\n\n`;
    
    Object.entries(testCase)
      .filter(([key]) => key !== 'title')
      .forEach(([key, value]) => {
        markdown += `**${key.charAt(0).toUpperCase() + key.slice(1)}:** ${value}\n\n`;
      });
  });
  
  const blob = new Blob([markdown], { type: getMimeType('markdown') });
  const filename = getDocumentFilename(options.contentType, 'md');
  saveAs(blob, filename);
};