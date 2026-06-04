# Day 2 — Provision Apigee X & your toolchain

> **Bottom line:** Today you stand up a real, free **Apigee X evaluation org** in your own GCP project and install every CLI you'll use for the next 28 days. From tomorrow on, every lab deploys to *your* org.

> **Builds on Day 1:** you'll create the exact objects you mapped yesterday — an organization, an environment, an environment group, and a runtime instance.

## Why this matters

You cannot learn proxy development by reading. The eval org gives you a 60-day, no-cost runtime to deploy against. Getting the toolchain right once saves you from environment friction every single day after.

## Step 0 — Prerequisites

- A Google Cloud account with **billing enabled** (eval runtime is free, but the project must have a billing account attached).
- Owner/Editor on a project you can use, or permission to create one.

```bash
# Authenticate and pick (or create) a project
gcloud auth login
export PROJECT_ID="my-apigee-training"      # change me
gcloud projects create "$PROJECT_ID" --set-as-default   # skip if it exists
gcloud config set project "$PROJECT_ID"

# Make sure billing is linked (replace with your billing account id)
gcloud billing accounts list
gcloud billing projects link "$PROJECT_ID" --billing-account=XXXXXX-XXXXXX-XXXXXX
```

## Step 1 — Enable the APIs

```bash
gcloud services enable \
  apigee.googleapis.com \
  compute.googleapis.com \
  servicenetworking.googleapis.com \
  cloudkms.googleapis.com \
  --project "$PROJECT_ID"
```

## Step 2 — Provision the eval organization

The fastest path is the **Apigee provisioning wizard** in the Cloud Console, which sets up networking for you.

> **Console route (recommended for Day 2):** Console → **Apigee** → **Set up Apigee** → choose **Evaluation** → pick a region (UK Open Banking → **europe-west2**, London) → let it create the org + environment + environment group + instance. Takes ~25–45 minutes to become ready.

If you prefer the CLI, the eval org is a multi-step gcloud sequence (org → instance → environment → env group → attachment). The console wizard does all of it; come back to the CLI version on Day 26 when we automate environments. For reference, the org-create call looks like:

```bash
# CLI equivalent of the wizard's first step (the wizard also does the rest)
gcloud alpha apigee organizations provision \
  --runtime-location=europe-west2 \
  --analytics-region=europe-west2 \
  --project="$PROJECT_ID"
```

> **Open Banking note:** choose **europe-west2 (London)** for UK data residency and low latency to UK rails. You can run multi-region later (Day 30); a single region is right for learning.

## Step 3 — Confirm the org is alive

```bash
export ORG="$PROJECT_ID"          # eval org name == project id
export ENV="eval"                 # the wizard's default environment is usually 'eval'

# List environments in your org
gcloud apigee environments list --organization="$ORG"

# Show the environment groups and their hostnames
gcloud apigee envgroups list --organization="$ORG"
```

You should see at least one environment and one environment group with a `*.nip.io`-style eval hostname (or a hostname you chose).

## Step 4 — Install the toolchain

`apigeecli` is the community-standard CLI for managing proxies, products, KVMs, and deployments. You'll use it daily.

```bash
# apigeecli (installs to ~/.apigeecli/bin)
curl -L https://raw.githubusercontent.com/apigee/apigeecli/main/downloadLatest.sh | sh -
export PATH="$PATH:$HOME/.apigeecli/bin"
apigeecli -v

# A throwaway access token you can reuse in commands today
export TOKEN=$(gcloud auth print-access-token)
```

Confirm `apigeecli` can see your org:

```bash
apigeecli organizations get --org "$ORG" --token "$TOKEN"
```

Also confirm you have the other tools the course uses:

```bash
gcloud --version      # Google Cloud CLI
curl --version        # HTTP client for testing
jq --version          # JSON pretty-printing (brew install jq if missing)
openssl version       # for keys/certs in the security weeks
```

## Step 5 — Save your environment variables

You'll reuse these constantly. Drop them in a file you can `source`:

```bash
cat > ~/.apigee-training.env <<'EOF'
export PROJECT_ID="my-apigee-training"
export ORG="$PROJECT_ID"
export ENV="eval"
export RUNTIME_HOST="<your-env-group-hostname>"   # from: gcloud apigee envgroups
export TOKEN=$(gcloud auth print-access-token)
EOF
echo "source ~/.apigee-training.env" >> ~/.zshrc
source ~/.apigee-training.env
```

> **⚠ Warning:** `gcloud auth print-access-token` produces a **short-lived** token (≈1 hour). Re-run `export TOKEN=$(gcloud auth print-access-token)` whenever a command returns `401`.

## Lab — prove the loop works

Deploy the sample "hello world" proxy that ships with Apigee, just to confirm the full create→deploy→call loop before you build your own tomorrow:

```bash
# Apigee ships a sample; if your org doesn't have it, this is fine —
# tomorrow you build one from scratch. For now just confirm listing works:
apigeecli apis list --org "$ORG" --token "$TOKEN"
apigeecli envs list --org "$ORG" --token "$TOKEN"
```

If both commands return JSON without error, your control-plane access is good.

## Recap — you can now…

- Provision a **free eval Apigee X org** in the right region for UK Open Banking.
- Confirm your **environment** and **environment group hostname**.
- Run `apigeecli` and `gcloud` against your org with a bearer token.

## Check yourself

1. Why did we pick `europe-west2`?
2. What's the difference between the **org name** and the **environment name** in an eval setup?
3. Your `apigeecli` call returns `401`. What's the first thing to refresh?

**Next:** Day 03 — build and deploy your *first* API proxy from an empty bundle, and read every file inside it.
