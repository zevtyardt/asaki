#!/usr/bin/python3
from lib.decorators import with_argparser
import re
import os
import urllib.request
from urllib.parse import urlparse
import signal
import argparse
import json
import sys
from colorama import Fore, Style, init

init()

# this ANSI code lets us erase the current line
ERASE_LINE = "\x1b[2K"

COLOR_NAME_TO_CODE = {"default": "", "red": Fore.RED,
                      "green": Fore.GREEN}


# type: (str, str, bool, any) -> None
def print_text(text, color="default", in_place=False, **kwargs):
    """
    print text to console, a wrapper to built-in print

    :param text: text to print
    :param color: can be one of "red" or "green", or "default"
    :param in_place: whether to erase previous line and print in place
    :param kwargs: other keywords passed to built-in print
    """
    if in_place:
        print("\r" + ERASE_LINE, end="")
    print(COLOR_NAME_TO_CODE[color] + text + Style.RESET_ALL, **kwargs)


def create_url(url):
    """
    From the given url, produce a URL that is compatible with Github's REST API. Can handle blob or tree paths.
    """
    # Check if the given url is a url to a GitHub repo. If it is, tell the
    # user to use 'git clone' to download it
    if len(list(filter(None,
                       urlparse(url).path.split("/")
                       ))) < 3:
        print_text("The given url is a complete repository. Use 'git clone' to download the repository",
                   "red", in_place=True)
        return 0

    # extract the branch name from the given url (e.g master)
    branch = re.search(r"/(tree|blob)/(.+?)/", url)
    download_dirs = url[branch.end():]
    api_url = (url[:branch.start()].replace("github.com", "api.github.com/repos", 1) +
               "/contents/" + download_dirs + "?ref=" + branch.group(2))
    return api_url, download_dirs


def download(repo_url, flatten=False, output_dir="./"):
    """ Downloads the files and directories in repo_url. If flatten is specified, the contents of any and all
     sub-directories will be pulled upwards into the root folder. """

    # generate the url which returns the JSON data
    if not (url := create_url(repo_url)):
        return 0
    api_url, download_dirs = url

    # To handle file names.
    if not flatten:
        if len(download_dirs.split(".")) == 0:
            dir_out = os.path.join(output_dir, download_dirs)
        else:
            dir_out = os.path.join(
                output_dir, "/".join(download_dirs.split("/")[:-1]))
    else:
        dir_out = output_dir

    try:
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        response = urllib.request.urlretrieve(api_url)
    except KeyboardInterrupt:
        # when CTRL+C is pressed during the execution of this script,
        # bring the cursor to the beginning, erase the current line, and dont make a new line
        print_text("Got interrupted", "red", in_place=True)
        return 0

    if not flatten:
        # make a directory with the name which is taken from
        # the actual repo
        os.makedirs(dir_out, exist_ok=True)

    # total files count
    total_files = 0

    with open(response[0], "r") as f:
        data = json.load(f)
        # getting the total number of files so that we
        # can use it for the output information later
        total_files += len(data)

        # If the data is a file, download it as one.
        if isinstance(data, dict) and data["type"] == "file":
            if os.path.isfile(f"{download_dirs}/{data['name']}"):
                print_text(
                    f"{Fore.YELLOW}Skipped: {Fore.WHITE}{download_dirs}/{data['name']} already downloaded")
            else:
                try:
                    # download the file
                    opener = urllib.request.build_opener()
                    opener.addheaders = [('User-agent', 'Mozilla/5.0')]
                    urllib.request.install_opener(opener)
                    urllib.request.urlretrieve(
                        data["download_url"], os.path.join(dir_out, data["name"]))
                    # bring the cursor to the beginning, erase the current line, and dont make a new line
                    print_text("Downloaded: " + Fore.WHITE +
                               "{}/{}".format(download_dirs, data["name"]), "green", in_place=True)

                    return total_files
                except KeyboardInterrupt:
                    # when CTRL+C is pressed during the execution of this script,
                    # bring the cursor to the beginning, erase the current line, and dont make a new line
                    print_text("✘ Got interrupted", 'red', in_place=False)
                    return 0

        for file in data:
            file_url = file["download_url"]
            file_name = file["name"]

            if flatten:
                path = os.path.basename(file["path"])
            else:
                path = file["path"]
            dirname = os.path.dirname(path)

            if dirname != '':
                os.makedirs(os.path.dirname(path), exist_ok=True)
            else:
                pass

            if file_url is not None:
                if os.path.isfile(f"{download_dirs}/{file_name}"):
                    print_text(
                        f"{Fore.YELLOW}Skipped: {Fore.WHITE}{download_dirs}/{file_name} already downloaded")
                else:
                    try:
                        opener = urllib.request.build_opener()
                        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
                        urllib.request.install_opener(opener)
                        # download the file
                        urllib.request.urlretrieve(file_url, path)

                        # bring the cursor to the beginning, erase the current line, and dont make a new line
                        print_text("Downloaded: " + Fore.WHITE +
                                   "{}/{}".format(download_dirs, file_name), "green", in_place=True)

                    except KeyboardInterrupt:
                        # when CTRL+C is pressed during the execution of this script,
                        # bring the cursor to the beginning, erase the current line, and dont make a new line
                        print_text("Got interrupted", 'red', in_place=False)
                        return 0
            else:
                download(file["html_url"], flatten, dir_out)

    return total_files


class Gitdir(object):
    parser = argparse.ArgumentParser()
    parser.add_argument('urls', nargs="+",
                        help="List of Github directories to download.")
    parser.add_argument('--output_dir', "-d", dest="output_dir", default="./",
                        help="All directories will be downloaded to the specified directory.")

    parser.add_argument('--flatten', '-f', action="store_true",
                        help='Flatten directory structures. Do not create extra directory and download found files to'
                             ' output directory. (default to current directory if not specified)')

    def download_git_directory(self, args):
        if isinstance(args, str):
            args = self.parser.parse_args([args])
        flatten = args.flatten
        total_files = 0
        for url in args.urls:
            total_files = download(url, flatten, args.output_dir)
        if total_files:
            print_text("Download complete", "green", in_place=True)

    @with_argparser(parser)
    def do_gitdir__Downloader(self, args):
        """Download a single directory/folder from a GitHub repo"""
        self.download_git_directory(args)
