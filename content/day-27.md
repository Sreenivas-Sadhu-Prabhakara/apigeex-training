# Day 27 — CI/CD & config-as-code with apigeecli

> **Bottom line:** You'll put your proxy bundles in Git and build a **GitHub Actions pipeline** that lints, deploys to `test`, runs API tests, and promotes the same revision to `prod` — config-as-code, no clicking.

> **Builds on Day 26:** automation just scripts the promotion model you did by hand yesterday.

## Why this matters

Banks need auditable, repeatable, four-eyes deployments. A proxy that's edited in the UI has no review, no history, no rollback. Config-as-code makes every change a reviewed PR and every deploy a logged pipeline run — table stakes for a regulated environment.

## Repository layout

Treat proxies, shared flows, and environment config as source:

```text
repo/
├── apiproxies/
│   ├── ob-aisp/apiproxy/...
│   └── ob-pisp/apiproxy/...
├── sharedflows/
│   └── sf-fapi-inbound/sharedflowbundle/...
├── config/
│   ├── test/{kvms.json,targetservers.json,products.json}
│   └── prod/{kvms.json,targetservers.json,products.json}
├── tests/
│   └── ob-aisp.apickli.feature        # or postman/newman collection
└── .github/workflows/deploy.yml
```

> **Config is environment-scoped JSON in Git** — the *values* differ per env, the *structure* is reviewed. apigeecli can apply these declaratively, so a backend host change is a PR, not a console edit.

## Authenticate the pipeline (Workload Identity Federation)

Don't put a service-account key in GitHub. Use **Workload Identity Federation** so the Actions runner exchanges its OIDC token for short-lived GCP creds:

```yaml
# .github/workflows/deploy.yml (excerpt) — keyless auth
permissions:
  contents: read
  id-token: write          # required for OIDC → GCP

steps:
  - uses: actions/checkout@v4
  - id: auth
    uses: google-github-actions/auth@v2
    with:
      workload_identity_provider: projects/123/locations/global/workloadIdentityPools/gh/providers/gh
      service_account: apigee-deployer@${{ env.PROJECT_ID }}.iam.gserviceaccount.com
  - uses: google-github-actions/setup-gcloud@v2
```

## The pipeline

```yaml
name: deploy-apigee
on:
  pull_request: { branches: [main] }     # validate on PR
  push: { branches: [main] }             # deploy on merge

env:
  ORG: my-apigee-training
  PROJECT_ID: my-apigee-training

jobs:
  build-test-deploy:
    runs-on: ubuntu-latest
    permissions: { contents: read, id-token: write }
    steps:
      - uses: actions/checkout@v4
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SA }}
      - uses: google-github-actions/setup-gcloud@v2

      - name: Install apigeecli
        run: |
          curl -L https://raw.githubusercontent.com/apigee/apigeecli/main/downloadLatest.sh | sh -
          echo "$HOME/.apigeecli/bin" >> "$GITHUB_PATH"

      - name: Token
        run: echo "TOKEN=$(gcloud auth print-access-token)" >> "$GITHUB_ENV"

      # 1) Lint / static checks (apigeelint catches anti-patterns)
      - name: Lint proxies
        run: |
          npm i -g apigeelint
          apigeelint -s apiproxies/ob-aisp/apiproxy -f table

      # 2) Deploy the bundle to TEST as a new revision
      - name: Deploy to test
        run: |
          apigeecli apis create bundle --name ob-aisp \
            --proxy-folder apiproxies/ob-aisp/apiproxy --org "$ORG" --token "$TOKEN"
          REV=$(apigeecli apis deploy --name ob-aisp --org "$ORG" --env test \
            --ovr --wait --token "$TOKEN" | jq -r '.revision')
          echo "REV=$REV" >> "$GITHUB_ENV"

      # 3) Integration tests against the test hostname
      - name: API tests
        run: |
          npm i -g newman
          newman run tests/ob-aisp.postman_collection.json \
            --env-var "baseUrl=https://api-test.demobank.example"

      # 4) Promote the SAME revision to PROD (only on main, gated by environment approval)
      - name: Promote to prod
        if: github.ref == 'refs/heads/main'
        run: |
          apigeecli apis deploy --name ob-aisp --rev "$REV" \
            --org "$ORG" --env prod --ovr --wait --token "$TOKEN"
```

> Use a GitHub **Environment** named `prod` with required reviewers to enforce **four-eyes approval** before the promote step runs. That's your change-control gate.

## API tests (apickli / newman)

A minimal contract test for the AISP consent guard, in apickli (Cucumber) style:

```gherkin
Feature: AISP consent enforcement
  Scenario: reject data access without an Authorised consent
    Given I set Authorization header to Bearer <unauthorised-token>
    And I set x-fapi-interaction-id header to a-uuid
    When I GET /open-banking/v3.1/aisp/accounts
    Then response code should be 403
    And response body path $.Errors[0].ErrorCode should be UK.OBIE.Resource.InvalidConsentStatus
```

## Config-as-code apply

Sync environment config declaratively so config drift is impossible:

```bash
# apply per-environment KVMs/targetservers/products from versioned JSON
apigeecli kvms import --org "$ORG" --env test -f config/test/kvms.json --token "$TOKEN"
apigeecli targetservers import --org "$ORG" --env test -f config/test/targetservers.json --token "$TOKEN"
apigeecli products import --org "$ORG" -f config/products.json --token "$TOKEN"
```

## Lab — pipeline your AISP proxy

1. Put `ob-aisp` and its tests in a repo; add the workflow.
2. Open a PR → confirm lint + test run but **no** prod deploy.
3. Merge → confirm deploy-to-test, tests, then a **gated** promote-to-prod requiring approval.
4. Break a test on purpose (e.g. expect `200` where consent should give `403`) and confirm the pipeline **blocks** promotion.

## Recap — you can now…

- Store proxies, shared flows, and env config as **versioned source**.
- Build a **GitHub Actions** pipeline: lint → deploy-test → test → gated promote-prod.
- Authenticate keylessly with **Workload Identity Federation** and enforce **four-eyes** approval.

## Check yourself

1. Why promote the *same revision* rather than re-running `create bundle` for prod?
2. What does Workload Identity Federation remove from your CI secrets?
3. Where do you enforce a human approval before production deploys?

**Next:** Day 28 — see what your live APIs are doing: **analytics, Cloud Logging, distributed tracing, and Debug sessions**.
