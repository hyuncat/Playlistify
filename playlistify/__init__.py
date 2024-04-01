
import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response
from flask_session import Session
import psycopg2

from .routes import main
from .login import login as lg


# XXX: The URI should be in the format of:
#     postgresql://USER:PASSWORD@34.73.36.248/project1
#
# For example, if you had username zy2431 and password 123123, then the following line would be:
#     DATABASEURI = "postgresql://zy2431:123123@34.73.36.248/project1"
#

DB_USERNAME = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = "35.212.75.104"
DATABASE_URI = f"postgresql://{DB_USERNAME}:{DB_USERNAME}@{DB_HOST}/proj1part2"

# Create a database engine that knows how to connect to the URI above.
engine = create_engine(DATABASE_URI)

app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY=os.urandom(24),
    DATABASE=os.path.join(app.instance_path, DATABASE_URI),
    DB_USER=DB_USERNAME,
    DB_PASSWORD=DB_PASSWORD,
    DB_HOST=DB_HOST,
    DB_PORT=8111,
    SESSION_TYPE='filesystem',  # Set the session type to use filesystem storage
    SESSION_FILE_DIR=os.path.join(app.instance_path, 'sessions'),  # Specify the directory to store session files
)

# Load additional configuration from config.py
app.config.from_pyfile('config.py', silent=True)

# Initialize the session
Session(app)

# Ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# Function to establish a database connection
def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(
            dbname=app.config['DATABASE'],
            user=app.config['DB_USER'],
            password=app.config['DB_PASSWORD'],
            host=app.config['DB_HOST'],
            port=app.config['DB_PORT']
        )
    return g.db

# Function to close the database connection
@app.teardown_appcontext
def close_db(error):
    if 'db' in g:
        g.db.close()


# Register Blueprints
app.register_blueprint(main)
app.register_blueprint(lg)