# Part 4: Object Oriented Features

### PostgreSQL information

- **Account:** ssh2198
- **Database Host:** 35.212.75.104
- **URL:** [http://34.139.227.109:8111/](http://34.139.227.109:8111/)

## Original Project Requirements
I already satisfied 3 of the additions in my Part 3:

1. **Text attribute** - The `comment` attribute in the `Rate` table is a **text** **attribute** which accommodates any kind of long review people would want to leave on a given playlist.
2. **Array attribute** - The `genres` attribute in the `Song` table is an **array attribute** which stores all the genres a particular `Song` is associated with.
3. **Composite attribute** - The `features` attribute in the `Song` table is a **composite attribute** which stores all the different audio features associated with a song. These include:
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

So, after checking with my project mentor I decided to expand on the search/browse functionality by focusing on the **genres** feature more heavily.

# New additions for Part 4
## Genre autocomplete
![Kapture 2024-04-21 at 02.57.35.gif](Part%204%20README%2049548b13c8864e84961d37aff63086c2/Kapture_2024-04-21_at_02.57.35.gif)

To help users discover genres they may not previously know about (permanent wave?) I implemented an search autocomplete function with JQuery which queries the database with each new character input.

- We unnest the `genres` array attribute in the `Song` table to expand it into individual rows on which we can compare against as a subquery.
- We return the top ten results where the beginning matches (case-insensitive) to the given input string.

### **routes.py: autocomplete_genres()**
```sql
SELECT DISTINCT genre
FROM (
    SELECT unnest(genres) AS genre
    FROM Song
) AS subquery
WHERE genre ILIKE :query_prefix 
LIMIT 10 
```

If no input is provided, the autocomplete suggests the top 10 most frequently appearing genres in the database.

```sql
SELECT genre, COUNT(*) AS count
FROM (
	  SELECT unnest(genres) AS genre
	  FROM Song
) AS subquery
GROUP BY genre
ORDER BY count DESC
LIMIT 10
```

### browse.html: JQuery scripting
I turned the results of the database query into JSON format, which allows me to use a JS `<script>` to parse the data and use it to populate the search bar.

```sql
<script>
  $(document).ready(function() {
    $('#genre_filter').select2({
      ajax: {
        url: '/autocomplete_genres',
        dataType: 'json',
        delay: 250,
        data: function (params) {
          return {
            term: params.term // search term
          };
        },
        processResults: function (data) {
          return {
            results: $.map(data.genres, function (item) {
              return {
                text: item,
                id: item
              }
            })
          };
        },
        cache: true
      },
      minimumInputLength: 0,
      width: 'resolve'
    });
  });
</script>
```

## Genre search: Playlists
Searching returns all playlists containing any of the specified genres!

![Screenshot 2024-04-21 at 3.09.01 AM.png](Part%204%20README%2049548b13c8864e84961d37aff63086c2/Screenshot_2024-04-21_at_3.09.01_AM.png)

The genres in bright blue reflect those genres which are present in the search query. The ones in light-grey are the non-matching, but most frequently occurring genres in the playlist. This way, users can get a sense of the overall ‘genre’ of the playlist, and discover new genres they may not have previously known about.

### **routes.py: filter_genres()**
I achieved this by iterating through and counting the frequency of the different genres of each song in the playlist. 

**SQL query**
```sql
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
```

The complexity of this query comes from the `union` which combines *matching_genres* which match the query, as well as the *top_genres*, which are the top few, most frequently occurring genres across all songs within the playlist.

- **Matching_genres** - We *unnest* the `genres` array and treat them as separate rows, and we *cross join* them with the corresponding playlist_id of the overarching playlist.
- **Top_genres** - We get the count of how many times each genre appears in a song in a given playlist, utilizing *cross join* again to associate each with a particular genre ‘row,’ and then limiting the results to only three (for brevity).

We then aggregate the result of these ‘rows’ into one array with **`array_agg`, and then join together the rest of the relevant information to be displayed in the cards.

```python
# Turn each row into array of tuples (genre, is_selected)
search_results["genres"] = search_results["genres"].apply(lambda x: [(genre, genre in genres) for genre in x])
search_results["genres"] = search_results["genres"].apply(lambda genres: [genre for genre in genres if genre[0] is not None])
```

And in order to differentiate between which songs were a result of the query or not, I turned each into a tuple, where the first item contains the genre, and the second item contains a boolean of whether it was selected from the query or not. This is used to help process the data in the front end.

The second line of code is just to filter out cases in which the most common genre was displayed as “None.” It stems from the consequence that if a song has no associated genres, it is returned as a “None” genre.

## Genre search: Songs
Below the returned playlists, we have a result showing the matching genres for a particular song, alongside the rest of its associated genres.

![Screenshot 2024-04-21 at 4.30.27 AM.png](Part%204%20README%2049548b13c8864e84961d37aff63086c2/Screenshot_2024-04-21_at_4.30.27_AM.png)

### **routes.py: filter_genres()**
It uses a similar logic to the playlist query, but it reflects an earlier attempt in which I tried to process the data without aggregating the genres into an array. 

```sql
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
```

**Array-type processing (routes.py)**
Array attributes are formatted as strings when they are retrieved from the PostgreSQL database (*some* of the time… other times it’s a nested list…). As a result, I had to do some processing before I could easily display it in the website.

```python
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
```

Again, I turn each genre into a tuple, where the first item contains the genre, and the second item contains a boolean of whether it was selected from the query or not. 

Clearly, it was much easier to process the data when I aggregated and returned the genres as an array. I kept the logic in the `Song` genre search query out of a lack of time (since it still works), but it proves illustrative in demonstrating the significance of the `ARRAY_AGG` function.

## Browse.html: Default behavior
By default, `browse.html` just returns all playlists in the database, and the 10 songs which appear most frequently across all playlists.

![Screenshot 2024-04-21 at 10.24.20 AM.png](Part%204%20README%2049548b13c8864e84961d37aff63086c2/Screenshot_2024-04-21_at_10.24.20_AM.png)

![Screenshot 2024-04-21 at 10.07.45 AM.png](Part%204%20README%2049548b13c8864e84961d37aff63086c2/Screenshot_2024-04-21_at_10.07.45_AM.png)

### routes.py: filter_genres
**Display all uploaded playlists**
The SQL logic to display **all uploaded playlists** used a simplified version of the logic to search for playlists by genre, in order to correctly parse through the array-type attribute.

```sql
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
```

**Display top 10 most frequently appearing songs**
In order to sort the songs by frequency, I had to group by the `song_id` attribute in `PlaylistSong` within a *subquery* so that I could still sort the full database query by `song_counts`.

- `Playlist_users` also had to be grouped together in a subquery in order to associate songs to a particular user_id without having to group it within the `song_counts` subquery.

```sql
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
```

## Testing the queries
You can test the functionality of these queries by going to the “Browse” page on the website and playing around with viewing the different search/autocomplete functionalities!

Alternatively, you can copy and paste these identical queries into the database directly:

### Autocomplete: Genres that begin with “b”
```sql
SELECT DISTINCT genre
FROM (
    SELECT unnest(genres) AS genre
    FROM Song
) AS subquery
WHERE genre ILIKE 'b%'
LIMIT 10;
```

### Autocomplete: Default behavior
```sql
SELECT genre, COUNT(*) AS count
FROM (
	  SELECT unnest(genres) AS genre
	  FROM Song
) AS subquery
GROUP BY genre
ORDER BY count DESC
LIMIT 10
```

### Search genres: ['shoegaze', 'permanent wave']
```sql
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
            AND genre = ANY(ARRAY['shoegaze', 'permanent wave'])
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
WHERE genre = ANY(ARRAY['shoegaze', 'permanent wave']);
```

### Search genres: Default behavior
```sql
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
) AS Song ON PlaylistSong.song_id = Song.song_id;
```

### Filter songs: ['shoegaze', 'permanent wave']
```sql
SELECT Song.title, Song.album_url, ARRAY_AGG(Artist.name) as artists, Song.genres, PlaylistSong.playlist_id, Users.name
FROM Song
INNER JOIN SongArtist ON Song.song_id = SongArtist.song_id
INNER JOIN Artist ON SongArtist.artist_id = Artist.artist_id
INNER JOIN PlaylistSong ON Song.song_id = PlaylistSong.song_id
INNER JOIN HasPlaylist ON HasPlaylist.playlist_id = PlaylistSong.playlist_id
INNER JOIN Users ON HasPlaylist.user_id = Users.user_id
CROSS JOIN UNNEST(Song.genres) as genre
WHERE genre = ANY(ARRAY['shoegaze', 'permanent wave'])
GROUP BY Song.title, Song.album_url, Song.genres, PlaylistSong.playlist_id, Users.name
```

### Filter songs: Default behavior
```sql
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
LIMIT 10;
```