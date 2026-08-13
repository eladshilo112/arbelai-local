<div dir="rtl" style="font-family: David; text-align: right;">

# דוח בדיקות מוצר

| תחום | תוצאה |
|---|---|
| Dry Run מקוון בנתיב עברי | עבר |
| גילוי Windows, CPU, RAM, GPU, אחסון וכלים | עבר |
| Metadata רשמי, רישיון, גרסה ו־SHA256 | עבר |
| Memory Fit לפני הורדה | עבר |
| הורדה ללא אישור | נחסמה כנדרש |
| חיבור Codex ו־Claude ללא אישור | נחסם כנדרש |
| Resume ו־Checkpoints | עבר |
| Backup עם SHA256 ו־Rollback | עבר |
| Config Conflict לאחר התקנה | נשמר ולא נדרס |
| Offline Mode | עבר |
| Safe Low RAM או Low Disk Fallback | עבר בבדיקת הזרקה |
| Update Check Only | עבר, ללא התקנה |
| Improvement Watcher | עבר Offline, Mock מקוון וסריקת Metadata רשמית, ללא הורדה או התקנה אוטומטית |
| ARBELAI Benchmark | איכות 0.90, יציבות 1.00, TTFT 0.902 שניות, 6.407 טוקנים לשנייה |
| macOS ו־Linux | בדיקות תחביר ותכנון בלבד, נדרשת בדיקת יעד |

49 בדיקות אוטומטיות עברו. בדיקת Symlink אחת של מערכת הקבצים דולגה עקב הרשאות מערכת והוגדרה כבדיקת יעד מחייבת. בדיקת Symlink בתוך ארכיון עברה. Metadata רשמי אמיתי נאסף בהסכמה חד פעמית מ־11 מקורות Registry: 13 מועמדים, שישה בהמתנת אישור, שבעה שנדחו ואפס כשלי מקור. לא הורד ולא הותקן רכיב. מקור DirectML הישן החזיר 404 ותוקן למסלול Metadata רשמי של NuGet. מסנן מערכת ההפעלה תוקן ונבדק כך שנכס Darwin אינו מסווג עוד כ־Windows.

</div>
