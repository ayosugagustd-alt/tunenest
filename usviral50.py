# 標準ライブラリ
import json  # JSON形式データのエンコード/デコード
import logging  # ロギング機能
import os  # OSレベルの機能を扱う
import time  # 時間に関する機能
from urllib.parse import quote_plus  # URLエンコーディング
from collections import defaultdict  # デフォルト値を持つ辞書

# サードパーティのHTTP関連ライブラリ
import requests  # HTTPリクエスト

# Flask関連ライブラリ
from flask import Flask  # Flask本体
from flask import jsonify  # JSONレスポンス生成
from flask import render_template  # HTMLテンプレートレンダリング
from flask import request  # HTTPリクエストオブジェクト
from flask import send_from_directory  # ファイル送信
from flask import url_for  # URL生成

# Google APIクライアント
from googleapiclient.discovery import build  # APIサービスビルド
from googleapiclient.errors import HttpError  # Google APIのHTTPエラー

# Spotify APIクライアント
from spotipy.oauth2 import SpotifyClientCredentials  # Spotify OAuth2認証
from spotipy import Spotify  # Spotify API本体

from threading import Lock
from functools import lru_cache


# 環境変数を一度だけ読み取る。これらの変数はAPI認証に使用される。
# 存在しない場合はNoneを設定。
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", None)  # Spotify API
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", None)
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", None)  # YouTube API


app = Flask(__name__)

# グローバル変数とロックを初期化
spotify_client = None
client_lock = Lock()

# playlists変数の初期化
playlists = None

try:
    # プレイリストIDと名前の辞書を開く
    with open("config/playlists.json", "r", encoding="utf-8") as f:
        # playlistsはインデックスページのルーティング処理で参照する
        playlists = json.load(f)
except FileNotFoundError:
    logging.warning("playlists.jsonが見つかりません。")
except json.JSONDecodeError:
    logging.warning("playlists.jsonの形式が不正です。")


# APIキーをチェック
def check_api_keys():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise ValueError("Spotifyの認証情報が設定されていません。環境変数で設定してください。")

    if not YOUTUBE_API_KEY:
        raise ValueError("YouTube APIのキーが設定されていません。環境変数で設定してください。")


# Spotify API Clientを生成して返す。言語設定はしない。
def get_spotify_client():
    global spotify_client
    with client_lock:
        if not spotify_client:
            spotify_client = Spotify(
                client_credentials_manager=SpotifyClientCredentials(
                    client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET
                ),
                language="ja",  # 動的に言語設定
            )
        return spotify_client


# トラック情報を取得する関数
# 引数: track (Spotify APIから取得したトラックの辞書)
# 戻り値: トラック情報を含む辞書
def get_track_info(track):
    try:
        image_url = (
            track["album"]["images"][0]["url"]
            if track["album"]["images"]
            else url_for("static", filename="TuneNest.png")
        )
        spotify_link = track["external_urls"]["spotify"]
        artist_name = track["artists"][0]["name"]
        track_info = {
            "id": track["id"],
            "url": track["preview_url"],
            "name": track["name"],
            "artist": artist_name,
            "image_url": image_url,
            "spotify_link": spotify_link,
        }
        return track_info
    except KeyError as e:
        logging.warning(f"不良データを検出: {e}")
        return None  # 不良データを無視


# robots.txtファイルを返すルート。
# Flaskのstaticフォルダからファイルを送信します。
@app.route("/robots.txt")
def static_from_root():
    return send_from_directory(app.static_folder, "robots.txt")


