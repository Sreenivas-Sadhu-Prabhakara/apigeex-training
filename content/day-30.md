# Day 30 — Production readiness & Open Banking capstone

> **Bottom line:** You'll run a go-live review over your Open Banking build — performance, resilience, multi-region, security hardening, and runbooks — and graduate with a production-readiness checklist you can defend to an auditor.

> **Builds on everything:** Day 30 doesn't add features; it makes what you built *operable, resilient, and compliant*.

## Why this matters

The gap between "it works in the demo" and "it survives Black Friday, a region outage, and an audit" is production readiness. In banking that gap is the whole job. Today turns your 29 days of building into something you can actually run.

## Performance & scaling

| Concern | What to do on Apigee X |
|---------|------------------------|
| **Latency budget** | Trace (Day 28) each hop; keep proxy overhead low — prefer declarative policies over JS; cache reference data and JWKS (Day 10) |
| **Backend protection** | SpikeArrest + Quota + ConcurrentRateLimit tuned to *real* backend limits (Day 6) |
| **Heavy policies** | Minimize per-request crypto; cache verified JWKS; avoid large JS payloads; stream don't buffer where possible |
| **Connection reuse** | Keep-alive to backends via TargetServer settings; right-size timeouts (`io.timeout.millis`) |
| **Load test** | Drive expected peak + headroom through `test`; watch p95/p99 and error rate, not just averages |

```widget
{"type":"chart","title":"A 200 ms latency budget, allocated","chartType":"doughnut","height":300,
 "data":{"labels":["Apigee policies","mTLS handshake (reused)","Consent/token checks","Core backend","Network"],
  "datasets":[{"data":[15,10,20,135,20],"backgroundColor":["#1a73e8","#8a5cf6","#e8710a","#0b8043","#9aa7b6"]}]},
 "caption":"Budget the whole path, then defend each slice. The backend usually dominates — which is why caching and pagination beat policy micro-tuning."}
```

## Resilience & multi-region

```text
Single region (eval)              Production (HA)
  europe-west2                      europe-west2  + europe-west1
  one instance                      instance per region, both attached to prod env
                                    global load balancer fails over on region loss
```

```bash
# add a second region for HA (production pattern)
apigeecli instances create --name inst-ew1 --location europe-west1 \
  --diskenckeyname "$KMS_KEY" --org "$ORG" --token "$TOKEN"
apigeecli instances attachments attach --name inst-ew1 --env prod --org "$ORG" --token "$TOKEN"
```

Resilience patterns to verify:

- **Backend failover** — TargetServer LoadBalancer with multiple servers + health monitors.
- **Graceful degradation** — if the consent store is down, fail *closed* (deny) for data, never fail open.
- **Idempotency** (Day 23) holds under retries and partial failures.
- **Circuit-breaking** — short timeouts + a fast OBIE error beat a hung request.

## Security hardening checklist (sign-off)

Walk this and cite the enforcing policy for each:

```text
[ ] mTLS required on ALL token + resource endpoints           (Day 16)
[ ] FAPI: PAR enforced, PS256 only, no RS256/none             (Day 18/19)
[ ] Access tokens certificate-bound; wrong-cert → 401         (Day 19/24)
[ ] private_key_jwt / tls_client_auth client auth only        (Day 18)
[ ] Detached JWS validated on writes; tamper → 401            (Day 23)
[ ] Consent status + expiry + permission enforced everywhere  (Day 21/22)
[ ] Threat protection + regex + CORS allowlist at the edge    (Day 17)
[ ] No secrets/PII in logs or traces; mask config applied     (Day 17/28)
[ ] Short-lived tokens; exact redirect_uri match; nonce/state (Day 18)
[ ] Quotas/spike arrest tuned per TPP                         (Day 6/13)
```

## Operability & runbooks

Production needs documented responses to predictable failures:

```text
Runbook: "TPP reports 403 on all AISP calls"
  1. Pull audit logs by software_id + interactionId (Day 28 query)
  2. Check consent status in store — Authorised? expired? revoked?
  3. Check token cnf thumbprint vs presented cert (cert rotation?)
  4. Check JWKS cache for the TPP — stale after their key rotation?
  Escalation: ... | Rollback: redeploy previous revision (Day 26)
```

