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

# Cấu hình
DATA_DIR = "Data"
CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint.json")
POST_ID_TRACK_FILE = os.path.join(DATA_DIR, "crawled_post_ids.json")
MAX_THREADS = 2
LIMIT_POSTS = 2000
LIMIT_COMMENTS = 10
BATCH_SIZE = 200

# Thiết lập logging
logging.basicConfig(
    filename=os.path.join(DATA_DIR, 'crawler.log'),
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def log(msg):
    logging.info(msg)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# Đảm bảo thư mục Data tồn tại
os.makedirs(DATA_DIR, exist_ok=True)

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

if os.path.exists(POST_ID_TRACK_FILE):
    with open(POST_ID_TRACK_FILE, 'r') as f:
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

# Lưu dữ liệu
def save_data(posts, comments, field, subreddit_name):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    post_file = os.path.join(DATA_DIR, f"posts_{field}_{subreddit_name}_{timestamp}.csv")
    comment_file = os.path.join(DATA_DIR, f"comments_{field}_{subreddit_name}_{timestamp}.csv")
    pd.DataFrame(posts).to_csv(post_file, index=False, encoding='utf-8-sig')
    pd.DataFrame(comments).to_csv(comment_file, index=False, encoding='utf-8-sig')
    log(f"Đã lưu {len(posts)} bài đăng và {len(comments)} bình luận từ r/{subreddit_name}")

# Thu thập dữ liệu từ subreddit
def collect_data(field, subreddit_name):
    if checkpoint.get(field, {}).get(subreddit_name):
        log(f"Bỏ qua r/{subreddit_name} vì đã thu thập trước đó.")
        return

    posts, comments = [], []
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
                posts.append({
                    "subreddit": subreddit_name,
                    "post_id": post.id,
                    "title": post.title,
                    "content": post.selftext,
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "num_comments": post.num_comments,
                    "created_at": datetime.utcfromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                    "url": post.url,
                    "author": str(post.author) if post.author else "N/A"
                })

                post.comments.replace_more(limit=0)
                for comment in post.comments[:LIMIT_COMMENTS]:
                    comments.append({
                        "subreddit": subreddit_name,
                        "post_id": post.id,
                        "comment_id": comment.id,
                        "comment_content": comment.body,
                        "comment_score": comment.score,
                        "comment_created_at": datetime.utcfromtimestamp(comment.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        "comment_author": str(comment.author) if comment.author else "N/A"
                    })

                if len(posts) >= BATCH_SIZE:
                    save_data(posts, comments, field, subreddit_name)
                    crawled_post_ids.update([post["post_id"] for post in posts])
                    with open(POST_ID_TRACK_FILE, 'w') as f:
                        json.dump(list(crawled_post_ids), f)
                    log(f"Đã thu thập {len(posts)} bài đăng từ r/{subreddit_name}")
                    posts, comments = [], []

            if posts:
                save_data(posts, comments, field, subreddit_name)
                crawled_post_ids.update([post["post_id"] for post in posts])
                with open(POST_ID_TRACK_FILE, 'w') as f:
                    json.dump(list(crawled_post_ids), f)
                log(f"Đã thu thập {len(posts)} bài đăng từ r/{subreddit_name}")

            checkpoint.setdefault(field, {})[subreddit_name] = True
            with open(CHECKPOINT_FILE, 'w') as f:
                json.dump(checkpoint, f, indent=2)
            break

        except (praw.exceptions.RedditAPIException, prawcore.exceptions.RequestException) as e:
            log(f"Lỗi API khi thu thập r/{subreddit_name}: {e}")
            if attempt < retries - 1:
                wait_time = 2 ** attempt * 60
                log(f"Thử lại sau {wait_time}s...")
                time.sleep(wait_time)
            else:
                log(f"Đã thử {retries} lần, bỏ qua r/{subreddit_name}")
        except Exception as e:
            log(f"Lỗi không xác định khi thu thập r/{subreddit_name}: {e}")
            break

# Chạy chương trình
start_time = datetime.now()
log(f"BẮT ĐẦU THU THẬP DỮ LIỆU: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

for field, subreddit_list in subreddits_by_field.items():
    log(f"\n--- LĨNH VỰC: {field} ---")
    try:
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = [executor.submit(collect_data, field, sub) for sub in subreddit_list]
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    log(f"Lỗi trong thread: {e}")
    except Exception as e:
        log(f"Lỗi cấp cao trong lĩnh vực {field}: {e}")

end_time = datetime.now()
log(f"\nHOÀN TẤT THU THẬP DỮ LIỆU: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
log(f"Tổng thời gian chạy: {(end_time - start_time).total_seconds() / 3600:.2f} giờ")