# Full Throttle Platform — Architecture Diagrams (Mermaid)

## 1. System Architecture (Deployment View)

```mermaid
graph TB
    subgraph Internet["🌐 Internet"]
        Owner["📱 Owner (SMS/Email)"]
        Lead["👤 Lead (Web Form / Call / LSA)"]
        GBP["📊 Google Business Profile"]
        CRM["🗄️ Jobber / HCP CRM"]
        CMS["📝 WordPress / Wix CMS"]
    end

    subgraph DO["🖥️ DigitalOcean Droplet"]
        subgraph Gateway["🚪 Hermes Gateway (per-client profile)"]
            SMSAdapter["📨 SMS Adapter<br/>(Twilio)"]
            WebhookAdptr["🪝 Webhook Adapter<br/>(api_server)"]
            CronSched["⏰ Cron Scheduler"]
        end

        subgraph Supervisor["🧠 Supervisor Agent"]
            Router["↗️ Task Router"]
            Policy["🛡️ Policy Engine"]
            Approvals["✅ Approval Queue"]
            Reporter["📋 Weekly Reporter"]
        end

        subgraph Workers["👷 Worker Agents (delegate_task)"]
            LeadAgent["⚡ Lead-Response<br/>Agent"]
            RepAgent["⭐ Reputation<br/>Agent"]
            GBPAgent["🏢 GBP<br/>Agent"]
            ContentAgent["✍️ Content<br/>Agent"]
        end

        subgraph State["💾 Per-Profile State"]
            Config["config.yaml"]
            DotEnv[".env (secrets)"]
            Memories["memories/<br/>MEMORY.md, USER.md"]
            StateDB["state.db<br/>(SQLite+FTS5)"]
            AuditLog["audit.log<br/>(append-only)"]
        end
    end

    Owner -->|"SMS: 'update headline...'"| SMSAdapter
    Lead -->|"POST /webhooks/lead"| WebhookAdptr
    CronSched -->|"9am Mon/Wed/Fri"| Supervisor

    SMSAdapter --> Supervisor
    WebhookAdptr --> Supervisor
    CronSched --> Supervisor

    Supervisor --> Router
    Router -->|"delegate_task"| LeadAgent
    Router -->|"delegate_task"| RepAgent
    Router -->|"delegate_task"| GBPAgent
    Router -->|"delegate_task"| ContentAgent

    LeadAgent -->|"sync lead"| CRM
    LeadAgent -->|"first-touch reply"| Owner
    LeadAgent -->|"notify"| Owner
    LeadAgent --> AuditLog

    RepAgent -->|"request review"| Owner
    RepAgent -->|"draft reply"| GBP
    RepAgent --> Approvals
    RepAgent --> AuditLog

    GBPAgent -->|"post / Q&A"| GBP
    GBPAgent --> AuditLog

    ContentAgent -->|"publish blog post"| CMS
    ContentAgent --> Approvals
    ContentAgent --> AuditLog

    Supervisor --> Reporter
    Reporter -->|"weekly summary"| Owner

    Router -.-> Config
    Router -.-> DotEnv
    Router -.-> Memories
    Router -.-> StateDB

    style DO fill:#1a1a2e,stroke:#e94560,color:#fff
    style Gateway fill:#16213e,stroke:#0f3460,color:#fff
    style Supervisor fill:#16213e,stroke:#0f3460,color:#fff
    style Workers fill:#16213e,stroke:#0f3460,color:#fff
    style State fill:#0f3460,stroke:#533483,color:#fff
```

## 2. Inbound Lead Flow (Flow A — Top Revenue Lever)

```mermaid
sequenceDiagram
    actor Lead as 👤 Lead
    participant Form as Web Form
    participant GW as 🪝 Gateway<br/>Webhook
    participant Sup as 🧠 Supervisor
    participant LR as ⚡ Lead-Response<br/>Agent
    participant CRM as 🗄️ Jobber/HCP
    participant Owner as 📱 Owner
    
    Lead->>Form: Submit form (name, phone, email, message)
    Form->>GW: POST /webhooks/lead (HMAC)
    GW->>GW: Validate HMAC secret
    GW->>Sup: Route new lead event
    
    Note over Sup: Spawn Lead-Response agent<br/>within seconds
    
    Sup->>LR: delegate_task(goal="Handle new lead...")
    LR->>LR: Parse lead data
    LR->>LR: Qualify (res/commercial, urgency)
    
    par Parallel Actions
        LR->>Lead: SMS first-touch reply<br/>"Hi {name}, we got your inquiry..."
        LR->>CRM: sync_lead.py → create contact + lead
    end
    
    LR->>Owner: Notify: "New lead: {name} {phone}<br/>from {source} — replied"
    LR-->>Sup: Summary: lead ID, actions taken
    Sup->>Sup: Log to audit trail
    
    Note over Lead,Owner: ⏱️ Target SLA: < 60 seconds
```

## 3. Owner Command Flow (Flow B — Human Override)

