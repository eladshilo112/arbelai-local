# ARBELAI Reflex Protocol 0.1

## מטרה

הפרוטוקול מפריד בין כוונה, הרשאה, Context, תועלת ותוצאה. הפרדה זו מונעת ממודל או מתוכן עוין להעניק לעצמם הרשאות.

## אובייקטים

### Intent Contract

שומר את בקשת המשתמש, Scope וקריטריוני הקבלה. הבקשה המקורית מוגנת באמצעות SHA 256.

### Policy Decision

נוצר רק על ידי Kernel דטרמיניסטי. הוא קובע Mode, סיכון, פרטיות, רשת ותקציב.

### Capability Grant

הרשאה קצרת חיים לפעולה אחת או לקבוצת פעולות מוגדרת. Grant אינו יכול להיות מורחב על ידי Executor.

### Evidence Manifest

רשימת ראיות עם מקור, Hash, סיבה ועלות Context. תוכן Repository מסומן כלא מהימן.

### Benefit Certificate

הוכחה גרסאית שמסלול מסוים עבר Gold Set על חומרה ותצורה מוגדרות. שינוי מודל, Runtime, Quantization, Driver או Hardware מבטל את ההסמכה.

### Evidence Receipt

קבלה הכוללת Route, גרסאות, שימוש, בדיקות, שינויים ותוצאת קבלה.

## כללי תאימות

1. אין לאפשר לשדה שמקורו במודל לשנות Policy או Capability Grant.

2. אין לשמור Prompt או Excerpt ב Ledger כברירת מחדל.

3. אין להציג Token Estimate כמדידת ספק.

4. אין להבטיח Rollback לפעולה בלתי הפיכה.

5. Adapter חייב לפעול מחוץ לתהליך הליבה.

6. כשל ב Kernel אינו משנה את מסלול הרשת של לקוח רשמי.

7. הרחבות לא מוכרות אינן מקבלות Ambient Authority.