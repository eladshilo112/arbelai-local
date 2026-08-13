<div dir="rtl" style="font-family: David; text-align: right;">

# דוח בדיקות אבטחה

## תוצאה

לא נמצאו חולשות קריטיות או גבוהות בבדיקות שבוצעו. אין בכך טענה שאין חולשות. שער השחרור חוסם כל ממצא Critical או High פתוח.

## בדיקות שעברו

עברו קומפילציית Python ו־48 בדיקות Unit, Integration ו־Failure Injection. נוספו Online Metadata מדומה, Deduplication ו־Cooldown, Source Timeout, Rate Limit, Metadata זדוני, CVE Unknown, License Unknown, Low RAM, Low Disk, Hash ו־Size Mismatch, Partial Download, ארכיון זדוני, Symlink בתוך ארכיון, מניעת Downgrade, Benchmark שעובר ו־Regression שנחסם, Promotion, Rollback, Revocation ו־Schedule Idempotency. יתר בדיקות הפרטיות, MCP, Zip Slip, Resume, Config Conflict ו־Dependency Lock נשמרו.

Windows Defender היה פעיל עם Real Time Protection וחתימות גרסה 1.457.130.0, והסריקה המותאמת הסתיימה בהצלחה. Static Analysis לא מצא Shell Execution מסוכן. חבילת המקור מבוססת Python Standard Library בלבד ואינה כוללת בינארים, מודלים או חבילות Python צד שלישי.

בדיקת Symlink של מערכת הקבצים דולגה בסביבת הבדיקה משום שהרשאת יצירת Symlink אינה זמינה למשתמש. לעומתה, בדיקת Symlink זדוני בתוך ZIP עברה ונחסמה. Junction Abuse מחייב בדיקת יעד נוספת עם הרשאות מתאימות.

Windows Task Scheduler נבדק בפועל: Create, שתי שאילתות, Disable, Remove ושאילתת היעדרות סופית. לא נשאר Task בדיקה.

סריקת Metadata מקוונת אמיתית ובהסכמה חד פעמית החזירה 13 מועמדים מ־11 מקורות רשמיים, ללא כשל מקור. שישה הועברו להמתנת אישור ושבעה נדחו. לא בוצעו הורדה או התקנה. לאחר תיקון סיווג מערכת ההפעלה, לא נמצא אף נכס Darwin ברשימת הנכסים התואמים ל־Windows.

## סיכונים שיוריים

אין Code Signing, ולכן אין התקנת עדכון אוטומטית וייתכן SmartScreen. macOS ו־Linux לא נבדקו על מכשיר. תוכנית Claude ממתינה למכסה. בדיקת CVE לרכיבי יעד מתבצעת לפני קידום בפועל, משום שאין רכיבי צד שלישי בחבילת ה־ZIP עצמה.

</div>
