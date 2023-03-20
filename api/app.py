from flask import Flask, url_for, session, request, redirect, render_template
from dotenv import load_dotenv, find_dotenv
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import time
import random
import openai
from collections import Counter
from pymongo import MongoClient
import os

load_dotenv(find_dotenv())

password = os.environ.get('password')
openai.api_key = os.environ.get('api_key')

connection_string = f"mongodb+srv://team8bits:{password}@spotifymatched.2u1gxhe.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(connection_string)

dbs = client.list_database_names()

user_info_db = client.user_info
users_top_songs = user_info_db.users_top_songs


# App config
app = Flask(__name__)

app.secret_key = 'SOMETHING-RANDOM'
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

@app.route('/loading')
def loading():
    return render_template("loading.html")



@app.route('/')
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/authorize')
def authorize():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect("/getTracks")

# Checks to see if token is valid and gets a new token if not

@app.route('/logout')
def logout():
    for key in list(session.keys()):
        session.pop(key)
    return "logged out"

@app.route('/getTracks', methods=['GET', 'POST'])
def get_all_tracks():
    session['token_info'], authorized = get_token()
    session.modified = True
    if not authorized:
        return redirect('/')

    if request.method == 'POST':
        token = session.get('token_info').get('access_token')
        pm = Musaic(token)
        user_input = request.form['user_input']
        playlist = get_playlist_from_gpt(user_input,token)
        link, tracks = main(token, playlist, user_input)
        response_body = {
            "link": link,
            "tracks": tracks,
        }
        return render_template("playlist.html", link=link, tracks=tracks)
    return render_template("input_form.html")


def create_spotify_oauth():
    return SpotifyOAuth(
        client_id ='39951c143d3f4fd1b8a4159d349399e8',
        client_secret='58ed9c7f0a7944efbc045a0393459e09',
        redirect_uri=url_for('authorize', _external=True),
        scope=['playlist-modify-private','playlist-modify-public','user-read-email','user-top-read','user-read-recently-played','user-read-private'])


def get_token():
    token_valid = False
    token_info = session.get("token_info", {})

    # Checking if the session already has a token stored
    if not (session.get('token_info', False)):
        token_valid = False
        return token_info, token_valid

    # Checking if token has expired
    now = int(time.time())
    is_token_expired = session.get('token_info').get('expires_at') - now < 60

    # Refreshing token if it has expired
    if (is_token_expired):
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(session.get('token_info').get('refresh_token'))
        
    token_valid = True
    return token_info, token_valid



# Function to get genres from ChatGPT API
def get_playlist_from_gpt(user_input, access_token):
    pm = Musaic(access_token)
    sp = spotipy.Spotify(auth=access_token)
    top_artists = pm.get_top_artists()

    prompt = f"Based on this phrase '{user_input}', give me a list of artists. Pick 3 artists from '{top_artists}' and choose 3 relevant artists not listed."
    response = openai.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=500, n=1, stop=None, temperature=0.7)
    artist_list_text = response.choices[0].text.strip()
    artist_text_lines = artist_list_text.split('\n')
    artist_list = [line.partition('. ')[-1].strip().rstrip('"') for line in artist_text_lines if line]
    artist_list = [line.partition('. ')[-1].strip().replace('"', '') for line in artist_text_lines if line]

    print(artist_list)

    # Convert track names to track IDs
    track_ids = []
    while(len(track_ids) <= 20):
        count = 0
        for count in range(10):
            for artist_name in artist_list:
                if artist_name:  # Check if the artist_name is not empty
                    search_results = sp.search(q=artist_name, type="track", limit=10)
                    random.shuffle(search_results)
                    if search_results["tracks"]["items"]:
                        track_id = search_results["tracks"]["items"][count]["id"]
                        if track_id in track_ids:
                            count+=1
                            print("already in tracks")
                            continue
                        if(len(track_ids) >= 20):
                            return track_ids
                        track_ids.append(track_id)
    print(track_ids)

    return track_ids


def main(access_token,suggested_playlist,user_input):
    sp = spotipy.Spotify(auth=access_token)

    # Get the user's ID
    user_id = sp.me()["id"]

    # Create a playlist
    playlist_name = user_input
    playlist = sp.user_playlist_create(user_id, playlist_name, public=True, description="By Musaic")
    playlist_id = playlist["id"]

    # Add the suggested tracks to the playlist
    sp.playlist_add_items(playlist_id, suggested_playlist)

    # Get the track details
    track_details = [sp.track(track_id) for track_id in suggested_playlist]

    # Return the link to the playlist and track details
    link = playlist["external_urls"]["spotify"]
    return link, track_details

