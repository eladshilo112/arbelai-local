#!/usr/bin/env python3
"""Check only updater. Without a trusted signature it refuses installation."""
import argparse,json,urllib.parse,urllib.request
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--manifest-url");p.add_argument("--offline",action="store_true");a=p.parse_args();result={"checked":False,"installed":False,"reason":"offline" if a.offline else "no_update_source_configured","signature_required_for_install":True,"automatic_install":False}
    if a.manifest_url and not a.offline:
        parsed=urllib.parse.urlparse(a.manifest_url)
        if parsed.scheme!="https" or parsed.hostname not in {"github.com","api.github.com","raw.githubusercontent.com"}:raise SystemExit("untrusted_update_source")
        with urllib.request.urlopen(urllib.request.Request(a.manifest_url,headers={"User-Agent":"ARBELAI-Updater/1.0"}),timeout=20) as response:manifest=json.loads(response.read(1_000_001).decode())
        result={"checked":True,"installed":False,"available_version":manifest.get("version"),"signature_present":bool(manifest.get("signature")),"reason":"check_only_code_signing_not_configured","automatic_install":False}
    print(json.dumps(result,ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