# インデックスページのルーティング処理
@app.route("/")
def index():
    try:
        # デフォルトIDかクエリパラメータIDを設定
        playlist_id = request.args.get("playlist_id", "37i9dQZF1DWUQlpHXZRO4T")

        # Spotifyクライアントを取得
        sp = get_spotify_client()

        # プレイリストの詳細情報を取得
        playlist_details = sp.playlist(playlist_id, market="JP")

        # クエリパラメータからプレイリスト説明を取得
        custom_description = request.args.get("description")
        if custom_description:
            playlist_description = custom_description
        else:
            # プレイリストのdescriptionを取得
            playlist_description = playlist_details.get("description", "No description")

        # プレイリストのURLを取得
        playlist_url = playlist_details.get("external_urls", {}).get("spotify", "#")

        # 現実のプレイリスト名を取得
        actual_playlist_name = playlist_details.get("name", "No playlist name")

        # クエリパラメータか現実のプレイリスト名を取得
        # ドロップリストではプレイリスト名を渡していないので
        # 通常クエリパラメータを与えられることはありません
        playlist_name = request.args.get("playlist_name", actual_playlist_name)

        # クエリパラメータからカバー画像のURLを取得
        custom_artwork_img = request.args.get("artwork_img")

        # プレイリストのカバー画像URLを安全に取得
        collage_filename = url_for("static", filename="TuneNest.png")  # デフォルト値
        if custom_artwork_img:
            collage_filename = url_for("static", filename=custom_artwork_img)
        elif playlist_details.get("images") and playlist_details["images"]:
            # プレイリストのimagesが存在し、空のリストでないことを確認
            collage_filename = playlist_details["images"][0].get(
                "url", collage_filename
            )

        # プレイリストのトラックを取得
        MAX_TRACKS = 500  # 最大取得曲数を定義

        offset = 0
        limit = 100  # 1回のAPI呼び出しで取得できる最大トラック数
        all_tracks = []  # 全トラックを格納するリスト

        exceeds_max_tracks = False  # 500曲以上かどうかのフラグ

        while True:
            results = sp.playlist_tracks(
                playlist_id, offset=offset, limit=limit, market="JP"
            )
            if results is None or results["items"] is None:
                raise ValueError("Spotify APIが正常な値を返しませんでした。")

            all_tracks.extend(results["items"])

            # 上限に達した場合、ループを抜ける
            if len(all_tracks) > MAX_TRACKS:
                exceeds_max_tracks = True
                all_tracks = all_tracks[:MAX_TRACKS]
                break

            # 全てのトラックを取得した場合、ループを抜ける
            if len(results["items"]) < limit:
                break

            offset += limit

        # トラック情報を整形（抜け番対応とNoneチェック）
        all_tracks_info = []
        for item in all_tracks:
            track = item.get("track")  # itemから"track"キーの値を安全に取得
            if track is not None:  # trackがNoneでないことを確認
                track_info = get_track_info(track)
                if track_info is not None:  # get_track_infoの結果がNoneでないことを確認
                    all_tracks_info.append(track_info)

        # 有効なトラック情報のみをフィルタリング
        valid_tracks_info = [track for track in all_tracks_info if track]

        # カテゴリごとにプレイリストを整理
        playlists_grouped = defaultdict(list)
        for id, name in playlists.items():
            try:
                category, temp_playlist_name = name.split(" : ", 1)
                playlists_grouped[category].append((id, temp_playlist_name))
            except ValueError as e:
                error = f"Error occurred with playlist ID: {id}, name: '{name}'. Error message: {str(e)}"
                return render_template("error.html", error=error)

        # HTMLテンプレートをレンダリング
        return render_template(
            "index.html",
            playlist_name=playlist_name,
            playlists_grouped=playlists_grouped,  # 追加
            tracks=valid_tracks_info,
            collage_filename=collage_filename,
            playlist_description=playlist_description,
            playlist_url=playlist_url,
            exceeds_max_tracks=exceeds_max_tracks,
        )
    except Exception as e:
        # エラーページを表示
        return render_template("error.html", error=str(e))


