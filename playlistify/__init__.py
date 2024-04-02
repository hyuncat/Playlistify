
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response
from flask_session import Session
import psycopg2

from .db_config import my_engine
from .routes import main
from .login import login as lg


# XXX: The URI should be in the format of:
#     postgresql://USER:PASSWORD@34.73.36.248/project1
#
# For example, if you had username zy2431 and password 123123, then the following line would be:
#     DATABASEURI = "postgresql://zy2431:123123@34.73.36.248/project1"
#

DB_USERNAME = os.getenv('DATABASE_USERNAME')
DB_PASSWORD = os.getenv('DATABASE_PASSWORD')
DB_HOST = os.getenv('DATABASE_HOST')
DATABASE_URI = f"postgresql://{DB_USERNAME}:{DB_USERNAME}@{DB_HOST}/proj1part2"

# Create a database engine that knows how to connect to the URI above.
my_engine = create_engine(DATABASE_URI)

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

# # Register database engine
# @app.before_request
# def before_request():
#     g.my_engine = my_engine

# # Register the database teardown
# @app.teardown_appcontext
# def teardown_db(error):
#     try:
#         g.conn.close()
#     except Exception as e:
#         pass

# Register Blueprints
app.register_blueprint(main)
app.register_blueprint(lg)