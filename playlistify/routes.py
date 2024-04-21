from flask import Blueprint, render_template, g, request, redirect, url_for, session, jsonify, abort
import pandas as pd
import os, json, ast
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
        session['playlist_id'] = playlist_id
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

        # Helper function to comma-join
        def join_genres(genres):
            if isinstance(genres, list):
                return ', '.join(genres)
            else:
                return genres
            
        song_data['genres'] = song_data['genres'].apply(join_genres)
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


        # Insert data into database if it doesn't already exist
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
                    INSERT INTO Song (song_id, title, features, popularity, genres, album_url)
                    VALUES (:song_id, :title, :features, :popularity, ARRAY[:genres], :album_url) 
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
                    'genres': row['genres'],
                    'album_url': row['album_url']
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

            # Insert Artist
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

                # Insert PlaylistArtists
                insert_song_artist = text("""INSERT INTO PlaylistArtists (playlist_id, artist_id) 
                                      VALUES (:playlist_id, :artist_id) 
                                      ON CONFLICT (playlist_id, artist_id) DO NOTHING""")
                params = {
                    'playlist_id': playlist_data['playlist_id'],
                    'artist_id': row['artist_id']
                }
                conn.execute(insert_song_artist, params)
                conn.commit()
                print(f'inserted playlist_artist: ({playlist_data["playlist_id"]}, {row["name"]})')


    else:
        print("Error uploading playlist to database")
    
    return redirect(url_for('main.playlist'))


@main.route('/browse')
def browse():
    return render_template('browse.html', playlists=None, songs=None, query=None)


@main.route('/search')
def search():
    return render_template('search.html')

