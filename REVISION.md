# Full Throttle Marketing — Architecture v2

## 1. Core Positioning

Full Throttle is an AI-powered marketing operations platform for local service businesses.

The platform is designed around one core business outcome:

> Convert more inbound leads into booked jobs while increasing local trust signals.

The system is intentionally **augment-first**, not replacement-first.

We do not attempt to replace:

* the client’s website
* CRM/FSM
* operational workflows
* existing marketing stack

Instead, the platform automates and coordinates:

* lead response
* review generation
* GBP activity
* lightweight content publishing
* reporting and diagnostics

The architecture prioritizes:

* operational reliability
* low onboarding friction
* measurable ROI
* constrained automation

Not:

* unrestricted autonomy
* generic AI orchestration
* “AI employee” demos

---

# 2. Product Scope (v2)

## Included in v2

### Primary Revenue Drivers

1. Lead-response automation
2. Review/reputation automation
3. GBP optimization and posting

### Supporting Systems

4. Lightweight SEO publishing
5. Weekly reporting
6. Owner command interface (SMS)

---

## Explicitly Deferred

The following are intentionally postponed until retention and operational stability are proven:

* autonomous ad management
* multi-platform social automation
* advanced website rebuilding
* fully autonomous outbound marketing
* recursive agent swarms
* generalized multi-channel orchestration

---

# 3. Architectural Philosophy

## Constraint-First Agents

Agents are not treated as autonomous decision-makers.

They are:

* bounded workflow executors
* tool-driven operators
* supervised automation layers

The system favors:

* deterministic actions
* structured outputs
* explicit approvals
* auditable execution

Over:

* open-ended autonomy
* freeform planning
* persistent self-directed behavior

---

# 4. Runtime Model

Hermes remains the orchestration runtime.

We use:

* profiles for tenant isolation
* gateway for inbound events
* delegation for bounded worker execution
* cron for scheduled workflows

We intentionally avoid:

* custom orchestration engines
* separate workflow DAG systems
* unnecessary microservices

---

# 5. Tenant Isolation

Each client operates as an isolated Hermes profile.

```
~/.hermes/profiles/<client>/
```

Contains:

* config.yaml
* .env
* memories/
* skills/
* state.db
* audit logs

Isolation guarantees:

* separate credentials
* separate memories
* separate execution history
* separate tool permissions

Profiles are the primary multi-tenant boundary in v2.

---

# 6. Narrowed Agent Topology

## Supervisor Agent

Responsibilities:

* route tasks
* enforce policy
* manage approvals
* compile reports
* coordinate workers

The Supervisor does NOT directly mutate external systems.

---

## Worker Agents

### A. Lead Response Agent (highest priority)

Handles:

* inbound form submissions
* missed-call text backs
* LSA responses
* lead qualification
* appointment routing

Business rationale:

* first-response speed has the highest direct revenue impact

Capabilities:

* SMS/email replies
* qualification workflows
* CRM sync
* booking coordination

Guardrails:

* cannot modify website content
* cannot alter CRM schema
* restricted messaging templates
* rate-limited communication

---

### B. Reputation Agent

Handles:

* review request automation
* AI-assisted review replies
* review monitoring
* escalation of negative reviews

Business rationale:

* review velocity and responsiveness strongly impact local rankings and conversion

Guardrails:

* all negative-review replies require approval
* generated responses must conform to templates
* duplicate review requests prevented via idempotency tracking

---

### C. GBP Agent

Handles:

* Google Business Profile posts
* Q&A suggestions
* service/category audits
* update reminders

Guardrails:

* no autonomous business detail edits
* factual fields require owner approval
* post scheduling only

---

### D. Content Agent

Handles:

* localized blog drafts
* lightweight SEO content
* publishing via adapter

Publishing is constrained to:

* blog/news sections
* approved landing pages
* metadata updates

The agent cannot:

* redesign pages
* alter navigation
* overwrite homepage layouts

---

# 7. Publishing Adapter System

