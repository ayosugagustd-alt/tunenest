# 必要なライブラリをインポート
from flask import Flask, render_template, request, redirect, url_for

import os
import unicodedata
import spotipy
import requests
from spotipy.oauth2 import SpotifyClientCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 定数の定義
DEFAULT_PLAYLIST_ID = '37i9dQZEVXbKuaTI1Z1Afx'
DEFAULT_PLAYLIST_NAME = 'Viral 50 - US'

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
    return spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))

# トラック情報を取得する関数
def get_track_info(track):
    track_info = {
        'id': track['id'],  # 楽曲IDを追加
        'url': track['preview_url'],
        'name': track['name'],
        'artist': track['artists'][0]['name'],
        'image_url': track['album']['images'][0]['url'],
        'spotify_link': track['external_urls']['spotify']
    }
#   print(f"Track Info: {track_info}")
    return track_info

# キャッシュ用の辞書
youtube_url_cache = {}

# YouTube動画を検索する関数
def youtube_search(q, max_results=1, youtube_api_key=None):
    # キャッシュからURLを取得
    if q in youtube_url_cache:
        return youtube_url_cache[q]


    try:
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        search_response = youtube.search().list(
            q=q,
            type='video',
            part='id,snippet',
            maxResults=max_results
        ).execute()
        videos = [search_result['id']['videoId'] for search_result in search_response.get('items', [])]

        # キャッシュにURLを保存
        video_id = videos[0] if videos else None
        youtube_url_cache[q] = video_id

        return video_id
    except HttpError as e:
        return {'error': f"An HTTP error occurred: {e}"}


# インデックスページのルート
@app.route('/')
def index():
    playlist_id = request.args.get('playlist_id', DEFAULT_PLAYLIST_ID)
    playlist_name = request.args.get('playlist_name', DEFAULT_PLAYLIST_NAME)
    try:
        sp = get_spotify_client()
        results = sp.playlist_tracks(playlist_id)
        tracks = [get_track_info(item['track']) for item in results['items']]
        return render_template('index.html', tracks=tracks, playlist_name=playlist_name)
    except Exception as e:
        return render_template('error.html', error=str(e))

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

#アルバム名でSpotifyを検索
def search_album(album_name):
    sp = get_spotify_client()
    album_name = unicodedata.normalize('NFKC', album_name)
    results = sp.search(q=album_name, type='album')
    return results['albums']['items']

# アーティストの詳細情報を取得
def get_artist_details(artist_id):
    sp = get_spotify_client()

    # アーティストの詳細情報を取得
    artist = sp.artist(artist_id)
    artist_details = {
        'id': artist['id'],
        'name': artist['name'],
        'image_url': artist['images'][0]['url'] if artist['images'] else None,
        'popularity': artist['popularity'],
        'genres': artist['genres'],
        'followers': artist['followers']['total']
    }

    # アーティストのトップ曲を取得
    top_tracks = sp.artist_top_tracks(artist_id)['tracks']
    top_tracks_details = [{'name': track['name'], 'id': track['id']} for track in top_tracks]

    # アーティストのアルバムを取得し、最新のアルバムを特定
    albums = sp.artist_albums(artist_id, album_type='album')['items']
    latest_album = albums[0] if albums else None
    latest_album_details = {'name': latest_album['name'], 'id': latest_album['id'], 'artist_id': artist_id} if latest_album else None

    return artist_details, top_tracks_details, latest_album_details


# アルバムIDを使用してアルバムの詳細情報を取得
def get_album_details(album_id):
    sp = get_spotify_client()  # Spotifyクライアントの取得
    album = sp.album(album_id)  # アルバムIDを使用してアルバム情報を取得

    # 収録曲リストを作成
    tracks = [{'name': track['name'], 'length': track['duration_ms'], 'id': track['id']} for track in album['tracks']['items']]


    details = {
        'name': album['name'],  # アルバム名
        'release_date': album['release_date'],  # リリース日
        'image': album['images'][0]['url'],  # ジャケット画像のURL
        'genres': album['genres'],  # ジャンル
        'artists': [{'name': artist['name'], 'id': artist['id']} for artist in album['artists']],  # アーティスト情報
        'tracks': tracks,  # 収録曲リスト
        'popularity': album['popularity']  # 人気度
    }

    # 詳細情報を整理して返却
    return details


