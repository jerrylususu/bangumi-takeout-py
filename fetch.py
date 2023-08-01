import json
import time
from datetime import datetime
from pathlib import Path
import logging
import os

import requests
from tqdm import tqdm

from auth import do_auth
from mapping import ep_type
from utils import env_in_github_workflow


logging.basicConfig(level=logging.INFO)

API_SERVER = "https://api.bgm.tv"
LOAD_WAIT_MS = 5000
USERNAME_OR_UID = ""
ACCESS_TOKEN = ""
IN_GITHUB_WORKFLOW = env_in_github_workflow()


def get_json_with_bearer_token(url):
    time.sleep(LOAD_WAIT_MS/1000)
    logging.debug(f"load url: {url}")
    headers = {'Authorization': 'Bearer ' + ACCESS_TOKEN, 'accept': 'application/json', 'User-Agent': 'bangumi-takeout-python/v1'}
    response = requests.get(url, headers=headers)
    return response.json()

def load_data_until_finish(endpoint, limit=30, name="", show_progress=False):
    resp = get_json_with_bearer_token(endpoint)

    if name != "":
        logging.debug(f"loading data from {name}")

    if "total" not in resp:
        logging.debug(f"no total {name}")
        return resp

    total = resp["total"]
    logging.debug(f"{name}: total count={total}")
    items = resp["data"]

    if show_progress:
        pbar = tqdm(total=total, desc=name)
        pbar.update(len(items))

    while(len(items) < total):
        offset = len(items)
        logging.debug(f"{name}: loading from offset={offset}")
        if "?" not in endpoint:
            new_url = f"{endpoint}?limit={limit}&offset={offset}"
        else:
            new_url = f"{endpoint}&limit={limit}&offset={offset}"
        resp = get_json_with_bearer_token(new_url)
        items += resp["data"]
        if show_progress:
            pbar.update(len(resp["data"]))
    
    logging.debug(f"{name}: loaded {len(items)} items")

    if show_progress:
        pbar.close()

    return items

def load_user_collections():
    endpoint = f"{API_SERVER}/v0/users/{USERNAME_OR_UID}/collections"
    limit = 30
    collections = load_data_until_finish(endpoint, limit, "user collections", show_progress=True)
    logging.info(f"loaded {len(collections)} collections")
    with open("collections.json","w",encoding="u8") as f:
        json.dump(collections, f, ensure_ascii=False, indent=4)

    return collections


def load_subject_data_remote(item):
    logging.debug(f"loading subject data from remote server, id={item['subject_id']}")
    endpoint = f"{API_SERVER}/v0/subjects/{item['subject_id']}"
    subject_data = get_json_with_bearer_token(endpoint)
    item["subject_data"] = subject_data
    logging.debug(f"subject is {subject_data['name']}, {subject_data.get('name_cn','no cn name')}") 


def load_subject_data_local(items):
    subject_id_to_data_map = {item["subject_id"]:None for item in items}
    with open("subject.jsonlines","r",encoding="u8") as f:
        for line in tqdm(f, desc="load subject locally"):
            subject = json.loads(line)
            if subject["id"] in subject_id_to_data_map.keys():
                subject_id_to_data_map[subject["id"]] = subject
    for item in items:
        item["subject_data"] = subject_id_to_data_map[item["subject_id"]]


def load_episode_data_remote(item):
    logging.debug(f"loading episode data from remote server, id={item['subject_id']}")
    endpoint = f"{API_SERVER}/v0/episodes?subject_id={item['subject_id']}"
    item["ep_data"] = {}
    for type_key in ep_type.keys():
        # workaround: following api server spec
        if type_key not in [0,1,2,3,4,5,6]:
            continue
        ep_type_data = load_data_until_finish(f"{endpoint}&type={type_key}", limit=100, name="episode")
        item["ep_data"][type_key] = ep_type_data

def load_episode_data_local(items):
    subject_id_to_episode_map = {item["subject_id"]:{} for item in items}
    with open("episode.jsonlines","r",encoding="u8") as f:
        for line in tqdm(f, desc="load episode locally"):
            episode = json.loads(line)
            if episode["subject_id"] in subject_id_to_episode_map.keys():
                if episode["type"] not in subject_id_to_episode_map[episode["subject_id"]]:
                    subject_id_to_episode_map[episode["subject_id"]][episode["type"]] = []
                subject_id_to_episode_map[episode["subject_id"]][episode["type"]].append(episode)
    for item in items:
        item["ep_data"] = subject_id_to_episode_map[item["subject_id"]]