The publishing adapter abstraction remains core.

## Supported v2 Adapters

### wordpress-rest

Primary supported CMS.

### proxy-subdir

Cloudflare Worker reverse-proxy serving content at:

```
client.com/blog
```

This enables:

* SEO continuity
* no migration requirement
* centralized infrastructure management

---

## Deferred Adapters

Deferred until demand justifies them:

* Wix
* Webflow
* custom webhook adapters
* Astro greenfield mode

---

# 8. Operational Governance Layer

This becomes a first-class architectural concern in v2.

---

## A. Execution Plans

Before performing mutations, agents generate:

```json
{
  "intent": "update_blog_post",
  "target": "/blog/summer-fence-maintenance",
  "actions": [
    "update title",
    "replace CTA",
    "publish metadata"
  ]
}
```

The plan is:

* logged
* validated
* optionally approved

before execution.

---

## B. Tool Permission Scopes

Each worker has restricted tools.

Example:

| Agent         | Allowed Actions                 |
| ------------- | ------------------------------- |
| Lead Response | SMS, CRM create/update          |
| Reputation    | Review replies, review requests |
| GBP           | GBP posting only                |
| Content       | CMS content publishing only     |

No worker receives unrestricted terminal or admin access in production.

---

## C. Idempotency

Every external action receives:

* unique execution IDs
* deduplication checks
* retry-safe semantics

Prevents:

* duplicate SMS
* duplicate reviews
* repeated CRM writes

---

## D. Audit Logging

Every mutation records:

* timestamp
* agent
* tool used
* input payload
* output payload
* approval state
* rollback reference

Logs are append-only.

---

## E. Rollback System

Before CMS mutations:

* snapshot previous state
* retain rollback version
* allow one-click revert

Critical for:

* accidental overwrites
* malformed content
* hallucinated edits

---

# 9. Inbound Lead Flow (Primary Workflow)

```
Lead arrives
    ↓
Gateway receives webhook
    ↓
Supervisor validates payload
    ↓
Lead Response Agent executes
    ↓
Qualification + response
    ↓
CRM sync
    ↓
Owner notification
    ↓
Audit log entry
```

Target SLA:

* first response under 60 seconds

This is the primary business KPI.

---

# 10. Review Automation Flow

```
Job completion event
    ↓
CRM/FSM webhook
    ↓
Reputation Agent
    ↓
Review request generated
    ↓
Delivery via SMS/email
    ↓
Tracking + deduplication
```

Negative review handling:

* flagged
* summarized
* approval required before public response

---

# 11. CRM/FSM Integration Philosophy

The platform augments operational systems.

It does not replace:

* ServiceTitan
* Jobber
* Housecall Pro
* existing CRMs

CRM/FSM systems remain the source of truth for:

* customers
* jobs
* scheduling
* invoices

Full Throttle owns:

* marketing automation
* response workflows
* reputation orchestration
* lightweight publishing

---

# 12. Observability

Operational visibility is mandatory in v2.

Required interfaces:

* execution timeline
* approval queue
* message replay
* lead tracking
* error monitoring
* tool execution logs
* cost tracking

Agent systems without observability become unmaintainable.

---

# 13. Scaling Strategy

## Phase 1 — Pilot

One profile per client on a single runtime node.

Focus:

* reliability
* onboarding
* retention
* operational safety

---

## Phase 2 — Worker Fleet

Introduce:

* queue-backed execution
* distributed workers
* tenant scheduling

Only after:

* stable workflows
* repeatable onboarding
* validated ROI

---

# 14. Key Strategic Principle

The system is not competing on:

* “most autonomous AI”
* “largest agent swarm”
* generalized intelligence

It competes on:

* fastest lead response
* operational reliability
* easiest onboarding
* measurable ROI
* preservation of existing business infrastructure

The platform succeeds if it reliably increases:

* booked jobs
* review volume
* local trust
* owner responsiveness

while requiring minimal workflow disruption.
