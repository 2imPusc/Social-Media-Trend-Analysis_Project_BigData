import os
import time
import logging
import requests
import pandas as pd
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

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

# Kiểm tra quyền ghi thư mục
if not os.access(DATA_DIR, os.W_OK):
    logging.error(f"Không có quyền ghi vào thư mục {DATA_DIR}.")
    raise PermissionError(f"Không có quyền ghi vào thư mục {DATA_DIR}")

# File lưu danh sách video đã thu thập
CRAWLED_VIDEO_IDS_FILE = os.path.join(DATA_DIR, "crawled_video_ids.json")
if os.path.exists(CRAWLED_VIDEO_IDS_FILE):
    with open(CRAWLED_VIDEO_IDS_FILE, "r") as f:
        crawled_video_ids = set(json.load(f))
else:
    crawled_video_ids = set()

# Khởi tạo YouTube API client
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)

# Quota tối đa mỗi ngày (YouTube API v3: 10,000 đơn vị)
MAX_QUOTA = 9500  # Giữ 500 đơn vị dự phòng
# Quota đã sử dụng
quota_used = 0

# Hàm kiểm tra kết nối mạng
def check_youtube_status():
    try:
        response = requests.get("https://www.youtube.com", timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False

# Hàm lưu dữ liệu vào CSV
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

# Hàm lấy danh sách video thịnh hành
def get_trending_videos(region_code="US", max_videos=50, category_cache=None):
    global quota_used
    videos = []
    next_page_token = None
    duplicates = 0
    max_attempts = 5  # Giới hạn số lần thử nếu toàn bộ batch trùng lặp

    while len(videos) < max_videos and max_attempts > 0:
        if quota_used >= MAX_QUOTA:
            logging.warning("Đã đạt giới hạn quota API.")
            print("Đã đạt giới hạn quota API.")
            break
        try:
            request = youtube.videos().list(
                part="id,snippet,statistics,contentDetails",
                chart="mostPopular",
                regionCode=region_code,
                maxResults=min(50, max_videos - len(videos)),
                pageToken=next_page_token
            )
            response = request.execute()
            quota_used += 1
            logging.info(f"Quota used: 1 (videos.list, page {next_page_token or 'first'})")

            new_videos = 0
            for item in response["items"]:
                video_id = item["id"]
                if video_id in crawled_video_ids:
                    logging.info(f"Bỏ qua video trùng lặp: {video_id}")
                    duplicates += 1
                    continue
                new_videos += 1
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

            logging.info(f"Batch: {new_videos} video mới, {duplicates} video trùng lặp")
            print(f"Batch: {new_videos} video mới, {duplicates} video trùng lặp")

            # Nếu không có video mới, giảm số lần thử
            if new_videos == 0:
                max_attempts -= 1
                logging.warning(f"Không tìm thấy video mới. Còn {max_attempts} lần thử.")
                time.sleep(5)  # Đợi trước khi thử lại
            else:
                max_attempts = 5  # Reset số lần thử nếu tìm thấy video mới

            next_page_token = response.get("nextPageToken")
            if not next_page_token or len(videos) >= max_videos:
                break
            time.sleep(1)
        except HttpError as e:
            logging.error(f"Lỗi khi lấy video thịnh hành: {e}")
            if "quotaExceeded" in str(e):
                logging.error("Vượt quá quota API.")
                print("Vượt quá quota API.")
                break
            return videos

    return videos

# Hàm lấy tên danh mục
def get_category_name(category_id, cache=None):
    global quota_used
    if cache is None:
        cache = {}
    if category_id in cache:
        return cache[category_id]
    if quota_used >= MAX_QUOTA:
        logging.warning("Đã đạt giới hạn quota API.")
        return "Unknown"
    try:
        request = youtube.videoCategories().list(
            part="snippet",
            id=category_id
        )
        response = request.execute()
        quota_used += 1
        logging.info(f"Quota used: 1 (videoCategories.list)")
        if response["items"]:
            category_name = response["items"][0]["snippet"]["title"]
            cache[category_id] = category_name
            return category_name
        return "Unknown"
    except HttpError as e:
        logging.error(f"Lỗi khi lấy danh mục video {category_id}: {e}")
        return "Unknown"

# Hàm lấy bình luận
def get_video_comments(video_id, max_comments=100):
    global quota_used
    comments = []
    next_page_token = None
    remaining_comments = max_comments
    if quota_used >= MAX_QUOTA:
        logging.warning("Đã đạt giới hạn quota API.")
        return comments
    try:
        while remaining_comments > 0:
            if quota_used >= MAX_QUOTA:
                logging.warning("Đã đạt giới hạn quota API.")
                break
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(remaining_comments, 100),
                pageToken=next_page_token
            )
            response = request.execute()
            quota_used += 1
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
        if "commentsDisabled" in str(e):
            logging.warning(f"Bình luận bị tắt cho video {video_id}.")
    return comments

# Hàm xử lý video đơn lẻ
def process_video(video, category_cache, max_comments_per_video):
    video_id = video["content_id"]
    logging.info(f"Đang xử lý video {video_id}: {video['title']}")
    
    # Lấy bình luận
    comments = get_video_comments(video_id, max_comments_per_video) if max_comments_per_video > 0 else []
    
    return video, comments

