import praw
import pandas as pd
import time
from datetime import datetime
import os
import json
from concurrent.futures import ThreadPoolExecutor
import logging
import praw.exceptions
import prawcore.exceptions
from kafka import KafkaProducer

# Cấu hình
DATA_DIR = "Data"
CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint.json")
CRAWLED_POST_IDS_FILE = os.path.join(DATA_DIR, "crawled_post_ids.json")
MAX_THREADS = 2
LIMIT_POSTS = 2000
LIMIT_COMMENTS = 10
BATCH_SIZE = 200

# Thiết lập logging
logging.basicConfig(
    filename=os.path.join(DATA_DIR, 'reddit_crawler.log'),
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def log(msg):
    logging.info(msg)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# Đảm bảo thư mục Data tồn tại
os.makedirs(DATA_DIR, exist_ok=True)

# Cấu hình Kafka
KAFKA_BOOTSTRAP_SERVERS = ['localhost:9092']
KAFKA_TOPIC = "social_media_data"
try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
except Exception as e:
    logging.error(f"Không thể kết nối Kafka: {e}")
    producer = None

# Khởi tạo Reddit instance
reddit = praw.Reddit(
    client_id='-azzbUReAtS9-o41ZbGNrQ',
    client_secret='Vb9gsVUPKL1nViZkF0Tp35rz9K7Ruw',
    user_agent='2imPusc_'
)

# Danh sách subreddit theo lĩnh vực
subreddits_by_field = {
    "Technology": ["technology", "gadgets", "programming"],
    "News": ["worldnews", "news", "VietNam"],
    "Entertainment": ["movies", "gaming", "music"],
    "Lifestyle": ["fitness", "food", "travel"]
}

# Load checkpoint và post_ids
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, 'r') as f:
        checkpoint = json.load(f)
else:
    checkpoint = {}

if os.path.exists(CRAWLED_POST_IDS_FILE):
    with open(CRAWLED_POST_IDS_FILE, 'r') as f:
        crawled_post_ids = set(json.load(f))
else:
    crawled_post_ids = set()

# Kiểm tra giới hạn API
def check_rate_limit(post_count):
    if post_count % 50 != 0:
        return
    limits = reddit.auth.limits
    remaining = limits.get('remaining', float('inf'))
    reset = limits.get('reset_timestamp', time.time() + 60)
    log(f"API còn lại: {remaining} yêu cầu, reset sau {(reset - time.time())/60:.2f} phút")
    if remaining < 50:
        wait_time = reset - time.time() + 10
        if wait_time > 0:
            log(f"Đang chờ {wait_time:.2f}s do giới hạn API...")
            time.sleep(wait_time)

# Hàm gửi dữ liệu vào Kafka
def send_to_kafka(data, data_type):
    if not producer:
        logging.warning("Kafka producer không khả dụng, bỏ qua gửi dữ liệu.")
        return
    try:
        for record in data:
            record["data_type"] = data_type  # Thêm trường để xác định loại dữ liệu
            producer.send(KAFKA_TOPIC, record)
        producer.flush()
        logging.info(f"Đã gửi {len(data)} bản ghi {data_type} vào Kafka topic {KAFKA_TOPIC}")
    except Exception as e:
        logging.error(f"Lỗi khi gửi dữ liệu vào Kafka: {e}")

# Hàm lưu dữ liệu vào CSV
def save_data(data, data_type):
    if not data:
        logging.warning(f"Không có dữ liệu để lưu vào {data_type}.")
        return
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(DATA_DIR, f"{data_type}_{timestamp}.csv")
    pd.DataFrame(data).to_csv(filename, index=False, encoding='utf-8-sig')
    log(f"Đã lưu {len(data)} bản ghi vào {filename}")

