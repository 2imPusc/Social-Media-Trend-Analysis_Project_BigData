import praw
import pandas as pd
import time
from datetime import datetime

# Khởi tạo Reddit instance với OAuth
# Lưu ý: Bạn cần đăng ký ứng dụng tại https://old.reddit.com/prefs/apps/
# và thay thế các thông tin sau bằng thông tin của bạn:
reddit = praw.Reddit(client_id='-azzbUReAtS9-o41ZbGNrQ', client_secret='Vb9gsVUPKL1nViZkF0Tp35rz9K7Ruw', user_agent='2imPusc_')

# Hàm kiểm tra giới hạn API và chờ nếu cần
def check_rate_limit():
    used = reddit.auth.limits['used']
    remaining = reddit.auth.limits['remaining']
    reset = reddit.auth.limits['reset_timestamp']
    print(f"Giới hạn API - Đã dùng: {used}, Còn lại: {remaining}, Đặt lại lúc: {datetime.fromtimestamp(reset)}")
    if remaining < 10:
        wait_time = reset - time.time() + 5
        print(f"Đang chờ {wait_time} giây do giới hạn API...")
        time.sleep(wait_time)

# Thu thập dữ liệu theo lô
subreddit = reddit.subreddit('VietNam')
top_posts = subreddit.top(limit=2000)
posts_data = []
post_count = 0
batch_size = 100

for post in top_posts:
    try:
        check_rate_limit()
        
        posts_data.append([
            post.title,
            post.score,
            post.id,
            post.url,
            post.num_comments,
            post.created_utc
        ])
        post_count += 1
        
        if post_count % batch_size == 0:
            print(f"Đã thu thập {post_count} bài viết. Đang lưu lô và chờ 60 giây...")
            df_batch = pd.DataFrame(posts_data[-batch_size:], columns=['Title', 'Score', 'ID', 'URL', 'Num_comments', 'Created_utc'])
            df_batch.to_csv(f'top_posts_batch_{post_count//batch_size}.csv', mode='a', index=False)
            time.sleep(60)
        
    except praw.exceptions.APIException as e:
        print(f"Lỗi API: {e}. Đang chờ 60 giây trước khi thử lại...")
        time.sleep(60)
        continue
    except Exception as e:
        print(f"Lỗi không mong muốn: {e}. Bỏ qua bài viết này.")
        continue

# Lưu lô cuối cùng nếu còn bài viết
if posts_data:
    df_final = pd.DataFrame(posts_data, columns=['Title', 'Score', 'ID', 'URL', 'Num_comments', 'Created_utc'])
    df_final.to_csv('top_posts_final.csv', index=False)

print(f"Đã thu thập {len(posts_data)} bài viết tổng cộng.")