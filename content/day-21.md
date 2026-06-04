# Day 21 — Consent: the account-access consent model

> **Bottom line:** You'll build the **account-access consent** lifecycle on Apigee — create a consent (status `AwaitingAuthorisation`), have the PSU authorize it (→ `Authorised`), and enforce its status and permissions on every later data call.

> **Builds on Days 19–20:** the consent is created with a *client-credentials* token, authorized via your *FAPI authorization-code* flow, then *enforced* on AISP resources.

## Why this matters

Consent is the legal and technical core of Open Banking. No data flows without an `Authorised` consent that grants specific **permissions** for a specific **period**. This is the single object regulators, TPPs, and PSUs all care about — and the one most implementations get subtly wrong.

## The consent lifecycle

```text
TPP (client_credentials token)
  └─ POST /account-access-consents  → ConsentId, Status=AwaitingAuthorisation
PSU authorization (your FAPI auth-code flow, Day 19)
  └─ consent is tied to the access token via the "openbanking_intent_id" claim
  └─ PSU approves → Status=Authorised   (or Rejected)
TPP (authorization_code token, bound to ConsentId)
  └─ GET /accounts ... enforced against the consent's Status + Permissions + ExpirationDateTime
Later: PSU or TPP revokes → Status=Revoked
```

```widget
{"type":"statemachine","title":"Drive the consent lifecycle","start":"await",
 "states":[
   {"id":"await","label":"AwaitingAuthorisation"},
   {"id":"auth","label":"Authorised"},
   {"id":"rej","label":"Rejected","terminal":true},
   {"id":"rev","label":"Revoked","terminal":true}
 ],
 "events":[
   {"id":"approve","label":"PSU approves"},
   {"id":"reject","label":"PSU rejects"},
   {"id":"revoke","label":"Revoke"}
 ],
 "transitions":[
   {"from":"await","event":"approve","to":"auth","desc":"PSU authenticates and approves; the issued access token now carries the ConsentId."},
   {"from":"await","event":"reject","to":"rej","desc":"PSU declines — data access is never granted."},
   {"from":"auth","event":"revoke","to":"rev","desc":"PSU or TPP withdraws consent; all data calls must now be refused."}
 ]}
```

> Notice the widget **disables events that aren't valid in the current state** — you can't `Revoke` something still `AwaitingAuthorisation`, and terminal states accept nothing. That's exactly the enforcement your consent-guard shared flow implements.

| Status | Meaning |
|--------|---------|
| `AwaitingAuthorisation` | Created, not yet approved by the PSU |
| `Authorised` | PSU approved; data calls allowed |
| `Rejected` | PSU declined |
| `Revoked` | Previously authorised, now withdrawn |

## 1 — Create the consent (`POST /account-access-consents`)

The TPP uses a **client-credentials** token (scope `accounts`) to register the *intent*. The body declares **Permissions**, optional **ExpirationDateTime**, and transaction date range.

```bash
curl -s -X POST "https://$RUNTIME_HOST/open-banking/v3.1/aisp/account-access-consents" \
  -H "Authorization: Bearer $CC_TOKEN" \
  -H "Content-Type: application/json" \
  -H "x-fapi-interaction-id: $(uuidgen)" \
  -H "x-idempotency-key: $(uuidgen)" \
  -d '{
    "Data": {
      "Permissions": ["ReadAccountsDetail","ReadBalances","ReadTransactionsDetail","ReadTransactionsCredits","ReadTransactionsDebits"],
      "ExpirationDateTime": "2026-12-31T00:00:00+00:00",
      "TransactionFromDateTime": "2026-01-01T00:00:00+00:00",
      "TransactionToDateTime": "2026-06-04T00:00:00+00:00"
    },
    "Risk": {}
  }' | jq .
# → { "Data": { "ConsentId": "aac-123", "Status": "AwaitingAuthorisation", ... } }
```

Inside Apigee, the consent flow:

```xml
<Flow name="CreateAccountAccessConsent">
  <Condition>(proxy.pathsuffix = "/account-access-consents") and (request.verb = "POST")</Condition>
  <Request>
    <Step><Name>OA-VerifyToken</Name></Step>                 <!-- scope=accounts (client_credentials) -->
    <Step><Name>EV-ConsentRequest</Name></Step>              <!-- pull Permissions, dates -->
    <Step><Name>JS-ValidatePermissions</Name></Step>         <!-- against allowed enum -->
    <Step><Name>JS-MintConsentId</Name></Step>               <!-- aac-<uuid> -->
    <Step><Name>KVM-StoreConsent</Name></Step>               <!-- persist status+permissions (see note) -->
    <Step><Name>AM-ConsentCreatedResponse</Name></Step>
  </Request>
</Flow>
```

> **Where to store consent state?** A KVM works for a lab, but production consent is high-volume mutable state — back it with a real datastore (Firestore/Cloud SQL/the core) reached via **ServiceCallout**. Treat the KVM examples here as a stand-in you'll swap on Day 25/30.

## 2 — Bind consent to authorization

The OB twist: the PSU authorizes a **specific consent**. The TPP puts the `ConsentId` into the **`openbanking_intent_id`** claim of the signed request object (Day 19 PAR). During `/authorize`, you:

1. Read `openbanking_intent_id` from the verified request object → the `ConsentId`.
2. Look up the consent; ensure it's `AwaitingAuthorisation`.
3. After PSU approval, set status `Authorised` and **stamp the ConsentId into the issued access token** (as a custom attribute/claim).

```xml
<!-- in the authorize flow, after PSU approval -->
<AssignMessage name="AM-AuthoriseConsent">
  <AssignVariable><Name>consent.id</Name><Ref>requestobject.claims.openbanking_intent_id</Ref></AssignVariable>
  <AssignVariable><Name>consent.newStatus</Name><Value>Authorised</Value></AssignVariable>
</AssignMessage>
<!-- KVM-StoreConsent updates status; OA-GenerateAuthCode carries consent.id as an attribute -->
```

## 3 — Enforce consent on every data call

This is the reusable guard for all AISP endpoints (Day 22). Put it in a shared flow:

```xml
<SharedFlow name="default">  <!-- sf-consent-guard -->
  <Step><Name>OA-VerifyToken</Name></Step>                  <!-- auth-code token, scope accounts -->
  <Step><Name>EV-ConsentIdFromToken</Name></Step>           <!-- read ConsentId attribute off the token -->
  <Step><Name>KVM-GetConsent</Name></Step>                  <!-- load status+permissions+expiry -->
  <Step><Name>RF-ConsentNotAuthorised</Name>
    <Condition>consent.status != "Authorised"</Condition></Step>
  <Step><Name>RF-ConsentExpired</Name>
    <Condition>consent.expiry LesserThanOrEquals system.timestamp</Condition></Step>
  <!-- permission check is per-endpoint, set consent.requiredPermission before calling this flow -->
  <Step><Name>RF-PermissionMissing</Name>
    <Condition>NOT (consent.permissions ~~ consent.requiredPermission)</Condition></Step>
</SharedFlow>
```

```xml
<RaiseFault name="RF-ConsentNotAuthorised">
  <FaultResponse><Set>
    <StatusCode>403</StatusCode>
    <Payload contentType="application/json">{"Code":"403 Forbidden","Errors":[{"ErrorCode":"UK.OBIE.Resource.InvalidConsentStatus","Message":"Consent is not Authorised."}]}</Payload>
  </Set></FaultResponse>
</RaiseFault>
```

## Lab — full consent lifecycle

1. Build the `aisp-consent` proxy with the create + status (`GET /account-access-consents/{ConsentId}`) + delete (revoke) flows.
2. Build the `sf-consent-guard` shared flow.
3. Run the lifecycle end to end:

```bash
# create
CONSENT=$(curl -s -X POST ".../account-access-consents" -H "Authorization: Bearer $CC_TOKEN" -d '{...}' | jq -r .Data.ConsentId)
# read status
curl -s ".../account-access-consents/$CONSENT" -H "Authorization: Bearer $CC_TOKEN" | jq .Data.Status   # AwaitingAuthorisation
# (PSU authorizes via the FAPI auth-code flow → Authorised, access token carries ConsentId)
# revoke
curl -s -X DELETE ".../account-access-consents/$CONSENT" -H "Authorization: Bearer $CC_TOKEN" -o /dev/null -w "%{http_code}\n"  # 204
```

## Recap — you can now…

- Implement the **consent lifecycle** and its four statuses.
- Bind a consent to authorization via **`openbanking_intent_id`** and stamp the `ConsentId` into the token.
- **Enforce** status, expiry, and permissions on data calls with a reusable consent-guard shared flow.

## Check yourself

1. What links a PSU's authorization to a *specific* consent?
2. Which permission must a consent hold for a TPP to read detailed transactions?
3. Why is a KVM a poor production store for consent state?

```widget
{"type":"quiz","title":"Day 21 check","questions":[
  {"q":"What links a PSU's authorization to a SPECIFIC consent?","options":["The openbanking_intent_id claim (the ConsentId)","The redirect_uri","The client_secret","The API key"],"answer":0,"explain":"The TPP puts the ConsentId in the openbanking_intent_id claim of the request object; after approval the access token is bound to that consent."},
  {"q":"Which permission must a consent hold to read DETAILED transactions?","options":["ReadTransactionsDetail","ReadAccountsBasic","ReadBalances","ReadProducts"],"answer":0,"explain":"Detailed transaction access requires ReadTransactionsDetail (plus Credits/Debits scopes as needed)."},
  {"q":"Why is a KVM a poor PRODUCTION store for consent state?","options":["Consent is high-volume, frequently-changing state — use a real datastore","KVMs can't be encrypted","KVMs aren't per-environment","KVMs can't be read at runtime"],"answer":0,"explain":"KVMs suit config and light secrets. Consent changes constantly and at volume — back it with Firestore/Cloud SQL/the core via ServiceCallout."}
]}
```

**Next:** Day 22 — use that consent to serve real data: the **AISP Accounts, Balances, and Transactions** APIs.
