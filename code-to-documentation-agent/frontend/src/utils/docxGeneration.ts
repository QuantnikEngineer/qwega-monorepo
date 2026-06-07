import { Document, Paragraph, TextRun, Packer } from 'docx';
import { saveAs } from 'file-saver';


export const generateTestScriptsDocx = async (content: string, filename = "Functional_TestScripts.docx", returnBlob?: boolean): Promise<Blob | void> => {
  try {
    // Clean the content to extract test scripts
    const cleanedContent = extractTestScriptsContent(content);
    
    // Split content into lines for better formatting
    const lines = cleanedContent.split('\n').filter(line => line.trim());

    // Create paragraphs for each line with better formatting
    const paragraphs = [];
    
    // Add title
    paragraphs.push(
      new Paragraph({
        children: [
          new TextRun({
            text: 'AUTOMATED TEST SCRIPTS',
            bold: true,
            size: 32,
          })
        ],
        spacing: { after: 400 }
      })
    );
    
    // Add subtitle
    paragraphs.push(
      new Paragraph({
        children: [
          new TextRun({
            text: 'Generated Test Automation Scripts',
            size: 24,
          })
        ],
        spacing: { after: 400 }
      })
    );

    // Process content lines
    lines.forEach(line => {
      const trimmedLine = line.trim();
      if (trimmedLine) {
        let fontSize = 24; // Default size (12pt = 24 half-points)
        let isBold = false;
        let spacingAfter = 200;
        let isCodeLine = false;

        // Format different types of content
        if (/^(Epic Title|Test Script ID|TC-|TS-)/i.test(trimmedLine)) {
          fontSize = 28;
          isBold = true;
          spacingAfter = 300;
        } else if (/^(Test Script Name|Test Script)/i.test(trimmedLine)) {
          fontSize = 26;
          isBold = true;
          spacingAfter = 250;
        } else if (/^(Given|When|Then|And):/i.test(trimmedLine)) {
          fontSize = 24;
          isBold = true;
          spacingAfter = 150;
        } else if (/^\d+\.\s/.test(trimmedLine)) {
          fontSize = 22;
          spacingAfter = 100;
        } else if (trimmedLine.startsWith('```') || trimmedLine.includes('import ') || trimmedLine.includes('public class') || trimmedLine.includes('@Test')) {
          // Code blocks or Java code
          fontSize = 20;
          isCodeLine = true;
          spacingAfter = 50;
        } else if (trimmedLine.startsWith('//') || trimmedLine.startsWith('/*') || trimmedLine.includes('Step ')) {
          // Comments or step descriptions
          fontSize = 22;
          isBold = false;
          spacingAfter = 100;
        }

        paragraphs.push(
          new Paragraph({
            children: [
              new TextRun({
                text: trimmedLine,
                bold: isBold,
                size: fontSize,
                font: isCodeLine ? 'Courier New' : 'Calibri',
              })
            ],
            spacing: { after: spacingAfter }
          })
        );
      }
    });

    // Create the DOCX document
    const doc = new Document({
      sections: [{
        children: paragraphs
      }]
    });

    if (returnBlob) {
      // Use blob generation for browser compatibility
      const blob = await Packer.toBlob(doc);
      return blob;
    } else {
      // Save the file using file-saver for download
      const blob = await Packer.toBlob(doc);
      saveAs(blob, filename.endsWith('.docx') ? filename : filename + '.docx');
    }
  } catch (error) {
    console.error('Error generating DOCX:', error);
    
    if (returnBlob) {
      // Fallback: create a simple text blob
      const cleanedContent = extractTestScriptsContent(content);
      return new Blob([cleanedContent], { 
        type: 'text/plain' 
      });
    } else {
      // Fallback: download as text file
      const cleanedContent = extractTestScriptsContent(content);
      const blob = new Blob([cleanedContent], { type: 'text/plain' });
      saveAs(blob, filename.replace('.docx', '.txt'));
    }
  }
};

// Utility function to clean content for any document type
export const cleanDocumentContent = (content: string, contentType: string): string => {
  
      return extractTestScriptsContent(content);
    
};

// Extract test scripts content
const extractTestScriptsContent = (content: string): string => {
  let cleanContent = content;
  
  // Clean up the content - remove any remaining prefixes
  cleanContent = cleanContent
    .replace(/^[\s\S]*?(?=\*\*Epic Title\*\*|\*\*Test Script ID\*\*|\*\*Test Case Name\*\*|Test Script ID|Epic Title)/i, '')
    .replace(/^.*?Test Script.*?:/gm, 'Test Script:')
    .trim();
  
  return cleanContent;
};