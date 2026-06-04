# Day 18 — FAPI 1.0 Advanced: the security profile

> **Bottom line:** You'll read the **FAPI 1.0 Advanced** security profile requirement-by-requirement and map each one to a concrete Apigee mechanism you've already learned — so tomorrow you can build it.

> **Builds on Days 14–17:** FAPI is not new technology; it's a *strict configuration* of OAuth, JWT, and mTLS with extra rules.

## Why this matters

UK Open Banking mandates **FAPI 1.0 Advanced** for the security of account and payment APIs. "Make it FAPI-compliant" is a checklist, and conformance is tested (the OpenID Foundation FAPI conformance suite). Knowing the checklist — and where each item lives in Apigee — is the difference between passing and a failed audit.

## What FAPI is

FAPI (Financial-grade API) is an OpenID Foundation profile that tightens OAuth 2.0 / OpenID Connect for high-value APIs. **FAPI 1.0** has two profiles:

- **Baseline** (read-only / lower risk)
- **Advanced** (read-write / payments) ← what UK OB requires

It constrains *how* you use OAuth: which grant types, which algorithms, how the client authenticates, how requests and responses are integrity-protected, and how tokens are bound to the client.

```widget
{"type":"chart","title":"Plain OAuth 2.0 vs FAPI 1.0 Advanced","chartType":"radar","height":360,
 "data":{"labels":["Client auth strength","Request integrity (PAR/JWT)","Token binding (cert)","Response integrity (JARM)","Algorithm strictness","PKCE / replay defense"],
  "datasets":[
    {"label":"Plain OAuth 2.0","data":[2,1,0,0,1,1],"borderColor":"#9aa7b6","backgroundColor":"rgba(154,167,182,0.25)"},
    {"label":"FAPI 1.0 Advanced","data":[5,5,5,4,5,5],"borderColor":"#1a73e8","backgroundColor":"rgba(26,115,232,0.20)"}
  ]},
 "options":{"scales":{"r":{"min":0,"max":5,"ticks":{"stepSize":1}}}},
 "caption":"FAPI doesn't add new technology — it ratchets every OAuth dimension to its strongest setting."}
```

## The FAPI 1.0 Advanced checklist → Apigee mapping

| # | FAPI Advanced requirement | What it means | Apigee mechanism |
|---|---------------------------|---------------|------------------|
| 1 | **Authorization-code flow only** (no implicit) | `response_type=code` (or `code id_token`) | OAuthV2 GenerateAuthorizationCode (Day 15) |
| 2 | **PKCE** (S256) | Code-interception defense | S256 check (Day 15) |
| 3 | **Confidential client auth** via `private_key_jwt` **or** `tls_client_auth` (mTLS) | No shared client secrets | VerifyJWT on `client_assertion`, **or** mTLS cert → app mapping (Day 16) |
| 4 | **Signed request object** (PS256) | Authorization params are integrity-protected in a JWT (`request`/`request_uri`) | VerifyJWT `<Algorithm>PS256</Algorithm>` (Day 15) |
| 5 | **PAR — Pushed Authorization Requests** | Client pushes the request object to a back-channel `/par` endpoint first, gets a `request_uri` | A proxy flow that VerifyJWTs and stores it (Day 19) |
| 6 | **Sender-constrained / certificate-bound tokens** | Access token bound to the client's mTLS cert (`cnf`/`x5t#S256`) | Bind at token issue; verify thumbprint on resource calls (Day 16/24) |
| 7 | **`PS256` / `ES256` signatures only** (no `RS256`, no `none`) | Strong algorithms | GenerateJWT/VerifyJWT `<Algorithm>` |
| 8 | **JARM or signed id_token with `s_hash`/`c_hash`** | Authorization *response* integrity | GenerateJWT for the response/id_token with hash claims (Day 19) |
| 9 | **`nonce` + `state`** required and validated | Replay/CSRF defense | Validate in the authorize flow |
| 10 | **`x-fapi-interaction-id`** echoed; **`x-fapi-auth-date`**, **`x-fapi-customer-ip-address`** handled | Traceability headers | AssignMessage (Day 5/12) |
| 11 | **mTLS on all token & resource endpoints** | Transport-level client auth | Northbound mTLS (Day 16) |
| 12 | **Short-lived access tokens**, exact-match `redirect_uri`, no token in URL | Hardening | OAuthV2 `ExpiresIn`, strict redirect validation |

