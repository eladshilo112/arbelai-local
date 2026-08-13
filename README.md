<div dir="rtl" style="font-family: David; text-align: right;">

# ARBELAI Local

ARBELAI Local הוא מתקין ומנוע ניתוב מקומי, מאובטח ורב־מערכתי לעומסי AI. הוא מגלה את החומרה ואת צורכי המשתמש לפני בחירת Runtime או מודל, בודק התאמת זיכרון, מבצע Benchmark בעברית ובאנגלית, ומחבר כלים תואמי MCP דרך stdio כאשר המשתמש מאשר זאת.

## עקרונות

* Local First וללא Telemetry כברירת מחדל.
* אין מודלים גדולים, Runtime או Secrets במאגר או בחבילת Release.
* אין הורדה, חיבור כלי, שינוי תצורה או קידום Canary ללא אישור מפורש.
* אין פתיחת פורט חיצוני, שינוי Firewall, Driver או BIOS.
* מקור רשמי, רישיון, גרסה, גודל ו־SHA256 נבדקים לפני הורדה.
* CVE או רישיון במצב Unknown חוסמים קידום.

## הפעלה ב־Windows

הורידו את קובץ ה־ZIP מעמוד Releases, אמתו SHA256, חלצו ולחצו פעמיים על `הפעלת ARBELAI.cmd`.

## בדיקה למפתחים

```text
python -m unittest discover -s tests -v
python release_gate.py --root .
```

Windows הוא היעד שנבדק בפועל. macOS ו־Linux נמצאים ברמת Designed עם בדיקות תחביר ומבנה, עד להרצת בדיקות יעד אמיתיות.

## רישיון ופרטיות

הקוד מופץ ברישיון Apache 2.0. מדיניות הפרטיות נמצאת ב־`docs/PRIVACY_POLICY_DRAFT.md`. המוצר אינו שולח תוכן משתמש או מזהה חומרה ייחודי לצורך Telemetry.

## אבטחה

אין לפתוח Issue ציבורי עם חולשה שטרם תוקנה. הוראות דיווח נמצאות ב־`SECURITY.md`.

</div>

## English

ARBELAI Local is a privacy-first, cross-platform installer and routing engine for local AI workloads. It discovers hardware and workload requirements before selecting any runtime or model, performs memory-fit checks and bilingual benchmarks, and connects compatible tools through MCP stdio only after explicit approval.

The code is licensed under Apache License 2.0. Windows is verified. macOS and Linux are currently designed and syntax-tested, not claimed as verified.
