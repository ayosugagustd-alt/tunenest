# 必要なライブラリをインポート
from flask import Flask, render_template, request
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def check_api_keys():
    spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
    spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    youtube_api_key = os.getenv('YOUTUBE_API_KEY')
    
    if not spotify_client_id or not spotify_client_secret:
        raise ValueError("Spotify credentials are not set")
        
    if not youtube_api_key:
        raise ValueError("YouTube API key is not set")

# Flaskアプリを初期化
app = Flask(__name__)

# Spotifyクライアントを取得する関数
def get_spotify_client():
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise ValueError("Spotify credentials are not set")
    return spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))

# トラック情報を取得する関数
def get_track_info(track):
    return {
        'url': track['preview_url'],
        'name': track['name'],
        'artist': track['artists'][0]['name'],
        'image_url': track['album']['images'][0]['url'],
    }

# インデックスページのルート
@app.route('/')
def index():
    playlist_id = request.args.get('playlist_id', '37i9dQZEVXbINTEnbFeb8d')  # default:Viral50-JP
    playlist_name = request.args.get('playlist_name', 'Viral 50 - JP')  # default name
    try:
        sp = get_spotify_client()
        results = sp.playlist_tracks(playlist_id)
        tracks = [get_track_info(item['track']) for item in results['items']]
        return render_template('index.html', tracks=tracks, playlist_name=playlist_name)
    except Exception as e:
        return render_template('error.html', error=str(e))

# YouTube動画を検索する関数
def youtube_search(q, max_results=1, youtube_api_key=None):
    try:
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        search_response = youtube.search().list(
            q=q,
            type='video',
            part='id,snippet',
            maxResults=max_results
        ).execute()
        videos = [search_result['id']['videoId'] for search_result in search_response.get('items', [])]
        return videos[0] if videos else None
    except HttpError as e:
        return {'error': f"An HTTP error occurred: {e}"}

# YouTube検索のルート
@app.route('/youtube')
def youtube():
    track_name = request.args.get('track')
    artist_name = request.args.get('artist')
    youtube_api_key = os.getenv('YOUTUBE_API_KEY')


    video_id = youtube_search(f"{track_name} {artist_name}", youtube_api_key=youtube_api_key)


    if isinstance(video_id, dict) and 'error' in video_id:
        return render_template('error.html', error=video_id['error'])


    if video_id:
        return render_template('youtube.html', video_id=video_id)
    else:
        return "No video found", 404

# メインのエントリーポイント
if __name__ == "__main__":
    check_api_keys()  # APIキーのチェック
    debug_mode = False
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
