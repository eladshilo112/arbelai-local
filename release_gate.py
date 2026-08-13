#!/usr/bin/env python3
import argparse,ast,hashlib,json,os,re,subprocess,sys,zipfile
from pathlib import Path
PRIVATE_PATTERNS=[r"C:"+r"\\Users\\",r"/"+r"Users/[^/]+/",r"/"+r"home/[^/]+/",r"(?i)api[_-]?key\s*[:=]\s*[^\s,;]{8,}",r"(?i)password\s*[:=]\s*[^\s,;]{8,}"]
FORBIDDEN_PARTS={"models","cache","logs","backups","downloads","benchmark_results","private_results","__pycache__",".arbelai-install"}
def sha(path):
    h=hashlib.sha256();h.update(path.read_bytes());return h.hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(Path(__file__).resolve().parent));p.add_argument("--zip");a=p.parse_args();root=Path(a.root).resolve();checks=[];findings=[]
    files=[x for x in root.rglob("*") if x.is_file() and "__pycache__" not in x.parts and ".git" not in x.parts]
    for path in files:
        rel=path.relative_to(root)
        if any(part in FORBIDDEN_PARTS for part in rel.parts):findings.append({"severity":"high","type":"forbidden_release_content","path":str(rel)})
        if path.suffix.lower() in {".gguf",".bin",".safetensors",".log",".pyc"}:findings.append({"severity":"high","type":"forbidden_binary_or_log","path":str(rel)})
        overlap=""
        try:
            with path.open("r",encoding="utf-8",errors="ignore") as stream:
                while True:
                    chunk=stream.read(1024*1024)
                    if not chunk:break
                    text=overlap+chunk
                    for pattern in PRIVATE_PATTERNS:
                        if re.search(pattern,text):findings.append({"severity":"high","type":"private_path_or_secret","path":str(rel),"pattern":pattern});break
                    overlap=text[-1024:]
        except OSError as exc:findings.append({"severity":"high","type":"unscannable_file","path":str(rel),"error":str(exc)})
    compile_result=subprocess.run([sys.executable,"-m","compileall","-q",str(root)],capture_output=True,text=True);checks.append({"name":"python_compile","ok":compile_result.returncode==0,"detail":compile_result.stderr})
    tests=subprocess.run([sys.executable,"-m","unittest","discover","-s",str(root/"tests"),"-v"],capture_output=True,text=True,timeout=180);test_text=tests.stdout+tests.stderr;match=re.search(r"Ran (\d+) tests?",test_text);skip_match=re.search(r"skipped=(\d+)",test_text);checks.append({"name":"unit_integration_failure_tests","ok":tests.returncode==0,"detail":{"test_count":int(match.group(1)) if match else None,"skipped":int(skip_match.group(1)) if skip_match else 0,"result":"passed" if tests.returncode==0 else "failed"}})
    sbom=root/"SBOM.spdx.json";checks.append({"name":"sbom_present_valid","ok":sbom.exists() and bool(json.loads(sbom.read_text()).get("packages"))})
    lock_path=root/"DEPENDENCY_LOCK.json";lock=read_lock=None
    try:lock=json.loads(lock_path.read_text(encoding="utf-8-sig"));lock_ok=lock.get("bundled_python_packages")==[] and lock.get("bundled_binaries")==[] and lock.get("bundled_models")==[]
    except Exception as exc:lock_ok=False;lock={"error":str(exc)}
    imported=set()
    standard=set(getattr(sys,"stdlib_module_names",set()))
    for path in root.rglob("*.py"):
        if ".git" in path.parts:continue
        try:
            tree=ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):imported.update(x.name.split('.')[0] for x in node.names)
                elif isinstance(node,ast.ImportFrom) and node.module:imported.add(node.module.split('.')[0])
        except SyntaxError:pass
    local={p.stem for p in root.rglob("*.py")};third_party=sorted(x for x in imported if x not in standard and x not in local and x!="__future__")
    dependency_ok=lock_ok and not third_party;checks.append({"name":"dependency_audit","ok":dependency_ok,"detail":{"lock":lock,"unlocked_imports":third_party}})
    static=[]
    for path in root.rglob("*.py"):
        if ".git" in path.parts:continue
        try:tree=ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError as exc:static.append({"path":str(path.relative_to(root)),"issue":str(exc)});continue
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=="os" and node.func.attr=="system":static.append({"path":str(path.relative_to(root)),"issue":"os.system"})
            if isinstance(node,ast.Call) and any(k.arg=="shell" and isinstance(k.value,ast.Constant) and k.value.value is True for k in node.keywords):static.append({"path":str(path.relative_to(root)),"issue":"shell_true"})
    checks.append({"name":"static_analysis","ok":not static,"detail":static})
    permissions=[]
    if os.name!="nt":
        for path in files:
            if path.stat().st_mode & 0o002:permissions.append(str(path.relative_to(root)))
    checks.append({"name":"permissions","ok":not permissions,"detail":permissions or "user scoped package"})
    defender={"available":False,"ran":False,"result":"not_available"}
    if os.name=="nt":
        candidates=[Path(os.environ.get("ProgramFiles",""))/"Windows Defender"/"MpCmdRun.exe",Path(os.environ.get("ProgramData",""))/"Microsoft"/"Windows Defender"/"Platform"]
        exe=next((x for x in candidates if x.is_file()),None)
        if not exe and candidates[1].is_dir():exe=next(iter(sorted(candidates[1].glob("*/MpCmdRun.exe"),reverse=True)),None)
        if exe:
            defender["available"]=True;scan_target=str(Path(a.zip).resolve()) if a.zip else str(root)
            escaped=scan_target.replace("'","''");script=f"$s=Get-MpComputerStatus;if(-not $s.AntivirusEnabled){{throw 'Defender disabled'}};Start-MpScan -ScanType CustomScan -ScanPath '{escaped}' -ErrorAction Stop;[pscustomobject]@{{AntivirusEnabled=$s.AntivirusEnabled;RealTimeProtectionEnabled=$s.RealTimeProtectionEnabled;SignatureVersion=$s.AntivirusSignatureVersion}}|ConvertTo-Json -Compress"
            cp=subprocess.run(["powershell","-NoProfile","-Command",script],capture_output=True,text=True,timeout=600);defender.update({"ran":True,"code":cp.returncode,"result":(cp.stdout+cp.stderr)[-4000:]});checks.append({"name":"windows_defender","ok":cp.returncode==0,"detail":defender})
    if a.zip:
        zip_path=Path(a.zip).resolve();checksum_path=Path(str(zip_path)+".sha256");expected=None
        if checksum_path.exists():expected=checksum_path.read_text(encoding="ascii",errors="ignore").split()[0].lower()
        checksum_ok=bool(expected and re.fullmatch(r"[0-9a-f]{64}",expected) and sha(zip_path)==expected);checks.append({"name":"zip_sha256","ok":checksum_ok,"detail":{"checksum_file_present":checksum_path.exists(),"match":checksum_ok}})
        with zipfile.ZipFile(zip_path) as z:names=z.namelist();bad=[n for n in names if any(part in FORBIDDEN_PARTS for part in Path(n).parts) or Path(n).suffix.lower() in {".gguf",".log",".pyc"}]
        checks.append({"name":"zip_clean","ok":not bad,"detail":bad})
    blockers=[x for x in findings if x["severity"] in {"critical","high"}];passed=not blockers and all(x["ok"] for x in checks);report={"status":"passed" if passed else "blocked","claim":"לא נמצאו חולשות קריטיות או גבוהות בבדיקות שבוצעו" if passed else "השחרור חסום בשל ממצא או בדיקה שנכשלה","known_open_critical_high":len(blockers),"findings":findings,"checks":checks,"defender":defender}
    out=root/"SECURITY_TEST_REPORT.json";out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8-sig");print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if passed else 1
if __name__=="__main__":raise SystemExit(main())
