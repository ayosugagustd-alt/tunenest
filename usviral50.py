# 標準ライブラリ
import os
import unicodedata
# サードパーティライブラリ
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import send_from_directory
from flask import url_for

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# 定数の定義
DEFAULT_PLAYLIST_ID = '37i9dQZF1DXdY5tVYFPWb2'
DEFAULT_PLAYLIST_NAME = 'City Pop'

# 環境変数を一度だけ読み取る（存在しない場合はNone）
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', None)
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', None)
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', None)
MUSIXMATCH_API_KEY = os.getenv('MUSIXMATCH_API_KEY', None)


# Flaskアプリを初期化
app = Flask(__name__)

# APIキーをチェック
def check_api_keys():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise ValueError("Spotifyの認証情報が設定されていません。環境変数で設定してください。")

    if not YOUTUBE_API_KEY:
        raise ValueError("YouTube APIのキーが設定されていません。環境変数で設定してください。")

# Spotifyクライアントを取得する関数
# 戻り値: 認証済みのSpotifyクライアントオブジェクト
class SpotifyClientSingleton:
    _instance = None

    @staticmethod
    def get_instance():
        if SpotifyClientSingleton._instance is None:
            SpotifyClientSingleton._instance = spotipy.Spotify(
                client_credentials_manager=SpotifyClientCredentials(
                    client_id=SPOTIFY_CLIENT_ID,
                    client_secret=SPOTIFY_CLIENT_SECRET
                )
            )
        return SpotifyClientSingleton._instance

"""
def get_spotify_client():
    return spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))
"""


# トラック情報を取得する関数
# 引数: track (Spotify APIから取得したトラックの辞書)
# 戻り値: トラック情報を含む辞書
def get_track_info(track):
    track_info = {
        'id': track['id'],
        'url': track['preview_url'],
        'name': track['name'],
        'artist': track['artists'][0]['name'],
        'image_url': track['album']['images'][0]['url'],
        'spotify_link': track['external_urls']['spotify']
    }
    return track_info

# キャッシュ用の辞書（検索クエリをキー、動画IDを値とする）
youtube_url_cache = {}

# YouTube動画を検索する関数
# 引数:
#   - q: 検索クエリ（例："Beatles Let it be"）
#   - max_results: 返す最大結果数（デフォルトは1）
#   - youtube_api_key: YouTube APIキー（デフォルトはNone）
# 戻り値:
#   - 動画のIDまたはエラーメッセージを含む辞書
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

        # キャッシュにURLを保存（次回の高速化のため）
        video_id = videos[0] if videos else None
        youtube_url_cache[q] = video_id

        return video_id
    except HttpError as e:
        return {'error': f"An HTTP error occurred: {e}"}

# robots.txtファイルを返すルート。
# このrobots.txtには、トップページのみをクロールさせる設定があります。
# Flaskのstaticフォルダからファイルを送信します。
@app.route('/robots.txt')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])

# コラージュ画像のファイルパスを取得する関数
# 引数: playlist_id (プレイリストのID)
# 戻り値: コラージュ画像のファイルパス
def get_collage_filepath(playlist_id):
    collage_filename = f"{playlist_id}_collage.jpg"
    return url_for('static', filename=collage_filename)

# インデックスページのルーティング処理
@app.route('/')
def index():
    try:
        # クエリパラメータからプレイリストのIDと名前を取得
        playlist_id = request.args.get('playlist_id', DEFAULT_PLAYLIST_ID)
        playlist_name = request.args.get('playlist_name', DEFAULT_PLAYLIST_NAME)

        # コラージュ画像のパスを取得
        collage_filename = get_collage_filepath(playlist_id)
        if collage_filename is None:
            raise ValueError("コラージュ画像が生成されていません。")

        # Spotifyクライアントを取得してプレイリストのトラックを取得
#        sp = get_spotify_client()
        sp = SpotifyClientSingleton.get_instance()

        results = sp.playlist_tracks(playlist_id)
        if results is None or results['items'] is None:
            raise ValueError("Spotify APIが正常な値を返しませんでした。")

        # トラック情報を整形
        tracks = [get_track_info(item['track']) for item in results['items']]

        # HTMLテンプレートをレンダリング
        return render_template('index.html', 
                                tracks=tracks, 
                                playlist_name=playlist_name,
                                collage_filename=collage_filename)
    except Exception as e:
        # エラーページを表示
        return render_template('error.html', error=str(e))

