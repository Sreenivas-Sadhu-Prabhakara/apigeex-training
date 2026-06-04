# Day 5 — Policies 101 & the execution model

> **Bottom line:** You'll attach your first policies into flow slots, give the no-route `/health` endpoint a real response with **AssignMessage**, and be able to predict the exact order policies execute.

> **Builds on Day 4:** we fill the `<Request>`/`<Response>` slots you created in the conditional flows.

## Why this matters

Policies *are* Apigee. Everything for the next 25 days — quotas, OAuth, JWT, threat protection, FAPI — is a policy attached to a flow slot. Today you learn the universal pattern so every later policy is "same shape, different verbs."

## What a policy is

A policy is an XML configuration file in `apiproxy/policies/`, **referenced by name** from a flow via a `<Step>`. Two pieces, always:

1. **The policy file** — `policies/AM-HealthResponse.xml` (the configuration).
2. **The attachment** — a `<Step><Name>AM-HealthResponse</Name></Step>` inside a flow's `<Request>` or `<Response>`.

> **Naming convention (use it all course):** prefix by policy type — `AM-` AssignMessage, `EV-` ExtractVariables, `Q-` Quota, `SA-` SpikeArrest, `JS-` JavaScript, `OA-` OAuthV2, `RF-` RaiseFault, `VK-` VerifyAPIKey. Future-you will thank present-you.

## The attachment model

```text
policies/AM-HealthResponse.xml   ← the policy definition (one file)
        ▲ referenced by name
proxies/default.xml
   <Flow name="Health">
     <Request>
        <Step><Name>AM-HealthResponse</Name></Step>   ← attachment point
     </Request>
   </Flow>
```

A `<Step>` can itself carry a `<Condition>`, so you can attach a policy *conditionally* even inside a flow that already matched.

## Your first policy: AssignMessage

`AssignMessage` builds or modifies a message (the request, the response, or a named variable). It's the swiss-army knife. Here we use it to **synthesize a response** for the `/health` no-route from Day 4.

```bash
mkdir -p hello-v1/apiproxy/policies

cat > hello-v1/apiproxy/policies/AM-HealthResponse.xml <<'XML'
<AssignMessage name="AM-HealthResponse">
  <DisplayName>AM-HealthResponse</DisplayName>
  <!-- Build the response message that goes back to the client -->
  <Set>
    <Payload contentType="application/json">{"status":"UP","proxy":"hello-v1"}</Payload>
    <StatusCode>200</StatusCode>
    <ReasonPhrase>OK</ReasonPhrase>
  </Set>
  <!-- Tell Apigee NOT to look for a backend response; we built it ourselves -->
  <AssignTo createNew="false" type="response">response</AssignTo>
</AssignMessage>
XML
```

Now attach it. Add a conditional flow in `proxies/default.xml` and reference the policy in its `<Request>` (it runs before routing, so the no-route never needs a backend):

```xml
<Flow name="Health">
  <Condition>(proxy.pathsuffix = "/health") and (request.verb = "GET")</Condition>
  <Request>
    <Step><Name>AM-HealthResponse</Name></Step>
  </Request>
  <Response/>
</Flow>
```

Redeploy and call:

```bash
apigeecli apis create bundle --name hello-v1 --proxy-folder ./hello-v1/apiproxy --org "$ORG" --token "$TOKEN"
apigeecli apis deploy --name hello-v1 --rev 3 --org "$ORG" --env "$ENV" --ovr --wait --token "$TOKEN"

curl -s "https://$RUNTIME_HOST/hello-v1/health" | jq .
# → {"status":"UP","proxy":"hello-v1"}
```

## A second policy: add a header to every response

This shows attaching a policy at the **PostFlow.Response** so it runs for *all* operations:

```bash
cat > hello-v1/apiproxy/policies/AM-StandardHeaders.xml <<'XML'
<AssignMessage name="AM-StandardHeaders">
  <Set>
    <Headers>
      <Header name="X-Apigee-Proxy">hello-v1</Header>
      <!-- echo the FAPI interaction id if present; generate one if not -->
      <Header name="x-fapi-interaction-id">{request.header.x-fapi-interaction-id}</Header>
    </Headers>
  </Set>
  <AssignTo createNew="false" type="response">response</AssignTo>
</AssignMessage>
XML
```

Attach it in PostFlow so it's truly cross-cutting:

```xml
<PostFlow name="PostFlow">
  <Request/>
  <Response>
    <Step><Name>AM-StandardHeaders</Name></Step>
  </Response>
</PostFlow>
```

## Predicting execution order

Given this proxy, a `GET /hello-v1/health` runs:

```text
ProxyEndpoint.PreFlow.Request          (empty)
Flow "Health".Request → AM-HealthResponse   ← response is now built
ProxyEndpoint.PostFlow.Request         (empty)
[no RouteRule target → no backend call]
ProxyEndpoint.PreFlow.Response         (empty)
Flow "Health".Response                 (empty)
ProxyEndpoint.PostFlow.Response → AM-StandardHeaders   ← header added
```

> **Mental model:** policies don't "run when attached" — they run **when the flow slot they're attached to is reached**, *if* the flow's (and step's) condition matches. Order = position in the pipeline, not order in the file.

## Lab

1. Add a `<Header name="X-Response-Time">` is *not* trivial (needs a variable) — instead add `<Header name="X-Served-By">apigee-x</Header>` and confirm it appears on **every** endpoint, including `/health` and `/json`.
2. Put a `<Condition>` on the `AM-StandardHeaders` *Step* so it only adds the header when `request.verb = "GET"`. Verify a `POST` doesn't get it.
3. Open a **Debug/Trace** session in the UI (Console → Apigee → your proxy → *Debug*), send a request, and watch each policy light up in the order above.

## Recap — you can now…

- Explain the **policy file + `<Step>` attachment** split.
- Use **AssignMessage** to build a response and set headers.
- **Predict execution order** from flow position, not file order.
- Apply the **policy naming convention** used for the rest of the course.

## Check yourself

1. Where do you attach a policy so it runs for **every** operation's response?
2. What does `<AssignTo type="response">` plus no RouteRule target let you build?
3. Two policies are in the same `<Request>` slot — what determines which runs first?

**Next:** Day 06 — Week 2 opens with **traffic management**: Quota, Spike Arrest, and Concurrent Rate Limit, and exactly when to reach for each.
