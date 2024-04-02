import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import psycopg2

DB_USERNAME = os.getenv('DATABASE_USERNAME')
DB_PASSWORD = os.getenv('DATABASE_PASSWORD')
DB_HOST = os.getenv('DATABASE_HOST')
DATABASE_URI = f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/proj1part2"

# Create a database engine that knows how to connect to the URI above.
my_engine = create_engine(DATABASE_URI)

