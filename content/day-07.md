# Day 7 — Mediation & variables: AssignMessage + ExtractVariables

> **Bottom line:** You'll read values out of any part of a request with **ExtractVariables**, and build/modify requests and responses precisely with **AssignMessage**, using Apigee's **flow variables** as the connective tissue.

> **Builds on Day 5–6:** you've used AssignMessage to set a payload; today you learn the full read/transform/write loop.

## Why this matters

Mediation — turning the client's request into what the backend wants, and the backend's response into what the client expects — is the single most common proxy job. In banking you constantly reshape: extract an account id from the path, inject auth headers for the core system, strip internal fields from responses.

## Flow variables: the data bus

Everything Apigee knows lives in **variables**. You read them in conditions, templates, and policies. The essentials:

| Variable | Holds |
|----------|-------|
| `request.verb`, `request.uri`, `proxy.pathsuffix` | method, full URI, path after BasePath |
| `request.header.NAME` / `response.header.NAME` | a header value |
| `request.queryparam.NAME` | a query parameter |
| `request.content` / `response.content` | the body as a string |
| `request.formparam.NAME` | a form field |
| `client.ip`, `messageid`, `system.timestamp` | context |
| `target.url` | the resolved backend URL |

Custom variables you create live in whatever name you choose (convention: `prefix.name`, e.g. `ob.accountId`).

## ExtractVariables — read structured data out

It pulls values from path, query, header, form, JSON, or XML into named variables.

```xml
<ExtractVariables name="EV-AccountId">
  <DisplayName>EV-AccountId</DisplayName>
  <!-- prefix for all created variables: ob.* -->
  <VariablePrefix>ob</VariablePrefix>

  <!-- from the URI path: /accounts/{accountId}/transactions -->
  <URIPath>
    <Pattern ignoreCase="false">/accounts/{accountId}/transactions</Pattern>
  </URIPath>

  <!-- from a query param ?fromBookingDateTime=... -->
  <QueryParam name="fromBookingDateTime">
    <Pattern ignoreCase="true">{fromDate}</Pattern>
  </QueryParam>

  <!-- from a JSON request body using JSONPath -->
  <JSONPayload>
    <Variable name="amount"><JSONPath>$.Data.Initiation.InstructedAmount.Amount</JSONPath></Variable>
    <Variable name="currency"><JSONPath>$.Data.Initiation.InstructedAmount.Currency</JSONPath></Variable>
  </JSONPayload>

  <!-- from a header -->
  <Header name="x-fapi-interaction-id">
    <Pattern>{interactionId}</Pattern>
  </Header>
</ExtractVariables>
```

After this runs you have `ob.accountId`, `ob.fromDate`, `ob.amount`, `ob.currency`, `ob.interactionId`.

> **Source matters:** by default ExtractVariables reads the **request**. To read a response body, add `<Source>response</Source>`.

## AssignMessage — build and modify, four verbs

`AssignMessage` has four kinds of children. Know what each does:

| Child | Does |
|-------|------|
| `<Set>` | Overwrite headers, query params, payload, verb, path, status |
| `<Add>` | Append (e.g. add a header **without** removing existing ones) |
| `<Copy>` | Copy from the *source* message into the target |
| `<Remove>` | Delete headers/params/payload |
| `<AssignVariable>` | Create/seed a flow variable |

### Inject backend auth + correlation onto the request

```xml
<AssignMessage name="AM-BackendRequest">
  <DisplayName>AM-BackendRequest</DisplayName>

  <!-- seed a variable, then use it in a template below -->
  <AssignVariable>
    <Name>ob.correlationId</Name>
    <Ref>messageid</Ref>
  </AssignVariable>

  <Set>
    <Headers>
      <Header name="Authorization">Bearer {private.backend.token}</Header>
      <Header name="X-Correlation-Id">{ob.correlationId}</Header>
    </Headers>
  </Set>

  <Remove>
    <Headers>
      <Header name="x-client-id"/>   <!-- don't leak the northbound client id to the core system -->
    </Headers>
  </Remove>

  <!-- run this against the outbound request message -->
  <AssignTo createNew="false" type="request">request</AssignTo>
</AssignMessage>
```

### Reshape the response for the client

```xml
<AssignMessage name="AM-ClientResponse">
  <Set>
    <Payload contentType="application/json">
{
  "accountId": "{ob.accountId}",
  "amount": "{ob.amount}",
  "currency": "{ob.currency}",
  "retrievedAt": "{system.timestamp}"
}
    </Payload>
  </Set>
  <AssignTo createNew="false" type="response">response</AssignTo>
</AssignMessage>
```

`{ob.accountId}` is **message templating** — any `{variable}` in a payload, header, or path is substituted at runtime. (Deep-dive tomorrow.)

## Lab — extract → transform → respond

1. Add `EV-AccountId.xml` and `AM-ClientResponse.xml`.
2. Create a conditional flow for `GET /accounts/{accountId}/transactions` that runs `EV-AccountId` (Request) then `AM-ClientResponse` (Response). Use a no-route so you respond from policies:

```xml
<Flow name="GetTransactions">
  <Condition>(proxy.pathsuffix MatchesPath "/accounts/{id}/transactions") and (request.verb = "GET")</Condition>
  <Request><Step><Name>EV-AccountId</Name></Step></Request>
  <Response><Step><Name>AM-ClientResponse</Name></Step></Response>
</Flow>
```

3. Redeploy and test the extraction:

```bash
curl -s "https://$RUNTIME_HOST/hello-v1/accounts/22289/transactions?fromBookingDateTime=2026-01-01" | jq .
# → accountId "22289" pulled from the path appears in the response
```

## Recap — you can now…

- Navigate the **flow variable** namespace.
- **ExtractVariables** from path, query, header, and JSON body.
- **AssignMessage** with Set/Add/Copy/Remove/AssignVariable to mediate both directions.

## Check yourself

1. Which AssignMessage child adds a header *without* clobbering an existing one of the same name?
2. You need a value from the **response** body — what one element must ExtractVariables include?
3. What's the difference between `<Set><Headers>` and `<Add><Headers>`?

**Next:** Day 08 — when XML policies aren't enough: the **JavaScript policy** and dynamic **message templates**.
