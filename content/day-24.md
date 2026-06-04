# Day 24 — Dynamic Client Registration, SSA & cert-bound tokens

> **Bottom line:** You'll auto-onboard TPPs with **Dynamic Client Registration (DCR)** — verify a Directory-signed **SSA**, create an Apigee developer app from it, fetch the TPP's **JWKS**, and finish wiring **certificate-bound tokens**.

> **Builds on Days 16, 19, 20:** SSA verification uses VerifyJWT; app creation uses the Day-13 model; cert-binding completes the Day-19 token work.

## Why this matters

A bank may onboard hundreds of TPPs. Manual app creation doesn't scale and isn't compliant. **DCR** lets a TPP register itself by presenting a Directory-issued Software Statement — your proxy validates it and provisions the OAuth client automatically. This is the onboarding backbone of the whole ecosystem.

## The DCR flow (`POST /register`)

```text
TPP → POST /register   (mTLS with OBWAC; body = a signed registration request JWT
                        that embeds the Directory-issued SSA)
ASPSP:
  1. Verify the registration JWT signature (TPP OBSEAL key from the SSA's JWKS)
  2. Verify the SSA signature against the OB Directory's JWKS  ← trust anchor
  3. Extract software_id, redirect_uris, roles, jwks_uri, org_id from the SSA
  4. Create an Apigee developer + app; assign products matching the TPP's roles
  5. Return the client_id (+ registration response)
```

```widget
{"type":"sequence","title":"Dynamic Client Registration, step by step","actors":[
  {"id":"tpp","label":"TPP"},
  {"id":"as","label":"Apigee /register"},
  {"id":"dir","label":"OB Directory"}
],"steps":[
  {"from":"tpp","to":"as","label":"POST /register (mTLS OBWAC)","note":"The TPP submits a signed registration request JWT that embeds the Directory-issued Software Statement (SSA)."},
  {"from":"as","to":"as","label":"verify registration JWT (TPP OBSEAL)","note":"Confirms the registration request is signed by the TPP's own key."},
  {"from":"as","to":"dir","label":"fetch Directory JWKS","note":"Apigee retrieves the OB Directory's public keys — the trust anchor for the whole ecosystem."},
  {"from":"dir","to":"as","label":"JWKS","kind":"return","note":"Cached aggressively; these keys change rarely."},
  {"from":"as","to":"as","label":"verify SSA vs Directory JWKS","note":"If the SSA signature verifies, the Directory issued it — so its claims (software_id, redirect_uris, roles, jwks_uri) can be trusted."},
  {"from":"as","to":"as","label":"create developer + app","note":"Provision an Apigee app from the SSA; map SSA roles (AISP/PISP) to API products; store jwks_uri + cert thumbprint as attributes."},
  {"from":"as","to":"tpp","label":"client_id (+ registration response)","kind":"return","note":"The TPP now has an OAuth client and can run the FAPI token flow — no manual onboarding."}
]}
```

## 1 — Verify the registration request and the SSA

```xml
<Flow name="Register">
  <Condition>(proxy.pathsuffix = "/register") and (request.verb = "POST")</Condition>
  <Request>
    <Step><Name>DecodeJWT-Registration</Name></Step>       <!-- read the embedded software_statement -->
    <Step><Name>JWT-VerifySSA</Name></Step>                <!-- against OB Directory JWKS (trust anchor) -->
    <Step><Name>EV-SSAClaims</Name></Step>                 <!-- software_id, redirect_uris, roles, jwks_uri -->
    <Step><Name>JWT-VerifyRegRequest</Name></Step>         <!-- registration JWT signed by TPP OBSEAL -->
    <Step><Name>JS-ValidateRedirectUris</Name></Step>      <!-- reg redirect_uris ⊆ SSA redirect_uris -->
    <Step><Name>SC-CreateDeveloperApp</Name></Step>        <!-- provision in Apigee via mgmt API -->
    <Step><Name>AM-RegistrationResponse</Name></Step>
  </Request>
</Flow>
```

```xml
<!-- verify the SSA against the Directory's published keys -->
<VerifyJWT name="JWT-VerifySSA">
  <Algorithm>PS256</Algorithm>
  <Source>ssa.jwt</Source>
  <PublicKey>
    <JWKS uri="https://keystore.openbankingtest.org.uk/keystore/openbanking.jwks"/>
  </PublicKey>
  <Issuer>OpenBanking Ltd</Issuer>
</VerifyJWT>
```