# YouTube検索のルーティング処理
@app.route('/youtube')
def youtube():
    # クエリパラメータからトラック名とアーティスト名を取得
    track_name = request.args.get('track')
    artist_name = request.args.get('artist')

    # YouTubeで動画を検索
    video_id = youtube_search(f"{track_name} {artist_name}", youtube_api_key=YOUTUBE_API_KEY)

    # エラーがあればエラーページを表示
    if isinstance(video_id, dict) and 'error' in video_id:
        return render_template('error.html', error=f"エラーが発生しました。：{video_id['error']}")

    # 動画IDが存在すれば結果を表示
    if video_id:
        return render_template('youtube.html', video_id=video_id)
    else:
        return "動画が見つかりません。", 404

# アーティストの詳細情報とトップ曲、最新のアルバムを取得
# 引数: artist_id (SpotifyのアーティストID)
# 戻り値: アーティストの詳細、トップ曲のリスト、最新のアルバムの詳細を含む辞書
def get_artist_details(artist_id):
#    sp = get_spotify_client()
    sp = SpotifyClientSingleton.get_instance()

    # アーティストの基本情報を取得
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
# 引数: album_id (SpotifyのアルバムID)
# 戻り値: アルバムの詳細情報を含む辞書
def get_album_details(album_id):
    # Spotifyクライアントの取得
#    sp = get_spotify_client()
    sp = SpotifyClientSingleton.get_instance()

    # アルバムIDを使用してアルバム情報を取得
    album = sp.album(album_id)

    # 収録曲リストを作成
    tracks = [{'name': track['name'], 'length': track['duration_ms'], 'id': track['id']} for track in album['tracks']['items']]

    # アルバムの詳細情報を辞書で整理
    details = {
        'name': album['name'],  # アルバム名
        'release_date': album['release_date'],  # リリース日
        'image': album['images'][0]['url'],  # ジャケット画像のURL
        'genres': album['genres'],  # ジャンル（通常、アルバムにジャンルは含まれていない）
        'artists': [{'name': artist['name'], 
        'id': artist['id']} for artist in album['artists']],  # 参加アーティスト
        'tracks': tracks,  # 収録曲リスト
        'popularity': album['popularity']  # 人気度
    }

    # 詳細情報を整理して返却
    return details

# 曲のIDを受け取り、その曲の詳細情報とオーディオ特性を返す
# 引数: song_id (Spotifyの曲ID)
# 戻り値: 曲の詳細情報とオーディオ特性を含む辞書
def get_song_details(song_id):
#    sp = get_spotify_client() # Spotifyクライアントの取得
    sp = SpotifyClientSingleton.get_instance()
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

    # 歌詞が存在する場合は整形
    if 'lyrics' in lyrics['message']['body']:
        lyrics_body = lyrics['message']['body']['lyrics']['lyrics_body']
        clean_lyrics = lyrics_body.split('\n*******')[0]
        clean_lyrics = clean_lyrics.replace('\n', '<br>')
    else:
        clean_lyrics = 'Lyrics not found.'

    # 必要な情報を整理して返却
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
        'album_artwork_url': album_artwork_url, # アートワークURL
		'artists': artists, # アーティスト情報
        'lyrics': clean_lyrics, # 歌詞情報
    }

# 総リリース数をカウントする関数
# 引数: artist_id (SpotifyのアーティストID), release_type (リリースの種類)
# 戻り値: 総リリース数
def count_total_releases(artist_id, release_type):
#    sp = get_spotify_client()
    sp = SpotifyClientSingleton.get_instance()
    total_releases = sp.artist_albums(artist_id, album_type=release_type)['total']
    return total_releases

# アーティストのアルバムとその楽曲をページ単位で取得する関数
# 引数: artist_id (SpotifyのアーティストID), page (ページ番号), per_page (1ページあたりのアルバム数)
# 戻り値: アーティストのアルバムと楽曲情報を含む辞書のリスト
def get_artist_albums_with_songs(artist_id, page, per_page=10):
#    sp = get_spotify_client()
    sp = SpotifyClientSingleton.get_instance()
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
            'album_id': album['id'],         # アルバムID
            'artist_id': artist_id           # アーティストID
        }

        # 各アルバムに含まれる楽曲を取得
        album_tracks = sp.album_tracks(album['id'])['items']
        for track in album_tracks:
            track_name = track['name']
            track_id = track['id']
            album_info['tracks'].append({'name': track_name, 'track_id': track_id})

        result.append(album_info)

    return result

