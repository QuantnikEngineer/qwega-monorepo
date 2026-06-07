import * as XLSX from "xlsx";

// Interfaces for Excel generation
export interface TestCase {
  testCaseId: string;
  title: string;
  description: string;
  steps: string[];
  expectedResult: string;
  priority: string;
}

export interface TestScenario {
  testScenarioId: string;
  title: string;
  description: string;
  expectedResults: string;
  priority: string;
  preCondition?: string;
}

export interface FilterOptions {
  priority: string;
}

// Excel generation for Test Cases
export const generateTestCasesExcel = (
  content: string,
  filename: string,
  filterOptions?: FilterOptions,
  returnBlob?: boolean
): Blob | void => {
  const defaultFilters: FilterOptions = { priority: 'all' };
  const filters = filterOptions || defaultFilters;
  const testCases: TestCase[] = [];
  
  // Split by test case sections - handle multiple formats
  const sections = content.split(/(?=\*\*Test Case ID\*\*)|(?=Test Case ID:)/);
  
  console.log('Content sections found:', sections.length);
  
  sections.forEach((section, index) => {
    if (section.trim() && (section.includes('TC-') || section.includes('Test Case'))) {
      console.log(`Processing section ${index}:`, section.substring(0, 200));
      
      const lines = section.split('\n');
      let testCase: Partial<TestCase> = { steps: [] };
      let collectingSteps = false;
      let collectingExpectedResults = false;
      let expectedResultLines: string[] = [];
      
      lines.forEach(line => {
        const trimmed = line.trim();
        
        // Extract Test Case ID
        if (trimmed.includes('**Test Case ID**:') || trimmed.includes('Test Case ID:')) {
          const match = trimmed.match(/TC-[\w-]+\d+/);
          if (match) {
            testCase.testCaseId = match[0];
            console.log('Found Test Case ID:', testCase.testCaseId);
          }
        }
        
        // Extract Test Case Name/Title
        if (trimmed.includes('**Test Case Name**:') || trimmed.includes('Test Case Name:')) {
          testCase.title = trimmed.replace(/.*?\*?\*?Test Case Name\*?\*?:\s*/, '').trim();
          console.log('Found Test Case Name:', testCase.title);
        }
        
        // Extract Test Case Description
        if (trimmed.includes('**Test Case Description**:') || trimmed.includes('Test Case Description:')) {
          testCase.description = trimmed.replace(/.*?\*?\*?Test Case Description\*?\*?:\s*/, '').trim();
          console.log('Found Test Case Description:', testCase.description);
        }
        
        // Detect Test Steps section
        if (trimmed.includes('**Test Steps**:') || trimmed.includes('Test Steps:')) {
          collectingSteps = true;
          collectingExpectedResults = false;
          testCase.steps = [];
          console.log('Started collecting test steps');
        }
        
        // Detect Expected Results section
        if (trimmed.includes('**Expected Results**:') || trimmed.includes('Expected Results:')) {
          collectingSteps = false;
          collectingExpectedResults = true;
          expectedResultLines = [];
          console.log('Started collecting expected results');
        }
        
        // Collect numbered steps
        if (collectingSteps && trimmed.match(/^\d+\./)) {
          if (!testCase.steps) testCase.steps = [];
          testCase.steps.push(trimmed);
          console.log('Added step:', trimmed);
        }
        
        // Collect expected results (bullet points or regular text)
        if (collectingExpectedResults && (trimmed.startsWith('-') || trimmed.startsWith('•') || (trimmed && !trimmed.includes('**') && !trimmed.includes('User Story')))) {
          expectedResultLines.push(trimmed);
        }
        
        // Stop collecting if we hit a new section
        if (trimmed.includes('####') || trimmed.includes('User Story:')) {
          collectingSteps = false;
          collectingExpectedResults = false;
        }
      });
      
      // Combine expected results
      if (expectedResultLines.length > 0) {
        testCase.expectedResult = expectedResultLines.join('\n');
      }
      
      // Add test case if it has an ID
      if (testCase.testCaseId) {
        const newTestCase = {
          testCaseId: testCase.testCaseId,
          title: testCase.title || `Test Case ${testCase.testCaseId}`,
          description: testCase.description || 'Description not provided',
          steps: testCase.steps || [],
          expectedResult: testCase.expectedResult || 'Expected result not specified',
          priority: 'Medium'
        };
        testCases.push(newTestCase);
        console.log('Added test case:', newTestCase);
      }
    }
  });
  
  console.log('Total test cases parsed:', testCases.length);

  // Apply filters
  const filteredTestCases = testCases.filter(tc => {
    if (filters.priority !== 'all' && tc.priority.toLowerCase() !== filters.priority) {
      return false;
    }
    return true;
  });

  // Create Excel worksheet
  const worksheetData = filteredTestCases.map(tc => ({
    'Test Case ID': tc.testCaseId,
    'Test Case Name': tc.title,
    'Description': tc.description,
    'Test Steps': tc.steps.join('\n'),
    'Expected Result': tc.expectedResult,
    'Priority': tc.priority
  }));

  const worksheet = XLSX.utils.json_to_sheet(worksheetData);
  
  // Set column widths
  worksheet['!cols'] = [
    { width: 15 }, // Test Case ID
    { width: 30 }, // Test Case Name
    { width: 40 }, // Description
    { width: 50 }, // Test Steps
    { width: 30 }, // Expected Result
    { width: 12 }  // Priority
  ];

  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Test Cases');
  
  if (returnBlob) {
    // Generate blob for upload
    const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
    return new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  } else {
    // Download file
    const excelFilename = filename.replace(/\.(docx|doc)$/i, '') + '_TestCases.xlsx';
    XLSX.writeFile(workbook, excelFilename);
  }
};

