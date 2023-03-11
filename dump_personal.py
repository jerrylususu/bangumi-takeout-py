
from http.cookiejar import CookieJar
import http.cookies
import csv
import time
from pathlib import Path
import json
import shutil
import argparse

import requests
from tqdm import tqdm
from bs4 import BeautifulSoup


delay_sec_between_request = 5

api_endpoint = "https://api.bgm.tv"
domain_name = "http://bgm.tv"
headers = {
    "User-Agent": ""
}
cookiejar: CookieJar = None




def parse_topic_row(row):
    topic_element = row.find("td", class_="subject").find("a")
    topic_title = topic_element.text
    topic_url = domain_name + topic_element["href"]
    topic_id = topic_url.split("/")[-1]
    group_element = row.find("td", class_="author").find("a")
    group_title = group_element.text
    group_link = domain_name + group_element["href"]
    post_count = int(row.find("td", class_="posts").text)
    publish_time = row.find("small", class_="time").text
    return {
        "topic_id": topic_id,
        "topic_title": topic_title,
        "topic_url": topic_url,
        "group_title": group_title,
        "group_link": group_link,
        "post_count": post_count,
        "publish_time": publish_time
    }

def parse_reply_topic_row(row):
    topic_element = row.find("td", class_="subject").find("a")
    topic_title = topic_element.text
    topic_url = domain_name + topic_element["href"]
    topic_id = topic_url.split("/")[-1]
    author_element = row.find("span", class_="tip_i").find("a")
    author_url = domain_name + author_element["href"]
    author_name = author_element.text
    group_element = row.find("td", class_="author").find("a")
    group_title = group_element.text
    group_link = domain_name + group_element["href"]
    post_count = int(row.find("td", class_="posts").text)
    publish_time = row.find("small", class_="time").text
    return {
        "topic_id": topic_id,
        "topic_title": topic_title,
        "topic_url": topic_url,
        "author_url": author_url,
        "author_name": author_name,
        "group_title": group_title,
        "group_link": group_link,
        "post_count": post_count,
        "publish_time": publish_time
    }


def parse_blog_row(row):
    blog_title_element = row.find("h2", class_="title").a
    blog_title = blog_title_element.text
    blog_url = domain_name + blog_title_element["href"]
    blog_id = blog_title_element["href"].split("/")[-1]
    published_at = row.find("small", class_="time").text
    reply_count = int(row.find("small", class_="orange").text[1:-1]) #(+0)
    summary = row.find("div", class_="content").text
    tags = []
    
    if row.find("div", class_="tags"):
        tag_elements = row.find("div", class_="tags").find_all("a")
        tags = [tag_element.text for tag_element in tag_elements]

    return {
        "blog_id": blog_id,
        "blog_title": blog_title,
        "blog_url": blog_url,
        "published_at": published_at,
        "reply_count": reply_count,
        "summary": summary,
        "tags": tags
    }

def parse_index_list_row(row):
    created_at = row.cite.text.replace("创建于:","")
    index_title = row.h6.a.text
    index_url = domain_name + row.h6.a["href"]
    index_id = index_url.split("/")[-1]
    item_count = int(row.h6.span.text[1:-1])
    
    return {
        "index_id": index_id,
        "index_title": index_title,
        "index_url": index_url,
        "item_count": item_count,
        "created_at": created_at,
    }

def parse_index_collect_row(row):
    index_url = domain_name + row.h3.a["href"]
    index_id = index_url.split("/")[-1]
    index_name = row.h3.a.text
    author_element = row.find("span", class_="tip_j")
    author_user_id = author_element.a["href"].replace("/user/", "")
    author_user_name = author_element.a.text
    created_at = author_element.span.text

    return {
        "index_id": index_id,
        "index_name": index_name,
        "index_url": index_url,
        "author_user_id": author_user_id,
        "author_user_name": author_user_name,
        "created_at": created_at
    }

def parse_person_row(row):
    element = row.find("a")
    person_url = domain_name + element["href"]
    person_id = element["href"].split("/")[-1]
    person_name = element["title"]
    return {
        "person_id": person_id,
        "person_name": person_name,
        "person_url": person_url
    }

def parse_friend_row(row):
    element = row.find("a", class_="avatar")
    friend_url = domain_name + element["href"]
    friend_id = element["href"].split("/")[-1]
    friend_name = element.text.strip()
    return {
        "friend_id": friend_id,
        "friend_name": friend_name,
        "friend_url": friend_url
    }

