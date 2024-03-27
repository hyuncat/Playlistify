
import os
from flask import Flask, render_template, request, redirect, url_for, session
import csv
import pandas as pd

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'playlistify.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/')
    def home():
        return render_template('index.html')\
        
    @app.route('/upload_playlist', methods=['POST'])
    def upload_playlist():
        if request.method == 'POST':
            playlist_link = request.form['playlist_link']
            session['user'] = playlist_link
            # Now you can process the playlist link (e.g., parse it, send it to Spotify API, etc.)
            # Placeholder code for demonstration
            return redirect(url_for('playlist'))
        else:
            return redirect(url_for('home'))
    
    @app.route('/playlist')
    def playlist():
        if 'user' in session:
            playlist_link = session['user']
            csv_data = pd.read_csv('playlistify/static/tiger_talk.csv')
            # with open('playlistify/static/tiger_talk_songs.csv', 'r') as file:
            #     reader = csv.reader(file)
            #     for row in reader:
            #         csv_data.append(row)
            # print(csv_data)
            
            return render_template('playlist.html', playlist_link=playlist_link, playlist=csv_data)
        else:
            return redirect(url_for('home'))
    
    return app