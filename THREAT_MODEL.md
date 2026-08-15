# מודל איומים

## נכסים מוגנים

1. קובצי המשתמש וה Repository.

2. Secrets והרשאות ספקים.

3. תעבורת Codex, Claude ו ChatGPT.

4. תקינות Policy ו Audit.

5. תקציב כספי ומשאבי חומרה.

## איומים מרכזיים

| איום | הגנה בגרסה 0.1 |
|---|---|
| Prompt Injection מתוך Repository | תוכן מסומן `PROJECT_UNTRUSTED` ואינו משפיע על Policy |
| Path Traversal | אימות Root ונתיב Canonical |
| קריאת Secrets | שמות קבצים רגישים מוחרגים וסביבת Observe אינה קוראת תוכן |
| זליגת Prompt ל Ledger | נשמר Hash בלבד |
| שינוי Proxy או Base URL | מזוהה כ Elevated ואינו מבוצע |
| Audit Tampering | שרשרת Hash ניתנת לאימות |
| Context Exhaustion | מגבלת קבצים, בתים וטוקנים |
| Supply Chain | אין תלויות Runtime חיצוניות בגרסה 0.1 |
| Semantic Cache Poisoning | Semantic Cache כבוי |
| Ambient Authority | אין Executor בגרסה 0.1 |

## הנחות

ה Kernel אינו מגן מפני משתמש מקומי שכבר שולט בחשבון ובקבצים. הוא גם אינו Sandbox. Adapter עתידי חייב לקבל בידוד מערכת הפעלה והרשאות זמניות.

## דרישות לפני Managed Execution

1. Ephemeral Runner.

2. Environment Allowlist.

3. Canonical Path Validation לפני ואחרי פתיחת קובץ.

4. Snapshot ו Diff לפני Commit.

5. Resource Lease.

6. Egress Allowlist.

7. בדיקות TOCTOU, Junction ו Symlink בכל מערכת נתמכת.