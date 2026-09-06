"""Offline tests for fetch.py.

No network access is used: network requests are replaced by a FakeService that
implements the same interface as BangumiApiService but returns canned payloads.
"""
import json

import pytest

import fetch


def collection_entry(subject_id, updated_at="2024-01-01T00:00:00Z", **extra):
    base = {
        "subject_id": subject_id,
        "subject_type": 2,
        "rate": 0,
        "type": 1,
        "comment": "",
        "tags": [],
        "ep_status": 0,
        "vol_status": 0,
        "updated_at": updated_at,
        "private": False,
    }
    base.update(extra)
    return base


def subject_payload(subject_id):
    return {"id": subject_id, "name": f"subject-{subject_id}", "name_cn": "", "eps": 12}


def episode_payload(subject_id, ep_type, count=3):
    return [
        {"id": subject_id * 100 + ep_type * 10 + i, "subject_id": subject_id, "type": ep_type, "sort": i + 1}
        for i in range(count)
    ]


def progress_payload(subject_id):
    return {"subject_id": subject_id, "updated_at": 1, "eps": []}


def enriched(sid, updated_at, with_progress=True):
    item = collection_entry(sid, updated_at)
    item["subject_data"] = subject_payload(sid)
    item["ep_data"] = {"0": episode_payload(sid, 0)}
    if with_progress:
        item["progress"] = progress_payload(sid)
    return item


class FakeService:
    """Implements the BangumiApiService interface with in-memory data."""

    def __init__(self, collections=None, subjects=None, episodes=None, progresses=None):
        self.collections = collections or []
        self.subjects = subjects or {}
        self.episodes = episodes or {}  # subject_id -> {ep_type: [ep, ...]}
        self.progresses = progresses or {}
        self.calls = {"subject": [], "episode": [], "progress": [], "collections": []}

    def get_user_collections_page(self, username, offset=0, limit=30):
        self.calls["collections"].append(offset)
        data = self.collections[offset : offset + limit]
        return {"total": len(self.collections), "limit": limit, "offset": offset, "data": data}

    def get_subject(self, subject_id):
        self.calls["subject"].append(subject_id)
        if subject_id not in self.subjects:
            raise AssertionError(f"unexpected get_subject call for {subject_id}")
        return self.subjects[subject_id]

    def get_episodes_page(self, subject_id, ep_type, offset=0, limit=100):
        self.calls["episode"].append((subject_id, ep_type))
        items = self.episodes.get(subject_id, {}).get(ep_type, [])
        data = items[offset : offset + limit]
        return {"total": len(items), "limit": limit, "offset": offset, "data": data}

    def get_user_progress(self, username, subject_id):
        self.calls["progress"].append(subject_id)
        if subject_id not in self.progresses:
            raise AssertionError(f"unexpected get_user_progress call for {subject_id}")
        return self.progresses[subject_id]


# --------------------------------------------------------------------------- #
# merge_fresh_with_cache
# --------------------------------------------------------------------------- #


def test_merge_reuses_heavy_data_only_for_unchanged_entries():
    a = enriched(1, "2024-01-01T00:00:00Z")
    cached = [a]

    # fresh list: same entry (unchanged) + a brand new one
    fresh = [collection_entry(1, "2024-01-01T00:00:00Z"), collection_entry(2, "2024-01-02T00:00:00Z")]
    merged = fetch.merge_fresh_with_cache(fresh, cached)

    assert len(merged) == 2
    assert merged[0]["subject_id"] == 1
    assert merged[0]["subject_data"] == a["subject_data"]
    assert merged[0]["ep_data"] == a["ep_data"]
    assert merged[0]["progress"] == a["progress"]
    # the new entry carries no cached heavy data yet
    assert merged[1]["subject_id"] == 2
    assert "subject_data" not in merged[1]
    assert "ep_data" not in merged[1]
    assert "progress" not in merged[1]


