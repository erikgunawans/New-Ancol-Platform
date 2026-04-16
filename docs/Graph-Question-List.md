# Graph Question List

> Live document. Updated alongside project development.
> Last updated: 2026-04-17 | Graph: 2,134 nodes, 5,228 edges, 123 communities
>
> Run any question: `/graphify query "<question>"`
> Update graph after code changes: `/graphify --update`

---

## How to use this list

Each question is tagged with its **impact category** and **graph traversal type**. Pick the ones relevant to your current work. After running a query, note the answer date and any follow-up questions that emerge.

**Impact categories:**
- **ARCH** — Architecture decisions, blast radius, coupling
- **SEC** — Security, auth flows, attack surface
- **PERF** — Performance, hot paths, bottlenecks
- **ONBOARD** — New developer understanding, knowledge transfer
- **RISK** — Hidden dependencies, single points of failure
- **PRODUCT** — Feature coverage, regulatory compliance gaps

---

## 1. Architecture & Blast Radius (ARCH)

### 1.1 God Node Impact Analysis

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 1 | How does `Document` (111 edges) flow through the entire system from upload to final report? | Document is the #1 connected entity. Any schema change cascades across 7 communities. Map the full lifecycle to understand blast radius. | Traced 2026-04-17 |
| 2 | Why does the `Extraction Agent` bridge 9 different communities? | Highest betweenness centrality (0.176). It's the system's gravitational center. Understanding WHY reveals architectural coupling that may need decoupling as the system scales. | Traced 2026-04-17 |
| 3 | What happens if `ProcessingMetadata` (91 edges) changes its schema? | Third most connected node. Carries extraction results through the entire pipeline. A field rename here breaks 4 agents silently. | |
| 4 | Which services would break if `UserRole` enum (101 edges) adds a new role? | RBAC touches every service. A new role needs handling in ROLE_PERMISSIONS, GATE_PERMISSIONS, MFA required roles, notification channel defaults, and frontend route guards. | |
| 5 | What is the full dependency chain of `get_session()` (78 edges, betweenness 0.095)? | DB session factory connects 8 communities. If connection pooling changes or async session behavior shifts, what breaks? | |

### 1.2 Cross-Community Coupling

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 6 | What are ALL the edges between the Agent Pipeline (c2) and Contract Schemas (c4)? | These are separate domains (MoM compliance vs CLM) sharing data structures. Tight coupling here means CLM changes can break MoM processing. | |
| 7 | How does the Notification Dispatch community (c3) connect to HITL gates? | Notifications were wired to gate transitions in session 25. The graph reveals whether the coupling is clean (via events) or leaky (via direct imports). | |
| 8 | Which communities does `ApiClient` (58 edges, betweenness 0.076) bridge? | The Gemini Agent's API client proxies all calls. If it goes down, which features degrade? | |
| 9 | Is there a hidden coupling between Email Ingest (c9) and Batch Processing (c8)? | Both create documents but through different paths. Are there shared assumptions about document state? | |

### 1.3 Module Boundaries

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 10 | What is the shortest path from `Neo4jGraphClient` to `WhatsApp notification`? | These should be completely independent. If a path exists, there's unexpected coupling. | |
| 11 | Can the Regulation Monitor (c13) function without the API Gateway (c1)? | Independence test. If regulation monitoring depends on the API gateway, a gateway outage stops compliance monitoring. | |
| 12 | What nodes exist in BOTH the MoM pipeline and the CLM pipeline? | Shared nodes are integration points. Too many shared nodes = the systems can't evolve independently. | |

---

## 2. Security & Auth (SEC)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 13 | Trace every path from an unauthenticated request to database write. | The MFA + IAP + RBAC layers should make this impossible. The graph can verify there are no bypass paths. | |
| 14 | Which endpoints does `User` (76 edges) connect to that DON'T have `require_permission`? | After the /review security fixes, all 54 endpoints should have RBAC. The graph can verify completeness. | |
| 15 | What is the full trust boundary around `mfa_secret_encrypted`? | Trace every function that reads, writes, or transforms the encrypted TOTP secret. Any function outside `auth/mfa.py` touching this is a leak. | |
| 16 | How does `GATE_PERMISSIONS` connect to `notify_gate_reviewers`? | The RBAC gate map drives who gets notified. If these diverge, the wrong people get WhatsApp alerts about documents they can't review. | |

---

