"""Attested Notion READY delivery evidence for independent Ops monitoring.

Only called AFTER the producer has confirmed the canonical Notion READY.
The JWT is short-lived and GitHub-issued. Never log it or the request token.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .notion_sync import check_period_ready

AUDIENCE="qjai-ops-delivery-v1"
INGEST_URL="https://ingest.ops.qjai.org/v1/github-events"

def _oidc_token() -> str:
    if (os.getenv("GITHUB_REPOSITORY")!="gamehack/producthunt"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_EVENT_NAME") not in ("schedule","workflow_dispatch")):
        raise RuntimeError("Ops evidence limited to authorized production workflow")
    url=os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL","")
    auth=os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN","")
    target=urlparse(url)
    if (target.scheme!="https" or not target.hostname
        or not target.hostname.endswith(".actions.githubusercontent.com")
        or target.username or target.password or target.fragment or not auth):
        raise RuntimeError("GitHub OIDC environment is missing or invalid")
    separator="&" if target.query else "?"
    request=Request(url+separator+"audience="+AUDIENCE,
        headers={"Authorization":"Bearer "+auth,"Accept":"application/json"},
        method="GET")
    try:
        with urlopen(request,timeout=15) as response:
            data=json.loads(response.read(32769))
    except (HTTPError,URLError,TimeoutError,ValueError):
        raise RuntimeError("GitHub OIDC token request failed") from None
    token=data.get("value") if isinstance(data,dict) else None
    if not isinstance(token,str) or len(token.split("."))!=3 or len(token)>20000:
        raise RuntimeError("GitHub OIDC token missing or invalid")
    return token

def report(date_text:str) -> dict:
    day=date.fromisoformat(date_text)
    if day.isoformat()!=date_text:
        raise ValueError("Invalid canonical Product Hunt date")
    source_key="producthunt:"+date_text
    # The second readback is deliberate. Successful GitHub runner completion
    # alone is not a business milestone; verify Notion's signed canonical page.
    if not check_period_ready(source_key=source_key,unique_prefix=date_text+"｜"):
        raise RuntimeError("READY missing at evidence emission time")
    jwt=_oidc_token()
    body={"job_id":"ph_not_ready","period_key":date_text,
          "stage":"notion_ready_verified","status":"success",
          "occurred_at":int(datetime.now(timezone.utc).timestamp()),
          "metadata":{"source_key":source_key}}
    request=Request(INGEST_URL,method="POST",
        data=json.dumps(body,separators=(",",":"),ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type":"application/json",
                 "Authorization":"Bearer "+jwt,
                 "User-Agent":"QJAI-ProductHunt-Evidence/1.0"})
    try:
        with urlopen(request,timeout=12) as response:
            if response.status!=202:
                raise RuntimeError("Unexpected Ops receipt status")
            result=json.loads(response.read(2048))
    except (HTTPError,URLError,TimeoutError,ValueError):
        raise RuntimeError("Ops evidence acknowledgement not confirmed") from None
    if result.get("accepted") is not True:
        raise RuntimeError("Ops evidence not accepted")
    return {"status":"OPS_NOTION_READY_CONFIRMED","period":date_text,
            "duplicate":bool(result.get("duplicate"))}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(report(args.date),ensure_ascii=False))
    except (RuntimeError,ValueError) as exc:
        parser.exit(2,"Ops READY attestation failed: "+str(exc)+"\n")

if __name__=="__main__":
    main()
