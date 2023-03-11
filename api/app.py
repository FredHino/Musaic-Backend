
from flask import Flask, url_for, session, request, redirect
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import time
import random



#comment
# App config
app = Flask(__name__)

app.secret_key = 'SOMETHING-RANDOM'
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

@app.route('/')
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    print(auth_url)
    return redirect(auth_url)

@app.route('/authorize')
def authorize():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect("/getTracks")

@app.route('/logout')
def logout():
    for key in list(session.keys()):
        session.pop(key)
    return redirect('/')

@app.route('/getTracks')
def get_all_tracks():
    session['token_info'], authorized = get_token()
    session.modified = True
    if not authorized:
        return redirect('/')

    link = main(session.get('token_info').get('access_token'))

    return redirect(link)


# Checks to see if token is valid and gets a new token if not
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


def create_spotify_oauth():
    return SpotifyOAuth(
        client_id ='39951c143d3f4fd1b8a4159d349399e8',
        client_secret='58ed9c7f0a7944efbc045a0393459e09',
        redirect_uri=url_for('authorize', _external=True),
        scope=['playlist-modify-private','playlist-modify-public','user-read-email','user-top-read','user-read-recently-played','user-read-private'])

def main(oauth):

    # replace auth with own authentication code (expires every hour)
    auth = oauth
    # for multiple people use
    listofauths = [auth]
    # get genre types?
    genres = ["jazz"]
    # "r-n-b", "pop", "jazz", "classical", "alternative", "indie", "j-rock", "latin"

    # main playlist
    pm = playlistmaker(listofauths)

    # get tracks, limit is 50 for top and recently played tracks
    # also if we go beyond 100 Spotify kind of breaks
    # since we're getting both top played and recently played, divide by 2
    num_tracks = int(20 / len(listofauths))
    # tracks = pm.multiple_get_tracks(num_tracks)
    tracks = pm.get_tracks_genre_filter(num_tracks, genres)
    title = "Musaic"
    description = "Recommended songs by Musaic heh c:"
    playlist = pm.create_playlist(title, description)
    pm.populate_playlist(playlist, tracks)

    # get recommended if not full
    if len(tracks) < 20:
        random.seed()
        rec_track_num = 20 - len(tracks)
        # check if songs actually found in library
        seed_tracks = list()
        if (len(tracks) != 0):
            # check if there's one song
            trackmax = 2
            if (len(tracks) == 1):
                trackmax = 1
            tracks = list(tracks)
            random.shuffle(tracks)
            for counter in range(trackmax):
                chosen_track = tracks[counter]
                print(chosen_track.name)
                seed_tracks.append(chosen_track.id)
        # if requested genres is over 3, find three random genres out of it
        random_requested_genres = genres
        if (len(genres) > (5-len(seed_tracks))):
            random_requested_genres = list()
            random.shuffle(genres)
            for i in range(5-len(seed_tracks)):
                random_requested_genres.append(genres[i])
        # test
        for yay in random_requested_genres:
            print(yay)
        rec_tracks = pm.get_track_recommendations(seed_tracks, random_requested_genres, rec_track_num)

        pm.populate_playlist(playlist, rec_tracks)



    # get link to playlist
    link = pm.get_playlist_link()
    # local test
    return(link)

