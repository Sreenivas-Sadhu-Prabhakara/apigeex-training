# Day 8 — Transformation with JavaScript & message templates

> **Bottom line:** You'll write a **JavaScript policy** for logic the XML policies can't express, and use **message templates** for dynamic strings — and you'll know when *not* to reach for JavaScript.

> **Builds on Day 7:** JavaScript reads and writes the same flow variables ExtractVariables/AssignMessage use.

## Why this matters

Most mediation should be declarative (AssignMessage/ExtractVariables) — it's faster and safer. But some logic is genuinely procedural: building an OB-format error object, computing a hash, looping over an array of accounts. That's the JavaScript policy's job.

> **Rule of thumb:** reach for JavaScript only when a declarative policy can't do it. JS runs in a sandbox, costs more CPU, and is harder to trace. Never put secrets or crypto you can avoid in JS — use dedicated policies (GenerateJWT on Day 15, HMAC, etc.).

## The JavaScript policy

Two parts: the policy XML (which names a resource file) and the resource file under `apiproxy/resources/jsc/`.

```bash
mkdir -p hello-v1/apiproxy/resources/jsc

cat > hello-v1/apiproxy/policies/JS-BuildOBError.xml <<'XML'
<Javascript name="JS-BuildOBError" timeLimit="200">
  <DisplayName>JS-BuildOBError</DisplayName>
  <ResourceURL>jsc://buildOBError.js</ResourceURL>
  <!-- properties are readable inside the script via properties.NAME -->
  <Properties>
    <Property name="defaultCode">UK.OBIE.Field.Invalid</Property>
  </Properties>
</Javascript>
XML
```

The script — note the `context`, `request`, `response` globals Apigee injects:

```javascript
// resources/jsc/buildOBError.js
// Build an OBIE-style error envelope from flow variables.
var code = context.getVariable('error.obie.code') || properties.defaultCode;
var message = context.getVariable('error.obie.message') || 'The request is invalid.';
var interactionId = context.getVariable('request.header.x-fapi-interaction-id') || '';

var body = {
  Code: '400 BadRequest',
  Id: interactionId,
  Message: 'The request failed validation.',
  Errors: [
    {
      ErrorCode: code,
      Message: message
    }
  ]
};

// write the response the client will receive
context.setVariable('response.content', JSON.stringify(body));
context.setVariable('response.header.Content-Type', 'application/json');
context.setVariable('response.status.code', 400);
context.setVariable('response.reason.phrase', 'Bad Request');
```

> **The bridge is `context.getVariable` / `context.setVariable`.** Anything you set is visible to later policies; anything earlier policies set is readable here. That's how JS composes with the declarative world.

## Message templates (no JavaScript needed)

A *message template* is any string with `{variable}` references, used in `<Header>`, `<Payload>`, `<Path>`, `<AssignVariable><Template>`, etc. They support functions and defaults:

```xml
<AssignMessage name="AM-Templated">
  <AssignVariable>
    <Name>ob.idempotencyKey</Name>
    <!-- default value if the source variable is empty -->
    <Template>{request.header.x-idempotency-key}</Template>
    <Value>auto-{messageid}</Value>
  </AssignVariable>

  <Set>
    <Headers>
      <!-- built-in template functions: createUuid(), toUpperCase(), substring() ... -->
      <Header name="X-Trace-Id">{createUuid()}</Header>
      <Header name="X-Account-Upper">{toUpperCase(ob.accountId)}</Header>
    </Headers>
    <Path>/v3.1/aisp/accounts/{ob.accountId}</Path>
  </Set>
  <AssignTo createNew="false" type="request">request</AssignTo>
</AssignMessage>
```

Useful template functions: `createUuid()`, `toUpperCase()`, `toLowerCase()`, `substring()`, `xPath()`, `jsonPath()`, `timeFormatUTC()`, `escapeJSON()`, `encodeBase64()`. Prefer these over a JS policy for one-liners.

## Lab — declarative first, JS only where needed

1. Add the message-template `AM-Templated` policy and confirm `X-Trace-Id` is a fresh UUID each call. (Pure template — no JS.)
2. Add `JS-BuildOBError` + `buildOBError.js`. Wire a flow that sets `error.obie.message` then runs the JS, returning the OB error envelope:

```xml
<Flow name="DemoError">
  <Condition>proxy.pathsuffix = "/boom"</Condition>
  <Request>
    <Step><Name>JS-BuildOBError</Name></Step>
  </Request>
</Flow>
```

3. Redeploy and test:

```bash
apigeecli apis create bundle --name hello-v1 --proxy-folder ./hello-v1/apiproxy --org "$ORG" --token "$TOKEN"
apigeecli apis deploy --name hello-v1 --rev 5 --org "$ORG" --env "$ENV" --ovr --wait --token "$TOKEN"

curl -s "https://$RUNTIME_HOST/hello-v1/boom" | jq .
# → a well-formed OBIE error envelope, status 400
```

4. **Refactor challenge:** rewrite the `X-Account-Upper` header to *not* use JS (you already did — it's a template). Internalize that most "I need JavaScript" instincts are actually a template or an AssignMessage.

## Recap — you can now…

- Write a **JavaScript policy** that reads/writes flow variables via `context`.
- Use **message templates** and built-in functions for dynamic strings without code.
- Apply the **declarative-first** rule and keep JS for genuinely procedural logic.

## Check yourself

1. How does a JavaScript policy pass a value to a downstream AssignMessage?
2. Name two things you should *not* do in a JS policy.
3. You need a fresh UUID header — JS or template?

**Next:** Day 09 — call a *second* service mid-flow with **ServiceCallout**, and stop hard-coding backend hosts using **TargetServers**.
