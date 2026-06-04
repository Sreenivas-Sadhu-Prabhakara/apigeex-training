# Day 14 — OAuth 2.0: client credentials & token endpoints

> **Bottom line:** You'll stand up an OAuth **token endpoint** on Apigee with the **OAuthV2** policy, issue tokens via the **client-credentials** grant, and protect a resource proxy with **VerifyAccessToken**.

> **Builds on Day 13:** the OAuth `client_id`/`client_secret` *are* the developer app's `consumerKey`/`consumerSecret`. Apigee is the authorization server.

## Why this matters

API keys identify an app but travel in the clear and never expire. OAuth 2.0 gives you short-lived, scoped **bearer tokens**. Apigee X can act as the OAuth 2.0 **authorization server** out of the box — no separate IdP required for machine-to-machine. Client credentials is the simplest grant and the backbone of B2B/TPP-to-bank server flows.

## The OAuthV2 policy: one policy, many operations

`OAuthV2` does different jobs depending on its `<Operation>`:

| Operation | Role |
|-----------|------|
| `GenerateAccessToken` | Token endpoint — mints an access token |
| `VerifyAccessToken` | Resource side — validates the bearer token |
| `GenerateAuthorizationCode` | Authorize endpoint (Day 15) |
| `RefreshAccessToken` | Exchange a refresh token |
| `InvalidateToken` | Revoke |

## Build the token endpoint

A proxy (or a flow in your proxy) exposes `POST /oauth/token`. The grant arrives as form params; OAuthV2 reads them.

```xml
<!-- policies/OA-GenerateToken.xml -->
<OAuthV2 name="OA-GenerateToken">
  <DisplayName>OA-GenerateToken</DisplayName>
  <Operation>GenerateAccessToken</Operation>
  <!-- token lifetime: 5 minutes (FAPI likes short tokens) -->
  <ExpiresIn>300000</ExpiresIn>
  <SupportedGrantTypes>
    <GrantType>client_credentials</GrantType>
  </SupportedGrantTypes>
  <!-- where to find the grant type -->
  <GrantType>request.formparam.grant_type</GrantType>
  <!-- echo scopes from the request, validated against the product's scopes -->
  <Scope>request.queryparam.scope</Scope>
  <GenerateResponse enabled="true"/>
</OAuthV2>
```

Before generating, you must validate the client credentials. Two common patterns:

1. **VerifyAPIKey-style:** clients send `client_id`/`client_secret`; you verify with a small flow.
2. **Basic auth header:** decode `Authorization: Basic ...` then verify.

A clean approach uses a dedicated credential check before `GenerateAccessToken`:

```xml
<!-- policies/OA-VerifyClient.xml : confirm client_id+secret belong to a real app -->
<OAuthV2 name="OA-VerifyClient">
  <Operation>GenerateAccessToken</Operation>
  <ExpiresIn>300000</ExpiresIn>
  <SupportedGrantTypes><GrantType>client_credentials</GrantType></SupportedGrantTypes>
  <GrantType>request.formparam.grant_type</GrantType>
  <ClientId>request.formparam.client_id</ClientId>
  <GenerateResponse enabled="true"/>
</OAuthV2>
```

> Apigee validates that the `client_id` (+ secret) maps to a developer app whose product grants the requested scopes. Scope enforcement is automatic when scopes are defined on the product (Day 13).

### The token flow

```xml
<Flow name="Token">
  <Condition>(proxy.pathsuffix = "/oauth/token") and (request.verb = "POST")</Condition>
  <Request>
    <Step><Name>OA-GenerateToken</Name></Step>
  </Request>
</Flow>
```

> Set the RouteRule so `/oauth/token` has **no** TargetEndpoint — `GenerateResponse` builds the JSON token response itself.

```widget
{"type":"sequence","title":"Client-credentials grant, step by step","actors":[
  {"id":"app","label":"TPP app"},
  {"id":"as","label":"Apigee · token endpoint"},
  {"id":"rs","label":"Apigee · resource"}
],"steps":[
  {"from":"app","to":"as","label":"POST /oauth/token","note":"The TPP sends grant_type=client_credentials with its client_id and client_secret (the developer app's consumerKey/secret)."},
  {"from":"as","to":"as","label":"validate client + scopes","note":"Apigee checks the credentials map to a developer app whose API product grants the requested scopes."},
  {"from":"as","to":"app","label":"access_token (5 min)","kind":"return","note":"A short-lived bearer token is returned. No user is involved — this is machine-to-machine."},
  {"from":"app","to":"rs","label":"GET /accounts  (Bearer token)","note":"The TPP calls the protected resource, presenting the token in the Authorization header."},
  {"from":"rs","to":"rs","label":"VerifyAccessToken + scope","note":"The OAuthV2 VerifyAccessToken policy validates the token and required scope before the flow continues."},
  {"from":"rs","to":"app","label":"200 data","kind":"return","note":"Token valid and scoped → the request proceeds to the backend and data returns."}
]}
```

## Protect a resource with VerifyAccessToken

On the AISP proxy, replace (or add to) VerifyAPIKey with token verification:

```xml
<!-- policies/OA-VerifyToken.xml -->
<OAuthV2 name="OA-VerifyToken">
  <Operation>VerifyAccessToken</Operation>
  <!-- require a scope for this operation -->
  <Scope>accounts</Scope>
</OAuthV2>
```

On success you get `oauth_access_token`, `apiproduct.name`, `developer.app.name`, `scope`, and any custom claims — same rich context as VerifyAPIKey, now token-based.

## Lab — issue and use a token

1. Add the token flow + policies to a small `oauth-v1` proxy (or your AISP proxy), and `OA-VerifyToken` on `/accounts`.
2. Deploy, then run the full handshake:

```bash
CK="<consumerKey>"; CS="<consumerSecret>"

# 1) get a token (client credentials)
TOKEN_JSON=$(curl -s -X POST "https://$RUNTIME_HOST/oauth-v1/oauth/token?scope=accounts" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=$CK&client_secret=$CS")
echo "$TOKEN_JSON" | jq .
AT=$(echo "$TOKEN_JSON" | jq -r .access_token)

# 2) call a protected resource with the bearer token
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $AT" -H "x-fapi-interaction-id: $(uuidgen)" \
  "https://$RUNTIME_HOST/aisp-house-style/accounts"

# 3) wrong/expired token → 401
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer not-a-token" \
  "https://$RUNTIME_HOST/aisp-house-style/accounts"
```

## Recap — you can now…

- Run an OAuth 2.0 **token endpoint** on Apigee with `GenerateAccessToken`.
- Issue tokens via **client credentials** tied to a developer app.
- Protect resources with **VerifyAccessToken** and scope checks.

## Check yourself

1. What Apigee objects back the OAuth `client_id` and `client_secret`?
2. Why does the `/oauth/token` flow use a **no-route** RouteRule?
3. Where do the *scopes* a token may request actually come from?

**Next:** Day 15 — the user-present flow: **authorization code + PKCE**, and minting/verifying **JWTs**.