# アーティストの詳細情報とトップ曲、最新のアルバムを取得
# 引数: artist_id (SpotifyのアーティストID)
# 戻り値: アーティストの詳細、トップ曲のリスト、最新のアルバムの詳細を含む辞書
# キャッシュを適用
@lru_cache(maxsize=128)  # キャッシュのサイズを適宜設定
def get_cached_artist_details(artist_id, sp):
    # 既に取得したSpotifyクライアントを使用する
    artist = sp.artist(artist_id)
    return {
        "id": artist["id"],
        "name": artist["name"],
        "image_url": artist["images"][0]["url"] if artist["images"] else None,
        "popularity": artist["popularity"],
        "genres": artist["genres"],
        "followers": artist["followers"]["total"],
    }


def get_artist_details(artist_id):
    # Spotifyクライアントを取得
    sp = get_spotify_client()

    # キャッシュされたアーティストの基本情報を取得
    artist_details = get_cached_artist_details(artist_id, sp)

    # アーティストのトップ曲を取得
    top_tracks = sp.artist_top_tracks(artist_id, country="JP")["tracks"]
    top_tracks_details = [
        {"name": track["name"], "id": track["id"]} for track in top_tracks
    ]

    # アーティストのアルバムを取得し、最新のアルバムを特定
    albums = sp.artist_albums(artist_id, album_type="album")["items"]
    latest_album = albums[0] if albums else None
    latest_album_details = (
        {"name": latest_album["name"], "id": latest_album["id"], "artist_id": artist_id}
        if latest_album
        else None
    )

    return artist_details, top_tracks_details, latest_album_details


# アルバムIDを使用してアルバムの詳細情報を取得
# 引数: album_id (SpotifyのアルバムID)
# 戻り値: アルバムの詳細情報を含む辞書
def get_album_details(album_id):
    # Spotifyクライアントの取得
    sp = get_spotify_client()

    # アルバムIDを使用してアルバム情報を取得
    album = sp.album(album_id, market="JP")

    # 収録曲リストを作成
    tracks = [
        {"name": track["name"], "length": track["duration_ms"], "id": track["id"]}
        for track in album["tracks"]["items"]
    ]

    # アルバムの詳細情報を辞書で整理
    details = {
        "name": album["name"],  # アルバム名
        "release_date": album["release_date"],  # リリース日
        "image": album["images"][0]["url"],  # ジャケット画像のURL
        "genres": album["genres"],  # ジャンル（通常、アルバムにジャンルは含まれていない）
        "artists": [
            {"name": artist["name"], "id": artist["id"]} for artist in album["artists"]
        ],  # 参加アーティスト
        "tracks": tracks,  # 収録曲リスト
        "popularity": album["popularity"],  # 人気度
    }

    # 詳細情報を整理して返却
    return details


# 曲のIDを受け取り、その曲の詳細情報とオーディオ特性を返す
# (タイムアウト対応版)
# 引数: song_id (Spotifyの曲ID)
# 戻り値: 曲の詳細情報とオーディオ特性を含む辞書。
# 最大リトライ回数を超えた場合はエラーをスローする。
@lru_cache(maxsize=128)
def get_cached_track(song_id, sp):
    return sp.track(song_id)


@lru_cache(maxsize=128)
def get_cached_audio_features(song_id, sp):
    return sp.audio_features([song_id])[0]


def get_song_details_with_retry(song_id, max_retries=3, delay=5):
    retries = 0
    while retries <= max_retries:
        try:
            sp = get_spotify_client()  # Spotifyクライアントの取得
            song_details = get_cached_track(song_id, sp)  # 曲の基本情報を取得
            audio_features = get_cached_audio_features(song_id, sp)  # 曲のオーディオ特性を取得

            # アルバムのアートワークURLを取得
            album_artwork_url = song_details["album"]["images"][0]["url"]

            # アーティスト名を取得（複数の場合あり）
            artists = [
                {"name": artist["name"], "id": artist["id"]}
                for artist in song_details["artists"]
            ]

            # 成功した場合、曲の詳細情報を返す
            return {
                "acousticness": audio_features["acousticness"] * 100,
                "danceability": audio_features["danceability"] * 100,
                "duration": song_details["duration_ms"] / 1000,
                "energy": audio_features["energy"] * 100,
                "instrumentalness": audio_features["instrumentalness"] * 100,
                "key": audio_features["key"],
                "mode": audio_features["mode"],
                "name": song_details["name"],
                "popularity": song_details["popularity"],
                "tempo": audio_features["tempo"],
                "time_signature": audio_features["time_signature"],
                "valence": audio_features["valence"] * 100,
                "album_artwork_url": album_artwork_url,
                "artists": artists,
            }
        except Exception as e:  # タイムアウトやその他の例外をキャッチ
            logging.error(f"An error occurred: {e}. Retrying...")
            retries += 1
            time.sleep(delay)  # delay秒待ってからリトライ

    raise Exception("Max retries reached")  # 最大を超えたら例外をスロー


# 総リリース数をカウントする関数
# 引数: artist_id (SpotifyのアーティストID), release_type (リリースの種類)
# 戻り値: 総リリース数
def count_total_releases(artist_id, release_type):
    sp = get_spotify_client()

    total_releases = sp.artist_albums(artist_id, album_type=release_type)["total"]
    return total_releases


# アーティストのアルバムとその楽曲をページ単位で取得する関数
# 引数: artist_id (SpotifyのアーティストID), page (ページ番号), per_page (1ページあたりのアルバム数)
# 戻り値: アーティストのアルバムと楽曲情報を含む辞書のリスト
def get_artist_albums_with_songs(artist_id, page, per_page=10):
    sp = get_spotify_client()
    offset = (page - 1) * per_page
    limit = per_page

    # アーティストのアルバムをページ単位で取得
    albums = sp.artist_albums(
        artist_id, album_type="album", offset=offset, limit=limit
    )["items"]
    result = []

    for album in albums:
        album_info = {
            "name": album["name"],
            "release_date": album["release_date"],
            "tracks": [],
            "album_id": album["id"],  # アルバムID
            "artist_id": artist_id,  # アーティストID
        }

        # 各アルバムに含まれる楽曲を取得
        album_tracks = sp.album_tracks(album["id"], market="JP")["items"]
        for track in album_tracks:
            track_name = track["name"]
            track_id = track["id"]
            album_info["tracks"].append({"name": track_name, "track_id": track_id})

        result.append(album_info)

    return result


# アーティストのシングルとその楽曲情報を取得
# 引数: artist_id (SpotifyのアーティストID), page (ページ番号), per_page (1ページあたりのアイテム数)
# 戻り値: シングル情報とその楽曲を含むリスト
def get_artist_singles_with_songs(artist_id, page, per_page=10):
    # Spotifyクライアントの取得
    sp = get_spotify_client()
    offset = (page - 1) * per_page
    limit = per_page

    # アーティストのシングルをページ単位で取得
    singles = sp.artist_albums(
        artist_id, album_type="single", offset=offset, limit=limit
    )["items"]
    result = []

    # シングル情報を取得
    for single in singles:
        single_info = {
            "name": single["name"],
            "release_date": single["release_date"],
            "tracks": [],
            "single_id": single["id"],  # シングルIDの追加
            "artist_id": artist_id,  # アーティストIDの追加
        }

        # シングルに含まれる楽曲を取得
        single_tracks = sp.album_tracks(single["id"], market="JP")["items"]
        for track in single_tracks:
            track_name = track["name"]
            track_id = track["id"]
            single_info["tracks"].append({"name": track_name, "track_id": track_id})

        result.append(single_info)

    return result