def common_multi_page_fetch(base_url, extract_rows):
    global headers, cookiejar
    # print(f"requesting page 1 on {base_url}")
    resp = requests.get(base_url, headers=headers, cookies=cookiejar)
    soup = BeautifulSoup(resp.content, "html.parser")
    rows = extract_rows(soup)
    print(f"found {len(rows)} rows")
    pages = soup.find_all("a", class_="p")
    last_page = 1
    if pages:
        last_page = max([int(page["href"].split("=")[-1]) for page in pages])
    print(f"last page is {last_page}")

    for page_num in tqdm(range(2, last_page + 1), desc="page"):
        url = f"{base_url}?page={page_num}"
        time.sleep(delay_sec_between_request)
        # print(f"requesting page {page_num} on {url}")
        resp = requests.get(url, headers=headers, cookies=cookiejar)
        soup = BeautifulSoup(resp.content, "html.parser")
        new_rows = extract_rows(soup)
        # print(f"found {len(new_rows)} rows")
        rows += new_rows
    return rows

def fetch_timelines_until_empty_response(base_url):
    global headers, cookiejar
    # print(f"requesting page 1 on {base_url}")
    current_page = 1
    response_not_empty = True
    
    pbar = tqdm(desc="timeline")
    while response_not_empty:
        time.sleep(delay_sec_between_request)
        resp = requests.get(f"{base_url}{current_page}", headers=headers, cookies=cookiejar)
        response_not_empty = (len(resp.content) != 0)
        if not response_not_empty:
            break
        
        with open(f"output/html/timeline/{current_page}.html", "wb") as f:
            f.write(resp.content)
        pbar.update(1)
        current_page += 1
    pbar.close()

    
def parse_rows(rows, one_row_parser):
    return [one_row_parser(row) for row in rows]

def write_list_dict_to_csv(list_dict, filename):
    if len(list_dict) == 0:
        print("empty, nothing to write")
        return
    with open("output/csv/" + filename, "w", encoding="u8", newline="\n") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list_dict[0].keys())
        writer.writeheader()
        writer.writerows(list_dict)


def get_json(url):
    time.sleep(delay_sec_between_request)
    headers = {'accept': 'application/json', 'User-Agent': 'bangumi-takeout-python/v1'}
    response = requests.get(url, headers=headers)
    return response.json()

def load_data_until_finish(endpoint, limit=30, name="", show_progress=False):
    resp = get_json(endpoint)

    if "total" not in resp:
        print(f"no total {name}")
        return resp

    total = resp["total"]
    items = resp["data"]

    if show_progress:
        pbar = tqdm(total=total, desc=name)
        pbar.update(len(items))

    while(len(items) < total):
        offset = len(items)
        if "?" not in endpoint:
            new_url = f"{endpoint}?limit={limit}&offset={offset}"
        else:
            new_url = f"{endpoint}&limit={limit}&offset={offset}"
        resp = get_json(new_url)
        items += resp["data"]
        if show_progress:
            pbar.update(len(resp["data"]))
    
    if show_progress:
        pbar.close()

    return items

def save_page(url, filename):
    resp = requests.get(url, headers=headers, cookies=cookiejar)
    with open(filename, "wb") as f:
        f.write(resp.content)

def save_url_list(urls, ids, folder_name):
    for url, id in tqdm(zip(urls, ids), desc="html " + folder_name, total=len(urls)):
        save_page(url, f"output/html/{folder_name}/{id}.html")
        time.sleep(delay_sec_between_request)

def save_index(index_id, folder_name):
    index_metadata = get_json(f"{api_endpoint}/v0/indices/{index_id}")
    index_subjects = load_data_until_finish(f"{api_endpoint}/v0/indices/{index_id}/subjects")
    index_json = {"metadata": index_metadata, "subjects": index_subjects}
    with open(f"output/index_json/{folder_name}/{index_id}.json", "w", encoding="u8") as f:
        json.dump(index_json, f, ensure_ascii=False)

def save_index_list(ids, folder_name):
    for id in tqdm(ids, desc="index json " + folder_name):
        save_index(id, folder_name)
        time.sleep(delay_sec_between_request)