# new to part 4
@main.route('/filter_genres', methods=['GET'])
def filter_genres():
    search_results = []
    song_search_results = []
    genres = []
    with my_engine.connect() as conn:
        if (request.args.get('genre_filter[]') is not None):
            genres = request.args.getlist('genre_filter[]')
            search_query = text("""
                SELECT DISTINCT Users.name, Users.image_url, Playlist.playlist_id, Playlist.image_url, Playlist.title, Playlist.description,
                (
                    SELECT ARRAY_AGG(genre)
                    FROM (
                        SELECT genre
                        FROM (
                            SELECT genre
                            FROM Song
                            INNER JOIN PlaylistSong ON Song.song_id = PlaylistSong.song_id
                            CROSS JOIN UNNEST(Song.genres) as genre
                            WHERE PlaylistSong.playlist_id = Playlist.playlist_id
                            AND genre = ANY(:genres)
                        ) AS matching_genres
                        UNION
                        SELECT genre
                        FROM (
                            SELECT genre, COUNT(*) as count
                            FROM Song
                            INNER JOIN PlaylistSong ON Song.song_id = PlaylistSong.song_id
                            CROSS JOIN UNNEST(Song.genres) as genre
                            WHERE PlaylistSong.playlist_id = Playlist.playlist_id
                            AND genre IS NOT NULL
                            GROUP BY genre
                            ORDER BY count DESC
                            LIMIT 3
                        ) AS top_genres
                    ) AS union_subquery
                ) AS genres
                FROM HasPlaylist
                INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
                INNER JOIN Playlist ON HasPlaylist.playlist_id = Playlist.playlist_id
                INNER JOIN PlaylistSong ON Playlist.playlist_id = PlaylistSong.playlist_id
                INNER JOIN Song ON Song.song_id = PlaylistSong.song_id
                CROSS JOIN UNNEST(Song.genres) as genre
                WHERE genre = ANY(:genres)
            """)
            params = {'genres': genres}
            cursor = conn.execute(search_query, params)
            for result in cursor:
                search_results.append(result)
            
            song_search_query = text("""
                SELECT Song.title, Song.album_url, ARRAY_AGG(Artist.name) as artists, Song.genres, PlaylistSong.playlist_id, Users.name
                FROM Song
                INNER JOIN SongArtist ON Song.song_id = SongArtist.song_id
                INNER JOIN Artist ON SongArtist.artist_id = Artist.artist_id
                INNER JOIN PlaylistSong ON Song.song_id = PlaylistSong.song_id
                INNER JOIN HasPlaylist ON HasPlaylist.playlist_id = PlaylistSong.playlist_id
                INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
                CROSS JOIN UNNEST(Song.genres) as genre
                WHERE genre = ANY(:genres)
                GROUP BY Song.title, Song.album_url, Song.genres, PlaylistSong.playlist_id, Users.name
            """)
            params = {'genres': genres}
            cursor = conn.execute(song_search_query, params)
            for result in cursor:
                song_search_results.append(result[0:6])
        else:
            search_query = text("""
                SELECT DISTINCT Users.name, Users.image_url, Playlist.playlist_id, Playlist.image_url, Playlist.title, Playlist.description,
                (
                    SELECT ARRAY_AGG(genre)
                    FROM (
                        SELECT UNNEST(genres) as genre, COUNT(*) as count
                        FROM Song
                        INNER JOIN PlaylistSong ON Song.song_id = PlaylistSong.song_id
                        WHERE PlaylistSong.playlist_id = Playlist.playlist_id
                        GROUP BY genre
                        ORDER BY count DESC
                        LIMIT 3
                    ) AS subquery
                ) AS genres
                FROM HasPlaylist
                INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
                INNER JOIN Playlist ON HasPlaylist.playlist_id = Playlist.playlist_id
                INNER JOIN PlaylistSong ON Playlist.playlist_id = PlaylistSong.playlist_id
                INNER JOIN (
                    SELECT song_id, UNNEST(genres) as genre
                    FROM Song
                ) AS Song ON PlaylistSong.song_id = Song.song_id
            """)
            cursor = conn.execute(search_query)
            for result in cursor:
                search_results.append(result)
            
            song_search_query = text("""
                WITH song_counts AS (
                    SELECT song_id, COUNT(*) as playlist_count
                    FROM PlaylistSong
                    GROUP BY song_id
                ),
                playlist_users AS (
                    SELECT playlist_id, user_id
                    FROM HasPlaylist
                )
                SELECT Song.title, Song.album_url, ARRAY_AGG(Artist.name) as artists, Song.genres, Users.name, song_counts.playlist_count
                FROM Song
                INNER JOIN song_counts ON Song.song_id = song_counts.song_id
                INNER JOIN SongArtist ON Song.song_id = SongArtist.song_id
                INNER JOIN Artist ON SongArtist.artist_id = Artist.artist_id
                INNER JOIN PlaylistSong ON Song.song_id = PlaylistSong.song_id
                INNER JOIN playlist_users ON PlaylistSong.playlist_id = playlist_users.playlist_id
                INNER JOIN Users ON playlist_users.user_id = Users.user_id
                GROUP BY Song.title, Song.album_url, Song.genres, Users.name, song_counts.playlist_count
                ORDER BY song_counts.playlist_count DESC
                LIMIT 10
            """)
            cursor = conn.execute(song_search_query)
            for result in cursor:
                song_search_results.append(result[0:6])

    # Process playlist search results
    if search_results:
        search_results = pd.DataFrame(search_results, columns=['user_name', 'user_img', 'playlist_id', 'playlist_img', 'playlist_title', 'playlist_desc', 'genres'])

    # Turn each row into array of tuples (genre, is_selected)
    search_results["genres"] = search_results["genres"].apply(lambda x: [(genre, genre in genres) for genre in x])
    search_results["genres"] = search_results["genres"].apply(lambda genres: [genre for genre in genres if genre[0] is not None])

    # Process song search results
    song_search_results = pd.DataFrame(song_search_results, columns=['song_title', 'album_url', 'artists', 'genres', 'playlist_id', 'user_name'])

    # If genres are stored as strings, convert them back to lists
    song_search_results["genres"] = song_search_results["genres"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)

    # Help unpack genres from nested lists, NoneType errors, and duplicates
    def process_genres(x):
        if x is None:
            return []
        else:
            result = []
            for sublist in x:
                if sublist is not None:
                    for item in sublist:
                        if item is not None:
                            result.append(item)
            return list(set(result)) # remove duplicates

    song_search_results["genres"] = song_search_results["genres"].apply(process_genres)

    # Turn each genre into a tuple (genre, is_selected)
    song_search_results["genres"] = song_search_results["genres"].apply(lambda x: [(genre, genre in genres) for genre in x])

    return render_template('browse.html', playlists=search_results, songs=song_search_results, query=genres)

