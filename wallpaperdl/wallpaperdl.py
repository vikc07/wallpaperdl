from bs4 import BeautifulSoup
import os
import re
import shutil
import requests
import argparse
import time
from gpm import logging, config, formatting

c = config.Config(script=__file__)
c.read()


def sanitize_string(input_str):
    output_str = input_str.lower().replace(' ', '_').rstrip('.')
    output_str = re.sub(r'[!@#$%^&*()\[\]{};:/<>?\\|`~\-=+\'\"]', '', output_str)
    return output_str


def do(site, download_dir=None):
    err = 0

    log.info('site: {}'.format(site))

    if download_dir is None:
        download_dir = os.path.dirname(os.path.abspath(__file__))

    log.info('download_dir: {}'.format(download_dir))

    total_downloaded = 0
    total_downloaded_size = 0
    total_skipped = 0

    start_time = time.time()

    # find total pages first
    total_pages = 0
    total_images = 0

    url = c.url_alphacoder
    r = requests.get(url)
    if r.status_code == 200:
        page_html = BeautifulSoup(r.text, features="html.parser")
        pagination = page_html.find('ul', attrs={'class':re.compile('pagination')})
        pagination = pagination.find_all('a', attrs={'href':re.compile('alphacoders')})
        del pagination[-1]
        total_pages = int(pagination.pop().string)

        if c.limit_num_pages != -1:
            total_pages = c.limit_num_pages
            log.info('page limit set in config file')

        # find number of thumbnails
        total_images = len(page_html.find_all('div', attrs={'class': re.compile('thumb-container-big')})) * total_pages

        log.info('total pages: {}'.format(total_pages))
        log.info('total estimated number of images: {}'.format(total_images))

    # let's rock n' roll
    page_num = 1
    while page_num <= total_pages:
        url = c.url_alphacoder
        if page_num > 1:
            url += '&page=' + str(page_num)

        # check if this url is valid
        r = requests.get(url)
        if r.status_code == 200:
            page_html = BeautifulSoup(r.text, features="html.parser")
            containers = page_html.find_all('div', attrs={'class':re.compile('thumb-container-big')})

            for container in containers:
                thumbnail_url = container.find('img', attrs={'alt':re.compile('HD Wallpaper')}).attrs['data-src']
                img_url = thumbnail_url.replace('thumb-350-','')
                category = sanitize_string(container.find('a', attrs={'href': re.compile('by_category')}).string)
                subcategory = sanitize_string(container.find('a', attrs={'href': re.compile('by_sub_category')}).string)
                tags = []

                for t in container.find_all('a', attrs={'href': re.compile('tags')}):
                    tags.append(sanitize_string(t.string))

                # define file name, considering OSes typically only allow 255 chars in file name
                local_file_dir = os.path.join(download_dir, c.default_download_dir_name + '_' + site, category,
                                              subcategory)
                local_file_name = sanitize_string(os.path.basename(img_url))
                local_file_name = os.path.splitext(local_file_name)[0] + '_' + category + '_' \
                                  + subcategory+ '_' + ','.join(tags)\
                                  + os.path.splitext(local_file_name)[1]
                if len(local_file_name) > 255:
                    local_file_name = os.path.splitext(local_file_name)[0][:240] + os.path.splitext(local_file_name)[1]

                local_file_path = os.path.join(local_file_dir, local_file_name)

                log.info('thumbnail: {}'.format(thumbnail_url))
                log.info('img: {}'.format(img_url))
                log.info('category: {}'.format(category))
                log.info('subcategory: {}'.format(subcategory))
                log.info('tags: {}'.format(','.join(tags)))
                log.info('local file: {}'.format(local_file_path))

                # create the actual file
                if not c.test_mode:
                    if not os.path.exists(local_file_dir):
                        os.makedirs(local_file_dir)

                    if not os.path.isfile(local_file_path):
                        r = requests.get(img_url, stream=True)
                        file_size = int(r.headers['Content-length'])
                        log.info('file size: {}'.format(formatting.fsize_pretty(file_size)))
                        if r.status_code == 200:
                            with open(local_file_path, 'wb') as f:
                                r.raw.decode_content = True
                                shutil.copyfileobj(r.raw, f)
                                total_downloaded += 1
                                total_downloaded_size += file_size
                    else:
                        log.info('local file {} exits, skipping'.format(local_file_path))
                        total_skipped += 1

                    elapsed_time = time.time() - start_time

                    files_remaining = total_images - total_downloaded - total_skipped

                    if total_downloaded != 0:
                        average_file_size = total_downloaded_size / total_downloaded
                    else:
                        average_file_size = 0

                    download_rate_files = total_downloaded / elapsed_time
                    download_rate_gb = total_downloaded_size / elapsed_time

                    if download_rate_files != 0:
                        time_remaining = files_remaining / download_rate_files
                    else:
                        time_remaining = 60 * 60 * 24 * 365

                    size_remaining = average_file_size * files_remaining

                    log.info('downloaded_count: {}'.format(total_downloaded))
                    log.info('downloaded_size: {}'.format(formatting.fsize_pretty(total_downloaded_size)))
                    log.info('skipped_count: {}'.format(total_skipped))
                    log.info('runtime: {}'.format(formatting.time_pretty(elapsed_time)))
                    log.info('download_rate: {}files/s {}/s'.format(round(download_rate_files, 2),
                                                                    formatting.fsize_pretty(download_rate_gb)))
                    log.info('est. number of files remaining: {}'.format(files_remaining))
                    log.info('est. time remaining: {}'.format(formatting.time_pretty(time_remaining)))
                    log.info('est. size remaining: {}'.format(formatting.fsize_pretty(size_remaining)))

            page_num += 1
        else:
            log.error('error occurred connecting to url {}'.format(url))

    return err


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('site', choices=['alphacoder'], help='site identifier')
    parser.add_argument('--download_dir', help='full path of the target folder to save images to')
    args = parser.parse_args()

    log = logging.Log(log_level=c.log_level, script=__file__)

    log.start()
    errcode = do(
        site=args.site,
        download_dir=args.download_dir
    )
    log.end()
    exit(errcode)
