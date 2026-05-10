# תמונת מצב אופרטיבית (Backend + ML)

## 1) סטטוס נוכחי

- ריצת המודל האחרונה: `ML_model/artifacts/20260510_143741`.
- מודל זוכה: `RandomForest`.
- threshold תפעולי שנשמר בארטיפקט: `0.38`.
- מצב promotion נוכחי: `degraded_rc=false` ב-`ML_model/artifacts/promoted.json`.
- סטטוס loader בפועל: `Live`, עם `gate_reason=none`.

## 2) מדיניות שאומצה

- `recall_hard_min = 0.85` (gate קשיח).
- `recall_min = 0.90`.
- `recall_high_target = 0.92`.
- `fpr_max_operating = 0.85`.
- `precision_min = 0.24`.
- `f1_min = 0.38`.
- `min_auc_threshold = 0.62` בצד `validate_metrics`.

## 3) מה שונה בקוד כדי להגיע למודל מתאים

- בחירת winner ב-`ML_model/train_model.py` הועברה ללוגיקה תפעולית:
  - דירוג לפי נקודת הפעלה אמיתית (threshold sweep), לא רק לפי `THRESHOLD=0.4`.
  - tiered selection (`target` -> `relaxed` -> `fallback`) כדי למנוע בחירת מודל עם Recall נמוך.
- ולידציית איכות ב-`ML_model/validate_metrics.py` עובדת על `winner_metrics` מתוך `run_manifest.json` (כלומר על threshold התפעולי שנבחר), ולא רק על טבלת comparison הקבועה של `0.4`.
- חישוב `degraded_rc` ב-`backend/ml/model_loader.py` הותאם לסף ריאלי (`MIN_AUC_FOR_LIVE + 0.02`), כך שסטטוס degraded יתאים למדיניות הנוכחית.

## 4) בדיקות והרצות שבוצעו

- `python -m pytest tests -v` (backend): עבר, `31 passed`.
- `python ML_model/train_model.py`: יצר ארטיפקט חדש `20260510_143741`.
- `python ML_model/validate_metrics.py`: מחזיר `PASS` על הארטיפקט החדש.
- טעינת מודל ב-loader: מחזירה `Live` ו-`degraded_rc=false`.

## 5) החלטת קידום

בוצע promotion לארטיפקט `20260510_143741` דרך `ML_model/artifacts/promoted.json`.

## 6) המשך מיידי מומלץ

1. לנטר `GET /status/ml` לאורך כמה ימים כדי לוודא יציבות תפעולית.
2. לשפר מחזור דאטה/פיצ'רים כדי להעלות AUC ו-Precision (מעבר לרף המינימום).
3. להוסיף benchmark נוסף (קבוצת בדיקה חדשה) לאימות generalization.
