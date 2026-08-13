#!/usr/bin/env python3
"""Core local routing, privacy, retrieval, cache, ledger and health services."""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def set_root(value=None):
    global ROOT
    if value: ROOT = Path(value).resolve()

def now(): return datetime.now(timezone.utc).isoformat()
def load(name, default=None):
    path=ROOT/"config"/name
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else ({} if default is None else default)
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_suffix(path.suffix+".tmp"); temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8-sig"); temp.replace(path)
def append(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f: f.write(json.dumps(value,ensure_ascii=False)+"\n")

def privacy_scan(text):
    patterns={"email":r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b","phone":r"(?<!\d)(?:\+?\d[\s\-]?){9,15}(?!\d)","credit_card_candidate":r"(?<!\d)(?:\d[ \-]?){13,19}(?!\d)","secret_candidate":r"(?i)\b(?:api[_\-]?key|token|secret|password|private[_\-]?key)\s*[:=]\s*[^\s,;]{8,}"}
    findings=[]; redacted=text
    for kind,pattern in patterns.items():
        matches=list(re.finditer(pattern,redacted,re.I))
        if matches: findings.append({"type":kind,"count":len(matches)}); redacted=re.sub(pattern,f"[REDACTED_{kind.upper()}]",redacted,flags=re.I)
    risk="high" if any(x["type"] in {"credit_card_candidate","secret_candidate"} for x in findings) else ("medium" if findings else "low")
    return {"risk":risk,"findings":findings,"redacted_text":redacted,"cloud_allowed_without_review":risk=="low"}

def route(task_type,risk="medium",privacy="internal"):
    registry=load("MODEL_REGISTRY.json",{"models":{}}); policy=load("ROUTING_POLICY.json",load("ROUTING_POLICY.template.json",{})); rules=policy.get("task_rules",{}); rule=rules.get(task_type,rules.get("default",{}))
    critical=risk in {"high","critical"} or task_type in policy.get("critical_task_types",[])
    candidates=[]
    for mid in rule.get("local_candidates",[]):
        model=registry.get("models",{}).get(mid,{}); q=model.get("qualification",{})
        if q.get(task_type)=="qualified" or q.get("default")=="qualified": candidates.append(mid)
    if candidates and not (critical and rule.get("cloud_required_for_critical")):
        decision={"execution":"local","model":candidates[0],"verification":critical,"reason":"qualified_for_category"}
    elif privacy not in {"restricted","secret"}:
        decision={"execution":"cloud","model":rule.get("cloud_tier","strong"),"verification":critical,"reason":"no_qualified_local_model"}
    else:
        decision={"execution":"blocked","model":None,"verification":True,"reason":"restricted_data_cannot_leave_device"}
    return {**decision,"task_type":task_type,"risk":risk,"privacy":privacy,"timestamp":now()}

def db():
    path=ROOT/"data"/"context_index.sqlite"; path.parent.mkdir(parents=True,exist_ok=True); con=sqlite3.connect(path); con.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,sha256 TEXT,mtime REAL)"); con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(path UNINDEXED,ordinal UNINDEXED,text)"); return con
def index(source):
    con=db(); count=unchanged=skipped=0; allowed={".md",".txt",".json",".csv",".yaml",".yml",".toml"}
    for path in Path(source).resolve().rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed or path.stat().st_size>10_000_000: continue
        raw=path.read_bytes(); digest=hashlib.sha256(raw).hexdigest(); old=con.execute("SELECT sha256 FROM files WHERE path=?",(str(path),)).fetchone()
        if old and old[0]==digest: unchanged+=1; continue
        try: text=raw.decode("utf-8-sig")
        except UnicodeDecodeError: skipped+=1; continue
        con.execute("DELETE FROM chunks WHERE path=?",(str(path),)); parts=[text[i:i+1800] for i in range(0,len(text),1550)]; con.executemany("INSERT INTO chunks VALUES(?,?,?)",[(str(path),i,p) for i,p in enumerate(parts)]); con.execute("INSERT OR REPLACE INTO files VALUES(?,?,?)",(str(path),digest,path.stat().st_mtime)); count+=1
    con.commit(); con.close(); return {"indexed":count,"unchanged":unchanged,"skipped":skipped}
def retrieve(query,limit=5):
    con=db(); terms=re.findall(r"[\w\u0590-\u05ff]+",query.lower())[:12]
    if not terms: return {"query":query,"results":[]}
    rows=con.execute("SELECT path,ordinal,text,bm25(chunks) score FROM chunks WHERE chunks MATCH ? ORDER BY score LIMIT ?",(" OR ".join('"'+t+'"' for t in terms),limit)).fetchall(); con.close(); return {"query":query,"results":[{"path":r[0],"ordinal":r[1],"text":r[2],"score":r[3]} for r in rows]}
def cache_key(payload): return hashlib.sha256(payload.encode()).hexdigest()
def cache_get(payload):
    path=ROOT/"cache"/(cache_key(payload)+".json")
    if not path.exists(): return {"hit":False}
    record=json.loads(path.read_text(encoding="utf-8-sig")); age=(datetime.now(timezone.utc)-datetime.fromisoformat(record["created_at"])).total_seconds(); return {"hit":age<=record["ttl"],"value":record.get("value"),"age_seconds":age}
def cache_put(payload,value,ttl=604800):
    path=ROOT/"cache"/(cache_key(payload)+".json"); write(path,{"created_at":now(),"ttl":ttl,"value":value,"source_hash":cache_key(payload)}); return {"stored":True,"sha256":cache_key(payload)}
def ledger(**record): append(ROOT/"logs"/"resource_ledger.jsonl",{"timestamp":now(),**record})
def health():
    required=["MODEL_REGISTRY.json","ROUTING_POLICY.json","QUALITY_THRESHOLDS.json","GOLD_SET.json","MACHINE_PROFILE.json","WORKLOAD_PROFILE.json"]; checks=[{"name":n,"ok":(ROOT/"config"/n).exists()} for n in required]
    registry=load("MODEL_REGISTRY.json",{"models":{},"runtimes":{}})
    for mid,m in registry.get("models",{}).items(): checks.append({"name":"model:"+mid,"ok":not m.get("local_path") or Path(m["local_path"]).exists()})
    for folder in [ROOT/"data",ROOT/"cache",ROOT/"logs"]:
        try: folder.mkdir(parents=True,exist_ok=True); probe=folder/".probe"; probe.write_text("ok"); probe.unlink(); ok=True
        except OSError: ok=False
        checks.append({"name":"writable:"+folder.name,"ok":ok})
    return {"status":"healthy" if all(x["ok"] for x in checks) else "degraded","checks":checks,"timestamp":now(),"external_ports":[]}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--root"); sub=p.add_subparsers(dest="command",required=True); sub.add_parser("health"); q=sub.add_parser("privacy"); q.add_argument("text"); q=sub.add_parser("route"); q.add_argument("task_type"); q.add_argument("--risk",default="medium"); q.add_argument("--privacy",default="internal"); q=sub.add_parser("index"); q.add_argument("source"); q=sub.add_parser("retrieve"); q.add_argument("query"); q.add_argument("--limit",type=int,default=5)
    a=p.parse_args(); set_root(a.root)
    result=health() if a.command=="health" else privacy_scan(a.text) if a.command=="privacy" else route(a.task_type,a.risk,a.privacy) if a.command=="route" else index(a.source) if a.command=="index" else retrieve(a.query,a.limit)
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result.get("status")!="degraded" else 1
if __name__=="__main__": raise SystemExit(main())