def test_merge_drops_entries_removed_from_collections():
    cached = [enriched(1, "t"), enriched(2, "t")]
    fresh = [collection_entry(1, "t")]
    merged = fetch.merge_fresh_with_cache(fresh, cached)
    assert [it["subject_id"] for it in merged] == [1]


def test_merge_refetches_when_updated_at_changed():
    cached = [enriched(1, "2024-01-01T00:00:00Z")]
    # collection entry was modified between the interrupted run and now
    fresh = [collection_entry(1, "2024-01-02T00:00:00Z")]
    merged = fetch.merge_fresh_with_cache(fresh, cached)
    assert len(merged) == 1
    assert merged[0]["subject_id"] == 1
    assert "subject_data" not in merged[0]
    assert "ep_data" not in merged[0]
    assert "progress" not in merged[0]


def test_merge_tolerates_noisy_cache():
    cached = [None, {"subject_id": 1, "updated_at": "t", "subject_data": {}}, "junk"]
    fresh = [collection_entry(1, "t")]
    merged = fetch.merge_fresh_with_cache(fresh, cached)
    assert len(merged) == 1
    assert merged[0]["subject_data"] == {}


# --------------------------------------------------------------------------- #
# copy_progress_from_sources
# --------------------------------------------------------------------------- #


def _entry_with_progress(sid, updated_at):
    it = collection_entry(sid, updated_at)
    it["progress"] = progress_payload(sid)
    return it


def test_copy_progress_from_previous_takeout():
    old = [_entry_with_progress(1, "t1"), _entry_with_progress(5, "old")]
    cache = [
        # 5 was fetched again during the interrupted run with a newer updated_at,
        # so the cache (later snapshot) must win over the previous takeout
        _entry_with_progress(5, "newer"),
        # 3 is in the cache but changed since -> must be re-fetched
        _entry_with_progress(3, "t1"),
    ]

    # 1 unchanged vs old takeout; 5 unchanged vs cache; 3 changed since cache
    items = [
        collection_entry(1, "t1"),
        collection_entry(5, "newer"),
        collection_entry(3, "newer2"),
    ]
    pending = fetch.copy_progress_from_sources(items, sources=[old, cache])

    assert [it["subject_id"] for it in pending] == [3]
    assert items[0]["progress"] == old[0]["progress"]
    assert items[1]["progress"] == cache[0]["progress"]


def test_copy_progress_pending_on_change_and_new_items():
    old = [_entry_with_progress(1, "t1")]
    items = [collection_entry(1, "changed"), collection_entry(2, "t2")]
    pending = fetch.copy_progress_from_sources(items, sources=[old])
    assert [it["subject_id"] for it in pending] == [1, 2]
    assert "progress" not in items[0]
    assert "progress" not in items[1]


# --------------------------------------------------------------------------- #
# resume across t1 (interrupted) -> t3 (re-run): no lost subscriptions
# --------------------------------------------------------------------------- #


@pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_resume_picks_up_new_collections_added_between_runs(tmp_cwd):
    # t1: run 1 fetched entries 1 and 2, fully enriched, then got interrupted.
    cached = [enriched(1, "2024-01-01T00:00:00Z"), enriched(2, "2024-01-01T00:00:00Z")]

    # t3: a day later the user added a new collection (subject 3).
    fresh_t3 = [
        collection_entry(1, "2024-01-01T00:00:00Z"),
        collection_entry(2, "2024-01-01T00:00:00Z"),
        collection_entry(3, "2024-01-02T00:00:00Z"),
    ]

    service = FakeService(
        collections=fresh_t3,
        subjects={3: subject_payload(3)},
        episodes={3: {"0": episode_payload(3, 0)}},
        progresses={3: progress_payload(3)},
    )

    items = fetch.merge_fresh_with_cache(service.collections, cached)
    checkpoints = []
    fetch.fill_subject_and_ep_data(service, items, save_checkpoint=lambda: checkpoints.append(1))
    fetch.load_progress_data(service, "user", items, cached, save_checkpoint=lambda: checkpoints.append(1))

    assert [it["subject_id"] for it in items] == [1, 2, 3]
    # entries 1 & 2 were reused from cache, not re-fetched
    assert items[0]["subject_data"]["id"] == 1
    assert items[2]["subject_data"]["id"] == 3
    assert service.calls["subject"] == [3]
    assert (3, 0) in service.calls["episode"]
    assert service.calls["progress"] == [3]
    assert checkpoints