# Thu thập dữ liệu từ subreddit
def collect_data(field, subreddit_name):
    if checkpoint.get(field, {}).get(subreddit_name):
        log(f"Bỏ qua r/{subreddit_name} vì đã thu thập trước đó.")
        return [], []

    content_data = []
    comment_data = []
    retries = 3
    post_count = 0
    for attempt in range(retries):
        try:
            log(f"Đang thu thập từ r/{subreddit_name}... (Lần thử {attempt + 1})")
            subreddit = reddit.subreddit(subreddit_name)
            for post in subreddit.top(limit=LIMIT_POSTS, time_filter="month"):
                check_rate_limit(post_count)
                post_count += 1
                time.sleep(0.5)
                if post.id in crawled_post_ids:
                    continue
                content_data.append({
                    "content_id": post.id,
                    "platform": "reddit",
                    "title": post.title,
                    "content": post.selftext,
                    "created_at": datetime.utcfromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                    "source_id": subreddit_name,
                    "source_name": subreddit_name,
                    "category_id": field.lower(),
                    "category_name": field,
                    "tags": json.dumps([]),
                    "views": 0,
                    "score": post.score,
                    "comment_count": post.num_comments,
                    "duration": "",
                    "upvote_ratio": post.upvote_ratio,
                    "url": post.url,
                    "author": str(post.author) if post.author else "N/A"
                })

                post.comments.replace_more(limit=0)
                for comment in post.comments[:LIMIT_COMMENTS]:
                    comment_data.append({
                        "comment_id": comment.id,
                        "content_id": post.id,
                        "platform": "reddit",
                        "content": comment.body,
                        "created_at": datetime.utcfromtimestamp(comment.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        "score": comment.score,
                        "author": str(comment.author) if comment.author else "N/A",
                        "source_name": subreddit_name
                    })

                if len(content_data) >= BATCH_SIZE:
                    save_data(content_data, "contents")
                    save_data(comment_data, "comments")
                    send_to_kafka(content_data, "contents")
                    send_to_kafka(comment_data, "comments")
                    crawled_post_ids.update([content["content_id"] for content in content_data])
                    with open(CRAWLED_POST_IDS_FILE, 'w') as f:
                        json.dump(list(crawled_post_ids), f)
                    log(f"Đã thu thập {len(content_data)} bài đăng từ r/{subreddit_name}")
                    content_data, comment_data = [], []

            if content_data:
                save_data(content_data, "contents")
                save_data(comment_data, "comments")
                send_to_kafka(content_data, "contents")
                send_to_kafka(comment_data, "comments")
                crawled_post_ids.update([content["content_id"] for content in content_data])
                with open(CRAWLED_POST_IDS_FILE, 'w') as f:
                    json.dump(list(crawled_post_ids), f)
                log(f"Đã thu thập {len(content_data)} bài đăng từ r/{subreddit_name}")

            checkpoint.setdefault(field, {})[subreddit_name] = True
            with open(CHECKPOINT_FILE, 'w') as f:
                json.dump(checkpoint, f, indent=2)
            return content_data, comment_data

        except (praw.exceptions.RedditAPIException, prawcore.exceptions.RequestException) as e:
            log(f"Lỗi API khi thu thập r/{subreddit_name}: {e}")
            if attempt < retries - 1:
                wait_time = 2 ** attempt * 60
                log(f"Thử lại sau {wait_time}s...")
                time.sleep(wait_time)
            else:
                log(f"Đã thử {retries} lần, bỏ qua r/{subreddit_name}")
                return [], []
        except Exception as e:
            log(f"Lỗi không xác định khi thu thập r/{subreddit_name}: {e}")
            return [], []

# Chạy chương trình
start_time = datetime.now()
log(f"BẮT ĐẦU THU THẬP DỮ LIỆU: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

content_data_all = []
comment_data_all = []
for field, subreddit_list in subreddits_by_field.items():
    log(f"\n--- LĨNH VỰC: {field} ---")
    try:
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = [executor.submit(collect_data, field, sub) for sub in subreddit_list]
            for future in futures:
                try:
                    content_data, comment_data = future.result()
                    content_data_all.extend(content_data)
                    comment_data_all.extend(comment_data)
                except Exception as e:
                    log(f"Lỗi trong thread: {e}")
    except Exception as e:
        log(f"Lỗi cấp cao trong lĩnh vực {field}: {e}")

# Lưu toàn bộ dữ liệu
if content_data_all:
    save_data(content_data_all, "contents")
    send_to_kafka(content_data_all, "contents")
if comment_data_all:
    save_data(comment_data_all, "comments")
    send_to_kafka(comment_data_all, "comments")

end_time = datetime.now()
log(f"\nHOÀN TẤT THU THẬP DỮ LIỆU: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
log(f"Tổng thời gian chạy: {(end_time - start_time).total_seconds() / 3600:.2f} giờ")