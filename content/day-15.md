# Day 15 — OAuth authorization code + PKCE & JWT

> **Bottom line:** You'll implement the user-present **authorization-code + PKCE** flow on Apigee, and mint/verify **JWTs** with GenerateJWT/VerifyJWT — the exact pieces Open Banking's consent and `id_token` need.

> **Builds on Day 14:** same OAuthV2 policy, new operations; JWTs become the token format FAPI requires.

## Why this matters

Client credentials is machine-to-machine. But account access requires a **human** (the bank customer) to authorize a TPP — that's the authorization-code grant. **PKCE** hardens it against code interception. And FAPI mandates **JWTs**: signed request objects, signed `id_token`s, and (Day 18) JWT-secured responses. Today you build both halves.

## Authorization-code + PKCE, end to end

```text
1. App → /authorize?response_type=code&client_id=..&redirect_uri=..
            &scope=accounts&state=..&code_challenge=..&code_challenge_method=S256
2. Apigee authenticates the user (delegated to your login app/IdP),
   the user consents, Apigee issues an authorization code → redirect back with ?code=..
3. App → /token  grant_type=authorization_code&code=..&code_verifier=..
4. Apigee verifies code + PKCE, returns access_token (+ refresh_token, id_token)
```

```widget
{"type":"sequence","title":"Authorization code + PKCE, step by step","actors":[
  {"id":"app","label":"TPP app"},
  {"id":"psu","label":"PSU (browser)"},
  {"id":"as","label":"Apigee authz server"}
],"steps":[
  {"from":"app","to":"as","label":"/authorize + code_challenge (S256)","note":"The app starts the flow and sends a PKCE code_challenge — the SHA-256 hash of a secret code_verifier it keeps to itself."},
  {"from":"as","to":"psu","label":"login + consent screen","note":"Apigee delegates user authentication to your login app/IdP and shows the consent screen."},
  {"from":"psu","to":"as","label":"authenticate + approve","kind":"return","note":"The PSU logs in and approves the requested access."},
  {"from":"as","to":"app","label":"redirect ?code=…","kind":"return","note":"Apigee issues an authorization code, storing the code_challenge alongside it."},
  {"from":"app","to":"as","label":"POST /token + code_verifier","note":"The app redeems the code, now revealing the original code_verifier."},
  {"from":"as","to":"as","label":"SHA256(verifier) == challenge?","note":"Apigee recomputes S256(code_verifier) and compares to the stored challenge. This is what defeats an intercepted authorization code."},
  {"from":"as","to":"app","label":"access_token + id_token","kind":"return","note":"Match → tokens issued. A stolen code is useless without the matching verifier."}
]}
```

### The /authorize endpoint

```xml
<!-- policies/OA-GenerateAuthCode.xml -->
<OAuthV2 name="OA-GenerateAuthCode">
  <Operation>GenerateAuthorizationCode</Operation>
  <GenerateResponse enabled="true"/>
  <!-- PKCE: capture and store the challenge with the code -->
  <Attributes>
    <Attribute name="code_challenge" ref="request.queryparam.code_challenge" display="false"/>
    <Attribute name="code_challenge_method" ref="request.queryparam.code_challenge_method" display="false"/>
  </Attributes>
</OAuthV2>
```

> In a real deployment the `/authorize` flow first **authenticates the user** (redirect to your login UI / IdP) and renders a **consent screen**, then runs `GenerateAuthorizationCode`. Apigee mints the code; your UI handles the human steps.

### The /token endpoint (auth-code grant + PKCE verification)

```xml
<!-- policies/OA-RedeemCode.xml -->
<OAuthV2 name="OA-RedeemCode">
  <Operation>GenerateAccessToken</Operation>
  <ExpiresIn>300000</ExpiresIn>
  <RefreshTokenExpiresIn>86400000</RefreshTokenExpiresIn>
  <SupportedGrantTypes><GrantType>authorization_code</GrantType></SupportedGrantTypes>
  <GrantType>request.formparam.grant_type</GrantType>
  <Code>request.formparam.code</Code>
  <GenerateResponse enabled="true"/>
</OAuthV2>
```

PKCE verification (compare `code_verifier` → SHA256 → base64url against the stored `code_challenge`) is done in a small step before redeem: read the stored challenge from the code's attributes, recompute from `code_verifier`, and RaiseFault on mismatch. Apigee exposes the code's stored attributes after a `VerifyAuthorizationCode`-style lookup; a JavaScript step computes `BASE64URL(SHA256(code_verifier))` and compares.

