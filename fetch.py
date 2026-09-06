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
IN_GITHUB_WORKFLOW = env_in_github_workflow()

# Cache (a.k.a. resume checkpoint) of already-fetched heavy data for the current
# run. It is written as items are enriched and deleted once a run succeeds, so it
# only ever represents an interrupted run that can be resumed.
CACHE_FILENAME = "resume.json"
COLLECTIONS_FILENAME = "collections.json"


class BangumiApiService:
    def __init__(self, access_token, api_server=API_SERVER, load_wait_ms=LOAD_WAIT_MS):
        self.access_token = access_token
        self.api_server = api_server.rstrip("/")
        self.load_wait_ms = load_wait_ms
        self.headers = {
            'Authorization': 'Bearer ' + access_token,
            'accept': 'application/json',
            'User-Agent': 'bangumi-takeout-python/v1',
        }

    def _get_json(self, url, params=None):
        time.sleep(self.load_wait_ms/1000)
        logging.debug(f"load url: {url}")
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def get_me(self):
        return self._get_json(f"{self.api_server}/v0/me")

    def get_user_collections_page(self, username, offset=0, limit=30):
        return self._get_json(
            f"{self.api_server}/v0/users/{username}/collections",
            {"limit": limit, "offset": offset},
        )

    def get_subject(self, subject_id):
        return self._get_json(f"{self.api_server}/v0/subjects/{subject_id}")

    def get_episodes_page(self, subject_id, type_key, offset=0, limit=100):
        return self._get_json(
            f"{self.api_server}/v0/episodes",
            {"subject_id": subject_id, "type": type_key, "limit": limit, "offset": offset},
        )

    def get_user_progress(self, username, subject_id):
        return self._get_json(
            f"{self.api_server}/user/{username}/progress",
            {"subject_id": subject_id},
        )


def trigger_auth():
    if IN_GITHUB_WORKFLOW:
        logging.info("in Github workflow, reading from secrets")
        return os.environ['BANGUMI_ACCESS_TOKEN']

    if Path("./no_gui").exists():
        logging.info("no gui, skipping oauth")
    else:
        do_auth()

    if not Path("./.bgm_token").exists():
        raise Exception("no access token (auth failed?)")

    with open("./.bgm_token", "r", encoding="u8") as f:
        tokens = json.load(f)
        access_token = tokens["access_token"]
        logging.info("access token loaded")

    if not access_token:
        logging.error("ACCESS_TOKEN is empty!")
        raise Exception("need access token (auth failed?)")

    return access_token


def fetch_user_collections(service, username, limit=30):
    """Always fetch the *current* collections list from the API.

    The list is the source of truth for what belongs in the takeout. Resume
    state (resume.json) only caches heavy per-item data and is merged
    against this freshly fetched list, so items added/removed/changed since an
    interrupted run are never lost.
    """
    logging.info(f"fetching current collections list for {username}")
    page = service.get_user_collections_page(username, offset=0, limit=limit)
    if "total" not in page or "data" not in page:
        raise RuntimeError(f"unexpected collections response (no total/data): {page}")

    total = page["total"]
    items = page["data"]

    pbar = tqdm(total=total, desc="user collections")
    pbar.update(len(items))

    while len(items) < total:
        offset = len(items)
        logging.debug(f"loading collections from offset={offset}")
        page = service.get_user_collections_page(username, offset=offset, limit=limit)
        items += page["data"]
        pbar.update(len(page["data"]))

    pbar.close()
    logging.info(f"fetched {len(items)} collections")
    with open(COLLECTIONS_FILENAME, "w", encoding="u8") as f:
        json.dump(items, f, ensure_ascii=False, indent=4)

    return items


def fetch_episode_type(service, subject_id, type_key, limit=100):
    """Fetch all episodes of a subject of a given type. Returns a list.

    Returns None if the request is invalid (the API answers without `total`),
    in which case the caller simply won't store that type at all.
    """
    page = service.get_episodes_page(subject_id, type_key, offset=0, limit=limit)
    if "total" not in page or "data" not in page:
        return None

    total = page["total"]
    items = page["data"]
    while len(items) < total:
        offset = len(items)
        page = service.get_episodes_page(subject_id, type_key, offset=offset, limit=limit)
        items += page["data"]
    return items


def fetch_episode_data(service, subject_id):
    ep_data = {}
    for type_key in ep_type:
        episodes = fetch_episode_type(service, subject_id, type_key)
        if episodes is not None:
            ep_data[type_key] = episodes
    return ep_data


def merge_fresh_with_cache(fresh_items, cached_items):
    """Merge the freshly fetched collections list with cached (enriched) items.

    Output is driven by the fresh list: new collections are appended, removed
    ones drop out. Heavy per-item data (subject_data / ep_data / progress) is
    only reused from the cache when the collection entry itself is unchanged
    since it was fetched (subject_id and updated_at both match).
    """
    cached = {}
    for it in cached_items:
        if isinstance(it, dict) and it.get("subject_id") is not None:
            cached[it["subject_id"]] = it

    merged = []
    for entry in fresh_items:
        item = dict(entry)
        prior = cached.get(item["subject_id"])
        if prior is not None and prior.get("updated_at") == item.get("updated_at"):
            for key in ("subject_data", "ep_data", "progress"):
                value = prior.get(key)
                if value is not None:
                    item[key] = value
        merged.append(item)
    return merged


def _fill_subject_data_from_local(items):
    pending = [it for it in items if it.get("subject_data") is None]
    if not pending:
        return
    need = {it["subject_id"] for it in pending}
    found = {}
    with open("subject.jsonlines", "r", encoding="u8") as f:
        for line in tqdm(f, desc="load subject locally"):
            subject = json.loads(line)
            if subject["id"] in need:
                found[subject["id"]] = subject
                need.discard(subject["id"])
                if not need:
                    break
    for item in pending:
        if item["subject_id"] in found:
            item["subject_data"] = found[item["subject_id"]]


def _fill_episode_data_from_local(items):
    pending = [it for it in items if it.get("ep_data") is None]
    if not pending:
        return
    need = {it["subject_id"] for it in pending}
    found = {}
    with open("episode.jsonlines", "r", encoding="u8") as f:
        for line in tqdm(f, desc="load episode locally"):
            episode = json.loads(line)
            subject_id = episode["subject_id"]
            if subject_id in need:
                by_type = found.setdefault(subject_id, {})
                by_type.setdefault(episode["type"], []).append(episode)
    for item in pending:
        subject_id = item["subject_id"]
        item["ep_data"] = found.get(subject_id, {})


def fill_subject_and_ep_data(service, items, save_checkpoint=None):
    """Enrich every item with subject_data and ep_data (from local archive if
    available, otherwise from the remote API), checkpointing after each item so
    an interrupted run can resume without re-fetching everything.
    """
    if Path("subject.jsonlines").exists() and Path("episode.jsonlines").exists():
        logging.info("local data exists, will load from local if possible")
        _fill_subject_data_from_local(items)
        _fill_episode_data_from_local(items)
        if save_checkpoint:
            save_checkpoint()

    for item in tqdm(items, desc="load subject & episode data (missing)"):
        need_change = False
        if item.get("subject_data") is None:
            item["subject_data"] = service.get_subject(item["subject_id"])
            need_change = True
        if item.get("ep_data") is None:
            item["ep_data"] = fetch_episode_data(service, item["subject_id"])
            need_change = True
        if need_change and save_checkpoint:
            save_checkpoint()


def load_old_takeout_items():
    """Items of the last successfully generated takeout.json, if present."""
    if not Path("takeout.json").exists():
        return []
    try:
        with open("takeout.json", "r", encoding="u8") as f:
            old_takeout = json.load(f)
    except json.decoder.JSONDecodeError:
        logging.info("empty takeout.json... seems to be Google Colab issue, skipping it")
        return []
    return old_takeout.get("data", [])


