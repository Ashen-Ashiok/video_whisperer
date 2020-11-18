#!/usr/bin/env python3
import argparse
import base64
import os
import re
import requests
import subprocess
import logging
from tqdm import tqdm

# TODO more functions
# TODO more options

parser = argparse.ArgumentParser(
    description="""
Video Whisperer is a simple Python script that downloads and merges segmented video and audio.
The primary input is a simle tab delimited file with pairs in following format:

<desired_filename_of_complete_video>TAB<URL_to_master_json_file>

The tool gets the highest quality video and audio tracks available defaultly.
This kind of video/audio segmentation can be often found in online streaming players, notably Vimeo.
Video Whisperer uses Requests to get the video and audio segments and calls FFmpeg for mixing.
It was developed for Python 3.9.""",
    epilog="""Find more info and latest version on https://github.com/Ashen-Ashiok/video_whisperer""",
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("-i", "--url-list", help="List of filename/master.json URL pairs, delimited by tabs")
parser.add_argument("--no-mix", help="Do not merge audio and video files. Use this option in case you want to merge "
                                     "these files manually. This is a superset of --no-mix", action="store_true")
parser.add_argument("--no-delete", help="Do not delete audio and video files after mixing", action="store_true")
parser.add_argument("--quiet", help="No terminal output. None. Zilch. Not recommended.", action="store_true")

args = parser.parse_args()

disable_progress_bar = False
if args.quiet:
    logging.basicConfig(level=logging.ERROR, format="%(message)s")
    disable_progress_bar = True
else:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def download_files():
    # Files map is a structure that holds output filename, audio track filename and video track filename
    files_map = []
    for line in open(args.url_list):
        output_file, master_json_url = line.rstrip().split("\t")
        logging.info("Processing {}".format(output_file))

        # Extract base URL for video/audio URL and fetch the JSON file via Requests response
        # The JSON file contains complete information about video and audio segments, codecs, format etc.
        base_url = master_json_url[:master_json_url.rfind("/", 0, -26) + 1]
        resp = requests.get(master_json_url)
        master_json_content = resp.json()

        # Download the video track in highest quality
        heights = [(i, d["height"]) for (i, d) in enumerate(master_json_content["video"])]
        idx = max(heights, key=lambda x: x[1])[0]
        video = master_json_content["video"][idx]
        video_base_url = base_url + video["base_url"]
        logging.info("\tBase URL: {}".format(video_base_url))

        video_filename = "video_%s" % output_file
        logging.info("Saving VIDEO to {}".format(video_filename))

        # Save the video files by joining them together (init_segment + all other segments)
        video_file = open(video_filename, "wb")
        init_segment = base64.b64decode(video["init_segment"])
        video_file.write(init_segment)

        for segment in tqdm(video["segments"], disable=disable_progress_bar):
            segment_url = video_base_url + segment["url"]
            resp = requests.get(segment_url, stream=True)
            if resp.status_code != 200:
                logging.info("not 200!")
                logging.info(resp)
                logging.info(segment_url)
                break
            for chunk in resp:
                video_file.write(chunk)

        video_file.flush()
        video_file.close()

        # Download the audio track in a similar way
        bit_rate = [(i, d["bitrate"]) for (i, d) in enumerate(master_json_content["audio"])]

        logging.info("Bitrate {}".format(bit_rate))

        idx = max(bit_rate, key=lambda x: x[1])[0]
        audio = master_json_content["audio"][idx]
        audio_base_url = base_url + audio["base_url"]
        logging.info("Base url: {}".format(audio_base_url))

        audio_filename = "audio_%s" % output_file
        logging.info("Saving AUDIO to {}".format(audio_filename))

        # Save the video files by joining them together (init_segment + all other segments)
        audio_file = open(audio_filename, "wb")

        init_segment = base64.b64decode(audio["init_segment"])
        audio_file.write(init_segment)

        for segment in tqdm(audio["segments"], disable=disable_progress_bar):
            segment_url = audio_base_url + segment["url"]
            segment_url = re.sub(r"/[a-zA-Z0-9_-]*/\.\./", r"/", segment_url.rstrip())
            resp = requests.get(segment_url, stream=True)
            if resp.status_code != 200:
                logging.info("not 200!")
                logging.info(resp)
                logging.info(segment_url)
                break
            for chunk in resp:
                audio_file.write(chunk)

        audio_file.flush()
        audio_file.close()
        logging.info("Finished downloading video and audio for file {}".format(output_file))

        files_map.append((output_file, audio_filename, video_filename))

    return files_map


def mix_files(files_map):
    # Create output files directory
    output_dir_name = "output"
    try:
        os.mkdir(output_dir_name)
    except OSError:
        logging.error("Creation of the directory {} failed".format(output_dir_name))

    for output_filename, audio_filename, video_filename in files_map:
        # Combine audio and video here
        logging.info("Mixing video and audio for file {}".format(output_filename))
        cmd = "ffmpeg -y -i {} -i {} {}\\{}".format(audio_filename, video_filename, output_dir_name, output_filename)
        if args.quiet:
            cmd += " -hide_banner -loglevel warning"

        subprocess.call(cmd, shell=True)
        logging.info("Mixing for file {} done".format(output_filename))

        if not args.no_delete:
            # Delete the remaining single audio and video files
            os.remove(audio_filename)
            os.remove(video_filename)
            logging.info("Temporary files {} and {} removed!".format(audio_filename, video_filename))


audio_video_output_map = download_files()

if not args.no_mix:
    mix_files(audio_video_output_map)
