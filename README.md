# ARBELAI Reflex

> שכבת Reflex פתוחה, מקומית ומבוססת ראיות לשיפור משימות AI בלי Proxy, בלי שירות רקע ובלי שינוי הגדרות גלובליות.

[English summary](#english-summary)

## למה הפרויקט קיים

מערכות תזמור AI רבות מוסיפות Router, Proxy, מספר מודלים ושירותי רקע לכל בקשה. לעיתים עלות התזמור גבוהה מהחיסכון, והמערכת הופכת לנקודת כשל שמשפיעה על לקוחות רשמיים.

ARBELAI Reflex פועל לפי עיקרון הפוך:

```text
Evidence Before Intervention
Tools Before Models
One Executor By Default
Every Result Carries Evidence
```

ברירת המחדל היא `BYPASS`. המערכת מתערבת רק כאשר קיימת הצדקה מפורשת או Benefit Certificate תקף.

## מצב גרסה 0.1

גרסה זו היא Reference Kernel בטוח ומוגבל. היא כוללת:

1. Intent Contract עם Hash לבקשה המקורית.

2. Policy Decision דטרמיניסטי.

3. Context Manifest מוגבל בתקציב ומסומן לפי מקור.

4. Capability Grant זמני וללא רשת.

5. SQLite Ledger עם שרשרת Hash.

6. Evidence Receipt לכל הכנה.

7. CLI במצב Observe או Advisor.

8. בדיקות להגנת Secrets, Path Traversal, הרשאות ותקציב Context.

הגרסה אינה מפעילה מודלים, אינה מתקשרת לספק ענן ואינה משנה את Codex, Claude או ChatGPT.

## דרישות

Node.js 24 ומעלה. אין חבילות צד שלישי ואין צורך ב `npm install`.

## התחלה

```powershell
node .\bin\arbel.js init C:\path\to\project
node .\bin\arbel.js prepare --workspace C:\path\to\project --task "בדוק את הפרויקט"
node .\bin\arbel.js status --workspace C:\path\to\project
node .\bin\arbel.js doctor --workspace C:\path\to\project
```

ברירת המחדל היא `observe-local`. במצב זה נאסף Metadata בלבד, ללא תוכן קבצים.

כדי לאפשר Context ממוקד יש לשנות במפורש את `mode` בקובץ `.arbel/policy.json` ל `advisor`, ולאחר מכן:

```powershell
node .\bin\arbel.js prepare --workspace C:\path\to\project --task "אתר את קוד האימות" --include-content
```

גם במצב זה ARBELAI אינו מבצע שינוי.

## התחייבויות אי התערבות

ה Kernel אינו:

1. משנה `OPENAI_BASE_URL`.

2. משנה Proxy של מערכת ההפעלה.

3. פותח Port.

4. מתקין Service או Scheduled Task.

5. משנה Registry, Firewall או Hosts.

6. יורש או שומר Secrets לצורך Ledger.

7. שולח Telemetry.

8. מוריד מודלים או Runtimes.

9. משנה קובצי Codex או Claude.

## ארכיטקטורה

```text
User or Agent
      ↓
Intent Contract
      ↓
Policy Kernel
      ↓
Context Compiler
      ↓
Executor Adapter, future and opt in
      ↓
Verifier
      ↓
Evidence Receipt
```

ראו [ARCHITECTURE.md](ARCHITECTURE.md), [THREAT_MODEL.md](THREAT_MODEL.md) ו [PRIVACY.md](PRIVACY.md).

## בדיקות

```powershell
cmd /c npm test
cmd /c npm run check
```

## רישיון

הקוד וה Schemas מופצים תחת Apache License 2.0. תרומות מתקבלות באמצעות DCO.

## English summary

ARBELAI Reflex is an evidence first, opt in task preparation kernel for AI coding and knowledge workflows. It does not proxy provider traffic, open ports, run a daemon, modify global configuration, call a model, or send telemetry. Version 0.1 implements typed task contracts, deterministic policy decisions, bounded context manifests, a privacy preserving hash chained ledger, and evidence receipts using only Node.js built in modules.