class playlistmaker:

    def __init__(self, listofauths):
        """
        :param listofauths (lst): list of Spotify API tokens
        """
        self.authorizationToken = listofauths[0]
        self.tokenslist = listofauths
        self.playlistid = ""

    # duplicate function for site testing purposes
    def get_tracks(self, limit):
        """Get the top and recent n tracks played by a user
        :param limit (int): Number of tracks to get. Should be <= 50
        :return tracks (list of Track): List of last played tracks
        """
        tracks = list()
        for user in self.tokenslist:
            # get top tracks first
            url = f"https://api.spotify.com/v1/me/top/tracks?limit={limit}"
            response = self._place_get_api_request(url, user)
            response_json = response.json()
            for track in response_json["items"]:
                tracks.append(Track(track["name"], track["id"], track["artists"][0]["name"]))

            # reset the url to get recently played tracks
            url = f"https://api.spotify.com/v1/me/player/recently-played?limit={limit}"
            response = self._place_get_api_request(url, user)
            response_json = response.json()
            for track in response_json["items"]:
                tracks.append(Track(track["track"]["name"], track["track"]["id"], track["track"]["artists"][0]["name"]))
        # remove duplicates
        tracks = set(tracks)
        return tracks


    def get_tracks_genre_filter(self, limit, requested_genres):
        """Get the top and recent n tracks played by a user
        :param limit (int): Number of tracks to get. Should be <= 50
        :param requested_genres (list): list of requested genres user wants
        :return tracks (list of Track): List of last played tracks
        """
        """Get the top and recent n tracks played by a user
                :param limit (int): Number of tracks to get. Should be <= 50
                :param requested_genres (list): list of requested genres user wants
                :return tracks (list of Track): List of last played tracks
                """
        tracks = list()
        for user in self.tokenslist:
            # get top tracks first
            url = f"https://api.spotify.com/v1/me/top/tracks?limit={limit}"
            response = self._place_get_api_request(url, user)
            response_json = response.json()
            # json testing for debugging purposes
            # json_object = json.dumps(response_json)
            # with open("test.json", "w") as outfile:
            #     outfile.write(json_object)
            # f = open('test.json')

            # returns JSON object as
            # a dictionary
            # data = json.load(f)
            #
            # # Iterating through the json
            # # list
            # for i in data['items']:
            #     print(i)
            # # Closing file
            # f.close()
            # separate by genre
            for track in response_json["items"]:
                artist_id = track["artists"][0]["id"]
                if self.match_artist_genre(artist_id, requested_genres, user):
                    tracks.append(Track(track["name"], track["id"], track["artists"][0]["name"]))

            # reset the url to get recently played tracks
            url = f"https://api.spotify.com/v1/me/player/recently-played?limit={limit}"
            response = self._place_get_api_request(url, user)
            response_json = response.json()
            for track in response_json["items"]:
                artist_id = track["track"]["artists"][0]["id"]
                if self.match_artist_genre(artist_id, requested_genres, user):
                    tracks.append(
                        Track(track["track"]["name"], track["track"]["id"], track["track"]["artists"][0]["name"]))

        # # reset url again to get specific genre tracks of 2022 (Carrie's design)
        # for genre in requested_genres:
        #     url = f"https://api.spotify.com/v1/search?type=track&q=year:2022%20genre:{genre}&limit=5"
        #     response = self._place_get_api_request(url)
        #     response_json = response.json()
        #     for track in response_json['tracks']['items']:
        #         tracks.append(Track(track["name"], track["id"], track["artists"][0]["name"]))

        # remove duplicates
        tracks = set(tracks)
        return tracks

    def get_user_id(self):
        """Get the user ID of user to access their Spotify and create a playlist
        :return userid: unique string for finding user's Spotify"""
        url = f"https://api.spotify.com/v1/me"
        response = self._place_get_api_request(url, self.authorizationToken)
        response_json = response.json()
        userid = response_json["id"]
        return userid


    # genre filter function
    # since apparently getting the track genre is broken
    def match_artist_genre(self, artist, requested_genres, userauth):
        """Gets artists' genres and sees if it matches with the requested genres
        :param artist: artist id
        :param requested_genres: list of requested genres
        :return: True if artists' genres is in the requested, False if otherwise
        """
        # testing purposes
        # track_id = "1fdlTXD7obDyqOpx96BEL9" — Maison
        # 5NK2NHvmKLOn8V3eBYDaKm July 7th
        url = f"https://api.spotify.com/v1/artists/{artist}"
        response = self._place_get_api_request(url, userauth)
        response_json = response.json()
        artist_genres = response_json["genres"]
        for artist_genre in artist_genres:
            if artist_genre in requested_genres:
                return True
        return False

    # WIP
    def get_track_recommendations(self, seed_tracks, requested_genres, limit):
        """Get a list of recommended tracks starting from a number of seed tracks.
        :param seed_tracks (list of Track): Reference tracks to get recommendations. Should be 5 or less.
        :param limit (int): Number of recommended tracks to be returned
        :return tracks (list of Track): List of recommended tracks
        Grab three random genres (if more than three) and two seed tracks as base """
        # get seed tracks first
        seed_tracks_url = ""
        for seed_track in seed_tracks:
            seed_tracks_url += seed_track + ","
        seed_tracks_url = seed_tracks_url[:-1]

        seed_genres_url = ""
        for seed_genre in requested_genres:
            seed_genres_url += seed_genre + ","
        seed_genres_url = seed_genres_url[:-1]

        url = f"https://api.spotify.com/v1/recommendations?limit={limit}&market=US&seed_genres={seed_genres_url}&seed_tracks={seed_tracks_url}"
        response = self._place_get_api_request(url, self.authorizationToken)
        response_json = response.json()
        tracks = [Track(track["name"], track["id"], track["artists"][0]["name"]) for track in response_json["tracks"]]
        return tracks


    # functions for creating a playlist
    def create_playlist(self, name, description):
        """
        :param name (str): New playlist name
        :return playlist (Playlist): Newly created playlist
        """
        userid = self.get_user_id()
        data = json.dumps({
            "name": name,
            "description": description,
            "collaborative": True,
            "public": False
        })
        url = f"https://api.spotify.com/v1/users/{userid}/playlists"
        response = self._place_post_api_request(url, data, self.authorizationToken)
        response_json = response.json()
        # get playlist ID for getting links
        playlist_id = response_json["id"]
        self.playlistid = playlist_id

        playlist = Playlist(name, playlist_id)
        return playlist

    def populate_playlist(self, playlist, tracks):
        """Add tracks to a playlist.
        :param playlist (Playlist): Playlist to which to add tracks
        :param tracks (list of Track): Tracks to be added to playlist
        :return response: API response
        """
        track_uris = [track.create_spotify_uri() for track in tracks]
        data = json.dumps(track_uris)
        url = f"https://api.spotify.com/v1/playlists/{playlist.id}/tracks"
        response = self._place_post_api_request(url, data, self.authorizationToken)
        response_json = response.json()
        return response_json

    def get_playlist_link(self):
        """Gets playlist link.
        :return: link of playlist (string)
        """
        url = f"https://api.spotify.com/v1/playlists/{self.playlistid}"
        response = self._place_get_api_request(url, self.authorizationToken)
        response_json = response.json()
        link = response_json['external_urls']['spotify']
        return link


# API requests for Spotify
    def _place_get_api_request(self, url, auth):
        response = requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth}"
            }
        )
        return response

    def _place_post_api_request(self, url, data, auth):
        response = requests.post(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth}"
            }
        )
        return response
    
class Track:

    def __init__(self, name, id, artist):
        """
        :param name (str): Track name
        :param id (int): Spotify track id
        :param artist (str): Artist who created the track
        """
        # add genre at some point?
        self.name = name
        self.id = id
        self.artist = artist

    def create_spotify_uri(self):
        return f"spotify:track:{self.id}"
    
    def __str__(self):
        return self.name + " by " + self.artist

    def __repr__(self):
        return '<track {}>'.format(self.id)

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)
    
class Playlist:
    
    def __init__(self, name, id):
        """
        :param name (str): Playlist name
        :param id (int): Spotify playlist id
        """
        self.name = name
        self.id = id

    def __str__(self):
        return f"Playlist: {self.name}"