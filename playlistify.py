# import libraries
import json

import requests
import pandas as pd
from pandas import json_normalize
import spotipy
import spotipy.util as util

from spotifysecrets import *


class SpotifyAnalyzer:
    # create SpotifyAnalyzer instance
    def __init__(self, username, redirect_uri='http://localhost:8888/callback', scope=["playlist-read-private"]):
        
        self.token = None
        self.sp = None
        self.username = username
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.generate_token()
        
    # set/modify scope
    def set_scope(self, scope):
        self.scope = scope
        self.generate_token()
        
    
    def generate_token(self):
        token = util.prompt_for_user_token(
            self.username, 
            self.scope, 
            client_id=CLIENT_ID, 
            client_secret=CLIENT_SECRET, 
            redirect_uri=self.redirect_uri
        )
        if token:
            self.sp = spotipy.Spotify(auth=token)
            self.token = token
        else:
            print(f"Cant get token for {self.username}")

        
    # Print top artists
    def get_top_artists(self):
        # Get request for top artists
        headers = {
            'Authorization': 'Bearer ' + self.token
        }
        params = {
            "limit": 20,  # number of artists to retrieve
            "time_range": "medium_term"  # time range for top artists (short_term, medium_term, long_term)
        }
        response = requests.get('https://api.spotify.com/v1/me/top/artists', headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
        else:
            print(f"Error: {response.status_code}")

        # ANALYSIS
        data_str  = json.dumps(data, indent=2)
        data_dict = json.loads(data_str)


        top_artists = data['items']

        for artist in top_artists:
            artists = artist['name']
            print(f"{artist['name']} Popularity: {artist['popularity']} Genres: {artist['genres']}")

        return
    
    # Print available genre seeds
    def get_genre_seeds(self):
        headers = {
            'Authorization': 'Bearer ' + self.token
        }
        response2 = requests.get('https://api.spotify.com/v1/recommendations/available-genre-seeds', headers=headers)

        if response2.status_code == 200:
            data2 = response2.json()
        else:
            print(f"Error: {response2.status_code}")

        data2_str = json.dumps(data2, indent=2)
        print(data2_str)

    # Get playlist details
    def get_playlist_details(self, playlist_link):
        # get playlist ID from the provided link
        playlist_id = playlist_link.split('/')[-1]

        # get playlist details using the Spotify Web API
        headers = {
            'Authorization': 'Bearer ' + self.token
        }
        response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=headers)

        if response.status_code == 200:
            playlist_data = response.json()
        else:
            print(f"Error: {response.status_code}")
            return None

        # Extract relevant details from playlist data
        def extract_track_info(track):
            song_title = track['track']['name']
            artists = ', '.join([artist['name'] for artist in track['track']['artists']])
            uri = track['track']['uri']
            popularity = track['track']['popularity']
            return song_title, artists, uri, popularity

        playinfo = []
        for track in playlist_data['tracks']['items']:
            # song_title, artists, uri, popularity = extract_track_info(track)
            # print(f"{song_title} - {artists}")
            playlist_info = {
                'playlist_id': playlist_data['id'],
                'title': playlist_data['name'],
                'description': playlist_data['description'],
                'image_url': playlist_data['images'][0]['url'] if playlist_data['images'] else None,
                'song_title' : track['track']['name'],
                'artists' : ', '.join([artist['name'] for artist in track['track']['artists']]),
                'artist_uris' : ', '.join([artist['uri'] for artist in track['track']['artists']]),
                'popularity' : track['track']['popularity'],
                'uri' : track['track']['uri']
            }
            playinfo.append(playlist_info)
        
        df = pd.DataFrame(playinfo)

        songinfo = []
        for index, row in df.iterrows():
            song_uri = row['uri'].split(':')[-1]
            artists = row['artist_uris'].split(', ')

            # Get genres for each artist in song
            genres = []
            for artist in artists:
                artist_uri = artist.split(':')[-1]
                genre_response = requests.get(f'https://api.spotify.com/v1/artists/{artist_uri}', headers=headers)
                if genre_response.status_code == 200:
                    genre_data = genre_response.json()
                    genres.extend(genre_data['genres'])

            song_response = requests.get(f'https://api.spotify.com/v1/audio-features/{song_uri}', headers=headers)

            if song_response.status_code == 200 and genre_response.status_code == 200:
                song_data_json = song_response.json()
                song_data = {
                    'song_title': row['song_title'],
                    'song_id': song_data_json['id'],
                    'artists' : row['artists'],
                    'popularity' : row['popularity'],
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
                    'genres': genres
                }
                genre_data = genre_response.json()

                songinfo.append(song_data)
            else:
                print(f"Error: {song_response.status_code}")
                return None
        
        songdf = pd.DataFrame(songinfo)
        # Return playlist details, list of song detail dataframes, list of song titles
        return df, songdf, playlist_data['name']


    # Get playlist details in SQL format
    def create_playlist_sql(self, playlist_links):
        # Define headers
        headers = {
            'Authorization': 'Bearer ' + self.token
        }

        # get playlist ID from the provided link
        playlist_ids, titles, descriptions, imgurls, uris = [], [], [], [], []
        for link in playlist_links:
            playlist_id = link.split('/')[-1]

            # Get playlist details using the Spotify Web API
            response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=headers)

            if response.status_code == 200:
                playlist_data = response.json()
            else:
                print(f"Error: {response.status_code}")
                return None

            playlist_ids.append(playlist_data['id'])
            titles.append(playlist_data['name'])
            descriptions.append(playlist_data['description'])
            imgurls.append(playlist_data['images'][0]['url'] if playlist_data['images'] else None)
            uris.append(playlist_data['uri'])
        
        playinfo = {
            'playlist_id': playlist_ids,
            'title': titles,
            'description': descriptions,
            'image_url': imgurls,
            'uri': uris
        }
        
        return pd.DataFrame(playinfo)

    # Gets playlist song details in SQL format
    def create_song_sql(self, playlist_link):
        # get playlist ID from the provided link
        playlist_id = playlist_link.split('/')[-1]

        # get playlist details using the Spotify Web API
        headers = {
            'Authorization': 'Bearer ' + self.token
        }
        response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=headers)

        if response.status_code == 200:
            playlist_data = response.json()
        else:
            print(f"Error: {response.status_code}")
            return None

        # Extract relevant details from playlist data
        def extract_track_info(track):
            song_title = track['track']['name']
            artists = ', '.join([artist['name'] for artist in track['track']['artists']])
            uri = track['track']['uri']
            popularity = track['track']['popularity']
            return song_title, artists, uri, popularity

        playinfo = []
        for track in playlist_data['tracks']['items']:
            # song_title, artists, uri, popularity = extract_track_info(track)
            # print(f"{song_title} - {artists}")
            playlist_info = {
                'playlist_id': playlist_data['id'],
                'title': playlist_data['name'],
                'description': playlist_data['description'],
                'image_url': playlist_data['images'][0]['url'] if playlist_data['images'] else None,
                'song_title' : track['track']['name'],
                'artists' : ', '.join([artist['name'] for artist in track['track']['artists']]),
                'artist_uris' : ', '.join([artist['uri'] for artist in track['track']['artists']]),
                'popularity' : track['track']['popularity'],
                'uri' : track['track']['uri']
            }
            playinfo.append(playlist_info)
        
        df = pd.DataFrame(playinfo)

        songinfo = []
        for index, row in df.iterrows():
            song_uri = row['uri'].split(':')[-1]
            artists = row['artist_uris'].split(', ')

            # Get genres for each artist in the song
            genres = []
            for artist in artists:
                artist_uri = artist.split(':')[-1]
                genre_response = requests.get(f'https://api.spotify.com/v1/artists/{artist_uri}', headers=headers)
                if genre_response.status_code == 200:
                    genre_data = genre_response.json()
                    genres.extend(genre_data['genres'])

            song_response = requests.get(f'https://api.spotify.com/v1/audio-features/{song_uri}', headers=headers)

            if song_response.status_code == 200:
                song_data_json = song_response.json()
            else:
                print(f"Error: {song_response.status_code}")
                return None
            
            # Construct the features tuple
            features_tuple = (
                song_data_json['acousticness'],
                song_data_json['danceability'],
                song_data_json['duration_ms'],
                song_data_json['energy'],
                song_data_json['instrumentalness'],
                song_data_json['key'],
                song_data_json['liveness'],
                song_data_json['loudness'],
                song_data_json['mode'],
                song_data_json['speechiness'],
                song_data_json['tempo'],
                song_data_json['time_signature'],
                song_data_json['valence']
            )
            song_data = {
                'song_id': song_data_json['id'],
                'title': row['song_title'],
                'features': features_tuple,
                'popularity': row['popularity'],
                'genres': genres
            }
            songinfo.append(song_data)
        
        songdf = pd.DataFrame(songinfo)

        # Return playlist details, list of song detail dataframes, list of song titles
        return df, songdf, playlist_data['name']
    
    # Get artist details in SQL format
    def create_artist_sql(self, playlist_link):
        # get playlist ID from the provided link
        playlist_id = playlist_link.split('/')[-1]

        # get playlist details using the Spotify Web API
        headers = {
            'Authorization': 'Bearer ' + self.token
        }
        response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=headers)

        if response.status_code == 200:
            playlist_data = response.json()
        else:
            print(f"Error: {response.status_code}")
            return None

        # Extract relevant details from playlist data
        def extract_artists(track):
            #artists = [artist['name'] for artist in track['track']['artists']]
            split_uri = lambda uri: uri.split(':')[-1]
            artist_uris = [split_uri(artist['uri']) for artist in track['track']['artists']]
            return artist_uris

        artinfo = []
        #artist_ids, names, members, imgurls, genres, popularities = [], [], [], [], [], []
        artists = []
        for track in playlist_data['tracks']['items']:
            artists.extend(extract_artists(track))
        artists = list(set(artists))
        for artist_uri in artists:
            artist_response = requests.get(f'https://api.spotify.com/v1/artists/{artist_uri}', headers=headers)
            if artist_response.status_code == 200:
                artist_data = artist_response.json()
            else:
                print(f"Error: {artist_response.status_code}")
                return None
            art_data = {
                'artist_id': artist_data['id'],
                'name': artist_data['name'],
                'image_url': artist_data['images'][0]['url'] if artist_data['images'] else None,
                'genres': artist_data['genres'],
                'popularity': artist_data['popularity']
            }
            artinfo.append(art_data)
        return pd.DataFrame(artinfo)


