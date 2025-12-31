"""
AthleAgent - Injury Prediction Model Training Script

This script compares multiple ML models to find the best one for injury prediction.
It includes comprehensive model evaluation, feature importance analysis, and feature selection.

Models tested:
- Random Forest
- XGBoost (if available)
- Logistic Regression
- Support Vector Machine (SVM)

"""

import pandas as pd
import numpy as np
import sys
import io
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score, roc_curve
)
import joblib
import os

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Try to import XGBoost (optional - better performance if available)
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Note: XGBoost not available. Install with: pip install xgboost")

# ============================================================================
# DATA LOADING
# ============================================================================

script_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(script_dir, 'athlete_injury_data.csv')

if os.path.exists(data_path):
    df = pd.read_csv(data_path)
    print("=" * 60)
    print("Data loaded successfully.")
    print(f"Dataset shape: {df.shape}")
    print("=" * 60)
else:
    print(f"Error: {data_path} not found. Run data_generator.py first!")
    exit()

# ============================================================================
# DATA PREPARATION
# ============================================================================

X = df.drop('injury_tomorrow', axis=1)
y = df['injury_tomorrow']

# Analyze class distribution
print("\n" + "=" * 60)
print("CLASS DISTRIBUTION ANALYSIS")
print("=" * 60)
class_counts = y.value_counts()
class_percentages = y.value_counts(normalize=True) * 100
print(f"No Injury (0): {class_counts[0]} samples ({class_percentages[0]:.2f}%)")
print(f"Injury (1): {class_counts[1]} samples ({class_percentages[1]:.2f}%)")
print(f"Class Imbalance Ratio: {class_counts[0] / class_counts[1]:.2f}:1")

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\nTrain set: {X_train.shape[0]} samples")
print(f"Test set: {X_test.shape[0]} samples")

# ============================================================================
# DATA SCALING (for models that need it)
# ============================================================================

# Scale data for Logistic Regression and SVM (they are sensitive to feature scale)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
X_train_scaled = pd.DataFrame(X_train_scaled, columns=X_train.columns, index=X_train.index)
X_test_scaled = pd.DataFrame(X_test_scaled, columns=X_test.columns, index=X_test.index)

# ============================================================================
# FEATURE SELECTION - Identify weak features
# ============================================================================

print("\n" + "=" * 60)
print("FEATURE SELECTION ANALYSIS")
print("=" * 60)

# Quick Random Forest to check feature importance
temp_rf = RandomForestClassifier(n_estimators=50, random_state=42, class_weight='balanced')
temp_rf.fit(X_train, y_train)

feature_importance_prelim = pd.DataFrame({
    'feature': X.columns,
    'importance': temp_rf.feature_importances_
}).sort_values('importance', ascending=False)

print("\nAll Features by Importance:")
print("-" * 60)
for idx, row in feature_importance_prelim.iterrows():
    print(f"{row['feature']:30s} {row['importance']:.4f} ({row['importance']*100:.2f}%)")

# Identify weak features (importance < 0.01 or bottom 20%)
threshold = 0.01
bottom_percentile = 0.20
weak_features = feature_importance_prelim[
    (feature_importance_prelim['importance'] < threshold) |
    (feature_importance_prelim['importance'] < feature_importance_prelim['importance'].quantile(bottom_percentile))
]

if len(weak_features) > 0:
    print(f"\n[WARNING] WEAK FEATURES DETECTED ({len(weak_features)} features):")
    print("-" * 60)
    for idx, row in weak_features.iterrows():
        print(f"  - {row['feature']:30s} (importance: {row['importance']:.4f})")
    print("\n[TIP] Consider removing these features to reduce overfitting and improve model performance.")
else:
    print("\n[OK] No obviously weak features detected.")

# ============================================================================
# MODEL COMPARISON - Test Multiple Models
# ============================================================================

print("\n" + "=" * 60)
print("MODEL COMPARISON - Training Multiple Models")
print("=" * 60)