// Excel generation for Test Scenarios
export const generateTestScenariosExcel = (
  content: string,
  filename: string,
  filterOptions?: FilterOptions,
  returnBlob?: boolean
): Blob | void => {
  const defaultFilters: FilterOptions = { priority: 'all' };
  const filters = filterOptions || defaultFilters;
  const testScenarios: TestScenario[] = [];
  
  // Split by test scenario sections - handle multiple formats  
  const sections = content.split(/(?=#### Test Scenario \d+)|(?=Test Scenario ID[:]*\s*TS-\d+)|(?=\*\*Test Scenario ID\*\*)/);
  
  sections.forEach(section => {
    if (section.trim() && (section.includes('TS-') || section.includes('Test Scenario'))) {
      const lines = section.split('\n');
      let scenario: Partial<TestScenario> = {};
      
      lines.forEach(line => {
        const trimmed = line.trim();
        
        // Extract Test Scenario ID
        if (trimmed.match(/TS-\d+/)) {
          scenario.testScenarioId = trimmed.match(/TS-\d+/)?.[0] || '';
        }
        
        // Extract Test Scenario Description
        if (trimmed.includes('Test Scenario Description:') || trimmed.includes('**Test Scenario Description**')) {
          scenario.description = trimmed.replace(/.*?Test Scenario Description\*?\*?:\s*/, '').replace(/[*-]/g, '').trim();
        }
        
        // Extract Expected Results
        if (trimmed.includes('Expected Results:') || trimmed.includes('**Expected Results**')) {
          scenario.expectedResults = trimmed.replace(/.*?Expected Results\*?\*?:\s*/, '').replace(/[*-]/g, '').trim();
        }
        
        // Extract Priority
        if (trimmed.includes('Priority:') || trimmed.includes('**Priority**')) {
          scenario.priority = trimmed.replace(/.*?Priority\*?\*?:\s*/, '').replace(/[*-]/g, '').trim();
        }
        
        // Extract Pre-Condition
        if (trimmed.includes('Pre-Condition:') || trimmed.includes('**Pre-Condition**')) {
          scenario.preCondition = trimmed.replace(/.*?Pre-Condition\*?\*?:\s*/, '').replace(/[*-]/g, '').trim();
        }
      });
      
      // Add test scenario if it has an ID
      if (scenario.testScenarioId) {
        testScenarios.push({
          testScenarioId: scenario.testScenarioId,
          title: scenario.description || `Test Scenario ${scenario.testScenarioId}`,
          description: scenario.description || 'Description not provided',
          expectedResults: scenario.expectedResults || 'Expected results not specified',
          priority: scenario.priority || 'Medium',
          preCondition: scenario.preCondition || 'Pre-condition not specified'
        });
      }
    }
  });

  // Apply filters
  const filteredScenarios = testScenarios.filter(ts => {
    if (filters.priority !== 'all' && ts.priority.toLowerCase() !== filters.priority) {
      return false;
    }
    return true;
  });

  // Create Excel worksheet
  const worksheetData = filteredScenarios.map(ts => ({
    'Test Scenario ID': ts.testScenarioId,
    'Test Scenario Description': ts.description,
    'Expected Results': ts.expectedResults,
    'Priority': ts.priority,
    'Pre-Condition': ts.preCondition || 'Pre-condition not specified'
  }));

  const worksheet = XLSX.utils.json_to_sheet(worksheetData);
  
  // Set column widths
  worksheet['!cols'] = [
    { width: 18 }, // Test Scenario ID
    { width: 40 }, // Description
    { width: 30 }, // Expected Results
    { width: 12 }, // Priority
    { width: 25 }  // Pre-Condition
  ];

  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Test Scenarios');
  
  if (returnBlob) {
    // Generate blob for upload
    const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
    return new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  } else {
    // Download file
    const excelFilename = filename.replace(/\.(docx|doc)$/i, '') + '_TestScenarios.xlsx';
    XLSX.writeFile(workbook, excelFilename);
  }
};

// Utility function to extract test content
export const extractTestContent = (
  fullText: string,
  contentType: string
): string => {
  try {
    let cleanContent = fullText;

    const conversationalPhrases = [
      /^I'll help you.*?\./gi,
      /^Here are.*?:/gi,
      /^Based on.*?:/gi,
      /^I'll generate.*?\./gi,
      /^Let me create.*?\./gi,
      /^I'll create.*?\./gi,
      /^I can help.*?\./gi,
      /^Sure.*?\./gi,
      /^Certainly.*?\./gi,
      /^Of course.*?\./gi,
      /Let me know if you need.*$/gi,
      /If you need.*modifications.*$/gi,
      /Feel free to.*$/gi,
      /Please let me know.*$/gi,
    ];

    conversationalPhrases.forEach((phrase) => {
      cleanContent = cleanContent.replace(phrase, "").trim();
    });

    if (contentType === "case") {
      const testCaseMatch = cleanContent.match(
        /(?:Test Case ID|TC-\d+)[\s\S]*?(?=\n\n(?:Test Case ID|TC-\d+)|$)/gi
      );
      if (testCaseMatch) {
        cleanContent = testCaseMatch.join("\n\n");
      }
    }

    if (contentType === "scenario") {
      const scenarioMatch = cleanContent.match(
        /(?:Test Scenario ID|TS-\d+)[\s\S]*?(?=\n\n(?:Test Scenario ID|TS-\d+)|$)/gi
      );
      if (scenarioMatch) {
        cleanContent = scenarioMatch.join("\n\n");
      }
    }

    return cleanContent;
  } catch (error) {
    return fullText;
  }
};