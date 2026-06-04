# Day 26 — Environments, env groups, revisions & config

> **Bottom line:** You'll promote a proxy from `test` to `prod` the right way — using **revisions**, **environment-specific config** (KVMs, property sets, TargetServers), and **environment groups** for hostnames — so the *same bundle* runs everywhere with different settings.

> **Builds on Day 2 & 10:** you saw env groups and KVMs created; today you use them as a promotion model.

## Why this matters

In banking you never edit a proxy in production. You promote an **identical artifact** through environments, changing only configuration. If a proxy needs code changes to move from test to prod, your config-vs-code boundary is wrong. Today you fix that boundary.

## The promotion model

```text
ONE proxy bundle (revision N)  ─────────────────────────────────►
   deployed to:   test env            prod env
   reads:         test KVM/propset     prod KVM/propset
   targets:       test TargetServer    prod TargetServer  (same NAME, different host)
   reachable via: test env group       prod env group     (different hostnames)
```

The bundle contains **zero** environment-specific values. Everything that differs lives outside it, keyed by name.

## Environments & environment groups

Add a `test` and `prod` environment, each with its own group + hostname:

```bash
# create environments
apigeecli envs create --name test --org "$ORG" --token "$TOKEN"
apigeecli envs create --name prod --org "$ORG" --token "$TOKEN"

# attach each to a runtime instance (eval has one; prod may have several)
apigeecli instances attachments attach --name "$INSTANCE" --env test --org "$ORG" --token "$TOKEN"
apigeecli instances attachments attach --name "$INSTANCE" --env prod --org "$ORG" --token "$TOKEN"

# environment groups bind hostnames
apigeecli envgroups create --name ob-test --hosts "api-test.demobank.example" --org "$ORG" --token "$TOKEN"
apigeecli envgroups create --name ob-prod --hosts "api.demobank.example" --org "$ORG" --token "$TOKEN"
apigeecli envgroups attach --name ob-test --env test --org "$ORG" --token "$TOKEN"
apigeecli envgroups attach --name ob-prod --env prod --org "$ORG" --token "$TOKEN"
```

> A request reaches an environment because its **`Host` header** matches a hostname on that environment's group. Same proxy, two hostnames, two environments — no bundle change.

## Revisions

Every `apis create bundle` for an existing proxy stores a **new revision**. Deployments target a *revision* per environment, so `test` can run rev 8 while `prod` runs rev 7 — that's your staged rollout.

```bash
# promote the exact revision that passed test into prod
apigeecli apis deploy --name ob-aisp --rev 8 --org "$ORG" --env prod --ovr --wait --token "$TOKEN"

# what's where?
apigeecli apis listdeploy --name ob-aisp --org "$ORG" --token "$TOKEN" | jq '.deployments[] | {env:.environment, rev:.revision}'
```

> **Promotion = redeploying the already-built revision to the next environment.** You do **not** rebuild for prod. Rebuilding risks a different artifact than the one you tested.

## Environment-specific config — three tools

| Tool | Holds | Mutability | Use for |
|------|-------|-----------|---------|
| **TargetServer** | host/port/TLS of a backend | Live edit | Backend endpoints that differ per env |
| **KVM** | key/value pairs (encrypted) | Live edit (runtime) | Config + light secrets, runtime-updatable |
| **Property set** | key/value pairs in the bundle or env | Bundle/deploy-time | Static-ish config you want versioned with intent |

Property sets are read with the `propertyset.<name>.<key>` variable:

```bash
# attach a property set to the prod environment
cat > ob.properties <<'EOF'
consent.maxExpiryDays=90
payments.fundsCheck.enabled=true
core.timeout.ms=4000
EOF
apigeecli env-config propertysets create --name ob --propsetfile ./ob.properties \
  --org "$ORG" --env prod --token "$TOKEN"
```

```xml
<!-- read it in a policy -->
<AssignMessage name="AM-ReadConfig">
  <AssignVariable><Name>cfg.fundsCheck</Name><Ref>propertyset.ob.payments.fundsCheck.enabled</Ref></AssignVariable>
</AssignMessage>
```

## Lab — promote ob-aisp test → prod

1. Create `test` + `prod` environments and groups (above), each with a `core-banking` TargetServer pointing at *different* hosts.
2. Deploy `ob-aisp` rev N to `test`; run the golden journey against the **test hostname**.
3. Promote the **same rev** to `prod`; run against the **prod hostname**. Confirm it hit the prod TargetServer (different backend) with no bundle change.
4. Change a property-set value in prod only (e.g. `core.timeout.ms`) and confirm test is unaffected.

```bash
# prove they're the same artifact, different config
apigeecli apis listdeploy --name ob-aisp --org "$ORG" --token "$TOKEN" \
  | jq '.deployments[] | {env:.environment, rev:.revision}'
# both envs → same rev number == identical bundle
```

## Recap — you can now…

- Promote an **identical revision** across environments instead of editing prod.
- Route environments by **hostname** via environment groups.
- Externalize all env-specific values into **TargetServers, KVMs, and property sets**.

## Check yourself

1. Why is rebuilding a separate bundle for prod a risk?
2. What determines which environment a given request lands in?
3. Where does the backend hostname for `prod` live, if not in the bundle?

**Next:** Day 27 — make promotion automatic and repeatable: **CI/CD and config-as-code** with apigeecli and GitHub Actions.