# Function to check if user's Spotify ID is in the database
def is_user_in_database(spotify_id):
    user = user_info_db.users_top_songs.find_one({"spotify_id": spotify_id})
    return user is not None

# Function to store user's Spotify ID and top songs in the database
def store_top_songs_in_database(spotify_id, top_tracks):
    if not is_user_in_database(spotify_id):
        user_data = {
            "spotify_id": spotify_id,
            "top_songs": top_tracks
        }
        user_info_db.users_top_songs.insert_one(user_data)

# Modified get_top_tracks function
def get_top_tracks_and_store_in_db(access_token):
    sp = spotipy.Spotify(auth=access_token)

    # Get the user's top tracks
    top_tracks = sp.current_user_top_tracks(limit=50)['items']

    # Get the track IDs
    top_track_ids = [track['id'] for track in top_tracks]

    # Get the user's Spotify ID
    spotify_id = sp.me()["id"]

    # Store the user's Spotify ID and top songs in the database
    store_top_songs_in_database(spotify_id, top_track_ids)

    return top_track_ids


class Musaic:
    def __init__(self, access_token):
        self.access_token = access_token
        self.sp = spotipy.Spotify(auth=self.access_token)
    
    def get_top_tracks(self):
        # Get the user's top tracks
        top_tracks = self.sp.current_user_top_tracks(limit=20)['items']

        # Get the track IDs
        top_track_ids = [track['id'] for track in top_tracks]
        return top_track_ids

    def get_top_genres(self):
        genres_counter = Counter()

        # Get the user's top artists
        top_artists = self.sp.current_user_top_artists(limit=20)['items']

        # Collect genres from the user's top artists
        for artist in top_artists:
            genres_counter.update(artist['genres'])

        # Get the user's top genres
        top_genres = [genre for genre, _ in genres_counter.most_common(20)]
        return top_genres

    def get_top_artists(self, limit=10):
        # Get the user's top artists
        top_artists = self.sp.current_user_top_artists(limit=limit)['items']

        # Get the artist names
        top_artist_names = [artist['name'] for artist in top_artists]

        # Shuffle the top_artist_names list
        random.shuffle(top_artist_names)

        # Return the first 20 artists
        return top_artist_names[:10]
    
    def get_recently_played_tracks(self):
        # Get the user's recently played tracks
        recently_played_tracks = self.sp.current_user_recently_played(limit=20)['items']

        # Get the track IDs
        track_ids = [track['track']['id'] for track in recently_played_tracks]
        return track_ids
    
    def get_combined_tracks(self, limit_top=10, limit_recent=10):
        top_tracks = self.get_top_tracks(limit_top)
        recently_played_tracks = self.get_recently_played_tracks(limit_recent)
        combined_tracks = top_tracks + recently_played_tracks
        return combined_tracks

    def create_playlist_from_tracks(self, track_ids, playlist_name="Generated Playlist: Top Tracks", description="A playlist based on the user's top tracks.", public=True):
        # Get the user's ID
        user_id = self.sp.me()["id"]

        # Create a playlist
        playlist = self.sp.user_playlist_create(user_id, playlist_name, public=public, description=description)
        playlist_id = playlist["id"]

        # Add the tracks to the playlist
        self.sp.playlist_add_items(playlist_id, track_ids)

        # Return the link to the playlist
        link = playlist["external_urls"]["spotify"]
        return link


    def create_playlist_from_input(self, suggested_playlist, playlist_name, description="By Musaic", public=True):
        # Get the user's ID
        user_id = self.sp.me()["id"]

        # Create a playlist
        playlist = self.sp.user_playlist_create(user_id, playlist_name, public=public, description=description)
        playlist_id = playlist["id"]

        # Add the suggested tracks to the playlist
        self.sp.playlist_add_items(playlist_id, suggested_playlist)

        # Get the track details
        track_details = [self.sp.track(track_id) for track_id in suggested_playlist]

        # Return the link to the playlist and track details
        link = playlist["external_urls"]["spotify"]
        return link, track_details



# def main(oauth):

