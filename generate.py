
import enum
import json
import datetime
import mapping
import time


html_start = """<!doctype html>
<html lang="zh-cn">

<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

  <title>Bangumi Takeout</title>
  <!-- Bootstrap core CSS -->
  <link href="https://cdn.bootcdn.net/ajax/libs/twitter-bootstrap/4.6.1/css/bootstrap.min.css" rel="stylesheet">

  <style>
    .bangumi-link {
      background-color: #f09199; 
      color: white; 
    }
    .ep-detail-div {
      line-height: 300%;
    }
  </style>
</head>

<body>

  <main role="main" class="container">
"""

html_end = """
  </main>

  <script src="https://cdn.bootcdn.net/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
  <script src="https://cdn.bootcdn.net/ajax/libs/twitter-bootstrap/4.6.1/js/bootstrap.bundle.min.js"></script>
  <script>
    $(function () {
        $('[data-toggle="tooltip"]').tooltip()
    })
    $('#toggle-all-collapse').click(function () {
        document.querySelectorAll('.card-body').forEach((it) => {
            it.classList.toggle('collapse')
        })
    });
  </script>
</body>

</html>"""


html_header = """<h1>Bangumi Takeout</h1>
    <p>使用 <a href="https://github.com/jerrylususu/bangumi-takeout-py" target="_blank">Bangumi Takeout</a> 为用户 <a href="https://bgm.tv/user/{user_id}" target="_blank">{username}</a> 于 {generated_at} 生成</p>
    <p>类型统计：
      {html_type_summary}
    </p>
    <p>状态统计： 
      {html_status_summary}
    </p>
    <p>分集图例：
      {html_ep_status_example}
    </p>
    <button type="button" class="btn btn-outline-secondary" id="toggle-all-collapse"> 全部展开/收起 </button>
    <hr>
"""

html_summary_button = """
      <button type="button" class="btn btn-{color}"> {name} <span class="badge badge-light">{count}</span></button>
"""

html_ep_status_example = """
<a href="#" class="btn btn-{color} btn-sm">{name}</a>
"""

html_card = """
    <div class="card mb-2">
      <div class="card-header" data-toggle="collapse" href="#card-body-subject-{subject_id}" aria-expanded="true" aria-controls="test-block" >
        {name_cn} <span class="badge badge-{subject_status_color}">{subject_status_str}</span>
      </div>
      <div class="card-body collapse" id="card-body-subject-{subject_id}">
        <h5 class="card-title">{name} <small>{name_cn}</small></h5>

        <a class="btn bangumi-link" href="https://bgm.tv/subject/{subject_id}"  target="_blank">Bangumi 条目链接</a>

        <dl class="row">
          <dt class="col-sm-2">最后更新于</dt>
          <dd class="col-sm-10">{updated_at}</dd>
          <dt class="col-sm-2">我的评分</dt>
          <dd class="col-sm-10">{rate}</dd>

          <dt class="col-sm-2">我的评论</dt>
          <dd class="col-sm-10">
            {comment}
          </dd>

          <dt class="col-sm-2">我的标签</dt>
          <dd class="col-sm-10">
            {html_tag}
          </dd>

          <dt class="col-sm-2">完成度</dt>
          <dd class="col-sm-10">
            <div class="progress">
              <div class="progress-bar" role="progressbar" style="width: {finish_percentage}%" aria-valuenow="{finish_percentage}" aria-valuemin="0"
                aria-valuemax="100"> {ep_status} / {main_ep_count} </div>
            </div>
          </dd>

          <dt class="col-sm-2 align-self-center">分集状态</dt>
          <dd class="col-sm-10 ep-detail-div">
            {html_ep_detail}
          </dd>
        </dl>



      </div>
    </div>
"""


html_ep_type_name = """<span class="font-weight-bold">{ep_type_str}</span>"""
html_ep_button = """
<a class="btn btn-{ep_status_color}" data-toggle="tooltip" data-placement="bottom" data-html="true"
    href="https://bgm.tv/ep/{ep_id}" target="_blank"
    title="ep.{ep_sort_str} {name} <br> 中文:{name_cn} <br> 首播:{airdate} <br>时长:{duration}">
    {ep_sort_str}</a> 
"""

html_type_begin = """<h2>{type_name}</h2>"""


def load_takeout_json():
    with open("takeout.json","r",encoding="u8") as f:
        takeout_data = json.load(f)
    return takeout_data["meta"], takeout_data["data"]


def build_summary(type_name_to_list_map, name_map, color_map):
    summary_html = ""
    for type_key, li in type_name_to_list_map.items():
        summary_html += html_summary_button.format(name=name_map[type_key], count=len(li), color=color_map[type_key])
    return summary_html

