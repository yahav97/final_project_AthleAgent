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

# Identify weak features - only remove VERY weak ones (more conservative)
# Only remove features with importance < 0.01 (very weak) or bottom 10% (not 20%)
threshold = 0.01
bottom_percentile = 0.10  # More conservative - only bottom 10%
weak_features = feature_importance_prelim[
    (feature_importance_prelim['importance'] < threshold) |
    (feature_importance_prelim['importance'] < feature_importance_prelim['importance'].quantile(bottom_percentile))
]

if len(weak_features) > 0:
    print(f"\n[WARNING] WEAK FEATURES DETECTED ({len(weak_features)} features):")
    print("-" * 60)
    for idx, row in weak_features.iterrows():
        print(f"  - {row['feature']:30s} (importance: {row['importance']:.4f})")
        # Explain why each feature might be weak
        feature_name = row['feature']
        if 'cadence' in feature_name.lower():
            print(f"    -> Reason: Cadence is often redundant with distance/intensity")
        elif 'calories' in feature_name.lower() and 'balance' not in feature_name.lower():
            print(f"    -> Reason: Raw calories less predictive than calorie balance")
        elif 'resting_hr' in feature_name.lower():
            print(f"    -> Reason: HRV is more sensitive indicator than resting HR")
        elif 'vo2_max' in feature_name.lower():
            print(f"    -> Reason: Static metric, doesn't change daily")
        elif 'bmi' in feature_name.lower():
            print(f"    -> Reason: Less relevant for injury prediction than load metrics")
    
    print("\n[ACTION] Removing only VERY weak features (conservative approach)...")
    weak_feature_names = weak_features['feature'].tolist()
    
    # Only remove features that are truly weak (importance < 0.01 or bottom 10%)
    # This is more conservative - keeps features that might still contribute
    X_train = X_train.drop(columns=weak_feature_names, errors='ignore')
    X_test = X_test.drop(columns=weak_feature_names, errors='ignore')
    
    print(f"[OK] Removed {len(weak_feature_names)} very weak features: {', '.join(weak_feature_names)}")
    print(f"[INFO] Keeping other features even if low importance - they may still contribute")
    
    # Recreate scaler with remaining features only (critical for validation set)
    # This ensures scaler only knows about features that remain after removal
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    X_train_scaled = pd.DataFrame(X_train_scaled, columns=X_train.columns, index=X_train.index)
    X_test_scaled = pd.DataFrame(X_test_scaled, columns=X_test.columns, index=X_test.index)
    print("[OK] Scaler recreated with remaining features only")
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
            n_estimators=200,  # More trees for better performance
            max_depth=12,  # Balanced depth (not too deep to avoid overfitting)
            min_samples_split=10,  # Prevent overfitting
            min_samples_leaf=5,  # Prevent overfitting
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
            solver='lbfgs',  # Good default solver
            C=1.0  # Regularization strength
        ),
        'use_scaled': True  # Needs scaling
    },
    'SVM': {
        'model': SVC(
            probability=True,
            random_state=42,
            class_weight='balanced',
            kernel='rbf',
            C=1.0,  # Regularization
            gamma='scale'  # Better default
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
            eval_metric='logloss'
            # Removed use_label_encoder (deprecated in newer versions)
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
    
    # Predictions with probability
    y_pred_proba = model.predict_proba(X_test_model)[:, 1]
    
    # For safety-focused model: Use lower threshold to catch more injuries
    # With severe class imbalance, need lower threshold to detect injuries
    # Threshold 0.2-0.25 is better for imbalanced data
    safety_threshold = 0.25  # Lower threshold to catch more injuries
    y_pred = (y_pred_proba >= safety_threshold).astype(int)
    
    # Also calculate with default threshold for comparison
    y_pred_default = model.predict(X_test_model)
    
    # Calculate metrics with safety threshold
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    
    # Calculate default threshold metrics for comparison
    recall_default = recall_score(y_test, y_pred_default, zero_division=0)
    
    # Cross-validation (use appropriate data scaling)
    cv_scores = cross_val_score(model, X_train_model, y_train, cv=5, scoring='f1')
    cv_mean = cv_scores.mean()
    cv_std = cv_scores.std()
    
    results.append({
        'Model': name,
        'Accuracy': accuracy,
        'Precision': precision,
        'Recall': recall,  # With safety threshold (0.3)
        'Recall_Default': recall_default,  # With default threshold (0.5)
        'F1-Score': f1,
        'ROC-AUC': roc_auc,
        'CV F1-Mean': cv_mean,
        'CV F1-Std': cv_std
    })
    
    print(f"  ✓ F1-Score: {f1:.4f}, Recall (safety): {recall:.4f}, ROC-AUC: {roc_auc:.4f}")

# Create comparison DataFrame
results_df = pd.DataFrame(results)

print("\n" + "=" * 60)
print("MODEL COMPARISON RESULTS")
print("=" * 60)
print("\n" + results_df.to_string(index=False))

# Find best model - prioritize Recall (safety) over F1-Score
# For injury prediction, we want to catch as many injuries as possible
print("\n" + "=" * 60)
print("SELECTING BEST MODEL (Safety-Focused)")
print("=" * 60)
print("Priority: High Recall (catch injuries) - class imbalance requires lower threshold")
print("Using safety threshold: 0.25 (lower to detect more injuries in imbalanced data)")

# For imbalanced data: Prioritize Recall and F1-Score over Accuracy
# High Accuracy with low Recall means model predicts "no injury" always
# Better to have lower Accuracy but catch injuries (higher Recall)
results_df['Balanced_Score'] = (
    0.15 * results_df['Accuracy'] +  # Lower weight - can be misleading with imbalance
    0.25 * results_df['Precision'] + 
    0.35 * results_df['Recall'] +    # Higher weight - must catch injuries
    0.25 * results_df['F1-Score']    # F1 balances Precision and Recall
)
results_df['Safety_Score'] = results_df['Balanced_Score']  # Keep for compatibility

# Find best model - prioritize balanced performance
# Also check that Accuracy is reasonable (at least 0.5)
valid_models = results_df[results_df['Accuracy'] >= 0.5]
if len(valid_models) > 0:
    best_model_idx = valid_models['Balanced_Score'].idxmax()
    print(f"\n[INFO] Filtered models with Accuracy < 0.5. Best from {len(valid_models)} valid models.")
else:
    # If no model has good accuracy, use balanced score anyway
    best_model_idx = results_df['Balanced_Score'].idxmax()
    print(f"\n[WARNING] No model has Accuracy >= 0.5. Using best Balanced Score.")
best_model_name = results_df.loc[best_model_idx, 'Model']
best_model_config = list(models.values())[best_model_idx]
best_model = best_model_config['model']
best_use_scaled = best_model_config['use_scaled']

print(f"\n[BEST MODEL] {best_model_name}")
print(f"  Balanced Score: {results_df.loc[best_model_idx, 'Balanced_Score']:.4f}")
print(f"  Accuracy: {results_df.loc[best_model_idx, 'Accuracy']:.4f}")
print(f"  Precision: {results_df.loc[best_model_idx, 'Precision']:.4f}")
print(f"  Recall: {results_df.loc[best_model_idx, 'Recall']:.4f}")
print(f"  F1-Score: {results_df.loc[best_model_idx, 'F1-Score']:.4f}")
print(f"  ROC-AUC: {results_df.loc[best_model_idx, 'ROC-AUC']:.4f}")

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
# Use safety threshold for final predictions
safety_threshold = 0.25  # Lower threshold for imbalanced data
y_pred_proba = model.predict_proba(X_test_best)[:, 1]
y_pred = (y_pred_proba >= safety_threshold).astype(int)

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

# Use appropriate data for cross-validation
X_train_cv = X_train_scaled if best_use_scaled else X_train
cv_scores = cross_val_score(model, X_train_cv, y_train, cv=5, scoring='f1')
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

# ============================================================================
# EVALUATION ON NEW DATA (Validation Set)
# ============================================================================

print("\n" + "=" * 60)
print("EVALUATION ON NEW DATA (Validation Set)")
print("=" * 60)

# Generate new validation data
print("\nGenerating new validation dataset...")
from data_generator import generate_validation_data

validation_df = generate_validation_data()
X_val = validation_df.drop('injury_tomorrow', axis=1)
y_val = validation_df['injury_tomorrow']

# Remove weak features if they were removed (MUST match training features)
# This ensures validation set has same features as training set
if len(weak_features) > 0:
    weak_feature_names = weak_features['feature'].tolist()
    X_val = X_val.drop(columns=weak_feature_names, errors='ignore')

# Ensure validation set has same features as training set (in same order)
# This is critical for scaling to work correctly
# Only keep features that exist in both sets and in same order
missing_features = [f for f in X_train.columns if f not in X_val.columns]
if missing_features:
    print(f"[WARNING] Missing features in validation set: {missing_features}")
    print("[INFO] Adding missing features with zero values...")
    for f in missing_features:
        X_val[f] = 0

X_val = X_val[X_train.columns]  # Ensure exact same order as training

# Scale if needed
if best_use_scaled:
    X_val_scaled = scaler.transform(X_val)
    X_val_scaled = pd.DataFrame(X_val_scaled, columns=X_val.columns, index=X_val.index)
    X_val_model = X_val_scaled
else:
    X_val_model = X_val

# Predictions on new data with safety threshold
safety_threshold = 0.25  # Lower threshold for imbalanced data
y_val_proba = model.predict_proba(X_val_model)[:, 1]
y_val_pred = (y_val_proba >= safety_threshold).astype(int)

# Calculate metrics on new data
val_accuracy = accuracy_score(y_val, y_val_pred)
val_precision = precision_score(y_val, y_val_pred, zero_division=0)
val_recall = recall_score(y_val, y_val_pred, zero_division=0)
val_f1 = f1_score(y_val, y_val_pred, zero_division=0)
val_roc_auc = roc_auc_score(y_val, y_val_proba)

print(f"\nValidation Set Performance (New Data):")
print(f"  Accuracy:  {val_accuracy:.4f} ({val_accuracy*100:.2f}%)")
print(f"  Precision: {val_precision:.4f} ({val_precision*100:.2f}%)")
print(f"  Recall:    {val_recall:.4f} ({val_recall*100:.2f}%)")
print(f"  F1-Score:  {val_f1:.4f} ({val_f1*100:.2f}%)")
print(f"  ROC-AUC:   {val_roc_auc:.4f} ({val_roc_auc*100:.2f}%)")

# Confusion Matrix on validation
val_cm = confusion_matrix(y_val, y_val_pred)
print(f"\nValidation Confusion Matrix:")
print(f"  True Negatives:  {val_cm[0,0]}")
print(f"  False Positives: {val_cm[0,1]} (warned but no injury - acceptable)")
print(f"  False Negatives: {val_cm[1,0]} (missed injury - CRITICAL)")
print(f"  True Positives:  {val_cm[1,1]}")

# Calculate injury risk percentage for all validation samples
print(f"\n[INJURY RISK PREDICTION - ALL VALIDATION SAMPLES]")
print("-" * 60)
print(f"Total validation samples: {len(X_val)}")
print(f"\nRisk Distribution:")
print(f"  Low risk (0-30%):    {np.sum((y_val_proba < 0.3))} samples ({np.sum((y_val_proba < 0.3))/len(y_val_proba)*100:.1f}%)")
print(f"  Medium risk (30-60%): {np.sum((y_val_proba >= 0.3) & (y_val_proba < 0.6))} samples ({np.sum((y_val_proba >= 0.3) & (y_val_proba < 0.6))/len(y_val_proba)*100:.1f}%)")
print(f"  High risk (60-100%):  {np.sum((y_val_proba >= 0.6))} samples ({np.sum((y_val_proba >= 0.6))/len(y_val_proba)*100:.1f}%)")

# Show detailed examples with risk percentages
print(f"\n[DETAILED RISK PREDICTIONS - SAMPLE EXAMPLES]")
print("-" * 60)
print(f"{'Sample':<8} {'Risk %':<10} {'Predicted':<12} {'Actual':<12} {'Status':<15}")
print("-" * 60)

# Show examples from different risk ranges
sample_indices = []
# High risk examples
high_risk_indices = np.where(y_val_proba >= 0.6)[0]
if len(high_risk_indices) > 0:
    sample_indices.extend(np.random.choice(high_risk_indices, min(3, len(high_risk_indices)), replace=False))
# Medium risk examples
medium_risk_indices = np.where((y_val_proba >= 0.3) & (y_val_proba < 0.6))[0]
if len(medium_risk_indices) > 0:
    sample_indices.extend(np.random.choice(medium_risk_indices, min(3, len(medium_risk_indices)), replace=False))
# Low risk examples
low_risk_indices = np.where(y_val_proba < 0.3)[0]
if len(low_risk_indices) > 0:
    sample_indices.extend(np.random.choice(low_risk_indices, min(3, len(low_risk_indices)), replace=False))

for idx in sample_indices[:10]:  # Show up to 10 examples
    risk_percent = y_val_proba[idx] * 100
    actual = y_val.iloc[idx]
    predicted = y_val_pred[idx]
    actual_label = "Injury" if actual == 1 else "No Injury"
    predicted_label = "Injury" if predicted == 1 else "No Injury"
    status = "CORRECT" if predicted == actual else "MISSED" if actual == 1 else "FALSE ALARM"
    print(f"{idx:<8} {risk_percent:>6.1f}%    {predicted_label:<12} {actual_label:<12} {status:<15}")

# Summary statistics
print(f"\n[RISK PERCENTAGE STATISTICS]")
print("-" * 60)
print(f"  Mean risk: {np.mean(y_val_proba)*100:.2f}%")
print(f"  Median risk: {np.median(y_val_proba)*100:.2f}%")
print(f"  Min risk: {np.min(y_val_proba)*100:.2f}%")
print(f"  Max risk: {np.max(y_val_proba)*100:.2f}%")
print(f"  Std deviation: {np.std(y_val_proba)*100:.2f}%")

# Save validation predictions with risk percentages to CSV
validation_results = pd.DataFrame({
    'sample_index': range(len(X_val)),
    'injury_risk_percentage': y_val_proba * 100,
    'predicted_injury': y_val_pred,
    'actual_injury': y_val.values,
    'correct': (y_val_pred == y_val.values).astype(int)
})
validation_results['risk_level'] = validation_results['injury_risk_percentage'].apply(
    lambda x: 'High' if x >= 60 else 'Medium' if x >= 30 else 'Low'
)

validation_results_path = os.path.join(script_dir, 'validation_risk_predictions.csv')
validation_results.to_csv(validation_results_path, index=False)
print(f"\n[OK] Validation risk predictions saved to {validation_results_path}")
print(f"     This file contains risk percentage for each validation sample (0-100%)")

print("\n" + "=" * 60)
print("TRAINING COMPLETE!")
print("=" * 60)
print(f"\n[SUMMARY]")
print(f"   Best Model: {best_model_name}")
print(f"   Safety Threshold: {safety_threshold} (balanced for Recall and Precision)")
print(f"   Test Accuracy: {results_df.loc[best_model_idx, 'Accuracy']:.4f}")
print(f"   Test Precision: {results_df.loc[best_model_idx, 'Precision']:.4f}")
print(f"   Test Recall: {results_df.loc[best_model_idx, 'Recall']:.4f}")
print(f"   Test F1-Score: {results_df.loc[best_model_idx, 'F1-Score']:.4f}")
print(f"   Validation Accuracy: {val_accuracy:.4f}")
print(f"   Validation Precision: {val_precision:.4f}")
print(f"   Validation Recall: {val_recall:.4f}")
print(f"   Validation F1-Score: {val_f1:.4f}")
if len(weak_features) > 0:
    print(f"   [INFO] {len(weak_features)} weak features removed")
print("=" * 60)