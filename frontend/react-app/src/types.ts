export type Lang = 'sql' | 'groovy' | 'oic' | 'shell' | 'auto';

export interface FlatBlueverseRaw {
  summary_oneliner?: string;
  summary_complexity?: string;
  summary_risk?: string;
  functional_purpose?: string;
  functional_inputs?: string;
  functional_outputs?: string;
  dataflow_steps?: string;
  complexity_score?: number | string;
  security_score?: number | string;
  security_issues?: string;
  antipatterns?: string;
  refactor_recommendations?: string;
  jira_tickets?: string;
  [key: string]: unknown;
}

export interface NormalizedResult {
  summary: {
    language: string;
    linesOfCode: number;
    functions: string | number;
    tables: string | number;
    complexity: string;
    overallRisk: string;
    oneliner: string;
  };
  functionalIntent: {
    purpose: string;
    businessLogic: string[];
    inputs: string[];
    outputs: string[];
    sideEffects: string[];
  };
  dataFlow: {
    steps: string[];
    tables: string[];
    transformations: string[];
    diagram: string[];
  };
  complexity: {
    cyclomaticComplexity: number;
    nestingDepth: number;
    hotspots: { name: string; score: number; reason: string }[];
    metrics: { maintainability: string | number; readability: string | number; testability: string | number };
  };
  security: {
    issues: { severity: string; type: string; description: string; line: string; confidence_score: string; evidence: string }[];
    hardcoding: { type?: string; description?: string }[];
    score: number;
  };
  antiPatterns: {
    severity: string;
    pattern: string;
    description: string;
    recommendation: string;
    confidence_score: string;
    evidence: string;
  }[];
  refactorRecommendations: {
    priority: string;
    title: string;
    description: string;
    benefit: string;
    codeHint: string;
    confidence_score: string;
    evidence: string;
  }[];
  jiraTickets: {
    title: string;
    description: string;
    story_points: number | string;
    type: string;
  }[];
}
