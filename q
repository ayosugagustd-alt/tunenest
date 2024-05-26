[1mdiff --git a/templates/song_details.html b/templates/song_details.html[m
[1mindex 6f1ae1b..6738a72 100644[m
[1m--- a/templates/song_details.html[m
[1m+++ b/templates/song_details.html[m
[36m@@ -77,7 +77,9 @@[m
             <a href="{{ url_for('artist_details', artist_id=artist.id) }}" title="アーティストの詳細を見る">{{ artist.name }}</a>[m
           </li>{% endfor %}[m
         </ul>[m
[31m-        <p>アルバム名：{{ song.album_name }}</p>[m
[32m+[m[32m        <p>収録作品：[m
[32m+[m[32m            <a href="{{ url_for('album_details', artist_id=song.artists[0].id, album_id=song.album_id) }}" title="収録作品の詳細を見る">{{ song.album_name }}</a>[m
[32m+[m[32m        </p>[m
         <p>リリース日：{{ song.release_date }}</p>[m
         <p>テンポ：{{ song.tempo|float|round(1) }} BPM</p>[m
         <p>キー：{{ ["C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"][song.key] }}</p>[m
[1mdiff --git a/usviral50.py b/usviral50.py[m
[1mindex f85b508..0fb2672 100644[m
[1m--- a/usviral50.py[m
[1m+++ b/usviral50.py[m
[36m@@ -633,6 +633,9 @@[m [mdef get_song_details_with_retry(song_id, max_retries=3, delay=5):[m
             # アルバム名を取得[m
             album_name = song_details["album"]["name"][m
 [m
[32m+[m[32m            # アルバムidを取得[m
[32m+[m[32m            album_id = song_details["album"]["id"][m
[32m+[m
             # リリース日を取得[m
             release_date = song_details["album"]["release_date"][m
 [m
[36m@@ -668,7 +671,8 @@[m [mdef get_song_details_with_retry(song_id, max_retries=3, delay=5):[m
                 "album_artwork_url": album_artwork_url,[m
                 "artists": artists,[m
                 "camelot_key": camelot_key_value,  # キャメロットキー[m
[31m-                "album_name": album_name,  # 追加されたアルバム名[m
[32m+[m[32m                "album_name": album_name,  # 収録作品（アルバム名）[m
[32m+[m[32m                "album_id": album_id,  # 収録作品id （アルバムid）[m
                 "release_date": release_date,  # 追加されたリリース日[m
                 "liveness": audio_features["liveness"] * 100,[m
                 "speechiness": audio_features["speechiness"] * 100,[m
