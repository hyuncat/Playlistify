from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
import urllib.parse
from datetime import datetime
import requests
import pandas as pd
import os
from sqlalchemy import text
import ast

from playlistify.SpotifyAnalyzer import SpotifyAnalyzer
from .db_config import my_engine

# Login blueprint
login = Blueprint('login', __name__)

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'


@login.route('/login')
def user_login():
    scope = 'playlist-read-private'
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': REDIRECT_URI,
        'show_dialog': 'true' # forces user to login every time
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

@login.route('/callback')
def callback():

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

    session['user_access_token'] = response_data['access_token']
    session['refresh_token'] = response_data['refresh_token']
    session['expires_at'] = datetime.now().timestamp() + response_data['expires_in']

    Sp = SpotifyAnalyzer(redirect_uri=REDIRECT_URI, token=session['user_access_token'])
    user_info = Sp.get_user_info()
    session['user_id'] = user_info['user_id']
    session['display_name'] = user_info['display_name']
    session['user_img'] = user_info['image_url']

    return redirect(url_for('login.user_playlists'))



@login.route('/refresh_token/<redirect_route>')
def refresh_token(redirect_route):
    refresh_token = session.get('refresh_token')
    if not refresh_token:
        return redirect('/login')

    if datetime.now().timestamp() > session.get('expires_at'):
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }

        response = requests.post(TOKEN_URL, data=data)
        new_response_data = response.json()

        session['user_access_token'] = new_response_data['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_response_data['expires_in']

    return redirect(url_for(redirect_route))


@login.route('/user_playlists', methods=['GET'])
def user_playlists():
    access_token = session.get('user_access_token')
    if not access_token or datetime.now().timestamp() > session.get('expires_at'):
        return redirect(url_for('login.refresh_token', redirect_route='login.user_playlists'))

    Sp = SpotifyAnalyzer(redirect_uri=REDIRECT_URI, token=access_token)
    playlists = Sp.get_user_playlists()
    user_info = Sp.get_user_info()
    print(playlists)

    # if request.method == 'POST':
    #     playlist_id = request.form['playlist_id']
    #     session['playlist_id'] = playlist_id
    #     return redirect(url_for('main.analyze_playlist', playlist_id=playlist_id))

    return render_template('user_playlists.html', user_info=user_info, playlists=playlists)

@login.route('/user_profile')
def user_profile():
    access_token = session.get('user_access_token')
    if not access_token or datetime.now().timestamp() > session.get('expires_at'):
        return redirect(url_for('login.refresh_token', redirect_route='login.user_profile'))

    if not session.get('user_id'):
        return redirect(url_for('login.refresh_token', redirect_route='login.user_profile'))

    # Sp = SpotifyAnalyzer(redirect_uri=REDIRECT_URI, token=access_token)
    # user_info = Sp.get_user_info()
    user_info = {
        'user_id': session.get('user_id'),
        'display_name': session.get('display_name'),
        'image_url': session.get('image_url')
    }
    with my_engine.connect() as conn:
        select_playlists = text("""
            SELECT playlist.title, playlist.playlist_id, AVG(rate.rating) AS avg_rating
            FROM HasPlaylist
            INNER JOIN playlist ON HasPlaylist.user_id = :user_id AND HasPlaylist.playlist_id = playlist.playlist_id
            LEFT JOIN rate ON playlist.playlist_id = rate.playlist_id
            GROUP BY playlist.title, playlist.playlist_id
        """)
        params = {
            'user_id': user_info['user_id']
        }
        cursor = conn.execute(select_playlists, params)
        uploaded_playlists = []
        for result in cursor:
            uploaded_playlists.append(result[0:3])
            print(result)
        uploaded_playlists = pd.DataFrame(uploaded_playlists, columns=['title', 'playlist_id', 'avg_rating'])
        uploaded_playlists['avg_rating'] = uploaded_playlists['avg_rating'].apply(lambda x: round(x, 2) if pd.notnull(x) else x)
    return render_template('user_profile.html', user_info=user_info, uploaded_playlists=uploaded_playlists)


@login.route('/view_playlist/<playlist_id>')
def view_playlist(playlist_id):
    with my_engine.connect() as conn:
        select_playlist = text("""
            SELECT p.playlist_id, p.title, p.image_url, p.description, u.user_id AS owner_id, u.name AS owner_name
            FROM playlist AS p
            INNER JOIN HasPlaylist AS hp ON p.playlist_id = hp.playlist_id
            INNER JOIN users AS u ON hp.user_id = u.user_id
            WHERE p.playlist_id = :playlist_id
        """)
        params = {
            'playlist_id': playlist_id
        }
        cursor = conn.execute(select_playlist, params)
        playlist_data = cursor.fetchone()

        select_songs = text("""
            SELECT song.song_id, song.title, song.popularity, 
                (song.features).danceability, (song.features).energy, (song.features).music_key, 
                (song.features).loudness, (song.features).music_mode, (song.features).speechiness, 
                (song.features).acousticness, (song.features).instrumentalness, 
                (song.features).liveness, (song.features).valence, (song.features).tempo, 
                (song.features).duration_ms, (song.features).time_signature, song.genres,
                array_agg(artist.name) AS artist_names
            FROM song
            INNER JOIN SongArtist ON song.song_id = SongArtist.song_id
            INNER JOIN artist ON SongArtist.artist_id = artist.artist_id
            WHERE song.song_id IN (
                SELECT song_id
                FROM PlaylistSong
                WHERE playlist_id = :playlist_id
            )
            GROUP BY song.song_id
        """)
        cursor = conn.execute(select_songs, params)
        song_rows = []
        for result in cursor:
            song_rows.append(result[0:18])
        
        song_colnames = [
            'song_id', 'title', 'popularity', 'danceability', 'energy', 'music_key',
            'loudness', 'music_mode', 'speechiness', 'acousticness', 'instrumentalness',
            'liveness', 'valence', 'tempo', 'duration_ms', 'time_signature', 'genres', 'artist_names'
        ]
        sql_reconstructed_song_panda = pd.DataFrame(song_rows, columns=song_colnames)

        def unpack_col(value):
            if isinstance(value, str):
                unstringed_list = ast.literal_eval(value)
            else:
                unstringed_list = value
            # Flatten the list if it contains sublists
            if any(isinstance(i, list) for i in unstringed_list):
                unstringed_list = [item for sublist in unstringed_list for item in sublist]
            try:
                return ', '.join(unstringed_list)
            except Exception as e:
                return unstringed_list

        sql_reconstructed_song_panda['artist_names'] = sql_reconstructed_song_panda['artist_names'].apply(unpack_col)
        sql_reconstructed_song_panda['genres'] = sql_reconstructed_song_panda['genres'].apply(unpack_col)

        select_reviews = text("""
            SELECT users.name, rate.rating, rate.rate_text
            FROM Rate
            INNER JOIN users ON Rate.user_id = users.user_id
            WHERE Rate.playlist_id = :playlist_id
        """)
        cursor = conn.execute(select_reviews, params)
        reviews = []
        for result in cursor:
            reviews.append(result)
        review_panda = pd.DataFrame(reviews, columns=['user_name', 'rating', 'rate_text'])

    return render_template('view_playlist.html', playlist_data=playlist_data, song_data=sql_reconstructed_song_panda, reviews=review_panda)
        

@login.route('/rate_playlist/<playlist_id>', methods=['GET', 'POST'])
def rate_playlist(playlist_id):
    if request.method == 'POST':
        rating = request.form['rating']
        comment = request.form.get('comment')  # .get() is used here so that it returns None if 'comment' is not in the form

        # Validate the inputs
        if not 0 <= int(rating) <= 10:
            flash('Rating must be between 0 and 10.')
            return redirect(url_for('main.rate_playlist', playlist_id=playlist_id))

        with my_engine.connect() as conn:
            # Check if the user has already rated the playlist
            select_query = text("""
                SELECT user_id
                FROM Rate
                WHERE user_id = :user_id AND playlist_id = :playlist_id
            """)
            params = {
                'user_id': session['user_id'],
                'playlist_id': playlist_id
            }
            cursor = conn.execute(select_query, params)
            if cursor.fetchone():
                flash('You have already rated this playlist.')
                return redirect(url_for('login.view_playlist', playlist_id=playlist_id))
            
            # Update the database if else
            update_query = text("""
                INSERT INTO Rate (user_id, playlist_id, rating, rate_text)
                VALUES (:user_id, :playlist_id, :rating, :comment)
            """)
            params = {
                'user_id': session['user_id'],  # 'user_id' is stored in the session when the user logs in
                'playlist_id': playlist_id,
                'rating': rating,
                'comment': comment
            }
            conn.execute(update_query, params)
            conn.commit()
            print(f'{session["user_id"]} submitted rating: {rating}, comment: {comment}')

        flash('Your rating has been submitted.')
        return redirect(url_for('login.view_playlist', playlist_id=playlist_id))
