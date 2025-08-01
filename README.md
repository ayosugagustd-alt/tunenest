# 長岡亮介WORKS

長岡亮介に関連したSpotifyのプレイリストをもとに、
楽曲の情報を可視化・分析するWebアプリです。  
プレイリストは JSONファイルを編集するだけで差し替え可能です。

URL: https://www.tunenest.com/

## 主な特徴

- 楽曲のテンポ・モード（曲調）・Camelotキー・人気度を表示
- アーティストや楽曲を並べ替え・検索・試聴
- プレイリストは `config/playlists.json` で自由に更新可能
- Spotify APIの使用制限（クォータ）も解除申請済みで、安定稼働を実現

## 想定ユーザー

- プレイリストを分析・視覚化したい音楽ファンや番組制作者
- DJや研究者など、楽曲構造に関心がある方

## 使用技術

- Python（Flask）
- Spotify Web API
- Heroku（無料プラン）
- HTML/CSS（Jinja2テンプレート）
- その他: requests, threading, functools.lru_cache, logging

## 環境変数

Heroku上で以下の環境変数を設定します：
SPOTIFY_CLIENT_ID = your_client_id
SPOTIFY_CLIENT_SECRET = your_client_secret

## 作者について

viでWebアプリを自作。プログラミングは単なる趣味。
