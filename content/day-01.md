# Day 1 — Apigee X: the platform & architecture

> **Bottom line:** Apigee X is a fully-managed API management platform that runs on Google Cloud. By the end of today you can draw the request path from a caller to your backend and name every object it passes through.

## Why this matters

For the next 29 days you will create *proxies*, attach *policies*, and deploy to *environments*. None of that makes sense until you can place each object in the architecture. Banking teams especially need this mental model, because the security boundary (where TLS terminates, where tokens are checked) maps directly onto these components.

## The two planes

Apigee X cleanly separates **management** from **traffic**:

| Plane | What lives here | Who touches it |
|-------|-----------------|----------------|
| **Control plane** | Where you design proxies, define products, configure environments. Google-managed, multi-tenant. Reached via the Apigee UI and the Apigee API. | Developers, operators, CI/CD |
| **Runtime plane** | The *instances* that actually process API calls in a GCP region. Single-tenant, in your project's network. | End-user / app traffic |

You **deploy** an artifact in the control plane; it is **distributed** to the runtime plane and executed there. This is why a deploy is not instant and why "deployed" and "saved" are different states.

## The data model (memorize this hierarchy)

```text
GCP Project (1:1)
└── Organization (your Apigee "org")
    ├── Environments        e.g. eval, test, prod
    │   └── deployed API proxy revisions
    ├── Environment Groups  e.g. ob-uk-group  → hostnames (api.bank.example)
    ├── Instances           regional runtime (europe-west2, ...)
    ├── API Products        bundles of proxy operations sold/granted as a unit
    ├── Developers & Apps   identities that get credentials
    └── Shared Flows / KVMs / Keystores / TargetServers (shared config)
```

Key facts that trip people up:

- An **organization is bound 1:1 to a GCP project** and is named after it. You do not "create many orgs" casually.
- A proxy is **deployed to an environment**, not to the org. The same proxy can run in `test` and `prod` with different config.
- **Environment groups** attach **hostnames**. A request reaches an environment because its `Host` header matches a hostname routed to a group that contains that environment.
- **Instances** are the regional runtimes. For UK Open Banking you'll typically pick `europe-west2` (London) for data residency.

## How a request flows

```text
Client app
  │  HTTPS  (northbound TLS)
  ▼
Google Front End / Load Balancer  ── matches Host header → Environment Group
  ▼
Apigee runtime instance (region)
  ▼  ProxyEndpoint  → policies (request flow)
  ▼  TargetEndpoint → policies → backend call (southbound TLS)
  ▼
Backend / system of record (core banking, ledger, ...)
  ▲  response flows run on the way back
```

Two terms you'll hear constantly:

- **Northbound** = the client-facing edge (app → Apigee).
- **Southbound** = the backend-facing edge (Apigee → your service).

In Open Banking, the *northbound* edge is where FAPI and mutual TLS live; the *southbound* edge is where you authenticate to the core banking system.

## Apigee X vs Edge vs hybrid (one paragraph)

You may meet three flavors. **Apigee Edge** is the older generation (often SaaS, "classic"). **Apigee X** is the current Google-Cloud-native managed product — *this course targets X*. **Apigee hybrid** runs the same runtime in your own Kubernetes (GKE/anywhere) for data-sovereignty cases, with the control plane still in Google Cloud. The proxy and policy concepts you learn here apply to all three; only provisioning and networking differ.

## Lab — map it yourself

You don't have an org yet (that's Day 2), but you can still anchor the model:

1. On paper or in a comment block, draw the flow from **a TPP's mobile app** → **your bank's `/accounts` API** → **core banking**. Label where northbound TLS terminates and where you'd check an access token.
2. Decide, for a UK bank, which **region** your instance should live in and **why** (hint: data residency + latency to London).
3. List which objects are **shared across environments** (proxies as artifacts, shared flows) versus **per-environment** (deployments, KVM *values*, hostnames).

```text
# Sample answer to step 3
Shared artifact (one definition):      proxy bundle, shared flow, API product
Per-environment (differs test/prod):   which revision is deployed,
                                        KVM/property-set values, target URLs,
                                        hostnames via environment groups
```

## Recap — you can now…

- Name the **control plane** vs **runtime plane** and why deploys aren't instant.
- Place **org → environment → env group → instance** in a hierarchy.
- Explain **northbound vs southbound** and where security boundaries fall.

## Check yourself

1. A request returns `404` with no matching proxy. Which object's misconfiguration most likely caused it — the proxy, or the **environment group hostname**?
2. True/false: deploying a proxy to `prod` automatically deploys it to `test`.
3. Where does **mutual TLS** for a TPP terminate — northbound or southbound?

**Next:** Day 02 — we stop drawing and actually provision a working Apigee X org plus the CLI tools you'll use for the rest of the course.
