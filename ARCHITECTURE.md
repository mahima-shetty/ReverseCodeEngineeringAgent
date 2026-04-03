# CodeLens Architecture And Flow

---

## 1. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          BROWSER (React + Vite)                         │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                         App.tsx (Root)                           │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │               PersonaProvider (Context)                     │ │   │
│  │  │  persona: developer | qa | pm   (persisted in localStorage) │ │   │
│  │  │  mode: technical | simplified                               │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                                                                   │   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌───────────────────────┐ │   │
│  │  │   Header     │  │  ConfigBar    │  │   CodeInputPanel      │ │   │
│  │  │ PersonaSelect│  │ endpoint/token│  │  lang tabs + upload   │ │   │
│  │  │ PersonaBadge │  └───────────────┘  │  code textarea        │ │   │
│  │  └──────────────┘                     │  [Analyze] button     │ │   │
│  │                                        └───────────────────────┘ │   │
│  │                                                                   │   │
│  │  ┌───────────────────────┐    ┌────────────────────────────────┐ │   │
│  │  │    QuickSummary       │    │         ReportPanel            │ │   │
│  │  │ Lines / Functions /   │    │  ┌──────────────────────────┐  │ │   │
│  │  │ Tables / Complexity / │    │  │  Tab Bar (persona-aware)  │  │ │   │
│  │  │ Risk / Language       │    │  │  Intent | DataFlow |      │  │ │   │
│  │  └───────────────────────┘    │  │  Complexity | Security |  │  │ │   │
│  │                               │  │  AntiPatterns | Refactor  │  │ │   │
│  │                               │  │  + QA: TestScenarios      │  │ │   │
│  │                               │  │  + PM: ImpactSummary/Jira │  │ │   │
│  │                               │  └──────────────────────────┘  │ │   │
│  │                               │  [ModeToggle: Tech/Simplified]  │ │   │
│  │                               └────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                              HTTP POST /api/analyze
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                   BACKEND  (FastAPI / Python)   :8000                   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                   /api/analyze  (POST)                           │   │
│  │                                                                  │   │
│  │  1. Auth: Bearer token (from UI or .env)                        │   │
│  │  2. rag_store.py: retrieve org coding standards (RAG)           │   │
│  │  3. _build_request_body(): build prompt with code + RAG context │   │
│  │  4. httpx POST → Blueverse Foundry chatservice                  │   │
│  │  5. _extract_flat_payload(): parse varied LLM response shapes   │   │
│  │     (JSON, markdown, OpenAI/Anthropic/Blueverse wrappers)       │   │
│  │  6. Return flat JSON schema to frontend                         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                        Bearer-authenticated HTTPS POST
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│          BLUEVERSE FOUNDRY  (LTMindtree AI Platform)                    │
│                                                                         │
│   Space: CodeReverseSimpleAgent_2b2a9f68                                │
│   Flow:  69c35f4bfc57495a91cffadf                                       │
│   API:   /chatservice/chat                                              │
│                                                                         │
│   Runs: LLM Agent → returns flat JSON with:                            │
│   summary_oneliner, summary_complexity, summary_risk,                   │
│   functional_purpose, business_logic, side_effects,                     │
│   functional_inputs, functional_outputs, dataflow_steps,                │
│   complexity_score, security_score, security_issues,                    │
│   antipatterns, refactor_recommendations, jira_tickets                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Frontend Module Map

```
frontend/react-app/src/
│
├── main.tsx                    Entry point — mounts <App />
├── App.tsx                     Root — wraps tree in PersonaProvider,
│                               holds analyze state, calls backend API
│
├── types.ts                    Shared TypeScript types:
│                               Lang, FlatBlueverseRaw, NormalizedResult,
│                               re-exports Persona, ExplainMode
│
├── context/
│   └── PersonaContext.tsx      React Context:
│                               • Persona state (developer/qa/pm)
│                               • ExplainMode (technical/simplified)
│                               • localStorage persistence
│                               • body[data-persona] CSS attribute sync
│                               • usePersona() hook
│                               • useTheme() hook → accentColor, label, icon
│
├── lib/
│   ├── api.ts                  analyzeCodeApi() — POST to /api/analyze
│   ├── normalize.ts            normalizeBlueverseResponse():
│   │                           FlatBlueverseRaw → NormalizedResult
│   │                           Derives: funcCount, tables, nestingDepth,
│   │                           maintainability, readability, testability
│   ├── transform.ts            transformResponse():
│   │                           NormalizedResult + Persona + Mode → PersonaView
│   │                           Computes: visibleTabs[], riskLabel,
│   │                           testScenarios (QA), impactSummary (PM),
│   │                           businessSummary text
│   ├── simplify.ts             simplifyText() — plain-English rewriting
│   │                           for mode='simplified' (PM persona)
│   └── utils.ts                riskColor() helper
│
├── components/
│   ├── Header.tsx              Logo + PersonaSelector + PersonaBadge
│   ├── ConfigBar.tsx           Endpoint URL + Bearer token inputs
│   ├── CodeInputPanel.tsx      Language tabs + file upload + code textarea
│   │                           + Analyze button + status bar
│   ├── QuickSummary.tsx        Metric chips: LoC, Functions, Tables,
│   │                           Complexity, Risk, Language + Overview card
│   ├── ReportPanel.tsx         Persona-aware tab bar + tab content renderer
│   │                           Consumes PersonaView from transform.ts
│   ├── PersonaSelector.tsx     3-button pill toggle (Developer/QA/PM)
│   ├── PersonaBadge.tsx        Header badge showing active persona icon+label
│   ├── ModeToggle.tsx          Technical ↔ Simplified view toggle
│   │
│   └── tabs/
│       ├── IntentTab.tsx       Functional purpose, business logic, I/O
│       │                       PM: shows businessSummary instead
│       │                       QA: adds "Testable Interpretation" card
│       ├── DataFlowTab.tsx     Processing steps, tables, transformations
│       │                       QA: adds "Edge Case Checklist"
│       ├── ComplexityTab.tsx   Cyclomatic/Nesting metrics + hotspots
│       │                       PM: simplified "What This Means" card
│       ├── SecurityTab.tsx     Issues list, hardcoded values
│       │                       PM: risk-label view, hides hardcoded
│       │                       QA: adds "write test" hints per issue
│       ├── AntiPatternsTab.tsx Anti-pattern list (all personas)
│       ├── RefactorTab.tsx     Refactor recommendations (all personas)
│       ├── JiraTab.tsx         Jira tickets
│       │                       PM: "Prioritized Backlog" header
│       │                       QA: "Test-Oriented Tickets" header
│       ├── TestScenariosTab.tsx QA-only: auto-derived test scenarios
│       │                        (security + edge + negative + positive)
│       └── ImpactSummaryTab.tsx PM-only: businessImpact, riskLevel,
│                                topActions (executive summary)
│
└── index.css                   CSS custom properties + persona themes:
                                body[data-persona="developer"] → purple #7b61ff
                                body[data-persona="qa"]        → cyan  #00d4ff
                                body[data-persona="pm"]        → pink  #ff61dc
                                All transitions: 0.3s ease
```

