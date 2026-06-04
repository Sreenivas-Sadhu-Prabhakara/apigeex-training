# Day 17 — Threat protection, CORS & data masking

> **Bottom line:** You'll block malformed and malicious payloads with **JSONThreatProtection / RegularExpressionProtection**, enable **CORS** safely for browser TPPs, and **mask** sensitive fields so they never leak into Debug traces or logs.

> **Builds on Day 11 & 12:** these go in your shared inbound flow so every proxy is protected by default.

## Why this matters

A bank's edge is a target. Oversized JSON, deeply nested payloads, SQL/script injection, and content-type confusion are everyday attacks. And under GDPR/PSD2 you must ensure PANs, tokens, and PII don't end up in logs or traces. These policies are cheap insurance you attach once, centrally.

## JSON & XML threat protection

Reject structurally abusive payloads *before* parsing them downstream:

```xml
<JSONThreatProtection name="JTP-Inbound">
  <DisplayName>JTP-Inbound</DisplayName>
  <ArrayElementCount>100</ArrayElementCount>
  <ContainerDepth>10</ContainerDepth>
  <ObjectEntryCount>100</ObjectEntryCount>
  <ObjectEntryNameLength>100</ObjectEntryNameLength>
  <StringValueLength>2000</StringValueLength>
  <Source>request</Source>
</JSONThreatProtection>
```

If you accept any XML (rare in OB, common in legacy core integrations), add `XMLThreatProtection` with `<NodeDepth>`, `<ChildCount>`, and entity-expansion limits to stop billion-laughs attacks.

## RegularExpressionProtection — injection patterns

Scan inputs for SQLi/XSS/path-traversal signatures across headers, query params, and body:

```xml
<RegularExpressionProtection name="REP-Inbound">
  <DisplayName>REP-Inbound</DisplayName>
  <Source>request</Source>
  <QueryParam name="q">
    <Pattern>[\s]*(?i)(select|insert|delete|update|drop|union)[\s]</Pattern>
  </QueryParam>
  <Header name="x-account-id">
    <Pattern>(?i)(\.\./|<script)</Pattern>
  </Header>
  <JSONPayload>
    <Element name="$.Data..*"><Pattern>(?i)(<script|onerror=)</Pattern></Element>
  </JSONPayload>
</RegularExpressionProtection>
```

> Threat-protection policies **throw** on a hit, so your Day-11 FaultRules catch them and return a clean `400`/`403` instead of a stack trace. Tune limits to your real payloads — too strict breaks legitimate traffic.

## CORS for browser-based TPPs

If a TPP's single-page app calls your API directly, browsers require CORS. Apigee X uses a dedicated **CORS** policy (preferred over hand-rolled AssignMessage):

```xml
<CORS name="CORS-Allow">
  <DisplayName>CORS-Allow</DisplayName>
  <AllowOrigins>https://app.acme-fintech.example</AllowOrigins>
  <AllowMethods>GET, POST, OPTIONS</AllowMethods>
  <AllowHeaders>Authorization, Content-Type, x-fapi-interaction-id, x-idempotency-key</AllowHeaders>
  <ExposeHeaders>x-fapi-interaction-id</ExposeHeaders>
  <MaxAge>3600</MaxAge>
  <AllowCredentials>true</AllowCredentials>
  <GeneratePreflightResponse>true</GeneratePreflightResponse>
  <IgnoreUnresolvedVariables>true</IgnoreUnresolvedVariables>
</CORS>
```

> **Never** use `AllowOrigins>*` with `AllowCredentials>true` — it's insecure and browsers reject it. List explicit origins. `GeneratePreflightResponse` lets Apigee answer the `OPTIONS` preflight itself.

## Data masking — keep secrets out of traces & logs

Two layers:

1. **`private.*` variables** (Day 10) — automatically masked in Debug.
2. **Mask configurations** — org/proxy-level rules that redact fields in Debug/trace output (e.g. `$.Data.Account.Identification`, the `Authorization` header, card PANs).

Create a mask config so account numbers never appear in a trace:

```json
{
  "name": "default",
  "jSONPathsRequest":  ["$.Data.Initiation.CreditorAccount.Identification"],
  "jSONPathsResponse": ["$.Data.Account[*].Account[*].Identification"],
  "xPathsRequest": [],
  "namespaces": {},
  "variables": ["request.header.authorization", "request.header.x-api-key"]
}
```

```bash
# apply a data-mask (maskconfig) to the org/proxy
apigeecli maskconfigs create --proxy aisp-house-style -f ./maskconfig.json \
  --org "$ORG" --token "$TOKEN"
```

> Masking affects **traces and analytics**, not the actual response to the client. To remove data from the *response*, strip it with AssignMessage `<Remove>` (Day 7). For real log redaction, also avoid logging sensitive vars in your MessageLogging policy (Day 28).

## Lab — harden the shared inbound flow

1. Add `JTP-Inbound` and `REP-Inbound` to `sf-fapi-inbound` so **every** proxy gets threat protection via the flow hook.
2. Add the `CORS-Allow` policy to the AISP proxy PreFlow and confirm an `OPTIONS` preflight returns the right headers:

```bash
curl -is -X OPTIONS "https://$RUNTIME_HOST/aisp-house-style/accounts" \
  -H "Origin: https://app.acme-fintech.example" \
  -H "Access-Control-Request-Method: GET" | grep -i access-control
```

3. Send an oversized/nested JSON body and confirm a clean `400` (not a `500`); send a `union select` query param and confirm `REP` blocks it.

```bash
# nested-depth attack
curl -s -o /dev/null -w "%{http_code}\n" -X POST "https://$RUNTIME_HOST/aisp-house-style/payments" \
  -H 'Content-Type: application/json' -H "x-fapi-interaction-id: $(uuidgen)" \
  -d "$(python3 -c 'print("{\"a\":"*30 + "1" + "}"*30)')"
```

## Recap — you can now…

- Reject abusive payloads with **JSON/XML threat protection** and **regex protection**.
- Enable **CORS** correctly for browser clients (explicit origins, preflight).
- **Mask** sensitive data in traces/analytics and know masking ≠ response stripping.

## Check yourself

1. Why is `AllowOrigins=*` + `AllowCredentials=true` rejected?
2. Does a mask config change what the *client* receives?
3. Where should threat protection live so all proxies inherit it?

**Next:** Day 18 — the profile that ties the whole security week together: **FAPI 1.0 Advanced**, requirement by requirement.