@main.route('/search_results', methods=['GET'])
def search_results():
    if request.method == 'GET':
        search_term = request.args.get('query')
        search_type = request.args.get('search_type')

        if search_type == 'genre_filter':
            with my_engine.connect() as conn:
                search_query = text("""
                    SELECT DISTINCT Users.name, Playlist.playlist_id, Playlist.title
                    FROM HasPlaylist
                    INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
                    INNER JOIN Playlist ON HasPlaylist.playlist_id = Playlist.playlist_id
                    INNER JOIN PlaylistSong ON Playlist.playlist_id = PlaylistSong.playlist_id
                    INNER JOIN Song ON PlaylistSong.song_id = Song.song_id
                    WHERE :query = ANY(Song.genres)
                """)
                params = {'query': search_term}
                cursor = conn.execute(search_query, params)
                search_results = []
                for result in cursor:
                    search_results.append(result[0:3])
                search_results = pd.DataFrame(search_results, columns=['user_name', 'playlist_id', 'title'])
            return render_template('search_results.html', search_results=search_results, query=search_term, search_type='genre')

        with my_engine.connect() as conn:
            if search_type == 'playlist':
                search_query = text("""
                    SELECT DISTINCT Users.name, Playlist.playlist_id, Playlist.title
                    FROM HasPlaylist
                    INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
                    INNER JOIN Playlist ON HasPlaylist.playlist_id = Playlist.playlist_id
                    WHERE Playlist.title iLIKE :query
                """)
            elif search_type == 'artist':
                search_query = text("""
                    SELECT DISTINCT Users.name, Playlist.playlist_id, Playlist.title
                    FROM HasPlaylist
                    INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
                    INNER JOIN Playlist ON HasPlaylist.playlist_id = Playlist.playlist_id
                    INNER JOIN PlaylistArtists ON Playlist.playlist_id = PlaylistArtists.playlist_id
                    INNER JOIN Artist ON PlaylistArtists.artist_id = Artist.artist_id
                    WHERE Artist.name iLIKE :query
                """)
            elif search_type == 'song':
                search_query = text("""
                    SELECT DISTINCT Users.name, Playlist.playlist_id, Playlist.title
                    FROM HasPlaylist
                    INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
                    INNER JOIN Playlist ON HasPlaylist.playlist_id = Playlist.playlist_id
                    INNER JOIN PlaylistSong ON Playlist.playlist_id = PlaylistSong.playlist_id
                    INNER JOIN Song ON PlaylistSong.song_id = Song.song_id
                    WHERE Song.title iLIKE :query
                """)
            
            params = {'query': f'%{search_term}%'}
            cursor = conn.execute(search_query, params)
            search_results = []
            for result in cursor:
                search_results.append(result[0:3])
            search_results = pd.DataFrame(search_results, columns=['user_name', 'playlist_id', 'title'])
            return render_template('search_results.html', search_results=search_results, query=search_term, search_type=search_type)


@main.route('/autocomplete_genres', methods=['GET'])
def autocomplete_genres():
    query = request.args.get('term')  # Get the query string from the request
    if query:
        # Query the database for genres matching the input
        with my_engine.connect() as conn:
            genres_query = text("""
                SELECT DISTINCT genre
                FROM (
                    SELECT unnest(genres) AS genre
                    FROM Song
                ) AS subquery
                WHERE genre ILIKE :query_prefix  -- Case-insensitive match for genres starting with the input
                LIMIT 10  -- Limit the number of results to 10
            """)
            cursor = conn.execute(genres_query, {'query_prefix': f'{query}%'})
            genres = [row[0] for row in cursor.fetchall()]  # Extract genres from query result
        # print(genres)
        return jsonify(genres=genres)  # Return genres as JSON response
    else:
        # Query the database for the top 10 most frequent genres
        with my_engine.connect() as conn:
            genres_query = text("""
                SELECT genre, COUNT(*) AS count
                FROM (
                    SELECT unnest(genres) AS genre
                    FROM Song
                ) AS subquery
                GROUP BY genre
                ORDER BY count DESC
                LIMIT 10  -- Limit the number of results to 10
            """)
            cursor = conn.execute(genres_query)
            genres = [row[0] for row in cursor.fetchall()]  # Extract genres from query result
        return jsonify(genres=genres)  # Return genres as JSON response


# moot
@main.route('/search_genres/<query>')
def search_genres(query):
    with my_engine.connect() as conn:
        search_query = text("""
            SELECT DISTINCT Users.name, Playlist.playlist_id, Playlist.title
            FROM HasPlaylist
            INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
            INNER JOIN Playlist ON HasPlaylist.playlist_id = Playlist.playlist_id
            INNER JOIN PlaylistSong ON Playlist.playlist_id = PlaylistSong.playlist_id
            INNER JOIN Song ON PlaylistSong.song_id = Song.song_id
            WHERE Song.genres @> ARRAY[:query]
        """)
        params = {'query': query}
        cursor = conn.execute(search_query, params)
        search_results = []
        for result in cursor:
            search_results.append(result[0:3])
        search_results = pd.DataFrame(search_results, columns=['user_name', 'playlist_id', 'title'])
    return render_template('search_results.html', search_results=search_results, query=query, search_type='genre')

@main.route('/test')
def test():
    return render_template('test.html')

# not yet working... many considerations.........
@main.route('/filter_features')
def search_features():
    feature_to_search = request.args.get('feature')
    sort_order = 'DESC' if request.args.get('desc_switch') == 'on' else 'ASC'

    with my_engine.connect() as conn:
        search_query = text(f"""
            SELECT Users.name, Playlist.playlist_id, Playlist.title, AVG(Song.{feature_to_search}) as avg_feature
            FROM HasPlaylist
            INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
            INNER JOIN Playlist ON HasPlaylist.playlist_id = Playlist.playlist_id
            INNER JOIN PlaylistSong ON Playlist.playlist_id = PlaylistSong.playlist_id
            INNER JOIN Song ON PlaylistSong.song_id = Song.song_id
            GROUP BY Playlist.playlist_id, Users.name, Playlist.title
            ORDER BY avg_feature {sort_order}
            LIMIT 10
        """)
        cursor = conn.execute(search_query)
        search_results = []
        for result in cursor:
            search_results.append(result)
        search_results = pd.DataFrame(search_results, columns=['user_name', 'playlist_id', 'title', 'avg_feature'])