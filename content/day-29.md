# Day 29 — API products, portal, monetization & API hub

> **Bottom line:** You'll package your proxies into **API products**, publish them on a **developer portal** with OpenAPI specs, optionally attach **monetization** rate plans, and catalog/govern everything in **API hub**.

> **Builds on Day 13:** API products return — now as the unit of *publishing and consumption*, not just access control.

## Why this matters

An API nobody can discover, understand, or self-serve onto is a cost, not an asset. The product/portal layer is how TPPs find your Open Banking APIs, read the spec, get credentials, and (in premium-API cases) pay. It's also where governance and the API catalog live.

## API products as the consumption unit

You built products for access (Day 13). The same product is what a developer **sees and subscribes to** on the portal. Design them around *consumer journeys*, not internal proxies:

```text
Product "Open Banking AISP (Read)"   → ob-aisp ops, scope=accounts, free, public
Product "Open Banking PISP (Write)"  → ob-pisp ops, scope=payments, onboarding-gated
Product "Premium Insights"           → enrichment proxy, paid rate plan, private
```

> A product can span **multiple proxies** and expose only **specific operations**. Bundle by what a TPP needs to do, e.g. an "AISP" product grouping accounts+balances+transactions across proxies.

## Attach an OpenAPI spec

Portals render from an **OpenAPI** document. Keep the spec in Git (Day 27) and associate it with the product so the portal shows accurate, try-it-out docs.

```yaml
# specs/ob-aisp.yaml (excerpt)
openapi: 3.0.3
info: { title: Open Banking AISP, version: "3.1.0" }
servers: [{ url: https://api.demobank.example/open-banking/v3.1/aisp }]
paths:
  /accounts:
    get:
      summary: Get consented accounts
      security: [{ openbanking: [accounts] }]
      parameters:
        - { name: x-fapi-interaction-id, in: header, required: true, schema: { type: string } }
      responses: { "200": { description: OK }, "403": { description: Consent not Authorised } }
components:
  securitySchemes:
    openbanking: { type: oauth2, flows: { authorizationCode: { authorizationUrl: /authorize, tokenUrl: /token, scopes: { accounts: read } } } }
```

```bash
apigeecli apidocs create --title "Open Banking AISP" --apiproductname "ob-aisp-read" \
  --oas-doc ./specs/ob-aisp.yaml --org "$ORG" --token "$TOKEN"
```

## Developer portal

Apigee X offers **integrated portals** (managed, no infra). Publish products, the spec, and let developers self-register apps and get keys.

```bash
# create a portal and publish the AISP product to it
apigeecli sites create --name ob-portal --org "$ORG" --token "$TOKEN"
# (publish products, upload spec, configure auth in the portal admin)
```

> For Open Banking, the *production* client onboarding is **DCR** (Day 24), not portal self-service — but the portal is still where TPPs read docs, try the **sandbox**, and manage non-production apps. Use portal for **discovery + sandbox**, DCR for **regulated production onboarding**.

## Monetization (optional, for premium APIs)

Core OB APIs are mandated and free, but banks monetize **premium/enrichment** APIs (categorized transactions, insights, confirmation-of-payee at scale). Apigee monetization attaches **rate plans** to products:

```text
Rate plan types:
  - Flat fee (subscription)         e.g. £500/month for Premium Insights
  - Per-use (per API call)          e.g. £0.002 / enrichment call
  - Revenue-share / freemium tiers  e.g. 10k free calls, then per-use
```

Rate plans meter against the same **product + app** model, using the quota counters you already wired. Billing data flows from analytics.

## API hub — catalog & governance

**API hub** is the org-wide catalog: every API (Apigee or not), its versions, specs, owners, lifecycle status, and deployments — with governance rules (style guides, linting) applied across teams.

```bash
# register an API and version in API hub
apigeecli apihub apis create --id ob-aisp --name "Open Banking AISP" \
  --org "$ORG" --region "$REGION" --token "$TOKEN"
```

> Use API hub to enforce **standards at scale**: a style guide (e.g. "all OB APIs must require `x-fapi-interaction-id`", "version in base path", "use OBIE error schema") linted automatically, plus a single place to answer "what APIs do we have and who owns them?"

## Lab — publish the AISP product

1. Create/refine the `ob-aisp-read` product scoped to the read operations with `scope=accounts`.
2. Author `specs/ob-aisp.yaml`, attach it as API docs.
3. Create an integrated portal, publish the product + spec, and walk the **self-service** flow as a developer: register an app, get a key, try `/accounts` in the sandbox.
4. (Optional) Attach a flat-fee rate plan to a `premium-insights` product and confirm a subscribing app is metered.
5. Register `ob-aisp` in **API hub** and add a style-guide rule requiring the FAPI header.

## Recap — you can now…

- Design **API products** around consumer journeys and attach **OpenAPI** specs.
- Publish to an **integrated developer portal** for discovery + sandbox (DCR for prod).
- Attach **monetization** rate plans to premium products and catalog everything in **API hub**.

## Check yourself

1. Why is DCR — not portal self-service — the production onboarding path for OB TPPs?
2. Can one API product span multiple proxies? Why would you want that?
3. What does API hub give you that per-proxy config doesn't?

**Next:** Day 30 — the finish line: a **production-readiness review** and the full **Open Banking capstone** sign-off.