```javascript
// resources/jsc/verifyPkce.js  (S256)
var crypto = require('crypto');           // available in Apigee JS callout
var verifier = context.getVariable('request.formparam.code_verifier') || '';
var stored   = context.getVariable('oauthv2authcode.OA-LookupCode.code_challenge') || '';
var hash = crypto.createHash('sha256').update(verifier).digest('base64')
             .replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,''); // base64url
context.setVariable('pkce.valid', (hash === stored).toString());
```

## JWT policies

Three policies cover the JWT lifecycle:

| Policy | Job |
|--------|-----|
| **GenerateJWT** | Sign a JWT (e.g. an `id_token`) |
| **VerifyJWT** | Validate signature, issuer, audience, expiry |
| **DecodeJWT** | Read claims *without* verifying (e.g. to inspect before routing) |

### Mint a signed id_token

```xml
<GenerateJWT name="JWT-IdToken">
  <DisplayName>JWT-IdToken</DisplayName>
  <Algorithm>RS256</Algorithm>
  <!-- private key from a keystore (Day 16) -->
  <PrivateKey>
    <Value ref="private.signing.key"/>
  </PrivateKey>
  <Subject>{oauthv2accesstoken.OA-RedeemCode.developer.id}</Subject>
  <Issuer>https://{RUNTIME_HOST}</Issuer>
  <Audience>{client_id}</Audience>
  <ExpiresIn>5m</ExpiresIn>
  <AdditionalClaims>
    <Claim name="scope">{scope}</Claim>
    <Claim name="acr">urn:openbanking:psd2:sca</Claim>
  </AdditionalClaims>
  <OutputVariable>jwt.idtoken</OutputVariable>
</GenerateJWT>
```

### Verify an incoming JWT (e.g. a TPP's signed request object)

```xml
<VerifyJWT name="JWT-VerifyRequestObject">
  <Algorithm>PS256</Algorithm>
  <Source>request.formparam.request</Source>     <!-- the request object JWT -->
  <PublicKey>
    <!-- TPP's JWKS, fetched from the OB directory (Day 24) -->
    <JWKS ref="tpp.jwks"/>
  </PublicKey>
  <Issuer>{tpp.client_id}</Issuer>
  <Audience>https://{RUNTIME_HOST}</Audience>
</VerifyJWT>
```

> **FAPI uses `PS256` (RSASSA-PSS), not `RS256`,** for signing — keep that in mind for Day 18/19. `DecodeJWT` is handy to read a token's `kid`/`iss` *before* deciding which key to verify with.

## Lab — auth code + PKCE round trip

1. Build an `/authorize` flow (GenerateAuthorizationCode) and a `/token` flow (auth-code grant + PKCE JS check).
2. Generate a PKCE pair locally and run the flow:

```bash
# create a PKCE verifier + S256 challenge
VERIFIER=$(openssl rand -base64 48 | tr -d '=+/' | cut -c1-43)
CHALLENGE=$(printf '%s' "$VERIFIER" | openssl dgst -sha256 -binary | openssl base64 | tr '+/' '-_' | tr -d '=')

echo "verifier=$VERIFIER"; echo "challenge=$CHALLENGE"
# Step 1: open /authorize?...&code_challenge=$CHALLENGE&code_challenge_method=S256 in a browser,
#         complete the (mock) consent, capture ?code=XYZ from the redirect.
# Step 3: redeem:
curl -s -X POST "https://$RUNTIME_HOST/oauth-v1/oauth/token" \
  -d "grant_type=authorization_code&code=XYZ&code_verifier=$VERIFIER&client_id=$CK" | jq .
```

3. Add `JWT-IdToken` to the token response and decode the returned `id_token` at jwt.io to inspect the claims.

## Recap — you can now…

- Implement **authorization-code + PKCE** with GenerateAuthorizationCode and the S256 check.
- **Mint** signed JWTs (GenerateJWT) and **verify** TPP JWTs (VerifyJWT), reading claims with DecodeJWT.
- Know FAPI's algorithm preference (**PS256**) for later.

## Check yourself

1. What attack does PKCE specifically defend against?
2. Which JWT policy reads claims *without* checking the signature?
3. Which signing algorithm does FAPI Advanced require?

**Next:** Day 16 — the *transport* layer those keys live in: **TLS, mutual TLS, keystores and truststores**.