---

## 3. End-to-End Data Flow

```
User pastes code + sets language
         │
         ▼
[Analyze button clicked]  App.tsx: analyze()
         │
         ▼
lib/api.ts: analyzeCodeApi(code, lang, endpoint, token)
         │  POST /api/analyze  { code, language, endpoint, token }
         │
         ▼
backend/main.py: /api/analyze
   │  rag_store.py → retrieve org standards (RAG)
   │  _build_request_body() → assemble prompt
   │  httpx.POST → Blueverse Foundry /chatservice/chat
   │  _extract_flat_payload() → parse LLM response variants
   │  return FlatBlueverseRaw JSON
         │
         ▼
lib/normalize.ts: normalizeBlueverseResponse(raw, code, lang)
   │  • safeParseJsonList() — tolerant JSON array parser
   │  • Count functions via regex (def/function/procedure/create...)
   │  • Count tables via SQL regex (FROM/JOIN/INTO/UPDATE...)
   │  • Estimate nesting depth (bracket tracking + indentation)
   │  • Derive maintainability/readability/testability from complexity_score
   │  Returns: NormalizedResult (structured, typed)
         │
         ▼
App.tsx: setResult(normalized)  →  QuickSummary + ReportPanel re-render
         │
         ▼
lib/transform.ts: transformResponse(result, persona, mode)
   │  • Filter visibleTabs[] per persona:
   │    developer → intent, dataflow, complexity, security, antipatterns, refactor, jira
   │    qa        → intent, dataflow, security, antipatterns, testscenarios, jira
   │    pm        → intent, complexity, security, jira, impact
   │  • Compute riskLabel (Low/Medium/High) for complexity + security
   │  • Derive testScenarios[] from security issues + anti-patterns (QA)
   │  • Build impactSummary { businessImpact, riskLevel, topActions } (PM)
   │  • Apply simplify.ts if mode='simplified'
   │  Returns: PersonaView
         │
         ▼
ReportPanel.tsx
   │  Renders persona-filtered tab bar
   │  Each tab → tab component (IntentTab, SecurityTab, etc.)
   │  Each tab reads PersonaView + persona to decide what to show/hide
         │
         ▼
User switches Persona (Developer → QA → PM)
   │  PersonaContext.setPersona()
   │  body[data-persona] updated → CSS theme instantly switches
   │  PersonaView recomputed → tabs re-filter
   │  Active tab resets to first visible tab if no longer available
         │
         ▼
User switches Mode (Technical ↔ Simplified)
   │  PersonaContext.setMode()
   │  PersonaView recomputed with simplify.ts applied
   │  All tab content re-renders with plain-English descriptions (PM default)
```

---

## 4. Persona Tab Visibility Matrix

| Tab              | Developer | QA  | PM  |
|------------------|-----------|-----|-----|
| Functional Intent| ✅        | ✅  | ✅  |
| Data Flow        | ✅        | ✅  | ❌  |
| Complexity       | ✅        | ❌  | ✅  |
| Security         | ✅        | ✅  | ✅  |
| Anti-Patterns    | ✅        | ✅  | ❌  |
| Refactor         | ✅        | ❌  | ❌  |
| Jira Tasks       | ✅        | ✅  | ✅  |
| Test Scenarios   | ❌        | ✅  | ❌  |
| Impact Summary   | ❌        | ❌  | ✅  |

---

## 5. Tech Stack

| Layer        | Technology                        |
|--------------|-----------------------------------|
| Frontend     | React 18, TypeScript, Vite 5      |
| Styling      | Vanilla CSS (CSS custom properties) |
| State        | React Context + localStorage      |
| Backend      | FastAPI (Python 3.11+), httpx, uvicorn |
| AI Platform  | LTMindtree Blueverse Foundry      |
| RAG          | rag_store.py (org coding standards) |
| Auth         | Bearer token (UI input or .env)   |
| Build output | dist/ (Vite production bundle)    |
