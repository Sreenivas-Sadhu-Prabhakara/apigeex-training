# Day 19 — Implementing FAPI on Apigee (Week 3 capstone)

> **Bottom line:** You'll build the FAPI 1.0 Advanced authorization server on Apigee: a **PAR** endpoint that verifies a **PS256 request object** and **private_key_jwt** client auth, then issues a **certificate-bound** access token verified on every resource call.

> **Builds on Day 18's gap list:** today you close every box you ticked "missing."

## Why this matters

This is the proxy a FAPI conformance suite runs against. Banks fail certification on exactly these flows. Building it once, correctly, is the single most valuable artifact in the course — Weeks 4 reuse it as the security layer under consent, AISP, and PISP.

## Architecture

```text
fapi-as  (one proxy, four flows)
  POST /par        → verify client_assertion (PS256) + request object (PS256), store, return request_uri
  GET  /authorize  → resolve request_uri, authenticate user + consent, issue code (+ id_token w/ hashes)
  POST /token      → verify client_assertion, redeem code+PKCE, mint cert-bound access token
  (resource proxies VerifyAccessToken + check cnf.x5t#S256 == presented cert)
```

```widget
{"type":"sequence","title":"The FAPI dance: PAR → authorize → token → resource","actors":[
  {"id":"tpp","label":"TPP"},
  {"id":"as","label":"Apigee FAPI AS"},
  {"id":"rs","label":"Apigee resource"}
],"steps":[
  {"from":"tpp","to":"tpp","label":"sign request object (PS256)","note":"The TPP signs a request object JWT with its OBSEAL key and builds a private_key_jwt client_assertion to authenticate itself."},
  {"from":"tpp","to":"as","label":"POST /par (mTLS)","note":"Pushed Authorization Request: the signed request object goes up the back channel, with the client_assertion."},
  {"from":"as","to":"as","label":"verify client + request object","note":"VerifyJWT (PS256) on both; store the claims; mint a one-time, short-lived request_uri."},
  {"from":"as","to":"tpp","label":"request_uri (60s)","kind":"return","note":"A reference to the stored request — nothing sensitive travels on the front channel."},
  {"from":"tpp","to":"as","label":"GET /authorize?request_uri","note":"Front channel. Apigee resolves the request_uri, authenticates the PSU and shows consent."},
  {"from":"as","to":"tpp","label":"code (+ id_token: c_hash/s_hash)","kind":"return","note":"Authorization code issued; the id_token's c_hash/s_hash protect the response integrity (JARM-style)."},
  {"from":"tpp","to":"as","label":"POST /token (mTLS, code, verifier)","note":"Redeem the code. Apigee stamps cnf.x5t#S256 = the TPP's mTLS cert thumbprint into the token."},
  {"from":"as","to":"tpp","label":"certificate-bound access_token","kind":"return","note":"The token is now sender-constrained to that exact client certificate."},
  {"from":"tpp","to":"rs","label":"GET /accounts (mTLS, Bearer)","note":"The TPP calls the resource presenting the same client certificate."},
  {"from":"rs","to":"rs","label":"token valid AND cnf == cert?","note":"VerifyAccessToken plus a thumbprint match. If the presenting cert differs from cnf, the call is rejected 401."},
  {"from":"rs","to":"tpp","label":"200 data","kind":"return","note":"Everything checks out → data returns. A stolen token alone is useless without the private key."}
]}
```

## 1 — PAR endpoint

The TPP pushes its request object up front. Verify both the client and the request object, then mint a one-time `request_uri` stored in cache.

```xml
<Flow name="PAR">
  <Condition>(proxy.pathsuffix = "/par") and (request.verb = "POST")</Condition>
  <Request>
    <Step><Name>JWT-VerifyClientAssertion</Name></Step>   <!-- private_key_jwt, Day 18 -->
    <Step><Name>JWT-VerifyRequestObject</Name></Step>      <!-- PS256 request object, Day 15 -->
    <Step><Name>JS-MintRequestUri</Name></Step>            <!-- urn:...:<uuid> -->
    <Step><Name>PC-RequestObject</Name></Step>             <!-- PopulateCache, 60s TTL -->
    <Step><Name>AM-ParResponse</Name></Step>               <!-- {"request_uri":..,"expires_in":60} -->
  </Request>
</Flow>
```

```javascript
// resources/jsc/mintRequestUri.js
var uri = 'urn:ietf:params:oauth:request_uri:' + crypto.createHash('sha256')
  .update(context.getVariable('messageid') + context.getVariable('client.received.start.timestamp'))
  .digest('hex').substring(0, 32);
context.setVariable('par.request_uri', uri);
// stash the verified request object claims for /authorize to read back
context.setVariable('par.claims', context.getVariable('jwt.JWT-VerifyRequestObject.payload-json'));
```

```xml
<PopulateCache name="PC-RequestObject">
  <CacheKey><KeyFragment ref="par.request_uri"/></CacheKey>
  <Source>par.claims</Source>
  <ExpirySettings><TimeoutInSeconds>60</TimeoutInSeconds></ExpirySettings>
</PopulateCache>
```

```xml
<AssignMessage name="AM-ParResponse">
  <Set>
    <StatusCode>201</StatusCode>
    <Payload contentType="application/json">{"request_uri":"{par.request_uri}","expires_in":60}</Payload>
  </Set>
  <AssignTo createNew="false" type="response">response</AssignTo>
</AssignMessage>
```