def test_resume_refetches_changed_and_drops_removed(tmp_cwd):
    cached = [enriched(1, "2024-01-01T00:00:00Z"), enriched(2, "2024-01-01T00:00:00Z")]

    # subject 1 changed, subject 2 was removed from the user's collection
    fresh = [collection_entry(1, "2024-01-03T00:00:00Z")]
    service = FakeService(
        collections=fresh,
        subjects={1: subject_payload(1)},
        episodes={1: {"0": episode_payload(1, 0)}},
        progresses={1: progress_payload(1)},
    )

    items = fetch.merge_fresh_with_cache(fresh, cached)
    fetch.fill_subject_and_ep_data(service, items)
    fetch.load_progress_data(service, "user", items, cached)

    assert [it["subject_id"] for it in items] == [1]
    assert service.calls["subject"] == [1]
    assert service.calls["progress"] == [1]


# --------------------------------------------------------------------------- #
# fetch_user_collections pagination
# --------------------------------------------------------------------------- #


def test_fetch_user_collections_paginates(tmp_cwd):
    data = [collection_entry(i, "t") for i in range(75)]
    service = FakeService(collections=data)

    result = fetch.fetch_user_collections(service, "user", limit=30)

    assert result == data
    assert service.calls["collections"] == [0, 30, 60]
    # intermediate collections.json dump is written (original behaviour)
    with open(fetch.COLLECTIONS_FILENAME, encoding="u8") as f:
        assert json.load(f) == data


# --------------------------------------------------------------------------- #
# cache file round-trip
# --------------------------------------------------------------------------- #


def test_cache_round_trip_and_user_guard(tmp_cwd):
    items = [enriched(1, "t")]
    fetch.save_cache(items, username="alice")

    assert fetch.load_cache("alice") == items
    # a different account resuming must not reuse the cache
    assert fetch.load_cache("bob") == []

    fetch.remove_cache()
    assert fetch.load_cache("alice") == []


def test_cache_corrupted_file_starts_fresh(tmp_cwd):
    with open(fetch.CACHE_FILENAME, "w", encoding="u8") as f:
        f.write("{not json")
    assert fetch.load_cache("alice") == []


# --------------------------------------------------------------------------- #
# enrichment: local archive first, remote for the rest
# --------------------------------------------------------------------------- #


def _write_local_archive(sid, ep_types):
    with open("subject.jsonlines", "w", encoding="u8") as f:
        f.write(json.dumps(subject_payload(sid)) + "\n")
    with open("episode.jsonlines", "w", encoding="u8") as f:
        for et in ep_types:
            for ep in episode_payload(sid, et):
                f.write(json.dumps(ep) + "\n")


def test_fill_from_local_then_remote(tmp_cwd):
    # subject 1 exists in the local archive, subject 2 must come from the API
    _write_local_archive(1, ep_types=[0])

    items = [collection_entry(1, "t"), collection_entry(2, "t")]
    service = FakeService(
        collections=items,
        subjects={2: subject_payload(2)},
        episodes={2: {"0": episode_payload(2, 0)}},
        progresses={},
    )

    fetch.fill_subject_and_ep_data(service, items)

    assert items[0]["subject_data"]["id"] == 1
    assert items[0]["ep_data"][0][0]["id"] == 1 * 100 + 0 * 10
    assert items[1]["subject_data"]["id"] == 2
    assert service.calls["subject"] == [2]
