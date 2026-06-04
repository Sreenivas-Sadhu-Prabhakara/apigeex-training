# Day 23 — PISP: payment initiation APIs

> **Bottom line:** You'll implement the **domestic payment** flow — create a payment *consent*, have the PSU authorize it, then *submit* the payment — with **idempotency**, **detached JWS signature** validation, and a **funds-confirmation** check.

> **Builds on Days 21–22:** payments reuse the consent pattern, but the consent is *single-payment* and the stakes (and validation) are higher.

## Why this matters

Payments are irreversible and high-value, so the spec adds protections AISP doesn't have: a **signed** request body (`x-jws-signature`), strict **idempotency** so a retried request never double-pays, and a **funds check**. This is where correctness is non-negotiable.

## The two-step payment model

```text
1. POST /domestic-payment-consents   → DomesticPaymentConsentId, Status=AwaitingAuthorisation
   (the TPP declares Initiation: amount, creditor, reference — IMMUTABLE once set)
2. PSU authorizes that consent (FAPI auth-code) → Status=Authorised, token carries ConsentId
3. POST /domestic-payments           → submit; Apigee validates the body == the consented Initiation
   → Status=AcceptedSettlementInProcess (then settlement async)
```

```widget
{"type":"sequence","title":"Two-step payment, step by step","actors":[
  {"id":"tpp","label":"TPP (PISP)"},
  {"id":"as","label":"Apigee"},
  {"id":"rail","label":"Payment rail / core"}
],"steps":[
  {"from":"tpp","to":"as","label":"POST /domestic-payment-consents (signed)","note":"The TPP declares the Initiation — amount, creditor, reference. This is immutable once set."},
  {"from":"as","to":"as","label":"verify detached JWS + validate","note":"The OBSEAL-signed body is verified, the Initiation validated, and the consent stored as AwaitingAuthorisation."},
  {"from":"as","to":"tpp","label":"ConsentId","kind":"return","note":"A reference to the pending payment consent."},
  {"from":"tpp","to":"as","label":"PSU authorises (auth-code)","note":"The PSU approves this SPECIFIC payment; status → Authorised and the token carries the ConsentId."},
  {"from":"tpp","to":"as","label":"POST /domestic-payments (signed)","note":"The submission body's Initiation must EXACTLY equal the consented Initiation."},
  {"from":"as","to":"as","label":"idempotency + match + funds","note":"Idempotency key checked (no double-pay), Initiation compared, optional funds-confirmation."},
  {"from":"as","to":"rail","label":"submit payment","note":"Apigee calls the core payment rail."},
  {"from":"rail","to":"as","label":"accepted","kind":"return","note":"The rail accepts the instruction for settlement."},
  {"from":"as","to":"tpp","label":"AcceptedSettlementInProcess","kind":"return","note":"Status returned to the TPP; settlement completes asynchronously."}
]}
```

```widget
{"type":"statemachine","title":"Payment status after submission","start":"proc",
 "states":[
   {"id":"proc","label":"AcceptedSettlementInProcess"},
   {"id":"pending","label":"Pending"},
   {"id":"done","label":"AcceptedSettlementCompleted","terminal":true},
   {"id":"rej","label":"Rejected","terminal":true}
 ],
 "events":[
   {"id":"settle","label":"Settles"},
   {"id":"hold","label":"Goes pending"},
   {"id":"clear","label":"Clears"},
   {"id":"fail","label":"Fails"}
 ],
 "transitions":[
   {"from":"proc","event":"settle","to":"done","desc":"Funds settled successfully."},
   {"from":"proc","event":"hold","to":"pending","desc":"Held for checks before settlement."},
   {"from":"proc","event":"fail","to":"rej","desc":"Rejected before settlement."},
   {"from":"pending","event":"clear","to":"done","desc":"Checks pass; settlement completes."},
   {"from":"pending","event":"fail","to":"rej","desc":"Checks fail; payment rejected."}
 ]}
```

Payment consent statuses: `AwaitingAuthorisation` → `Authorised` / `Rejected` → (`Consumed` after the payment is created).
Payment statuses: `AcceptedSettlementInProcess`, `AcceptedSettlementCompleted`, `Pending`, `Rejected`.

## 1 — Create the payment consent

```bash
curl -s -X POST "https://$RUNTIME_HOST/open-banking/v3.1/pisp/domestic-payment-consents" \
  -H "Authorization: Bearer $CC_TOKEN_PAYMENTS" \
  -H "Content-Type: application/json" \
  -H "x-fapi-interaction-id: $(uuidgen)" \
  -H "x-idempotency-key: $(uuidgen)" \
  -H "x-jws-signature: $DETACHED_JWS" \
  -d '{
    "Data": {
      "Initiation": {
        "InstructionIdentification": "ACME-INSTR-001",
        "EndToEndIdentification": "E2E-001",
        "InstructedAmount": { "Amount": "25.00", "Currency": "GBP" },
        "CreditorAccount": {
          "SchemeName": "UK.OBIE.SortCodeAccountNumber",
          "Identification": "08080021325698",
          "Name": "ACME Coffee Ltd"
        },
        "RemittanceInformation": { "Reference": "Invoice-22", "Unstructured": "Thanks" }
      }
    },
    "Risk": { "PaymentContextCode": "EcommerceGoods" }
  }' | jq .
```

## 2 — Validate the detached JWS signature

The TPP signs the body with its **OBSEAL** key; the signature travels in `x-jws-signature` as a **detached** JWS (header + ".." + signature, no payload). You reconstruct and verify it:

