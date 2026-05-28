# Market Research — Fencing / Home-Services Vertical

The "why" behind the platform architecture. Findings from web research (May 2026) on how
fencing contractors actually find customers and make money. Architecture decisions in
`ARCHITECTURE.md` trace back to the facts here.

> Figures are US-market, fencing or close home-services-adjacent, from marketing-vendor
> blogs and cost-guide aggregators (Angi/HomeAdvisor) plus SEO/industry sources —
> directionally reliable, not audited. `[EST]` marks our inference vs sourced data.

## 1. Customer acquisition — ranked by jobs driven

1. **Speed-to-lead is the biggest lever.** 78% of customers hire the *first* responder;
   replying within 60s lifts conversion ~**391%**. (CallRail/Hatch)
2. **Google Local Services Ads (LSA / "Google Guaranteed")** — pay-per-lead, exclusive,
   top placement. Fencing closes at **40–50%** (caller already chose material/style).
3. **Google Business Profile + organic local SEO** — the free engine behind search/maps;
   reviews + photos drive map-pack clicks. SEO leads ≈ $0 at scale.
4. **Google Search Ads (PPC)** — high volume, lower close (~12% lead→customer vs ~31% LSA).
5. **Referrals / word-of-mouth** — highest trust, lowest cost, unpredictable volume. `[EST]`
6. **Lead marketplaces (Angi, HomeAdvisor, Thumbtack, Networx)** — easy volume but shared
   3–5 ways; ~70% of Angi leads reportedly don't answer/aren't qualified. Cost-per-booked-job
   2–4× exclusive channels.
7. **Meta/Facebook ads** — cheap leads (~$23) but low intent; retargeting/awareness.
8. **Nextdoor, yard signs, truck wraps, door hangers** — local brand reinforcement. `[EST]`

## 2. Lead economics

- **CPL by channel:** LSA ~$25–85 (home-services avg **$71**); Angi $25–120 (shared);
  HomeAdvisor $15–100 + ~$350/yr; Thumbtack $10–75 (shared); Facebook ~$23; Google PPC $40–60.
- **Conversion:** LSA ~31% lead→customer; PPC ~12%; avg home-services site CVR **7.33%**.
- **Cost-per-booked-job example:** $71 LSA lead @25% close = **$284/job**; $23 FB lead @12% =
  **$192/job**. A "good" lead = exclusive, answered, < ~10% of job value.

## 3. Job economics

- **Avg residential job** ~$4,000–12,000; priced **per linear foot** ($20–60 installed;
  chain link $8–40, wood $10–45). Commercial = larger, longer, lower-margin, bid-driven.
- **Margins:** gross **35–50%**, net 10–25%. Labor ≈ 50% of project cost.
- **Seasonality:** demand peaks spring/summer; CPCs peak May–Aug, drop Sep–Nov.
- **Buyer motives:** privacy ~45%, security ~30%, pet containment ~20%.

## 4. The funnel & the website's role

Path: trigger (privacy/pet/security) → Google search or map-pack → compares 2–3 contractors
via **reviews + photos** → calls the one that looks trustworthy and **responds fast**.
Decisions often happen in <60s.

- **Reviews:** ~87% won't consider a low-rated business; rating/volume gate the shortlist.
- **Real before/after photos:** strongest conversion element — +20–35% vs stock; video up to +80%.
- **Call-vs-bounce drivers:** clear service area + city pages, visible phone/CTA, fast load,
  trust signals (Google Guaranteed badge, real team photos, guarantees).

## 5. Local SEO — what moves the needle

- **Google Business Profile is the #1 lever.** Primary GBP category = top local-pack ranking
  factor (2026 survey); GBP signals ~32% of local-pack weight. For service-area businesses
  (most fence installers), proximity matters less, so **prominence + reviews dominate**.
- **Reviews = ~20% of local-pack influence** (up from 16%), and **velocity/recency now beat
  raw count** — 80 reviews with steady weekly flow beat 200 stale ones. First ~10 reviews
  give the biggest trust lift.
- **NAP consistency / citations** ~6–9% of signals — foundational, table-stakes, not a
  growth lever. Consistent NAP → 40% more likely to appear in local pack.

## 6. Website SEO structure for fencing

- **Per-service pages win** (wood/vinyl/aluminum/chain-link/repair/gates/commercial), each
  800–1,500 words with pricing, process, warranty, 5–8 FAQs.
- **Location pages are high-risk if templated.** Post-March-2024 core update, **>80% of
  doorway pages lost rankings** (one case −63% in 30 days). Safe: start with **5–8 top
  markets**, each genuinely unique (local projects, permits/HOA, real photos). Programmatic
  mass-generation is the main penalty risk.
- **Schema:** LocalBusiness + FAQ on every page, Service per service page, AreaServed for
  coverage. Plus Core Web Vitals, mobile-first, internal linking.

## 7. Content strategy & the AI-content constraint

- **Lead-earning topics:** cost guides, material comparisons, buying/budget guides, permit/HOA,
  climate-specific picks, high-intent commercial pages.
- **Google does not penalize AI per se** — it penalizes content made to manipulate rankings.
  Safe AI output must show **E-E-A-T**, especially first-hand *Experience*: real project
  photos, local pricing you've quoted, named author/owner bios, human review. **Design
  constraint: agents must inject real local data, not generic prose.**
- **Cadence:** consistency > volume; ~2–4 substantive posts/month.

## 8. Reviews & reputation

- **Velocity is a confirmed ranking factor**; steady recent reviews lift local rank ~5–10%
  and pull more clicks.
- **Post-job automated requests (within hours) raise response rates up to ~80%** — automating
  the *ask* is the highest-leverage review play.
- **Responding to reviews** is itself a signal Google uses and builds conversion trust.

## 9. Paid ads

