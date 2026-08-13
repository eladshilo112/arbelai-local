#!/usr/bin/env python3
import argparse,json
from pathlib import Path
def gb(value):return f"{int(value or 0)/1024**3:.2f} GB"
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);a=p.parse_args();root=Path(a.root);path=root/"reports"/"IMPROVEMENT_REPORT.json"
    if not path.exists():print("טרם בוצעה בדיקת שיפורים. אפשר לבחור Run Now לאחר Opt In.");return 1
    report=json.loads(path.read_text(encoding="utf-8-sig"));print("ARBELAI, דוח שיפורים בטוח\n")
    for item in report.get("candidates",[]):
        source=item.get("source",{});asset=(source.get("assets") or [{}])[0];risk="נמוך" if item.get("license_gate",{}).get("promotion_allowed") and item.get("cve_gate",{}).get("promotion_allowed") else "דורש בדיקה"
        print(f"מקור: {source.get('source_id')}  גרסה: {source.get('version')}  מצב: {item.get('state')}")
        print(f"גודל: {gb(asset.get('size'))}  רישיון: {source.get('license')}  סיכון: {risk}")
        print("סיבה: "+", ".join(item.get("reasons",[])))
        regression=item.get("regression")
        if regression:print(f"שיפור מהירות: {regression.get('speed_delta_percent',0):.1f}%  שינוי RAM: {regression.get('ram_delta_percent',0):.1f}%")
        print("פעולה מומלצת: "+("בחינה ואישור Canary" if item.get("state")=="awaiting_user_approval" else "אין פעולה אוטומטית")+"\n")
    print("לא מתבצעת הורדה, התקנה, החלפת Driver או קידום ללא אישור מפורש.");return 0
if __name__=="__main__":raise SystemExit(main())
