#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# Author: kakakaya, Date: Sun Jan 22 20:54:27 2017
import time
import tweepy
import sys
import datetime
import logging
import click
import yaml
import requests
from bs4 import BeautifulSoup
from os import path, makedirs


CONFIG_DIR = path.expanduser("~/.config/buttweet")
CONFIG_FILE = "config.yaml"
WORK_DIR = path.expanduser("~/.cache/buttweet")
WORK_FILE = "work.log"

DEFAULT_CONFIG_YAML = '''# User's ID, check https://greedbutt.com/player/<player-id>
player_id: 0
# if true, use AB+'s daily run data
plus: true
# for formatting, see README.md
succeed_daily_tweet_format: "TBoI:R、{latest_play_date.year}年{latest_play_date.month}月{latest_play_date.day}日のデイリーランは{play_data[1]} Pointsで暫定{play_data[2]}位(上位{play_data[3]}%)でした。{play_time.hour}時間{play_time.minute}分{play_time.second}秒で終了。"
fail_daily_tweet_format: "TBoI:R、{latest_play_date.year}年{latest_play_date.month}月{latest_play_date.day}日のデイリーランは{play_data[1]} Pointsで暫定{play_data[2]}位(上位{play_data[3]}%)でした。"
succeed_summary_tweet_format: ""
fail_summary_tweet_format: ""
# dry_runをtrueにすると、投稿を行わずに標準出力を行う
dry_run: false
twitter:
    consumer_key: "myJRsoneDPkX6WRIOneVq8Xun"
    consumer_sec: "YpJU2DT8jxMzcMXalpB8uc9GVT81Wock3AOWpqo8MLZNJ7rBwR"
    access_key: ""
    access_sec: ""
'''
logger = logging.getLogger(__name__)


def logging_config(verbose):
    loglevel = logging.CRITICAL
    if verbose == 1:
        loglevel = logging.WARN
    elif verbose == 2:
        loglevel = logging.INFO
    elif verbose >= 3:
        loglevel = logging.DEBUG

    logging.basicConfig(
        level=loglevel,
        format='%(levelname)6s:%(name)10s:%(lineno)3d:%(funcName)15s: %(message)s',
        datefmt="%Y-%m-%d %H:%M:%S", )


def get_config():
    config_path = CONFIG_DIR + "/" + CONFIG_FILE
    config = {
        "player_id": 0,
        "plus": True,
        "daily_tweet_format": "",
        "summary_tweet_format": "",
        "twitter": {
            "consumer_key": "myJRsoneDPkX6WRIOneVq8Xun",
            "consumer_sec": "YpJU2DT8jxMzcMXalpB8uc9GVT81Wock3AOWpqo8MLZNJ7rBwR",
            "access_key": "",
            "access_sec": ""
        }
    }
    if not path.exists(config_path):
        logger.debug("{} not found, making default config file.".format(config_path))
        # デフォルトの設定を作成する
        if not path.exists(CONFIG_DIR):
            makedirs(CONFIG_DIR, exist_ok=True)  # make ~/.cache/, ~/.cache/buttweet/
        with open(config_path, 'w') as f:
            f.write(DEFAULT_CONFIG_YAML)
    with open(config_path, 'r') as f:
        data = yaml.load(f)
    config.update(data)
    return config


def set_config(config):
    config_path = CONFIG_DIR + "/" + CONFIG_FILE
    if not path.exists(CONFIG_DIR):
        makedirs(CONFIG_DIR, exist_ok=True)
    with open(config_path, 'w') as f:
        f.write(yaml.dump(config, allow_unicode=True))


def get_worklog():
    log_path = WORK_DIR + "/" + WORK_FILE
    if path.exists(log_path):
        with open(log_path, 'r') as f:
            data = yaml.load(f)
    else:
        data = {}
    return data


def set_worklog(worklog):
    log_path = WORK_DIR + "/" + WORK_FILE
    if not path.exists(WORK_DIR):
        makedirs(CONFIG_DIR, exsist_ok=True)
    with open(log_path, 'w') as f:
        f.write(yaml.dump(worklog, allow_unicode=True))


def get_playlog(player_id, plus):
    url = 'https://greedbutt.com{}/player/{}'.format(
        "/plus" if plus else "",
        player_id
    )
    # logger.info(url)
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    history = soup.select(".player-history")[0].find_all('tr')
    # p(history[0])
    playlog = []
    for i in history[1:]:
        cols = i.find_all('td')
        row = [col.text.strip() for col in cols]
        # [プレイ日, 得点, 得点ランク, 得点ランク(パーセント), プレイ時間, プレイ時間順位, プレイ時間順位(パーセント)]
        daily = [
            datetime.datetime.strptime(row[0], '%Y-%m-%d').date(),
            int(row[1].split()[0].replace(',', '')),
            int(row[2].split()[0].replace(',', '')),
            float(row[2].split()[1][1:-2]),  # (0.0%)のような感じなので[1:-2]でスライスする
        ]
        if len(row) == 5 and row[4] != "":
            # プレイ時間をパースしておく
            hour, minute, second = row[3].split(":")
            hour = int(hour) if hour else 0
            minute = int(minute) if minute else 0
            second = int(second) if second else 0
            playtime = datetime.timedelta(hours=hour, minutes=minute, seconds=second)

            daily += [
                playtime,
                int(row[4].split()[0].replace(',', '')),
                float(row[4].split()[1][1:-2])
            ]
        logger.debug(daily[0])
        playlog.append(daily)

    logger.info("Fetched {} data, latest: {}".format(len(playlog), playlog[0][0]))
    return playlog


