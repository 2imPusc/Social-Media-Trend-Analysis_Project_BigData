import praw
import pandas as pd
import time
from datetime import datetime
import os
import json
from concurrent.futures import ThreadPoolExecutor

# Cấu hình
DATA_DIR = "Data"
CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint.json")
POST_ID_TRACK_FILE = os.path.join(DATA_DIR, "crawled_post_ids.json")
MAX_THREADS = 4
LIMIT_POSTS = 500
LIMIT_COMMENTS = 10
BATCH_SIZE = 100

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

# Load checkpoint nếu có
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, 'r') as f:
        checkpoint = json.load(f)
else:
    checkpoint = {}

# Load post_ids đã thu thập nếu có
if os.path.exists(POST_ID_TRACK_FILE):
    with open(POST_ID_TRACK_FILE, 'r') as f:
        crawled_post_ids = set(json.load(f))
else:
    crawled_post_ids = set()

# Hàm ghi log
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# Hàm kiểm tra giới hạn API
def check_rate_limit():
    limits = reddit.auth.limits
    remaining = limits.get('remaining', float('inf'))
    reset = limits.get('reset_timestamp', time.time() + 60)
    if remaining < 10:
        wait_time = reset - time.time() + 5
        if wait_time > 0:
            log(f"Đang chờ {wait_time:.2f}s do giới hạn API...")
            time.sleep(wait_time)

# Lưu dữ liệu vào file CSV
def save_data(posts, comments, field, subreddit_name):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    post_file = os.path.join(DATA_DIR, f"posts_{field}_{subreddit_name}_{timestamp}.csv")
    comment_file = os.path.join(DATA_DIR, f"comments_{field}_{subreddit_name}_{timestamp}.csv")
    pd.DataFrame(posts).to_csv(post_file, index=False, encoding='utf-8-sig')
    pd.DataFrame(comments).to_csv(comment_file, index=False, encoding='utf-8-sig')
    log(f"Đã lưu {len(posts)} bài đăng và {len(comments)} bình luận từ r/{subreddit_name}")

# Thu thập dữ liệu từ một subreddit
def collect_data(field, subreddit_name):
    if checkpoint.get(field, {}).get(subreddit_name):
        log(f"Bỏ qua r/{subreddit_name} vì đã thu thập trước đó.")
        return

    posts, comments = [], []
    try:
        log(f"Đang thu thập từ r/{subreddit_name}...")
        subreddit = reddit.subreddit(subreddit_name)
        for post in subreddit.top(limit=LIMIT_POSTS, time_filter="month"):
            check_rate_limit()
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

        save_data(posts, comments, field, subreddit_name)
        checkpoint.setdefault(field, {})[subreddit_name] = True
        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump(checkpoint, f, indent=2)

        crawled_post_ids.update([post["post_id"] for post in posts])
        with open(POST_ID_TRACK_FILE, 'w') as f:
            json.dump(list(crawled_post_ids), f)

    except Exception as e:
        log(f"Lỗi khi thu thập r/{subreddit_name}: {e}")
        # Thử lại sau 10 giây, tối đa 2 lần
        retries = 2
        for i in range(retries):
            log(f"Thử lại lần {i+1} cho r/{subreddit_name} sau 10 giây...")
            time.sleep(10)
            try:
                collect_data(field, subreddit_name)
                return
            except Exception as e:
                log(f"Thử lại lần {i+1} thất bại: {e}")

# Thu thập tất cả subreddit theo lĩnh vực
for field, subreddit_list in subreddits_by_field.items():
    log(f"\n--- LĨNH VỰC: {field} ---")
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(collect_data, field, sub) for sub in subreddit_list]
        for future in futures:
            future.result()

log("\nHoàn tất quá trình thu thập dữ liệu!")
