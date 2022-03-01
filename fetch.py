import json
import requests
from time import sleep
import time
from tqdm import tqdm
from mapping import ep_type

# CHANGE THIS!!!
ACCESS_TOKEN = ""
#####################################


API_SERVER = "https://api.bgm.tv"
LOAD_WAIT_MS = 200
USERNAME_OR_UID = ""

def get_json_with_bearer_token(url):
    sleep(LOAD_WAIT_MS/1000)
    # print("load url", url)
    headers = {'Authorization': 'Bearer ' + ACCESS_TOKEN, 'accept': 'application/json', 'client': 'bangumi-takeout-python'}
    response = requests.get(url, headers=headers)
    return response.json()

def load_data_until_finish(endpoint, limit=30, name=""):
    resp = get_json_with_bearer_token(endpoint)

    if name != "":
        print("loading data from", name)

    if "total" not in resp:
        print("no total", name)
        return resp

    total = resp["total"]
    print(f"{name}: total count={total}")
    items = resp["data"]

    while(len(items) < total):
        offset = len(items)
        print(f"{name}: loading from offset={offset}")
        if "?" not in endpoint:
            new_url = f"{endpoint}?limit={limit}&offset={offset}"
        else:
            new_url = f"{endpoint}&limit={limit}&offset={offset}"
        resp = get_json_with_bearer_token(new_url)
        items += resp["data"]
    
    print(f"{name}: loaded", len(items), "items")
    return items

def load_user_collections():
    endpoint = f"{API_SERVER}/v0/users/{USERNAME_OR_UID}/collections"
    limit = 30
    collections = load_data_until_finish(endpoint, limit, "user collections")
    print("loaded", len(collections), "collections")
    with open("collections.json","w",encoding="u8") as f:
        json.dump(collections, f, ensure_ascii=False, indent=4)
    print("saved collections")

    return collections


def load_subject_data(item):
    print("loading subject data, id=", item["subject_id"])
    endpoint = f"{API_SERVER}/v0/subjects/{item['subject_id']}"
    subject_data = get_json_with_bearer_token(endpoint)
    item["subject_data"] = subject_data
    print(f"subject is {subject_data['name']}, {subject_data.get('name_cn','no cn name')}") 

def load_episode_data(item):
    print("loading episode data, id=", item["subject_id"])
    endpoint = f"{API_SERVER}/v0/episodes?subject_id={item['subject_id']}"
    item["ep_data"] = {}
    for type_key in ep_type.keys():
        ep_type_data = load_data_until_finish(f"{endpoint}&type={type_key}", limit=100, name="episode")
        item["ep_data"][type_key] = ep_type_data

def load_progress(item):
    print("loading progress, id=", item["subject_id"])
    endpoint = f"{API_SERVER}/user/{USERNAME_OR_UID}/progress?subject_id={item['subject_id']}"
    item["progress"] = get_json_with_bearer_token(endpoint)

def load_user():
    global USERNAME_OR_UID

    print("loading user")
    endpoint = f"{API_SERVER}/v0/me"
    user_data = get_json_with_bearer_token(endpoint)
    USERNAME_OR_UID = user_data["username"]
    return user_data

def main():
    if ACCESS_TOKEN == "":
        raise Exception("need access token")

    print("begin fetch")
    user = load_user()
    collections = load_user_collections()
    for item in tqdm(collections, position=0, leave=True):
        print(f"working on {item['subject_id']}")
        load_subject_data(item)
        load_episode_data(item)
        load_progress(item)
    takeout_data = {"meta": {"generated_at": time.time(), "user": user}, "data": collections}
    with open("takeout.json","w",encoding="u8") as f:
        json.dump(takeout_data, f, ensure_ascii=False, indent=4)
    print("done")

if __name__ == "__main__":
    main()