# アーティストのシングルとその楽曲情報を取得
# 引数: artist_id (SpotifyのアーティストID), page (ページ番号), per_page (1ページあたりのアイテム数)
# 戻り値: シングル情報とその楽曲を含むリスト
def get_artist_singles_with_songs(artist_id, page, per_page=10):
    # Spotifyクライアントの取得
#    sp = get_spotify_client()
    sp = SpotifyClientSingleton.get_instance()
    offset = (page - 1) * per_page
    limit = per_page

    # アーティストのシングルをページ単位で取得
    singles = sp.artist_albums(artist_id, album_type='single', offset=offset, limit=limit)['items']
    result = []

    # シングル情報を取得
    for single in singles:
        single_info = {
            'name': single['name'],
            'release_date': single['release_date'],
            'tracks': [],
            'single_id': single['id'], # シングルIDの追加
            'artist_id': artist_id     # アーティストIDの追加
        }

        # シングルに含まれる楽曲を取得
        single_tracks = sp.album_tracks(single['id'])['items']
        for track in single_tracks:
            track_name = track['name']
            track_id = track['id']
            single_info['tracks'].append({'name': track_name, 'track_id': track_id})

        result.append(single_info)

    return result

# get_artist_compilations_with_songs()
# アーティストのコンピレーションアルバムとその楽曲を取得
# 引数: artist_id (SpotifyのアーティストID), page (ページ番号), 
# per_page (1ページ当たりのアイテム数)
# 戻り値: コンピレーションアルバムとその楽曲情報を含むリスト
def get_artist_compilations_with_songs(artist_id, page, per_page=10):
    # Spotifyクライアントを取得
#    sp = get_spotify_client()
    sp = SpotifyClientSingleton.get_instance()

    # ページングのためのオフセットとリミットを計算
    offset = (page - 1) * per_page
    limit = per_page

    # アーティストのコンピレーションアルバムをページ単位で取得
    compilations = sp.artist_albums(artist_id, album_type='compilation', offset=offset, limit=limit)['items']
    result = []

    # 各コンピレーションアルバムの詳細情報を取得
    for compilation in compilations:
        compilation_info = {
            'name': compilation['name'],    # アルバム名
            'release_date': compilation['release_date'],    #リリース日
            'tracks': [],   # 収録曲リスト
            'compilation_id': compilation['id'], #  コンピレーションID
            'artist_id': artist_id  # アーティストID
        }

        # 各コンピレーションアルバムに含まれる楽曲を取得
        compilation_tracks = sp.album_tracks(compilation['id'])['items']
        for track in compilation_tracks:
            track_name = track['name']
            track_id = track['id']
            compilation_info['tracks'].append({'name': track_name, 'track_id': track_id})

        result.append(compilation_info)

    return result

# musixmatchのtrack_idから歌詞を取得
# 引数: track_id (Musixmatchの楽曲ID)
# 戻り値: 歌詞情報を含むJSONデータ、またはエラー時にはNone
def get_lyrics(track_id):
    base_url = "https://api.musixmatch.com/ws/1.1/"
    endpoint = f"{base_url}track.lyrics.get?track_id={track_id}&apikey={MUSIXMATCH_API_KEY}"

    # 歌詞情報を取得するAPIリクエストを送信
    response = requests.get(endpoint)
    if response.status_code == 200:
        return response.json() # 歌詞情報をJSONとして返す
    else:
        return None # 200以外の場合はエラーとしてNoneを返す 

# アーティスト名と楽曲名からmusixmatchのtrack_idを取得
# 引数: artist_name (アーティスト名), song_name (楽曲名)
# 戻り値: musixmatchのトラックID、またはエラー時にはNone
def get_musixmatch_track_id(artist_name, song_name):
    base_url = "https://api.musixmatch.com/ws/1.1/"
    query = f"track.search?q_track={song_name}&q_artist={artist_name}&apikey={MUSIXMATCH_API_KEY}"
    endpoint = base_url + query

    # musixmatch APIにリクエストを送信
    response = requests.get(endpoint)

    if response.status_code == 200:
        track_data = response.json()['message']['body']['track_list']

        if track_data:
            return track_data[0]['track']['track_id'] # 最初のトラックIDを返す
    return None     # エラーまたは該当なしの場合はNoneを返す

# アーティスト詳細ページ 
@app.route('/artist/<artist_id>')
def artist_details(artist_id):
    # アーティストの詳細情報、トップトラック、最新のアルバム情報を取得
    artist_details, top_tracks_details, latest_album_details = get_artist_details(artist_id)
    # 取得した情報を使ってテンプレートをレンダリングして返す
    return render_template('artist_details.html', artist=artist_details, top_tracks=top_tracks_details, latest_album=latest_album_details)

