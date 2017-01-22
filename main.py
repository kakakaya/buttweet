#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# Author: kakakaya, Date: Sun Jan 22 20:54:27 2017
from pprint import pprint as p
import tweepy
import sys
import datetime
import logging
import click
import yaml
import requests
from bs4 import BeautifulSoup
from os import path, makedirs


CACHE_DIR = path.expanduser("~/.cache/buttweet")
WORK_FILE = "work.log"
CONFIG_FILE = "config.yaml"


logger = logging.getLogger(__name__)


def logging_config(verbose):
    loglevel = logging.CRITICAL
    if verbose == 1:
        loglevel = logging.WARN
    elif verbose == 2:
        loglevel = logging.INFO
    elif verbose >= 2:
        loglevel = logging.DEBUG

    logging.basicConfig(
        level=loglevel,
        format='%(levelname)6s:%(name)20s:%(lineno)3d:%(funcName)10s: %(message)s',
        datefmt="%Y-%m-%d %H:%M:%S", )


def get_config():
    config_path = "{}/{}".format(CACHE_DIR, CONFIG_FILE)
    if not path.exists(config_path):
        logger.info("{} not found, making default config file.".format(config_path))
        # デフォルトの設定を作成する
        if not path.exists(CACHE_DIR):
            makedirs(CACHE_DIR, exist_ok=True)  # make ~/.cache/, ~/.cache/buttweet/
        with open(config_path, 'w') as f:
            default_text = '''# User's ID, check https://greedbutt.com/player/<player-id>
player_id: 0
# if true, use AB+'s daily run data
plus: true
twitter:
    consumer_key: "myJRsoneDPkX6WRIOneVq8Xun"
    consumer_sec: "YpJU2DT8jxMzcMXalpB8uc9GVT81Wock3AOWpqo8MLZNJ7rBwR"
    access_key: ""
    acccess_sec: ""
    tweet_format = ""
'''
            f.write(default_text)
    with open(config_path, 'r') as f:
        data = yaml.load(f)
    return data


def set_config(config):
    config_path = "{}/{}".format(CACHE_DIR, CONFIG_FILE)
    with open(config_path, 'w') as f:
        f.write(yaml.dump(config))


def get_worklog():
    log_path = "{}/{}".format(CACHE_DIR, WORK_FILE)
    if path.exists(log_path):
        with open(log_path, 'r') as f:
            data = yaml.load(f)
    else:
        data = {}
    return data


def set_worklog(worklog):
    log_path = "{}/{}".format(CACHE_DIR, WORK_FILE)
    with open(log_path, 'w') as f:
        f.write(yaml.dump(worklog))



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
        playlog.append(daily)

    logger.info("fetched {} data".format(len(playlog)))
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
    api = tweepy.API(auth)
    
    logger.critical("tweeting but not implemented:"+str(playlog[0]))


def summary_tweet(playlog, days, auth, config):
    logger.warn("Not implemented")
    pass


@click.command()
@click.option("--player-id", type=int, help='"https://greedbutt.com/player/<player-id>"←の<player-id>部分。')
@click.option("--plus", is_flag=True, help="このオプションを指定するとAB+版のデータを取得するようになる。")
@click.option("--summary", type=int, help="指定した回数分の記録をまとめて投稿する。")
@click.option("--twitter-auth", is_flag=True, help="Twitterへの認証を行う。")
@click.option("--verbose", "-v", count=True, help="ログレベルを指定する。")
def main(player_id, plus, summary, twitter_auth, verbose):
    """greedbutt.comのデータを取得してツイートする
    各オプションは指定しなければ~/.cache/buttweet/config.yamlの値が優先される。
    """
    logging_config(verbose)

    config = get_config()
    logger.info(config)

    last_date = config.get("last_date")
    player_id = player_id or config.get("player_id")
    twitter = config.get("twitter")

    if twitter_auth:
        access_key, access_sec = twitter_authorize(twitter["consumer_key"], twitter["consumer_sec"])
        config["twitter"]["access_key"] = access_key
        config["twitter"]["access_sec"] = access_sec
        set_config(config)
        sys.exit(0)

    plus = plus or config.get("config")

    if not player_id:
        raise ValueError("Player ID not set, use config or argument(see --help)")

    playlog = get_playlog(player_id, plus)
    logger.info(playlog[0])

    auth = tweepy.OAuthHandler(twitter["consumer_key"], twitter["consumer_sec"])
    auth.set_access_token(twitter["access_key"], twitter["access_sec"])
    if summary:
        summary_tweet(playlog, summary, auth, config)
    else:
        daily_tweet(playlog, twitter, config)


if __name__ == "__main__":
    main()
