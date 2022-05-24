import time
import datetime

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
def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.datetime.fromtimestamp(now_timestamp) - datetime.datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset