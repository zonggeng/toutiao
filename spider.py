import json
from json.decoder import JSONDecodeError
from urllib.parse import urlencode
from hashlib import md5
import re

import os
import pymongo
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
import requests
from config import *
from multiprocessing import Pool #线程池

client = pymongo.MongoClient(MONGO_URL,connect=False) #多线程的情况下加入connect防止死锁
db = client[MONGO_DB]

def get_page_index(offset,keyword,):
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': 20,
        'cur_tab': 3
    }
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data) #把字典转换成url请求参数
    try:
        response = requests.get(url)
        if response.status_code == 200 :
            return response.text
        return None
    except RequestException:
        print('请求索引页面出错')
        return None

def parse_page_index(html):
    try:
        data = json.loads(html)
        if data and 'data' in data.keys():
            for item in data.get('data'):
                yield item.get('article_url')  # 构造一个生成器
    except JSONDecodeError:
        pass



def get_page_detail(url):
    try:
        response = requests.get(url)
        if response.status_code == 200 :
            return response.text
        return None
    except RequestException:
        print('请求详情页面出错',url)
        return None

def parse_page_detail(html,url):
    soup = BeautifulSoup(html,'lxml')
    title = soup.select('title')[0].get_text() # 这里获取title标签内容
    images_pattern = re.compile('gallery: JSON.parse\("(.*?)"\),',re.S)
    result = re.search(images_pattern,html)
    try:
        temp = re.sub(r'\\','',result.group(1)) #这里因为是获取到的json字符串里面有\反斜杠!所以要去掉不然等会json.loads转换不了
    except AttributeError:
        print('页面不符合要求')
    if result:
        data = json.loads(temp)
        if data and 'sub_images' in data.keys():
            sub_imges = data.get('sub_images')
            images = [item.get('url') for item in sub_imges]
            for image in images : download_image(image,title)
            return {
                'title' : title ,
                'url' : url ,
                'images' : images
            }
        print('111')

def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储到MongoDB成功',result)
        return True
    return False

def download_image(url,title):
    print("正在下载"+url+'图片')
    try:
        response = requests.get(url)
        if response.status_code == 200 :
            save_image(response.content,title) #content返回的是二进制 text返回的是文本
        return None
    except RequestException:
        print('请求图片出错',url)
        return None

def GetDesktopPath():
    return os.path.join(os.path.expanduser("~"), 'Desktop')

def save_image(content,title):
    directory = GetDesktopPath() + '\\' + '爬虫' + '\\' + title
    if not os.path.exists(directory) : os.makedirs(directory)
    file_path = '{0}\{1}.{2}'.format(directory,md5(content).hexdigest(),'jpg')  # md5(content).hexdigest() 图片用MD5值来命名可以防止重复下载
    if not os.path.exists(file_path):
        with open(file_path,'wb') as f :
            f.write(content)
            f.close()

def main(offset):
    html = get_page_index(offset,KEYWORD)
    for url in parse_page_index(html):
        html = get_page_detail(url)
        if html :
            result = parse_page_detail(html,url)
            # if result:save_to_mongo(result)   #保存到mongo数据库里面去
if __name__ == '__main__':

    groups = [x * 20 for x in range(GROUP_START,GROUP_END+1)]
    pool = Pool()
    pool.map(main,groups)