## 2 — Authorize endpoint (resolve request_uri, enforce nonce/state)

```xml
<Flow name="Authorize">
  <Condition>(proxy.pathsuffix = "/authorize") and (request.verb = "GET")</Condition>
  <Request>
    <Step><Name>LC-RequestObject</Name></Step>             <!-- LookupCache by request_uri -->
    <Step><Name>RF-UnknownRequestUri</Name><Condition>par.claims = null</Condition></Step>
    <!-- authenticate user + render consent here (your login app) -->
    <Step><Name>OA-GenerateAuthCode</Name></Step>          <!-- carries nonce/state, PKCE challenge -->
    <Step><Name>JWT-IdToken</Name></Step>                  <!-- id_token with c_hash + s_hash (JARM-style) -->
  </Request>
</Flow>
```

`c_hash`/`s_hash` are left-half base64url of SHA-256 over the code/state — compute in a JS step and add as claims in `JWT-IdToken`.

## 3 — Token endpoint with a certificate-bound token

Verify client_assertion + PKCE, redeem the code, then **stamp the client cert thumbprint** into the token as `cnf.x5t#S256`.

```xml
<Flow name="Token">
  <Condition>(proxy.pathsuffix = "/token") and (request.verb = "POST")</Condition>
  <Request>
    <Step><Name>JWT-VerifyClientAssertion</Name></Step>
    <Step><Name>JS-VerifyPkce</Name></Step>
    <Step><Name>AM-BindCert</Name></Step>                  <!-- set cnf thumbprint var -->
    <Step><Name>OA-RedeemCode</Name></Step>                <!-- includes the cnf as a custom attribute -->
  </Request>
</Flow>
```

```xml
<AssignMessage name="AM-BindCert">
  <!-- thumbprint of the TPP's mTLS client cert, base64url SHA-256 -->
  <AssignVariable>
    <Name>token.cnf.x5t</Name>
    <Ref>tls.client.certificate.fingerprint</Ref>
  </AssignVariable>
</AssignMessage>
```

Add the binding as a token attribute so it travels with the token (and surfaces on VerifyAccessToken):

```xml
<OAuthV2 name="OA-RedeemCode">
  <Operation>GenerateAccessToken</Operation>
  <ExpiresIn>300000</ExpiresIn>
  <SupportedGrantTypes><GrantType>authorization_code</GrantType></SupportedGrantTypes>
  <GrantType>request.formparam.grant_type</GrantType>
  <Code>request.formparam.code</Code>
  <Attributes>
    <Attribute name="cnf_x5t" ref="token.cnf.x5t" display="false"/>
  </Attributes>
  <GenerateResponse enabled="true"/>
</OAuthV2>
```

## 4 — Enforce the binding on resource calls

On AISP/PISP proxies, after `VerifyAccessToken`, fail if the presenting cert ≠ the bound thumbprint:

```xml
<Step><Name>OA-VerifyToken</Name></Step>
<Step>
  <Name>RF-CertMismatch</Name>
  <Condition>oauthv2accesstoken.OA-VerifyToken.accesstoken.cnf_x5t != tls.client.certificate.fingerprint</Condition>
</Step>
```

> This is the heart of **sender-constrained tokens**: a stolen bearer token is useless without the TPP's private key/cert. Conformance suites test exactly this.

## Capstone — run the FAPI dance

1. Assemble `fapi-as` with the four flows + all referenced policies; deploy.
2. As the "TPP", sign a request object and a `client_assertion` (PS256) with a key whose JWKS you registered, then:

```bash
# (using a helper script that signs JWTs with your TPP key)
# 1) PAR
REQ_URI=$(curl -s --cert tpp.crt --key tpp.key -X POST "https://$RUNTIME_HOST/fapi-as/par" \
  -d "client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer" \
  -d "client_assertion=$CLIENT_ASSERTION" -d "request=$REQUEST_OBJECT" | jq -r .request_uri)

# 2) authorize (browser): /authorize?client_id=$CK&request_uri=$REQ_URI  → capture code
# 3) token (mTLS) → cert-bound access_token
curl -s --cert tpp.crt --key tpp.key -X POST "https://$RUNTIME_HOST/fapi-as/token" \
  -d "grant_type=authorization_code&code=$CODE&code_verifier=$VERIFIER" \
  -d "client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer&client_assertion=$CLIENT_ASSERTION" | jq .
```

3. Prove the binding: call `/accounts` with the token but a **different** client cert → expect `401` from `RF-CertMismatch`.

## Recap — you can now…

- Stand up a **PAR** endpoint validating a **PS256 request object** and **private_key_jwt**.
- Issue **certificate-bound** access tokens and enforce the binding on resources.
- Pass the structural requirements of **FAPI 1.0 Advanced**.

## Check yourself

1. What stops a stolen access token from being replayed by an attacker?
2. Why must the `request_uri` from PAR be short-lived and one-time?
3. Where does `cnf.x5t#S256` come from at issue, and what's it compared against at use?

**Next:** Day 20 — Week 4 opens the domain: the **UK Open Banking landscape, roles, and trust framework** that this FAPI server plugs into.
