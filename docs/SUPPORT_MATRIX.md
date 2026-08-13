<div dir="rtl" style="font-family: David; text-align: right;">

# מטריצת תאימות

| מערכת | ארכיטקטורה | דירוג | מה נבדק |
|---|---|---|---|
| Windows 11 | x64 | Verified | Dry Run, גילוי, נתיב עברי, Resume, Rollback, פרטיות, MCP ואריזת ZIP במחשב הנוכחי |
| Windows 10 | x64 | Designed | קוד נתמך, נדרשת בדיקת יעד מלאה |
| macOS | Apple Silicon | Designed | תחביר Python ו־Shell בלבד, נדרשת בדיקת יעד ו־Metal |
| macOS | Intel | Designed | מסלול CPU תוכנן, נדרשת בדיקת יעד |
| Linux | x64 | Designed | תחביר Python ו־Shell בלבד, נדרשת בדיקת יעד והפצה ספציפית |
| Linux | arm64 | Designed | גילוי תוכנן, Runtime ומודל דורשים בדיקת יעד |

דרישת מינימום למסלול Local Inference היא Python 3.10, לפחות 8GB RAM ולפחות 12GB פנויים. מומלץ 16GB RAM ו־25GB פנויים. בפחות מכך המוצר עובר ל־Context Only או Cloud Only בטוח ואינו מוריד מודל.

מצבים לא נתמכים כוללים Python ישן, מערכת ללא TLS תקין, אחסון לא כתיב, ארכיטקטורה ללא נכס Runtime רשמי, או מדיניות ארגונית שחוסמת את המקורות. Proxy ארגוני נתמך רק אם Python ומערכת ההפעלה סומכים על תעודת הארגון.

</div>
