# Day 10 — Caching: response, lookup/populate & KVM

> **Bottom line:** You'll cut latency and backend load with **ResponseCache**, store arbitrary values with **LookupCache/PopulateCache**, and keep config and lightweight secrets in **Key Value Maps (KVMs)**.

> **Builds on Day 9:** caching is what stops you repeating that ServiceCallout (e.g. a funds-confirmation token) on every request.

## Why this matters

Backends are the bottleneck and the cost center. Caching a reference-data response, or a backend OAuth token, can remove thousands of southbound calls. KVMs give you a place to store per-environment config (URLs, client ids) and small secrets without redeploying the bundle.

## ResponseCache — cache a whole backend response

Best for idempotent `GET`s on reference data (currencies, branch lists, product catalogs). It short-circuits the backend on a hit.

```xml
<ResponseCache name="RC-Reference">
  <DisplayName>RC-Reference</DisplayName>
  <CacheKey>
    <Prefix>refdata</Prefix>
    <!-- vary the key by path + a query param so different requests cache separately -->
    <KeyFragment ref="proxy.pathsuffix"/>
    <KeyFragment ref="request.queryparam.type"/>
  </CacheKey>
  <ExpirySettings>
    <TimeoutInSeconds>3600</TimeoutInSeconds>
  </ExpirySettings>
  <!-- only cache successful responses -->
  <ExcludeErrorResponse>true</ExcludeErrorResponse>
</ResponseCache>
```

> Attach **one** ResponseCache policy and reference it in **both** the Request flow (lookup) and the Response flow (store). Apigee handles the two phases from the single policy: on the request side it checks the cache and skips the target on a hit; on the response side it populates the cache.

> **Never** ResponseCache an Open Banking account or transaction response — it's per-consumer, consent-bound, and changes constantly. Cache *reference data and tokens*, not customer data.

## LookupCache / PopulateCache — cache a value you compute

When you want to cache *one value* (not a whole response) — classically a backend access token from a ServiceCallout — use the pair explicitly.

Lookup first:

```xml
<LookupCache name="LC-BackendToken">
  <CacheKey><KeyFragment>backend-token</KeyFragment></CacheKey>
  <AssignTo>private.backend.token</AssignTo>   <!-- sets this var if found -->
</LookupCache>
```

Then, only if it missed, fetch and populate:

```xml
<PopulateCache name="PC-BackendToken">
  <CacheKey><KeyFragment>backend-token</KeyFragment></CacheKey>
  <!-- store the token you just fetched; expire a little before it really does -->
  <Source>fetched.access_token</Source>
  <ExpirySettings><TimeoutInSeconds>3000</TimeoutInSeconds></ExpirySettings>
</PopulateCache>
```

Pattern in the flow:

```xml
<Request>
  <Step><Name>LC-BackendToken</Name></Step>
  <!-- fetch a new token only on a cache miss -->
  <Step>
    <Name>SC-GetBackendToken</Name>
    <Condition>private.backend.token = null</Condition>
  </Step>
  <Step>
    <Name>PC-BackendToken</Name>
    <Condition>private.backend.token = null</Condition>
  </Step>
</Request>
```

> The `private.` prefix marks a variable as **sensitive** — Apigee masks it in Debug/trace by default. Use it for tokens and secrets.

## Key Value Maps (KVM) — config & light secrets

A KVM is a named, per-environment (or per-org) store of key/value pairs. Use it for backend URLs, client ids, feature flags, and small secrets you don't want in the bundle.

Create and seed a KVM:

```bash
# encrypted KVM, scoped to the environment
apigeecli kvms create --name ob-config --org "$ORG" --env "$ENV" --token "$TOKEN"

apigeecli kvms entries create --map ob-config \
  --key core-banking-base-url --value "https://mocktarget.apigee.com" \
  --org "$ORG" --env "$ENV" --token "$TOKEN"
```

Read it at runtime with the **KeyValueMapOperations** policy:

```xml
<KeyValueMapOperations name="KVM-GetConfig" mapIdentifier="ob-config">
  <Scope>environment</Scope>
  <Get assignTo="config.coreBankingBaseUrl">
    <Key><Parameter>core-banking-base-url</Parameter></Key>
  </Get>
</KeyValueMapOperations>
```

> KVMs are **encrypted** in Apigee X. They're great for config and low-sensitivity secrets, but for client secrets and signing keys prefer the proper mechanisms you'll meet in the security week (keystores, GenerateJWT, and a secrets manager via callout).

## Lab — cache a backend token + read config from KVM

1. Create the `ob-config` KVM and a `core-banking-base-url` entry.
2. Add `KVM-GetConfig` to PreFlow.Request and confirm `config.coreBankingBaseUrl` is populated (surface it as a debug header).
3. Add the LookupCache/PopulateCache token pattern around a ServiceCallout (reuse `SC-FundsCheck` as a stand-in token fetch). Fire the same request twice and confirm the second call **skips** the callout (watch the Debug trace — no second SC transaction).

```bash
apigeecli apis create bundle --name hello-v1 --proxy-folder ./hello-v1/apiproxy --org "$ORG" --token "$TOKEN"
apigeecli apis deploy --name hello-v1 --rev 6 --org "$ORG" --env "$ENV" --ovr --wait --token "$TOKEN"
```

## Recap — you can now…

- Use **ResponseCache** for idempotent reference responses (and know not to cache customer data).
- Cache a single computed value with **LookupCache/PopulateCache** + conditional refetch.
- Store and read per-environment config/secrets in **KVMs**, masking secrets with `private.`.

## Check yourself

1. Why is it wrong to ResponseCache an AISP `/transactions` response?
2. What does the `private.` variable prefix change about tracing?
3. Which caching tool fits "cache the backend OAuth token for 50 minutes"?

**Next:** Day 11 — when things go wrong on purpose: **RaiseFault, FaultRules, and DefaultFaultRule** for predictable errors.