# get_artist_compilations_with_songs()
# アーティストのコンピレーションアルバムとその楽曲を取得
# 引数: artist_id (SpotifyのアーティストID), page (ページ番号),
# per_page (1ページ当たりのアイテム数)
# 戻り値: コンピレーションアルバムとその楽曲情報を含むリスト
def get_artist_compilations_with_songs(artist_id, page, per_page=10):
    # Spotifyクライアントを取得
    sp = get_spotify_client()

    # ページングのためのオフセットとリミットを計算
    offset = (page - 1) * per_page
    limit = per_page

    # アーティストのコンピレーションアルバムをページ単位で取得
    compilations = sp.artist_albums(
        artist_id, album_type="compilation", offset=offset, limit=limit
    )["items"]
    result = []

    # 各コンピレーションアルバムの詳細情報を取得
    for compilation in compilations:
        compilation_info = {
            "name": compilation["name"],  # アルバム名
            "release_date": compilation["release_date"],  # リリース日
            "tracks": [],  # 収録曲リスト
            "compilation_id": compilation["id"],  # コンピレーションID
            "artist_id": artist_id,  # アーティストID
        }

        # 各コンピレーションアルバムに含まれる楽曲を取得
        compilation_tracks = sp.album_tracks(compilation["id"], market="JP")["items"]
        for track in compilation_tracks:
            track_name = track["name"]
            track_id = track["id"]
            compilation_info["tracks"].append(
                {"name": track_name, "track_id": track_id}
            )

        result.append(compilation_info)

    return result


# アーティスト詳細ページ
@app.route("/artist/<artist_id>")
def artist_details(artist_id):
    # アーティストの詳細情報、トップトラック、最新のアルバム情報を取得
    artist_details, top_tracks_details, latest_album_details = get_artist_details(
        artist_id
    )

    # 取得した情報を使ってテンプレートをレンダリングして返す
    return render_template(
        "artist_details.html",
        artist=artist_details,
        top_tracks=top_tracks_details,
        latest_album=latest_album_details,
    )


# アルバム詳細ページ
@app.route("/artist/<artist_id>/albums/<album_id>")
def album_details(artist_id, album_id):
    try:
        album = get_album_details(album_id)  # 既存の関数でSpotifyからアルバム情報を取得

        # アーティスト名を結合してからテンプレートに渡す準備
        artist_names = ", ".join([artist["name"] for artist in album["artists"]])

        return render_template(
            "album_details.html",
            album=album,
            artist_names=artist_names,
        )

    except Exception as e:
        return render_template("error.html", error=str(e))


@lru_cache(maxsize=32)
def cached_count_total_releases(artist_id, release_type):
    return count_total_releases(artist_id, release_type)


# 全アルバム表示ページのルーティング処理
# アーティストIDとページ番号（オプション）を引数として受け取る
@lru_cache(maxsize=128)
def cached_get_artist_albums_with_songs(artist_id, page, per_page=10):
    return get_artist_albums_with_songs(artist_id, page, per_page)


@app.route("/artist/<artist_id>/all_albums_and_songs", methods=["GET"])
@app.route("/artist/<artist_id>/all_albums_and_songs/page/<int:page>", methods=["GET"])
def all_albums_and_songs_for_artist(artist_id, page=1):
    per_page = 10  # 1ページあたりのアルバム数
    albums_with_songs = cached_get_artist_albums_with_songs(artist_id, page, per_page)

    # 総アルバム数を取得して、総ページ数を計算
    total_albums = cached_count_total_releases(artist_id, "album")
    total_pages = (total_albums + per_page - 1) // per_page

    # レンダリングされたHTMLテンプレートを返す
    return render_template(
        "albums_and_tracks_list.html",
        albums_with_songs=albums_with_songs,
        artist_id=artist_id,
        page=page,
        total_pages=total_pages,
        total_albums=total_albums,
        per_page=per_page,
    )


# 全シングル表示ページのルート
# アーティストIDとページ番号（オプション）を引数として受け取る
@lru_cache(maxsize=32)  # キャッシュのサイズを32に設定します。必要に応じて調整してください。
def cached_get_artist_singles_with_songs(artist_id, page, per_page):
    return get_artist_singles_with_songs(artist_id, page, per_page)


