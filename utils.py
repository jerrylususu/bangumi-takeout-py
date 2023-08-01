import time
import datetime
from math import isclose
import requests
import os

# 写入进度信息（用于完成度计算）
def write_progress_info(item):
    # books -> vol, anime -> ep
    item["ep_status"] = max([item["ep_status"], item["vol_status"]])

    # determine number of main episodes (used to calculate progress percentage)
    item["main_ep_count"] = 0
    if "eps" in item["subject_data"]:
      # api server has this
      item["main_ep_count"] = item["subject_data"]["eps"]
    else:
      # local archive doesn't
      if "ep_data" in item and "0" in item["ep_data"]:
        item["main_ep_count"] = len(item["ep_data"]["0"])

    if item["main_ep_count"] == 0:
        if "volumes" in item["subject_data"] and "total_episodes" in item["subject_data"]:
          item["main_ep_count"] = max([item["subject_data"]["volumes"], item["subject_data"]["total_episodes"]])
    if item["main_ep_count"] == 0:
        # no data
        item["main_ep_count"] = 1
    item["finish_percentage"] = min(100, round(100 * item["ep_status"] / item["main_ep_count"], 2))

# https://stackoverflow.com/questions/4770297/convert-utc-datetime-string-to-local-datetime
def datetime_from_utc_with_offset(utc_datetime, offset: datetime.timedelta=None):
    if offset is None:
        now_timestamp = time.time()
        offset = datetime.datetime.fromtimestamp(now_timestamp) - datetime.datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset


def remove_response_of_invalid_request(item):
    to_be_deteleted = []
    for ep_type_key, ep_type_list in item["ep_data"].items():
        if type(ep_type_list) is dict:
            # invalid request
            to_be_deteleted.append(ep_type_key)
    for key in to_be_deteleted:
        del item["ep_data"][key]


def build_ep_id_to_addr_map(item):
    ep_id_to_addr_map = {}
    for ep_type_key, ep_type_list in item["ep_data"].items():
        for idx, ep in enumerate(ep_type_list):
            ep_id_to_addr_map[ep["id"]] = (ep_type_key,idx)
            ep["status"] = 0

    if "progress" in item and item["progress"] is not None:
        for watch_status in item["progress"]["eps"]:
            ep_id = watch_status["id"]

            # workaround of issue #1: strange data inconsistency, some ep in progress but not in ep_data
            if ep_id not in ep_id_to_addr_map:
                print("skipped ep_id {}".format(ep_id))
                continue
            ep_type_key, idx = ep_id_to_addr_map[ep_id]
            item["ep_data"][ep_type_key][idx]["status"] = watch_status["status"]["id"]
    
    item["ep_id_to_addr_map"] = ep_id_to_addr_map


def rebuild_ep_type_list_for_music(item):
    # check: not music
    if item["subject_type"] != 3:
        return

    # check: has multiple disc?
    if all([ep["disc"] == 0 for ep_list in item["ep_data"].values() for ep in ep_list]):
        return

    # is music, should use "disc" attribute to classify
    new_ep_type_dict = {}
    for ep_type, ep_list in item["ep_data"].items():
        for ep in ep_list:
            ep_disc_str = f"Disc {ep['disc']}"
            if ep_disc_str not in new_ep_type_dict:
                new_ep_type_dict[ep_disc_str] = []
            new_ep_type_dict[ep_disc_str].append(ep)
    
    item["ep_data"] = new_ep_type_dict
    item["should_display_as_disc"] = True

def ep_sort_to_str(ep_sort):
    # 1.0 -> 1, 13.5 -> 13.5
    if isclose(int(ep_sort), ep_sort):
        return str(int(ep_sort))
    else:
        return str(ep_sort)

def combine_ep_and_progress(item): 
    remove_response_of_invalid_request(item)
    build_ep_id_to_addr_map(item)
    rebuild_ep_type_list_for_music(item)

def get_newest_archive():
    url = f"https://api.github.com/repos/bangumi/Archive/releases/tags/archive"
    response = requests.get(url)
    release = response.json()

    # Find the asset with the newest date
    newest_asset = max(release["assets"], key=lambda asset: asset["created_at"])

    # Print the asset name and download URL
    asset_name = newest_asset["name"]
    asset_download_url = newest_asset["browser_download_url"]
    return asset_download_url

def env_in_github_workflow():
    return os.environ.get('GITHUB_ACTIONS') == 'true'


if env_in_github_workflow():
    print(get_newest_archive())