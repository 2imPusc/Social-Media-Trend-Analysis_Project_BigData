import os
import time
import logging
import requests
import pandas as pd
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import argparse

# Thiết lập logging
logging.basicConfig(
    filename="youtube_crawler.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load API Key từ .env
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    logging.error("API Key không được cấu hình.")
    raise ValueError("API Key không được cấu hình trong biến môi trường YOUTUBE_API_KEY.")

# Cấu hình thư mục lưu trữ
DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)

# File lưu danh sách video đã thu thập
CRAWLED_VIDEO_IDS_FILE = os.path.join(DATA_DIR, "crawled_video_ids.json")
if os.path.exists(CRAWLED_VIDEO_IDS_FILE):
    with open(CRAWLED_VIDEO_IDS_FILE, "r") as f:
        crawled_video_ids = set(json.load(f))
else:
    crawled_video_ids = set()

# Khởi tạo YouTube API client
youtube = build("youtube", "v3", developerKey=API_KEY)

# Hàm kiểm tra kết nối YouTube
def check_youtube_status():
    try:
        response = requests.get("https://www.youtube.com", timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False

# Lưu dữ liệu vào CSV
def save_to_csv(data, data_type):
    if not data:
        logging.warning(f"Không có dữ liệu để lưu vào {data_type}.")
        return
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(DATA_DIR, f"{data_type}_{timestamp}.csv")
        pd.DataFrame(data).to_csv(filename, index=False, encoding="utf-8-sig")
        logging.info(f"Đã lưu {len(data)} bản ghi vào {filename}")
        print(f"✅ Đã lưu {len(data)} bản ghi vào {filename}")
    except Exception as e:
        logging.error(f"Lỗi khi lưu file CSV {data_type}: {e}")

# Lấy danh sách video thịnh hành
def get_trending_videos(region_code="US", max_videos=50, category_cache=None):
    videos = []
    next_page_token = None

    while len(videos) < max_videos:
        try:
            request = youtube.videos().list(
                part="id,snippet,statistics,contentDetails",
                chart="mostPopular",
                regionCode=region_code,
                maxResults=min(50, max_videos - len(videos)),
                pageToken=next_page_token
            )
            response = request.execute()
            logging.info(f"Quota used: 1 (videos.list)")

            for item in response["items"]:
                video_id = item["id"]
                if video_id in crawled_video_ids:
                    logging.info(f"Bỏ qua video trùng lặp: {video_id}")
                    continue
                videos.append({
                    "content_id": video_id,
                    "platform": "youtube",
                    "title": item["snippet"]["title"],
                    "content": item["snippet"].get("description", ""),
                    "created_at": datetime.strptime(item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S"),
                    "source_id": item["snippet"]["channelId"],
                    "source_name": item["snippet"]["channelTitle"],
                    "category_id": item["snippet"]["categoryId"],
                    "category_name": get_category_name(item["snippet"]["categoryId"], category_cache),
                    "tags": json.dumps(item["snippet"].get("tags", [])),
                    "views": int(item["statistics"].get("viewCount", 0)),
                    "score": int(item["statistics"].get("likeCount", 0)),
                    "comment_count": int(item["statistics"].get("commentCount", 0)),
                    "duration": item["contentDetails"]["duration"],
                    "upvote_ratio": 1.0,
                    "url": f"https://youtube.com/watch?v={video_id}",
                    "author": item["snippet"].get("channelTitle", "N/A")
                })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
            time.sleep(1)
        except HttpError as e:
            logging.error(f"Lỗi khi lấy video thịnh hành: {e}")
            break

    return videos

# Lấy tên danh mục video
def get_category_name(category_id, cache=None):
    if cache is None:
        cache = {}
    if category_id in cache:
        return cache[category_id]
    try:
        request = youtube.videoCategories().list(part="snippet", id=category_id)
        response = request.execute()
        logging.info(f"Quota used: 1 (videoCategories.list)")
        if response["items"]:
            category_name = response["items"][0]["snippet"]["title"]
            cache[category_id] = category_name
            return category_name
        return "Unknown"
    except HttpError as e:
        logging.error(f"Lỗi khi lấy danh mục video {category_id}: {e}")
        return "Unknown"

# Lấy bình luận video
def get_video_comments(video_id, max_comments=100):
    comments = []
    next_page_token = None
    remaining_comments = max_comments
    try:
        while remaining_comments > 0:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(remaining_comments, 100),
                pageToken=next_page_token
            )
            response = request.execute()
            logging.info(f"Quota used: 1 (commentThreads.list)")

            for item in response["items"]:
                comment = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "comment_id": f"yt_{video_id}_{hash(comment['textDisplay'])}",
                    "content_id": video_id,
                    "platform": "youtube",
                    "content": comment["textDisplay"],
                    "created_at": datetime.strptime(comment["publishedAt"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S"),
                    "score": comment["likeCount"],
                    "author": comment["authorDisplayName"],
                    "source_name": item["snippet"].get("channelTitle", "Unknown")
                })
            remaining_comments -= len(response["items"])
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
            time.sleep(1)
    except HttpError as e:
        logging.error(f"Lỗi khi lấy bình luận video {video_id}: {e}")
    return comments

# Xử lý từng video
def process_video(video, category_cache, max_comments):
    video_id = video["content_id"]
    logging.info(f"Đang xử lý video {video_id}: {video['title']}")
    comments = get_video_comments(video_id, max_comments) if max_comments > 0 else []
    return video, comments

# Hàm chính
def crawl_youtube_trending(region_code="US", max_videos=50, max_comments_per_video=100, max_workers=3):
    global crawled_video_ids
    content_data = []
    comment_data = []
    category_cache = {}

    print(f"🔍 Lấy video thịnh hành tại khu vực {region_code}...")
    videos = get_trending_videos(region_code, max_videos, category_cache)
    if not videos:
        print("⚠️ Không tìm thấy video thịnh hành.")
        return

    # Xử lý đa luồng
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(
            lambda video: process_video(video, category_cache, max_comments_per_video),
            videos
        ))

    for video, comments in results:
        content_data.append(video)
        comment_data.extend(comments)
        crawled_video_ids.add(video["content_id"])

    save_to_csv(content_data, "contents")
    save_to_csv(comment_data, "comments")

    with open(CRAWLED_VIDEO_IDS_FILE, "w") as f:
        json.dump(list(crawled_video_ids), f)

    print(f"✅ Hoàn tất. Đã thu thập {len(content_data)} video và {len(comment_data)} bình luận.")

# Entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl video thịnh hành YouTube.")
    parser.add_argument("--region", default="US", help="Mã quốc gia (ví dụ: US, VN, JP)")
    parser.add_argument("--max-videos", type=int, default=20, help="Số lượng video")
    parser.add_argument("--max-comments", type=int, default=100, help="Số bình luận mỗi video")
    parser.add_argument("--max-workers", type=int, default=3, help="Số luồng xử lý song song")
    args = parser.parse_args()

    crawl_youtube_trending(
        region_code=args.region,
        max_videos=args.max_videos,
        max_comments_per_video=args.max_comments,
        max_workers=args.max_workers
    )
