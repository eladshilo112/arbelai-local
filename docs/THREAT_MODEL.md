<div dir="rtl" style="font-family: David; text-align: right;">

# מודל איומים לפי STRIDE

| רכיב | איום | בקרה | בדיקה |
|---|---|---|---|
| מתקין | התחזות למקור | Allowlist, HTTPS, מקור רשמי, SHA256 | Metadata זדוני ומקור חסום |
| Updater | Spoofing ו־Tampering | בדיקה בלבד ללא חתימה, Stable בלבד | Manifest לא מהימן |
| ארכיון | Zip Slip, Symlink ופצצת דחיסה | Path Validation, דחיית Symlink, מגבלת 10,000 פריטים ו־20GB לאחר חילוץ | ארכיון זדוני |
| MCP | Tool Poisoning | שמות כלים קבועים, stdio, ללא קוד מרוחק | בקשת כלי לא ידוע |
| Retrieval | Prompt Injection | תוכן מסומן כמידע לא מהימן | הוראה זדונית במסמך |
| Privacy Gate | Information Disclosure | סריקה, Redaction, Restricted מקומי בלבד | סוד מדומה ופרטי זיהוי |
| Cache ולוגים | חשיפת מידע | אין Telemetry, Redaction, שמירה מקומית | סריקת Secrets בחבילה ובדוחות |
| תצורה | Tampering | Backup, SHA256, כתיבה אטומית, זיהוי Conflict | שינוי לאחר התקנה |
| תהליך מודל | Denial of Service | Timeout, Lock, מודל יחיד, סגירה מובטחת | Crash והפסקה |
| הרשאות | Elevation of Privilege | התקנת משתמש, ללא shell מרוחק | הרצה ללא הרשאת מנהל |
| מודל | Repudiation ואיכות | Manifest, Benchmark ו־Resource Ledger | Gold Set קבוע |
| Supply Chain | רכיב פגום | SBOM, רישיון, CVE Gate ו־Revocation | Hash mismatch |

סיכונים שיוריים כוללים תלות באבטחת מערכת ההפעלה, Python שמותקן במחשב, ספקי Runtime ומודל, ועדכוני דרייבר שהמוצר אינו מנהל.

## RC6, Improvement Watcher ו־Scheduler

| רכיב | איום | בקרה |
|---|---|---|
| Source Registry | מקור קהילתי או התחזות | Official בלבד, HTTPS ו־Host Allowlist |
| Metadata | שדות זדוניים או חסרים | Schema מצומצם, מגבלת 5MB, אין הרצת תוכן, Hash ו־Size חובה |
| CVE ו־License | מידע חסר | Unknown חוסם מעבר Security ו־Promotion |
| Canary | שינוי Production | תיקייה מבודדת, אישור ייחודי, Resume, Hash, Size ו־Zip Slip |
| Comparator | קידום Regression | אותו Gold Set, פרטיות, איכות, יציבות, מהירות ו־RAM |
| Promotion | Downgrade או השחתה | אישור מפורש, כתיבה אטומית, Backup ו־Last Known Good |
| Revocation | שחזור רכיב פגיע | רשימת שלילה חוסמת הורדה, קידום ושחזור |
| Scheduler | Persistence ללא ידיעה | Opt In, משתמש בלבד, Least Privilege, Pause, Disable ו־Remove |
| סיווג נכס | התאמת Runtime של מערכת אחרת | סמני OS מפורשים ובדיקת נכס Darwin מול Windows |
| Release Attestation | זיוף מעבר שער חיצוני | אין דגלי עקיפה, נדרשים קובצי ראיה עם SHA256 |

</div>