def copy_progress_from_sources(items, sources):
    """Reuse progress for entries unchanged since a previous snapshot.

    For each item still lacking `progress`, look it up in `sources` (a list of
    prior item snapshots, e.g. the last takeout and the resume cache). Progress
    is copied only when the collection's updated_at is unchanged; otherwise the
    item is returned as still pending a fresh fetch.
    """
    known = {}
    for source in sources:
        for it in source:
            if not isinstance(it, dict):
                continue
            if it.get("progress") is not None:
                known[it["subject_id"]] = (it.get("updated_at"), it["progress"])

    pending = []
    for item in items:
        if item.get("progress") is not None:
            continue
        old = known.get(item["subject_id"])
        if old is not None and old[0] == item.get("updated_at"):
            item["progress"] = old[1]
        else:
            pending.append(item)
    return pending


def load_progress_data(service, username, items, cached_items, save_checkpoint=None):
    old_items = load_old_takeout_items()
    # the resume cache (more recent) takes precedence over the previous takeout
    pending = copy_progress_from_sources(items, sources=[old_items, cached_items])
    logging.info(
        f"view progress: {len(items) - len(pending)} reused, {len(pending)} to fetch"
    )

    for item in tqdm(pending, desc="load view progress"):
        logging.debug(f"loading progress, id={item['subject_id']}")
        item["progress"] = service.get_user_progress(username, item["subject_id"])
        if save_checkpoint:
            save_checkpoint()


def unix_timestamp_to_datetime_str(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d-%H-%M-%S")


def load_cache(username):
    """Read the resume cache, returning the list of previously enriched items."""
    if not Path(CACHE_FILENAME).exists():
        return []
    try:
        with open(CACHE_FILENAME, "r", encoding="u8") as f:
            cache = json.load(f)
    except json.decoder.JSONDecodeError:
        logging.info("cache file corrupted, starting a fresh run")
        return []

    if isinstance(cache, list):
        return cache
    if isinstance(cache, dict):
        if username is not None and cache.get("user") not in (None, username):
            logging.info("cache belongs to a different user, starting a fresh run")
            return []
        return cache.get("items", [])
    return []


def save_cache(items, username=None):
    """Write the resume cache atomically (avoids a torn file on interruption)."""
    payload = {"user": username, "items": items}
    tmp_path = CACHE_FILENAME + ".tmp"
    with open(tmp_path, "w", encoding="u8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp_path, CACHE_FILENAME)


def remove_cache():
    try:
        Path(CACHE_FILENAME).unlink()
    except FileNotFoundError:
        pass


def write_takeout(user, items):
    # keep a dated copy of the previous takeout (per-run history), like before
    if Path("takeout.json").exists():
        try:
            with open("takeout.json", "r", encoding="u8") as f:
                old_takeout = json.load(f)
            Path("takeout.json").rename(
                f'takeout_{unix_timestamp_to_datetime_str(old_takeout["meta"]["generated_at"])}.json'
            )
        except (json.decoder.JSONDecodeError, KeyError):
            logging.info("previous takeout.json is unreadable, overwriting it")

    takeout_data = {"meta": {"generated_at": time.time(), "user": user}, "data": items}
    with open("takeout.json", "w", encoding="u8") as f:
        json.dump(takeout_data, f, ensure_ascii=False, indent=4)


def main():
    access_token = trigger_auth()
    service = BangumiApiService(access_token)

    logging.info("begin fetch")

    user = service.get_me()
    username = user["username"]

    cached_items = load_cache(username)
    if cached_items:
        logging.info(
            f"resuming interrupted run: {len(cached_items)} cached item(s) found"
        )
    else:
        logging.info("no usable cache, starting a fresh run")

    # First re-check: the collections list is always re-fetched, so data that
    # changed since an interrupted run (new/deleted/modified collections) is
    # reflected in the output instead of being silently dropped.
    collections = fetch_user_collections(service, username)
    items = merge_fresh_with_cache(collections, cached_items)

    def checkpoint():
        save_cache(items, username)

    save_cache(items, username)

    fill_subject_and_ep_data(service, items, save_checkpoint=checkpoint)
    load_progress_data(service, username, items, cached_items, save_checkpoint=checkpoint)

    write_takeout(user, items)
    remove_cache()

    logging.info("done")


if __name__ == "__main__":
    main()
