# Day 13 — App identity: API keys, products, apps & developers

> **Bottom line:** You'll model *who* can call your APIs using **API products**, **developers**, and **developer apps**, then enforce it at the edge with **VerifyAPIKey** — the foundation OAuth builds on tomorrow.

> **Builds on Day 6 & 12:** API products are also where quotas *should* live (`countRef`), and VerifyAPIKey belongs in your shared inbound flow.

## Why this matters

Before you can authorize a call, you must know *which app* is making it. Apigee's app-identity model is the registry of consumers. Even in OAuth and Open Banking, the OAuth **client** is an Apigee **developer app** under the hood — so this model never goes away; it gets a security layer on top.

## The object model

```text
Developer (a person/org: tpp-acme@example.com)
└── Developer App  (a registered client: "Acme Budgeting App")
    ├── consumerKey / consumerSecret   ← the credentials
    └── is granted one or more →
        API Product ("AISP Read")
        └── bundles specific proxy operations + quota + scopes + environments
```

Key insight: an app doesn't get access to a *proxy* directly. It's granted an **API product**, and the product decides which proxies/paths/methods and which environments are reachable, plus the quota and OAuth scopes. **The API product is the unit of access control.**

## Create the chain

### 1 — an API product

```bash
apigeecli products create \
  --name aisp-read \
  --displayName "AISP Read" \
  --approval auto \
  --envs "$ENV" \
  --scopes "accounts" \
  --quota 1000 --interval 1 --unit day \
  --opgrp '{"operationConfigs":[{"apiSource":"aisp-house-style","operations":[{"resource":"/accounts","methods":["GET"]},{"resource":"/accounts/**","methods":["GET"]}]}]}' \
  --org "$ORG" --token "$TOKEN"
```

> The operation group scopes the product to *specific paths and methods* of named proxies — `/accounts` and `/accounts/**` GET only. This is far stronger than "grant the whole proxy."

### 2 — a developer

```bash
apigeecli developers create \
  --email tpp-acme@example.com \
  --first Acme --last Fintech --user acme \
  --org "$ORG" --token "$TOKEN"
```

### 3 — a developer app bound to the product

```bash
apigeecli apps create \
  --name acme-budgeting \
  --email tpp-acme@example.com \
  --prods aisp-read \
  --org "$ORG" --token "$TOKEN"

# read back the credentials
apigeecli apps get --name acme-budgeting --email tpp-acme@example.com \
  --org "$ORG" --token "$TOKEN" | jq '.credentials[0]'
# → { "consumerKey": "....", "consumerSecret": "....", "apiProducts":[{"apiproduct":"aisp-read"}] }
```

Grab the `consumerKey` — that's the API key clients send.

## Enforce with VerifyAPIKey

```xml
<VerifyAPIKey name="VK-Key">
  <DisplayName>VK-Key</DisplayName>
  <!-- where the key arrives: a header, query param, etc. -->
  <APIKey ref="request.header.x-api-key"/>
</VerifyAPIKey>
```

On success Apigee populates rich variables you can use downstream:

- `verifyapikey.VK-Key.client_id` — the consumerKey
- `verifyapikey.VK-Key.apiproduct.name` — which product authorized it
- `verifyapikey.VK-Key.developer.email`, `...developer.app.name`
- `verifyapikey.VK-Key.apiproduct.developer.quota.limit` — drive Quota's `countRef` from here!

Attach it early (PreFlow.Request), and now make Quota product-driven:

```xml
<Quota name="Q-PerApp">
  <Allow countRef="verifyapikey.VK-Key.apiproduct.developer.quota.limit" count="1000"/>
  <Interval ref="verifyapikey.VK-Key.apiproduct.developer.quota.interval">1</Interval>
  <TimeUnit ref="verifyapikey.VK-Key.apiproduct.developer.quota.timeunit">day</TimeUnit>
  <Identifier ref="verifyapikey.VK-Key.client_id"/>
</Quota>
```

> Now changing a customer's plan is a **product edit**, not a proxy redeploy. This is the separation Open Banking and monetization both rely on.

## Lab — gate the AISP proxy on app identity

1. Create the product → developer → app chain above; capture the `consumerKey`.
2. Add `VK-Key` to PreFlow.Request **before** `Q-PerApp`, and switch the quota to `countRef`.
3. Redeploy and test allow/deny:

```bash
apigeecli apis create bundle --name aisp-house-style --proxy-folder ./aisp-house-style/apiproxy --org "$ORG" --token "$TOKEN"
apigeecli apis deploy --name aisp-house-style --rev 2 --org "$ORG" --env "$ENV" --ovr --wait --token "$TOKEN"

KEY="<paste consumerKey>"
# no key → 401
curl -s -o /dev/null -w "%{http_code}\n" -H "x-fapi-interaction-id: $(uuidgen)" "https://$RUNTIME_HOST/aisp-house-style/accounts"
# valid key → proceeds
curl -s -o /dev/null -w "%{http_code}\n" -H "x-api-key: $KEY" -H "x-fapi-interaction-id: $(uuidgen)" "https://$RUNTIME_HOST/aisp-house-style/accounts"
```

## Recap — you can now…

- Explain why the **API product** — not the proxy — is the unit of access.
- Build the **developer → app → product** chain and read out the credentials.
- Enforce identity with **VerifyAPIKey** and drive quotas from the product.

## Check yourself

1. An app needs access to two proxies' specific endpoints. Where do you define that?
2. Why drive `Quota` from `countRef` rather than a fixed `count`?
3. In OAuth/Open Banking, what Apigee object represents the OAuth *client*?

**Next:** Day 14 — turn that app identity into bearer tokens: **OAuth 2.0 client credentials** with the OAuthV2 policy.
