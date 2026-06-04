# Day 28 — Observability: analytics, logging, tracing & debug

> **Bottom line:** You'll instrument your proxies for production visibility — **Analytics** for trends, **MessageLogging → Cloud Logging** for audit, **distributed tracing** for latency, and **Debug sessions** for live troubleshooting — without leaking sensitive data.

> **Builds on Day 17 & 12:** logging reuses your data-masking discipline and lives in shared flows.

## Why this matters

You can't operate what you can't see, and in banking you *must* be able to reconstruct what happened to any transaction. Apigee gives four complementary lenses; using the right one for each question (trend vs audit vs latency vs "why did *this* call fail") is an operations skill.

## The four lenses

| Lens | Answers | Latency | Retention |
|------|---------|---------|-----------|
| **Analytics** | "What's my traffic/error/latency *trend*?" | minutes | long (built-in) |
| **MessageLogging → Cloud Logging** | "What exactly happened on *this* call?" (audit) | seconds | your retention policy |
| **Distributed tracing (Cloud Trace)** | "*Where* did the latency go across hops?" | seconds | configurable |
| **Debug session** | "Let me watch live calls flow through policies *right now*" | live | short (capture window) |

## Analytics

Apigee collects analytics automatically — per-proxy traffic, latency percentiles, error rates, by environment/region/app. Add **custom dimensions** by setting analytics variables in a policy:

```xml
<!-- surface OB-specific dimensions into analytics -->
<AssignMessage name="AM-AnalyticsDims">
  <AssignVariable><Name>ax.consentStatus</Name><Ref>consent.status</Ref></AssignVariable>
  <AssignVariable><Name>ax.tppSoftwareId</Name><Ref>app.software_id</Ref></AssignVariable>
  <AssignVariable><Name>ax.obApi</Name><Value>aisp</Value></AssignVariable>
</AssignMessage>
```

Then build a **custom report** grouping by `ax.obApi` and `responseStatusCode` to watch AISP vs PISP error rates per TPP. Query via API:

```bash
apigeecli analytics reports ... # or the Apigee UI → Analyze → Custom Reports
```

## MessageLogging → Cloud Logging (audit trail)

`MessageLogging` ships structured logs to **Cloud Logging**. This is your regulator-grade audit trail — but **never log secrets, tokens, or PANs**.

```xml
<MessageLogging name="ML-Audit">
  <DisplayName>ML-Audit</DisplayName>
  <CloudLogging>
    <LogName>projects/{organization.name}/logs/apigee-ob-audit</LogName>
    <Message contentType="application/json">{
      "interactionId": "{fapi.interactionId}",
      "proxy": "{apiproxy.name}",
      "operation": "{request.verb} {proxy.pathsuffix}",
      "tpp": "{app.software_id}",
      "consentId": "{consent.id}",
      "status": "{response.status.code}",
      "latencyMs": "{client.received.end.timestamp}",
      "timestamp": "{system.timestamp}"
    }</Message>
    <ResourceType>apigee.googleapis.com/Environment</ResourceType>
    <Labels><Label><Key>env</Key><Value>{environment.name}</Value></Label></Labels>
  </CloudLogging>
</MessageLogging>
```

> **Log identifiers, not secrets.** Log the `consentId`, `interactionId`, `software_id`, status — never the access token, the JWS, account numbers, or the request body. Pair with the Day-17 mask config. Attach `ML-Audit` in **PostFlow.Response** *and* in the **DefaultFaultRule** so failures are audited too.

Query the audit trail:

```bash
gcloud logging read \
  'logName="projects/'"$PROJECT_ID"'/logs/apigee-ob-audit" AND jsonPayload.status>="400"' \
  --project "$PROJECT_ID" --limit 20 --format json | jq '.[].jsonPayload'
```

## Distributed tracing

Apigee X integrates with **Cloud Trace**. Enable it per environment to see spans for each proxy, policy group, and the backend call — so you can attribute latency to *your* policies vs the core banking call.

```bash
apigeecli env trace enable --env prod --org "$ORG" \
  --endpoint cloudtrace.googleapis.com --sample 50 --token "$TOKEN"
```

> Sample (e.g. 50%) in prod to control cost; trace shows whether a slow `/transactions` is your proxy, the consent-store callout, or the core. Propagate `traceparent` to the backend so the trace spans your whole system.

## Debug sessions (live troubleshooting)

A **Debug session** captures real transactions and shows every policy's input/output — the single best tool for "why did this fail?". Start one from the CLI and replay a request:

```bash
# start a debug session on prod for ob-aisp rev 8
apigeecli apis debugsessions create --name ob-aisp --rev 8 \
  --env prod --org "$ORG" --token "$TOKEN"

# now send traffic; then fetch captured transactions
apigeecli apis debugsessions list --name ob-aisp --rev 8 --env prod --org "$ORG" --token "$TOKEN"
```

In the UI, each captured call shows the policy execution order you learned on Day 5, with variable values at each step (sensitive `private.*` and masked fields redacted).

## Lab — full observability on ob-aisp

1. Add `AM-AnalyticsDims` (PreFlow) and `ML-Audit` (PostFlow.Response **and** DefaultFaultRule).
2. Enable Cloud Trace at 100% on test; run the golden journey; open the trace and identify the slowest hop.
3. Query Cloud Logging for all `4xx`/`5xx` in the last hour and confirm **no token or account number** appears in any log line.
4. Start a Debug session, trigger a `403` consent failure, and walk the trace to the exact RaiseFault that produced it.

## Recap — you can now…

- Choose the right lens: **Analytics** (trend), **MessageLogging** (audit), **Trace** (latency), **Debug** (live).
- Emit a **safe, structured audit log** to Cloud Logging on success *and* failure.
- Attribute latency across hops and troubleshoot a live call to the exact policy.

## Check yourself

1. Which lens answers "where did the 800 ms go" across proxy + backend?
2. Name three things you must **never** put in a message log.
3. Why attach the audit MessageLogging to the DefaultFaultRule too?

**Next:** Day 29 — package and publish for the people who consume your APIs: **API products, the developer portal, monetization, and API hub**.
