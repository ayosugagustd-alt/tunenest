# 標準ライブラリ
import os
from flask import Flask, request, render_template
from flask_babel import Babel

# Flaskアプリケーションの初期化
app = Flask(__name__)
app.config['BABEL_DEFAULT_LOCALE'] = 'ja'
app.config['BABEL_SUPPORTED_LOCALES'] = ['ja', 'en']

# Babelの初期化時にロケールセレクタを設定
babel = Babel(app, locale_selector=lambda: request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES']))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/hello')
def hello():
    return _("Hello, World!")

if __name__ == '__main__':
    app.run(debug=True)

