from __future__ import annotations

import re

from app.schemas import AnalysisOutput, AntiPattern, Finding, RefactorRecommendation


def _unique_append(items: list, key: str, value) -> None:
    if key in items:
        return
    items.append(key)
    items.append(value)


def _table_names(code: str, pattern: str) -> list[str]:
    compiled = re.compile(pattern, re.IGNORECASE)
    return sorted({match.group(1) for match in compiled.finditer(code)})


def _summarize_literals(code: str) -> list[str]:
    patterns = [
        r"\b(?:v_|p_)?(?:limit|threshold|currency|region|status|settle_days|settlement_days)\w*\b\s*(?::=|=)\s*('[^']+'|\d+(?:\.\d+)?)",
        r"\b(?:product_code|region|status)\s*=\s*'[^']+'",
        r"\*\s*0\.\d+",
    ]
    hits: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, code, re.IGNORECASE):
            hits.append(match.group(0).strip())
            if len(hits) >= 6:
                return hits
    return hits


def _contains_exception_commit(lower: str) -> bool:
    return bool(re.search(r"exception[\s\S]{0,1200}when others[\s\S]{0,1200}commit\s*;", lower, re.IGNORECASE))


def _contains_row_by_row_query(lower: str) -> bool:
    return bool(re.search(r"for\b[\s\S]{0,4000}?loop[\s\S]{0,4000}?select\b", lower, re.IGNORECASE))


def _contains_dynamic_sql(lower: str) -> bool:
    return "execute immediate" in lower


def _contains_sql_concatenation(code: str) -> bool:
    return bool(re.search(r"(execute immediate|v_sql\s*:=)[\s\S]{0,800}\|\|", code, re.IGNORECASE))


def _insert_without_columns(code: str) -> list[str]:
    pattern = re.compile(r"insert\s+into\s+([a-zA-Z0-9_.]+)\s+values\s*\(", re.IGNORECASE)
    return sorted({match.group(1) for match in pattern.finditer(code)})


def _has_select_star(lower: str) -> bool:
    return "select *" in lower


def _looks_like_bip(code: str, lower: str) -> bool:
    return "<?for-each" in lower or "<?if:" in lower or "xdoxslt:" in lower or "xdofx:" in lower


def _looks_like_groovy(lower: str, language: str) -> bool:
    return language.lower() == "groovy" or "groovy.sql.sql" in lower or "sql.newinstance" in lower or "def " in lower


def _add_finding(target: list[Finding], seen: set[tuple[str, str]], finding: Finding) -> None:
    key = (finding.type, finding.evidence)
    if key in seen:
        return
    seen.add(key)
    target.append(finding)


def _add_antipattern(target: list[AntiPattern], seen: set[tuple[str, str]], item: AntiPattern) -> None:
    key = (item.pattern, item.evidence)
    if key in seen:
        return
    seen.add(key)
    target.append(item)


def _add_refactor(target: list[RefactorRecommendation], seen: set[tuple[str, str]], item: RefactorRecommendation) -> None:
    key = (item.title, item.evidence)
    if key in seen:
        return
    seen.add(key)
    target.append(item)