def load_progress_if_not_loaded(item):
    # skip existing progress
    if "progress" in item:
        return
    logging.debug(f"loading progress, id={item['subject_id']}")
    endpoint = f"{API_SERVER}/user/{USERNAME_OR_UID}/progress?subject_id={item['subject_id']}"
    item["progress"] = get_json_with_bearer_token(endpoint)

def load_user():
    global USERNAME_OR_UID

    logging.info("loading user info")
    endpoint = f"{API_SERVER}/v0/me"
    user_data = get_json_with_bearer_token(endpoint)
    USERNAME_OR_UID = user_data["username"]
    return user_data

def trigger_auth():
    global ACCESS_TOKEN

    if IN_GITHUB_WORKFLOW:
        logging.info("in Github workflow, reading from secrets")
        ACCESS_TOKEN = os.environ['BANGUMI_ACCESS_TOKEN']
        return


    if Path("./no_gui").exists():
        logging.info("no gui, skipping oauth")
    else:
        do_auth()

    if not Path("./.bgm_token").exists():
        raise Exception("no access token (auth failed?)")

    with open("./.bgm_token", "r", encoding="u8") as f:
        tokens = json.load(f)
        ACCESS_TOKEN = tokens["access_token"]
        logging.info("access token loaded")

    if not ACCESS_TOKEN:
        logging.error("ACCESS_TOKEN is empty!")
        raise Exception("need access token (auth failed?)")


def load_locally_if_possible(collections):
    if Path("./subject.jsonlines").exists() and Path("./episode.jsonlines").exists():
        logging.info("local data exists, will load from local if possible")
    else:
        logging.info("local data not exists, will load from remote")
        return

    logging.debug("load from local")
    load_subject_data_local(collections)
    load_episode_data_local(collections)

def load_remotely_for_the_rest(collections):
    for item in tqdm(collections, desc="load from remote (not exist in local)"):
        if "subject_data" in item and "ep_data" in item and item["subject_data"] is not None and item["ep_data"] is not None:
            continue
        logging.debug(f"working on {item['subject_id']}")
        if "subject_data" not in item or item["subject_data"] is None:
            load_subject_data_remote(item)
        if "ep_data" not in item or item["ep_data"] is None:
            load_episode_data_remote(item)

def copy_existing_progress_from_old_takeout(new_collection, old_takeout):
    existing_progress = {item["subject_id"]:{"progress": item["progress"], "updated_at": item["updated_at"]} 
                        for item in old_takeout["data"]}
    for item in new_collection:
        # if the progress for that subject (item) has not been updated since last fetch
        if item["subject_id"] in existing_progress and item["updated_at"] == existing_progress[item["subject_id"]]["updated_at"]:
            # just use the existing progress
            item["progress"] = existing_progress[item["subject_id"]]["progress"]

def unix_timestamp_to_datetime_str(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d-%H-%M-%S")

def load_progress_data(collections):
    if Path("takeout.json").exists():
        logging.info("takeout.json exists, will load from it")
        try:
            with open("takeout.json", "r", encoding="u8") as f:
                old_takeout = json.load(f)
            Path("takeout.json").rename(f'takeout_{unix_timestamp_to_datetime_str(old_takeout["meta"]["generated_at"])}.json')
            copy_existing_progress_from_old_takeout(collections, old_takeout)
        except json.decoder.JSONDecodeError:
            logging.info("empty takeout.json... seems to be Google Colab issue, skipping it")

    for item in tqdm(collections, desc="load view progress"):    
        load_progress_if_not_loaded(item)

def write_to_json(user, collections):
    takeout_data = {"meta": {"generated_at": time.time(), "user": user}, "data": collections}
    with open("takeout.json","w",encoding="u8") as f:
        json.dump(takeout_data, f, ensure_ascii=False, indent=4)

def main():
    trigger_auth()

    logging.info("begin fetch")

    user = load_user()
    collections = load_user_collections()
    
    load_locally_if_possible(collections)
    load_remotely_for_the_rest(collections)
    load_progress_data(collections)

    write_to_json(user, collections)

    logging.info("done")

if __name__ == "__main__":
    main()