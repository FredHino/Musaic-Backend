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
        print(pm.get_top_artists)
        playlist = pm.get_playlist_from_gpt(user_input)
        link, tracks = pm.main(playlist, user_input)
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


class Musaic:
    def __init__(self, access_token):
        self.access_token = access_token
        self.sp = spotipy.Spotify(auth=self.access_token)

        load_dotenv(find_dotenv())

        password = os.environ.get('password')
        openai.api_key = os.environ.get('api_key')

        self.connection_string = f"mongodb+srv://team8bits:{password}@spotifymatched.2u1gxhe.mongodb.net/?retryWrites=true&w=majority"
        self.client = MongoClient(self.connection_string)

        self.user_info_db = self.client.user_info
        self.users_top_songs = self.user_info_db.users_top_songs

        self.artists_db = self.client.artists

    def is_artist_in_database(self, artist_name):
        artist = self.artists_db[artist_name].find_one({})
        return artist is not None

    def store_artist_tracks_in_database(self, artist_name, top_tracks, related_tracks):
        artist_data = {
            "top_tracks": [{"id": track["id"], "name": track["name"], "artist": artist_name} for track in top_tracks],
            "related_tracks": [{"id": track["id"], "name": track["name"], "artist": track["artists"][0]["name"]} for track in related_tracks],
        }
        self.artists_db[artist_name].insert_one(artist_data)

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

    def get_top_artists(self):

        # Get the user's ID
        user_id = self.sp.me()['id']

        user_artists = self.user_info_db.users_top_artists

        # Check if the user is in the user_info.users_top_artists
        user_artists = self.user_info_db.users_top_artists.find_one({"user_id": user_id})

        if user_artists:
            # If the user is in the collection, select 25 random artists from their document
            artist_names = user_artists['artists']
            random.shuffle(artist_names)
            top_artist_names = artist_names[:50]
        else:
            # If the user is not in the collection, add the user with their top 50 artists
            top_artists = self.sp.current_user_top_artists(limit=50, time_range="medium_term")['items']
            top_artist_names = [artist['name'] for artist in top_artists]

            # Add the user and their top artists to user_info.users_top_artists
            self.user_info_db.users_top_artists.insert_one({"user_id": user_id, "artists": top_artist_names})
            print("new user")

            # Shuffle the top_artist_names list and select the first 25 artists
            random.shuffle(top_artist_names)
            top_artist_names = top_artist_names[:50]
        random.shuffle(top_artist_names)

        return top_artist_names[:25]
    
    def get_artist_top_50_tracks(self, artist_name):
        # Search for the artist ID using the artist name

        results = self.sp.search(q=f"artist:{artist_name}", type="artist")
        print("results found")
        if results['artists']['items']:
            artist_id = results['artists']['items'][0]['id']
        else:
            print("returning empty")
            return []

        # Get the artist's top 10 tracks
        top_tracks = self.sp.artist_top_tracks(artist_id, country='US')['tracks']
        print("top tracks founds")

        # Get the artist's albums
        albums = self.sp.artist_albums(artist_id, limit=6)

        # Get the tracks from the artist's albums
        for album in albums['items']:
            album_tracks = self.sp.album_tracks(album['id'])['items']
            top_tracks.extend(album_tracks)

        # Remove duplicate tracks
        unique_tracks = {track['id']: track for track in top_tracks}.values()

        # Limit to the top 50 tracks
        top_50_tracks = list(unique_tracks)[:50]

        return top_50_tracks

    
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

    # experimental function for recommending songs
    def get_recommended_songs(self, seed_tracks, requested_genres, limit):
        """Get a list of recommended tracks
        :param seed_tracks: Reference tracks to get recommendations. Should be 5 or less.
        :param requested_genres : list of genres
        :param limit (int): Number of recommended tracks to be returned
        :return tracks: List of recommended tracks
        Grab three random genres (if more than three) and two seed tracks as base"""
        recommended_tracks = self.sp.recommendations(seed_genres=requested_genres, seed_tracks=seed_tracks, limit=limit) ['tracks']
        tracks = [track['id'] for track in recommended_tracks]
        return tracks

    def get_playlist_from_gpt(self,user_input):
        sp = self.sp
        top_artists = self.get_top_artists()
        print("get_playlist_from_gpt called")


        # Get the artist list from ChatGPT
        prompt = f"Your output will be a list of artists names. Based on the meaning and vibe of this phrase '{user_input}', output a list of 3 artists you think are related to the phrase. If an artist's name is included in the phrase, include the artist too."
        response = openai.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=500, n=1, stop=None, temperature=0.7)
        artist_list_text_1 = response.choices[0].text.strip()
        artist_text_lines_1= artist_list_text_1.split('\n')
        artist_list_1 = [line.partition('. ')[-1].strip().rstrip('"') for line in artist_text_lines_1 if line]
        artist_list_1 = [line.partition('. ')[-1].strip().replace('"', '') for line in artist_text_lines_1 if line]
        artist_list_1= [line.partition('. ')[-1].strip().replace('.', '') for line in artist_text_lines_1 if line]


        prompt = f"Your output will be a list of artists names. Based on the meaning and vibe of this phrase '{user_input}', rank the top 3 artists from this list '{top_artists}', that match the phrase the most. If an artist's name is included in the phrase, include the artist too."
        response = openai.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=500, n=1, stop=None, temperature=0.7)
        artist_list_text_2 = response.choices[0].text.strip()
        artist_text_lines_2= artist_list_text_2.split('\n')

        artist_list_2 = [line.partition('. ')[-1].strip().rstrip('"') for line in artist_text_lines_2 if line]
        artist_list_2 = [line.partition('. ')[-1].strip().replace('"', '') for line in artist_text_lines_2 if line]
        artist_list_2 = [line.partition('. ')[-1].strip().replace('.', '') for line in artist_text_lines_2 if line]

        artist_list = artist_list_2 + artist_list_1

        print(artist_list)
        track_ids_set = set()
        for artist_name in artist_list:
            print(f"Before processing artist: {artist_name}")

            if artist_name:

                # Search for the artist ID using the artist name
                results = sp.search(q=f"artist:{artist_name}", type="artist")
                
                if results['artists']['items']:
                    artist_id = results['artists']['items'][0]['id']
                    print(artist_id)
                else:
                    continue

                if not self.is_artist_in_database(artist_name):
                    # Get top tracks and related tracks
                    print("artist not in DB")
                    top_tracks = self.get_artist_top_50_tracks(artist_name)
                    print("got top tracks")
                    related_artists = sp.artist_related_artists(artist_id)['artists']
                    related_artist_ids = [artist['id'] for artist in related_artists[:5]]
                    related_tracks = []
                    for related_artist_id in related_artist_ids:
                        related_artist_tracks = sp.artist_top_tracks(related_artist_id, country='US')['tracks']
                        related_tracks.extend(related_artist_tracks[:5])
                        print("stored songs")

                    # Store the artist's top tracks and related tracks in the database
                    self.store_artist_tracks_in_database(artist_name, top_tracks, related_tracks)
                    print("stored all")

                # Get 10 random tracks from the artist's collection
                artist_tracks = list(self.artists_db[artist_name].find_one({}, {'_id': 0, 'top_tracks': 1, 'related_tracks': 1}).values())
                top_tracks, related_tracks = artist_tracks
                selected_tracks = top_tracks[:50] + related_tracks[:10]
                for track in selected_tracks[:10]:
                    track_id = track['id']
                    if track_id not in track_ids_set:
                        track_ids_set.add(track_id)
                print(f"After processing artist: {artist_name}")

        # Shuffle the track_ids list and return 20 random songs from it

        track_ids = list(track_ids_set)[:20]
        random.shuffle(track_ids)

        print("returning tracks ids")
        return track_ids


    def main(self,suggested_playlist,user_input):
        sp = self.sp

        # Get the user's ID
        user_id = sp.me()["id"]
        print(user_id + ": this is the user id")

        # Create a playlist
        playlist_name = user_input
        playlist = sp.user_playlist_create((user_id), playlist_name, public=True, description="By Musaic")
        playlist_id = playlist["id"]

        # Add the suggested tracks to the playlist
        sp.playlist_add_items(playlist_id, suggested_playlist)

        # Get the track details
        track_details = [sp.track(track_id) for track_id in suggested_playlist]

        # Return the link to the playlist and track details
        link = playlist["external_urls"]["spotify"]
        return link, track_details



    


