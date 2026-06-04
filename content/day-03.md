# Day 3 — Build & deploy your first API proxy

> **Bottom line:** You'll hand-build a reverse-proxy bundle, deploy it to your eval environment, and call it over HTTPS — and you'll be able to name what every file in the bundle does.

> **Builds on Day 2:** uses your `$ORG`, `$ENV`, `$RUNTIME_HOST`, and `$TOKEN`.

## Why this matters

A proxy bundle is just a folder of XML. Once you can read it, the Apigee UI stops being magic — it's an editor over these files. CI/CD (Day 27) ships these folders. So we start from the files, not the UI.

## Anatomy of a proxy bundle

The minimum viable reverse proxy is three files inside an `apiproxy/` directory:

```text
hello-v1/
└── apiproxy/
    ├── hello-v1.xml          # manifest: proxy name + revision
    ├── proxies/
    │   └── default.xml       # ProxyEndpoint: the northbound (client) side
    └── targets/
        └── default.xml       # TargetEndpoint: the southbound (backend) side
```

| File | Object | Responsibility |
|------|--------|----------------|
| `hello-v1.xml` | `APIProxy` | Names the proxy and its revision |
| `proxies/default.xml` | `ProxyEndpoint` | Where clients hit it (`BasePath`), what flows run, and which target to route to |
| `targets/default.xml` | `TargetEndpoint` | The backend URL and its flows |

## Create the bundle

Paste this whole block — it writes all three files:

```bash
mkdir -p hello-v1/apiproxy/proxies hello-v1/apiproxy/targets

cat > hello-v1/apiproxy/hello-v1.xml <<'XML'
<APIProxy revision="1" name="hello-v1">
  <DisplayName>hello-v1</DisplayName>
  <Description>First reverse proxy — fronts the public Apigee mock target.</Description>
</APIProxy>
XML

cat > hello-v1/apiproxy/proxies/default.xml <<'XML'
<ProxyEndpoint name="default">
  <HTTPProxyConnection>
    <!-- Clients call:  https://$RUNTIME_HOST/hello-v1  -->
    <BasePath>/hello-v1</BasePath>
  </HTTPProxyConnection>

  <PreFlow name="PreFlow"><Request/><Response/></PreFlow>
  <Flows/>
  <PostFlow name="PostFlow"><Request/><Response/></PostFlow>

  <RouteRule name="default">
    <TargetEndpoint>default</TargetEndpoint>
  </RouteRule>
</ProxyEndpoint>
XML

cat > hello-v1/apiproxy/targets/default.xml <<'XML'
<TargetEndpoint name="default">
  <PreFlow name="PreFlow"><Request/><Response/></PreFlow>
  <Flows/>
  <PostFlow name="PostFlow"><Request/><Response/></PostFlow>

  <HTTPTargetConnection>
    <!-- Apigee's public mock backend; returns "Hello, Guest!" at / -->
    <URL>https://mocktarget.apigee.com</URL>
  </HTTPTargetConnection>
</TargetEndpoint>
XML

echo "Bundle created:" && find hello-v1 -type f
```

### Read the ProxyEndpoint

- `BasePath` is the path clients use. `/hello-v1` + whatever they append becomes the request.
- `PreFlow` runs **before** any conditional flow; `PostFlow` runs **after**. Empty for now — tomorrow you'll fill them.
- `RouteRule` says "send this request to the `default` TargetEndpoint." A RouteRule with **no** `<TargetEndpoint>` would mean *no backend* (a "no-target" proxy that responds entirely from policies).

### Read the TargetEndpoint

- `URL` is the backend. The part of the request path **after** the BasePath is appended automatically. So `GET /hello-v1/json` → `GET https://mocktarget.apigee.com/json`.

## Deploy it

```bash
source ~/.apigee-training.env   # refresh vars; re-run TOKEN export if needed

# Upload the bundle as revision 1 of an API proxy named "hello-v1"
apigeecli apis create bundle \
  --name hello-v1 \
  --proxy-folder ./hello-v1/apiproxy \
  --org "$ORG" --token "$TOKEN"

# Deploy that revision to your environment and wait for it to go live
apigeecli apis deploy \
  --name hello-v1 --rev 1 \
  --org "$ORG" --env "$ENV" \
  --ovr --wait --token "$TOKEN"
```

> The `--ovr` (override) flag forces the deploy even if another revision is deployed; `--wait` blocks until the runtime reports the deployment ready.

## Call it

```bash
# Root path → mock target returns a greeting
curl -i "https://$RUNTIME_HOST/hello-v1"

# Append a path → proxied through to the backend's /json
curl -s "https://$RUNTIME_HOST/hello-v1/json" | jq .
```

You should see a `200` greeting from the first call and a JSON body from the second. **You just shipped an API.**

## Lab — make it yours

1. Change the `BasePath` to `/echo-v1`, re-create as **revision 2** (`apigeecli apis create bundle` again increments nothing automatically — pass `--name hello-v1` and it stores a new revision), redeploy, and confirm the old path 404s while the new one works.
2. Point the `URL` at `https://mocktarget.apigee.com/user?user=YOURNAME` and observe the response change. (Note how query handling differs from path handling — we fix this properly on Day 7.)
3. Open the same proxy in the **Apigee UI** (Console → Apigee → Proxy development → API proxies → hello-v1 → *Develop* tab) and find the exact XML you just wrote.

## Recap — you can now…

- Author a **3-file reverse proxy bundle** from scratch.
- Explain `BasePath`, `RouteRule`, `TargetEndpoint`, and path pass-through.
- **Deploy and call** a proxy via `apigeecli` + `curl`.

## Check yourself

1. What does a RouteRule with no `<TargetEndpoint>` element produce?
2. A client calls `/hello-v1/ip`. What URL does the backend receive?
3. Which file would you edit to change the **backend hostname**?

**Next:** Day 04 — control *which* logic runs *when* with PreFlow/PostFlow, conditional flows, and multiple RouteRules.
