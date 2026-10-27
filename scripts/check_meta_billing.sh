#!/usr/bin/env bash
# Checks whether the Meta Model API key can actually make a billed call yet.
# Exits 0 and prints READY when a chat completion succeeds; otherwise prints the blocker.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json, urllib.request, urllib.error
d=json.load(open('/home/ubuntu/.config/abacusai_auth_secrets.json'))
key=None
for k,v in d.items():
    if 'meta' in k.lower():
        s=v.get('secrets',v)
        for kk,vv in s.items():
            key=vv.get('value') if isinstance(vv,dict) else vv; break
        break
base="https://api.meta.ai/v1"
body=json.dumps({"model":"muse-spark-1.3","messages":[{"role":"user","content":"OK"}]}).encode()
req=urllib.request.Request(base+"/chat/completions",data=body,
    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","User-Agent":"navigator/1.0"})
try:
    with urllib.request.urlopen(req,timeout=40) as r:
        j=json.loads(r.read().decode())
        print("READY -", j["choices"][0]["message"]["content"][:60])
except urllib.error.HTTPError as e:
    msg=e.read().decode(errors='replace')
    print(f"NOT READY - HTTP {e.code}: {msg[:300]}")
PY