# Hàm chính để crawl dữ liệu
def crawl_youtube_trending(region_code="US", max_videos=1000, max_comments_per_video=100, max_workers=3):
    global crawled_video_ids, quota_used
    retries = 3
    content_data = []
    comment_data = []
    category_cache = {}
    batch_size = 100  # Lưu mỗi 100 video
    videos_processed = 0

    # Tải category_cache từ file (nếu có)
    CATEGORY_CACHE_FILE = os.path.join(DATA_DIR, "category_cache.json")
    if os.path.exists(CATEGORY_CACHE_FILE):
        with open(CATEGORY_CACHE_FILE, "r") as f:
            category_cache = json.load(f)

    # Làm mới crawled_video_ids nếu cần
    if len(crawled_video_ids) > 10000:  # Giới hạn để tránh file quá lớn
        logging.info("Danh sách video đã thu thập quá lớn. Làm mới...")
        crawled_video_ids.clear()
        with open(CRAWLED_VIDEO_IDS_FILE, "w") as f:
            json.dump(list(crawled_video_ids), f)

    while quota_used < MAX_QUOTA:
        for attempt in range(retries):
            if not check_youtube_status():
                logging.warning(f"YouTube không phản hồi. Thử lại sau {2 ** attempt * 120}s...")
                print(f"YouTube không phản hồi. Thử lại sau {2 ** attempt * 120}s...")
                time.sleep(2 ** attempt * 120)
                continue

            try:
                # Lấy số lượng video tối đa còn lại trong ngày hoặc theo batch
                videos_to_fetch = min(batch_size, max_videos - videos_processed)
                if videos_to_fetch <= 0 or quota_used >= MAX_QUOTA:
                    break

                logging.info(f"Lấy {videos_to_fetch} video thịnh hành tại khu vực {region_code}...")
                print(f"Lấy {videos_to_fetch} video thịnh hành tại khu vực {region_code}...")
                videos = get_trending_videos(region_code, videos_to_fetch, category_cache)
                if not videos:
                    logging.warning("Không tìm thấy video thịnh hành mới.")
                    print("Không tìm thấy video thịnh hành mới.")
                    break

                # Song song hóa xử lý video
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    results = list(executor.map(
                        lambda video: process_video(video, category_cache, max_comments_per_video),
                        videos
                    ))

                for video, comments in results:
                    content_data.append(video)
                    comment_data.extend(comments)
                    crawled_video_ids.add(video["content_id"])
                    videos_processed += 1

                # Lưu dữ liệu nếu đủ 100 video hoặc hết video cần lấy
                if len(content_data) >= batch_size or videos_processed >= max_videos or quota_used >= MAX_QUOTA:
                    save_to_csv(content_data, "contents")
                    save_to_csv(comment_data, "comments")
                    content_data = []
                    comment_data = []

                # Cập nhật danh sách video đã thu thập
                with open(CRAWLED_VIDEO_IDS_FILE, "w") as f:
                    json.dump(list(crawled_video_ids), f)

                # Lưu category_cache
                with open(CATEGORY_CACHE_FILE, "w") as f:
                    json.dump(category_cache, f)

                logging.info(f"Tổng quota sử dụng ước tính: {quota_used}")
                print(f"Tổng quota sử dụng ước tính: {quota_used}")

                # Thoát nếu đã lấy đủ video hoặc hết quota
                if videos_processed >= max_videos or quota_used >= MAX_QUOTA:
                    break

            except HttpError as e:
                logging.error(f"Lỗi API: {e}. Thử lại lần {attempt + 1}/{retries}...")
                print(f"Lỗi API: {e}. Thử lại lần {attempt + 1}/{retries}...")
                if "quotaExceeded" in str(e):
                    logging.error("Vượt quá quota API. Thoát chương trình.")
                    print("Vượt quá quota API. Vui lòng kiểm tra quota và thử lại sau.")
                    return
                time.sleep(2 ** attempt * 120)
            except Exception as e:
                logging.error(f"Lỗi không xác định: {e}. Thử lại lần {attempt + 1}/{retries}...")
                print(f"Lỗi không xác định: {e}. Thử lại lần {attempt + 1}/{retries}...")
                time.sleep(2 ** attempt * 120)

        # Thoát vòng lặp ngoài nếu đã lấy đủ video hoặc hết quota
        if videos_processed >= max_videos or quota_used >= MAX_QUOTA:
            break

    # Lưu bất kỳ dữ liệu còn lại
    if content_data or comment_data:
        save_to_csv(content_data, "contents")
        save_to_csv(comment_data, "comments")

    # Lưu category_cache cuối cùng
    with open(CATEGORY_CACHE_FILE, "w") as f:
        json.dump(category_cache, f)

    logging.info(f"Hoàn tất thu thập. Tổng video: {videos_processed}. Quota sử dụng: {quota_used}")
    print(f"Hoàn tất thu thập. Tổng video: {videos_processed}. Quota sử dụng: {quota_used}")

# Chạy chương trình với tùy chọn dòng lệnh
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl dữ liệu YouTube thịnh hành.")
    parser.add_argument("--region", default="US", help="Mã vùng (VD: VN, US, JP)")
    parser.add_argument("--max-videos", type=int, default=1000, help="Số lượng video tối đa")
    parser.add_argument("--max-comments", type=int, default=100, help="Số lượng bình luận tối đa mỗi video")
    parser.add_argument("--max-workers", type=int, default=1, help="Số luồng tối đa cho song song hóa")
    args = parser.parse_args()

    crawl_youtube_trending(
        region_code=args.region,
        max_videos=args.max_videos,
        max_comments_per_video=args.max_comments,
        max_workers=args.max_workers
    )