import json
import csv
import datetime
from pathlib import Path
from math import isclose

import utils
import mapping

OFFSET_TIMEDELTA = None

def format_rate(rate):
    if rate == 0:
        return "(无评分)"
    return rate

def format_comment(comment):
    if comment is None:
        return "(无评论)"
    return comment

def write_progress_detail(item):
    utils.combine_ep_and_progress(item)

    progress_detail = {}
    for ep_type_key, ep_type_list in item["ep_data"].items():
        # skip empty ep type
        if len(ep_type_list) == 0:
            continue

        if "should_display_as_disc" in item and item["should_display_as_disc"]:
            ep_type_str = ep_type_key
        else:
            ep_type_str = mapping.ep_type[int(ep_type_key)]

        ep_type_list.sort(key=lambda x: x["sort"])

        current_ep_type_list = []
        for ep in ep_type_list:
            # 未标注
            if ep["status"] == 0:
                continue
            
            ep_sort_str = utils.ep_sort_to_str(ep["sort"])
            ep_status_text = mapping.ep_status[ep["status"]]
            ep_progress_tuple = (ep_sort_str, ep_status_text) 
            current_ep_type_list.append(ep_progress_tuple)

        progress_detail[ep_type_str] = current_ep_type_list
    
    item["progress_detail"] = progress_detail

def format_progress_finished_only(item):
    # using run-length encoding, see issue #9
    progress_detail = item["progress_detail"]
    encoded_progress_detail = {ep_type: [] for ep_type in progress_detail.keys()}
    for ep_type, ep_list in progress_detail.items():
        finished_ep_list = filter(lambda x: x[1] == "看过", ep_list)
        finished_ep_nums = list(map(lambda x: x[0], finished_ep_list))

        if len(finished_ep_nums) == 0:
            continue
        current_begin = current_end = float(finished_ep_nums[0])
        for ep_num in finished_ep_nums[1:]:
            ep_num = float(ep_num)
            if isclose(ep_num, current_end + 1):
                current_end = ep_num
            else:
                if current_begin == current_end:
                    encoded_progress_detail[ep_type].append(f"{utils.ep_sort_to_str(current_begin)}")
                    current_begin = current_end = ep_num
                else:
                    encoded_progress_detail[ep_type].append(f"{utils.ep_sort_to_str(current_begin)}-{utils.ep_sort_to_str(current_end)}")
                    current_begin = current_end = ep_num

        if current_begin == current_end:
            encoded_progress_detail[ep_type].append(f"{utils.ep_sort_to_str(current_begin)}")
        else:
            encoded_progress_detail[ep_type].append(f"{utils.ep_sort_to_str(current_begin)}-{utils.ep_sort_to_str(current_end)}")

        encoded_progress_detail[ep_type] = ",".join(encoded_progress_detail[ep_type])

    progress_string = ""
    for ep_type, ep_list in encoded_progress_detail.items():
        if len(ep_list) == 0:
            continue 
        progress_string += f"{ep_type}:{ep_list} "

    return progress_string.strip()

def build_row_dict(item):
    utils.write_progress_info(item)
    write_progress_detail(item)

    item["updated_at"] = utils.datetime_from_utc_with_offset(
        datetime.datetime.fromisoformat(item["updated_at"].strip("Z")), OFFSET_TIMEDELTA).strftime("%Y-%m-%d %H:%M:%S")

    row = {
        "名称": item["subject_data"]["name"],
        "名称(中文)": item["subject_data"].get("name_cn", ""),
        "条目类型": mapping.subject_type[item["subject_type"]],
        "地址": f'https://bgm.tv/subject/{item["subject_id"]}',
        "状态": mapping.collection_status[item["type"]],
        "最后标注": item["updated_at"],
        "完成度": f'{item["ep_status"]} | {item["main_ep_count"]}',
        "完成度(百分比)": min(100, round(100 * item["ep_status"] / item["main_ep_count"], 2)),
        "完成单集": format_progress_finished_only(item),
        "我的评分": format_rate(item["rate"]),
        "我的标签": " ".join(item["tags"]),
        "我的评论": format_comment(item["comment"]),
        # "分集详细状态": repr(item["progress_detail"])
    }
    return row


def load_takeout_json():
    with open("takeout.json","r",encoding="u8") as f:
        takeout_data = json.load(f)
    return takeout_data["meta"], takeout_data["data"]

def main(offset_hours=None):
    global OFFSET_TIMEDELTA
    if offset_hours is not None:
        OFFSET_TIMEDELTA = datetime.timedelta(hours=offset_hours)

    print("start generate csv")
    meta, data = load_takeout_json()
    generated_at_str = utils.datetime_from_utc_with_offset(datetime.datetime.utcfromtimestamp(int(meta['generated_at'])), OFFSET_TIMEDELTA).strftime("%Y-%m-%d")
    csv_file_name = f"takeout-{meta['user']['nickname']}-{generated_at_str}.csv"
    
    if Path("./no_gui").exists():
        csv_file_name = "takeout.csv"

    items = [build_row_dict(item) for item in data]

    with open(csv_file_name, "w", encoding="utf-8-sig", newline="", errors="ignore") as f:
        writer = csv.DictWriter(f, fieldnames=items[0].keys())
        writer.writeheader()
        for item in items:
            writer.writerow(item)
    
    print("done")

if __name__ == "__main__":
    main(offset_hours=None)