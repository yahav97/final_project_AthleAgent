import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

# Load the data
script_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(script_dir, 'athlete_injury_data.csv')
if os.path.exists(data_path):
    df = pd.read_csv(data_path)
    print("Data loaded successfully.")
else:
    print(f"Error: {data_path} not found. Run data_generator.py first!")
    exit()

# Train the model
X = df.drop('injury_tomorrow', axis=1)
y = df['injury_tomorrow']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
print("Training model...")
model.fit(X_train, y_train)

# Save model to the backend directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
output_dir = os.path.join(project_root, 'backend')
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

output_path = os.path.join(output_dir, 'injury_model.pkl')
joblib.dump(model, output_path)
print(f"SUCCESS: Model saved to {output_path}")