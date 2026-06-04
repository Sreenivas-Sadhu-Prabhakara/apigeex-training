# Day 6 — Traffic management: quotas & rate limiting

> **Bottom line:** You'll protect a backend with three different controls — **Quota** (business limits), **SpikeArrest** (smoothing), and **ConcurrentRateLimit** (in-flight cap) — and know exactly which problem each one solves.

> **Builds on Day 5:** these are just more policies attached to flow slots — same `<Step>` pattern you already know.

## Why this matters

A core-banking backend will fall over long before Apigee does. Traffic management is how you keep a misbehaving TPP from taking down the bank. In Open Banking these limits are also **contractual** — the spec defines fair-usage and rate expectations you must enforce per client.

## The three controls — pick the right one

| Policy | Answers the question | Counter | Use it for |
|--------|----------------------|---------|------------|
| **Quota** | "How many calls is this *app* allowed this month/day/minute?" | Distributed, persistent | Business/plan entitlements, per-app fair use |
| **SpikeArrest** | "Is traffic arriving *too fast right now*?" | Per-instance, smoothing | Absorbing bursts, protecting the backend's instantaneous rate |
| **ConcurrentRateLimit** | "How many requests are *in flight* to the backend at once?" | Per-target | Backends with a hard connection/concurrency ceiling |

> They compose. A typical proxy uses **SpikeArrest** (machine protection) **+ Quota** (business limit) together. They are not alternatives.

## Quota

Counts allowed calls over a window. Bind it to an identity (here, the API product / app you'll add on Day 13 — for now key it on a header so you can test).

```xml
<Quota name="Q-PerApp">
  <DisplayName>Q-PerApp</DisplayName>
  <!-- 1000 calls per app per day -->
  <Allow count="1000"/>
  <Interval>1</Interval>
  <TimeUnit>day</TimeUnit>
  <!-- Identifier: distinct counter per client. Later this becomes the app id. -->
  <Identifier ref="request.header.x-client-id"/>
  <Distributed>true</Distributed>
  <Synchronous>true</Synchronous>
</Quota>
```

Once an app and product exist (Day 13), prefer **product-driven quotas** by setting `<Allow countRef="verifyapikey.VK-Key.apiproduct.developer.quota.limit"/>` so limits live in the product, not the proxy.

## SpikeArrest

Smooths the *rate*, not a total. `30pm` = 30 per minute, enforced as ~1 per 2 seconds (it divides the window). Put it as early as possible — usually **ProxyEndpoint PreFlow**.

```xml
<SpikeArrest name="SA-Smooth">
  <DisplayName>SA-Smooth</DisplayName>
  <!-- 30 per minute, smoothed; or use 10ps for per-second -->
  <Rate>30pm</Rate>
  <!-- optional: key per client so one TPP can't consume another's budget -->
  <Identifier ref="request.header.x-client-id"/>
</SpikeArrest>
```

> SpikeArrest does **not** mean "30 in any 60s window." `30pm` ≈ one allowed every 2000 ms; two requests 100 ms apart trip it. That's the point — it stops bursts.

## ConcurrentRateLimit

Caps simultaneous in-flight calls to a **TargetEndpoint**. Attach it in the TargetEndpoint flow.

```xml
<ConcurrentRatelimit name="CRL-Backend">
  <AllowConnections count="50" ttl="5"/>
  <Distributed>true</Distributed>
  <Strict>false</Strict>
</ConcurrentRatelimit>
```

## Lab — layer machine + business protection

1. Add `SA-Smooth.xml` and `Q-PerApp.xml` to `policies/`.
2. Attach them in `proxies/default.xml` **PreFlow.Request**, SpikeArrest first:

```xml
<PreFlow name="PreFlow">
  <Request>
    <Step><Name>SA-Smooth</Name></Step>
    <Step><Name>Q-PerApp</Name></Step>
  </Request>
  <Response/>
</PreFlow>
```

3. Redeploy, then hammer it:

```bash
apigeecli apis create bundle --name hello-v1 --proxy-folder ./hello-v1/apiproxy --org "$ORG" --token "$TOKEN"
apigeecli apis deploy --name hello-v1 --rev 4 --org "$ORG" --env "$ENV" --ovr --wait --token "$TOKEN"

# Fire 10 quick requests with the same client id → SpikeArrest should 429 some
for i in $(seq 1 10); do
  curl -s -o /dev/null -w "%{http_code} " -H "x-client-id: tpp-123" "https://$RUNTIME_HOST/hello-v1/"
done; echo
```

You'll see a mix of `200` and `429 Too Many Requests`. The 429s are SpikeArrest tripping on burst spacing.

4. Inspect the quota counter headers — Apigee exposes `quota.Q-PerApp.allowed.count` and `...used.count` as flow variables; surface them with an AssignMessage header to watch the budget burn down.

## Recap — you can now…

- Choose between **Quota / SpikeArrest / ConcurrentRateLimit** by the problem.
- Key limits **per client** so tenants are isolated.
- Layer machine protection (SpikeArrest) under business limits (Quota).

## Check yourself

1. A TPP sends 2 requests 200 ms apart and gets one `429`. Quota or SpikeArrest?
2. Why prefer `countRef` from an API product over a hard-coded `count` in production?
3. Which of the three protects a backend that can only hold 40 simultaneous DB connections?

**Next:** Day 07 — read and reshape messages with **flow variables, AssignMessage (deep), and ExtractVariables**.
