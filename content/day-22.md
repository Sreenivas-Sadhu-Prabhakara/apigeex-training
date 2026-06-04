# Day 22 — AISP: account information APIs

> **Bottom line:** You'll expose the OBIE **Accounts, Balances, and Transactions** endpoints, each gated by the consent guard with the *right permission*, returning spec-shaped responses with correct FAPI headers and pagination.

> **Builds on Day 21:** every endpoint here reuses `sf-consent-guard`; today you set the per-endpoint `requiredPermission` and shape OBIE responses.

## Why this matters

This is what an AISP actually consumes — the data layer behind every budgeting and aggregation app. It's also where consent meets *granularity*: a consent for `ReadBalances` must not be able to read transactions. Mapping endpoints → required permissions correctly is the security crux of AISP.

## Endpoint → permission map

| Method & path | Returns | Required permission |
|---------------|---------|---------------------|
| `GET /accounts` | List of consented accounts | `ReadAccountsBasic` / `ReadAccountsDetail` |
| `GET /accounts/{AccountId}` | One account | `ReadAccountsDetail` |
| `GET /accounts/{AccountId}/balances` | Balances | `ReadBalances` |
| `GET /accounts/{AccountId}/transactions` | Transactions (paged) | `ReadTransactionsDetail` (+ Credits/Debits) |
| `GET /balances` | Balances across all consented accounts | `ReadBalances` |

> **Filtering by consent:** `GET /accounts` returns **only** the accounts the PSU selected during authorization — not every account the customer holds. Store the selected account list with the consent at authorization time and filter against it here.

## Wire an endpoint with the consent guard

Set the required permission, then call the shared guard, then fetch from core via TargetServer:

```xml
<Flow name="GetTransactions">
  <Condition>(proxy.pathsuffix MatchesPath "/accounts/{AccountId}/transactions") and (request.verb = "GET")</Condition>
  <Request>
    <Step><Name>EV-AccountId</Name></Step>
    <Step><Name>AM-RequirePermission-Tx</Name></Step>   <!-- sets consent.requiredPermission -->
    <Step><Name>FC-ConsentGuard</Name></Step>           <!-- sf-consent-guard: status+expiry+permission -->
    <Step><Name>RF-AccountNotConsented</Name>
      <Condition>NOT (consent.accounts ~~ ob.AccountId)</Condition></Step>
  </Request>
  <Response>
    <Step><Name>JS-ShapeTransactions</Name></Step>      <!-- map core → OBIE schema -->
    <Step><Name>AM-PaginationLinks</Name></Step>
  </Response>
</Flow>
```

```xml
<AssignMessage name="AM-RequirePermission-Tx">
  <AssignVariable><Name>consent.requiredPermission</Name><Value>ReadTransactionsDetail</Value></AssignVariable>
</AssignMessage>
```

## OBIE response shape

OBIE responses follow a strict envelope: `Data`, `Links`, `Meta`. Map your core banking response into it:

```javascript
// resources/jsc/shapeTransactions.js — core → OBIE v3.1
var core = JSON.parse(context.getVariable('coreResponse.content') || '{}');
var accountId = context.getVariable('ob.AccountId');
var txns = (core.transactions || []).map(function (t) {
  return {
    AccountId: accountId,
    TransactionId: t.id,
    CreditDebitIndicator: t.amount >= 0 ? 'Credit' : 'Debit',
    Status: 'Booked',
    BookingDateTime: t.bookedAt,
    Amount: { Amount: Math.abs(t.amount).toFixed(2), Currency: t.currency },
    TransactionInformation: t.description
  };
});
var self = context.getVariable('proxy.url');
var body = {
  Data: { Transaction: txns },
  Links: { Self: self },
  Meta: { TotalPages: 1 }
};
context.setVariable('response.content', JSON.stringify(body));
context.setVariable('response.header.Content-Type', 'application/json');
```

## FAPI response headers

Every AISP response must echo/emit the FAPI traceability headers (you built the inbound check on Day 12):

```xml
<AssignMessage name="AM-FapiResponseHeaders">
  <Set>
    <Headers>
      <Header name="x-fapi-interaction-id">{fapi.interactionId}</Header>
    </Headers>
  </Set>
  <AssignTo createNew="false" type="response">response</AssignTo>
</AssignMessage>
```

## Pagination

Transactions are paged. OBIE uses `?page=` with `Links.Next`/`Links.Prev` and `Meta.TotalPages`. Build links from the request URL:

```xml
<AssignMessage name="AM-PaginationLinks">
  <AssignVariable><Name>ob.page</Name><Template>{request.queryparam.page}</Template><Value>1</Value></AssignVariable>
  <!-- JS-ShapeTransactions can append Links.Next when more pages exist -->
</AssignMessage>
```

## Lab — serve consented AISP data

1. Build the `aisp-resources` proxy with `GET /accounts`, `/accounts/{id}/balances`, `/accounts/{id}/transactions`, each setting its `requiredPermission` and calling `FC-ConsentGuard`.
2. Point the TargetEndpoint at the `core-banking` TargetServer (mock).
3. Run with an **Authorised** consent token and check enforcement:

```bash
# accounts: returns only consented accounts
curl -s ".../v3.1/aisp/accounts" -H "Authorization: Bearer $AC_TOKEN" -H "x-fapi-interaction-id: $(uuidgen)" | jq '.Data.Account[].AccountId'

# balances: needs ReadBalances — present → 200
curl -s -o /dev/null -w "%{http_code}\n" ".../v3.1/aisp/accounts/22289/balances" -H "Authorization: Bearer $AC_TOKEN" -H "x-fapi-interaction-id: $(uuidgen)"

# transactions with a consent that LACKS ReadTransactionsDetail → 403 UK.OBIE.Resource.InvalidConsentStatus
curl -s ".../v3.1/aisp/accounts/22289/transactions" -H "Authorization: Bearer $AC_TOKEN_NO_TX" -H "x-fapi-interaction-id: $(uuidgen)" | jq .
```

4. Confirm an account **not** in the consent's selected list returns `403`/`404` even with a valid token.

## Recap — you can now…

- Map each AISP endpoint to its **required permission** and enforce it.
- Filter `/accounts` to the PSU's **consented accounts** only.
- Shape core responses into the **OBIE `Data`/`Links`/`Meta`** envelope with pagination and FAPI headers.

## Check yourself

1. A token's consent has `ReadBalances` but not `ReadTransactionsDetail`. What should `/transactions` return?
2. Why might `/accounts` return fewer accounts than the customer actually holds?
3. Which three top-level keys make up the OBIE response envelope?

**Next:** Day 23 — money moves: the **PISP payment-initiation** flow with idempotency and funds confirmation.