## 3. Performance & Hot Paths (PERF)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 17 | What is the critical path from document upload to `hitl_gate_1`? | This is the user-facing latency. Every node on this path adds to the time between "upload" and "ready for review." | |
| 18 | Which functions in the hot path call `get_session()` multiple times? | Unnecessary DB session creation on every request. The graph can find functions that open sessions redundantly. | |
| 19 | What is the fan-out of `notify_gate_reviewers`? | When a document enters a gate, how many users get notified via how many channels? If 10 users x 3 channels = 30 async HTTP calls per gate transition. | |
| 20 | Which graph queries in the RAG orchestrator are sequential vs parallel? | The orchestrator uses `asyncio.gather` for some queries. The graph reveals if any calls are accidentally sequential. | |

---

## 4. New Developer Onboarding (ONBOARD)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 21 | Explain the `Document` state machine (14 states) and which service owns each transition. | A new developer needs to understand the state machine before touching any agent code. The graph traces which service triggers which transition. | |
| 22 | What are the 5 most important files a new developer should read first? | The god nodes + bridge nodes point to the architectural spine. Reading these files first gives 80% understanding. | |
| 23 | How does data flow from a Gemini Enterprise chat message to a compliance report? | End-to-end trace through the webhook, tool handlers, API client, agents, and HITL gates. This is the "explain the whole system" question. | |
| 24 | What is the relationship between `ancol-common` schemas and each service? | The shared package is the contract between services. Understanding which schemas each service consumes prevents breaking changes. | |

---

## 5. Risk & Single Points of Failure (RISK)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 25 | What are the single points of failure in the system? | Nodes with high betweenness AND high degree that have no redundancy. If `get_session()` or `ApiClient` fails, what's the blast radius? | |
| 26 | Which Alembic migrations have the widest impact? | Migration 003 (MFA) and 004 (phone/notifications) touch the User table, which connects to 76+ nodes. A migration failure here is catastrophic. | |
| 27 | What happens if the Vertex AI Search datastore is unavailable? | RAG depends on vector search. Trace the fallback path. Does the system degrade gracefully or hard-fail? | |
| 28 | If Spanner Graph goes down, does the system still function? | The graph backend is swappable (`GRAPH_BACKEND=none`). But does the code actually handle `None` graph client everywhere? | |

---

## 6. Regulatory Compliance & Product (PRODUCT)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 29 | Which Indonesian regulations (POJK, UUPT, IDX) are connected to which red flag detectors? | Compliance completeness: every regulation should map to at least one detector. Missing connections = uncovered compliance risks. | |
| 30 | How does the GCG governance matrix connect to the 4-agent pipeline? | The matrix defines what to check. The agents do the checking. Trace the connection to verify nothing falls through the cracks. | |
| 31 | Which BOD/BOC charter requirements are covered by the extraction agent vs not? | The charters define what MoM content is required. If the extraction agent doesn't extract a required field, that's a product gap. | |
| 32 | What is the connection between obligation reminders and WhatsApp delivery? | After session 25, obligation deadlines should trigger notifications. Trace the full path from `check_obligation_deadlines()` to `send_obligation_reminder()`. | |

---

## 7. Evolution & Refactoring (future)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 33 | Which communities have the lowest cohesion scores? | Low cohesion = the community is a grab-bag, not a real module. These are candidates for splitting or reorganizing. | |
| 34 | If we extract `auth/` into a standalone microservice, what breaks? | The auth module (RBAC, MFA, IAP) is used by every router. Trace all consumers to estimate extraction cost. | |
| 35 | What would it take to make the Contract pipeline fully independent from the MoM pipeline? | They share `ancol-common`, `Document` model, `get_session()`, and state machine. Quantify the shared surface. | |
| 36 | Which INFERRED edges in the graph should be verified or removed? | 109 inferred edges on `Document`, 99 on `UserRole`, 88 on `ProcessingMetadata`. Some may be false positives. Systematic verification improves graph accuracy. | |

---

## Query Log

Track answers here as questions are explored:

| Date | # | Question | Key Finding | Follow-up |
|------|---|----------|-------------|-----------|
| 2026-04-17 | 2 | Extraction Agent bridges 9 communities | First agent in pipeline, output schema shared by all downstream. Schema change = 9 communities affected. | Q3: ProcessingMetadata impact |
| 2026-04-17 | 1 | Document lifecycle | 111 edges, 7 communities, 14-state machine. Never touches Graph Client directly (clean separation). | Q21: State machine detail |
| | | | | |

---

## How to add new questions

When you discover something surprising during development:

1. Run `/graphify query "<what surprised you>"`
2. If the answer reveals a non-obvious connection, add the question to the relevant section above
3. Tag it with impact category and note the date
4. Run `/graphify --update` after major code changes to keep the graph current
