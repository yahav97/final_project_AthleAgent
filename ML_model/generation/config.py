"""Synthetic data generation configuration."""

NUM_ATHLETES = 1000         # Default scale: 1,000 × 340 days = 340,000 rows
DAYS_PER_ATHLETE = 340      # ~11 months per athlete (round dataset size for training)
ANNUAL_CYCLE_DAYS = 365     # Calendar seasonality period (independent of simulation length)
START_DATE = "2025-01-01"   # Starting date for data generation
DEFAULT_SEED = 42
