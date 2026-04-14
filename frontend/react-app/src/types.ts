export type Lang = 'sql' | 'groovy' | 'bip' | 'oic' | 'shell' | 'auto';
export type { Persona, ExplainMode } from './context/PersonaContext';

export interface AnalysisInput {
  id: string;
  label: string;
  code: string;
  language: Lang;
}

export interface RagCitation {
  chunk_id?: string;
  source: string;
  excerpt: string;
  product?: string;
}

export interface RagDiagnostics {
  products?: string[];
  local_hits?: number;
  vertex_hits?: number;
  returned_hits?: number;
}

export interface HardcodedItemRaw {
  type?: string;
  description?: string;
  evidence?: string;
}

export interface TestScenarioRaw {
  title?: string;
  type?: string;
  description?: string;
  source?: string;
}

export interface ImpactSummaryRaw {
  business_impact?: string;
  risk_overview?: string;
  risk_level?: string;
  top_actions?: string[];
}

export interface RetrievalHit {
  chunk_id: string;
  source: string;
  title: string;
  section_path: string[];
  product: string;
  text: string;
  excerpt: string;
  dense_score: number;
  sparse_score: number;
  fused_score: number;
  rerank_score: number;
}

export interface RetrievalBundle {
  query: string;
  inferred_product: string;
  corpus_version: string;
  lexical_candidates: RetrievalHit[];
  reranked_hits: RetrievalHit[];
}

export interface ClaimVerification {
  claim: string;
  source_fields: string[];
  status: 'supported' | 'weakly_supported' | 'unsupported';
  evidence_chunk_ids: string[];
  confidence: number;
}

export interface VerificationSummary {
  claims: ClaimVerification[];
  supported_claim_rate: number;
  unsupported_claim_rate: number;
  grounded_accuracy: number;
  unsupported_claims: string[];
}

export interface TraceEvent {
  step: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  status: 'ok' | 'degraded' | 'failed';
  provider?: string;
  details?: Record<string, unknown>;
}

export interface FlatBlueverseRaw {
  summary_oneliner?: string;
  summary_complexity?: string;
  summary_risk?: string;
  functional_purpose?: string;
  business_logic?: unknown;
  side_effects?: unknown;
  functional_inputs?: unknown;
  functional_outputs?: unknown;
  testable_interpretation?: unknown;
  dataflow_steps?: unknown;
  dataflow_tables?: unknown;
  dataflow_transformations?: unknown;
  complexity_score?: number | string;
  nesting_depth?: number | string;
  maintainability?: string | number;
  readability?: string | number;
  testability?: string | number;
  security_score?: number | string;
  security_issues?: unknown;
  hardcoded_items?: unknown;
  antipatterns?: unknown;
  refactor_recommendations?: unknown;
  jira_tickets?: unknown;
  test_scenarios?: unknown;
  impact_summary?: ImpactSummaryRaw;
  rag_citations?: RagCitation[];
  rag_diagnostics?: RagDiagnostics;
  llm_metadata?: {
    provider?: string;
    model?: string;
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
    cost_usd?: number;
    duration_seconds?: number;
    raw_status?: string;
    error_message?: string;
    provider_failures?: string[];
    failure_reason?: string;
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
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
    cost_usd?: number;
    duration_seconds?: number;
    raw_status?: string;
    error_message?: string;
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
    testableInterpretation: string[];
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
    hardcoding: { type?: string; description?: string; evidence?: string }[];
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
  testScenarios: {
    title: string;
    type: string;
    description: string;
    source: string;
  }[];
  impactSummaryRaw?: {
    businessImpact: string;
    riskOverview: string;
    riskLevel: 'Low' | 'Medium' | 'High';
    topActions: string[];
  };
}

export interface AnalyzeBatchItemRaw {
  id: string;
  label: string;
  language: string;
  original_input: string;
  primary_output: FlatBlueverseRaw;
  final_output?: FlatBlueverseRaw;
  retrieval?: RetrievalBundle;
  verification?: VerificationSummary;
  execution_trace?: TraceEvent[];
  judge_evaluation: JudgeEvaluation;
  final_status: 'approved' | 'flagged' | 'rejected';
  deliverable: boolean;
  analysis_state?: 'ok' | 'degraded' | 'failed';
  render_source?: 'graph' | 'heuristic' | 'failed' | 'none';
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
  retrieval: RetrievalBundle | null;
  verification: VerificationSummary | null;
  executionTrace: TraceEvent[];
  finalStatus: 'approved' | 'flagged' | 'rejected';
  deliverable: boolean;
  analysisState: 'ok' | 'degraded' | 'failed';
  renderSource: 'graph' | 'heuristic' | 'failed' | 'none';
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
  actual_result: FlatBlueverseRaw;
  expected_answer: {
    summary: string;
    raw_expected: {
      query: string;
      expected_claims: string[];
      forbidden_claims: string[];
      expected_sources: string[];
      qrels: string[];
    };
  };
  case_kpis: {
    grounded_accuracy: number;
    claim_support_rate: number;
    unsupported_claim_rate: number;
    citation_precision: number;
    recall_at_k: number;
    mrr: number;
    workflow_success: boolean;
    latency_seconds: number;
    cost_per_bundle_usd: number;
  };
  analysis_item: AnalyzeBatchItemRaw;
}

export interface BenchmarkSummary {
  total_cases: number;
  approved: number;
  flagged: number;
  rejected: number;
  kpis: {
    review_time_reduction_percent: number;
    claim_support_rate_percent?: number;
    unsupported_claim_rate_percent: number;
    citation_precision_percent?: number;
    recall_at_k_percent?: number;
    mrr_percent?: number;
    grounded_accuracy_percent: number;
    workflow_success_rate_percent: number;
    p95_latency_seconds: number;
    cost_per_bundle_usd: number;
  };
  artifact_type_breakdown: Record<string, { count: number; approved: number; avg_grounded_accuracy: number }>;
  oracle_product_breakdown: Record<string, { count: number; approved: number; avg_grounded_accuracy: number }>;
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
  actualResult: NormalizedResult;
  actualRaw: FlatBlueverseRaw;
  expectedAnswer: {
    summary: string;
    rawExpected: {
      query: string;
      expected_claims: string[];
      forbidden_claims: string[];
      expected_sources: string[];
      qrels: string[];
    };
  };
  caseKpis: {
    groundedAccuracy: number;
    claimSupportRate: number;
    unsupportedClaimRate: number;
    citationPrecision: number;
    recallAtK: number;
    mrr: number;
    workflowSuccess: boolean;
    latencySeconds: number;
    costPerBundleUsd: number;
  };
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
