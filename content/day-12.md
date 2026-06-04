# Day 12 — Shared flows, flow hooks & reuse (Week 2 capstone)

> **Bottom line:** You'll extract cross-cutting logic (FAPI header checks, error formatting, logging) into a **shared flow**, call it from any proxy with **FlowCallout**, and attach it to *every* proxy in an environment with a **flow hook** — then assemble a clean "house style" proxy.

> **Builds on Days 5–11:** every policy you've written is a candidate for sharing. Today you stop copy-pasting them.

## Why this matters

Across a bank's API estate, the same 8–10 policies repeat in every proxy: spike arrest, FAPI header validation, correlation id, standard error mapping, audit logging. Copy-paste is a governance failure — fix a bug in one place and 40 proxies still have it. Shared flows make cross-cutting concerns **write-once, enforce-everywhere**.

## Shared flow vs flow callout vs flow hook

| Concept | What it is |
|---------|-----------|
| **Shared flow** | A standalone bundle of policies — like a proxy with no endpoints, deployable on its own |
| **FlowCallout** | A policy you put *inside a proxy* to invoke a shared flow at a chosen point |
| **Flow hook** | An environment-level attachment that runs a shared flow **automatically** for *all* proxies (pre-proxy, post-proxy, etc.) — no per-proxy edit |

## Build a shared flow

A shared flow bundle mirrors a proxy bundle but uses `sharedflowbundle/` and `sharedflows/` instead of `apiproxy/proxies`:

```bash
mkdir -p sf-fapi-inbound/sharedflowbundle/{policies,sharedflows}

cat > sf-fapi-inbound/sharedflowbundle/sf-fapi-inbound.xml <<'XML'
<SharedFlowBundle name="sf-fapi-inbound" revision="1">
  <DisplayName>sf-fapi-inbound</DisplayName>
</SharedFlowBundle>
XML

# the shared flow definition (entry point)
cat > sf-fapi-inbound/sharedflowbundle/sharedflows/default.xml <<'XML'
<SharedFlow name="default">
  <Step><Name>SA-Smooth</Name></Step>
  <Step><Name>RF-MissingFapiHeader</Name>
    <Condition>request.header.x-fapi-interaction-id = null</Condition>
  </Step>
  <Step><Name>AM-EnsureInteractionId</Name></Step>
</SharedFlow>
XML
```

Add the referenced policies into `sf-fapi-inbound/sharedflowbundle/policies/` (reuse `SA-Smooth.xml`; create the two below):

```xml
<!-- policies/RF-MissingFapiHeader.xml -->
<RaiseFault name="RF-MissingFapiHeader">
  <FaultResponse>
    <Set>
      <StatusCode>400</StatusCode>
      <Payload contentType="application/json">{"Code":"400 BadRequest","Errors":[{"ErrorCode":"UK.OBIE.Header.Missing","Message":"x-fapi-interaction-id is required."}]}</Payload>
    </Set>
  </FaultResponse>
</RaiseFault>
```

```xml
<!-- policies/AM-EnsureInteractionId.xml : echo it on the response for correlation -->
<AssignMessage name="AM-EnsureInteractionId">
  <AssignVariable>
    <Name>fapi.interactionId</Name>
    <Template>{request.header.x-fapi-interaction-id}</Template>
    <Value>{createUuid()}</Value>
  </AssignVariable>
</AssignMessage>
```

Deploy the shared flow like a proxy:

```bash
apigeecli sharedflows create bundle \
  --name sf-fapi-inbound \
  --sf-folder ./sf-fapi-inbound/sharedflowbundle \
  --org "$ORG" --token "$TOKEN"

apigeecli sharedflows deploy \
  --name sf-fapi-inbound --rev 1 \
  --org "$ORG" --env "$ENV" --ovr --wait --token "$TOKEN"
```

## Call it from a proxy (FlowCallout)

```xml
<!-- policies/FC-FapiInbound.xml -->
<FlowCallout name="FC-FapiInbound">
  <DisplayName>FC-FapiInbound</DisplayName>
  <SharedFlowBundle>sf-fapi-inbound</SharedFlowBundle>
</FlowCallout>
```

Attach in the proxy's PreFlow.Request:

```xml
<PreFlow name="PreFlow">
  <Request><Step><Name>FC-FapiInbound</Name></Step></Request>
  <Response/>
</PreFlow>
```

## Or attach it to everything (flow hook)

A **flow hook** binds a shared flow to a position for *all* proxies in the environment. Positions: `pre-proxy`, `post-proxy`, `pre-target`, `post-target`.

```bash
# attach sf-fapi-inbound to the pre-proxy hook of this environment
apigeecli flowhooks attach \
  --name pre-proxy \
  --sharedflow sf-fapi-inbound \
  --org "$ORG" --env "$ENV" --token "$TOKEN"
```

Now **every** proxy in `eval` runs FAPI header validation first — even ones you haven't written yet. That's platform-level governance.

> **Use a flow hook for guarantees you want unconditional** (security headers, global rate limiting, audit logging). Use a **FlowCallout** when only *some* proxies need the logic, or when ordering relative to other in-proxy steps matters.

## Capstone — the "house style" proxy

Assemble everything from Week 2 into one clean AISP-shaped proxy:

1. PreFlow runs `FC-FapiInbound` (shared) → `Q-PerApp` (quota).
2. Conditional flows for `GET /accounts`, `GET /accounts/{id}/balances`, `GET /accounts/{id}/transactions`, each running `EV-AccountId`.
3. TargetEndpoint uses the `core-banking` **TargetServer** and a **ResponseCache** for the (mock) reference data.
4. A full **FaultRules + DefaultFaultRule** block returning OBIE errors.
5. PostFlow adds standard headers and echoes `fapi.interactionId`.

```bash
apigeecli apis create bundle --name aisp-house-style --proxy-folder ./aisp-house-style/apiproxy --org "$ORG" --token "$TOKEN"
apigeecli apis deploy --name aisp-house-style --rev 1 --org "$ORG" --env "$ENV" --ovr --wait --token "$TOKEN"

# missing FAPI header → 400 from the shared flow (via flow hook OR flow callout)
curl -s -o /dev/null -w "%{http_code}\n" "https://$RUNTIME_HOST/aisp-house-style/accounts"
# with the header → proceeds
curl -s -o /dev/null -w "%{http_code}\n" -H "x-fapi-interaction-id: $(uuidgen)" "https://$RUNTIME_HOST/aisp-house-style/accounts"
```

## Recap — you can now…

- Build, deploy, and version a **shared flow**.
- Invoke it per-proxy with **FlowCallout**, or globally with a **flow hook**.
- Assemble a maintainable proxy where cross-cutting concerns live in **one** place.

## Check yourself

1. You must guarantee *every* proxy logs an audit event. FlowCallout or flow hook?
2. What's the structural difference between a shared flow bundle and a proxy bundle?
3. Why is copy-pasting the spike-arrest policy into 40 proxies a governance problem?

**Next:** Day 13 — Week 3 (Security) opens with **app identity**: API keys, API products, developer apps, and `VerifyAPIKey`.