def prepare_folder_structure(topic=True, reply_topic=True, 
                             blog=True, 
                             created_index=True, collected_index=True, 
                             timeline=True,
                             person=True,
                             friend=True
                            ):
    Path("output/csv/").mkdir(parents=True,exist_ok=True)
    if topic:
        Path("output/html/topic").mkdir(parents=True,exist_ok=True)
    if reply_topic:
        Path("output/html/reply_topic").mkdir(parents=True,exist_ok=True)
    if blog:
        Path("output/html/blog").mkdir(parents=True,exist_ok=True)
    if created_index:
        Path("output/html/created_index").mkdir(parents=True,exist_ok=True)
        Path("output/index_json/created_index").mkdir(parents=True,exist_ok=True)
    if collected_index:
        Path("output/html/collected_index").mkdir(parents=True,exist_ok=True)
        Path("output/index_json/collected_index").mkdir(parents=True,exist_ok=True)
    if timeline:
        Path("output/html/timeline").mkdir(parents=True,exist_ok=True)
    if person:
        Path("output/html/person").mkdir(parents=True,exist_ok=True)
        Path("output/html/character").mkdir(parents=True,exist_ok=True)
    if friend:
        Path("output/html/friend").mkdir(parents=True,exist_ok=True)

        
def compress_output():
    shutil.make_archive("dump", "zip", "output")


def build_cookiejar(cookie_str: str):
    global cookiejar
    # either the string literal (with start/end quote) or just the text value should work
    if cookie_str.startswith("'") and cookie_str.endswith("'"):
        cookie_str = cookie_str.strip("'")
    simple_cookie = http.cookies.SimpleCookie(cookie_str)
    cookiejar = requests.cookies.RequestsCookieJar()
    cookiejar.update(simple_cookie)    


def main(user_id="", user_agent="", cookie_str="",
         topic=True, reply_topic=True, 
         blog=True, 
         created_index=True, collected_index=True, 
         timeline=True,
         person=True,
         friend=True,
         deep=True):
    global headers, cookiejar

    build_cookiejar(cookie_str)
    headers["User-Agent"] = user_agent

    print("here!")

    prepare_folder_structure(
        topic=topic, 
        reply_topic=reply_topic, 
        blog=blog, 
        created_index=created_index, 
        collected_index=collected_index, 
        timeline=timeline,
        person=person,
        friend=friend
    )

    # 我发表的讨论
    my_topic_url = "https://bgm.tv/group/my_topic"
    topic_extract_rows = lambda soup: soup.find_all("tr", class_="topic")
    
    # 我回复的讨论
    my_reply_topic_url = "https://bgm.tv/group/my_reply"
    reply_topic_extract_rows = lambda soup: soup.find_all("tr", class_="topic")

    # 日志
    blogs_url = f"https://bgm.tv/user/{user_id}/blog"
    blog_extract_rows = lambda soup: soup.find_all("div", class_="item")

    # 我收藏的目录
    index_list_url = f"https://bgm.tv/user/{user_id}/index"
    index_list_extract_rows = lambda soup: soup.find("ul", class_="line_list").find_all("li")

    # 我创建的目录
    index_collect_page_url = f"https://bgm.tv/user/{user_id}/index/collect"
    index_collect_extract_rows = lambda soup: soup.find_all("li", class_="tml_item")

    # 时间胶囊
    # TODO: 从 HTML 解析时间胶囊
    timeline_url = f"https://bgm.tv/user/{user_id}/timeline?type=all&ajax=1&page="
    
    # 人物
    person_url = f"https://bgm.tv/user/{user_id}/mono/person"
    character_url = f"https://bgm.tv/user/{user_id}/mono/character"
    person_extract_rows = lambda soup: soup.find_all("li", class_="clearit")
    
    # 朋友
    friend_url = f"https://bgm.tv/user/{user_id}/friends"
    friend_extract_rows = lambda soup: soup.find_all("li", class_="user")
    
    print("列表收集")
    if topic:
        print("我发表的讨论")
        my_topics = parse_rows(common_multi_page_fetch(my_topic_url, topic_extract_rows), parse_topic_row)
        print(f"dumped {len(my_topics)} my topics")
        write_list_dict_to_csv(my_topics, "my_topics.csv")
    
    if reply_topic:
        print("我回复的讨论")
        my_reply_topics = parse_rows(common_multi_page_fetch(my_reply_topic_url, topic_extract_rows), parse_reply_topic_row)
        print(f"dumped {len(my_reply_topics)} my reply topics")
        write_list_dict_to_csv(my_reply_topics, "my_reply_topics.csv")

    if blog:
        print("日志")
        blogs = parse_rows(common_multi_page_fetch(blogs_url, blog_extract_rows), parse_blog_row)
        print(f"dumped {len(blogs)} blogs")
        write_list_dict_to_csv(blogs, "blogs.csv")

    if created_index:
        print("我创建的目录")
        created_indexes = parse_rows(common_multi_page_fetch(index_list_url, index_list_extract_rows), parse_index_list_row)
        print(f"dumped {len(created_indexes)} indexes (created by me)")
        write_list_dict_to_csv(created_indexes, "created_indexes.csv")

    if collected_index:
        print("我收藏的目录")
        collected_indexes = parse_rows(common_multi_page_fetch(index_collect_page_url, index_collect_extract_rows), parse_index_collect_row)
        print(f"dumped {len(collected_indexes)} indexes (collected)")
        write_list_dict_to_csv(collected_indexes, "collected_indexes.csv")

    if timeline:
        print("时间胶囊（这个可能比较慢，建议多等等")
        fetch_timelines_until_empty_response(timeline_url)
    
    if person:
        print("收藏的现实人物")
        my_person = parse_rows(common_multi_page_fetch(person_url, person_extract_rows), parse_person_row)
        print(f"dumped {len(my_person)} my person")
        write_list_dict_to_csv(my_person, "my_person.csv")
        
        print("收藏的虚拟人物")
        my_characters = parse_rows(common_multi_page_fetch(character_url, person_extract_rows), parse_person_row)
        print(f"dumped {len(my_characters)} my character")
        write_list_dict_to_csv(my_characters, "my_characters.csv")
    
    if friend:
        print("好友")
        my_friends =  parse_rows(common_multi_page_fetch(friend_url, friend_extract_rows), parse_friend_row)
        print(f"dumped {len(my_friends)} my friend")
        write_list_dict_to_csv(my_friends, "my_friends.csv")

    if deep:
        print("深度导出已启用")

        if topic:
            urls = [t["topic_url"] for t in my_topics]
            ids = [t["topic_id"] for t in my_topics]
            save_url_list(urls, ids, "topic")
        if reply_topic:
            urls = [t["topic_url"] for t in my_reply_topics]
            ids = [t["topic_id"] for t in my_reply_topics]
            save_url_list(urls, ids, "reply_topic")
        if blog:
            urls = [b["blog_url"] for b in blogs]
            ids = [b["blog_id"] for b in blogs]
            save_url_list(urls, ids, "blog")
        if created_index:
            urls = [i["index_url"] for i in created_indexes]
            ids = [i["index_id"] for i in created_indexes]
            save_url_list(urls, ids, "created_index")
            save_index_list(ids, "created_index")
        if collected_index:
            urls = [i["index_url"] for i in collected_indexes]
            ids = [i["index_id"] for i in collected_indexes]
            save_url_list(urls, ids, "collected_index")
            save_index_list(ids, "collected_index")
        if person:
            urls = [i["person_url"] for i in my_person]
            ids = [i["person_id"] for i in my_person]
            save_url_list(urls, ids, "person")

            urls = [i["person_url"] for i in my_characters]
            ids = [i["person_id"] for i in my_characters]
            save_url_list(urls, ids, "character")

        if friend:
            urls = [t["friend_url"] for t in my_friends]
            ids = [t["friend_id"] for t in my_friends]
            save_url_list(urls, ids, "friend")

    compress_output()
    print("Done.")