Have runbooks for: certificate/key rotation (Day 16 references → zero downtime), TPP key rotation (JWKS cache flush), region failover drill, and revision rollback.

## Compliance & lifecycle

- **Auditability** — every transaction reconstructable from `interactionId` + audit log (Day 28).
- **Data residency** — runtime + analytics in `europe-west2` (Day 2); confirm no data leaves region.
- **Conformance** — run the OpenID FAPI + OBIE conformance suites against `test`; keep the pass report.
- **Versioning & deprecation** — `v3.1` and `v4.0` side by side (Day 25); published sunset dates via the portal.

## Capstone — production-readiness sign-off

Produce the deliverable that proves you're done:

1. **Run the golden journey** (Day 25) against a **multi-region prod** config.
2. **Kill a region** (detach one instance) mid-journey and confirm continuity via the other.
3. **Complete the hardening checklist** above, citing the policy/flow enforcing each line.
4. **Trigger and resolve** one runbook scenario using only logs/traces (no code reading).
5. **Export** your conformance + load-test + checklist artifacts as the go-live package.

```bash
# final proof: same golden journey, prod hostname, region failover survived
./scripts/golden-journey.sh https://api.demobank.example
# detach a region, re-run, expect identical success
apigeecli instances attachments detach --name inst-ew1 --env prod --org "$ORG" --token "$TOKEN"
./scripts/golden-journey.sh https://api.demobank.example   # still 2xx end-to-end
```

## You're done — what you can now do

Over 30 days you went from the architecture diagram to a **production-grade, FAPI-secured UK Open Banking platform** on Apigee X:

- **Build** proxies, flows, and the full policy toolkit (Weeks 1–2).
- **Secure** them with keys, OAuth, JWT, mTLS, threat protection, and **FAPI 1.0 Advanced** (Week 3).
- **Implement** consent, AISP, PISP, and DCR end to end (Week 4).
- **Operate** them with environments, CI/CD, observability, products, and production readiness (Week 5).

## Where to go next

- Run the **OpenID FAPI conformance suite** against your build and close any gaps.
- Explore **Apigee hybrid** if data sovereignty needs the runtime in your own GKE.
- Add **Event Notifications** (OBIE `event-subscriptions`) and **Variable Recurring Payments (VRP)** as the natural next OBIE families.
- Templatize your shared flows + estate as an internal **Open Banking accelerator** for the next team.

## Final check

1. Your consent store goes down. Do AISP data calls fail **open** or **closed** — and why?
2. Name the single artifact that lets you reconstruct any transaction for an audit.
3. A region fails. What keeps traffic serving, and what did you do on Day 2 to make that possible?

```widget
{"type":"quiz","title":"Final check — graduation","questions":[
  {"q":"Your consent store goes down. AISP data calls should fail…","options":["Closed — deny access","Open — allow access","Silently return 200 empty","Retry forever"],"answer":0,"explain":"Fail closed. Never serve account data without a verifiable Authorised consent — availability never trumps the consent guarantee."},
  {"q":"The single artifact that lets you reconstruct any transaction for an audit is…","options":["The structured audit log keyed by x-fapi-interaction-id","The proxy bundle XML","The API product definition","The TLS certificate"],"answer":0,"explain":"Per-transaction audit logs carrying the interaction id are your regulator-grade reconstruction trail (Day 28)."},
  {"q":"A region fails but traffic keeps serving because…","options":["A second regional instance is attached to prod and the global LB fails over","Apigee instantly rebuilds the region","The control plane serves the traffic","Clients retry until it works"],"answer":0,"explain":"Multi-region HA: instances in 2+ regions attached to the prod environment, with the global load balancer routing around the failed region."}
]}
```

**Congratulations — you've completed the 30-Day Apigee X Open Banking training.** Return to the [overview](index.html) any time, or fork the repo and adapt it for your own team.
