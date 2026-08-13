#!/usr/bin/env python3
"""Explicit opt-in, user-scoped schedule manager for the metadata-only watcher."""
from __future__ import annotations
import argparse,html,json,os,platform,shlex,subprocess,sys,tempfile
from pathlib import Path
NAME="ARBELAI-Improvement-Watcher"
def run(command):
    cp=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30);return {"ok":cp.returncode==0,"code":cp.returncode,"output":((cp.stdout or "")+(cp.stderr or ""))[-3000:]}
def watcher_command(root):return [sys.executable,str(root/"engine"/"improvement_watcher.py"),"scan","--root",str(root)]
def require(value,expected):
    if value!=expected:raise SystemExit("explicit_schedule_approval_required")
def windows(action,root,approval):
    task=NAME
    if action=="enable":
        require(approval,"APPROVE-WEEKLY-METADATA-CHECK");parts=watcher_command(root);command=html.escape(parts[0]);arguments=html.escape(subprocess.list2cmdline(parts[1:]));xml=f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><RegistrationInfo><Description>ARBELAI weekly official metadata check, user opt in</Description></RegistrationInfo><Triggers><CalendarTrigger><StartBoundary>2026-01-05T10:00:00</StartBoundary><Enabled>true</Enabled><ScheduleByWeek><DaysOfWeek><Monday/></DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek></CalendarTrigger></Triggers><Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals><Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>false</StartWhenAvailable><RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable><Enabled>true</Enabled><Hidden>false</Hidden><ExecutionTimeLimit>PT15M</ExecutionTimeLimit><Priority>7</Priority></Settings><Actions Context="Author"><Exec><Command>{command}</Command><Arguments>{arguments}</Arguments></Exec></Actions></Task>'''
        handle=tempfile.NamedTemporaryFile(prefix="arbelai-task-",suffix=".xml",delete=False);path=Path(handle.name);handle.close()
        try:path.write_text(xml,encoding="utf-16");return run(["schtasks","/Create","/TN",task,"/XML",str(path),"/F"])
        finally:path.unlink(missing_ok=True)
    if action=="pause":return run(["schtasks","/Change","/TN",task,"/DISABLE"])
    if action=="run-now":return run(["schtasks","/Run","/TN",task])
    if action=="disable":return run(["schtasks","/Change","/TN",task,"/DISABLE"])
    if action=="remove":require(approval,"APPROVE-REMOVE-SCHEDULE");return run(["schtasks","/Delete","/TN",task,"/F"])
    return run(["schtasks","/Query","/TN",task,"/FO","LIST"])
def mac(action,root,approval):
    path=Path.home()/"Library"/"LaunchAgents"/"local.arbelai.improvement.plist";label="local.arbelai.improvement"
    if action=="enable":
        require(approval,"APPROVE-WEEKLY-METADATA-CHECK");args="".join(f"<string>{str(x).replace('&','&amp;')}</string>" for x in watcher_command(root));content=f'<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict><key>Label</key><string>{label}</string><key>ProgramArguments</key><array>{args}</array><key>StartCalendarInterval</key><dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>10</integer></dict><key>RunAtLoad</key><false/></dict></plist>';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding="utf-8");return run(["launchctl","bootstrap",f"gui/{os.getuid()}",str(path)])
    if action in {"pause","disable"}:return run(["launchctl","bootout",f"gui/{os.getuid()}",str(path)])
    if action=="run-now":return run(["launchctl","kickstart",f"gui/{os.getuid()}/{label}"])
    if action=="remove":require(approval,"APPROVE-REMOVE-SCHEDULE");result=run(["launchctl","bootout",f"gui/{os.getuid()}",str(path)]);path.unlink(missing_ok=True);return result
    return {"ok":path.exists(),"path":str(path)}
def linux(action,root,approval):
    directory=Path.home()/".config"/"systemd"/"user";service=directory/"arbelai-improvement.service";timer=directory/"arbelai-improvement.timer"
    if action=="enable":
        require(approval,"APPROVE-WEEKLY-METADATA-CHECK");directory.mkdir(parents=True,exist_ok=True);service.write_text("[Unit]\nDescription=ARBELAI metadata watcher\n[Service]\nType=oneshot\nExecStart="+" ".join(shlex.quote(x) for x in watcher_command(root))+"\n",encoding="utf-8");timer.write_text("[Unit]\nDescription=Weekly ARBELAI metadata check\n[Timer]\nOnCalendar=Mon *-*-* 10:00:00\nPersistent=false\n[Install]\nWantedBy=timers.target\n",encoding="utf-8");run(["systemctl","--user","daemon-reload"]);return run(["systemctl","--user","enable","--now",timer.name])
    if action in {"pause","disable"}:return run(["systemctl","--user","disable","--now",timer.name])
    if action=="run-now":return run(["systemctl","--user","start",service.name])
    if action=="remove":require(approval,"APPROVE-REMOVE-SCHEDULE");run(["systemctl","--user","disable","--now",timer.name]);service.unlink(missing_ok=True);timer.unlink(missing_ok=True);run(["systemctl","--user","daemon-reload"]);return {"ok":True,"removed":True}
    return run(["systemctl","--user","status",timer.name])
def main():
    p=argparse.ArgumentParser();p.add_argument("action",choices=["enable","pause","run-now","disable","remove","status"]);p.add_argument("--root",required=True);p.add_argument("--approval");a=p.parse_args();root=Path(a.root).resolve();system=platform.system();result=windows(a.action,root,a.approval) if system=="Windows" else mac(a.action,root,a.approval) if system=="Darwin" else linux(a.action,root,a.approval);print(json.dumps({"os":system,"action":a.action,"user_scoped":True,"result":result},ensure_ascii=False,indent=2));return 0 if result.get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
