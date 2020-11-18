#!/usr/bin/env python3
import argparse
import base64
import os
import re
import requests
import subprocess
from tqdm import tqdm

# TODO add output folder param
# TODO functions
# TODO add option to use pre-downloaded?
# TODO interactive mode?

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--url-list", help="List of URL/filename pairs, delimited by tabs")
parser.add_argument("--no-mix", help="Do not merge audio and video files", action="store_true")
parser.add_argument("--no-delete", help="Do not merge audio and video files", action="store_true")
args = parser.parse_args()


def download_files():
    files_map = []
    for line in open(args.url_list):
        output_file, master_json_url = line.rstrip().split('\t')
        print('\n\n\nProcessing %s' % output_file)

        # Extract some stuff
        base_url = master_json_url[:master_json_url.rfind('/', 0, -26) + 1]
        resp = requests.get(master_json_url)
        content = resp.json()

        # Video download here
        heights = [(i, d["height"]) for (i, d) in enumerate(content["video"])]
        idx = max(heights, key=lambda x: x[1])[0]
        video = content["video"][idx]
        video_base_url = base_url + video["base_url"]
        print("Base url:", video_base_url)

        video_filename = "video_%s.mp4" % output_file
        print("Saving VIDEO to %s" % video_filename)

        video_file = open(video_filename, "wb")

        init_segment = base64.b64decode(video["init_segment"])
        video_file.write(init_segment)

        for segment in tqdm(video["segments"]):
            segment_url = video_base_url + segment["url"]
            resp = requests.get(segment_url, stream=True)
            if resp.status_code != 200:
                print("not 200!")
                print(resp)
                print(segment_url)
                break
            for chunk in resp:
                video_file.write(chunk)

        video_file.flush()
        video_file.close()

        # Audio download here
        bit_rate = [(i, d["bitrate"]) for (i, d) in enumerate(content["audio"])]

        print("Bitrate", bit_rate)

        idx = max(bit_rate, key=lambda x: x[1])[0]
        audio = content["audio"][idx]
        audio_base_url = base_url + audio["base_url"]
        print("Base url:", audio_base_url)

        audio_filename = "audio_%s.mp4" % output_file
        print("Saving AUDIO to %s" % audio_filename)

        audio_file = open(audio_filename, "wb")

        init_segment = base64.b64decode(audio["init_segment"])
        audio_file.write(init_segment)

        for segment in tqdm(audio["segments"]):
            segment_url = audio_base_url + segment["url"]
            segment_url = re.sub(r"/[a-zA-Z0-9_-]*/\.\./", r"/", segment_url.rstrip())
            resp = requests.get(segment_url, stream=True)
            if resp.status_code != 200:
                print("not 200!")
                print(resp)
                print(segment_url)
                break
            for chunk in resp:
                audio_file.write(chunk)

        audio_file.flush()
        audio_file.close()
        print("Finished downloading video and audio for file %s" % output_file)

        files_map.append((output_file, audio_filename, video_filename))

    return files_map


def mix_files(files_map):
    for output_filename, audio_filename, video_filename in files_map:
        # Combine audio and video here
        print("Mixing video and audio for file %s" % output_filename)
        cmd = "ffmpeg -y -i "
        cmd += audio_filename
        cmd += " -i "
        cmd += video_filename
        cmd += " " + output_filename
        subprocess.call(cmd, shell=True)
        print("Mixing for file %s done" % output_filename)

        if not args.no_delete:
            # Delete the remaining single audio and video files
            os.remove(audio_filename)
            os.remove(video_filename)
            print("Temporary files {} and {} removed!".format(audio_filename, video_filename))


audio_video_output_map = download_files()

if not args.no_mix:
    mix_files(audio_video_output_map)
