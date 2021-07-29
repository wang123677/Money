# -*- coding: utf-8 -*-
from selenium import webdriver
import time
import json
import pymongo
import os
import random
import sys
import re
import subprocess
import shutil
from time import strftime, localtime
import datetime
from selenium.webdriver import ActionChains

with open(r'twitter_config.json', 'rb') as f:
    config = json.load(f)

COMMON_DATABASE = config["common_database"]
CHROME_DATA_PATH = config["chrome_path"]
CHROME_EXE_PATH = config["chrome_exe"]

def get_unuse_port():
    while True:
        port = random.randint(15000, 20000)

        pscmd = "netstat -ano | findstr {}".format(port)
        procs = os.popen(pscmd).read()

        if str(port) in procs:
            continue
        else:
            return port

class Twitter(object):
    def __init__(self, username=None, path=None):
        self.username = username

        # 数据库
        myclient = pymongo.MongoClient(COMMON_DATABASE)
        self.mydb = myclient["twitter_{}".format(self.username)]
        self.table_star_list = self.mydb["star_list"]
        self.table_detail = self.mydb["detail"]
        self.table_message = self.mydb["message"]
        self.table_following = self.mydb['following']
        self.table_auto_retweet = self.mydb['retweet']
        self.table_my_tweet = self.mydb['mytweet']
        self.table_my_retweet_task = self.mydb["retweet_task"]
        self.table_my_retweet_task2 = self.mydb["retweet_task2"]
        self.table_check_retweet = self.mydb["check_retweet"]
        self.table_daily_task = self.mydb["daily_task"]
        self.table_auto_retweet_block = self.mydb["retweet_block"]

        self.chrome_path = CHROME_DATA_PATH + '\\' + username + '_daily'
        print(self.chrome_path)
        port = get_unuse_port()
        chrome_cmd = r'"{}" --remote-debugging-port={} --user-data-dir={}'.format(CHROME_EXE_PATH, str(port), self.chrome_path)

        try:
            self.proc = subprocess.Popen(chrome_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL)
            self.chrome_pid = self.proc.pid
        except Exception as e:
            print("start chrome error")
            print(e)
            pass

        option = webdriver.ChromeOptions()
        option.add_argument('--disable-gpu')
        option.add_argument('enable-automation')
        # coption.add_argument('--headless')
        option.add_experimental_option("debuggerAddress", "127.0.0.1:{}".format(port))
        self.driver = webdriver.Chrome(options=option)

    def check_access(self):
        if "/account/access" in self.driver.current_url:
            print("需要验证access!\nExit program: {}".format(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
            sys.exit()

    def retweet(self, tweet_url, comment=None, is_force=False, is_untweet=False):

        # is_force为True时，如果是已经推过的推文，则取消重推
        # retweet
        tweet_url = tweet_url.split("?")[0]
        try:
            self.driver.get(tweet_url)
            time.sleep(8)

            #把信息存起来
            try:
                # 获取评论数、转推数和like数

                try:
                    retweets = int(self.driver.find_elements_by_xpath('//div[@class="css-1dbjc4n r-mxfbl1 r-1efd50x r-5kkj8d r-13awgt0 r-18u37iz r-tzz3ar r-s1qlax r-1yzf0co"]//span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')[0].text.replace(",", "").replace("K", "000"))
                    likes = int(self.driver.find_elements_by_xpath('//div[@class="css-1dbjc4n r-mxfbl1 r-1efd50x r-5kkj8d r-13awgt0 r-18u37iz r-tzz3ar r-s1qlax r-1yzf0co"]//span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')[-2].text.replace(",", "").replace("K", "000"))

                except Exception as e:
                    pass

                # 判断是jpg类型还是video类型
                tweet_type = ''
                tweet_ele = self.driver.find_elements_by_xpath('//div[@data-testid="videoPlayer"]')
                if len(tweet_ele) != 0:
                    tweet_type = "video"

                else:
                    tweet_type = "jpg"

                # 获取推文内容
                tweet_content = ''
                content_eles = self.driver.find_elements_by_xpath('//div[@class="css-901oao r-18jsvk2 r-1qd0xha r-1blvdjr r-16dba41 r-vrz42v r-bcqeeo r-bnwqim r-qvutc0"]/span')

                for con in content_eles:
                    if con != '':
                        tweet_content += con.text

                datestamp = time.strftime("%Y-%m-%d", time.localtime())
                myclient = pymongo.MongoClient(COMMON_DATABASE)
                mydb = myclient["pop_retweet"]
                mycol = mydb["detail"]

                if mycol.find_one({"detail":tweet_url}) == None and tweet_type == "video":
                    data = {"detail":tweet_url,
                            "likes":likes,
                            "retweets":retweets,
                            "percent":likes/retweets,
                            "is_download":False,
                            "content": tweet_content,
                            "date":datestamp
                            }
                    mycol.insert_one(data)
            except Exception  as e:
                print("存取推文信息失败，忽略")
                pass

            # 如果是取消重推
            if is_untweet:
                if len(self.driver.find_elements_by_xpath('//div[@data-testid="unretweet"]')) != 0:
                    self.driver.find_element_by_xpath('//div[@data-testid="unretweet"]').click()
                    time.sleep(2)
                    self.driver.find_element_by_xpath('//div[@data-testid="unretweetConfirm"]').click()
                    time.sleep(5)
                return

            # 如果已推，撤了重推
            if len(self.driver.find_elements_by_xpath('//div[@data-testid="unretweet"]')) != 0 and is_force:
                self.driver.find_element_by_xpath('//div[@data-testid="unretweet"]').click()
                time.sleep(2)
                self.driver.find_element_by_xpath('//div[@data-testid="unretweetConfirm"]').click()
                time.sleep(5)

            self.driver.find_element_by_xpath('//div[@data-testid="retweet"]').click()
            time.sleep(2)

            if comment == None:

                # 不带评论转推
                time.sleep(1)
                self.driver.find_element_by_xpath('//div[@data-testid="retweetConfirm"]').click()
                time.sleep(3)

            else:
                # 带评论转推
                self.driver.find_element_by_xpath('//a[@role="menuitem"]').click()
                time.sleep(2)
                self.driver.find_element_by_xpath('//div[@data-testid="tweetTextarea_0"]').send_keys("ttt")  # 改成评论内容
                time.sleep(1)
                self.driver.find_element_by_xpath('//div[@data-testid="retweetConfirm"]').click()
                time.sleep(3)
        except Exception as e:
            pass

    def retweet_all_my_tweet(self):
        all_retweet = []

        myclient2 = pymongo.MongoClient(COMMON_DATABASE)
        mydb = myclient2["retweet_old_tweet"]
        mycol1 = mydb["mustretweet"]
        mycol2 = mydb["randomretweet"]

        for t in list(mycol1.find({})):
            all_retweet.append(t)

        count = 10
        t_list = list(mycol2.find({}))

        for t in t_list:
            if count ==0:
                break
            all_retweet.append(t)

        random.shuffle(all_retweet)

        for t in all_retweet:
            detail = t['detail']
            self.retweet(detail, comment=None, is_force=True, is_untweet=False)
            time.sleep(2)

    def do_task(self, item, datestamp, mode):

        while len(self.driver.window_handles) != 1:
            for h in self.driver.window_handles:
                self.driver.switch_to.window(h)
                if "twitter" not in self.driver.current_url:
                    self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
        try:
            # black list
            f_black = open("blacklist.txt", "r")
            data_black = f_black.readlines()
            f_black.close()
            black_list = []
            for i in data_black:
                black_list.append(i.lower().strip())
                if "username" in item.keys() and item["username"].lower() in black_list:
                    #print("黑名单:{}".format(item["username"]))
                    self.table_auto_retweet.delete_one({"dialog": item["dialog"]})
                    self.table_auto_retweet_block.insert_one({"dialog": item["dialog"]})
                    return

            if item["last_task_time"] == datestamp and item["last_send_time"] == datestamp:
                return

            if "block" in item.keys() and item["block"]:
                return

            dialog = item['dialog']

            self.driver.get(dialog)
            self.check_access()
            time.sleep(15)

            #如果有"suspicious content"，点击一下
            if "Message hidden due to suspicious content" in self.driver.page_source:
                for i in self.driver.find_elements_by_xpath('//div[@role="button"]//span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')[-10:]:
                    if i.text == "View":
                        i.click()
                        time.sleep(3)
                        self.driver.find_elements_by_xpath('//div[@class="css-18t94o4 css-1dbjc4n r-1niwhzg r-p1n3y5 r-sdzlij r-1phboty r-rs99b7 r-1b7u577 r-ero68b r-vkv6oe r-1ny4l3l r-1fneopy r-o7ynqc r-6416eg r-lrvibr"]//span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')[0].click()
                        time.sleep(3)

            if "You can no longer send messages to this person" in self.driver.page_source:
                self.table_auto_retweet.delete_one({"dialog":dialog})
                self.table_auto_retweet_block.insert_one({"dialog":dialog})

            if len(self.driver.find_elements_by_xpath('//div[@data-testid="dmComposerTextInput"]')) == 0:
                # self.table_auto_retweet.update_one({"dialog": dialog}, {"$set": {"block": True}})
                return

            count = 30
            while len(self.driver.find_elements_by_xpath('//div[@data-testid="messageEntry"]')) == 0 and count > 0:
                print("wait")
                time.sleep(1)
                count -= 1

            # 如果用户名字没获取，则获取一下
            try:
                username = self.driver.find_element_by_xpath(
                    '//div[@class="css-901oao css-bfa6kz r-14j79pv r-1qd0xha r-n6v787 r-16dba41 r-1cwl3u0 r-bcqeeo r-qvutc0"]/span').text.replace(
                    '@', '')
                self.table_auto_retweet.update_one({"dialog": dialog}, {"$set": {"username": username}})
            except Exception as e:
                print("get user name error")
                pass

            # 我来发送任务
            if item["last_send_time"] != datestamp:
                #新互推用户的词
                if item["last_task"] == "":
                    content_list = [
                        "亲,诚信互推",
                        "互推亲 "
                    ]
                else:
                    content_list = [
                        #"昨日已推。今日互推，推完请回复我会检查，谢谢！ ",
                        #"昨天的已推亲，可以去主页检查。推完请回复，会去主页检查，谢谢！",
                        #"昨日已推,今日互推，麻烦了，谢谢！",
                        "111。今日互推 ",
                        "好了。互推亲。推过请撤回重推一下，",
                        #"昨天的推了.今天互推 请挂24小时 会检查,谢谢！"
                        "每日互推, 转完回1 方便核对 诚信互推"
                        "今日互推，推完请回复我会检查，谢谢！ ",
                        "互推，可以去主页检查。推完请回复，会去主页检查，谢谢！",
                        # "今日互推，麻烦了，谢谢！",
                        # "今日互推 ",
                        # "互推亲。推过请撤回重推一下，",
                        # "1今天互推 请挂24小时 会检查,谢谢！",
                        # "每日互推, 转完回1 方便核对 诚信互推"
                        # "你好，今日互推，麻烦了！ 转完回1 方便核对 诚信互推 "
                        #"抱歉，VPN除了问题，可能没收到信息或者漏推了，请重发一遍，谢谢。 5.12互"
                    ]
                if self.username == "xiaokele520":
                    content_send = "亲，互推. 你的发来，看到马上推哦 " + content
                else:
                    content_send = content_list[random.randint(0, len(content_list) - 1)] + content
                # 发送要别人转推的内容
                try:
                    self.check_access()
                    self.driver.find_elements_by_xpath('//div[@data-testid="dmComposerTextInput"]')[0].send_keys(
                        content_send)
                    time.sleep(5)
                    self.driver.find_elements_by_xpath('//div[@data-testid="dmComposerSendButton"]')[0].click()
                    time.sleep(3)
                    # ActionChains(self.driver).move_to_element_with_offset(self.driver.find_elements_by_xpath('//div[@class="css-1dbjc4n r-obd0qt r-18u37iz r-1uu6nss r-13qz1uu"]')[0], 578, 30).click().perform()
                    if "try again" in self.driver.page_source.lower():
                        print("try again")
                        time.sleep(500000)

                except Exception as e:
                    print("send task error")
                    print(e)

                # 拉到最下面
                count_min_tmp = 20
                while count_min_tmp > 0:
                    ActionChains(self.driver).move_to_element_with_offset(
                        self.driver.find_elements_by_xpath('//div[@data-testid="dmComposerSendButton"]')[0], 30,
                        -30).click().perform()
                    count_min_tmp -= 1
                    time.sleep(0.1)

                for send_items in list(self.driver.find_elements_by_xpath('//div[@data-testid="messageEntry"]'))[-4:][
                                  ::-1]:
                    # send_items = list(self.driver.find_elements_by_xpath('//div[@data-testid="messageEntry"]'))[-1]

                    time_item = send_items.find_elements_by_xpath('../div[@class="css-1dbjc4n r-173mn98 r-17s6mgv r-1bymd8e r-1udh08x r-1nwbi2h"]//div[@class="css-1dbjc4n r-1loqt21"]/div')

                    if len(time_item) != 0:
                        time_tmp = time_item[0].text
                        if len(time_tmp.split(' ')) != 3 or len(time_tmp.split(',')) <= 1:
                            self.table_auto_retweet.update_one({"dialog": dialog},
                                                               {"$set": {"last_send_time": datestamp,
                                                                         "wait_check": False}})
                            print("分配任务成功")
                            # time.sleep(2 * 60)

                            min = 1.5
                            count_min_tmp = min * 60 / 10
                            while count_min_tmp > 0:
                                ActionChains(self.driver).move_to_element_with_offset(
                                    self.driver.find_elements_by_xpath(
                                        '//div[@data-testid="dmComposerSendButton"]')[0], 30, -30).click().perform()
                                time.sleep(10)
                                count_min_tmp -= 1
                            break
                    else:
                        print("分配失败")
            if item["last_task_time"] == datestamp:
                print("已经完成对方任务")
                return

            # 如果没分配过任务，则不接受任务
            if self.table_auto_retweet.find_one({"dialog": dialog})["last_send_time"] != datestamp:
                return

            # 获取推文,存成字典：时间、内容，待补充
            his_contents = []
            time_tmp = ''
            msg_mark = False  # 消息mark 标记这条消息属于谁

            count = 15
            last_msg_item = self.driver.find_elements_by_xpath('//div[@data-testid="messageEntry"]')
            while count > 0:
                # ActionChains(self.driver).move_to_element_with_offset(self.driver.find_elements_by_xpath('//div[@class="css-1dbjc4n r-obd0qt r-18u37iz r-1uu6nss r-13qz1uu"]')[0], 590, -30).click().perform()
                ActionChains(self.driver).move_to_element_with_offset(
                    self.driver.find_elements_by_xpath('//div[@data-testid="dmComposerSendButton"]')[0], 30,
                    -30).click().perform()
                time.sleep(0.3)
                if last_msg_item == self.driver.find_elements_by_xpath('//div[@data-testid="messageEntry"]'):
                    count -= 1
                else:
                    last_msg_item = self.driver.find_elements_by_xpath('//div[@data-testid="messageEntry"]')
                    count = 15

            # 点开open tweet
            try:
                if "watch" not in self.driver.find_elements_by_xpath(
                        '//span[@class="css-901oao css-16my406 css-bfa6kz r-poiln3 r-bcqeeo r-qvutc0"]/span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')[
                    -1].text.lower():
                    self.driver.find_elements_by_xpath(
                        '//span[@class="css-901oao css-16my406 css-bfa6kz r-poiln3 r-bcqeeo r-qvutc0"]/span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')[
                        -1].click()
            except Exception as e:
                pass
            dialog_items = list(self.driver.find_elements_by_xpath('//div[@data-testid="messageEntry"]'))
            msg_mark = False
            for dialog_item in dialog_items[::-1]:
                if len(his_contents) != 0:
                    break
                if len(self.driver.find_elements_by_xpath(
                        '//div[@role="button"]/div[@dir="auto"]/span[@class="css-901oao css-16my406 css-bfa6kz r-poiln3 r-bcqeeo r-qvutc0"]/span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')) != 0:
                    try:
                        if self.driver.find_elements_by_xpath(
                                '//div[@role="button"]/div[@dir="auto"]/span[@class="css-901oao css-16my406 css-bfa6kz r-poiln3 r-bcqeeo r-qvutc0"]/span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')[
                            -1].text == "View":
                            self.driver.find_elements_by_xpath(
                                '//div[@role="button"]/div[@dir="auto"]/span[@class="css-901oao css-16my406 css-bfa6kz r-poiln3 r-bcqeeo r-qvutc0"]/span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')[
                                -1].click()
                            time.sleep(3)
                            self.driver.find_elements_by_xpath(
                                '//div[@role="button"]/div[@dir="auto"]/span[@class="css-901oao css-16my406 css-bfa6kz r-poiln3 r-bcqeeo r-qvutc0"]/span[@class="css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0"]')[
                                -2].click()
                    except Exception as e:
                        print("message spam failed")
                        sys.exit()


                # 判断是我的，还是对方的(True)
                #如果是我的，continue
                try:
                    if len(dialog_item.find_elements_by_xpath('../div[@class="css-1dbjc4n r-173mn98 r-17s6mgv r-1bymd8e r-1udh08x r-1nwbi2h"]//div[@class="css-1dbjc4n r-1loqt21"]/div')) != 0 :
                        msg_mark = False
                        continue
                    #对方的
                    elif not msg_mark and len(dialog_item.find_elements_by_xpath('../div[@class="css-1dbjc4n r-1bymd8e r-1udh08x r-1nwbi2h"]//div[@class="css-1dbjc4n r-kp55a4"]/div')) !=0 :
                        msg_mark = True

                except Exception as e:
                    print("test")

                time_item = dialog_item.find_elements_by_xpath('../div[@class="css-1dbjc4n r-1bymd8e r-1udh08x r-1nwbi2h"]//div[@class="css-1dbjc4n r-kp55a4"]/div')
                if len(time_item) != 0:
                    time_tmp = time_item[0].text

                # span_item = dialog_item.find_elements_by_xpath('..//div[@class="css-901oao r-hkyrab r-1qd0xha r-a023e6 r-16dba41 r-ad9z0x r-bcqeeo r-1udh08x r-bnwqim r-fdjqy7 r-qvutc0"]//a')
                span_items = dialog_item.find_elements_by_xpath('.//a')
                if len(span_items) != 0:
                    for span_item in span_items:
                        url_tmp = span_item.get_attribute('href')
                        # print(url_tmp)
                        if "twitter.com" not in url_tmp:
                            continue
                        if "https" in url_tmp and len(url_tmp.split('/')) < 5:
                            continue
                        # 如果是昨天的，则掠过
                        if len(time_tmp.split(' ')) == 3 or (len(time_tmp.split(',')) > 1 and mode != 2):
                            datestamp = time.strftime("%Y-%m-%d", time.localtime())
                            yesterday_timestamp = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                            if item["last_task_time"] == datestamp or item["last_task_time"] == yesterday_timestamp:
                                continue
                        msg_item = {
                            "date": time_tmp,
                            "task": url_tmp
                        }
                        if msg_mark:
                            his_contents.append(msg_item)
                            break
                if len(his_contents) >= 1:
                    break
                # 另一种  pic
                if len(dialog_item.find_elements_by_xpath('.//span[@aria-hidden="true"]')) != 0 and len(
                        dialog_item.find_elements_by_xpath('.//span[@aria-hidden="true"]')[0].find_elements_by_xpath(
                                '..')) != 0:
                    if len(time_tmp.split(' ')) == 3 or (len(time_tmp.split(',')) > 1 and mode != 2):
                        datestamp = time.strftime("%Y-%m-%d", time.localtime())
                        yesterday_timestamp = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                        if item["last_task_time"] == datestamp or item["last_task_time"] == yesterday_timestamp:
                            continue

                    hiden_eles = dialog_item.find_elements_by_xpath('.//span[@aria-hidden="true"]')
                    for h in hiden_eles:
                        url_tmp = h.find_elements_by_xpath('..')[0].text
                        if "twitter.com" not in url_tmp:
                            continue

                        # url_tmp = dialog_item.find_elements_by_xpath('.//span[@aria-hidden="true"]')[0].find_elements_by_xpath('..')[0].text
                        msg_item = {
                            "date": time_tmp,
                            "task": url_tmp
                        }
                        if msg_mark:
                            his_contents.append(msg_item)
                if len(his_contents) >= 1:
                    break

                # 另一种
                # elif len(his_contents) == 0:
                span_items = dialog_item.find_elements_by_xpath(
                    './/span[@class="r-1qd0xha r-ad9z0x r-bcqeeo r-qvutc0 css-901oao css-16my406"]')
                if len(span_items) != 0 and len(his_contents) != 0:
                    for span_item in span_items:
                        url_tmp = span_item.get_attribute('title')
                        # print(url_tmp)
                        if "twitter.com" not in url_tmp:
                            continue
                        # 如果是昨天的，则掠过
                        if len(time_tmp.split(' ')) == 3 or (len(time_tmp.split(',')) > 1 and mode != 2):
                            datestamp = time.strftime("%Y-%m-%d", time.localtime())
                            yesterday_timestamp = (datetime.date.today() - datetime.timedelta(days=1)).strftime(
                                "%Y-%m-%d")
                            if item["last_task_time"] == datestamp or item["last_task_time"] == yesterday_timestamp:
                                continue
                        msg_item = {
                            "date": time_tmp,
                            "task": url_tmp
                        }
                        if msg_mark:
                            his_contents.append(msg_item)
                            break
                if len(his_contents) >= 1:
                    break

                # 还有一种
                if len(his_contents) == 0 and len(time_tmp.split(' ')) != 3 and (
                        len(time_tmp.split(',')) <= 1 or mode != 2):

                    span_items = dialog_item.find_elements_by_xpath('.//div[@role="link"]')
                    if len(span_items) != 0:
                        dialog_item.find_elements_by_xpath('.//div[@class="css-1dbjc4n r-6gpygo r-1fz3rvf"]')[0].click()
                        time.sleep(5)
                        url_tmp = self.driver.current_url
                        # print(url_tmp)
                        if "twitter.com" not in url_tmp:
                            continue
                        # 如果是昨天的，则掠过
                        if len(time_tmp.split(' ')) == 3 or (len(time_tmp.split(',')) > 1 and mode != 2):
                            datestamp = time.strftime("%Y-%m-%d", time.localtime())
                            yesterday_timestamp = (datetime.date.today() - datetime.timedelta(days=1)).strftime(
                                "%Y-%m-%d")
                            if item["last_task_time"] == datestamp or item["last_task_time"] == yesterday_timestamp:
                                continue
                        msg_item = {
                            "date": time_tmp,
                            "task": url_tmp
                        }
                        if msg_mark:
                            his_contents.append(msg_item)
                            self.driver.get(dialog)
                            time.sleep(10)
                            while len(self.driver.find_elements_by_xpath('//div[@data-testid="messageEntry"]')) == 0:
                                print("wait")
                                time.sleep(1)
                            break

            # 先看他的列表，判断是否今天，如果是，然后判断如果是已经转了，略过，如果没转，则转推，并找到他上一条转推，取消
            for t in his_contents:
                # 转推

                print("执行任务...")

                # 先把上一条untweet
                if item["last_task"] != "":
                    # 数据库里判断一下，如果是今天推的，就不要untweet
                    if len(list(self.table_auto_retweet.find(
                            {"last_task": item["last_task"], "last_task_time": datestamp}))) != 0:
                        continue
                    self.retweet(item["last_task"], None, True, True)
                    self.driver.get(dialog)
                    self.check_access()
                    time.sleep(5)
                    while len(self.driver.find_elements_by_xpath('//div[@data-testid="messageEntry"]')) == 0:
                        print("wait")
                        time.sleep(1)

                # 发送1告知别人已完成
                self.check_access()
                # reply_final = '{}。自动互推软件请联系作者@UtopiaCD'.format(reply)
                reply_final = '{}'.format(reply)
                self.driver.find_elements_by_xpath('//div[@data-testid="dmComposerTextInput"]')[0].send_keys(
                    reply_final + '\n')
                time.sleep(5)
                self.driver.find_elements_by_xpath('//div[@data-testid="dmComposerSendButton"]')[0].click()
                time.sleep(5)
                # ActionChains(self.driver).move_to_element_with_offset(self.driver.find_elements_by_xpath('//div[@class="css-1dbjc4n r-obd0qt r-18u37iz r-1uu6nss r-13qz1uu"]')[0], 578, 30).click().perform()

                # 发推
                self.retweet(t["task"], None, True, False)

                # 标记
                if mode == 2:
                    i_tmp = {"last_task_time": datestamp}

                else:
                    i_tmp = {
                        "last_task_time": datestamp,
                        "last_task": t["task"]
                    }
                self.table_auto_retweet.update_one({"dialog": dialog}, {"$set": i_tmp})
                time.sleep(2)
                break

        except Exception as e:
            print("kkkkk")
            print(e)
            pass

    # 自动和人互推
    def auto_retweet(self, content, reply):
        # 临时功能，将已经不互推的人重新开始护腿
        # f = open("restart_retweet.txt", "r")
        # data = f.readlines()
        # f.close()

        # for i in data :
        #     i = i.strip()
        #     print(i)
        #     if self.table_auto_retweet.find_one({"dialog": i}) != None:
        #         self.table_auto_retweet.update_one({"dialog": i}, {"$set": {"last_task_time": "2021-02-21", "block":False}})

        datestamp = time.strftime("%Y-%m-%d", time.localtime())
        yesterday_timestamp = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            f = open("retweet_{}.txt".format(self.username), "r")
            data = f.readlines()
            f.close()

            for d in data:
                if self.table_auto_retweet.find_one({"dialog": d.strip()}) == None and self.table_auto_retweet_block.find_one({"dialog": d.strip()}) == None:
                    item = {
                        "dialog": d.strip(),
                        "last_task_time": yesterday_timestamp,
                        "last_send_time": "",
                        "last_task": "",
                        "username": "",
                        "ad": True,
                        "follower": "",
                        "block": False,
                        "start_from": datestamp
                    }
                    self.table_auto_retweet.insert_one(item)
        except Exception as e:
            pass

        # 先把未完成的任务完成了
        to_do_task = list(self.table_my_retweet_task.find({}))
        print("上次未完成任务数:{}".format(len(to_do_task)))

        for t in to_do_task:
            dialog_tmp = t["dialog"]
            task_tmp = self.table_auto_retweet.find_one({"dialog": dialog_tmp})
            self.do_task(task_tmp, datestamp, 0)
            self.table_my_retweet_task.delete_one({"dialog": dialog_tmp})
            # sys.exit()

        mode = 0
        if mode == 1:
            item_list = []
            f = open("retweet_spec.txt", "r")
            data = f.readlines()
            f.close()
            for i in data:
                result = self.table_auto_retweet.find_one({"dialog": i.strip()})
                if result != None:
                    item_list.append(result)

        else:
            item_list = list(self.table_auto_retweet.find({}))
            # item_list = list(self.table_auto_retweet.find({"country":"CH"}))
            #item_list = list(self.table_auto_retweet.find({"dialog":"https://twitter.com/messages/1209303423121674240-1298472543255326722"}))

        # 要改成查找未完成的
        for item in item_list:

            try:
                flag = False
                try:
                    if "last_task_time" not in item.keys() or item["last_task_time"] == '':
                        self.table_auto_retweet.update_one({"dialog": item["dialog"]},
                                                           {"$set": {"last_task_time": (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")}})
                        item["last_task_time"] = "2020-01-01"

                    if (datetime.datetime.strptime(datestamp, "%Y-%m-%d") - datetime.datetime.strptime(
                            item["last_task_time"], "%Y-%m-%d")).days < 4:
                        self.table_auto_retweet.update_one({"dialog": item["dialog"]}, {"$set": {"block": False}})
                        item["block"] = False
                        flag = True
                except Exception as e:
                    pass

                if "block" in item.keys() and item["block"] and not flag:
                    continue

                elif not flag:
                    try:
                        if "last_task_time" not in item.keys() or item["last_task_time"] == None or item[
                            "last_task_time"] == '':
                            if "start_from" not in item.keys() or item["start_from"] == '':

                                if (datetime.datetime.strptime(datestamp, "%Y-%m-%d") - datetime.datetime.strptime(
                                        item["last_send_time"], "%Y-%m-%d")).days > 3:
                                    self.table_auto_retweet.update_one({"dialog": item["dialog"]},
                                                                       {"$set": {"block": True}})
                                    item["block"] = True

                            elif (datetime.datetime.strptime(datestamp, "%Y-%m-%d") - datetime.datetime.strptime(
                                    item["start_from"], "%Y-%m-%d")).days > 3:
                                self.table_auto_retweet.update_one({"dialog": item["dialog"]},
                                                                   {"$set": {"block": True}})
                                item["block"] = True

                        elif "start_from" not in item.keys() or item["start_from"] == '':
                            if (datetime.datetime.strptime(datestamp, "%Y-%m-%d") - datetime.datetime.strptime(
                                    item["last_task_time"], "%Y-%m-%d")).days > 3:
                                self.table_auto_retweet.update_one({"dialog": item["dialog"]},
                                                                   {"$set": {"block": True}})
                                item["block"] = True

                        else:
                            last_task_time_tmp = item["last_task_time"]
                            start_from_tmp = item["start_from"]
                            d1 = datetime.datetime.strptime(start_from_tmp, "%Y-%m-%d")
                            d2 = datetime.datetime.strptime(last_task_time_tmp, "%Y-%m-%d")
                            d3 = datetime.datetime.strptime(datestamp, "%Y-%m-%d")
                            if (d3 - d2).days > 3:
                                self.table_auto_retweet.update_one({"dialog": item["dialog"]},
                                                                   {"$set": {"block": True}})
                                item["block"] = True

                    except Exception as e:
                        print(e)

                if item["last_send_time"] == datestamp and mode == 0:
                    continue

                print("任务总数:{}, 当前任务:{}, {}".format(len(item_list), item_list.index(item), item["dialog"]))
                self.do_task(item, datestamp, mode)
                # if self.username.lower() == "forfun776" or self.username.lower() == "chunshuitanggg": # or self.username.lower() == "jianhuangshi0":
                # time.sleep(2*60)
            except Exception as e:
                print(e)

        # -----------------------------------------------------------------------------------------------------------------------
        self.driver.get("https://twitter.com/messages")
        wait_flag = True
        while True:
            flag = True
            while flag:
                conversation_items = self.driver.find_elements_by_xpath('//div[@data-testid="conversation"]')
                for con_item in conversation_items:
                    # 判断是已读还是未读
                    if con_item.get_attribute(
                            "class") == "css-1dbjc4n r-14lw9ot r-j7yic r-rull8r r-qklmqi r-1loqt21 r-1ny4l3l r-1j3t67a r-9qu9m4 r-o7ynqc r-6416eg r-13qz1uu":
                        # 已读
                        continue

                    else:
                        flag = False
                        break

                time.sleep(5)

            # 这个大循环，是要读取全部的未读信息
            flag = True
            while flag:
                try:
                    task_list = []

                    self.driver.get("https://twitter.com/messages")
                    # 第一遍先遍历，把所有未读的都读一遍

                    if self.driver.current_url != "https://twitter.com/messages" and self.driver.current_url != "https://twitter.com/messages/":
                        self.driver.get("https://twitter.com/messages")

                    while "Search for people and groups" not in self.driver.page_source:
                        time.sleep(1)
                        if "try again" in self.driver.page_source:
                            self.driver.get("https://twitter.com/messages")

                    count = 500
                    while count > 0:
                        try:
                            conversation_items = self.driver.find_elements_by_xpath(
                                '//div[@data-testid="conversation"]')

                            flag_second = False
                            con_item_list = []
                            for con_item in conversation_items:
                                # 判断是已读还是未读
                                if con_item.get_attribute("class") == "css-1dbjc4n r-14lw9ot r-j5o65s r-rull8r r-qklmqi r-1loqt21 r-1ny4l3l r-ymttw5 r-1yzf0co r-o7ynqc r-6416eg r-13qz1uu":
                                    # 已读
                                    continue

                                # 未读
                                #elif con_item.get_attribute("class") == "css-1dbjc4n r-zv2cs0 r-j5o65s r-rull8r r-qklmqi r-1loqt21 r-1ny4l3l r-ymttw5 r-1yzf0co r-o7ynqc r-6416eg r-13qz1uu":
                                else:
                                    try:
                                        if con_item in con_item_list:
                                            continue
                                        con_item.click()
                                        con_item_list.append(con_item)
                                        time.sleep(2)
                                        dialog_tmp = self.driver.current_url
                                        item_tmp = self.table_auto_retweet.find_one({"dialog": dialog_tmp})

                                        if item_tmp["block"]:
                                            self.table_auto_retweet.update_one({"dialog": dialog_tmp}, {
                                                "$set": {"last_task_time": (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d"), "block": False}})

                                        if item_tmp["last_task_time"] == datestamp and item_tmp[
                                            "last_send_time"] == datestamp:
                                            flag_second = True
                                            continue

                                        # self.do_task(item_tmp, datestamp, mode)
                                        if item_tmp not in task_list:
                                            task_list.append(item_tmp)
                                            self.table_my_retweet_task.insert_one({"dialog": item_tmp["dialog"]})
                                        time.sleep(1)
                                        # flag_second = True
                                        # flag = True
                                        # break

                                    except Exception as e:
                                        print("fffffffff")
                                        print(e)
                                        # f = open("talk.txt", "a")
                                        # f.write("\n{}:未加入互推列表:{}".format(self.username, dialog_tmp))
                                        # f.close()
                                        # print("{}:未加入互推列表:{}".format(self.username, dialog_tmp))
                            # if flag_second:
                            #     break
                            # 下滑
                            if len(self.driver.find_elements_by_xpath('//div[@data-testid="conversation"]//time')[
                                       0].text.split(' ')) != 1:
                                flag = False
                                break
                            ActionChains(self.driver).move_to_element_with_offset(
                                self.driver.find_element_by_xpath('//a[@data-testid="NewDM_Button"]'), 40,
                                self.driver.get_window_size()["height"] - 147).click().perform()
                            time.sleep(1.5)
                            count -= 1
                        except Exception as e:
                            print("eeeeeeeeeeeee")
                            print(e)
                            continue

                    for task_tmp in task_list:
                        print("总共{}条，正在完成第{}条:{}".format(len(task_list), task_list.index(task_tmp), task_tmp["dialog"]))
                        self.do_task(task_tmp, datestamp, mode)
                        self.table_auto_retweet.update_one({"dialog": task_tmp["dialog"]},
                                                           {"$set": {"wait_check": True}})
                        self.table_my_retweet_task.delete_one({"dialog": task_tmp["dialog"]})

                    if len(task_list) == 0:
                        flag = False

                    else:
                        flag = True

                except Exception as e:
                    print("ddddddddd")
                    print(e)
                    pass
            self.driver.get("https://twitter.com/messages")
            wait = ''

            if wait_flag:
                #wait = input("是否实时接收消息？")
                wait = "ggg"
            if wait == "ggg":
                wait_flag = False

            return

    def get_retweet_user(self, fans_range, get_count):
        start_range, end_range = fans_range.split('-')

        myclient2 = pymongo.MongoClient(COMMON_DATABASE)
        db = myclient2["all_fans"]
        table_fans = db['fans']
        first_fans = db["first_retweet"]
        count = get_count  # 每次30个

        all_list = []

        userlist = list(table_fans.find({"country":"CH"}))
        random.shuffle(userlist)

        firstlist = list(first_fans.find({}))
        random.shuffle(firstlist)

        for i in firstlist:
            if self.table_auto_retweet.find_one({"username": i["user"]}) != None:
                continue
            all_list.append(i["user"].replace('/', ''))

        for item in userlist:
            user = item['user']

            if item['fans'] < int(start_range) or item['fans'] > int(end_range):
                continue

            if self.table_auto_retweet.find_one({"username": user}) != None:
                continue

            all_list.append(user)

        for user in all_list:
            try:
                if self.table_auto_retweet.find_one({"username": user}) != None:
                    continue

                self.driver.get("https://twitter.com/{}".format(user))
                time.sleep(3)

                if len(self.driver.find_elements_by_xpath('//div[@aria-label="Message"]')) == 0:
                    continue
                else:
                    self.driver.find_elements_by_xpath('//div[@aria-label="Message"]')[0].click()
                    time.sleep(5)
                    # 如果用户名字没获取，则获取一下
                    try:
                        username = self.driver.find_element_by_xpath(
                            '//div[@class="css-901oao css-bfa6kz r-14j79pv r-1qd0xha r-n6v787 r-16dba41 r-1cwl3u0 r-bcqeeo r-qvutc0"]/span').text.replace(
                            '@', '')
                        if self.table_auto_retweet.find_one({"dialog": self.driver.current_url}) != None:
                            self.table_auto_retweet.update_one({"dialog": self.driver.current_url}, {"$set": {"username": username}})
                            continue
                    except Exception as e:
                        print("update user name error")
                        print(e)
                        pass

                    url = self.driver.current_url
                    if "request" in url or self.table_auto_retweet_block.find_one({"dialog":url}) != None:
                        continue
                    if self.table_auto_retweet.find_one({"dialog": url}) == None:
                        item_new = {"dialog": url,
                                    "last_task_time": (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                    "last_send_time": "",
                                    "last_task": "",
                                    "username": "",
                                    "start_from": time.strftime("%Y-%m-%d", time.localtime())
                                    }
                        self.table_auto_retweet.insert_one(item_new)
                        count -= 1
                        print(count)
                        if count == 0:
                            break
                        time.sleep(3)
            except Exception as e:
                print("获取互推用户失败")
                print(e)

    def check_his_retweet(self, user_name, my_content_list):
        # print("正在检查:{}".format(user_name))
        self.driver.get('https://twitter.com/{}'.format(user_name))
        time.sleep(3)
        self.check_access()
        detail_list = []

        if "is blocked" in self.driver.page_source.lower():
            return

        check_height = self.driver.execute_script("return document.body.scrollHeight;")
        check_count = 0
        circle_flag = True
        while circle_flag:
            link_element = self.driver.find_elements_by_xpath(
                '//a[@class="css-4rbku5 css-18t94o4 css-901oao r-m0bqgq r-1loqt21 r-1q142lx r-1qd0xha r-a023e6 r-16dba41 r-rjixqe r-bcqeeo r-3s2u2q r-qvutc0"]')
            for element in link_element:
                try:
                    href = element.get_attribute("href")
                    detail = href
                    if detail in my_content_list:
                        # print("{}帮我推了".format(user_name))
                        return True
                    if detail not in detail_list:
                        detail_list.append(detail)
                        if len(detail_list) > 500:
                            circle_flag = False
                            break

                except Exception as e:
                    print(e)
                    continue

            js = "window.scrollBy(0, 1000)"
            self.driver.execute_script(js)
            time.sleep(2)
            height = self.driver.execute_script("return document.body.scrollHeight;")
            if height == check_height:
                if check_count == 200:
                    break
                else:
                    check_count += 1
            else:
                check_count = 0
                check_height = height

        # 对比我给他的推文，是否在它的列表里

        print("{}没帮我推，内容：{}".format(user_name, my_content))
        item = {"username": user_name, "retweet_list": detail_list}
        if self.table_check_retweet.find_one({"username": user_name}) == None:
            self.table_check_retweet.insert_one(item)
        else:
            self.table_check_retweet.delete_one({"username": user_name})
            self.table_check_retweet.insert_one(item)
        return False

if __name__ == '__main__':
    #将优先互推的用户存入
#--------------------------------------------
    f = open("first_retweet.txt", "r")
    data = f.readlines()
    f.close()

    myclient = pymongo.MongoClient("mongodb://192.168.123.214:27017/")
    mydb = myclient["all_fans"]
    mycol = mydb["first_retweet"]

    for d in data:
        if mycol.find_one({"user":d.strip()}) == None:
            mycol.insert_one({"user":d.strip()})
# --------------------------------------------

    if len(sys.argv) >= 4:
        input_user = sys.argv[2]
    else:
        input_user = input("Please choose user:\n")
    user = config["user"][input_user]

    if len(sys.argv) >= 4:
        input_action = sys.argv[3]
    else:
        input_action = input("13.retweet_all_my_tweet\n14.auto_retweet\n16.talk_retweet_user\n19.check_if_retweet")

    if input_action == "13":
        action = "retweet_all_my_tweet"

    elif input_action == "14":
        action = "auto_retweet"

    elif input_action == "16":
        action = "get_retweet_user"

    elif input_action == "19":
        action = "check_if_retweet"

    t = Twitter(user, action)

    if action == "retweet_all_my_tweet":
        t.retweet_all_my_tweet()

    elif action == "auto_retweet":
        datestamp = time.strftime("%Y-%m-%d", time.localtime())

        myclient = pymongo.MongoClient(COMMON_DATABASE)
        mydb = myclient["daily_retweet_task"]
        mycol = mydb["detail"]

        data = mycol.find_one({"date":datestamp})["item"]

        user_data = data[t.username]
        if datestamp != user_data["date"]:
            print("日期不符，更新一下")
            sys.exit()
        if t.table_daily_task.find_one({"date": datestamp}) == None:
            t.table_daily_task.insert_one({"date": datestamp, "retweet": user_data["content"]})

        content = user_data["content"]
        reply = user_data["reply"]
        print(content)
        print(reply)

        while True:
            datestamp2 = time.strftime("%Y-%m-%d", time.localtime())
            if datestamp != datestamp2:
                break
            t.auto_retweet(content, reply)
            time.sleep(5*60)

    elif action == "get_retweet_user":
        datestamp = time.strftime("%Y-%m-%d", time.localtime())

        if len(sys.argv) >= 5:
            fans_range = sys.argv[4]
        else:
            fans_range = input("please input fans range, 10000-20000:\n")

        if len(sys.argv) >= 6:
            get_count = int(sys.argv[5])
        else:
            get_count = int(input("please input user num:\n"))

        myclient = pymongo.MongoClient(COMMON_DATABASE)
        mydb = myclient["daily_retweet_task"]
        mycol = mydb["detail"]
        data = mycol.find_one({"date":datestamp})["item"]

        user_data = data[t.username]
        if datestamp != user_data["date"]:
            print("日期不符，更新一下")
            sys.exit()

        t.get_retweet_user(fans_range.strip(), get_count)
        # a = input("{} done".format(t.username))
        print("获取互推用户结束，开始重推自己的推文\n")

        t.retweet_all_my_tweet()
        print("重推自己的推文结束，开始日常互推\n")

        if t.table_daily_task.find_one({"date": datestamp}) == None:
            t.table_daily_task.insert_one({"date": datestamp, "retweet": user_data["content"]})
        content = user_data["content"]
        reply = user_data["reply"]
        print(content)
        print(reply)
        t.auto_retweet(content, reply)
        t.retweet_all_my_tweet()

    elif action == "check_if_retweet":
        print(t.username)
        my_content_list = []
        my_content = t.table_daily_task.find({}).sort("_id", pymongo.DESCENDING)
        for i in my_content:
            my_content_list.append(i["retweet"])
            if len(my_content_list) == 3:
                break

        count = 30
        yesterday_timestamp = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        # result = list(t.table_auto_retweet.find({"last_send_time":datestamp, "last_task_time":datestamp, "wait_check":True}))
        result = t.table_auto_retweet.find({"last_task_time": yesterday_timestamp}).sort("check_point", pymongo.ASCENDING)
        #random.shuffle(result)

        for r in result:
            if "last_task" not in r.keys():
                continue

            if "check_point" not in r.keys():
                check_point = 100
            else:
                check_point = r["check_point"]

            if "username" in r.keys() and r["username"] != '':
                username = r["username"]
                if t.check_his_retweet(username, my_content_list):
                    t.table_auto_retweet.update_one({"username":username}, {"$set": {"check_point": check_point + 1}})
                else:
                    t.table_auto_retweet.update_one({"username": username}, {"$set": {"check_point": check_point - 1}})

                count -= 1
                if count == 0:
                    break
        tmp = input("结束")