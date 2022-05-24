import json
import csv
from datetime import datetime

import utils
import mapping

def format_rate(rate):
    if rate == 0:
        return "(无评分)"
    return rate

def format_comment(comment):
    if comment is None:
        return "(无评论)"
    return comment

def build_row_dict(item):
    utils.write_progress_info(item)
    row = {
        "名称": item["subject_data"]["name"],
        "名称(中文)": item["subject_data"].get("name_cn", ""),
        "条目类型": mapping.subject_type[item["subject_type"]],
        "地址": f'https://bgm.tv/subject/{item["subject_id"]}',
        "状态": mapping.collection_status[item["type"]],
        "最后标注": item["updated_at"],
        "完成度": f'{item["ep_status"]} | {item["main_ep_count"]}',
        "完成度(百分比)": min(100, round(100 * item["ep_status"] / item["main_ep_count"], 2)),
        "我的评分": format_rate(item["rate"]),
        "我的标签": " ".join(item["tags"]),
        "我的评论": format_comment(item["comment"]),
    }
    return row


def load_takeout_json():
    with open("takeout.json","r",encoding="u8") as f:
        takeout_data = json.load(f)
    return takeout_data["meta"], takeout_data["data"]

def main():
    print("start generate csv")
    meta, data = load_takeout_json()
    generated_at_str = utils.datetime_from_utc_to_local(datetime.utcfromtimestamp(int(meta['generated_at']))).strftime("%Y-%m-%d")
    csv_file_name = f"takeout-{meta['user']['nickname']}-{generated_at_str}.csv"
    
    items = [build_row_dict(item) for item in data]

    with open(csv_file_name, "w", newline="", errors="ignore") as f:
        writer = csv.DictWriter(f, fieldnames=items[0].keys())
        writer.writeheader()
        for item in items:
            writer.writerow(item)
    
    print("done")

if __name__ == "__main__":
    main()