def local_test():
    user_id = ""
    ua = ""
    cookie_str = ""
    main(user_id=user_id, user_agent=ua, cookie_str=cookie_str,
         topic=True, reply_topic=False, 
         blog=False, created_index=False, 
         collected_index=False, timeline=False, person=False, friend=False, deep=False)    


def command_line_launch():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user_id", help="not username")
    parser.add_argument("--user_agent", help="Browser's User Agent String")
    parser.add_argument("--cookie_str", help="document.cookie")
    parser.add_argument("--deep", help="also fetch HTML and JSON, not just the list")
    parser.add_argument("--topic", help="我发表的讨论", action="store_true")
    parser.add_argument("--reply_topic", help="我回复的讨论", action="store_true")
    parser.add_argument("--blog", help="日志", action="store_true")
    parser.add_argument("--created_index", help="我创建的目录", action="store_true")
    parser.add_argument("--collected_index", help="我收藏的目录", action="store_true")
    parser.add_argument("--timeline", help="时间胶囊", action="store_true")
    parser.add_argument("--person", help="我收藏的人物（虚拟&现实）", action="store_true")
    parser.add_argument("--friend", help="我的好友", action="store_true")
    
    args = parser.parse_args()
    main(user_id=args.user_id, user_agent=args.user_agent, cookie_str=args.cookie_str,
         topic=args.topic, reply_topic=args.reply_topic, 
         blog=args.blog, 
         created_index=args.created_index, collected_index=args.collected_index, 
         timeline=args.timeline, 
         person=args.person, 
         friend=args.friend, 
         deep=args.deep)   

if __name__ == "__main__":
    # command_line_launch()
    local_test()