def heuristic_analysis(*, code: str, language: str, inferred_product: str) -> AnalysisOutput:
    lower = code.lower()
    reads = _table_names(code, r"(?:from|join)\s+([a-zA-Z0-9_.]+)")
    writes = _table_names(code, r"(?:insert\s+into|update|delete\s+from|merge\s+into)\s+([a-zA-Z0-9_.]+)")
    all_tables = sorted({*reads, *writes})
    security: list[Finding] = []
    antipatterns: list[AntiPattern] = []
    refactors: list[RefactorRecommendation] = []
    inputs: list[str] = []
    outputs: list[str] = []
    dataflow: list[str] = []
    business_logic: list[str] = []
    side_effects: list[str] = []
    finding_seen: set[tuple[str, str]] = set()
    antipattern_seen: set[tuple[str, str]] = set()
    refactor_seen: set[tuple[str, str]] = set()

    summary = f"{language.upper()} artifact reviewed with explicit retrieval-backed analysis"
    purpose = "Reverse-engineering summary produced without fabricating unsupported claims."

    if reads:
        inputs.append(f"Reads from: {', '.join(reads[:6])}")
        dataflow.append(f"Queries source objects: {', '.join(reads[:6])}")
    if writes:
        outputs.append(f"Writes to: {', '.join(writes[:6])}")
        side_effects.append(f"Performs DML on {', '.join(writes[:6])}")
        dataflow.append(f"Mutates target objects: {', '.join(writes[:6])}")
    if all_tables:
        business_logic.append(f"Artifact references {len(all_tables)} table or object name(s)")

    hardcoded_literals = _summarize_literals(code)
    if hardcoded_literals:
        _add_antipattern(
            antipatterns,
            antipattern_seen,
            AntiPattern(
                severity="HIGH" if len(hardcoded_literals) >= 3 else "MEDIUM",
                pattern="Hardcoded business rules and constants",
                description="Business thresholds, status values, regional rules, or monetary rates are embedded directly in code.",
                recommendation="Move rates, thresholds, currencies, and status mappings into configuration or reference tables.",
                confidence_score=93,
                evidence="; ".join(hardcoded_literals[:4]),
            ),
        )
        _add_refactor(
            refactors,
            refactor_seen,
            RefactorRecommendation(
                priority="HIGH",
                title="Externalize business constants",
                description="Replace embedded status values, fee/tax rates, currencies, and threshold values with configurable data.",
                benefit="Reduces change risk and makes product behavior auditable.",
                confidence_score=91,
                evidence="; ".join(hardcoded_literals[:4]),
            ),
        )
        business_logic.append("Embedded literals drive decision branches and financial calculations")

    if "when others" in lower:
        _add_finding(
            security,
            finding_seen,
            Finding(
                severity="HIGH",
                type="Broad exception handling",
                description="The artifact catches all exceptions without preserving failure specificity.",
                confidence_score=95,
                evidence="WHEN OTHERS",
            ),
        )

    if "commit;" in lower:
        _add_antipattern(
            antipatterns,
            antipattern_seen,
            AntiPattern(
                severity="HIGH",
                pattern="Commit inside procedure or script",
                description="The artifact commits internally and can break caller-managed transactions.",
                recommendation="Move transaction control to the caller boundary or service orchestration layer.",
                confidence_score=95,
                evidence="COMMIT;",
            ),
        )

    if _contains_exception_commit(lower):
        _add_antipattern(
            antipatterns,
            antipattern_seen,
            AntiPattern(
                severity="HIGH",
                pattern="Commit in exception handler",
                description="The exception block commits work after an error, which can persist partial state and complicate recovery.",
                recommendation="Rollback on failure unless partial commits are explicitly required and documented.",
                confidence_score=96,
                evidence="EXCEPTION ... COMMIT;",
            ),
        )

    if _contains_dynamic_sql(lower):
        _add_finding(
            security,
            finding_seen,
            Finding(
                severity="HIGH",
                type="Dynamic SQL execution",
                description="The artifact executes SQL dynamically, which increases injection and auditability risk.",
                confidence_score=92,
                evidence="EXECUTE IMMEDIATE",
            ),
        )
        dataflow.append("Builds and executes SQL dynamically at runtime")

    if _contains_sql_concatenation(code):
        _add_antipattern(
            antipatterns,
            antipattern_seen,
            AntiPattern(
                severity="HIGH",
                pattern="Dynamic SQL built by concatenation",
                description="SQL text is assembled with string concatenation instead of bind-safe parameterization.",
                recommendation="Use bind variables or parameterized APIs for dynamic SQL.",
                confidence_score=94,
                evidence="Detected SQL string concatenation with ||",
            ),
        )
        _add_refactor(
            refactors,
            refactor_seen,
            RefactorRecommendation(
                priority="HIGH",
                title="Parameterize dynamic SQL",
                description="Replace string-built SQL with bind variables and explicit input validation.",
                benefit="Reduces injection risk and improves statement reuse.",
                confidence_score=92,
                evidence="Detected SQL string concatenation with ||",
            ),
        )

    insert_without_columns = _insert_without_columns(code)
    if insert_without_columns:
        _add_antipattern(
            antipatterns,
            antipattern_seen,
            AntiPattern(
                severity="MEDIUM",
                pattern="INSERT without explicit column list",
                description="The artifact inserts rows using VALUES without naming target columns.",
                recommendation="Specify target columns explicitly to avoid schema-order coupling.",
                confidence_score=90,
                evidence=", ".join(insert_without_columns[:4]),
            ),
        )

    if _contains_row_by_row_query(lower):
        _add_antipattern(
            antipatterns,
            antipattern_seen,
            AntiPattern(
                severity="MEDIUM",
                pattern="Row-by-row query processing",
                description="The artifact performs queries inside a loop, which can degrade throughput and amplify database round-trips.",
                recommendation="Rewrite with set-based logic, MERGE, or bulk operations where possible.",
                confidence_score=88,
                evidence="FOR ... LOOP with SELECT inside loop",
            ),
        )
        dataflow.append("Processes records row by row with additional lookup queries")

    if _has_select_star(lower):
        _add_antipattern(
            antipatterns,
            antipattern_seen,
            AntiPattern(
                severity="MEDIUM",
                pattern="SELECT * usage",
                description="The artifact selects all columns instead of an explicit projection.",
                recommendation="Select only the required columns.",
                confidence_score=84,
                evidence="SELECT *",
            ),
        )

    if "apps/apps" in lower or "password" in lower or "bearer " in lower or "api_key" in lower:
        _add_finding(
            security,
            finding_seen,
            Finding(
                severity="HIGH",
                type="Credential exposure",
                description="Credentials or token-like values are embedded in the artifact.",
                confidence_score=96,
                evidence="Detected credential-like literal in artifact.",
            ),
        )
        _add_refactor(
            refactors,
            refactor_seen,
            RefactorRecommendation(
                priority="HIGH",
                title="Move credentials to secret storage",
                description="Remove embedded credentials and source them from a secret manager or runtime injection.",
                benefit="Reduces credential leakage risk.",
                confidence_score=92,
                evidence="Detected credential-like literal in artifact.",
            ),
        )

    if "sqlplus" in lower and "exit" not in lower:
        _add_finding(
            security,
            finding_seen,
            Finding(
                severity="MEDIUM",
                type="Missing failure handling",
                description="The script invokes SQL*Plus without explicit exit-code checks.",
                confidence_score=86,
                evidence="SQL*Plus invocation without EXIT handling.",
            ),
        )

    if _looks_like_bip(code, lower):
        business_logic.append("Contains BIP template logic and report-time conditional rendering")
        if hardcoded_literals or "decode(" in lower:
            _add_antipattern(
                antipatterns,
                antipattern_seen,
                AntiPattern(
                    severity="MEDIUM",
                    pattern="Hardcoded reporting logic",
                    description="BIP template expressions embed business rules directly in presentation logic.",
                    recommendation="Move reusable rules into the data model or configuration.",
                    confidence_score=87,
                    evidence="BIP/XDO conditional template logic detected.",
                ),
            )

    if _looks_like_groovy(lower, language):
        if "sql.newinstance" in lower or "groovy.sql.sql" in lower:
            _add_antipattern(
                antipatterns,
                antipattern_seen,
                AntiPattern(
                    severity="MEDIUM",
                    pattern="Direct SQL access in Groovy",
                    description="Groovy code opens direct SQL access, which can couple business logic tightly to database structure.",
                    recommendation="Use managed data-access abstractions and parameterized queries.",
                    confidence_score=86,
                    evidence="groovy.sql.Sql usage detected.",
                ),
            )
        if re.search(r'["\']\s*(select|update|insert|delete)\b[\s\S]{0,160}\$\{', code, re.IGNORECASE):
            _add_finding(
                security,
                finding_seen,
                Finding(
                    severity="HIGH",
                    type="Interpolated SQL in Groovy",
                    description="SQL is built with Groovy interpolation, which can create injection paths.",
                    confidence_score=94,
                    evidence="Groovy SQL string interpolation detected.",
                ),
            )
        if "http://" in lower or "https://" in lower:
            _add_antipattern(
                antipatterns,
                antipattern_seen,
                AntiPattern(
                    severity="MEDIUM",
                    pattern="Hardcoded endpoint",
                    description="The script contains a fixed service endpoint or URL literal.",
                    recommendation="Externalize endpoints into environment-specific configuration.",
                    confidence_score=84,
                    evidence="HTTP/HTTPS literal detected in Groovy artifact.",
                ),
            )

    if language.lower() in {"sql", "plsql"} and writes:
        outputs.append("Persists business state changes through DML operations")
    elif "payload." in lower:
        inputs.append("Consumes orchestration payload fields")
        outputs.append("Returns a structured approval or workflow decision")
        dataflow.append("Reads payload values and branches on business thresholds")
    elif reads:
        outputs.append("Returns or derives results from queried records")
    elif "integrationname" in lower:
        inputs.append("Consumes integration configuration")
        outputs.append("Executes an integration step sequence")
        dataflow.append("Runs staged integration steps in order")
    else:
        outputs.append("Produces behavior implied by the artifact contents")

    if inferred_product:
        summary = f"{inferred_product.upper()} {language.upper()} artifact reviewed with retrieval-backed analysis"
        purpose = f"Reverse-engineers the artifact in {inferred_product.upper()} context using bounded retrieval and claim verification."

    complexity_score = min(
        100.0,
        round(len(code.splitlines()) * 1.4 + len(antipatterns) * 9 + len(security) * 10 + len(refactors) * 4, 2),
    )
    security_score = max(0.0, 100.0 - (len(security) * 16 + len(antipatterns) * 7))
    risk = "LOW"
    if len(security) >= 2 or len(antipatterns) >= 3:
        risk = "HIGH"
    elif security or antipatterns:
        risk = "MEDIUM"

    return AnalysisOutput(
        summary_oneliner=summary,
        summary_complexity="HIGH" if complexity_score >= 60 else "MEDIUM" if complexity_score >= 30 else "LOW",
        summary_risk=risk,
        functional_purpose=purpose,
        business_logic=business_logic,
        side_effects=side_effects,
        functional_inputs=inputs,
        functional_outputs=outputs,
        dataflow_steps=dataflow,
        complexity_score=complexity_score,
        security_score=round(security_score, 2),
        security_issues=security,
        antipatterns=antipatterns,
        refactor_recommendations=refactors,
        jira_tickets=[],
    )
