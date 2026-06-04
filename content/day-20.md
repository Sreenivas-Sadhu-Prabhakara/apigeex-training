# Day 20 — UK Open Banking landscape & trust framework

> **Bottom line:** You'll map the OBIE ecosystem — the **roles**, the **Directory**, and the **eIDAS/OB certificates** — so every API you build in Week 4 has a clear "who is calling, and how do I trust them?" answer.

> **Builds on Day 19:** the FAPI authorization server you built is the *security layer*; this is the *ecosystem* it operates inside.

## Why this matters

Open Banking isn't just APIs — it's a **regulated trust framework**. You can't design the consent or payment APIs without knowing which actor does what, how they're identified, and which certificate proves it. Get the roles wrong and your authorization logic is wrong.

## The actors

| Role | Full name | What they do |
|------|-----------|--------------|
| **ASPSP** | Account Servicing Payment Service Provider | **The bank** — holds accounts, exposes the APIs. *This is you.* |
| **TPP** | Third Party Provider | The fintech calling your APIs. Umbrella term for the three below. |
| **AISP** | Account Information Service Provider | Reads account data (budgeting, aggregation apps) |
| **PISP** | Payment Initiation Service Provider | Initiates payments on the user's behalf |
| **CBPII** | Card-Based Payment Instrument Issuer | Confirms funds availability |
| **PSU** | Payment Service User | The **end customer** whose accounts/consent are involved |

> The **PSU consents**, the **TPP acts**, the **ASPSP (you) enforces**. Memorize that triangle — it's the spine of every flow in Week 4.

## The governing pieces

- **OBIE** (Open Banking Implementation Entity) — defines the **Read/Write API specifications** (Accounts, Payments, Confirmation of Funds, Events), the **security profile** (FAPI), the **operational guidelines**, and the **customer experience guidelines (CEG)**.
- **The OB Directory** — the ecosystem registry. Every participant is enrolled; it issues/anchors certificates and publishes each TPP's **JWKS** and **Software Statement Assertions (SSA)**. Your proxy fetches a TPP's signing keys from here (Day 24).
- **The FCA register / passporting** — establishes that a TPP is *authorized and regulated* to perform AISP/PISP roles.

## The certificates (this trips everyone up)

UK Open Banking uses two certificate types per participant, issued under the OB / eIDAS trust framework:

| Cert | Purpose | Used for |
|------|---------|----------|
| **OBWAC** (or eIDAS **QWAC**) | *Transport* — Web Authentication Certificate | **mTLS** between TPP and ASPSP (Day 16) |
| **OBSEAL** (or eIDAS **QSEAL**) | *Signing* — Seal Certificate | **Message signing** (the `x-jws-signature` JWS) and signing request objects |

```text
TPP presents OBWAC  ──mTLS──►  ASPSP   (transport identity)
TPP signs with OBSEAL ─JWS──►  payload (non-repudiation / integrity)
```

So a single TPP request to you involves **two** certificates: one secures the *pipe* (OBWAC/QWAC), one seals the *message* (OBSEAL/QSEAL). Your proxy validates both.

## The Software Statement Assertion (SSA)

The **SSA** is a signed JWT issued by the Directory describing a TPP's software: its `software_id`, registered `redirect_uris`, roles (AISP/PISP/CBPII), and JWKS URI. During **Dynamic Client Registration** (Day 24) the TPP presents its SSA; you verify the Directory's signature and auto-provision a client from it. The SSA is how onboarding scales to hundreds of TPPs without manual setup.

## The API families you'll build

| OBIE API | Endpoints (v3.1) | Week 4 day |
|----------|------------------|-----------|
| **Account & Transaction** | `/account-access-consents`, `/accounts`, `/balances`, `/transactions` | Days 21–22 |
| **Payment Initiation** | `/domestic-payment-consents`, `/domestic-payments` | Day 23 |
| **Confirmation of Funds** | `/funds-confirmation-consents`, `/funds-confirmations` | (referenced) |
| **Event Notification** | `/event-subscriptions`, callbacks | (referenced) |

All sit under a versioned base path like `/open-banking/v3.1/aisp/...` and `/open-banking/v3.1/pisp/...`.

## Lab — model your ecosystem

1. Draw the trust triangle (PSU ↔ TPP ↔ ASPSP) and annotate **which certificate** secures the TPP→ASPSP edge and **which** seals the payload.
2. For each role (AISP, PISP, CBPII) write the **one** OBIE API family it primarily uses.
3. Sketch the base-path scheme you'll deploy on Apigee:

```text
https://api.demobank.example/open-banking/v3.1/aisp/account-access-consents
https://api.demobank.example/open-banking/v3.1/aisp/accounts
https://api.demobank.example/open-banking/v3.1/pisp/domestic-payment-consents
https://api.demobank.example/open-banking/v3.1/pisp/domestic-payments
```

4. Map the actors onto your Day-13 Apigee objects: a **TPP** = a developer + app; its **roles** = scopes/products; its **OBWAC** = the mTLS client cert; its **OBSEAL** = the JWKS used by VerifyJWT.

## Recap — you can now…

- Name every OBIE **role** and the **PSU–TPP–ASPSP** trust triangle.
- Explain the **Directory**, **SSA**, and the **OBWAC vs OBSEAL** certificate split.
- Map ecosystem actors onto the **Apigee objects** you've already built.

## Check yourself

1. Which certificate secures the mTLS connection, and which signs the message body?
2. Who *consents*, who *acts*, and who *enforces*?
3. What is an SSA, and at which point in onboarding is it used?

**Next:** Day 21 — build the first real OB surface: the **account-access consent** lifecycle.