```mermaid
sequenceDiagram
    actor Owner as 📱 Owner
    participant GW as 🚪 Gateway<br/>SMS Adapter
    participant Sup as 🧠 Supervisor
    participant Worker as 👷 Content/Website<br/>Agent
    participant Adapter as 🔌 Publishing<br/>Adapter
    participant CMS as 📝 WordPress/CMS
    
    Owner->>GW: SMS: "update homepage headline to X"
    GW->>Sup: Route owner message
    
    Note over Sup: Verify owner identity<br/>(allowed_users check)
    
    Sup->>Worker: delegate_task(goal="Update homepage headline")
    
    Worker->>Worker: Generate execution plan (JSON)
    Note over Worker: {intent, target, actions}
    
    alt Is risky/destructive?
        Worker->>Owner: "I plan to: [actions].<br/>Reply /approve or /deny"
        Owner->>Worker: "/approve"
    end
    
    Worker->>Adapter: Apply change via configured adapter
    
    alt wordpress-rest
        Adapter->>CMS: POST /wp-json/wp/v2/pages/{id}<br/>(Basic Auth with App Password)
    else proxy-subdir
        Adapter->>CMS: git commit + push →<br/>Cloudflare Worker deploys
    else manual
        Adapter->>Adapter: Write outbox file for human
    end
    
    Worker->>Worker: Log execution plan + result to audit
    Worker-->>Sup: Summary: "Done — live at {url}"
    Sup->>Owner: SMS: "Done — live at<br/>https://client.com/new-headline"
```

## 4. Autonomous Cadence Flow (Flow C — Cron-Driven)

```mermaid
graph TB
    Cron["⏰ Cron Tick<br/>e.g. Mon 9am"] --> Sup["🧠 Supervisor"]
    
    Sup --> FanOut{"delegate_task<br/>(parallel workers)"}
    
    subgraph Content["✍️ Content Worker"]
        C1["Research local topic<br/>(SEMrush keywords)"] --> C2["Draft blog post<br/>(real local data)"]
        C2 --> C3["Publish via adapter<br/>(CMS / proxy-subdir)"]
    end
    
    subgraph Reviews["⭐ Reviews Worker"]
        R1["Check CRM for<br/>completed jobs"] --> R2{"Already<br/>requested?"}
        R2 -->|"no (dedup check)"| R3["Send review request<br/>SMS/email"]
        R2 -->|"yes"| Skip["Skip"]
        R3 --> R4["Fetch new reviews<br/>from GBP"]
        R4 --> R5["AI-draft replies"]
        R5 --> R6{"Negative<br/>review?"}
        R6 -->|"yes"| Approve["→ Approval queue<br/>(owner must approve)"]
        R6 -->|"no"| Post["Auto-post reply"]
    end
    
    subgraph Social["📱 Social Worker (basics)"]
        S1["Pick real photos<br/>+ recent reviews"] --> S2["Schedule 2-3 posts/week"]
        S2 --> S3["GBP + Facebook<br/>+ Nextdoor"]
    end
    
    subgraph Report["📋 Weekly Report"]
        W1["Compile: leads, reviews,<br/>rankings, content"] --> W2["SMS/email summary<br/>to owner"]
    end
    
    FanOut --> Content
    FanOut --> Reviews
    FanOut --> Social
    FanOut --> Report
    
    Content --> Audit["📝 Audit Log<br/>(append-only)"]
    Reviews --> Audit
    Social --> Audit
    
    style Cron fill:#e94560,stroke:#ff6b6b,color:#fff
    style Approve fill:#ffd700,stroke:#ffaa00,color:#000
    style Audit fill:#533483,stroke:#7b68ee,color:#fff
```

## 5. Client Onboarding Flow (Flow E — intake → live)

```mermaid
flowchart TD
    Start(["📋 Intake form filled"]) --> Validate{"Validate intake.json<br/>slug, business_name,<br/>site.mode, adapter"}
    
    Validate -->|"invalid"| Fail(["❌ Die with error"])
    Validate -->|"valid"| Mode{site.mode?}
    
    Mode -->|"augment<br/>(has existing site)"| PickAdapter{"Pick adapter"}
    Mode -->|"greenfield<br/>(no site)"| Deferred(["⏸️ Deferred<br/>clone Astro template"])
    
    PickAdapter -->|"WordPress"| WP["wordpress-rest"]
    PickAdapter -->|"subdirectory"| Proxy["proxy-subdir"]
    PickAdapter -->|"fallback"| Manual["manual"]
    
    WP --> CreateProfile
    Proxy --> CreateProfile
    Manual --> CreateProfile
    
    CreateProfile["1️⃣ Create profile<br/>hermes profile create SLUG"] --> WriteConfig["2️⃣ Write config.yaml<br/>site_type, adapter, model,<br/>platforms, terminal.cwd"]
    
    WriteConfig --> WriteEnv["3️⃣ Write .env (chmod 600)<br/>API keys: Anthropic, Twilio,<br/>WP_APP_PASSWORD, Jobber, etc."]
    
    WriteEnv --> InstallSkills["4️⃣ Install platform skills<br/>→ profile/skills/<br/>content-publisher<br/>review-automation<br/>social-scheduler<br/>lead-response"]
    
    InstallSkills --> SeedContext["5️⃣ Seed context<br/>memories/MEMORY.md<br/>memories/USER.md<br/>AGENTS.md"]
    
    SeedContext --> CreateCrons["6️⃣ Create cron jobs<br/>reviews: daily 9am<br/>social: Mon/Wed/Fri 10am<br/>content: Mon 9am<br/>report: Mon 8am"]
    
    CreateCrons --> WriteRunbook["7️⃣ Write NEXT_STEPS.md<br/>manual steps for operator"]
    
    WriteRunbook --> StartGateway["8️⃣ Start gateway<br/>hermes -p SLUG gateway"]
    
    StartGateway --> Welcome["📱 Send welcome SMS<br/>to owner → LIVE"]
    
    style Start fill:#00b894,stroke:#55efc4,color:#000
    style Welcome fill:#00b894,stroke:#55efc4,color:#000
    style Fail fill:#d63031,stroke:#ff7675,color:#fff
    style Deferred fill:#636e72,stroke:#b2bec3,color:#fff
```