> **The big four to internalize:** (a) **PAR** pushes the signed request object up front; (b) the request object is a **PS256 JWT**; (c) the client authenticates with **private_key_jwt or mTLS**; (d) tokens are **certificate-bound**. Everything else is hardening around those.

## How the pieces fit in a FAPI authorization

```text
1. TPP signs a request object (PS256 JWT) with its OB signing key.
2. TPP → POST /par  (mTLS, client_assertion=private_key_jwt, request=<JWT>)
        Apigee verifies client + request object, returns request_uri.
3. TPP → GET /authorize?client_id=..&request_uri=..   (user consents)
        Apigee returns code (+ optional id_token with c_hash/s_hash) → JARM-protected.
4. TPP → POST /token  (mTLS, client_assertion, code, code_verifier)
        Apigee issues a cert-bound access token (cnf.x5t#S256 = TPP cert thumbprint).
5. TPP → GET /accounts  (mTLS, Bearer token)
        Apigee verifies token AND that the presenting cert == cnf thumbprint.
```

Notice: **every** numbered Apigee mechanism from Days 14–17 appears here. FAPI is the assembly.

## `private_key_jwt` client authentication

Instead of a client secret, the TPP signs a short JWT (`client_assertion`) proving key possession. Apigee verifies it against the TPP's registered JWKS:

```xml
<VerifyJWT name="JWT-VerifyClientAssertion">
  <Algorithm>PS256</Algorithm>
  <Source>request.formparam.client_assertion</Source>
  <PublicKey><JWKS ref="tpp.jwks"/></PublicKey>
  <Issuer>{request.formparam.client_id}</Issuer>
  <Subject>{request.formparam.client_id}</Subject>
  <Audience>https://{RUNTIME_HOST}/oauth/token</Audience>
  <AdditionalClaims>
    <Claim name="jti"/>   <!-- must be present & one-time (replay defense) -->
  </AdditionalClaims>
</VerifyJWT>
```

## Lab — audit a flow against the checklist

You won't build today (that's Day 19) — you'll *assess*:

1. Take your Day 15 auth-code proxy. Walk the 12-row table and mark each row **present / missing**. You'll likely find PAR, PS256 request objects, private_key_jwt, and cert-binding all missing — that's exactly Day 19's work.
2. Write down, for your proxy, *which policy file* will satisfy each missing row. This is your build plan.
3. Download the **OpenID Foundation FAPI conformance suite** test list and note which tests map to rows 4, 5, 6, 8 — these are the ones teams most often fail.

```text
# Your gap list should look like:
[ ] PAR endpoint                → new flow + VerifyJWT + short-lived request_uri store
[ ] PS256 request object        → VerifyJWT (PS256) on request/request_uri
[ ] private_key_jwt client auth → VerifyJWT on client_assertion
[ ] cert-bound tokens           → add cnf.x5t#S256 at issue; verify at resource
[ ] JARM / c_hash,s_hash        → GenerateJWT response object
```

## Recap — you can now…

- State the **FAPI 1.0 Advanced** requirements as a checklist.
- Map **every** requirement to an Apigee mechanism you already know.
- Recognize the **big four** (PAR, PS256 request object, private_key_jwt/mTLS, cert-bound tokens).

## Check yourself

1. Which signing algorithms does FAPI Advanced permit — and which does it forbid?
2. What does PAR move *off* the front channel, and why is that safer?
3. "Sender-constrained token" — bound to *what*, and verified *how* on a resource call?

```widget
{"type":"quiz","title":"Day 18 check","questions":[
  {"q":"Which signing algorithms does FAPI 1.0 Advanced permit?","options":["PS256 / ES256","RS256 only","HS256 (HMAC)","'none' is allowed for testing"],"answer":0,"explain":"FAPI Advanced requires PS256 or ES256 and explicitly forbids RS256 and 'none'."},
  {"q":"What does PAR (Pushed Authorization Requests) move off the front channel?","options":["The (signed) authorization request object","The issued access token","The user's password","The API product definition"],"answer":0,"explain":"The client pushes the request object to a back-channel /par endpoint first and gets a request_uri — keeping request parameters out of the browser URL where they could be tampered with."},
  {"q":"A 'sender-constrained' access token is bound to…","options":["The client's mTLS certificate (cnf / x5t#S256)","The user's IP address","The redirect_uri","The environment group"],"answer":0,"explain":"The token carries the client cert thumbprint; the resource verifies the presenting cert matches, so a stolen token can't be replayed without the private key."}
]}
```

**Next:** Day 19 — Week 3 capstone: **build** the FAPI flow — PAR, signed request object, private_key_jwt, and a certificate-bound token.