# https://stackoverflow.com/questions/4770297/convert-utc-datetime-string-to-local-datetime
def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.datetime.fromtimestamp(now_timestamp) - datetime.datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset

def build_ep_status_example():
    html = ""
    for status_key, status_name in mapping.ep_status.items():
        html += html_ep_status_example.format(color=mapping.ep_color[status_key], name=mapping.ep_status[status_key])
    return html

def build_header(meta, data):
    generated_at_timestamp = meta["generated_at"]
    generated_at_str = datetime_from_utc_to_local(datetime.datetime.utcfromtimestamp(int(generated_at_timestamp))).strftime("%Y-%m-%d %H:%M:%S")

    type_summary = build_summary(classify_by_type(data), mapping.subject_type, mapping.subject_color)
    status_summary = build_summary(classify_by_status(data), mapping.collection_status, mapping.collection_color)
    html = html_header.format(generated_at=generated_at_str, html_type_summary=type_summary, html_status_summary=status_summary,
        user_id=meta["user"]["id"], username=meta["user"]["nickname"], html_ep_status_example=build_ep_status_example())
    return html


def build_tag(item_tags):
    html_tag = ""
    if len(item_tags) == 0:
        return "(无标签)"
    for tag in item_tags:
        html_tag += "<span class='badge badge-pill badge-primary'>{}</span> \n".format(tag)
    return html_tag


def replace_collection_status_do_verb(item_status, item_type):
    word = mapping.collection_status[item_status]
    return word.replace("看", mapping.subject_do_word[item_type])


def build_progress_bar(item):
    
    # books -> vol, anime -> ep
    item["ep_status"] = max([item["ep_status"], item["vol_status"]])
    item["main_ep_count"] = item["subject_data"]["eps"]
    if item["main_ep_count"] == 0:
        item["main_ep_count"] = max([item["subject_data"]["volumes"], item["subject_data"]["total_episodes"]])
    if item["main_ep_count"] == 0:
        # no data
        item["main_ep_count"] = 1
    item["finish_percentage"] = round(100 * item["ep_status"] / item["main_ep_count"], 2)


def ep_sort_to_str(ep_sort):
    if int(ep_sort) - ep_sort < 0.001:
        return str(int(ep_sort))
    else:
        return str(ep_sort)


def build_ep_detail(item):
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
    
    html = ""

    for ep_type_key, ep_type_list in item["ep_data"].items():
        ep_type_str = mapping.ep_type[int(ep_type_key)]
        if len(ep_type_list) == 0:
            continue
        html += html_ep_type_name.format(ep_type_str=ep_type_str)
        ep_type_list.sort(key=lambda x: x["sort"])
        for idx, ep in enumerate(ep_type_list):
            ep["ep_status_color"] = mapping.ep_color[ep["status"]]
            ep["ep_sort_str"] = ep_sort_to_str(ep["sort"])
            ep["ep_id"] = ep["id"]
            html += html_ep_button.format_map(ep)

    return html

def build_card(item):
    item["name"] = item["subject_data"]["name"]
    item["name_cn"] = item["subject_data"].get("name_cn", item["name"])
    if item["name_cn"] == "":
        item["name_cn"] = item["name"]
    if item["comment"] is None:
        item["comment"] = "(无评论)"
    item["comment"] = item["comment"].replace("\n", "<br>")
    item["subject_status_color"] = mapping.collection_color[item["type"]]
    item["subject_status_str"] = replace_collection_status_do_verb(item["type"], item["subject_type"])
    item["html_tag"] = build_tag(item["tags"])
    build_progress_bar(item)
    item["html_ep_detail"] = build_ep_detail(item)

    return html_card.format_map(item)
    
def classify_by_type(items):
    items_by_type = { type_key:[] for type_key in mapping.subject_type.keys() }
    for item in items:
        items_by_type[item["subject_type"]].append(item)
    return items_by_type

def classify_by_status(items):
    item_by_status = { status_key:[] for status_key in mapping.collection_status.keys() }
    for item in items:
        item_by_status[item["type"]].append(item)
    return item_by_status


def build_inner_html(items_by_type):
    html = ""
    for type_key, items in items_by_type.items():
        if len(items) > 0:
          html += html_type_begin.format(type_name=mapping.subject_type[type_key])
          for item in items:
              html += build_card(item)
    return html

def main():
    print("start generate html")
    meta, data = load_takeout_json()
    header = build_header(meta, data)
    inner = build_inner_html(classify_by_type(data))
    html = html_start + header + inner + html_end
    with open("takeout.html", "w", encoding="u8") as f:
        f.write(html)
    print("done")

if __name__ == "__main__":
    main()