def twitter_authorize(ck, cs):
    auth = tweepy.OAuthHandler(ck, cs)
    print("Authorize: " + auth.get_authorization_url())
    print("Input PIN:", end="")
    verifier = input()
    if len(verifier) != 7:
        raise ValueError("This PIN seems not valid: {}".format(verifier))
    auth.get_access_token(verifier)
    api = tweepy.API(auth)
    logger.info("Authorized: @{}".format(api.me().screen_name))
    return (auth.access_token, auth.access_token_secret)


def daily_tweet(playlog, auth, config):
    pl = playlog[0]             # 最新
    td = pl[4]
    worklog = get_worklog()
    last_date_str = worklog.get("last_daily_tweet_date")
    last_date = datetime.datetime.strptime(last_date_str, '%Y-%m-%d').date() if last_date_str else datetime.date.min
    latest_play_date = pl[0]
    if last_date and last_date == latest_play_date:
        # 最後に投稿された日付から更新されていない
        logger.info("Nothing new. 最終投稿:{last_date}、最新プレイ日:{latest_play_date}".format(
            last_date=last_date, latest_play_date=latest_play_date
        ))
        return None
    tmpl = config["succeed_daily_tweet_format"] if len(pl) == 7 else config["fail_daily_tweet_format"]
    play_time = datetime.time(td.seconds//3600, (td.seconds//60) % 60, td.seconds % 60)
    logger.debug(pl)
    tweet_text = tmpl.format(
        now=datetime.datetime.now(),
        last_date=last_date,
        latest_play_date=latest_play_date,
        play_data=pl,
        play_time=play_time
    )
    logger.debug(config["dry_run"])
    if not config["dry_run"]:
        api = tweepy.API(auth)
        result = api.update_status(tweet_text)
        worklog["last_daily_tweet_date"] = last_date.strftime("%Y-%m-%d")
    else:
        print(tweet_text)
        result = None

    if result:
        set_worklog(worklog)
    return result


def summary_tweet(playlog, days, auth, config):
    # pls = playlog[:days]        # days日分
    # worklog = get_worklog()
    logger.critical("Not implemented.")
    return None


@click.command()
@click.option("--player-id", type=int,
              help='"https://greedbutt.com/player/<player-id>"←の<player-id>部分。指定しなければ設定の値が優先される。')
@click.option("--plus", is_flag=True,
              help="このオプションを指定するとAB+版のデータを取得するようになる。指定しなければ設定の値が優先される。")
@click.option("--summary", type=int, help="指定した回数分の記録をまとめて投稿する。未実装。")
@click.option("--twitter-auth", is_flag=True, help="Twitterへの認証を行う。")
@click.option("--force", is_flag=True, help="前回実行時の結果に関わらず投稿する。--daemonとの併用は不可能。")
@click.option("--daemon", "-d", is_flag=True,
              help="ページを定期的に取得し、更新があったら投稿する。--summaryが指定されている場合、その日数分溜まったら投稿する。--forceとの併用は不可能(無限に投稿してしまうので)。")
@click.option("--dry-run", is_flag=True, help="このオプションを指定した場合、投稿をせずに標準出力への出力を行う")
@click.option("--verbose", "-v", count=True, help="ログレベルを指定する。")
def main(player_id, plus, summary, twitter_auth, force, daemon, dry_run, verbose):
    """greedbutt.comのデータを取得してツイートする
    """
    logging_config(verbose)
    if daemon and force:
        raise ValueError("Both daemon and force was specified; it will cause infinite tweeting.")

    config = get_config()       # 設定を読み込む
    logger.debug(config)

    # Twitter認証を行う
    twitter = config.get("twitter")

    if twitter_auth:
        access_key, access_sec = twitter_authorize(twitter["consumer_key"], twitter["consumer_sec"])
        config["twitter"]["access_key"] = access_key
        config["twitter"]["access_sec"] = access_sec
        # この流れの場合のみ、configを汚染(dry_run、plus、player_idの上書き)をしていないのでset_configが使える
        set_config(config)
        sys.exit(0)
    else:
        auth = tweepy.OAuthHandler(twitter["consumer_key"], twitter["consumer_sec"])
        auth.set_access_token(twitter["access_key"], twitter["access_sec"])


    player_id = player_id or config.get("player_id")
    if not player_id:
        raise ValueError("Player ID not set, use config or argument(see --help)")
    else:
        config["player_id"] = player_id  # 指定されていたら上書きしておく
    plus = plus or config.get("config")
    config["plus"] = plus       # 同上
    if dry_run:
        config["dry_run"] = True

    # GreedButt.comからの取得を行う
    playlog = get_playlog(player_id, plus)
    logger.debug(playlog)

    while True:
        # まず投稿できるかやってみる
        if summary:
            result = summary_tweet(playlog, summary, auth, config)
        else:
            result = daily_tweet(playlog, auth, config)
        if result:
            logger.info("https://twitter.com/{status.user.screen_name}/status/{status.id_str}".format(status=result))
        # そして、
        if daemon:              # デーモン動作なら
            sleep_time = 60*60*2 if summary else 60*20  # サマリーなら2時間に一度、さもなくば20分に一度
            time.sleep(sleep_time)
            playlog = get_playlog(player_id, plus)  # 確認する
        else:                   # さもなくば、
            break               # そのまま終了する


if __name__ == "__main__":
    main()