models = {
    'Random Forest': {
        'model': RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight='balanced'
        ),
        'use_scaled': False  # Tree-based models don't need scaling
    },
    'Logistic Regression': {
        'model': LogisticRegression(
            max_iter=2000,  # Increased iterations
            random_state=42,
            class_weight='balanced',
            solver='lbfgs'  # Good default solver
        ),
        'use_scaled': True  # Needs scaling
    },
    'SVM': {
        'model': SVC(
            probability=True,
            random_state=42,
            class_weight='balanced',
            kernel='rbf'
        ),
        'use_scaled': True  # Needs scaling
    }
}

# Add XGBoost if available
if XGBOOST_AVAILABLE:
    models['XGBoost'] = {
        'model': XGBClassifier(
            n_estimators=100,
            max_depth=6,
            random_state=42,
            eval_metric='logloss',
            use_label_encoder=False
        ),
        'use_scaled': False  # Tree-based models don't need scaling
    }

# Train and evaluate all models
results = []

for name, model_config in models.items():
    model = model_config['model']
    use_scaled = model_config['use_scaled']
    
    # Choose scaled or unscaled data
    X_train_model = X_train_scaled if use_scaled else X_train
    X_test_model = X_test_scaled if use_scaled else X_test
    
    print(f"\nTraining {name}...")
    model.fit(X_train_model, y_train)
    
    # Predictions
    y_pred = model.predict(X_test_model)
    y_pred_proba = model.predict_proba(X_test_model)[:, 1]
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    
    # Cross-validation (use appropriate data scaling)
    cv_scores = cross_val_score(model, X_train_model, y_train, cv=5, scoring='f1')
    cv_mean = cv_scores.mean()
    cv_std = cv_scores.std()
    
    results.append({
        'Model': name,
        'Accuracy': accuracy,
        'Precision': precision,
        'Recall': recall,
        'F1-Score': f1,
        'ROC-AUC': roc_auc,
        'CV F1-Mean': cv_mean,
        'CV F1-Std': cv_std
    })
    
    print(f"  ✓ F1-Score: {f1:.4f}, ROC-AUC: {roc_auc:.4f}")

# Create comparison DataFrame
results_df = pd.DataFrame(results)

print("\n" + "=" * 60)
print("MODEL COMPARISON RESULTS")
print("=" * 60)
print("\n" + results_df.to_string(index=False))

# Find best model
best_model_idx = results_df['F1-Score'].idxmax()
best_model_name = results_df.loc[best_model_idx, 'Model']
best_model_config = list(models.values())[best_model_idx]
best_model = best_model_config['model']
best_use_scaled = best_model_config['use_scaled']

print(f"\n[BEST MODEL] {best_model_name}")
print(f"   F1-Score: {results_df.loc[best_model_idx, 'F1-Score']:.4f}")
print(f"   ROC-AUC: {results_df.loc[best_model_idx, 'ROC-AUC']:.4f}")

# ============================================================================
# DETAILED EVALUATION OF BEST MODEL
# ============================================================================

print("\n" + "=" * 60)
print(f"DETAILED EVALUATION - {best_model_name}")
print("=" * 60)

model = best_model  # Use best model for detailed evaluation

# Use appropriate data for best model
X_train_best = X_train_scaled if best_use_scaled else X_train
X_test_best = X_test_scaled if best_use_scaled else X_test

# ============================================================================
# MODEL EVALUATION - Basic Metrics
# ============================================================================

print("\n" + "=" * 60)
print("MODEL EVALUATION - TEST SET PERFORMANCE")
print("=" * 60)

# Predictions (using appropriate scaled/unscaled data)
y_pred = model.predict(X_test_best)
y_pred_proba = model.predict_proba(X_test_best)[:, 1]

# Calculate metrics
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, zero_division=0)
recall = recall_score(y_test, y_pred, zero_division=0)
f1 = f1_score(y_test, y_pred, zero_division=0)
roc_auc = roc_auc_score(y_test, y_pred_proba)