# 曲のIDを受け取り、その曲の詳細情報とオーディオ特性を返す
def get_song_details(song_id):
    sp = get_spotify_client() # Spotifyクライアントの取得
    song = sp.track(song_id)  # 曲の基本情報を取得

    features = sp.audio_features([song_id])[0]  # 曲のオーディオ特性を取得

    # アルバムのアートワークURLを取得
    album_artwork_url = song['album']['images'][0]['url']

	# アーティスト名を取得（複数の場合あり）
    artists = [{'name': artist['name'], 'id': artist['id']} for artist in song['artists']]

    # アーティスト名と楽曲名からmusixmatchのtrack_idを取得
    musixmatch_track_id = get_musixmatch_track_id(song['artists'][0]['name'], song['name'])
    
    # track_idから歌詞を取得
    lyrics = get_lyrics(musixmatch_track_id)

    if 'lyrics' in lyrics['message']['body']:
        lyrics_body = lyrics['message']['body']['lyrics']['lyrics_body']
        clean_lyrics = lyrics_body.split('\n*******')[0]
        clean_lyrics = clean_lyrics.replace('\n', '<br>')
    else:
        clean_lyrics = 'Lyrics not found.'

    # 必要な情報を整理
    return {
        'acousticness': features['acousticness'] * 100,
        'danceability': features['danceability'] * 100,
        'duration': song['duration_ms'] / 1000, # 秒単位に変換
        'energy': features['energy'] * 100,
        'instrumentalness': features['instrumentalness'] * 100,
        'key': features['key'],
        'mode': features['mode'],
        'name': song['name'],
        'popularity': song['popularity'],
        'tempo': features['tempo'],
        'time_signature': features['time_signature'],
        'valence': features['valence'] * 100,
        'album_artwork_url': album_artwork_url, # アートワークURLを追加
		'artists': artists,
        'lyrics': clean_lyrics, # 歌詞情報を追加
    }

# count_total_albums()
def count_total_albums(artist_id):
    sp = get_spotify_client() # Spotifyクライアントの取得
    total_albums = sp.artist_albums(artist_id, album_type='album')['total']
    return total_albums

# count_total_singles()
def count_total_singles(artist_id):
    sp = get_spotify_client()
    total_singles = sp.artist_albums(artist_id, album_type='single')['total']
    return total_singles

# count_total_compilations()
def count_total_compilations(artist_id):
    sp = get_spotify_client()
    total_compilations = sp.artist_albums(artist_id, album_type='compilation')['total']
    return total_compilations

# get_artist_albums_with_songs()
def get_artist_albums_with_songs(artist_id, page, per_page=10):
    sp = get_spotify_client()
    offset = (page - 1) * per_page
    limit = per_page

    # アーティストのアルバムをページ単位で取得
    albums = sp.artist_albums(artist_id, album_type='album', offset=offset, limit=limit)['items']
    result = []

    for album in albums:
        album_info = {
            'name': album['name'],
            'release_date': album['release_date'],
            'tracks': [],
            'album_id': album['id'],         # アルバムIDの追加
            'artist_id': artist_id           # アーティストIDの追加
        }

        # 各アルバムに含まれる楽曲を取得
        album_tracks = sp.album_tracks(album['id'])['items']
        for track in album_tracks:
            track_name = track['name']
            track_id = track['id']
            album_info['tracks'].append({'name': track_name, 'track_id': track_id})

        result.append(album_info)

    return result

# get_artist_singles_with_songs()
def get_artist_singles_with_songs(artist_id, page, per_page=10):
    sp = get_spotify_client()
    offset = (page - 1) * per_page
    limit = per_page

    # アーティストのシングルをページ単位で取得
    singles = sp.artist_albums(artist_id, album_type='single', offset=offset, limit=limit)['items']
    result = []

    for single in singles:
        single_info = {
            'name': single['name'],
            'release_date': single['release_date'],
            'tracks': [],
            'single_id': single['id'], # シングルIDの追加
            'artist_id': artist_id     # アーティストIDの追加
        }

        # 各シングルに含まれる楽曲を取得
        single_tracks = sp.album_tracks(single['id'])['items']
        for track in single_tracks:
            track_name = track['name']
            track_id = track['id']
            single_info['tracks'].append({'name': track_name, 'track_id': track_id})

        result.append(single_info)

    return result


# get_artist_compilations_with_songs()
def get_artist_compilations_with_songs(artist_id, page, per_page=10):
    sp = get_spotify_client()
    offset = (page - 1) * per_page
    limit = per_page

    # アーティストのコンピレーションアルバムをページ単位で取得
    compilations = sp.artist_albums(artist_id, album_type='compilation', offset=offset, limit=limit)['items']
    result = []

    for compilation in compilations:
        compilation_info = {
            'name': compilation['name'],
            'release_date': compilation['release_date'],
            'tracks': [],
            'compilation_id': compilation['id'], # コンピレーションIDの追加
            'artist_id': artist_id               # アーティストIDの追加
        }

        # 各コンピレーションアルバムに含まれる楽曲を取得
        compilation_tracks = sp.album_tracks(compilation['id'])['items']
        for track in compilation_tracks:
            track_name = track['name']
            track_id = track['id']
            compilation_info['tracks'].append({'name': track_name, 'track_id': track_id})

        result.append(compilation_info)

    return result