@app.route("/artist/<artist_id>/all_singles_and_songs", methods=["GET"])
@app.route("/artist/<artist_id>/all_singles_and_songs/page/<int:page>", methods=["GET"])
def all_singles_and_songs_for_artist(artist_id, page=1):
    per_page = 10  # 1ページあたりのシングル数
    singles_with_songs = cached_get_artist_singles_with_songs(artist_id, page, per_page)

    # 総シングル数を取得し、総ページ数を計算
    total_singles = cached_count_total_releases(artist_id, "single")
    total_pages = (total_singles + per_page - 1) // per_page

    # レンダリングされたHTMLテンプレートを返す
    return render_template(
        "singles_and_tracks_list.html",
        singles_with_songs=singles_with_songs,
        artist_id=artist_id,
        page=page,
        total_pages=total_pages,
        total_singles=total_singles,
        per_page=per_page,
    )


# 全コンピレーションアルバム表示ページのルーティング処理
# アーティストIDとページ番号（オプション）を引数として受け取る
@lru_cache(maxsize=32)
def cached_get_artist_compilations_with_songs(artist_id, page, per_page=10):
    return get_artist_compilations_with_songs(artist_id, page, per_page)


@app.route("/artist/<artist_id>/all_compilations_and_songs", methods=["GET"])
@app.route(
    "/artist/<artist_id>/all_compilations_and_songs/page/<int:page>", methods=["GET"]
)
def all_compilations_and_songs_for_artist(artist_id, page=1):
    per_page = 10  # 1ページあたりのコンピレーション数
    compilations_with_songs = cached_get_artist_compilations_with_songs(
        artist_id, page, per_page
    )

    # 総コンピレーション数を取得し、総ページ数を計算
    total_compilations = cached_count_total_releases(artist_id, "compilation")
    total_pages = (total_compilations + per_page - 1) // per_page

    # レンダリングされたHTMLテンプレートを返す
    return render_template(
        "compilations_and_tracks_list.html",
        compilations_with_songs=compilations_with_songs,
        artist_id=artist_id,
        page=page,
        total_pages=total_pages,
        total_compilations=total_compilations,
        per_page=per_page,
    )


# 楽曲詳細ヘルプページのルート
# help_song_details.htmlテンプレートをレンダリングして返す
@app.route("/help_song_details")
def help_song_details():
    return render_template("help_song_details.html")


# 楽曲詳細ページのルート
# 引数: song_id (Spotifyの楽曲ID)
# get_song_details関数で楽曲の詳細を取得し、
# song_details.htmlテンプレートをレンダリングして返す
@app.route("/song_details/<song_id>", methods=["GET"])
def song_details(song_id):
    try:
        song = get_song_details_with_retry(song_id)  # Spotifyから曲情報を取得

        return render_template(
            "song_details.html",
            song=song,
            song_id=song_id,
        )

    except Exception as e:
        return render_template("error.html", error=str(e))


# キーワードでプレイリストを検索する新しいルート
@app.route("/search_playlist", methods=["GET"])
def search_playlist():
    keyword = request.args.get("keyword")
    if not keyword:
        return jsonify({"error": "No keyword provided"}), 400

    sp = get_spotify_client()

    # Spotify APIでキーワードでプレイリストを検索
    results = sp.search(q=keyword, type="playlist", limit=1, market="JP")
    if (
        not results
        or not results.get("playlists")
        or not results["playlists"].get("items")
    ):
        return jsonify({"error": "No playlists found"}), 404

    playlist = results["playlists"]["items"][0]
    playlist_id = playlist["id"]

    return jsonify({"playlist_id": playlist_id})


# メインのエントリーポイント
# スクリプトが直接実行された場合に以下のコードが実行される
if __name__ == "__main__":
    check_api_keys()  # APIキーの存在をチェック
    debug_mode = False  # デバッグモードの設定
    port = int(os.environ.get("PORT", 8080))  # 環境変数からポート番号取得
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=port, debug=debug_mode)  # Webアプリを起動
