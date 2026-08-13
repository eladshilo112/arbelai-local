<div dir="rtl" style="font-family: David; text-align: right;">

# מדיניות עדכון ושיפור

ערוץ ברירת המחדל הוא Stable. ללא Code Signing, מנגנון העדכון רשאי לבדוק Metadata ולהציע גרסה בלבד. אין התקנה אוטומטית.

Improvement Watcher כבוי עד Opt In. לאחר הסכמה הוא בודק פעם בשבוע Metadata רשמי בלבד. מועמד עובר רישיון, CVE, התאמת חומרה, Memory Fit, Canary Sandbox, אותו Gold Set והשוואת Regression. קידום דורש שיפור מדיד, היעדר Regression, Backup, Rollback ואישור משתמש.

אין Fine Tuning אוטומטי. אין שינוי Driver, BIOS, Firewall או הגדרות אבטחה. רכיב שנשלל נכנס לרשימת Revocation ולא יקודם או יורד בגרסה.

RC6 מנהל מצבים: discovered, rejected, awaiting_user_approval, canary_downloaded, security_passed, benchmark_passed, promoted, rolled_back ו־revoked. CVE או License במצב Unknown חוסמים Security Passed וקידום. Memory Fit שומר לפחות 25% RAM למערכת. קידום דורש ללא Regression באיכות, יציבות ופרטיות, וכן שיפור מדיד שמצדיק משאבים.

מניעת Downgrade משווה לגרסת Production. Revocation נבדק מחדש לפני כל פעולה. Last Known Good נשמר עד מעבר תקופת יציבות ויכול לשמש Rollback רק אם אינו ברשימת שלילה. קובץ SHA256 של חבילת Release נדרש ונבדק בפועל.

</div>
