import spotipy
from spotipy.oauth2 import SpotifyOAuth

rank = []
name = []
artist = []

client_id = 'cf905901dbf84332b90962831fcb8f29'

def tracks():
    sp = spotipy.Spotify(auth_manager=
    SpotifyOAuth(client_id ='cf905901dbf84332b90962831fcb8f29',
    client_secret='ee13223bc921459592be3a89540ea4c6',
    redirect_uri='http://localhost:8888/callback',
    scope=['user-library-read','user-top-read']))

    results = sp.current_user_top_tracks(limit=10)
    
    for i, item in enumerate(results['items']):
        rank.append(i+1)
        name.append(item['name'])
        artist.append(item['artists'][0]['name'])

    