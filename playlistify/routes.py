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
            return redirect(url_for('main.analyze_playlist', playlist_id=session['playlist_id']))
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
    try:
        Sp = SpotifyAnalyzer(redirect_uri=REDIRECT_URI, token=session['access_token'])
        play_dict, song_pd, art_pd = Sp.get_playlist_details(playlist_id)
    except Exception as e:
        return redirect(url_for('main.auth'))
    session['playlist_data'] = play_dict

    # Pickle data to compress and store in session
    pickled_panda = zlib.compress(pickle.dumps(song_pd))
    pickled_artsy_panda = zlib.compress(pickle.dumps(art_pd))
    session['song_panda'] = pickled_panda
    session['art_panda'] = pickled_artsy_panda
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

        if 'user_access_token' not in session:
            return redirect(url_for('login.user_login'))

        playlist_data = session['playlist_data']
        song_data = pickle.loads(zlib.decompress(session['song_panda']))
        art_data = pickle.loads(zlib.decompress(session['art_panda']))

        with my_engine.connect() as conn:
            # Insert playlist
            insert_playlist = text("""INSERT INTO playlist (playlist_id, title, image_url, description) 
                                   VALUES (:playlist_id, :title, :image_url, :description) 
                                   ON CONFLICT (playlist_id) DO NOTHING""")
            params = {
                'playlist_id': playlist_data['playlist_id'],
                'title': playlist_data['title'],
                'image_url': playlist_data['image_url'],
                'description': playlist_data['description']
            }
            conn.execute(insert_playlist, params)
            conn.commit()
            print(f'inserted playlist: {playlist_data["title"]}')

            # Insert Users
            insert_user = text("""INSERT INTO Users (user_id, name, image_url) 
                                VALUES (:user_id, :name, :image_url) 
                                ON CONFLICT (user_id) DO NOTHING""")
            params = {
                'user_id': session['user_id'],
                'name': session['display_name'],
                'image_url': session['user_img']
            }
            conn.execute(insert_user, params)
            conn.commit()
            print(f"inserted user: {session['display_name']}")

            # Insert HasPlaylist
            insert_has_playlist = text("""INSERT INTO HasPlaylist (user_id, playlist_id, date_uploaded) 
                                       VALUES (:user_id, :playlist_id, :date) 
                                       ON CONFLICT (user_id, playlist_id) DO NOTHING""")
            params = {
                'user_id': session['user_id'],
                'playlist_id': playlist_data['playlist_id'],
                'date': datetime.now()
            }
            conn.execute(insert_has_playlist, params)
            conn.commit()
            print(f"inserted HasPlaylist: ({session['display_name']}, {playlist_data['title']})")

            # Insert Song
            for _, row in song_data.iterrows():
                insert_song = text("""
                    INSERT INTO Song (song_id, title, features, popularity, genres)
                    VALUES (:song_id, :title, :features, :popularity, ARRAY[:genres]) 
                    ON CONFLICT (song_id) DO NOTHING
                """)
                params = {
                    'song_id': row['song_id'],
                    'title': row['song_title'],
                    'features': f"({row['acousticness']}, {row['danceability']}, {row['duration_ms']}, {row['energy']}, "
                                f"{row['instrumentalness']}, {row['music_key']}, {row['liveness']}, {row['loudness']}, "
                                f"{row['music_mode']}, {row['speechiness']}, {row['tempo']}, {row['time_signature']}, "
                                f"{row['valence']})",
                    'popularity': row['popularity'],
                    'genres': row['genres']
                }
                conn.execute(insert_song, params)
                conn.commit()
                print(f'inserted song: {row["song_title"]}')

                # Insert PlaylistSong
                insert_playlist_song = text("""INSERT INTO PlaylistSong (playlist_id, song_id) 
                                          VALUES (:playlist_id, :song_id) 
                                          ON CONFLICT (playlist_id, song_id) DO NOTHING""")
                params = {
                    'playlist_id': playlist_data['playlist_id'],
                    'song_id': row['song_id']
                }
                conn.execute(insert_playlist_song, params)
                conn.commit()
                print(f'inserted playlist_song: ({playlist_data["title"]}, {row["song_title"]})')

            # Insert PlaylistArtists
            for _, row in art_data.iterrows():
                insert_artist = text("""INSERT INTO Artist (artist_id, name, image_url, popularity, genres) 
                                   VALUES (:artist_id, :name, :image_url, :popularity, ARRAY[:genres]) 
                                   ON CONFLICT (artist_id) DO NOTHING""")
                params = {
                    'artist_id': row['artist_id'],
                    'name': row['name'],
                    'image_url': row['image_url'],
                    'popularity': row['popularity'],
                    'genres': row['genres']
                }
                conn.execute(insert_artist, params)
                conn.commit()
                print(f'inserted artist: {row["name"]}')

                # Insert SongArtists
                insert_song_artist = text("""INSERT INTO SongArtist (song_id, artist_id) 
                                      VALUES (:song_id, :artist_id) 
                                      ON CONFLICT (song_id, artist_id) DO NOTHING""")
                params = {
                    'song_id': row['song_id'],
                    'artist_id': row['artist_id']
                }
                conn.execute(insert_song_artist, params)
                conn.commit()
                print(f'inserted song_artist: ({row["song_title"]}, {row["name"]})')


    else:
        print("Error uploading playlist to database")
    
    return redirect(url_for('main.playlist'))


@main.route('/browse')
def browse():
    with my_engine.connect() as conn:
        all_playlists = text("""
            SELECT playlist.title, playlist.playlist_id, users.name
            FROM HasPlaylist
            JOIN playlist ON HasPlaylist.playlist_id = playlist.playlist_id
            JOIN users ON HasPlaylist.user_id = users.user_id
        """)
        cursor = conn.execute(all_playlists)
        uploaded_playlists = []
        for result in cursor:
            uploaded_playlists.append(result[0:3])
            print(result)
        uploaded_playlists = pd.DataFrame(uploaded_playlists, columns=['title', 'playlist_id', 'user_name'])
    return render_template('browse.html', all_playlists=uploaded_playlists)