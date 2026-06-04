# Day 25 — End-to-end Open Banking reference build (Week 4 capstone)

> **Bottom line:** You'll assemble everything from Weeks 3–4 into one coherent, FAPI-secured Open Banking surface — a clean proxy estate with shared security, consistent errors, and a single tested journey from TPP onboarding to a completed payment.

> **Builds on Days 19–24:** today is integration, not new policies. You wire the pieces into a maintainable whole.

## Why this matters

Individually-correct flows can still form an incoherent estate: duplicated security, drifting error formats, unclear proxy boundaries. The capstone is where you impose **architecture** — the thing a bank actually ships and a conformance suite actually tests.

## The reference proxy estate

Decompose by concern (MECE), share what's cross-cutting:

```text
Shared flows (governance, attached via flow hook + callout)
  sf-fapi-inbound      spike arrest, threat protection, FAPI headers
  sf-consent-guard     token verify + consent status/expiry/permission
  sf-jws-verify        detached JWS validation (OBSEAL)
  sf-error-obie        DefaultFaultRule formatter (OBIE envelope)

Proxies
  fapi-as              /par /authorize /token   (Day 19)  — the security brain
  ob-dcr               /register                (Day 24)  — onboarding
  ob-aisp              /account-access-consents, /accounts, /balances, /transactions (Days 21–22)
  ob-pisp              /domestic-payment-consents, /domestic-payments (Day 23)
  ob-cof               /funds-confirmation-consents, /funds-confirmations (reuse Day 9 pattern)

Backends (TargetServers, per-environment)
  core-banking, payment-rail, consent-store
```

> **Boundary rule:** one proxy per OBIE API family, security centralized in `fapi-as` + shared flows. Don't fold AISP and PISP into one proxy — they have different scopes, products, and risk, and you want to deploy/rate-limit them independently.

## Consistent base paths & versioning

Deploy under a single, versioned scheme so clients have one mental model:

```text
/open-banking/v3.1/par
/open-banking/v3.1/token
/open-banking/v3.1/register
/open-banking/v3.1/aisp/account-access-consents
/open-banking/v3.1/aisp/accounts
/open-banking/v3.1/pisp/domestic-payment-consents
/open-banking/v3.1/pisp/domestic-payments
```

Version in the **base path** (`v3.1`), not headers — it's what OBIE specs and TPPs expect. Run `v3.1` and a future `v4.0` as separate proxy revisions/base paths side by side during migration.

## Bind it together with flow hooks

```bash
# every OB proxy inherits inbound hardening + FAPI headers
apigeecli flowhooks attach --name pre-proxy --sharedflow sf-fapi-inbound \
  --org "$ORG" --env "$ENV" --token "$TOKEN"
# and a uniform OBIE error envelope on the way out
apigeecli flowhooks attach --name post-proxy --sharedflow sf-error-obie \
  --org "$ORG" --env "$ENV" --token "$TOKEN"
```

Consent guard and JWS verification stay **FlowCallouts** (only AISP/PISP need them, and ordering matters), not hooks.

## The golden journey (one end-to-end test)

This is your acceptance test — the path a conformance run and a demo both follow:

```bash
# 0) Onboard the TPP (DCR) → client_id, registered OBWAC
CLIENT_ID=$(curl -s -X POST ".../v3.1/register" --cert tpp-obwac.crt --key tpp-obwac.key \
  -H "Content-Type: application/jwt" --data "$REGISTRATION_JWT" | jq -r .client_id)

# 1) AISP: create + authorise an account-access consent, then read accounts
AAC=$(curl -s -X POST ".../v3.1/aisp/account-access-consents" -H "Authorization: Bearer $CC_TOKEN" \
  -H "x-fapi-interaction-id: $(uuidgen)" -d "$CONSENT_BODY" | jq -r .Data.ConsentId)
# (PSU authorises via fapi-as → AC_TOKEN bound to AAC)
curl -s ".../v3.1/aisp/accounts" -H "Authorization: Bearer $AC_TOKEN" -H "x-fapi-interaction-id: $(uuidgen)" | jq '.Data.Account | length'

# 2) PISP: create + authorise a payment consent, then submit (idempotent)
PCID=$(curl -s -X POST ".../v3.1/pisp/domestic-payment-consents" -H "Authorization: Bearer $CC_PAY" \
  -H "x-jws-signature: $JWS" -H "x-idempotency-key: $(uuidgen)" -d "$PAY_CONSENT" | jq -r .Data.ConsentId)
# (PSU authorises → PAY_TOKEN)
curl -s -X POST ".../v3.1/pisp/domestic-payments" -H "Authorization: Bearer $PAY_TOKEN" \
  -H "x-jws-signature: $JWS" -H "x-idempotency-key: $(uuidgen)" -d "$PAYMENT_BODY" | jq '.Data.Status'
# → "AcceptedSettlementInProcess"
```

## Conformance mindset

Before you call it done, self-check against the OBIE/FAPI test themes:

- **Security:** PAR enforced? PS256 only? cert-bound token rejected on wrong cert? mTLS required on all endpoints?
- **Consent:** can't read data with `AwaitingAuthorisation`? expired consent blocked? permission scoping correct?
- **Payments:** Initiation immutability enforced? idempotency replay-safe? detached JWS validated and tamper-detected?
- **Errors:** every failure returns the OBIE envelope with a documented `ErrorCode`?
- **Headers:** `x-fapi-interaction-id` echoed on every response, success and error?

## Lab — ship the estate

1. Create the five shared flows and five proxies above; attach the two flow hooks.
2. Run the golden journey script end to end against your eval org.
3. Produce a one-page **conformance checklist** (the bullets above) and mark each PASS, citing the policy that enforces it. This artifact is what you'd hand an auditor.

## Recap — you can now…

- Decompose an Open Banking surface into a **MECE proxy estate** with centralized security.
- Apply consistent **versioned base paths** and **flow-hook governance**.
- Execute and self-assess the **golden journey** from DCR to a completed payment.

## Check yourself

1. Why keep AISP and PISP as separate proxies instead of one?
2. Which security concerns belong in a **flow hook** vs a **flow callout**, and why?
3. Name three things a FAPI/OBIE conformance run will try to break in your build.

**Next:** Day 26 — Week 5 (Operations) begins: promote this estate cleanly across **environments, env groups, and revisions**.
