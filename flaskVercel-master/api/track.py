"""
Song track class
Author: Ellie Paek
"""

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