> The Directory's JWKS is the **trust anchor**. If the SSA's signature verifies against it, you *know* the Directory issued it — that's what lets you trust the embedded claims without a manual check.

## 2 — Provision the Apigee app from SSA claims

Use a ServiceCallout to the Apigee management API (or apigeecli in a batch job) to create the developer + app, mapping SSA `roles` → API products:

```xml
<AssignMessage name="AM-CreateAppRequest">
  <AssignTo createNew="true" type="request">createAppReq</AssignTo>
  <Set>
    <Verb>POST</Verb>
    <Path>/v1/organizations/{org}/developers/{ssa.org_id}@tpp.example/apps</Path>
    <Headers><Header name="Authorization">Bearer {mgmt.token}</Header></Headers>
    <Payload contentType="application/json">
{
  "name": "{ssa.software_id}",
  "apiProducts": ["aisp-read","pisp-write"],
  "attributes": [
    {"name":"software_id","value":"{ssa.software_id}"},
    {"name":"jwks_uri","value":"{ssa.jwks_uri}"},
    {"name":"redirect_uris","value":"{ssa.redirect_uris}"},
    {"name":"org_id","value":"{ssa.org_id}"}
  ]
}
    </Payload>
  </Set>
</AssignMessage>
```

The returned `consumerKey` becomes the TPP's `client_id`, returned in the registration response.

## 3 — Resolve the TPP's JWKS at runtime

You stored `jwks_uri` as an app attribute. On token/PAR flows you fetch it (cached) to verify the TPP's signatures — this is the `tpp.jwks` your Day-15/18/19 VerifyJWT policies referenced:

```xml
<ServiceCallout name="SC-FetchTppJwks">
  <Request variable="jwksReq"/>
  <Response>jwksResp</Response>
  <HTTPTargetConnection><URL>{app.jwks_uri}</URL></HTTPTargetConnection>
</ServiceCallout>
<!-- cache aggressively: JWKS rarely change -->
```

Wrap it in LookupCache/PopulateCache (Day 10) keyed by `client_id` so you fetch each TPP's keys at most once per TTL.

## 4 — Finish certificate-bound tokens

You stamped `cnf.x5t#S256` at issue (Day 19). DCR adds the missing half: bind the registration to the **OBWAC** presented at `/register`, and ensure the cert used at the token endpoint belongs to the same registered TPP. Store the OBWAC subject/thumbprint as an app attribute and assert it:

```xml
<Step>
  <Name>RF-CertNotRegistered</Name>
  <Condition>tls.client.certificate.fingerprint != app.registered_cert_thumbprint</Condition>
</Step>
```

Now the chain is complete: **registered cert → issues cert-bound token → token only usable from that cert.**

## Lab — onboard a TPP end to end

1. Build the `dcr` proxy `/register` flow with SSA verification (use the OB **sandbox** Directory JWKS).
2. Obtain a sandbox SSA (or a self-signed test SSA signed by a key you treat as the Directory), POST a registration JWT, and confirm an Apigee app is created:

```bash
curl -s -X POST "https://$RUNTIME_HOST/open-banking/v3.1/register" \
  --cert tpp-obwac.crt --key tpp-obwac.key \
  -H "Content-Type: application/jwt" \
  --data "$REGISTRATION_JWT" | jq .
# → { "client_id":"...", "software_id":"...", "redirect_uris":[...], ... }

# confirm the app exists in Apigee
apigeecli apps get --name "$SOFTWARE_ID" --org "$ORG" --token "$TOKEN" | jq '.credentials[0].consumerKey'
```

3. Use the new `client_id` to run the Day-19 FAPI token flow and confirm the issued token is cert-bound to the OBWAC you registered with.

## Recap — you can now…

- Implement **DCR**: verify a Directory-signed **SSA** and provision an Apigee app from it.
- Resolve and cache a TPP's **JWKS** for signature verification.
- Complete **certificate-bound tokens**: registered cert → bound token → cert-checked resource calls.

## Check yourself

1. What is the **trust anchor** that lets you accept an SSA's embedded claims?
2. How do SSA `roles` map onto Apigee objects?
3. Which two certificates does a single onboarded TPP use, and for what?

**Next:** Day 25 — Week 4 capstone: assemble **consent + AISP + PISP + DCR** into one coherent Open Banking surface.
