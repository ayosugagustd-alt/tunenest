from flask import Flask, render_template
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__)

def get_spotify_client():
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise ValueError("Spotify credentials are not set")
    return spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))

def get_track_info(track):
    return {
        'url': track['preview_url'],
        'name': track['name'],
        'artist': track['artists'][0]['name'],
        'image_url': track['album']['images'][0]['url'],
    }

@app.route('/')
def index():
    try:
        sp = get_spotify_client()
        results = sp.playlist_tracks('37i9dQZEVXbKuaTI1Z1Afx')
        tracks = [get_track_info(item['track']) for item in results['items']]
        return render_template('index.html', tracks=tracks)
    except Exception as e:
        return render_template('error.html', error=str(e))

if __name__ == "__main__":
    debug_mode = False
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