#     # replace auth with own authentication code (expires every hour)
#     auth = oauth
#     # for multiple people use
#     listofauths = [auth]
#     # get genre types?
#     genres = ["rap"]
#     # "r-n-b", "pop", "jazz", "classical", "alternative", "indie", "j-rock", "latin"

#     # main playlist
#     pm = playlistmaker(listofauths)

#     # get tracks, limit is 50 for top and recently played tracks
#     # also if we go beyond 100 Spotify kind of breaks
#     # since we're getting both top played and recently played, divide by 2
#     num_tracks = int(20 / len(listofauths))
#     # tracks = pm.multiple_get_tracks(num_tracks)
#     tracks = pm.get_tracks_genre_filter(num_tracks, genres)
#     title = "Musaic"
#     description = "Recommended songs by Musaic heh c:"
#     playlist = pm.create_playlist(title, description)
#     pm.populate_playlist(playlist, tracks)

#     # get recommended if not full
#     if len(tracks) < 20:
#         random.seed()
#         rec_track_num = 20 - len(tracks)
#         # check if songs actually found in library
#         seed_tracks = list()
#         if (len(tracks) != 0):
#             # check if there's one song
#             trackmax = 2
#             if (len(tracks) == 1):
#                 trackmax = 1
#             tracks = list(tracks)
#             random.shuffle(tracks)
#             for counter in range(trackmax):
#                 chosen_track = tracks[counter]
#                 print(chosen_track.name)
#                 seed_tracks.append(chosen_track.id)
#         # if requested genres is over 3, find three random genres out of it
#         random_requested_genres = genres
#         if (len(genres) > (5-len(seed_tracks))):
#             random_requested_genres = list()
#             random.shuffle(genres)
#             for i in range(5-len(seed_tracks)):
#                 random_requested_genres.append(genres[i])
#         # test
#         for yay in random_requested_genres:
#             print(yay)
#         rec_tracks = pm.get_track_recommendations(seed_tracks, random_requested_genres, rec_track_num)

#         pm.populate_playlist(playlist, rec_tracks)



#     # get link to playlist
#     link = pm.get_playlist_link()
#     # local test
#     return(link)

# class playlistmaker:

#     def __init__(self, listofauths):
#         """
#         :param listofauths (lst): list of Spotify API tokens
#         """
#         self.authorizationToken = listofauths[0]
#         self.tokenslist = listofauths
#         self.playlistid = ""

#     # duplicate function for site testing purposes
#     def get_tracks(self, limit):
#         """Get the top and recent n tracks played by a user
#         :param limit (int): Number of tracks to get. Should be <= 50
#         :return tracks (list of Track): List of last played tracks
#         """
#         tracks = list()
#         for user in self.tokenslist:
#             # get top tracks first
#             url = f"https://api.spotify.com/v1/me/top/tracks?limit={limit}"
#             response = self._place_get_api_request(url, user)
#             response_json = response.json()
#             for track in response_json["items"]:
#                 tracks.append(Track(track["name"], track["id"], track["artists"][0]["name"]))

#             # reset the url to get recently played tracks
#             url = f"https://api.spotify.com/v1/me/player/recently-played?limit={limit}"
#             response = self._place_get_api_request(url, user)
#             response_json = response.json()
#             for track in response_json["items"]:
#                 tracks.append(Track(track["track"]["name"], track["track"]["id"], track["track"]["artists"][0]["name"]))
#         # remove duplicates
#         tracks = set(tracks)
#         return tracks


#     def get_tracks_genre_filter(self, limit, requested_genres):
#         """Get the top and recent n tracks played by a user
#         :param limit (int): Number of tracks to get. Should be <= 50
#         :param requested_genres (list): list of requested genres user wants
#         :return tracks (list of Track): List of last played tracks
#         """
#         """Get the top and recent n tracks played by a user
#                 :param limit (int): Number of tracks to get. Should be <= 50
#                 :param requested_genres (list): list of requested genres user wants
#                 :return tracks (list of Track): List of last played tracks
#                 """
#         tracks = list()
#         for user in self.tokenslist:
#             # get top tracks first
#             url = f"https://api.spotify.com/v1/me/top/tracks?limit={limit}"
#             response = self._place_get_api_request(url, user)
#             response_json = response.json()
#             # json testing for debugging purposes
#             # json_object = json.dumps(response_json)
#             # with open("test.json", "w") as outfile:
#             #     outfile.write(json_object)
#             # f = open('test.json')

