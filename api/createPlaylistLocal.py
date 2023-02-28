"""
Local testing function for creating playlists
Note: Please don't delete or integrate this into Vercel!
Author: Ellie Paek
"""


from playlistMaker import playlistmaker

def main():

    # replace auth with own authentication code (expires every hour)
    auth = "BQBaCrXh1O5lIteXlxxccAthIDC1-nNEwuKYLqEuHA0eXDmg7x3hbxTUa--G4NhPDSQpwAu8FFlCJd3s6mvRdj7cwHEODZpf_5BKKZI4h20rSn2c5Ns-xF9UmKxsNjQBDhQKa2E-_1G-Lu-xWlqjf2KyQlyGfnRGDCLYDzQi5rNbIEK1zH00Kgk_7xhCyLLIJEmY0CbDc7_jge8Wmb6CNnmvfZOEhyk20ybkCp1bcCG0EdayP4AU7OqjcYYs9Nt8vjrYoC1e_R5zzgTy-yE9f_gayzo65vWyykheuQeViIgUVys9Ox2Gw9zZ_1mGm4uJLN4vI9iPDOQKkxHf4g"
    # for multiple people use
    listofauths = [auth]
    pm = playlistmaker(auth)

    # get genre types?
    genres = ["r-n-b", "k-pop"]

    # get tracks, limit is 50 for top and recently played tracks
    # also if we go beyond 100 Spotify kind of breaks
    num_tracks = 15
    tracks = pm.get_tracks(num_tracks)
    # tracks = pm.get_tracks_genre_filter(num_tracks, genres)

    # get playlist name from user and create playlist
    playlist = pm.create_playlist("Test")

    # populate playlist with recommended tracks
    pm.populate_playlist(playlist, tracks)
    # get link to playlist
    link = pm.get_playlist_link()
    # local test
    print(link)
if __name__ == "__main__":
    main()