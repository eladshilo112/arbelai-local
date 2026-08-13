#!/usr/bin/env python3
"""ARBELAI Portable installer and migration manager. Standard library only."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent
VERSION = (BUNDLE / "VERSION").read_text(encoding="utf-8").strip()
USER_AGENT = f"ARBELAI-Portable/{VERSION}"

def allowed_download_url(url: str) -> bool:
    parsed=urllib.parse.urlparse(url)
    allowed=read_json(BUNDLE/"config"/"OFFICIAL_CATALOG.json").get("allowed_hosts",[])
    host=parsed.hostname or ""
    host_ok=host in allowed or host.endswith(".cdn.hf.co")
    return parsed.scheme=="https" and host_ok and not parsed.username and not parsed.password

def verify_sha256(path: Path, expected: str) -> bool:
    return bool(expected) and sha256(path).lower()==expected.lower().removeprefix("sha256:")

def safe_extract_zip(archive: Path, destination: Path) -> None:
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            resolved=(destination/info.filename).resolve()
            if not resolved.is_relative_to(destination):raise RuntimeError("Unsafe archive path")
        z.extractall(destination)


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    os.replace(temp, path)


class Installer:
    def __init__(self, target: Path, dry_run=False, non_interactive=False, approvals=None, config_home=None, offline=False):
        self.target = target.resolve()
        self.dry_run = dry_run
        self.non_interactive = non_interactive
        self.approvals = set(approvals or [])
        self.config_home = (config_home or Path.home()).resolve()
        self.offline = offline
        self.meta = self.target / ".arbelai-install"
        self.state_path = self.meta / "state.json"
        self.log_path = self.meta / "install.jsonl"
        self.failure_path = self.meta / "failure_memory.jsonl"
        self.state = read_json(self.state_path, {"version": VERSION, "checkpoints": {}, "changes": [], "created_at": utcnow()})
        self.session = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.current_profile = {}

    def record(self, event, **detail):
        row = {"timestamp": utcnow(), "session": self.session, "event": event, **detail}
        self.meta.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def checkpoint(self, name, payload=None):
        self.state["checkpoints"][name] = {"completed_at": utcnow(), "payload": payload or {}}
        atomic_json(self.state_path, self.state)
        self.record("checkpoint", name=name)

    def failed(self, stage, error):
        self.meta.mkdir(parents=True, exist_ok=True)
        row = {"timestamp": utcnow(), "session": self.session, "stage": stage, "error": repr(error)}
        with self.failure_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.record("failure", stage=stage, error=str(error))

    def approved(self, kind, explanation):
        if kind in self.approvals:
            self.record("approval", kind=kind, source="command_line")
            return True
        if self.dry_run or self.non_interactive:
            self.record("approval_not_granted", kind=kind)
            return False
        print(f"\nנדרש אישור: {explanation}")
        answer = input("לאשר? הקלד כן: ").strip()
        ok = answer == "כן"
        self.record("approval", kind=kind, granted=ok, source="interactive")
        return ok

    def backup(self, path: Path):
        if not path.exists():
            return None
        before = sha256(path)
        backup = self.meta / "backups" / self.session / path.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        if sha256(backup) != before:
            raise RuntimeError(f"Backup verification failed: {path}")
        entry = {"path": str(path), "backup": str(backup), "sha256_before": before, "timestamp": utcnow(), "session": self.session}
        self.state["changes"].append(entry)
        atomic_json(self.state_path, self.state)
        self.record("backup", **entry)
        return entry

    def write(self, path: Path, content: bytes):
        for parent in [path, *path.parents]:
            if parent.exists() and parent.is_symlink():
                raise RuntimeError(f"Refusing write through symbolic link or junction candidate: {parent}")
        if path.exists() and path.read_bytes() == content:
            self.record("unchanged", path=str(path))
            return False
        if self.dry_run:
            self.record("would_write", path=str(path), bytes=len(content))
            return False
        previous = self.backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(content)
        os.replace(temp, path)
        if previous is None:
            self.state["changes"].append({"path": str(path), "created": True, "sha256_after": sha256(path), "timestamp": utcnow(), "session": self.session})
        else:
            previous["sha256_after"] = sha256(path)
        atomic_json(self.state_path, self.state)
        self.record("write", path=str(path), sha256=sha256(path))
        return True

    def copy_payload(self):
        for source in sorted(BUNDLE.rglob("*")):
            if not source.is_file() or ".arbelai-install" in source.parts or source.name in {"הפעלת ARBELAI.cmd", "run-arbelai.sh"}:
                continue
            relative = source.relative_to(BUNDLE)
            if relative.parts and relative.parts[0] in {"tests", "docs"}:
                continue
            if source.name.endswith(".template.json"):
                relative=relative.with_name(source.name.replace(".template.json",".json"))
            self.write(self.target / relative, source.read_bytes())

    def run_capture(self, command, timeout=20):
        try:
            cp = subprocess.run(command, capture_output=True, text=True, timeout=timeout, errors="replace")
            return {"ok": cp.returncode == 0, "code": cp.returncode, "stdout": cp.stdout[-12000:], "stderr": cp.stderr[-4000:]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def discover(self):
        system = platform.system()
        profile = {
            "profile_date": utcnow(), "os": {"name": system, "release": platform.release(), "version": platform.version(), "architecture": platform.machine()},
            "cpu": {"name": platform.processor() or "unknown", "logical_processors": os.cpu_count()},
            "ram": {}, "storage": {}, "gpu": [], "npu": [], "acceleration": {}, "tools": {}
        }
        try:
            usage = shutil.disk_usage(self.target.anchor or Path.home().anchor)
            profile["storage"] = {"total_bytes": usage.total, "free_bytes": usage.free}
        except OSError as exc:
            profile["storage"] = {"error": str(exc)}
        if system == "Windows":
            ps = shutil.which("powershell") or shutil.which("pwsh")
            if ps:
                script = "$c=Get-CimInstance Win32_ComputerSystem;$p=Get-CimInstance Win32_Processor;$g=Get-CimInstance Win32_VideoController;[pscustomobject]@{ram=[int64]$c.TotalPhysicalMemory;cpu=$p.Name;gpu=@($g|%{$_.Name});gpuDriver=@($g|%{$_.DriverVersion})}|ConvertTo-Json -Compress"
                out = self.run_capture([ps, "-NoProfile", "-Command", script])
                if out.get("ok"):
                    try:
                        hw = json.loads(out["stdout"]); profile["ram"]["total_bytes"] = hw.get("ram"); profile["cpu"]["name"] = hw.get("cpu"); profile["gpu"] = hw.get("gpu") or []
                    except json.JSONDecodeError:
                        pass
            profile["acceleration"]["directml"] = "candidate" if profile["gpu"] else "not_detected"
        elif system == "Darwin":
            mem = self.run_capture(["sysctl", "-n", "hw.memsize"])
            if mem.get("ok") and mem["stdout"].strip().isdigit(): profile["ram"]["total_bytes"] = int(mem["stdout"].strip())
            gpu = self.run_capture(["system_profiler", "SPDisplaysDataType", "-json"])
            profile["gpu"] = ["Apple GPU or detected display adapter"] if gpu.get("ok") else []
            profile["acceleration"]["metal"] = "candidate" if platform.machine().lower() in {"arm64", "aarch64"} else "probe_required"
        else:
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                first = meminfo.read_text(errors="ignore").splitlines()[0].split()
                if len(first) > 1: profile["ram"]["total_bytes"] = int(first[1]) * 1024
            gpu = self.run_capture(["lspci"])
            if gpu.get("ok"): profile["gpu"] = [line for line in gpu["stdout"].splitlines() if "VGA" in line or "3D controller" in line]
        probes = {"cuda":["nvidia-smi"], "rocm":["rocminfo"], "vulkan":["vulkaninfo", "--summary"], "openvino":[sys.executable, "-c", "import openvino;print(openvino.__version__)"], "sycl":["sycl-ls"]}
        for name, command in probes.items():
            executable = shutil.which(command[0]) if command[0] != sys.executable else sys.executable
            profile["acceleration"][name] = "available" if executable and self.run_capture([executable, *command[1:]], timeout=12).get("ok") else "not_verified"
        for name in ["python", "git", "codex", "claude", "winget", "brew", "apt-get", "dnf"]:
            profile["tools"][name] = shutil.which(name)
        profile["npu"] = ["OpenVINO probe available, target inference required"] if profile["acceleration"].get("openvino") == "available" else []
        total=int(profile.get("ram",{}).get("total_bytes") or 0); free=int(profile.get("storage",{}).get("free_bytes") or 0)
        if total and total < 8*1024**3: mode="context_only"
        elif free and free < 12*1024**3: mode="context_only"
        else: mode="local_inference_candidate"
        profile["compatibility"]={"mode":mode,"minimum_ram_bytes":8*1024**3,"minimum_free_disk_bytes":12*1024**3,"safe_fallback":"context_only_or_cloud_only","local_download_allowed":mode=="local_inference_candidate"}
        self.current_profile=profile
        if not self.dry_run: atomic_json(self.target / "config" / "MACHINE_PROFILE.json", profile)
        self.record("hardware_profile", profile=profile)
        return profile

    def workload(self):
        template = read_json(BUNDLE / "config" / "WORKLOAD_PROFILE.template.json")
        if not self.non_interactive and not self.dry_run:
            roots = input("תיקיות ידע מקומיות לאינדוקס, מופרדות בנקודה פסיק, או Enter לדילוג: ").strip()
            if roots: template["context_roots"] = [x.strip() for x in roots.split(";") if x.strip()]
            watcher=input("להפעיל בדיקת שיפורים שבועית של Metadata רשמי בלבד? הקלד כן: ").strip()=="כן"
            watcher_path=self.target/"config"/"IMPROVEMENT_WATCHER.json"
            watcher_config=read_json(watcher_path,read_json(BUNDLE/"config"/"IMPROVEMENT_WATCHER.json"));watcher_config["enabled"]=watcher
            if not self.dry_run: atomic_json(watcher_path,watcher_config)
        template["profile_date"] = utcnow()
        if not self.dry_run: atomic_json(self.target / "config" / "WORKLOAD_PROFILE.json", template)
        self.record("workload_profile", profile=template)
        return template

    def fetch_json(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def head_metadata(self,url):
        if not allowed_download_url(url):raise RuntimeError("Unapproved metadata host")
        request=urllib.request.Request(url,headers={"User-Agent":USER_AGENT},method="HEAD")
        with urllib.request.urlopen(request,timeout=30) as response:
            final=response.geturl()
            if not allowed_download_url(final):raise RuntimeError("Unapproved redirect host")
            raw=(response.headers.get("X-Linked-Etag") or response.headers.get("ETag") or "").strip('"')
            digest=raw if len(raw)==64 and all(c in "0123456789abcdefABCDEF" for c in raw) else None
            size=int(response.headers.get("X-Linked-Size") or response.headers.get("Content-Length") or 0)
            return {"sha256":digest,"size":size,"final_host":urllib.parse.urlparse(final).hostname}

    def official_shortlist(self, profile):
        catalog = read_json(BUNDLE / "config" / "OFFICIAL_CATALOG.json")
        total_ram = int(profile.get("ram", {}).get("total_bytes") or 0)
        reserve = max(4 * 1024**3, int(total_ram * 0.25)) if total_ram else 8 * 1024**3
        usable = max(0, total_ram - reserve)
        result = {"generated_at": utcnow(), "official_metadata_checked": False, "runtime": {}, "models": [], "memory_fit": {"total_ram_bytes": total_ram, "reserved_bytes": reserve, "usable_bytes": usable}}
        if not self.offline:
            release = self.fetch_json(catalog["runtimes"][0]["metadata_url"])
            result["official_metadata_checked"] = True
            result["runtime"] = {"id":"llama.cpp", "version":release.get("tag_name"), "source":release.get("html_url"), "license":"MIT", "assets":[{"name":a.get("name"),"url":a.get("browser_download_url"),"size":a.get("size"),"digest":a.get("digest")} for a in release.get("assets",[])]}
        else:
            result["runtime"] = {"id":"llama.cpp","status":"metadata_not_checked_offline"}
        for model in catalog["models"]:
            estimate = int((model["estimated_weights_gb"] + 1.2) * 1024**3)
            row = {**model, "estimated_total_bytes": estimate, "fit": bool(usable and estimate <= usable)}
            if not self.offline:
                api = self.fetch_json("https://huggingface.co/api/models/" + urllib.parse.quote(model["repo"], safe="/"))
                license_value = (api.get("cardData") or {}).get("license")
                siblings = api.get("siblings") or []
                matches = [s for s in siblings if model["filename_hint"].lower() in s.get("rfilename", "").lower()]
                file_verification=None
                if matches:
                    resolved=f"https://huggingface.co/{model['repo']}/resolve/{api.get('sha')}/{urllib.parse.quote(matches[0]['rfilename'])}"
                    file_verification=self.head_metadata(resolved)
                row["official_metadata"] = {"model_id":api.get("modelId"), "revision":api.get("sha"), "license":license_value, "files":matches,"file_verification":file_verification}
                row["source_verified"] = api.get("modelId", "").casefold() == model["repo"].casefold() and str(license_value).lower() in {"apache-2.0","apache 2.0"} and bool(file_verification and file_verification.get("sha256") and file_verification.get("size"))
            result["models"].append(row)
        if not self.dry_run: atomic_json(self.target / "config" / "SHORTLIST_AND_MEMORY_FIT.json", result)
        self.record("shortlist", shortlist=result)
        return result

    def choose_asset(self, runtime):
        system = platform.system().lower(); machine = platform.machine().lower()
        accel=self.current_profile.get("acceleration",{});gpu=" ".join(self.current_profile.get("gpu",[])).lower()
        if system=="windows" and accel.get("cuda")=="available":tokens=["win","cuda","x64"]
        elif system=="windows" and accel.get("vulkan")=="available":tokens=["win","vulkan","x64"]
        elif system=="windows":tokens=["win","cpu","x64"]
        elif system=="darwin" and machine in {"arm64","aarch64"}:tokens=["macos","arm64"]
        elif system=="linux" and accel.get("cuda")=="available":tokens=["ubuntu","cuda","x64"]
        elif system=="linux":tokens=["ubuntu","x64"]
        else:tokens=[]
        assets = runtime.get("assets", [])
        scored = sorted(assets, key=lambda a: sum(t in a.get("name", "").lower() for t in tokens), reverse=True)
        return scored[0] if scored and sum(t in scored[0].get("name", "").lower() for t in tokens) >= max(1, len(tokens)-1) else None

    def install_candidates(self, shortlist):
        if self.current_profile.get("compatibility",{}).get("local_download_allowed") is False:
            return {"installed":False,"reason":"safe_fallback_context_only","plan":{"runtime":None,"models":[]}}
        fit = [m for m in shortlist["models"] if m.get("fit") and m.get("source_verified", self.offline)]
        selected_general = next((m for m in reversed(fit) if "general" in m["roles"]), None)
        selected_embed = next((m for m in fit if "retrieval" in m["roles"]), None)
        plan = {"runtime": self.choose_asset(shortlist["runtime"]), "models":[m for m in [selected_general, selected_embed] if m]}
        atomic_json(self.target / "config" / "DOWNLOAD_PLAN.json", plan) if not self.dry_run else None
        if not plan["runtime"] or not selected_general:
            self.record("download_plan_incomplete", plan=plan)
            return {"installed": False, "reason":"No verified fitting runtime and general model", "plan":plan}
        total = int(plan["runtime"].get("size") or 0) + sum(int(m.get("estimated_total_bytes",0)) for m in plan["models"])
        if not self.approved("downloads", f"הורדת Runtime ומודלים חינמיים ממקורות רשמיים בלבד, בהיקף משוער של {total/1024**3:.1f} GB"):
            return {"installed": False, "reason":"approval_required", "plan":plan}
        return self._download_plan(plan)

    def download(self, url, destination, expected=None):
        host = urllib.parse.urlparse(url).hostname or ""
        if not allowed_download_url(url): raise RuntimeError(f"Unapproved download host: {host}")
        destination.parent.mkdir(parents=True, exist_ok=True);part=destination.with_suffix(destination.suffix+".part");last_error=None
        for attempt in range(1,4):
            try:
                offset=part.stat().st_size if part.exists() else 0;headers={"User-Agent":USER_AGENT}
                if offset:headers["Range"]=f"bytes={offset}-"
                request=urllib.request.Request(url,headers=headers)
                with urllib.request.urlopen(request,timeout=90) as source:
                    status=getattr(source,"status",200);mode="ab" if offset and status==206 else "wb"
                    with part.open(mode) as out:shutil.copyfileobj(source,out)
                os.replace(part,destination);last_error=None;break
            except Exception as exc:
                last_error=exc;self.record("download_retry",url=url,attempt=attempt,error=str(exc));time.sleep(min(2**attempt,8))
        if last_error:raise last_error
        actual = sha256(destination)
        if expected and not verify_sha256(destination,expected):
            raise RuntimeError(f"SHA256 mismatch for {destination.name}")
        self.record("download", url=url, path=str(destination), sha256=actual, expected=expected)
        return actual

    def _download_plan(self, plan):
        downloads = self.target / "downloads"; runtimes = self.target / "runtimes"; models = self.target / "models"
        asset = plan["runtime"]; archive = downloads / asset["name"]
        digest = asset.get("digest"); expected = digest.split(":",1)[1] if isinstance(digest,str) and digest.startswith("sha256:") else None
        if not expected: raise RuntimeError("Official runtime SHA256 is unavailable")
        self.download(asset["url"], archive, expected)
        runtime_dir = runtimes / "llama.cpp"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(archive): safe_extract_zip(archive,runtime_dir)
        registry = {"version":2,"runtimes":{},"models":{},"promotion_rule":"Local Preferred only after category threshold passes"}
        servers = list(runtime_dir.rglob("llama-server.exe")) + list(runtime_dir.rglob("llama-server"))
        registry["runtimes"]["llama.cpp"] = {"status":"installed_verified","server_path":str(servers[0]) if servers else None,"archive_sha256":sha256(archive),"source":asset["url"]}
        for model in plan["models"]:
            meta = model.get("official_metadata",{}); files = meta.get("files") or []
            if not files: continue
            file = files[0]; name=file["rfilename"]; lfs=file.get("lfs") or {}; expected_model=lfs.get("sha256") or lfs.get("oid") or meta.get("file_verification",{}).get("sha256")
            if isinstance(expected_model,str) and expected_model.startswith("sha256:"): expected_model=expected_model.split(":",1)[1]
            url=f"https://huggingface.co/{model['repo']}/resolve/{meta.get('revision') or 'main'}/{urllib.parse.quote(name)}"
            dest=models/model["id"]/Path(name).name
            if not expected_model:raise RuntimeError("Official model SHA256 is unavailable")
            actual=self.download(url,dest,expected_model)
            registry["models"][model["id"]]={"status":"candidate","source":model["repo"],"revision":meta.get("revision"),"license":model["license"],"local_path":str(dest),"sha256":actual,"qualification":{}}
        atomic_json(self.target/"config"/"MODEL_REGISTRY.json",registry)
        return {"installed":True,"registry":registry}

    def benchmark(self, installed):
        if not installed.get("installed"):
            return {"ran":False,"reason":installed.get("reason")}
        registry=read_json(self.target/"config"/"MODEL_REGISTRY.json")
        server=registry["runtimes"]["llama.cpp"].get("server_path")
        general=next(((mid,m) for mid,m in registry["models"].items() if "embedding" not in mid),None)
        if not server or not general: return {"ran":False,"reason":"runtime_or_model_missing"}
        out=self.target/"benchmark_results"/(general[0]+".json")
        command=[sys.executable,str(self.target/"engine"/"benchmark.py"),"--model-id",general[0],"--model",general[1]["local_path"],"--server",server,"--output",str(out),"--repetitions","2"]
        result=self.run_capture(command,timeout=1800)
        if not result.get("ok"): raise RuntimeError("Benchmark failed: "+result.get("stderr",result.get("error","")))
        qualify=self.run_capture([sys.executable,str(self.target/"engine"/"qualify.py"),"--root",str(self.target),"--result",str(out),"--model-id",general[0]],timeout=60)
        if not qualify.get("ok"): raise RuntimeError("Qualification failed: "+qualify.get("stderr",qualify.get("error","")))
        return {"ran":True,"result":str(out),"qualification":qualify.get("stdout")}

    def integrate(self):
        codex=shutil.which("codex"); claude=shutil.which("claude")
        plan={"codex":bool(codex),"claude_code":bool(claude),"transport":"stdio","persistent_port":False}
        if not (codex or claude): return {**plan,"changed":False,"reason":"clients_not_found"}
        if not self.approved("integration", "גיבוי ועדכון תצורת המשתמש של Codex ושל Claude Code שנמצאו, לצורך MCP מקומי מסוג stdio"):
            return {**plan,"changed":False,"reason":"approval_required"}
        python=json.dumps(sys.executable); server=json.dumps(str(self.target/"engine"/"mcp_server.py"))
        if codex:
            config=self.config_home/".codex"/"config.toml"
            current=config.read_text(encoding="utf-8-sig") if config.exists() else ""
            marker="[mcp_servers.arbelai]"
            if marker not in current:
                addition=f"\n{marker}\ncommand = {python}\nargs = [{server}]\n"
                self.write(config,(current+addition).encode("utf-8"))
        if claude:
            config=self.config_home/".claude.json"
            current=read_json(config,{})
            servers=current.setdefault("mcpServers",{})
            desired={"type":"stdio","command":sys.executable,"args":[str(self.target/"engine"/"mcp_server.py")],"env":{}}
            if servers.get("arbelai") != desired:
                servers["arbelai"]=desired
                self.write(config,json.dumps(current,ensure_ascii=False,indent=2).encode("utf-8"))
        return {**plan,"changed":True}

    def rollback_external_session_changes(self):
        restored=[]
        for item in reversed(self.state.get("changes",[])):
            path=Path(item["path"])
            if item.get("session") != self.session: continue
            try: external=not path.resolve().is_relative_to(self.target)
            except OSError: external=True
            if not external or not item.get("backup"):continue
            backup=Path(item["backup"])
            if backup.exists() and sha256(backup)==item.get("sha256_before"):
                shutil.copy2(backup,path);restored.append(str(path))
        self.record("automatic_failure_rollback",restored=restored)
        return restored

    def health(self):
        command=[sys.executable,str(self.target/"engine"/"arbelai.py"),"--root",str(self.target),"health"]
        result=self.run_capture(command,timeout=30)
        return {"ok":result.get("ok",False),"output":result.get("stdout"),"error":result.get("stderr")}

    def report(self, profile, shortlist, installed, benchmark, integration, health):
        status="TARGET_READY" if installed.get("installed") and benchmark.get("ran") and health.get("ok") else ("DRY_RUN_VALIDATED" if self.dry_run else "AWAITING_APPROVAL_OR_TARGET_VALIDATION")
        report={"generated_at":utcnow(),"status":status,"version":VERSION,"dry_run":self.dry_run,"hardware":profile,"shortlist":shortlist,"installation":installed,"benchmark":benchmark,"integration":integration,"health":health,"backups":self.state.get("changes",[]),"external_ports_opened":[],"security_or_driver_changes":[]}
        if not self.dry_run:
            atomic_json(self.target/"reports"/"TARGET_REPORT.json",report)
            text='<div dir="rtl" style="font-family: David; text-align: right;">\n\n# דוח מחשב יעד\n\n**סטטוס: '+status+'**\n\nהגילוי בוצע מחדש במחשב זה. לא נפתח פורט קבוע, לא שונו דרייברים ולא בוצעה רכישה.\n\n## תוצאות\n\n```json\n'+json.dumps({"installation":installed,"benchmark":benchmark,"integration":integration,"health":health},ensure_ascii=False,indent=2)+'\n```\n\n</div>\n'
            self.write(self.target/"reports"/"TARGET_REPORT.md",text.encode("utf-8"))
        self.record("final_report", status=status)
        return report

    def bootstrap(self):
        self.record("session_start",dry_run=self.dry_run,target=str(self.target),version=VERSION)
        try:
            prior_payload=self.state["checkpoints"].get("payload",{}).get("payload",{})
            if "payload" not in self.state["checkpoints"] or (prior_payload.get("dry_run") and not self.dry_run):
                self.copy_payload(); self.checkpoint("payload",{"dry_run":self.dry_run})
            profile=self.discover(); self.checkpoint("discovery",profile)
            workload=self.workload(); self.checkpoint("workload",workload)
            shortlist=self.official_shortlist(profile); self.checkpoint("shortlist",{"checked":shortlist["official_metadata_checked"]})
            installed=self.install_candidates(shortlist); self.checkpoint("downloads",{"installed":installed.get("installed",False)})
            bench=self.benchmark(installed); self.checkpoint("benchmark",bench)
            integration=self.integrate(); self.checkpoint("integration",integration)
            health=self.health() if not self.dry_run else {"ok":True,"mode":"dry_run_static_validation"}
            report=self.report(profile,shortlist,installed,bench,integration,health); self.checkpoint("complete",{"status":report["status"]})
            print(json.dumps(report,ensure_ascii=False,indent=2))
            return 0
        except Exception as exc:
            self.failed("bootstrap",exc)
            self.rollback_external_session_changes()
            print(f"ההתקנה נעצרה בבטחה: {exc}",file=sys.stderr)
            print("אפשר להפעיל שוב. התהליך ימשיך לפי נקודות הבקרה.",file=sys.stderr)
            return 1

    def rollback(self, confirm=False):
        if not confirm: raise SystemExit("Rollback requires --confirm-rollback")
        restored=[]; skipped=[]
        for item in reversed(self.state.get("changes",[])):
            path=Path(item["path"])
            if item.get("backup"):
                backup=Path(item["backup"])
                if not backup.exists() or sha256(backup)!=item["sha256_before"]: raise RuntimeError(f"Invalid backup: {backup}")
                if path.exists() and item.get("sha256_after") and sha256(path)!=item["sha256_after"]:
                    skipped.append({"path":str(path),"reason":"changed_after_install"}); continue
                shutil.copy2(backup,path); restored.append(str(path))
            elif item.get("created") and path.exists():
                if sha256(path)==item.get("sha256_after"):
                    quarantine=self.meta/"rollback_quarantine"/self.session/path.name; quarantine.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(path),quarantine); restored.append(str(path))
                else: skipped.append({"path":str(path),"reason":"changed_after_install"})
        result={"timestamp":utcnow(),"restored_or_quarantined":restored,"skipped":skipped}
        atomic_json(self.meta/f"rollback_{self.session}.json",result); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0


def main():
    p=argparse.ArgumentParser(); p.add_argument("command",choices=["bootstrap","rollback","discover"],nargs="?",default="bootstrap")
    p.add_argument("--target",default=str(Path.home()/"ARBELAI_COMPUTE_NODE")); p.add_argument("--dry-run",action="store_true"); p.add_argument("--non-interactive",action="store_true")
    p.add_argument("--approve",default=""); p.add_argument("--config-home"); p.add_argument("--offline",action="store_true"); p.add_argument("--confirm-rollback",action="store_true")
    a=p.parse_args(); manager=Installer(Path(a.target),a.dry_run,a.non_interactive,[x for x in a.approve.split(",") if x],Path(a.config_home) if a.config_home else None,a.offline)
    if a.command=="rollback": return manager.rollback(a.confirm_rollback)
    if a.command=="discover": print(json.dumps(manager.discover(),ensure_ascii=False,indent=2)); return 0
    return manager.bootstrap()


if __name__=="__main__": raise SystemExit(main())
