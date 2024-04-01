from flask import Blueprint, render_template, request, redirect, url_for, session
import pandas as pd
import os, json
import pickle, zlib
import requests
import base64
from datetime import datetime

from playlistify.SpotifyAnalyzer import SpotifyAnalyzer

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

@main.route('/auth', methods=['POST'])
def auth():
    """Get user authorization and set access token"""
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode('utf-8')
    headers = {'Authorization': 'Basic ' + auth_header}
    data = {'grant_type': 'client_credentials'}

    # If "analyze playlist" form submitted
    if request.method == 'POST':
        # Save playlist link to session
        playlist_link = request.form['playlist_link'] 
        session['playlist_link'] = playlist_link
    
        try: # Try to get access token for Spotify API
            res = requests.post(TOKEN_URL, headers=headers, data=data)
            if res.status_code == 200:
                access_token = res.json()['access_token']
                session['access_token'] = access_token
                return redirect(url_for('main.analyze_playlist'))
            else:
                abort(400, 'Failed to get access token')
                return redirect(url_for('main.home'))
               
        except Exception as e:
            abort(500, str(e))
    
    return redirect(url_for('main.home'))


@main.route('/callback')
def playlist_callback():

    error = request.args.get('error')
    if error:
        return f"Error: {error}"

    code = request.args.get('code')
    data = {
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }

    response = requests.post(TOKEN_URL, data=data)
    response_data = response.json()

    session['access_token'] = response_data['access_token']
    session['refresh_token'] = response_data['refresh_token']
    session['expires_at'] = datetime.now().timestamp() + response_data['expires_in']

    return redirect(url_for('main.analyze_playlist'))

    
@main.route('/analyze_playlist', methods=['GET', 'POST'])
def analyze_playlist():
    """After auth, analyze a given Spotify playlist."""
    # Process the playlist link
    Sp = SpotifyAnalyzer(redirect_uri=REDIRECT_URI, token=session['access_token'])
    play_dict, song_pd = Sp.get_playlist_details(session['playlist_link'])
    session['playlist_data'] = play_dict

    # Pickle data to compress and store in session
    pickled_panda = zlib.compress(pickle.dumps(song_pd))
    session['song_panda'] = pickled_panda
    return redirect(url_for('main.playlist'))


@main.route('/playlist')
def playlist():
    if 'playlist_data' in session:
        playlist_data = session['playlist_data']
        song_data = pickle.loads(zlib.decompress(session['song_panda']))
        return render_template('playlist.html', playlist_data=playlist_data, song_data=song_data)
    else:
        return redirect(url_for('main.home'))

