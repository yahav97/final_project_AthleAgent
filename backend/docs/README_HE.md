# AthleAgent Backend Docs (HE)

מטרת הסט הזה: לתת תמונה מלאה ומדויקת על הבקאנד, בלי עומס מסמכים.

## מה קוראים ובאיזה סדר

1. `ONBOARDING_BACKEND_ML_HE.md`  
   מסמך היכרות מלא עם הארכיטקטורה, זרימת הנתונים, שכבת ה-ML, endpoints ונהלי עבודה.
2. `PROTOTYPE_PRESENTATION_PREP_HE.md`  
   מסמך הכנה להצגת פרוטוטייפ (תסריט, מסרים, Q&A, checklist).
3. `FRONTEND_BACKEND_SYNC_MEETING_HE.md`  
   מסמך פגישת תיאום עם השותף בפרונט (חלוקת אחריות, החלטות, DoD ובדיקות).
4. `DATA_CONTRACT_FRONTEND_BACKEND.md`  
   חוזה נתונים פורמלי (EN) בין Firestore/Frontend לבין ה-Backend לחיזוי.

## מה לא צריך יותר

- המסמכים הישנים תחת `docs/` ברמת הפרויקט שאיחדו אליהם תוכן, הוחלפו בסט מרוכז זה.
- אם צריך להוסיף מסמך חדש, קודם בודקים שהמידע לא מתאים לאחד משלושת המסמכים הקיימים.

## כללי עדכון

- כל שינוי ב-API חיזוי (`/predict`, `/predict/daily`) מחייב עדכון ב-`DATA_CONTRACT_FRONTEND_BACKEND.md`.
- כל שינוי תפעולי/ארכיטקטוני בבקאנד או ב-ML מחייב עדכון ב-`ONBOARDING_BACKEND_ML_HE.md`.
- כל שינוי בתהליך הדמו מחייב עדכון ב-`PROTOTYPE_PRESENTATION_PREP_HE.md`.
- כל שינוי החלטות אינטגרציה מול הפרונט מחייב עדכון ב-`FRONTEND_BACKEND_SYNC_MEETING_HE.md`.