# アルバム詳細ページ 
@app.route('/artist/<artist_id>/albums/<album_id>')
def album_details(artist_id, album_id):
    # アルバム詳細の取得ロジック
    album = get_album_details(album_id)
    return render_template('album_details.html', album=album)

# 全アルバム表示ページのルーティング処理
# アーティストIDとページ番号（オプション）を引数として受け取る
@app.route('/artist/<artist_id>/all_albums_and_songs', methods=['GET'])
@app.route('/artist/<artist_id>/all_albums_and_songs/page/<int:page>', methods=['GET'])
def all_albums_and_songs_for_artist(artist_id, page=1):
    per_page = 10 # 1ページあたりのアルバム数
    albums_with_songs = get_artist_albums_with_songs(artist_id, page, per_page)

    # 総アルバム数を取得して、総ページ数を計算
    total_albums = count_total_releases(artist_id, 'album')
    total_pages = (total_albums + per_page - 1) // per_page

    # レンダリングされたHTMLテンプレートを返す
    return render_template('albums_and_tracks_list.html', 
                           albums_with_songs=albums_with_songs, 
                           artist_id=artist_id, 
                           page=page, 
                           total_pages=total_pages,
                           total_albums=total_albums,
                           per_page=per_page) # 1ページあたりのアルバム数 

# 全シングル表示ページのルート
# アーティストIDとページ番号（オプション）を引数として受け取る
@app.route('/artist/<artist_id>/all_singles_and_songs', methods=['GET'])
@app.route('/artist/<artist_id>/all_singles_and_songs/page/<int:page>', methods=['GET'])
def all_singles_and_songs_for_artist(artist_id, page=1):
    per_page = 10   # 1ページあたりのシングル数
    singles_with_songs = get_artist_singles_with_songs(artist_id, page, per_page)

    # 総シングル数を取得し、総ページ数を計算
    total_singles = count_total_releases(artist_id, 'single')
    total_pages = (total_singles + per_page - 1) // per_page

    # レンダリングされたHTMLテンプレートを返す
    return render_template('singles_and_tracks_list.html',
                           singles_with_songs=singles_with_songs,
                           artist_id=artist_id,
                           page=page,
                           total_pages=total_pages,
                           total_singles=total_singles,
                           per_page=per_page)

# 全コンピレーションアルバム表示ページのルーティング処理
# アーティストIDとページ番号（オプション）を引数として受け取る
@app.route('/artist/<artist_id>/all_compilations_and_songs', methods=['GET'])
@app.route('/artist/<artist_id>/all_compilations_and_songs/page/<int:page>', methods=['GET'])
def all_compilations_and_songs_for_artist(artist_id, page=1):
    per_page = 10   # 1ページあたりのコンピレーション数
    compilations_with_songs = get_artist_compilations_with_songs(artist_id, page, per_page)
    
    # 総コンピレーション数を取得し、総ページ数を計算
    total_compilations= count_total_releases(artist_id, 'compilation')
    total_pages = (total_compilations + per_page - 1) // per_page

    # レンダリングされたHTMLテンプレートを返す
    return render_template('compilations_and_tracks_list.html',
                           compilations_with_songs=compilations_with_songs,
                           artist_id=artist_id,
                           page=page,
                           total_pages=total_pages,
                           total_compilations=total_compilations,
                           per_page=per_page)

# 楽曲詳細ヘルプページのルート
# help_song_details.htmlテンプレートをレンダリングして返す
@app.route('/help_song_details')
def help_song_details():
    return render_template('help_song_details.html')

# 楽曲詳細ページのルート
# 引数: song_id (Spotifyの楽曲ID)
# get_song_details関数で楽曲の詳細を取得し、
# song_details.htmlテンプレートをレンダリングして返す
@app.route('/song_details/<song_id>', methods=['GET'])
def song_details(song_id):
    song = get_song_details(song_id)
    return render_template('song_details.html', song=song, song_id=song_id)


# メインのエントリーポイント
# スクリプトが直接実行された場合に以下のコードが実行される
if __name__ == "__main__":
    check_api_keys()  # APIキーの存在をチェック
    debug_mode = False # デバッグモードの設定
    port = int(os.environ.get('PORT', 8080)) # 環境変数からポート番号を取得、デフォルトは8080
    app.run(host='0.0.0.0', port=port, debug=debug_mode) # Webアプリを起動