print(f"\nAccuracy:  {accuracy:.4f} ({accuracy*100:.2f}%)")
print(f"Precision: {precision:.4f} ({precision*100:.2f}%)")
print(f"Recall:    {recall:.4f} ({recall*100:.2f}%)")
print(f"F1-Score:  {f1:.4f} ({f1*100:.2f}%)")
print(f"ROC-AUC:   {roc_auc:.4f} ({roc_auc*100:.2f}%)")

# Confusion Matrix
print("\n" + "-" * 60)
print("CONFUSION MATRIX")
print("-" * 60)
cm = confusion_matrix(y_test, y_pred)
print("\n                Predicted")
print("              No Injury  Injury")
print(f"Actual No Injury   {cm[0,0]:5d}    {cm[0,1]:5d}")
print(f"Actual Injury      {cm[1,0]:5d}    {cm[1,1]:5d}")
print(f"\nTrue Negatives:  {cm[0,0]}")
print(f"False Positives: {cm[0,1]}")
print(f"False Negatives: {cm[1,0]}")
print(f"True Positives:  {cm[1,1]}")

# Classification Report
print("\n" + "-" * 60)
print("DETAILED CLASSIFICATION REPORT")
print("-" * 60)
print(classification_report(y_test, y_pred, target_names=['No Injury', 'Injury']))

# ============================================================================
# CROSS-VALIDATION
# ============================================================================

print("\n" + "=" * 60)
print("CROSS-VALIDATION (5-fold)")
print("=" * 60)

cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='f1')
print(f"F1-Score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
print(f"Individual fold scores: {cv_scores}")

# ============================================================================
# FEATURE IMPORTANCE ANALYSIS (Best Model)
# ============================================================================

print("\n" + "=" * 60)
print("FEATURE IMPORTANCE ANALYSIS")
print("=" * 60)

# Feature importance (works for tree-based models and can be approximated for others)
if hasattr(model, 'feature_importances_'):
    feature_importance = pd.DataFrame({
        'feature': X_train_best.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 10 Most Important Features:")
    print("-" * 60)
    for idx, row in feature_importance.head(10).iterrows():
        print(f"{row['feature']:25s} {row['importance']:.4f} ({row['importance']*100:.2f}%)")
    
    # Save feature importance
    importance_path = os.path.join(script_dir, 'feature_importance.csv')
    feature_importance.to_csv(importance_path, index=False)
    print(f"\n[OK] Feature importance saved to {importance_path}")
    
elif hasattr(model, 'coef_'):
    # For linear models (Logistic Regression)
    feature_importance = pd.DataFrame({
        'feature': X_train_best.columns,
        'coefficient': np.abs(model.coef_[0])
    }).sort_values('coefficient', ascending=False)
    
    print("\nTop 10 Features by Absolute Coefficient:")
    print("-" * 60)
    for idx, row in feature_importance.head(10).iterrows():
        print(f"{row['feature']:25s} {row['coefficient']:.4f}")
else:
    print("\n[WARNING] Feature importance not available for this model type.")
    feature_importance = None

# ============================================================================
# SAVE MODEL
# ============================================================================

print("\n" + "=" * 60)
print("SAVING MODEL")
print("=" * 60)

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
output_dir = os.path.join(project_root, 'backend')

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

output_path = os.path.join(output_dir, 'injury_model.pkl')
joblib.dump(model, output_path)
print(f"[OK] Model saved to {output_path}")

# Save model comparison results
comparison_path = os.path.join(script_dir, 'model_comparison.csv')
results_df.to_csv(comparison_path, index=False)
print(f"[OK] Model comparison saved to {comparison_path}")

print("\n" + "=" * 60)
print("TRAINING COMPLETE!")
print("=" * 60)
print(f"\n[SUMMARY]")
print(f"   Best Model: {best_model_name}")
print(f"   F1-Score: {results_df.loc[best_model_idx, 'F1-Score']:.4f}")
print(f"   ROC-AUC: {results_df.loc[best_model_idx, 'ROC-AUC']:.4f}")
if len(weak_features) > 0:
    print(f"   [WARNING] {len(weak_features)} weak features identified - consider removal")
print("=" * 60)