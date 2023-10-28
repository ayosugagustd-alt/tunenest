[1mdiff --git a/usviral50.py b/usviral50.py[m
[1mindex 39942a0..186f721 100644[m
[1m--- a/usviral50.py[m
[1m+++ b/usviral50.py[m
[36m@@ -1,6 +1,7 @@[m
 # 標準ライブラリ[m
 import json[m
 import os[m
[32m+[m[32mimport time[m
 [m
 # サードパーティライブラリ[m
 import requests[m
[36m@@ -367,6 +368,7 @@[m [mdef get_album_details(album_id):[m
 # 曲のIDを受け取り、その曲の詳細情報とオーディオ特性を返す[m
 # 引数: song_id (Spotifyの曲ID)[m
 # 戻り値: 曲の詳細情報とオーディオ特性を含む辞書[m
[32m+[m[32m"""[m
 def get_song_details(song_id):[m
     sp = get_spotify_client()  # Spotifyクライアントの取得[m
     song = sp.track(song_id, market="JP")  # 曲の基本情報を取得[m
[36m@@ -414,6 +416,70 @@[m [mdef get_song_details(song_id):[m
         "artists": artists,  # アーティスト情報[m
         "lyrics": clean_lyrics,  # 歌詞情報を追加[m
     }[m
[32m+[m[32m"""[m
[32m+[m
[32m+[m
[32m+[m[32m# 曲のIDを受け取り、その曲の詳細情報とオーディオ特性を返す[m
[32m+[m[32m# (タイムアウト対応版)[m
[32m+[m[32m# 引数: song_id (Spotifyの曲ID)[m
[32m+[m[32m# 戻り値: 曲の詳細情報とオーディオ特性を含む辞書。最大リトライ回数を超えた場合はNone。[m
[32m+[m[32mdef get_song_details_with_retry(song_id, max_retries=3, delay=5):[m
[32m+[m[32m    retries = 0[m
[32m+[m[32m    while retries <= max_retries:[m
[32m+[m[32m        try:[m
[32m+[m[32m            sp = get_spotify_client()  # Spotifyクライアントの取得[m
[32m+[m[32m            song = sp.track(song_id, market="JP")  # 曲の基本情報を取得[m
[32m+[m[32m            features = sp.audio_features([song_id])[0]  # 曲のオーディオ特性を取得[m
[32m+[m
[32m+[m[32m            # アルバムのアートワークURLを取得[m
[32m+[m[32m            album_artwork_url = song["album"]["images"][0]["url"][m
[32m+[m
[32m+[m[32m            # アーティスト名を取得（複数の場合あり）[m
[32m+[m[32m            artists = [[m
[32m+[m[32m                {"name": artist["name"], "id": artist["id"]}[m
[32m+[m[32m                for artist in song["artists"][m
[32m+[m[32m            ][m
[32m+[m
[32m+[m[32m            # アーティスト名と楽曲名からmusixmatchのtrack_idを取得[m
[32m+[m[32m            musixmatch_track_id = get_musixmatch_track_id([m
[32m+[m[32m                song["artists"][0]["name"], song["name"][m
[32m+[m[32m            )[m
[32m+[m
[32m+[m[32m            # track_idから歌詞を取得[m
[32m+[m[32m            lyrics = get_lyrics(musixmatch_track_id)[m
[32m+[m
[32m+[m[32m            if "lyrics" in lyrics["message"]["body"]:[m
[32m+[m[32m                lyrics_body = lyrics["message"]["body"]["lyrics"]["lyrics_body"][m
[32m+[m[32m                clean_lyrics = lyrics_body.split("\n*******")[0][m
[32m+[m[32m                clean_lyrics = clean_lyrics.replace("\n", "<br>")[m
[32m+[m[32m            else:[m
[32m+[m[32m                clean_lyrics = "Lyrics not found."[m
[32m+[m
[32m+[m[32m            # 成功した場合、曲の詳細情報を返す[m
[32m+[m[32m            return {[m
[32m+[m[32m                "acousticness": features["acousticness"] * 100,[m
[32m+[m[32m                "danceability": features["danceability"] * 100,[m
[32m+[m[32m                "duration": song["duration_ms"] / 1000,[m
[32m+[m[32m                "energy": features["energy"] * 100,[m
[32m+[m[32m                "instrumentalness": features["instrumentalness"] * 100,[m
[32m+[m[32m                "key": features["key"],[m
[32m+[m[32m                "mode": features["mode"],[m
[32m+[m[32m                "name": song["name"],[m
[32m+[m[32m                "popularity": song["popularity"],[m
[32m+[m[32m                "tempo": features["tempo"],[m
[32m+[m[32m                "time_signature": features["time_signature"],[m
[32m+[m[32m                "valence": features["valence"] * 100,[m
[32m+[m[32m                "album_artwork_url": album_artwork_url,[m
[32m+[m[32m                "artists": artists,[m
[32m+[m[32m                "lyrics": clean_lyrics,[m
[32m+[m[32m            }[m
[32m+[m[32m        except Exception as e:  # タイムアウトやその他の例外をキャッチ[m
[32m+[m[32m            print(f"An error occurred: {e}. Retrying...")[m
[32m+[m[32m            retries += 1[m
[32m+[m[32m            time.sleep(delay)  # delay秒待ってからリトライ[m
[32m+[m
[32m+[m[32m    print("Max retries reached. Exiting.")[m
[32m+[m[32m    return None  # 最大リトライ回数を超えた場合はNoneを返す[m
 [m
 [m
 # 総リリース数をカウントする関数[m
[36m@@ -700,8 +766,13 @@[m [mdef help_song_details():[m
 @app.route("/song_details/<song_id>", methods=["GET"])[m
 def song_details(song_id):[m
     try:[m
[31m-        song = get_song_details(song_id)  # 既存の関数でSpotifyから曲情報を取得[m
[32m+[m[32m        song = get_song_details_with_retry(song_id)  # 既存の関数でSpotifyから曲情報を取得[m
 [m
[32m+[m[32m        if song is None:[m
[32m+[m[32m            return render_template([m
[32m+[m[32m                "error.html",[m
[32m+[m[32m                error="Failed to retrieve song details after multiple retries.",[m
[32m+[m[32m            )[m
         # 楽曲名とアーティスト名に基づいてAmazon検索URLを作成[m
         keywords = f"{song['name']} {song['artists'][0]['name']}"[m
         affiliate_code = "withmybgm-22"[m