#             # returns JSON object as
#             # a dictionary
#             # data = json.load(f)
#             #
#             # # Iterating through the json
#             # # list
#             # for i in data['items']:
#             #     print(i)
#             # # Closing file
#             # f.close()
#             # separate by genre
#             for track in response_json["items"]:
#                 artist_id = track["artists"][0]["id"]
#                 if self.match_artist_genre(artist_id, requested_genres, user):
#                     tracks.append(Track(track["name"], track["id"], track["artists"][0]["name"]))

#             # reset the url to get recently played tracks
#             url = f"https://api.spotify.com/v1/me/player/recently-played?limit={limit}"
#             response = self._place_get_api_request(url, user)
#             response_json = response.json()
#             for track in response_json["items"]:
#                 artist_id = track["track"]["artists"][0]["id"]
#                 if self.match_artist_genre(artist_id, requested_genres, user):
#                     tracks.append(
#                         Track(track["track"]["name"], track["track"]["id"], track["track"]["artists"][0]["name"]))

#         # # reset url again to get specific genre tracks of 2022 (Carrie's design)
#         # for genre in requested_genres:
#         #     url = f"https://api.spotify.com/v1/search?type=track&q=year:2022%20genre:{genre}&limit=5"
#         #     response = self._place_get_api_request(url)
#         #     response_json = response.json()
#         #     for track in response_json['tracks']['items']:
#         #         tracks.append(Track(track["name"], track["id"], track["artists"][0]["name"]))

#         # remove duplicates
#         tracks = set(tracks)
#         return tracks

#     def get_user_id(self):
#         """Get the user ID of user to access their Spotify and create a playlist
#         :return userid: unique string for finding user's Spotify"""
#         url = f"https://api.spotify.com/v1/me"
#         response = self._place_get_api_request(url, self.authorizationToken)
#         response_json = response.json()
#         userid = response_json["id"]
#         return userid


#     # genre filter function
#     # since apparently getting the track genre is broken
#     def match_artist_genre(self, artist, requested_genres, userauth):
#         """Gets artists' genres and sees if it matches with the requested genres
#         :param artist: artist id
#         :param requested_genres: list of requested genres
#         :return: True if artists' genres is in the requested, False if otherwise
#         """
#         # testing purposes
#         # track_id = "1fdlTXD7obDyqOpx96BEL9" — Maison
#         # 5NK2NHvmKLOn8V3eBYDaKm July 7th
#         url = f"https://api.spotify.com/v1/artists/{artist}"
#         response = self._place_get_api_request(url, userauth)
#         response_json = response.json()
#         artist_genres = response_json["genres"]
#         for artist_genre in artist_genres:
#             if artist_genre in requested_genres:
#                 return True
#         return False

#     # WIP
#     def get_track_recommendations(self, seed_tracks, requested_genres, limit):
#         """Get a list of recommended tracks starting from a number of seed tracks.
#         :param seed_tracks (list of Track): Reference tracks to get recommendations. Should be 5 or less.
#         :param limit (int): Number of recommended tracks to be returned
#         :return tracks (list of Track): List of recommended tracks
#         Grab three random genres (if more than three) and two seed tracks as base """
#         # get seed tracks first
#         seed_tracks_url = ""
#         for seed_track in seed_tracks:
#             seed_tracks_url += seed_track + ","
#         seed_tracks_url = seed_tracks_url[:-1]

#         seed_genres_url = ""
#         for seed_genre in requested_genres:
#             seed_genres_url += seed_genre + ","
#         seed_genres_url = seed_genres_url[:-1]

#         url = f"https://api.spotify.com/v1/recommendations?limit={limit}&market=US&seed_genres={seed_genres_url}&seed_tracks={seed_tracks_url}"
#         response = self._place_get_api_request(url, self.authorizationToken)
#         response_json = response.json()
#         tracks = [Track(track["name"], track["id"], track["artists"][0]["name"]) for track in response_json["tracks"]]
#         return tracks