```xml
<Flow name="CreatePaymentConsent">
  <Condition>(proxy.pathsuffix = "/domestic-payment-consents") and (request.verb = "POST")</Condition>
  <Request>
    <Step><Name>OA-VerifyToken</Name></Step>                <!-- scope=payments -->
    <Step><Name>RF-MissingJws</Name><Condition>request.header.x-jws-signature = null</Condition></Step>
    <Step><Name>JS-ReconstructJws</Name></Step>             <!-- header + '.' + base64url(body) + '.' + sig -->
    <Step><Name>JWT-VerifyDetachedJws</Name></Step>         <!-- VerifyJWT (PS256) against TPP OBSEAL JWKS -->
    <Step><Name>JS-ValidateInitiation</Name></Step>         <!-- amount>0, currency, scheme valid -->
    <Step><Name>EV-Idempotency</Name></Step>
    <Step><Name>JS-MintPaymentConsentId</Name></Step>
    <Step><Name>KVM-StorePaymentConsent</Name></Step>       <!-- store Initiation immutably -->
    <Step><Name>AM-PaymentConsentResponse</Name></Step>
  </Request>
</Flow>
```

```javascript
// resources/jsc/reconstructJws.js — rebuild detached JWS for verification
var jws = context.getVariable('request.header.x-jws-signature') || '';
var parts = jws.split('.');                 // header..signature  (middle empty = detached)
var body = context.getVariable('request.content') || '';
var b64url = function (s) {
  return Buffer.from(s, 'utf8').toString('base64').replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
};
context.setVariable('jws.reconstructed', parts[0] + '.' + b64url(body) + '.' + parts[2]);
```

## 3 — Idempotency (never double-pay)

`x-idempotency-key` must make a retried, identical request safe. Cache the key → response for ≥24h; on a repeat key, **return the original response** instead of re-creating the payment.

```xml
<Step><Name>LC-Idempotency</Name></Step>   <!-- LookupCache by x-idempotency-key -->
<Step>
  <Name>AM-ReplayStoredResponse</Name>
  <Condition>idempotency.storedResponse != null</Condition>
</Step>
<!-- only if not a replay do we create + then PopulateCache the response -->
```

> **Idempotency vs the body:** the spec requires the *same key + same body* to be idempotent, and the *same key + different body* to be a `400`. Hash the body and store it with the key; compare on replay.

## 4 — Submit the payment (`POST /domestic-payments`)

The submission body's `Initiation` **must exactly equal** the consented Initiation. Re-validate, optionally funds-check, then call the core payment rail.

```xml
<Flow name="CreatePayment">
  <Condition>(proxy.pathsuffix = "/domestic-payments") and (request.verb = "POST")</Condition>
  <Request>
    <Step><Name>OA-VerifyToken</Name></Step>
    <Step><Name>JWT-VerifyDetachedJws</Name></Step>
    <Step><Name>EV-ConsentIdFromBody</Name></Step>
    <Step><Name>KVM-GetPaymentConsent</Name></Step>
    <Step><Name>RF-ConsentNotAuthorised</Name><Condition>pcons.status != "Authorised"</Condition></Step>
    <Step><Name>JS-AssertInitiationMatches</Name></Step>     <!-- body.Initiation == consented Initiation -->
    <Step><Name>SC-FundsCheck</Name></Step>                  <!-- optional CoF (Day 9) -->
    <Step><Name>RF-InsufficientFunds</Name><Condition>funds.fundsAvailable = "false"</Condition></Step>
    <Step><Name>SC-SubmitToRail</Name></Step>                <!-- core payment system -->
    <Step><Name>AM-PaymentAcceptedResponse</Name></Step>     <!-- Status=AcceptedSettlementInProcess -->
  </Request>
</Flow>
```

## Lab — a complete payment

1. Build the `pisp` proxy: `/domestic-payment-consents` (POST + GET), `/domestic-payments` (POST + GET status).
2. Run the flow with a valid consent and confirm idempotency:

```bash
IDEM=$(uuidgen)
# first submit
curl -s -X POST ".../pisp/domestic-payments" -H "Authorization: Bearer $PAY_TOKEN" \
  -H "x-idempotency-key: $IDEM" -H "x-jws-signature: $DETACHED_JWS" -d "$PAYMENT_BODY" | jq '.Data.Status, .Data.DomesticPaymentId'
# retry SAME key + SAME body → identical response, NO second payment
curl -s -X POST ".../pisp/domestic-payments" -H "Authorization: Bearer $PAY_TOKEN" \
  -H "x-idempotency-key: $IDEM" -H "x-jws-signature: $DETACHED_JWS" -d "$PAYMENT_BODY" | jq '.Data.DomesticPaymentId'
# same key + DIFFERENT body → 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST ".../pisp/domestic-payments" -H "Authorization: Bearer $PAY_TOKEN" \
  -H "x-idempotency-key: $IDEM" -H "x-jws-signature: $DETACHED_JWS" -d "$DIFFERENT_BODY"
```

3. Tamper with the body after signing → `JWT-VerifyDetachedJws` fails → `401`. This proves message integrity.

## Recap — you can now…

- Implement the **two-step** payment-consent → submit model with immutable Initiation.
- Validate a **detached JWS** signature against the TPP's OBSEAL key.
- Enforce **idempotency** (same key+body safe; key+different-body rejected) and a **funds check**.

## Check yourself

1. Why must the `/domestic-payments` body's Initiation equal the consent's Initiation?
2. What does `x-jws-signature` protect that mTLS does not?
3. Same idempotency key, different body — what status do you return?

**Next:** Day 24 — onboard TPPs at scale: **Dynamic Client Registration**, SSA validation, and certificate-bound tokens.
