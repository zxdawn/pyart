# Xin Zhang (xinzhang1215@gmail.com)
# 29 Jun 2018
# coding: utf-8

import os
import requests
import argparse
import urllib.error
import urllib.request
from bs4 import BeautifulSoup

def parse_args():
    """
    Parses command line arguments given in bash.
    Allows for two types of arguments: required and optional.
     Required:
        region and savepath
     Optional:
        resolution
    :param args_in: Pass
    :return:
    """
    parser = argparse.ArgumentParser(description='program to download radar maps from nmc')
    parser.add_argument('-r', '--region', default = 'all', type = str, help="region of maps")
    parser.add_argument('-p', '--resolution', default = 'medium', type = str, help="small or medium resolution")
    parser.add_argument('-s', '--savepath', default = './', type = str, help="savepath of images")
    parser.add_argument('-d', '--debug', default = 0, type = int, help="debug level")
    args = parser.parse_args()

    return vars(args)

def get_urls(region, resolution):
    # Download the Response object and parse
    page = requests.get('http://www.nmc.cn/publish/radar/'+region+'.html')
    soup = BeautifulSoup(page.content, 'html.parser')

    # Finding all instances of 'img' at once
    pics = soup.find_all('p', class_='img')

    # get url of each picture and save to a list
    urls = []
    for pic in pics:
        url = pic.img.get('data-original')
        urls.append(url)
    urls = [url.replace('small', resolution) for url in urls]

    return (urls)

def download(urls, region, savepath, debug):
    # Check whether savepath end with '/'.
    if savepath.endswith('/'):
        pass
    else:
        savepath = savepath+'/'

    # Check whether savepath exists. If not, create it.
    savepath = savepath+region+'/'
    if not os.path.exists(savepath):
        if debug > 0:
            print ('mkdir '+savepath)
        os.makedirs(savepath)

    # Download images to savepath
    print ('Download '+region+' radar maps......')
    
    for url in urls:
        try:
            name = url.split("/")[9][38:50]+'.png'
            fullfilename = os.path.join(savepath, name)

            if debug > 0:
                if os.path.isfile(savepath+name):
                    print (name, 'exists in', savepath, ' Skip!!')
                else:
                    print ('Downloading',name)
            
            urllib.request.urlretrieve(url, fullfilename)

        except urllib.error.HTTPError as err:
            # pass
            print(err.code)

    print ('    Finish. Save images to', savepath)

def main(region, resolution, savepath, debug):
    # list of constant maps
    maps = ['chinaall','dongbei','huabei','huanan','huazhong','xibei','xinan','huadong']

    if region == 'all':
        for r in maps:
            urls = get_urls(r, resolution)
            download(urls, r, savepath, debug)
    else:
        urls = get_urls(region, resolution)
        download(urls, region, savepath, debug)

if __name__ == '__main__':
    args = parse_args()
    main(**args)