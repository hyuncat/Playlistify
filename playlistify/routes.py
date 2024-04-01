from flask import Blueprint, render_template, request, redirect, url_for, session
import pandas as pd
import os
import pickle
import zlib

from playlistify.SpotifyAnalyzer import SpotifyAnalyzer


REDIRECT_URI = 'http://127.0.0.1:5000/callback'

# Create main_blueprint as a Blueprint object
main = Blueprint('main', __name__)

# Homepage
@main.route('/')
def home():
    return render_template('index.html')
    
@main.route('/upload_playlist', methods=['POST'])
def upload_playlist():
    if request.method == 'POST':
        playlist_link = request.form['playlist_link']
        session['user'] = playlist_link
        # Process the playlist link
        Sp = SpotifyAnalyzer(redirect_uri=REDIRECT_URI)
        play_dict, song_pd = Sp.get_playlist_details(playlist_link)
        session['playlist_data'] = play_dict
        # Pickle data to compress and store in session
        pickled_panda = zlib.compress(pickle.dumps(song_pd))
        session['song_panda'] = pickled_panda
        return redirect(url_for('main.playlist'))
    else:
        return redirect(url_for('main.home'))

@main.route('/playlist')
def playlist():
    if 'playlist_data' in session:
        playlist_data = session['playlist_data']
        song_data = pickle.loads(zlib.decompress(session['song_panda']))
        return render_template('playlist.html', playlist_data=playlist_data, song_data=song_data)
    else:
        return redirect(url_for('main.home'))

