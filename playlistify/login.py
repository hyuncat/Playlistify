from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
import urllib.parse
from datetime import datetime
import requests

import pandas as pd
import os

# Create main_blueprint as a Blueprint object
login = Blueprint('login', __name__)

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = 'http://127.0.0.1:5000/callback'

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'

# a simple page that says hello
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

    session['access_token'] = response_data['access_token']
    session['refresh_token'] = response_data['refresh_token']
    session['expires_at'] = datetime.now().timestamp() + response_data['expires_in']

    return redirect(url_for('login.profile'))


@login.route('/profile')
def profile():
    access_token = session.get('access_token')
    if not access_token:
        return redirect('/login')
    
    if datetime.now().timestamp() > session.get('expires_at'):
        return redirect(url_for('login.refresh_token'))

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(f'{API_BASE_URL}me', headers=headers)
    response_data = response.json()

    return jsonify(response_data)


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

        session['access_token'] = new_response_data['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_response_data['expires_in']

    return redirect(url_for('login.profile'))