# Day 4 — Flows, conditions & routing

> **Bottom line:** You'll make one proxy behave differently per HTTP method and path using **conditional flows**, and route to different backends using **RouteRules with conditions**.

> **Builds on Day 3:** we extend the `hello-v1` bundle's empty `<Flows/>` and single `RouteRule`.

## Why this matters

Real APIs aren't one path. An Open Banking AISP proxy serves `GET /accounts`, `GET /accounts/{id}/balances`, `GET /accounts/{id}/transactions` — each needs its own logic. Conditional flows are how you attach the right policies to the right operation without writing one giant if-statement.

## The execution order (the pipeline)

Every request walks this fixed path. Memorize it — Day 5 attaches policies to each slot:

```text
REQUEST
  ProxyEndpoint.PreFlow.Request
  ProxyEndpoint.<matching conditional Flow>.Request
  ProxyEndpoint.PostFlow.Request
  ── RouteRule selects a TargetEndpoint ──
  TargetEndpoint.PreFlow.Request
  TargetEndpoint.<matching conditional Flow>.Request
  TargetEndpoint.PostFlow.Request
        → backend call →
RESPONSE
  TargetEndpoint.PreFlow.Response
  TargetEndpoint.<matching conditional Flow>.Response
  TargetEndpoint.PostFlow.Response
  ProxyEndpoint.PreFlow.Response
  ProxyEndpoint.<matching conditional Flow>.Response
  ProxyEndpoint.PostFlow.Response
```

Two rules that surprise newcomers:

- **PreFlow always runs; conditional flows run only if their condition matches; the *first* matching conditional flow wins** (the rest are skipped).
- On the response side the order is **reversed** for the conditional flow selection — but PreFlow still runs before PostFlow.

## Conditional flows

A `<Flow>` has a `<Condition>`. Conditions are boolean expressions over **flow variables**. The two you'll use constantly:

- `request.verb` — the HTTP method (`"GET"`, `"POST"`, …)
- `proxy.pathsuffix` — the path *after* the BasePath (e.g. for `/hello-v1/accounts/123`, it's `/accounts/123`)

The `MatchesPath` operator (`~/` or `MatchesPath`) supports `{}` wildcards.

Replace the `<Flows/>` in `proxies/default.xml` with named flows:

```xml
<Flows>
  <Flow name="GetGreeting">
    <Condition>(proxy.pathsuffix = "/") and (request.verb = "GET")</Condition>
    <!-- request/response policies for this op go here (Day 5) -->
    <Request/>
    <Response/>
  </Flow>

  <Flow name="GetAccountById">
    <Condition>(proxy.pathsuffix MatchesPath "/accounts/{id}") and (request.verb = "GET")</Condition>
    <Request/>
    <Response/>
  </Flow>

  <Flow name="CreatePayment">
    <Condition>(proxy.pathsuffix = "/payments") and (request.verb = "POST")</Condition>
    <Request/>
    <Response/>
  </Flow>
</Flows>
```

> **Always end with a catch-all.** If nothing matches and you want a clean 404 instead of silently proxying, add a final flow with `<Condition>true</Condition>` that raises a fault (you'll wire RaiseFault on Day 11).

## RouteRules: routing to different targets

A `ProxyEndpoint` can have **multiple** `RouteRule`s, evaluated **top to bottom; first match wins**. Use conditions to pick a backend — or to return a response from policies with **no** backend at all.

```xml
<!-- Send health checks nowhere (answered by a policy), everything else to the backend -->
<RouteRule name="noRoute">
  <Condition>proxy.pathsuffix = "/health"</Condition>
  <!-- no <TargetEndpoint> => no backend call; a policy must build the response -->
</RouteRule>

<RouteRule name="sandbox">
  <Condition>request.header.X-Env = "sandbox"</Condition>
  <TargetEndpoint>sandbox</TargetEndpoint>
</RouteRule>

<RouteRule name="default">
  <TargetEndpoint>default</TargetEndpoint>
</RouteRule>
```

> RouteRules are ordered: put the most specific conditions first and an **unconditional `default` last** so there's always a fallback.

## Lab — add a versioned, method-aware route

1. Edit `hello-v1/apiproxy/proxies/default.xml`: add the three conditional flows above and the `/health` no-route RouteRule.
2. Add a second TargetEndpoint file `targets/sandbox.xml` (copy `default.xml`, change `URL` to `https://mocktarget.apigee.com` too for now — different backend comes on Day 9) and the `sandbox` RouteRule.
3. Re-create + redeploy:

```bash
apigeecli apis create bundle --name hello-v1 --proxy-folder ./hello-v1/apiproxy --org "$ORG" --token "$TOKEN"
apigeecli apis deploy --name hello-v1 --rev 2 --org "$ORG" --env "$ENV" --ovr --wait --token "$TOKEN"
```

4. Test routing and method matching:

```bash
curl -s -o /dev/null -w "%{http_code}\n" "https://$RUNTIME_HOST/hello-v1/"            # GET / → matches GetGreeting
curl -s -o /dev/null -w "%{http_code}\n" -X POST "https://$RUNTIME_HOST/hello-v1/payments"  # POST → CreatePayment
curl -is "https://$RUNTIME_HOST/hello-v1/health" | head -n 1   # no-route: will error until Day 11 gives it a response
curl -is -H "X-Env: sandbox" "https://$RUNTIME_HOST/hello-v1/" | head -n 1   # routed via sandbox RouteRule
```

The `/health` call will currently fail because no policy builds its response — that's expected and intentional; it proves the no-route path is taken. Day 5's AssignMessage will give it a body.

## Recap — you can now…

- Recite the **request/response pipeline** order.
- Attach logic per operation with **conditional flows** and `proxy.pathsuffix` / `request.verb`.
- Branch backends (or skip the backend) with **conditional RouteRules**, first-match-wins.

## Check yourself

1. Two conditional flows both match a request. Which runs?
2. What happens to a request whose RouteRule has no `<TargetEndpoint>` and no policy to build a response?
3. Where would you enforce "every request must carry an `x-fapi-interaction-id` header" so it applies to *all* operations — a conditional flow, or PreFlow?

**Next:** Day 05 — finally attach **policies** into these flow slots and predict their exact execution point.
