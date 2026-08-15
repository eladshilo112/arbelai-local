# Migration מ ARBELAI Local הישן

## מטרת השינוי

הגרסה הישנה שילבה Installer, Hardware Discovery, Update Watcher, MCP ומנוע מודלים מקומי. הגרסה החדשה מצמצמת את בסיס האמון ומפרידה בין Protocol, Kernel ו Adapters.

## מה אינו עובר אוטומטית

1. אין הפעלת `portable.py`.

2. אין העתקת `engine/mcp_server.py`.

3. אין Scheduled Improvement Watcher.

4. אין הפעלת llama.cpp או Port מקומי.

5. אין העתקת Model Registry או Routing Policy ישנים.

6. אין שינוי בהגדרות Codex, Claude או ChatGPT.

## נתונים שניתן לייבא בעתיד

רק Gold Set ותוצאות Benchmark שעברו אימות מחדש מול Protocol 0.1 יוכלו להפוך ל Benefit Certificates. אין אמון אוטומטי בתוצאות או במדיניות ישנות.

## Rollback

הענף `main` הישן נשמר ללא שינוי במהלך ביקורת `reflex-v0.1`. מיזוג יתבצע רק לאחר CI, Code Review ואישור מפורש.