# musixmatchの認証情報を設定
def get_musixmatch_api_key():
    api_key = os.environ.get('MUSIXMATCH_API_KEY')
    return api_key

# musixmatchのtrack_idから歌詞を取得
def get_lyrics(track_id):
    api_key = get_musixmatch_api_key() # 環境変数からAPIキーを取得
    base_url = "https://api.musixmatch.com/ws/1.1/"
    endpoint = f"{base_url}track.lyrics.get?track_id={track_id}&apikey={api_key}"

    response = requests.get(endpoint)
    if response.status_code == 200:
        return response.json() # 歌詞情報をJSONとして返す
    else:
        return None # エラー処理

#アーティスト名と楽曲名からmusixmatchのtrack_idを取得
def get_musixmatch_track_id(artist_name, song_name):
    api_key = get_musixmatch_api_key() # 環境変数からAPIキーを取得
    base_url = "https://api.musixmatch.com/ws/1.1/"
    query = f"track.search?q_track={song_name}&q_artist={artist_name}&apikey={api_key}"
    endpoint = base_url + query

    response = requests.get(endpoint)

    if response.status_code == 200:
        track_data = response.json()['message']['body']['track_list']

        if track_data:
            return track_data[0]['track']['track_id'] # トラックIDを返す
    return None

# artist_details
@app.route('/artist/<artist_id>')
def artist_details(artist_id):
    # アーティストの詳細情報、トップトラック、最新のアルバム情報を取得
    artist_details, top_tracks_details, latest_album_details = get_artist_details(artist_id)
    # 取得した情報を使ってテンプレートをレンダリングして返す
    return render_template('artist_details.html', artist=artist_details, top_tracks=top_tracks_details, latest_album=latest_album_details)

# album_details
@app.route('/artist/<artist_id>/albums/<album_id>')
def album_details(artist_id, album_id):
    # アルバム詳細の取得ロジック
    album = get_album_details(album_id)
    return render_template('album_details.html', album=album)

# albums_and_tracks_list
@app.route('/artist/<artist_id>/all_albums_and_songs', methods=['GET'])
@app.route('/artist/<artist_id>/all_albums_and_songs/page/<int:page>', methods=['GET'])
def all_albums_and_songs_for_artist(artist_id, page=1):
    per_page = 10
    albums_with_songs = get_artist_albums_with_songs(artist_id, page, per_page)

    # 総アルバム数を取得して、総ページ数を計算
    total_albums = count_total_albums(artist_id)
    total_pages = (total_albums + per_page - 1) // per_page

    return render_template('albums_and_tracks_list.html', 
                           albums_with_songs=albums_with_songs, 
                           artist_id=artist_id, 
                           page=page, 
                           total_pages=total_pages,
                           total_albums=total_albums,
                           per_page=per_page) # per_page変数を追加

# singles_and_tracks_list
@app.route('/artist/<artist_id>/all_singles_and_songs', methods=['GET'])
@app.route('/artist/<artist_id>/all_singles_and_songs/page/<int:page>', methods=['GET'])
def all_singles_and_songs_for_artist(artist_id, page=1):
    per_page = 10
    singles_with_songs = get_artist_singles_with_songs(artist_id, page, per_page)
    total_singles = count_total_singles(artist_id)
    total_pages = (total_singles + per_page - 1) // per_page
    return render_template('singles_and_tracks_list.html',
                           singles_with_songs=singles_with_songs,
                           artist_id=artist_id,
                           page=page,
                           total_pages=total_pages,
                           total_singles=total_singles,
                           per_page=per_page)

# compilations_and_tracks_list
@app.route('/artist/<artist_id>/all_compilations_and_songs', methods=['GET'])
@app.route('/artist/<artist_id>/all_compilations_and_songs/page/<int:page>', methods=['GET'])
def all_compilations_and_songs_for_artist(artist_id, page=1):
    per_page = 10
    compilations_with_songs = get_artist_compilations_with_songs(artist_id, page, per_page)
    total_compilations = count_total_compilations(artist_id)
    total_pages = (total_compilations + per_page - 1) // per_page
    return render_template('compilations_and_tracks_list.html',
                           compilations_with_songs=compilations_with_songs,
                           artist_id=artist_id,
                           page=page,
                           total_pages=total_pages,
                           total_compilations=total_compilations,
                           per_page=per_page)

# help_song_details.html 
@app.route('/help_song_details')
def help_song_details():
    return render_template('help_song_details.html')

# help_index.html
@app.route('/help_index')
def help_index():
    return render_template('help_index.html')

# 楽曲詳細画面のルート
@app.route('/song_details/<song_id>', methods=['GET'])
def song_details(song_id):
    song = get_song_details(song_id)
    return render_template('song_details.html', song=song, song_id=song_id)


# メインのエントリーポイント
if __name__ == "__main__":
    check_api_keys()  # APIキーのチェック
    debug_mode = False
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