#     # functions for creating a playlist
#     def create_playlist(self, name, description):
#         """
#         :param name (str): New playlist name
#         :return playlist (Playlist): Newly created playlist
#         """
#         userid = self.get_user_id()
#         data = json.dumps({
#             "name": name,
#             "description": description,
#             "collaborative": True,
#             "public": False
#         })
#         url = f"https://api.spotify.com/v1/users/{userid}/playlists"
#         response = self._place_post_api_request(url, data, self.authorizationToken)
#         response_json = response.json()
#         # get playlist ID for getting links
#         playlist_id = response_json["id"]
#         self.playlistid = playlist_id

#         playlist = Playlist(name, playlist_id)
#         return playlist

#     def populate_playlist(self, playlist, tracks):
#         """Add tracks to a playlist.
#         :param playlist (Playlist): Playlist to which to add tracks
#         :param tracks (list of Track): Tracks to be added to playlist
#         :return response: API response
#         """
#         track_uris = [track.create_spotify_uri() for track in tracks]
#         data = json.dumps(track_uris)
#         url = f"https://api.spotify.com/v1/playlists/{playlist.id}/tracks"
#         response = self._place_post_api_request(url, data, self.authorizationToken)
#         response_json = response.json()
#         return response_json

#     def get_playlist_link(self):
#         """Gets playlist link.
#         :return: link of playlist (string)
#         """
#         url = f"https://api.spotify.com/v1/playlists/{self.playlistid}"
#         response = self._place_get_api_request(url, self.authorizationToken)
#         response_json = response.json()
#         link = response_json['external_urls']['spotify']
#         return link


# # API requests for Spotify
#     def _place_get_api_request(self, url, auth):
#         response = requests.get(
#             url,
#             headers={
#                 "Content-Type": "application/json",
#                 "Authorization": f"Bearer {auth}"
#             }
#         )
#         return response

#     def _place_post_api_request(self, url, data, auth):
#         response = requests.post(
#             url,
#             data=data,
#             headers={
#                 "Content-Type": "application/json",
#                 "Authorization": f"Bearer {auth}"
#             }
#         )
#         return response
    
# class Track:

#     def __init__(self, name, id, artist):
#         """
#         :param name (str): Track name
#         :param id (int): Spotify track id
#         :param artist (str): Artist who created the track
#         """
#         # add genre at some point?
#         self.name = name
#         self.id = id
#         self.artist = artist

#     def create_spotify_uri(self):
#         return f"spotify:track:{self.id}"
    
#     def __str__(self):
#         return self.name + " by " + self.artist

#     def __repr__(self):
#         return '<track {}>'.format(self.id)

#     def __eq__(self, other):
#         return self.id == other.id

#     def __hash__(self):
#         return hash(self.id)
    
# class Playlist:
    
#     def __init__(self, name, id):
#         """
#         :param name (str): Playlist name
#         :param id (int): Spotify playlist id
#         """
#         self.name = name
#         self.id = id

#     def __str__(self):
#         return f"Playlist: {self.name}"



# # Function to get genres from ChatGPT API
# def get_playlist_from_gpt(user_input, access_token):
#     pm = Musaic(access_token)
#     sp = spotipy.Spotify(auth=access_token)
#     top_artists = pm.get_top_artists()

#     prompt = f"Based on these artists '{top_artists}', choose only the artists that best fit the phrase '{user_input}' and make me a list of artists."
#     response = openai.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=50, n=1, stop=None, temperature=0.7)
#     print(response)
#     artist_list_text = response.choices[0].text.strip()
#     artist_text_lines = [line.strip().lstrip('-') for line in artist_list_text.split('\n') if line]
#     artist_list = [line.strip().replace('"', '') for line in artist_text_lines if line]

#     # Convert track names to track IDs
#     track_ids = []
#     unique_track_ids = set()
#     while(len(track_ids) <= 20):
#         for count in range(5):
#             for artist_name in artist_list:
#                 if artist_name:  # Check if the artist_name is not empty
#                     search_results = sp.search(q=artist_name, type="track", limit=20)
#                     random.shuffle(search_results)
#                     if search_results["tracks"]["items"]:
#                         try:
#                             track_id = search_results["tracks"]["items"][count]["id"]
#                             if track_id in unique_track_ids:
#                                 print("already in tracks")
#                                 continue
#                             if len(track_ids) >= 20:
#                                 return track_ids
#                             unique_track_ids.add(track_id)
#                             track_ids.append(track_id)
#                         except IndexError:
#                             print(f"No track found for '{artist_name}' at index {count}")
#                             continue

#     return track_ids