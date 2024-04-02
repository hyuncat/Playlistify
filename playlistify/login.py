from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
import urllib.parse
from datetime import datetime
import requests
import pandas as pd
import os

from playlistify.SpotifyAnalyzer import SpotifyAnalyzer

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



@login.route('/refresh_token')
def refresh_token():
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

    return redirect(url_for('login.user_profile'))


@login.route('/user_playlists')
def user_playlists():
    access_token = session.get('user_access_token')
    if not access_token or datetime.now().timestamp() > session.get('expires_at'):
        return redirect(url_for('login.refresh_token'))

    Sp = SpotifyAnalyzer(redirect_uri=REDIRECT_URI, token=access_token)
    playlists = Sp.get_user_playlists()
    user_info = Sp.get_user_info()
    print(playlists)
    print(user_info)
    return render_template('user_playlists.html', user_info=user_info, playlists=playlists)

@login.route('/user_profile')
def user_profile():
    access_token = session.get('user_access_token')
    if not access_token or datetime.now().timestamp() > session.get('expires_at'):
        return redirect(url_for('login.refresh_token'))

    # Sp = SpotifyAnalyzer(redirect_uri=REDIRECT_URI, token=access_token)
    # user_info = Sp.get_user_info()
    user_info = {
        'user_id': session.get('user_id'),
        'display_name': session.get('display_name'),
        'image_url': session.get('image_url')
    }
    dummy_uploads = pd.DataFrame({'name': ['jigsaw'], 'avg_rating': [4.9]})
    return render_template('user_profile.html', user_info=user_info, uploaded_playlists=dummy_uploads)