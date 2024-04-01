"""
A SpotifyAnalyzer class to analyze a user's Spotify data.
Author: Sarah Hong
"""

import json
import os

import requests
import pandas as pd
from pandas import json_normalize
import spotipy
import spotipy.util as util


DEFAULT_USERNAME = 'nrkjbdqb3gwxlzypjce5vvqra'
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = 'http://127.0.0.1:5000/callback'

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'


class SpotifyAnalyzer:
    def __init__(self, username=DEFAULT_USERNAME, redirect_uri=REDIRECT_URI, scope=["playlist-read-private"]):
        """
        Create a SpotifyAnalyzer instance with the specified username, redirect_uri, and scope.
        """
        self.token = None
        self.sp = None
        self.username = username
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.token = self.generate_token()
        self.headers = {
            'Authorization': 'Bearer ' + self.token
        }
        
    def set_scope(self, scope):
        """Set/modify permissions for the SpotifyAnalyzer instance."""
        self.scope = scope
        self.generate_token()
        
    
    def generate_token(self):
        """Generate a Spotify API token for the user."""
        token = util.prompt_for_user_token(
            self.username, 
            self.scope, 
            client_id=CLIENT_ID, 
            client_secret=CLIENT_SECRET, 
            redirect_uri=self.redirect_uri
        )
        if token:
            self.sp = spotipy.Spotify(auth=token)
            return token
        else:
            print(f"Cant get token for {self.username}")

    def get_spotipy_playlist(self, playlist_link):
        # Get playlist ID from the provided link
        playlist_id = playlist_link.split('/')[-1]

        playlist = self.sp.playlist(playlist_id)
        print(json.dumps(playlist, indent=4))



    def get_playlist_details(self, playlist_link):
        """
        Get playlist and song details from a Spotify playlist link.
        @param:
            - playlist_link: Spotify playlist link
        @return:
            - playlist_info: dictionary containing playlist details
                - playlist_id
                - title
                - description
                - image_url
            - song_panda: dataframe containing song details
                - song_title
                - song_id
                - song_uri
                - artists
                - artist_uris
                - popularity
                - danceability
                - energy
                - key
                - loudness
                - mode
                - speechiness
                - acousticness
                - instrumentalness
                - liveness
                - valence
                - tempo
                - duration_ms
                - time_signature
                - genres
        """
        # Get playlist ID from the provided link
        playlist_id = playlist_link.split('/')[-1]

        # Get playlist details using the Spotify Web API
        response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=self.headers)

        if response.status_code == 200:
            playlist_data = response.json()
        else:
            print(f"Error: {response.status_code}")
            return None

        # General playlist details
        playlist_info = {
            'playlist_id': playlist_data['id'],
            'title': playlist_data['name'],
            'description': playlist_data['description'],
            'image_url': playlist_data['images'][0]['url'] if playlist_data['images'] else None
        }

        # Create dataframe of audio features for each song in playlist
        song_df = []
        for track in playlist_data['tracks']['items']:

            # Get genres for each artist in song
            genres = []
            artists = [artist['id'] for artist in track['track']['artists']]
            artists_uri_string = ",".join(artists)
            several_artists_response = requests.get(f'https://api.spotify.com/v1/artists?ids={artists_uri_string}', headers=self.headers)
            if several_artists_response.status_code == 200:
                several_artists_data = several_artists_response.json()
                print(several_artists_data)
                for artist in several_artists_data['artists']:
                    genres.extend(artist['genres'])


            # Get song audio features
            song_uri = track['track']['uri'].split(':')[-1]
            song_response = requests.get(f'https://api.spotify.com/v1/audio-features/{song_uri}', headers=self.headers)

            if song_response.status_code != 200:
                print(f"Error: {song_response.status_code}")
                return None
            
            song_data_json = song_response.json()
            song_row = {
                'song_title': track['track']['name'],
                'song_id': song_data_json['id'],
                'song_uri' : track['track']['uri'],
                'artists' : ', '.join([artist['name'] for artist in track['track']['artists']]),
                'artist_uris' : ', '.join([artist['uri'] for artist in track['track']['artists']]),
                'popularity' : track['track']['popularity'],
                'danceability': song_data_json['danceability'],
                'energy': song_data_json['energy'],
                'key': song_data_json['key'],
                'loudness': song_data_json['loudness'],
                'mode': song_data_json['mode'],
                'speechiness': song_data_json['speechiness'],
                'acousticness': song_data_json['acousticness'],
                'instrumentalness': song_data_json['instrumentalness'],
                'liveness': song_data_json['liveness'],
                'valence': song_data_json['valence'],
                'tempo': song_data_json['tempo'],
                'duration_ms': song_data_json['duration_ms'],
                'time_signature': song_data_json['time_signature'],
                'genres': genres if genres else None
            }
            
            song_df.append(song_row)
        
        song_panda = pd.DataFrame(song_df)
        return playlist_info, song_panda
    
if __name__ == '__main__':
    username = 'nrkjbdqb3gwxlzypjce5vvqra'
    redirect_uri = 'http://localhost:3000/callback'
    playlistify = SpotifyAnalyzer(username, redirect_uri)

    playlist_info, song_panda = playlistify.get_playlist_details('https://open.spotify.com/playlist/6B68YiiaqNNQRQpNuDgPJA?si=b3ec1829ef1645c8')
    print(playlist_info)
    song_panda.to_csv('smule_panda.csv', index=False)

    # playlistify.get_spotipy_playlist('https://open.spotify.com/playlist/6B68YiiaqNNQRQpNuDgPJA?si=b3ec1829ef1645c8')