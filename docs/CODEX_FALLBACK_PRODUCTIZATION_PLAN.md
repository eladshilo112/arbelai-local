<div dir="rtl" style="font-family: David; text-align: right;">

# תוכנית Productization חלופית של Codex

מסמך זה אינו תוכנית Claude ואינו סוגר את שער Claude. הוא שימש להמשך עבודה בטוחה בזמן שמכסת Claude Code חסומה.

## סדר העבודה

1. לנקות את ה־Payload מנתיבים אישיים, מידע עסקי, Secrets, מודלים, Runtime, Cache, לוגים וגיבויים.
2. להפריד בין חבילת הפצה קלה לבין התקנת יעד דינמית.
3. לבצע Discovery, Compatibility ו־Workload לפני Metadata ולפני הורדה.
4. לבחור Runtime Variant ומודל רק מתוך מקורות רשמיים, לפי האצה, Memory Fit, רישיון ו־SHA256.
5. להתקין בהיקף משתמש, לבקש אישור לכל הורדה ולכל שינוי תצורה, ולשמור Backup ו־Rollback.
6. להריץ Gold Set אחיד, לקדם Local Preferred לפי קטגוריה בלבד ולהשאיר משימות קריטיות לענן חזק עם אימות.
7. לחבר Codex ו־Claude Code ב־stdio בלבד, אם נמצאו ולאחר גיבוי.
8. להפעיל Threat Model, בדיקות כשל, פרטיות, Release Scan, SBOM, Dependency Lock ו־Defender.
9. לאפשר Improvement Watcher בהסכמה בלבד, Metadata בלבד, Canary ו־Regression לפני קידום.
10. לחסום Release על סיכון גבוה או קריטי, על בדיקת חובה שנכשלה, או על שער Claude שלא עבר.

</div>
