<!-- coding:utf-8, mode:gfm-mode -->
<!-- Author: kakakaya, Date: Mon Jan 23 00:11:59 2017 -->
# buttweet
GreedButt.com からのデータを取得してtwitterに投稿する。

# Install
```sh
% ./main.py --twitter-auth
```

# Configure
`$HOME/.config/buttweet/config.yaml` に設定ファイルがあるので、適宜変更する。
## daily_tweet_format / summary_tweet_format で使える変数
* 

# Usage
## 毎日の結果を投稿する
```sh
% ./main.py
```

## 数日分の結果をまとめて投稿する
(未実装)
* 一週間分の結果を投稿する
```sh
% ./main.py --summary-mode 7
```

# FAQ

# TODO
- [ ] サマリー投稿で画像を添付るする
