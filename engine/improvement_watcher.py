#!/usr/bin/env python3
"""ARBELAI Improvement Watcher: official metadata, gated canary and atomic promotion."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,os,re,shutil,ssl,sys,tempfile,time,urllib.error,urllib.parse,urllib.request,zipfile
from pathlib import Path

UTC=dt.timezone.utc
STATES={"discovered","rejected","awaiting_user_approval","canary_downloaded","security_passed","benchmark_passed","promoted","rolled_back","revoked"}
ALLOWED_TRANSITIONS={
 "discovered":{"rejected","awaiting_user_approval","revoked"},"awaiting_user_approval":{"rejected","canary_downloaded","revoked"},
 "canary_downloaded":{"security_passed","rejected","revoked"},"security_passed":{"benchmark_passed","rejected","revoked"},
 "benchmark_passed":{"promoted","rejected","revoked"},"promoted":{"rolled_back","revoked"},"rolled_back":{"awaiting_user_approval","revoked"},
 "rejected":{"awaiting_user_approval","revoked"},"revoked":set()
}

def now():return dt.datetime.now(UTC).isoformat()
def read(path,default=None):return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else ({} if default is None else default)
def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8-sig");os.replace(tmp,path)
def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()
def version_key(value):return tuple(int(x) for x in re.findall(r"\d+",str(value))[:4]) or (0,)
def candidate_key(source_id,version,artifact="metadata"):return hashlib.sha256(f"{source_id}|{version}|{artifact}".encode()).hexdigest()[:20]
def host_allowed(url,registry):
    parsed=urllib.parse.urlparse(url);host=parsed.hostname or "";return parsed.scheme=="https" and not parsed.username and not parsed.password and (host in registry["allowed_hosts"] or host.endswith(".cdn.hf.co"))
def safe_extract(archive,destination):
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        items=z.infolist()
        if len(items)>10000:raise RuntimeError("archive_entry_limit")
        total=sum(item.file_size for item in items)
        if total>20*1024**3:raise RuntimeError("archive_uncompressed_size_limit")
        for item in items:
            mode=(item.external_attr>>16)&0o170000
            if mode==0o120000:raise RuntimeError("archive_symlink_rejected")
            target=(destination/item.filename).resolve()
            if not target.is_relative_to(destination):raise RuntimeError("malicious_archive_path")
        z.extractall(destination)

class Watcher:
    def __init__(self,root,offline=False,opener=None,sleep=time.sleep,session_opt_in=False):
        self.root=Path(root).resolve();self.offline=offline;self.opener=opener or urllib.request.urlopen;self.sleep=sleep
        self.config=read(self.root/"config"/"IMPROVEMENT_WATCHER.json");self.sources=read(self.root/"config"/"IMPROVEMENT_SOURCES.json");self.revocations=read(self.root/"config"/"REVOCATIONS.json",{"revoked":[]});self.cve=read(self.root/"config"/"CVE_POLICY.json")
        self.session_opt_in=session_opt_in
        self.state_path=self.root/"data"/"improvement_candidates.json";self.state=read(self.state_path,{"version":1,"candidates":{},"last_scan":None,"last_known_good":None,"production":None})
    def request(self,url,method="GET",payload=None,timeout=20,retries=3):
        if not host_allowed(url,self.sources):raise RuntimeError("source_not_allowed")
        body=json.dumps(payload).encode() if payload is not None else None;last=None
        for attempt in range(retries):
            try:
                req=urllib.request.Request(url,data=body,method=method,headers={"User-Agent":"ARBELAI-Watcher/1.0","Accept":"application/json","Content-Type":"application/json"})
                with self.opener(req,timeout=timeout,context=ssl.create_default_context()) as response:
                    length=int(response.headers.get("Content-Length") or 0)
                    if length>5_000_000:raise RuntimeError("metadata_too_large")
                    raw=response.read(5_000_001)
                    if len(raw)>5_000_000:raise RuntimeError("metadata_too_large")
                    return json.loads(raw.decode())
            except urllib.error.HTTPError as exc:
                last=exc
                if exc.code!=429:break
                self.sleep(min(2**attempt,4))
            except (TimeoutError,urllib.error.URLError) as exc:last=exc;self.sleep(min(2**attempt,4))
        raise RuntimeError(f"metadata_source_failure:{last}")
    def memory_fit(self,estimated_bytes):
        hw=read(self.root/"config"/"MACHINE_PROFILE.json");work=read(self.root/"config"/"WORKLOAD_PROFILE.json",{})
        ram=int(hw.get("ram",{}).get("total_bytes") or 0);free=int(hw.get("storage",{}).get("free_bytes") or 0);headroom=max(int(ram*.25),4*1024**3) if ram else 0;usable=max(0,ram-headroom);disk_need=int(estimated_bytes*1.2)+2*1024**3
        return {"total_ram_bytes":ram,"system_headroom_bytes":headroom,"usable_ram_bytes":usable,"estimated_candidate_bytes":estimated_bytes,"free_disk_bytes":free,"required_disk_bytes":disk_need,"fit":bool(ram and free and estimated_bytes<=usable and disk_need<=free),"workload_priorities":work.get("priorities",[])}
    def license_gate(self,source,license_value):
        configured=source.get("license_allowlist");allowed={str(x).lower() for x in configured} if configured else {"mit","apache-2.0","apache 2.0","bsd-3-clause"};value=str(license_value or source.get("license") or "unknown").lower();known=value not in {"","unknown","none"};return {"status":"passed" if known and value in allowed else ("unknown" if not known else "blocked"),"license":license_value or source.get("license"),"allowlist":sorted(allowed),"promotion_allowed":known and value in allowed}
    def cve_gate(self,source,version):
        ecosystem=self.cve.get("ecosystem_mapping",{}).get(source["id"])
        if not ecosystem:return {"status":"unknown","promotion_allowed":False,"reason":"no_reliable_cve_mapping"}
        if self.offline:return {"status":"unknown","promotion_allowed":False,"reason":"offline"}
        try:data=self.request(self.cve["endpoint"],"POST",{"package":{"name":source["id"],"ecosystem":ecosystem},"version":str(version)})
        except Exception as exc:return {"status":"unknown","promotion_allowed":False,"reason":str(exc)}
        blocked=[]
        for vuln in data.get("vulns",[]):
            severity=" ".join(x.get("score","") for x in vuln.get("severity",[])).upper()
            if any(level in severity for level in self.cve.get("blocked_severities",[])):blocked.append(vuln.get("id"))
        return {"status":"blocked" if blocked else "passed","promotion_allowed":not blocked,"blocked_ids":blocked,"vulnerability_count":len(data.get("vulns",[]))}
    def revoked(self,source_id,version):return any(x.get("source_id")==source_id and str(x.get("version"))==str(version) for x in self.revocations.get("revoked",[]))
    def refresh_revocations(self):self.revocations=read(self.root/"config"/"REVOCATIONS.json",{"revoked":[]})
    def enforce_not_revoked(self,candidate):
        self.refresh_revocations()
        if self.revoked(candidate["source"]["source_id"],candidate["source"].get("version")):
            if candidate["state"]!="revoked" and "revoked" in ALLOWED_TRANSITIONS.get(candidate["state"],set()):self.transition(candidate,"revoked","revocation_list_refresh")
            raise RuntimeError("candidate_revoked")
    def normalized_release(self,source,data):
        version=data.get("tag_name") or data.get("name");assets=[]
        for item in data.get("assets",[]):
            digest=item.get("digest");assets.append({"name":item.get("name"),"url":item.get("browser_download_url"),"size":int(item.get("size") or 0),"sha256":digest.split(":",1)[1] if isinstance(digest,str) and digest.startswith("sha256:") else None,"signature":None})
        return {"source_id":source["id"],"kind":source["kind"],"version":version,"date":data.get("published_at"),"license":source.get("license"),"project_url":source.get("project_url"),"os":source.get("os",[]),"architectures":source.get("architectures",[]),"hardware_tags":source.get("hardware_tags",[]),"assets":assets,"runtime_requirements":[],"context_tokens":None,"quantizations":[]}
    def normalized_hf(self,source,repo,data):
        license_value=(data.get("cardData") or {}).get("license");siblings=data.get("siblings") or [];artifacts=[]
        for item in siblings:
            name=item.get("rfilename","")
            if not any(q.lower() in name.lower() for q in source.get("quantizations",[])):continue
            lfs=item.get("lfs") or {};digest=lfs.get("sha256") or lfs.get("oid");size=int(lfs.get("size") or 0);url=f"https://huggingface.co/{repo}/resolve/{data.get('sha') or 'main'}/{urllib.parse.quote(name)}"
            if not digest or not size:
                try:
                    req=urllib.request.Request(url,method="HEAD",headers={"User-Agent":"ARBELAI-Watcher/1.0"})
                    with self.opener(req,timeout=20,context=ssl.create_default_context()) as response:
                        value=(response.headers.get("X-Linked-Etag") or response.headers.get("ETag") or "").strip('"');digest=value if re.fullmatch(r"[0-9a-fA-F]{64}",value) else None;size=int(response.headers.get("X-Linked-Size") or response.headers.get("Content-Length") or 0)
                except Exception:digest=None;size=0
            artifacts.append({"name":name,"url":url,"size":size,"sha256":str(digest).removeprefix("sha256:") if digest else None,"signature":None})
        return {"source_id":source["id"],"repo":repo,"kind":"model","version":data.get("sha"),"date":data.get("lastModified"),"license":license_value,"project_url":f"https://huggingface.co/{repo}","os":source.get("os",[]),"architectures":source.get("architectures",[]),"hardware_tags":source.get("hardware_tags",[]),"assets":artifacts,"runtime_requirements":["GGUF compatible runtime"],"context_tokens":source.get("context_tokens"),"quantizations":source.get("quantizations",[])}
    def normalized_nuget(self,source,data):
        versions=[x for x in data.get("versions",[]) if "-" not in x];version=versions[-1] if versions else None
        return {"source_id":source["id"],"kind":source["kind"],"version":version,"date":None,"license":source.get("license"),"project_url":source.get("project_url"),"os":source.get("os",[]),"architectures":source.get("architectures",[]),"hardware_tags":source.get("hardware_tags",[]),"assets":[],"runtime_requirements":["NuGet package verification required"],"context_tokens":None,"quantizations":[]}
    def compatible_assets(self,record):
        hw=read(self.root/"config"/"MACHINE_PROFILE.json");system=str(hw.get("os",{}).get("name") or sys.platform).lower();arch=str(hw.get("os",{}).get("architecture") or "").lower();accel=hw.get("acceleration",{});items=[]
        for asset in record.get("assets",[]):
            name=str(asset.get("name","")).lower()
            if name.endswith((".ps1",".sh",".txt",".sig",".sha256")):continue
            windows_asset=bool(re.search(r"(^|[-_.])(win|windows)([-_.]|$)",name) or name.endswith((".exe",".msi")))
            mac_asset=bool(re.search(r"(^|[-_.])(darwin|macos|osx)([-_.]|$)",name) or name.endswith((".dmg",".pkg")))
            linux_asset=bool(re.search(r"(^|[-_.])(linux|ubuntu)([-_.]|$)",name))
            if ("windows" in system or system.startswith("win")) and (mac_asset or linux_asset):continue
            if ("darwin" in system or "mac" in system) and (windows_asset or linux_asset):continue
            if "linux" in system and (windows_asset or mac_asset):continue
            if arch in {"amd64","x86_64","x64"} and "arm64" in name:continue
            if arch in {"arm64","aarch64"} and any(x in name for x in ["x64","amd64"]):continue
            if accel.get("cuda")!="available" and "cuda" in name:continue
            if accel.get("rocm")!="available" and "rocm" in name:continue
            if accel.get("sycl")!="available" and "sycl" in name:continue
            if accel.get("vulkan")!="available" and "vulkan" in name:continue
            items.append(asset)
        return items
    def discover(self):
        report={"timestamp":now(),"enabled":self.config.get("enabled",False),"metadata_only":True,"automatic_download":False,"automatic_install":False,"channel":"stable","candidates":[],"source_failures":[]}
        if self.offline:report["status"]="offline_no_change";return self.save_report(report)
        if not self.config.get("enabled") and not self.session_opt_in:report["status"]="paused_not_opted_in";return self.save_report(report)
        for source in self.sources.get("sources",[]):
            if not source.get("official") or source.get("channel")!="stable":continue
            try:
                if source["metadata_type"]=="github_release":records=[self.normalized_release(source,self.request(source["metadata_url"]))]
                elif source["metadata_type"]=="huggingface_model":records=[self.normalized_hf(source,repo,self.request("https://huggingface.co/api/models/"+urllib.parse.quote(repo,safe="/"))) for repo in source["repos"]]
                elif source["metadata_type"]=="nuget_versions":records=[self.normalized_nuget(source,self.request(source["metadata_url"]))]
                else:
                    records=[{"source_id":source["id"],"kind":source["kind"],"version":None,"date":None,"license":source.get("license"),"project_url":source.get("project_url") or source.get("metadata_url"),"os":source.get("os",[]),"architectures":source.get("architectures",[]),"hardware_tags":source.get("hardware_tags",[]),"assets":[],"advisory_only":True}]
                for record in records:self.evaluate(source,record,report)
            except Exception as exc:report["source_failures"].append({"source_id":source["id"],"error":str(exc)})
        self.state["last_scan"]=now();atomic(self.state_path,self.state);report["status"]="metadata_collected_user_review_required";return self.save_report(report)
    def evaluate(self,source,record,report):
        artifact=record.get("assets",[{}])[0].get("name","metadata") if record.get("assets") else "metadata";cid=candidate_key(source["id"],record.get("version"),artifact)
        existing=self.state["candidates"].get(cid)
        if existing:
            self.refresh_revocations()
            if self.revoked(source["id"],record.get("version")) and existing["state"]!="revoked" and "revoked" in ALLOWED_TRANSITIONS.get(existing["state"],set()):self.transition(existing,"revoked","revocation_list_refresh")
            age=(dt.datetime.now(UTC)-dt.datetime.fromisoformat(existing["updated_at"])).total_seconds()/86400
            existing["cooldown"]={"days":self.config.get("cooldown_days",14),"remaining_days":max(0,round(self.config.get("cooldown_days",14)-age,2)),"active":age<self.config.get("cooldown_days",14)}
            report["candidates"].append(existing);return
        compatible=self.compatible_assets(record);estimated=min([int(x.get("size") or 0) for x in compatible if int(x.get("size") or 0)>0] or [0]);license_gate=self.license_gate(source,record.get("license"));cve_gate=self.cve_gate(source,record.get("version"));fit=self.memory_fit(estimated);reasons=[]
        if self.revoked(source["id"],record.get("version")):state="revoked";reasons.append("revocation_list")
        elif source.get("never_install") or record.get("advisory_only"):state="rejected";reasons.append("advisory_only_no_driver_or_bios_changes")
        elif not license_gate["promotion_allowed"]:state="rejected";reasons.append("license_gate_"+license_gate["status"])
        elif not fit["fit"]:state="rejected";reasons.append("memory_or_disk_fit_failed")
        elif not any(x.get("sha256") and x.get("size") for x in compatible):state="rejected";reasons.append("verified_compatible_artifact_unavailable")
        else:state="awaiting_user_approval";reasons.append("cve_gate_requires_resolution" if not cve_gate["promotion_allowed"] else "ready_for_optional_canary")
        stamp=now();candidate={"id":cid,"state":state,"discovered_at":stamp,"updated_at":stamp,"source":record,"compatible_assets":compatible,"license_gate":license_gate,"cve_gate":cve_gate,"memory_fit":fit,"reasons":reasons,"cooldown":{"days":self.config.get("cooldown_days",14),"remaining_days":self.config.get("cooldown_days",14),"active":True},"history":[{"state":"discovered","at":stamp,"reason":"official_metadata_discovery"},{"state":state,"at":stamp,"reason":"discovery_evaluation"}]}
        self.state["candidates"][cid]=candidate;report["candidates"].append(candidate)
    def transition(self,candidate,new_state,reason):
        if new_state not in STATES or new_state not in ALLOWED_TRANSITIONS.get(candidate["state"],set()):raise RuntimeError(f"invalid_transition:{candidate['state']}->{new_state}")
        candidate["state"]=new_state;candidate["updated_at"]=now();candidate.setdefault("history",[]).append({"state":new_state,"at":now(),"reason":reason});atomic(self.state_path,self.state)
    def canary(self,cid,approval):
        candidate=self.state["candidates"].get(cid)
        if not candidate:raise RuntimeError("candidate_not_found")
        self.enforce_not_revoked(candidate)
        if approval!=f"APPROVE-CANARY-{cid}":raise RuntimeError("explicit_canary_approval_required")
        if candidate["state"]!="awaiting_user_approval":raise RuntimeError("candidate_not_awaiting_approval")
        if not candidate["license_gate"]["promotion_allowed"]:raise RuntimeError("license_gate_not_passed")
        assets=[x for x in candidate.get("compatible_assets",candidate["source"].get("assets",[])) if x.get("sha256") and x.get("size")]
        if not assets:raise RuntimeError("verified_artifact_unavailable")
        asset=min(assets,key=lambda x:x["size"]);sandbox=self.root/"canary"/cid;download=sandbox/"downloads"/Path(asset["name"]).name;download.parent.mkdir(parents=True,exist_ok=True);part=download.with_suffix(download.suffix+".part")
        if not host_allowed(asset["url"],self.sources):raise RuntimeError("source_not_allowed")
        offset=part.stat().st_size if part.exists() else 0;headers={"User-Agent":"ARBELAI-Watcher/1.0"}
        if offset:headers["Range"]=f"bytes={offset}-"
        req=urllib.request.Request(asset["url"],headers=headers)
        with self.opener(req,timeout=120,context=ssl.create_default_context()) as response:
            mode="ab" if offset and getattr(response,"status",200)==206 else "wb"
            with part.open(mode) as out:shutil.copyfileobj(response,out)
        if part.stat().st_size!=asset["size"]:raise RuntimeError("size_mismatch")
        if sha256(part)!=asset["sha256"]:raise RuntimeError("hash_mismatch")
        os.replace(part,download)
        if zipfile.is_zipfile(download):safe_extract(download,sandbox/"extracted")
        atomic(sandbox/"CANARY_MANIFEST.json",{"candidate_id":cid,"artifact":str(download.relative_to(self.root)),"sha256":sha256(download),"size":download.stat().st_size,"production_changed":False})
        self.transition(candidate,"canary_downloaded","verified_canary_download")
        if candidate["cve_gate"]["promotion_allowed"]:self.transition(candidate,"security_passed","license_cve_hash_size_archive_passed")
        return candidate
    def benchmark(self,cid,runtime_path=None):
        candidate=self.state["candidates"].get(cid)
        if not candidate or candidate["state"]!="security_passed":raise RuntimeError("candidate_not_security_passed")
        self.enforce_not_revoked(candidate)
        manifest=read(self.root/"canary"/cid/"CANARY_MANIFEST.json");artifact=(self.root/manifest["artifact"]).resolve()
        if not artifact.is_relative_to((self.root/"canary"/cid).resolve()):raise RuntimeError("canary_path_invalid")
        runtime=Path(runtime_path).resolve() if runtime_path else None
        if not runtime or not runtime.is_file():raise RuntimeError("verified_runtime_path_required")
        output=self.root/"canary"/cid/"benchmark.json";command=[sys.executable,str(self.root/"engine"/"benchmark.py"),"--model-id",cid,"--model",str(artifact),"--server",str(runtime),"--output",str(output),"--repetitions","2"]
        import subprocess
        cp=subprocess.run(command,capture_output=True,text=True,timeout=1800,errors="replace")
        if cp.returncode:raise RuntimeError("canary_benchmark_failed:"+cp.stderr[-1000:])
        return {"candidate_id":cid,"gold_set":str((self.root/"config"/"GOLD_SET.json").relative_to(self.root)),"result":str(output.relative_to(self.root))}
    def compare(self,cid,baseline_path,result_path):
        candidate=self.state["candidates"].get(cid)
        if not candidate or candidate["state"]!="security_passed":raise RuntimeError("candidate_not_security_passed")
        self.enforce_not_revoked(candidate)
        baseline=read(Path(baseline_path));result=read(Path(result_path));quality_ok=result.get("average_quality",0)>=baseline.get("average_quality",0);stability_ok=result.get("stability_success_rate",0)>=baseline.get("stability_success_rate",0);privacy_ok=result.get("privacy_gate_passed") is True;speed=((result.get("average_tokens_per_second",0)/max(baseline.get("average_tokens_per_second",0),.001))-1)*100;ram=((result.get("peak_ram_bytes",0)/max(baseline.get("peak_ram_bytes",1),1))-1)*100
        justified=speed>=self.config.get("minimum_speed_improvement_percent",5) or result.get("average_quality",0)>baseline.get("average_quality",0)
        comparison={"quality_no_regression":quality_ok,"stability_no_regression":stability_ok,"privacy_passed":privacy_ok,"speed_delta_percent":speed,"ram_delta_percent":ram,"resource_limit_ok":ram<=self.config.get("maximum_ram_increase_percent",10),"improvement_justified":justified}
        candidate["regression"]=comparison
        if all([quality_ok,stability_ok,privacy_ok,comparison["resource_limit_ok"],justified]):self.transition(candidate,"benchmark_passed","regression_gate_passed")
        else:self.transition(candidate,"rejected","benchmark_regression_or_no_justified_improvement")
        return comparison
    def promote(self,cid,approval):
        candidate=self.state["candidates"].get(cid)
        if not candidate or candidate["state"]!="benchmark_passed":raise RuntimeError("candidate_not_benchmark_passed")
        self.enforce_not_revoked(candidate)
        if approval!=f"APPROVE-PROMOTION-{cid}":raise RuntimeError("explicit_promotion_approval_required")
        current=self.state.get("production")
        if current and self.config.get("downgrade_protection") and version_key(candidate["source"].get("version"))<version_key(current.get("version")):raise RuntimeError("downgrade_blocked")
        backup=self.root/"data"/"promotion_backups"/(dt.datetime.now().strftime("%Y%m%d-%H%M%S")+".json");atomic(backup,{"production":current,"last_known_good":self.state.get("last_known_good")})
        if current:self.state["last_known_good"]=current
        self.state["production"]={"candidate_id":cid,"source_id":candidate["source"]["source_id"],"version":candidate["source"].get("version"),"promoted_at":now(),"backup":str(backup.relative_to(self.root))};self.transition(candidate,"promoted","explicit_atomic_promotion");return self.state["production"]
    def rollback(self,cid,approval):
        candidate=self.state["candidates"].get(cid)
        if not candidate or candidate["state"]!="promoted":raise RuntimeError("candidate_not_promoted")
        self.enforce_not_revoked(candidate)
        if approval!=f"APPROVE-ROLLBACK-{cid}":raise RuntimeError("explicit_rollback_approval_required")
        lkg=self.state.get("last_known_good")
        if lkg and self.revoked(lkg.get("source_id"),lkg.get("version")):raise RuntimeError("last_known_good_revoked")
        self.state["production"]=lkg;self.transition(candidate,"rolled_back","explicit_atomic_rollback");return self.state.get("production")
    def revoke(self,cid,reason):
        candidate=self.state["candidates"].get(cid)
        if not candidate:raise RuntimeError("candidate_not_found")
        self.revocations.setdefault("revoked",[]).append({"source_id":candidate["source"]["source_id"],"version":candidate["source"].get("version"),"reason":reason,"at":now()});atomic(self.root/"config"/"REVOCATIONS.json",self.revocations)
        if candidate["state"]!="revoked":self.transition(candidate,"revoked",reason)
        if self.state.get("production",{}).get("candidate_id")==cid:self.state["production"]=None;atomic(self.state_path,self.state)
        return candidate
    def save_report(self,report):
        out=self.root/"reports"/"IMPROVEMENT_REPORT.json";atomic(out,report)
        he=["מה נמצא: "+str(len(report.get("candidates",[]))),"מה נפסל: "+str(sum(x.get("state") in {"rejected","revoked"} for x in report.get("candidates",[]))),"המלצה: לאשר Canary רק למועמד שעבר מקור, רישיון, CVE, זיכרון ו־SHA256."]
        (self.root/"reports"/"IMPROVEMENT_REPORT_HE.txt").write_text("\n".join(he),encoding="utf-8-sig");return report

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["scan","canary","benchmark","compare","promote","rollback","revoke"],nargs="?",default="scan");p.add_argument("--root",required=True);p.add_argument("--offline",action="store_true");p.add_argument("--session-opt-in",action="store_true",help="One-time metadata scan without enabling a schedule");p.add_argument("--candidate");p.add_argument("--approval");p.add_argument("--baseline");p.add_argument("--result");p.add_argument("--runtime");p.add_argument("--reason",default="security_revocation");a=p.parse_args();w=Watcher(a.root,a.offline,session_opt_in=a.session_opt_in)
    if a.command=="scan":result=w.discover()
    elif a.command=="canary":result=w.canary(a.candidate,a.approval)
    elif a.command=="benchmark":result=w.benchmark(a.candidate,a.runtime)
    elif a.command=="compare":result=w.compare(a.candidate,a.baseline,a.result)
    elif a.command=="promote":result=w.promote(a.candidate,a.approval)
    elif a.command=="rollback":result=w.rollback(a.candidate,a.approval)
    else:result=w.revoke(a.candidate,a.reason)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
