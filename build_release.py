#!/usr/bin/env python3
import argparse,hashlib,json,re,shutil,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EXCLUDE={".git",".github","__pycache__",".arbelai-install","models","cache","logs","downloads","backups","benchmark_results","private_results"}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def staged_sources(root,out):
    out=out.resolve()
    for source in root.rglob("*"):
        rel=source.relative_to(root)
        if source.resolve().is_relative_to(out) or any(part in EXCLUDE for part in rel.parts):continue
        if source.is_file():yield source,rel
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);p.add_argument("--name",default="ARBELAI-Local-1.0.0-rc");a=p.parse_args();out=Path(a.output).resolve();stage=out/(a.name+"-folder")
    if not re.fullmatch(r"[A-Za-z0-9._-]+",a.name):raise SystemExit("Invalid release name")
    if stage.exists() or (out/(a.name+".zip")).exists():raise SystemExit("Release target exists. Choose a new output or remove it only after explicit approval.")
    for source,rel in staged_sources(ROOT,out):
        dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    security=subprocess.run([sys.executable,str(stage/"release_gate.py"),"--root",str(stage)],capture_output=True,text=True,timeout=900)
    if security.returncode!=0:print(security.stdout);print(security.stderr,file=sys.stderr);return 1
    product=subprocess.run([sys.executable,str(stage/"product_gate.py"),"--root",str(stage)],capture_output=True,text=True)
    files=[]
    for path in sorted(x for x in stage.rglob("*") if x.is_file() and "__pycache__" not in x.parts):files.append({"path":path.relative_to(stage).as_posix(),"size":path.stat().st_size,"sha256":digest(path)})
    version=(ROOT/"VERSION").read_text(encoding="utf-8-sig").strip();manifest={"name":"ARBELAI Local","version":version,"channel":"release_candidate","created_at":datetime.now(timezone.utc).isoformat(),"code_signing":False,"large_models_bundled":False,"telemetry_default":False,"files":files}
    (stage/"RELEASE_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8-sig")
    archive=out/(a.name+".zip");out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(x for x in stage.rglob("*") if x.is_file() and "__pycache__" not in x.parts):z.write(path,(Path(a.name)/path.relative_to(stage)).as_posix())
    checksum=digest(archive);(out/(a.name+".zip.sha256")).write_text(checksum+"  "+archive.name+"\n",encoding="ascii")
    summary={"zip":str(archive),"sha256":checksum,"security_gate":"passed","product_gate_exit_code":product.returncode,"product_gate":product.stdout.strip()};(out/"BUILD_REPORT.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8-sig");print(json.dumps(summary,ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
