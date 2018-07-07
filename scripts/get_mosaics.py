import os
import time
import requests
import argparse
import urllib.error
import urllib.request
from bs4 import BeautifulSoup

domain_name = 'http://www.nmc.cn'
base_mosaic_url = domain_name + '/publish/radar/chinaall.html'
base_station_url = domain_name + '/publish/radar/bei-jing/da-xing.htm'

def parse_args():
    """
    Parses command line arguments given in bash.
    Defaults:
        region: all
        resolution: medium
        savepath: ./
        debug: 0
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


# Get main urls
def get_main_url(base_url, suffix):
    htmls =[]
    base_page = requests.get(base_url)
    soup = BeautifulSoup(base_page.content, 'html.parser')
    for link in soup.findAll('a'):
        sub_htmls = link.get('href')
        if sub_htmls.startswith('/publish/radar/') & sub_htmls.endswith(suffix):
            htmls.append(sub_htmls)

    return ['{}{}'.format(domain_name,html) for html in list(set(htmls))]


def get_stations_url(base_url, suffix):
    htmls =[]
    base_page = requests.get(base_url)
    soup = BeautifulSoup(base_page.content, 'html.parser')
    for link in soup.findAll('a'):
        sub_htmls = link.get('href')
        if sub_htmls.startswith('/publish/radar/') & sub_htmls.endswith(suffix):
            # Filter out Surpluses
            if sub_htmls.split("/")[3] == base_url.split("/")[5]:
                htmls.append(sub_htmls)

    return ['{}{}'.format(domain_name,html) for html in list(set(htmls))]



def get_img_urls(url, resolution):
    # Download the Response object and parse
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')

    # Finding all instances of 'img' at once
    pics = soup.find_all('p', class_='img')

    # get url of each picture and save to a list
    img_urls = []
    for pic in pics:
        img_url = pic.img.get('data-original')
        img_urls.append(img_url)
    img_urls = [url.replace('small', resolution) for url in img_urls]

    return img_urls


def download(urls, region, resolution, savepath, debug):
    # Download images to savepath
    if region == 'regions':
        print ('Downloading regional radar maps......')
    elif region == 'stations':
        print ('Downloading '+urls[0].split("/")[5]+' radar maps......')

    for url in urls:
        try:
            htmls = get_img_urls(url, resolution)

            # get dir_name and subdir_name
            if region == 'regions':
                dir_name = url.split("/")[5][:-5]
                subdir_name = ''
            elif region == 'stations':
                dir_name = url.split("/")[5]
                subdir_name = url.split("/")[6][:-4]

            # Check whether dirs of savepath exists. If not, create it.
            full_savepath = os.path.join(savepath, dir_name, subdir_name)
            if not os.path.exists(full_savepath):
                if debug > 0:
                    print ('mkdir '+full_savepath)
                os.makedirs(full_savepath, exist_ok=True)

            if region == 'regions':
                print ('    Downloading', dir_name, 'mosaics')
            elif region == 'stations' and debug > 0:
                print ('    Downloading', subdir_name, 'mosaics')

            # get name/url and download
            for html in htmls:
                # get date for img_name
                split_html = html.split("/")
                name = ''.join(split_html[4:7])
                sdate = split_html[9].find(name)
                edate = sdate+12
                name  = split_html[9][sdate:edate]

                fullfilename = os.path.join(full_savepath, name+'.png')

                if debug > 0:
                    if os.path.isfile(fullfilename):
                        print ('    ', name, 'exists in', full_savepath, ' Skip!!')
                    else:
                        print ('        Downloading',name)
                
                urllib.request.urlretrieve(html, fullfilename)

        except urllib.error.HTTPError as err:
            # pass
            print(err.code)

        finally:
            finish_output = '    Finish. Save images to '+ os.path.join(savepath,dir_name)
            if region == 'regions':
                print (finish_output)
    if region == 'stations':
        print (finish_output)


# Get all urls
def download_imgs(region, resolution, savepath, debug):
    # get main urls;
    # for mosaics: url of areas, suffix = html
    # for stations: url of provinces, suffix = htm
    if region == 'regions':
        suffix = 'html'
        main_htmls = get_main_url(base_mosaic_url, suffix)
    elif region == 'stations':
        suffix = 'htm'
        main_htmls = get_main_url(base_station_url, suffix)

    # for mosaics: download directly
    if region == 'regions':
        download (main_htmls, region, resolution, savepath, debug)
    # for stations: get urls of sub_stations and download
    elif region == 'stations':
        for html in main_htmls:
            sub_htmls = get_stations_url(html, suffix)
            download (sub_htmls, region, resolution, savepath, debug)


def main(region, resolution, savepath, debug):
    if region == 'all':
        download_imgs('regions', resolution, savepath, debug)
        download_imgs('stations', resolution, savepath, debug)
    elif region == 'regions' or region == 'stations':
        download_imgs(region, resolution, savepath, debug)
    else:
        print ('Please input supported region:\
            all, mosaics and stations')


if __name__ == '__main__':
    start_time = time.time()
    args = parse_args()
    main(**args)
    print("--- %s seconds ---" % (time.time() - start_time))