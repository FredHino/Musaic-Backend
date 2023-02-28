from dotenv import load_dotenv, find_dotenv
import os
import pprint
import spotify_python
from pymongo import MongoClient

load_dotenv(find_dotenv())

password = os.environ.get("MONGODB_PWD")


connection_string = f"mongodb+srv://team8bits:{password}@spotifymatched.2u1gxhe.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(connection_string)

dbs = client.list_database_names()

id = spotify_python.client_id
test_db = client.test
fred_topSongs = test_db.fred_topSongs

spotify_python.tracks()

def insert_test_doc():
    rank = []
    for i in range(0,len(spotify_python.rank)):
        rank.append(spotify_python.rank[i])
    name = []
    for i in range(0,len(spotify_python.name)):
        name.append(spotify_python.name[i])
    artist = []
    for i in range(0,len(spotify_python.artist)):
        artist.append(spotify_python.artist[i])

    docs = []
    for rank, name, artist in zip(rank, name, artist):
        doc = {"rank": rank, "name": name, "artist": artist}
        docs.append(doc)
    
    fred_topSongs.insert_many(docs)

insert_test_doc()
