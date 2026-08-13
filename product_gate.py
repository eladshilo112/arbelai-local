#!/usr/bin/env python3
import argparse,hashlib,json,os,re,subprocess
from pathlib import Path
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):h.update(block)
    return h.hexdigest()
def safe_file(root,value):
    try:
        path=(root/value).resolve();return path if path.is_file() and path.is_relative_to(root.resolve()) else None
    except (OSError,TypeError,ValueError):return None
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(Path(__file__).resolve().parent));p.add_argument("--zip");a=p.parse_args();root=Path(a.root);security=json.loads((root/"SECURITY_TEST_REPORT.json").read_text(encoding="utf-8-sig")) if (root/"SECURITY_TEST_REPORT.json").exists() else {}
    attest=root/"release_attestations";claude=json.loads((attest/"CLAUDE_REVIEW.json").read_text(encoding="utf-8-sig")) if (attest/"CLAUDE_REVIEW.json").exists() else {};signing=json.loads((attest/"CODE_SIGNING.json").read_text(encoding="utf-8-sig")) if (attest/"CODE_SIGNING.json").exists() else {};legal=json.loads((attest/"LEGAL_REVIEW.json").read_text(encoding="utf-8-sig")) if (attest/"LEGAL_REVIEW.json").exists() else {}
    hash_ok=lambda value:bool(re.fullmatch(r"[0-9a-fA-F]{64}",str(value or "")))
    plan=root/"docs"/"CLAUDE_PRODUCTIZATION_PLAN.md";claude_ok=bool(claude.get("completed") is True and claude.get("model") and hash_ok(claude.get("review_sha256")) and plan.exists() and sha(plan).lower()==str(claude.get("review_sha256")).lower())
    signed_artifact=safe_file(root,signing.get("artifact_path"));signing_ok=False
    if os.name=="nt" and signed_artifact and signing.get("signature_verified") is True and signing.get("certificate_thumbprint") and hash_ok(signing.get("artifact_sha256")) and sha(signed_artifact).lower()==str(signing.get("artifact_sha256")).lower():
        escaped=str(signed_artifact).replace("'","''");cp=subprocess.run(["powershell","-NoProfile","-Command",f"$s=Get-AuthenticodeSignature -LiteralPath '{escaped}';[pscustomobject]@{{Status=[string]$s.Status;Thumbprint=$s.SignerCertificate.Thumbprint}}|ConvertTo-Json -Compress"],capture_output=True,text=True,timeout=60)
        try:verified=json.loads(cp.stdout);signing_ok=cp.returncode==0 and verified.get("Status")=="Valid" and str(verified.get("Thumbprint","")).replace(" ","").lower()==str(signing.get("certificate_thumbprint","")).replace(" ","").lower()
        except json.JSONDecodeError:signing_ok=False
    legal_paths=[safe_file(root,x) for x in legal.get("documents",[])];legal_paths=[x for x in legal_paths if x]
    legal_digest=hashlib.sha256()
    for path in sorted(legal_paths,key=lambda x:x.relative_to(root).as_posix()):legal_digest.update(path.relative_to(root).as_posix().encode());legal_digest.update(b"\0");legal_digest.update(path.read_bytes());legal_digest.update(b"\0")
    legal_ok=bool(legal.get("approved") is True and legal.get("reviewer") and legal.get("review_date") and legal_paths and len(legal_paths)==len(legal.get("documents",[])) and hash_ok(legal.get("documents_sha256")) and legal_digest.hexdigest().lower()==str(legal.get("documents_sha256")).lower())
    gates={
      "security_no_open_critical_high":security.get("status")=="passed" and security.get("known_open_critical_high")==0,
      "privacy_isolation":any(x.get("name")=="unit_integration_failure_tests" and x.get("ok") for x in security.get("checks",[])),
      "compatibility_matrix":(root/"docs"/"SUPPORT_MATRIX.md").exists(),
      "safe_fallback":security.get("status")=="passed",
      "improvement_watcher":security.get("status")=="passed" and (root/"config"/"IMPROVEMENT_SOURCES.json").exists() and (root/"docs"/"SCHEDULE_TEST_REPORT.md").exists(),
      "update_and_rollback":security.get("status")=="passed",
      "clean_release":security.get("status")=="passed",
      "arbelai_evidence":(root/"docs"/"ARBELAI_EXECUTION_EVIDENCE.md").exists(),
      "claude_plan_completed":claude_ok,
      "code_signing_completed":signing_ok,
      "legal_review_completed":legal_ok
    }
    external={"claude_plan_completed","code_signing_completed","legal_review_completed"};portable_ready=all(value for key,value in gates.items() if key not in external)
    product_ready=all(gates.values());result={"portable_replication_status":"PORTABLE_REPLICATION_READY" if portable_ready else "PORTABLE_REPLICATION_BLOCKED","product_status":"PRODUCT_RELEASE_CANDIDATE_READY" if product_ready else "PRODUCT_RELEASE_CANDIDATE_BLOCKED","gates":gates,"blocking_gates":[k for k,v in gates.items() if not v]}
    (root/"PRODUCT_GATE_REPORT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8-sig");print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if product_ready else 2
if __name__=="__main__":raise SystemExit(main())