## 6. Onboarding Script Profile Tree

```mermaid
graph LR
    subgraph Repo["full-throttle-platform/"]
        Skills["skills/"]
        Onboard["scripts/onboard_client.py"]
        Intake["intake.json + secrets.json"]
    end
    
    subgraph Profile["~/.hermes/profiles/mrfence/"]
        direction TB
        Config2["config.yaml<br/>(site_type, adapter, model)"]
        Env2[".env<br/>(ANTHROPIC_API_KEY, TWILIO_*,...)"]
        Skills2["skills/<br/>├─ content-publisher/<br/>├─ review-automation/<br/>├─ social-scheduler/<br/>└─ lead-response/"]
        Mem["memories/<br/>├─ MEMORY.md<br/>└─ USER.md"]
        Agents["AGENTS.md<br/>(brand voice, hard rules)"]
        State2["state.db<br/>(SQLite + FTS5)"]
        NextSteps["NEXT_STEPS.md<br/>(operator runbook)"]
    end
    
    Onboard -->|"copies"| Skills2
    Onboard -->|"generates"| Config2
    Onboard -->|"renders"| Env2
    Onboard -->|"seeds"| Mem
    Onboard -->|"seeds"| Agents
    Onboard -->|"writes"| NextSteps
    Onboard -->|"creates"| State2
    
    Skills -.->|"source"| Skills2
    
    style Repo fill:#16213e,stroke:#0f3460,color:#fff
    style Profile fill:#0f3460,stroke:#533483,color:#fff
```

## 7. Approval & Governance State Machine

```mermaid
stateDiagram-v2
    [*] --> PlanGenerated: Agent creates execution plan
    
    PlanGenerated --> LowRisk: Pre-approved action
    PlanGenerated --> NeedsApproval: Risky/destructive action
    
    LowRisk --> Executing: Auto-proceed
    NeedsApproval --> PendingApproval: SMS owner with plan
    
    PendingApproval --> Executing: Owner: /approve
    PendingApproval --> RolledBack: Owner: /deny
    PendingApproval --> TimedOut: No response (timeout)
    
    TimedOut --> RolledBack: Default = safe (deny)
    
    Executing --> Snapshot: Snapshot prior state
    Snapshot --> Mutate: Apply changes
    
    Mutate --> Success: Mutation OK
    Mutate --> Failed: Mutation error
    
    Failed --> RolledBack: git revert / WP restore
    
    Success --> AuditLogged: Log: timestamp, agent, tool, payload
    RolledBack --> AuditLogged: Log rollback
    
    AuditLogged --> NotifyOwner: "Done" or "Rolled back"
    NotifyOwner --> [*]
```

## 8. Scaling Path (Profiles → Kanban)

```mermaid
graph LR
    subgraph Phase1["Phase 1: Pilot (1-20 clients)"]
        P1["One PROFILE per client<br/>One GATEWAY per profile<br/>Hard isolation"]
    end
    
    subgraph Phase2["Phase 2: Scale (20-50 clients)"]
        P2["KANBAN dispatcher<br/>Worker fleet<br/>Board = hard boundary<br/>Tenant = per-client namespace"]
    end
    
    subgraph Phase3["Phase 3: Enterprise (50+)"]
        P3["Containerized workers<br/>Job queue<br/>Auto-scaling<br/>Config migration,<br/>not re-architecture"]
    end
    
    Phase1 -->|"grows past ~20"| Phase2
    Phase2 -->|"grows past ~50"| Phase3
    
    style Phase1 fill:#00b894,stroke:#55efc4,color:#000
    style Phase2 fill:#fdcb6e,stroke:#ffeaa7,color:#000
    style Phase3 fill:#e17055,stroke:#fab1a0,color:#000
```
