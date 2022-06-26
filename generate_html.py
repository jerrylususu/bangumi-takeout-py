
import json
import datetime

import mapping
import utils

OFFSET_TIMEDELTA = None

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
    .extra-line-height {
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
        const firstBody = document.querySelector('.card-body')
        if (firstBody.classList.contains('collapse')) {
            document.querySelectorAll('.card-body').forEach((it) => {
                it.classList.remove('collapse')
                it.classList.add('show')
            })
        } else {
            document.querySelectorAll('.card-body').forEach((it) => {
                it.classList.remove('show')
                it.classList.add('collapse')
            })
        }
    });
  </script>
</body>

</html>"""


html_header = """<h1>Bangumi Takeout</h1>
    <p>使用 <a href="https://github.com/jerrylususu/bangumi-takeout-py" target="_blank">Bangumi Takeout</a> 为用户 <a href="https://bgm.tv/user/{user_id}" target="_blank">{username}</a> 于 {generated_at} 生成</p>
    <p class="extra-line-height">类型统计：
      {html_type_summary}
    </p>
    <p class="extra-line-height">状态统计： 
      {html_status_summary}
    </p>
    <p class="extra-line-height">分集图例：
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
          <dd class="col-sm-10 extra-line-height">
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
    title="{ep_tooltip}">
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



def build_ep_status_example():
    html = ""
    for status_key, status_name in mapping.ep_status.items():
        html += html_ep_status_example.format(color=mapping.ep_color[status_key], name=mapping.ep_status[status_key])
    return html

def build_header(meta, data):
    generated_at_timestamp = meta["generated_at"]
    generated_at_str = utils.datetime_from_utc_with_offset(datetime.datetime.utcfromtimestamp(int(generated_at_timestamp)), OFFSET_TIMEDELTA).strftime("%Y-%m-%d %H:%M:%S")

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





def build_ep_detail(item):
    utils.combine_ep_and_progress(item)

    html = ""

    for ep_type_key, ep_type_list in item["ep_data"].items():
        if len(ep_type_list) == 0:
            continue
        if "should_display_as_disc" in item and item["should_display_as_disc"]:
            ep_type_str = ep_type_key
        else:
            ep_type_str = mapping.ep_type[int(ep_type_key)]
        html += html_ep_type_name.format(ep_type_str=ep_type_str)
        ep_type_list.sort(key=lambda x: x["sort"])
        for idx, ep in enumerate(ep_type_list):
            ep["ep_status_color"] = mapping.ep_color[ep["status"]]
            ep["ep_sort_str"] = utils.ep_sort_to_str(ep["sort"])
            ep["ep_id"] = ep["id"]

            # build ep_tooltip
            html_tooltip = "ep.{ep_sort_str} {name}".format_map(ep)
            for key, key_str in mapping.ep_tooltip_key_str.items():
                if key in ep and ep[key]: 
                    html_tooltip += "<br>{key_str}: {value} ".format_map({"key_str": key_str, "value": ep[key]})
            ep["ep_tooltip"] = html_tooltip
            html += html_ep_button.format_map(ep)

    if html == "":
        html = "(无分集)"

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
    utils.write_progress_info(item)
    item["html_ep_detail"] = build_ep_detail(item)

    item["updated_at"] = utils.datetime_from_utc_with_offset(
        datetime.datetime.fromisoformat(item["updated_at"].strip("Z")), OFFSET_TIMEDELTA).strftime("%Y-%m-%d %H:%M:%S")

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

def main(offset_hours=None):
    global OFFSET_TIMEDELTA
    if offset_hours is not None:
        OFFSET_TIMEDELTA = datetime.timedelta(hours=offset_hours)
    
    print("start generate html")
    meta, data = load_takeout_json()
    header = build_header(meta, data)
    inner = build_inner_html(classify_by_type(data))
    html = html_start + header + inner + html_end
    with open("takeout.html", "w", encoding="u8") as f:
        f.write(html)
    print("done")

if __name__ == "__main__":
    main(offset_hours=None)