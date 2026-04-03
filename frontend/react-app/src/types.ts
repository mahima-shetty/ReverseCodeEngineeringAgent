export type Lang = 'sql' | 'groovy' | 'bip' | 'oic' | 'shell' | 'auto';
export type { Persona, ExplainMode } from './context/PersonaContext';

export interface AnalysisInput {
  id: string;
  label: string;
  code: string;
  language: Lang;
}

export interface RagCitation {
  source: string;
  excerpt: string;
}

export interface RagDiagnostics {
  products?: string[];
  local_hits?: number;
  vertex_hits?: number;
  returned_hits?: number;
}

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
  rag_citations?: RagCitation[];
  rag_diagnostics?: RagDiagnostics;
  llm_metadata?: {
    provider?: string;
    model?: string;
    usage?: {
      input_tokens?: number;
      output_tokens?: number;
      total_tokens?: number;
    };
    cost_usd?: number;
    fallback_used?: boolean;
    duration_seconds?: number;
  };
  [key: string]: unknown;
}

export interface JudgeEvaluation {
  scores: {
    completeness: number;
    correctness: number;
    hallucination: number;
  };
  thresholds: {
    approved: {
      completeness_min: number;
      correctness_min: number;
      hallucination_max: number;
    };
    flagged: {
      completeness_min: number;
      correctness_min: number;
      hallucination_max: number;
    };
  };
  validation: {
    accuracy: number;
    oracle_grounding: number;
    oracle_specificity: number;
  };
  finding_metrics?: {
    precision: number;
    recall: number;
    false_positive_rate: number;
  };
  latency_metrics?: {
    time_to_first_useful_output: number;
    total_runtime: number;
  };
  status: 'approved' | 'flagged' | 'rejected';
  deliverable: boolean;
  summary: string;
  blocking_issues: string[];
  recommended_action: string;
  provider_metadata?: {
    provider?: string;
    model?: string;
    usage?: {
      input_tokens?: number;
      output_tokens?: number;
      total_tokens?: number;
    };
    cost_usd?: number;
    fallback_used?: boolean;
    duration_seconds?: number;
  };
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
  ragCitations: RagCitation[];
  ragDiagnostics: RagDiagnostics;
}

export interface AnalyzeBatchItemRaw {
  id: string;
  label: string;
  language: string;
  original_input: string;
  primary_output: FlatBlueverseRaw;
  final_output?: FlatBlueverseRaw;
  judge_evaluation: JudgeEvaluation;
  final_status: 'approved' | 'flagged' | 'rejected';
  deliverable: boolean;
  analysis_state?: 'ok' | 'degraded' | 'failed';
  render_source?: 'judge_reviewed' | 'primary_fallback' | 'failed' | 'none';
  failure_reason?: string;
  session_id?: string;
}

export interface AnalyzeBatchResponseRaw {
  items: AnalyzeBatchItemRaw[];
  summary: {
    total: number;
    approved: number;
    flagged: number;
    rejected: number;
  };
}

export interface BatchAnalysisItem {
  id: string;
  label: string;
  language: Lang | string;
  originalInput: string;
  primaryRaw: FlatBlueverseRaw;
  finalRaw: FlatBlueverseRaw;
  finalResult: NormalizedResult;
  judgeEvaluation: JudgeEvaluation;
  finalStatus: 'approved' | 'flagged' | 'rejected';
  deliverable: boolean;
  analysisState: 'ok' | 'degraded' | 'failed';
  renderSource: 'judge_reviewed' | 'primary_fallback' | 'failed' | 'none';
  failureReason: string;
}

export interface BatchAnalysisSummary {
  total: number;
  approved: number;
  flagged: number;
  rejected: number;
}

export interface BenchmarkSampleResultRaw {
  case_id: string;
  artifact_type: string;
  oracle_product: 'fusion' | 'jde' | 'ebs' | 'epm';
  baseline_manual_review_seconds: number;
  review_time_reduction_percent: number;
  category_scores: Record<string, number>;
  matched_keywords: Record<string, string[]>;
  missed_keywords: Record<string, string[]>;
  unsupported_findings: string[];
  grounding: {
    expected_sources: string[];
    matched_sources: string[];
    citation_sources: string[];
  };
  judge_evaluation: JudgeEvaluation;
  final_status: 'approved' | 'flagged' | 'rejected';
  deliverable: boolean;
  analysis_item: AnalyzeBatchItemRaw;
}

export interface BenchmarkSummary {
  total_cases: number;
  approved: number;
  flagged: number;
  rejected: number;
  kpis: {
    review_time_reduction_percent: number;
    review_time_target_met: boolean;
    reviewer_confidence_percent: number;
    reviewer_confidence_target_met: boolean;
    anti_pattern_catch_rate_percent: number;
    anti_pattern_target_met: boolean;
    critical_issue_recall_percent: number;
    unsupported_claim_rate_percent: number;
    oracle_grounding_pass_rate_percent: number;
    time_to_first_useful_output_seconds: number;
    time_to_first_useful_output_target_met: boolean;
    manual_judge_score: number;
    adoption_target_met: boolean;
    post_release_defect_reduction: string;
  };
  artifact_type_breakdown: Record<string, { count: number; approved: number; avg_review_time_reduction: number }>;
  oracle_product_breakdown: Record<string, { count: number; approved: number; avg_grounding: number }>;
}

export interface BenchmarkEvaluationResponseRaw {
  run_id: string;
  generated_at: string;
  summary: BenchmarkSummary;
  sample_results: BenchmarkSampleResultRaw[];
  exports?: {
    json_report: string;
    csv_report: string;
    manifest: string;
  };
}

export interface BenchmarkSampleResult {
  caseId: string;
  artifactType: string;
  oracleProduct: 'fusion' | 'jde' | 'ebs' | 'epm';
  baselineManualReviewSeconds: number;
  reviewTimeReductionPercent: number;
  categoryScores: Record<string, number>;
  matchedKeywords: Record<string, string[]>;
  missedKeywords: Record<string, string[]>;
  unsupportedFindings: string[];
  grounding: {
    expectedSources: string[];
    matchedSources: string[];
    citationSources: string[];
  };
  judgeEvaluation: JudgeEvaluation;
  finalStatus: 'approved' | 'flagged' | 'rejected';
  deliverable: boolean;
  analysisItem: BatchAnalysisItem;
}

export interface BenchmarkEvaluationResult {
  runId: string;
  generatedAt: string;
  summary: BenchmarkSummary;
  sampleResults: BenchmarkSampleResult[];
  exports: {
    json_report: string;
    csv_report: string;
    manifest: string;
  };
}
