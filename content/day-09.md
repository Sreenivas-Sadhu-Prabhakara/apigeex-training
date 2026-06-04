# Day 9 — Service composition: ServiceCallout & target servers

> **Bottom line:** You'll call a *secondary* service in the middle of a flow with **ServiceCallout**, parse its response, and decouple backend hostnames from your bundle using **TargetServers**.

> **Builds on Day 7–8:** the callout's request/response are messages you shape with AssignMessage and read with ExtractVariables.

## Why this matters

Real proxies rarely talk to one backend. An Open Banking payment flow checks **funds availability** at one service, validates the **consent** at another, then submits the payment. ServiceCallout makes those mid-flow calls. And you never want a hostname like `core-banking.prod.internal` baked into a bundle that's supposed to move between environments — that's what TargetServers fix.

## TargetServers — environment-specific backends

A **TargetServer** is a named, per-environment definition of a host/port. Your bundle references the *name*; each environment supplies the real host. This is how the same proxy hits a test core in `test` and the real core in `prod`.

Create one in your environment:

```bash
apigeecli targetservers create \
  --name core-banking \
  --host mocktarget.apigee.com --port 443 --tls=true \
  --org "$ORG" --env "$ENV" --token "$TOKEN"
```

Reference it from a TargetEndpoint with `<LoadBalancer>` instead of a hard `<URL>`:

```xml
<TargetEndpoint name="default">
  <HTTPTargetConnection>
    <LoadBalancer>
      <Server name="core-banking"/>
    </LoadBalancer>
    <Path>/json</Path>     <!-- path on the backend; host/port come from the TargetServer -->
  </HTTPTargetConnection>
</TargetEndpoint>
```

> Now promoting to `prod` changes **zero lines** of the bundle — you just define a `core-banking` TargetServer in the prod environment pointing at the real host. This is core to Day 26's promotion model.

## ServiceCallout — call a service mid-flow

ServiceCallout makes an HTTP call to another service *during* your flow and stores the result in a variable you choose. You typically: (1) build the callout request with AssignMessage, (2) run the callout, (3) extract from the callout response.

### 1 — build the request

```xml
<AssignMessage name="AM-FundsCheckRequest">
  <AssignTo createNew="true" type="request">fundsCheckRequest</AssignTo>
  <Set>
    <Verb>POST</Verb>
    <Path>/funds-confirmations</Path>
    <Headers><Header name="Content-Type">application/json</Header></Headers>
    <Payload contentType="application/json">{"accountId":"{ob.accountId}","amount":"{ob.amount}"}</Payload>
  </Set>
</AssignMessage>
```

### 2 — the callout

```xml
<ServiceCallout name="SC-FundsCheck">
  <DisplayName>SC-FundsCheck</DisplayName>
  <Request clearPayload="false" variable="fundsCheckRequest"/>
  <Response>fundsCheckResponse</Response>
  <Timeout>3000</Timeout>
  <HTTPTargetConnection>
    <LoadBalancer>
      <Server name="core-banking"/>
    </LoadBalancer>
  </HTTPTargetConnection>
</ServiceCallout>
```

### 3 — read its response

```xml
<ExtractVariables name="EV-FundsResult">
  <Source>fundsCheckResponse</Source>
  <JSONPayload>
    <Variable name="fundsAvailable"><JSONPath>$.Data.FundsAvailable</JSONPath></Variable>
  </JSONPayload>
  <VariablePrefix>funds</VariablePrefix>
</ExtractVariables>
```

Now `funds.fundsAvailable` is available to a `<Condition>` deciding whether to proceed.

> **ServiceCallout vs the proxy target:** the *target* (RouteRule → TargetEndpoint) is the main backend, called automatically after the request flow. A **ServiceCallout** is an extra, explicit call you make at a chosen point — auth servers, lookups, funds checks, fraud scoring.

## Composition patterns

| Need | Reach for |
|------|-----------|
| One main backend per request | RouteRule → TargetEndpoint |
| An auxiliary call mid-flow (lookup, auth, funds) | ServiceCallout |
| Choose backend by condition | multiple RouteRules (Day 4) |
| Hostname differs per environment | TargetServer (`<LoadBalancer>`) |
| Failover across hosts | TargetServer LoadBalancer with multiple `<Server>` |

## Lab — funds check before routing

1. Create the `core-banking` TargetServer (above).
2. Add `AM-FundsCheckRequest`, `SC-FundsCheck`, `EV-FundsResult` and chain them in the `CreatePayment` flow's `<Request>`. After them, add a conditional Step that raises a fault (Day 11 wires the fault) when funds aren't available:

```xml
<Flow name="CreatePayment">
  <Condition>(proxy.pathsuffix = "/payments") and (request.verb = "POST")</Condition>
  <Request>
    <Step><Name>EV-AccountId</Name></Step>
    <Step><Name>AM-FundsCheckRequest</Name></Step>
    <Step><Name>SC-FundsCheck</Name></Step>
    <Step><Name>EV-FundsResult</Name></Step>
  </Request>
</Flow>
```

3. Redeploy. Use a Debug session to watch the **callout** appear as its own transaction in the trace, separate from the main target call.

## Recap — you can now…

- Decouple hostnames with **TargetServers** referenced via `<LoadBalancer>`.
- Make a mid-flow **ServiceCallout**, build its request, and parse its response.
- Pick the right composition tool for each backend-interaction shape.

## Check yourself

1. Why does using a TargetServer make environment promotion cleaner?
2. What variable does `SC-FundsCheck` write, and how do you read a field out of it?
3. ServiceCallout vs RouteRule target — which is "automatic after the request flow"?

**Next:** Day 10 — make all this fast and cheap with **caching** (ResponseCache, LookupCache/PopulateCache) and store config in **KVMs**.
