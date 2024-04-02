from flask import Blueprint, render_template, g, request, redirect, url_for, session, jsonify, abort
import pandas as pd
import os, json
import pickle, zlib
import requests
import base64
from datetime import datetime
from sqlalchemy import text

from playlistify.SpotifyAnalyzer import SpotifyAnalyzer, extract_playlist_id
from .db_config import my_engine

# Client info
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')

# Spotify API endpoints
TOKEN_URL = 'https://accounts.spotify.com/api/token'
SEARCH_ENDPOINT = 'https://api.spotify.com/v1/search'
REDIRECT_URI = os.getenv('REDIRECT_URI')

# Create main_blueprint as a Blueprint object
main = Blueprint('main', __name__)

# Homepage
@main.route('/')
def home():
    return render_template('index.html')

@main.route('/redirect-playlist', methods=['POST'])
def redirect_playlist():
    if request.method == 'POST':
        playlist_link = request.form['playlist_link']
        playlist_id = extract_playlist_id(playlist_link)
        session['playlist_id'] = playlist_id
        return redirect(url_for('main.auth'))

@main.route('/auth')
def auth():
    """Get user authorization and set access token"""
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode('utf-8')
    headers = {'Authorization': 'Basic ' + auth_header}
    data = {'grant_type': 'client_credentials'}
    
    try: # Try to get access token for Spotify API
        res = requests.post(TOKEN_URL, headers=headers, data=data)
        # if res.status_code == 200:
        #     access_token = res.json()['access_token']
        #     session['access_token'] = access_token
        #     return redirect(url_for('main.analyze_playlist'), playlist_id=session['playlist_id'])
        if res.status_code == 200:
            access_token = res.json()['access_token']
            session['access_token'] = access_token
            response = jsonify({'redirect': url_for('main.analyze_playlist', playlist_id=session['playlist_id'])})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response
        else:
            abort(400, 'Failed to get access token')
            return redirect(url_for('main.home'))
            
    except Exception as e:
        abort(500, str(e))
    
    return redirect(url_for('main.home'))

    
@main.route('/analyze_playlist/<playlist_id>', methods=['GET', 'POST'])
def analyze_playlist(playlist_id):
    """After auth, analyze a given Spotify playlist."""
    if 'access_token' not in session:
        session['playlist_id'] = playlist_id
        return redirect(url_for('main.auth'))
    
    # Process the playlist link
    Sp = SpotifyAnalyzer(redirect_uri=REDIRECT_URI, token=session['access_token'])
    play_dict, song_pd = Sp.get_playlist_details(playlist_id)
    session['playlist_data'] = play_dict

    # Pickle data to compress and store in session
    pickled_panda = zlib.compress(pickle.dumps(song_pd))
    session['song_panda'] = pickled_panda
    return redirect(url_for('main.playlist'))


@main.route('/playlist', methods=['GET'])
def playlist():
    if 'playlist_data' in session:
        playlist_data = session['playlist_data']
        song_data = pickle.loads(zlib.decompress(session['song_panda']))
        return render_template('playlist.html', playlist_data=playlist_data, song_data=song_data)
    else:
        return redirect(url_for('main.home'))

@main.route('/post_playlist', methods=['POST', 'GET'])
def post_playlist():
    if 'playlist_data' in session:
        playlist_data = session['playlist_data']
        song_data = pickle.loads(zlib.decompress(session['song_panda']))

        with my_engine.connect() as conn:
            # Insert or update user
            insert_playlist = text("""INSERT INTO playlist (playlist_id, title, image_url, description) 
                                   VALUES (:id, :title, :image_url, :description) 
                                   ON CONFLICT (id) DO NOTHING""")
            params = {
                'id': playlist_data['playlist_id'],
                'title': playlist_data['name'],
                'image_url': playlist_data['image_url'],
                'description': playlist_data['description']
            }
            conn.execute(insert_playlist, params)
            conn.commit()
            print(f'inserted playlist: {playlist_data["name"]}!')
    else:
        print("Error uploading playlist to database")
    
    return redirect(url_for('main.playlist'))