- **Google PPC:** $18–65/click (home-services avg ~$6.55); 5–8% click→lead; CPL $25–75 in-season.
- **LSA:** pay-per-lead ~$71, invalid-lead credits, higher intent, 40–50% fence close.
- **Meta/Facebook:** $12–35/lead (avg ~$27.66, +21% YoY) — demand-generation, not capture.
- **Spend:** typical fence ad spend $3,000+/mo (test $1–2k; competitive metros $5–10k+);
  management fees separate.

## 10. Agency landscape & positioning

- **Typical bundle:** local SEO, GBP, Google/LSA/Meta management, content, reviews, web design.
- **Pricing:** contractor SEO+ads $1,000–5,000/mo; <$1M revenue $1,500–3,000; $2M+ $3,500–7,500.
- **Pilot's ~$2,500/mo** = basic-to-mid band.
- **Documented pain points:** 12-month lock-in; "reports that don't translate into phone
  calls"; vague optimization stalls; clients not owning their ad accounts; transparency gaps.
- **Players seen:** Hook Agency, Footbridge Media, Savo Group, Andrew Ryan Marketing,
  FencingLaunch, Clicks Geek, Deck & Fence Marketers.
- **Wedge for us:** transparency + no lock-in (the top complaints).

## 11. Existing-website clients (decisive for architecture)

- **Keep the existing site unless it's broken.** Migrations show **44–50% organic traffic
  loss** and avg **~523 days to recover**; you lose accumulated domain authority/backlinks.
  A *redesign* (same CMS/URLs) is safer than a *rebuild* (new platform).
- **Publishing into a site you don't own the code for:** WordPress **REST API** (most common
  contractor CMS); **Wix Data/CMS API**; generic **webhooks**; per-client "projects."
- **Locked/legacy platforms (ColdFusion, builder-locked):** no clean API — either hire dev
  access or **route around** the site. `[EST]`
- **The route-around wedge:** host new content on a **`/blog` subdirectory via reverse proxy**
  (Cloudflare Workers) on the client's own domain — subdirectories outperform subdomains
  (one case +40% organic) because Google treats subdomains as separate sites. Publishes on
  infra we control while keeping SEO equity on the client's domain.

## 12. Organic social media — trust surface, not lead engine

- **Honest ROI:** for local fencing, organic social is primarily a **credibility/proof layer**,
  not a direct lead engine. Attribution is weak; likes/follows are vanity. Direct-lead case
  studies almost always involve paid boosting. `[EST]` Treat organic-attributed leads as a minority.
- **Platform ranking (realistic payoff):** GBP posts (highest intent) → Facebook (35–65
  homeowner demo) → **Nextdoor** (high-trust, underrated; users 161% more likely interested
  in remodeling) → Instagram → YouTube/TikTok (secondary) → Pinterest (lowest).
- **Content that works:** before/after photos (3× shares) → time-lapse install videos →
  testimonials → educational → behind-the-scenes.
- **AI-content risk:** labeling content AI-generated **reduces engagement + purchase intent**
  (trust 3.0 vs 4.5 human); platform engagement collapsing (~79% YoY drop). The agent should
  **assist/schedule real job content, not auto-generate generic posts.**
- **Cadence:** 2–3 posts/week busy season, 1–2 slow. Consistency > volume.
- **Funnel role:** trust-check before calling, UGC/review amplification, retargeting
  feedstock, GBP freshness. **Vanity zones:** follower chasing, TikTok/Pinterest, daily posting.

## 13. Tool/CRM coexistence

Coexist, don't replace. Field-service/CRM: **ServiceTitan** (enterprise), **Jobber** (SMB),
**Housecall Pro** (small). Reputation/messaging: **Podium**, **Birdeye**. Best practice:
fire review requests on FSM job-completion; sync leads back into the client's pipeline.
Native integrations to Jobber/HCP/ServiceTitan/QuickBooks are table-stakes.

## Strategic takeaways

1. **Augment-first.** Most clients have a site; rebuilding risks 44–50% traffic loss. Default
   to working in place (CMS API / proxy-subdirectory); greenfield only for site-less/broken.
2. **Lead by reviews/GBP + speed-to-lead**, not by building websites — they work for every
   client regardless of platform and hit the biggest conversion levers.
3. **Real data over AI fluff** — both site content (E-E-A-T) and social (authenticity penalty)
   demand real photos/pricing; agents assist, humans/real-jobs supply the substance.
4. **Integrate the CRM/FSM layer**; own marketing + content + ads + GBP; sync leads back.
5. **Position on transparency + no lock-in** against the basic agency tier.

## Sources

Lead-gen & economics: Andrew Ryan Marketing; Blue Grid Media (LSA stats 2026); Ollyolly (Angi);
Home Service Direct; Angi & HomeAdvisor cost guides; BH Accounting; ArcSite; Minyona; LocaliQ;
CallRail. Local SEO & content: BrightLocal; clickrank; Local Dominator; Search Engine Journal;
Home Service Direct; The Fencing Marketers; RicketyRoo; Arc4; Google Search Central; ALM Corp;
Birdeye; MyBusinessFlow. Ads & agencies & existing-site: WebTheoryPPC; The Media Captain;
LeadSync; Search Engine Land; WebFX; Phlash Consulting; Contractor Marketing Pros; M.Wolf Media;
DreamHost; iPullRank/Marcel Digital; Wix Studio docs; RightBlogger; Semrush; Cloudflare;
ButterCMS; ContractorPlus; NiceJob; Jobber. Organic social: WebFX; BearFox Marketing;
FenceMarketingPros; Nextdoor/SEC case study; Buildertrend; International Outsourcing Group;
Improvado; dataslayer.ai; Springer/Nature AI-content study; LMB Marketing Group; Comrade.
