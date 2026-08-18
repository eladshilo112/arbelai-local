# ארכיטקטורה

## מטרת המערכת

ARBELAI Reflex נועד לצמצם טוקנים, ניסיונות חוזרים ועבודה ידנית בלי להכניס מתווך למסלול הרשת של לקוחות רשמיים.

## גבולות אמון

```text
Trusted
User Approval
Static Policy
Deterministic Kernel

Untrusted
Repository Content
Web Content
Model Output
MCP Output
Executor Suggestions
```

תוכן לא מהימן יכול להציע Context או פעולה. הוא אינו יכול לשנות Policy, Scope או Capability Grant.

## רכיבי הליבה

### Intent Contract

שומר את הבקשה המקורית ואת ה Hash שלה. כל עיבוד מאוחר יותר ניתן להשוואה למקור.

### Policy Kernel

קוד דטרמיניסטי ללא מודל, רשת או Shell. הוא קובע סיכון, פרטיות, Mode ותקציב.

### Context Compiler

מתחיל מ Metadata. תוכן נקרא רק ב Mode מתאים ובהוראה מפורשת. כל ראיה מקבלת מקור, Hash וסיבה. קיימות מגבלות על מספר קבצים, מספר בתים ותקציב טוקנים מוערך.

### Ledger

SQLite מקומי במצב WAL. הוא אינו שומר Prompt מקורי או Excerpts. הוא שומר Hashes, Metadata ורצף Audit עם Hash מקושר.

### Adapter Boundary

Adapters עתידיים ירוצו מחוץ לתהליך דרך JSON RPC או MCP `stdio`. הצהרת Capability של Adapter אינה הרשאה. הרשאה נוצרת רק על ידי Kernel ולזמן מוגבל.

## מצבים

| מצב | משמעות |
|---|---|
| `off` | אין פעולה |
| `observe-local` | Metadata מקומי בלבד |
| `advisor` | Context ממוקד ללא Side Effects |
| `managed-read` | מיועד בעתיד למבצע בעל הרשאות קריאה |
| `managed-write` | מיועד בעתיד לפעולה עם Grant מפורש |

## Fail Safe

כשל בליבה אינו משנה את מסלול Codex או ChatGPT. כשל במדיניות, ב Audit או בפרטיות חוסם Side Effect. כשל ב Cache גורם לחישוב מחדש.