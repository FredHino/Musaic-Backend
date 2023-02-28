"""
A testing function for creating a basic playlist
Author: Ellie Paek
"""

from playlistMaker import playlistmaker

# pretend account for vercel: qwertyay@gmail.com
# pretend password: hahanerd

def main(oauth):
    auth = oauth
    pm = playlistmaker(auth)

    # get tracks
    num_tracks = 20
    tracks = pm.get_tracks(num_tracks)

    # get playlist name from user and create playlist
    playlist = pm.create_playlist("Test")

    # populate playlist with recommended tracks
    pm.populate_playlist(playlist, tracks)

    # get link to playlist
    link = pm.get_playlist_link()
    return link

if __name__ == "__main__":
    main()