def main():

    # credentials
    username = 'nrkjbdqb3gwxlzypjce5vvqra'
    redirect_uri = 'http://localhost:8888/callback'

    # list of predefined scopes
    scope = [
        'user-top-read',
        'user-read-recently-played',
        'user-read-currently-playing', 
        'playlist-read-private', 
        'playlist-read-collaborative', 
        'playlist-modify-private', 
        'playlist-modify-public', 
        'user-library-read'
    ]

    sp = SpotifyAnalyzer(username, redirect_uri)
    # sp.get_top_artists()
    # sp.get_genre_seeds()
    
    # df, songdf, playlist_name = sp.get_playlist_details('https://open.spotify.com/playlist/1W7ZTOHtVIcA3Js5sEzNZV?si=302c6798a03d4b07')
    # df.to_csv(f'data/{playlist_name}.csv', index=False)
    # songdf.to_csv(f'data/{playlist_name}_songs.csv', index=False)

    # df, songdf, playlist_name = sp.create_song_sql('https://open.spotify.com/playlist/1W7ZTOHtVIcA3Js5sEzNZV?si=302c6798a03d4b07')
    # songdf.to_csv(f'data/{playlist_name}_songs_SQL.csv', index=False)

    playlist_links = [
        'https://open.spotify.com/playlist/3cjYbN4XilLifi50NqfHCE?si=6ec0064da63b4077', 
        'https://open.spotify.com/playlist/37i9dQZF1DZ06evO1IPOOk?si=1ac5922b9b3a498d', 
        'https://open.spotify.com/playlist/1W7ZTOHtVIcA3Js5sEzNZV?si=302c6798a03d4b07',
        'https://open.spotify.com/playlist/6WOBAYupbzo9MNfJSzlVC4?si=084b31cbcd33436e',
        'https://open.spotify.com/playlist/4mmb4O8bso8D4wraSEl69G?si=9b229a44d14d4094',
        'https://open.spotify.com/playlist/08PBkNMTE5LTpDjDcaG5Eo?si=b241d410e3f14f73',
        'https://open.spotify.com/playlist/4ekzhQpXq310TTRzn5oR7B?si=b4c2540ac7d74265',
        'https://open.spotify.com/playlist/3WN0EcRKtMgOm6NLFm27Sy?si=d755817bc8004241',
        'https://open.spotify.com/playlist/1ZjT1DCZApRMzTmIJNt56A?si=2f35479fe7d147b9',
        'https://open.spotify.com/playlist/6B68YiiaqNNQRQpNuDgPJA?si=7e2cfc34d4a04c76'
    ]
    # playsql = sp.create_playlist_sql(playlist_links)
    # playsql.to_csv('data/playlists_SQL.csv', index=False)

    artsql = sp.create_artist_sql(playlist_links[2])
    artsql.to_csv('data/artists_SQL.csv', index=False)

if __name__ == "__main__":
    main()