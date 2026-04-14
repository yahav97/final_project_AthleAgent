"""
Create all database tables.
Run this script once to initialize the database schema.
"""

# Import all models FIRST to register them with Base
from models import (
    User, Team, TeamMember, JoinRequest,
    DailyRecord, Prediction, NutritionRecord,
    StressSurvey, HealthConnectPermission, Injury
)

from database.connection import init_db
from utils.logging import logger

if __name__ == "__main__":
    logger.info("Creating database tables...")
    try:
        init_db()
        logger.info("All tables created successfully!")
        print("\n[OK] Database tables created successfully!")
        print("You can now start using the API.")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        print(f"\n[ERROR] Failed to create tables: {e}")
        raise

