import praw
import pandas as pd
import time

# Khởi tạo Reddit instance với thông tin xác thực của bạn
reddit = praw.Reddit(client_id='-azzbUReAtS9-o41ZbGNrQ', client_secret='Vb9gsVUPKL1nViZkF0Tp35rz9K7Ruw', user_agent='2imPusc_')


# Chọn subreddit và lấy top bài viết
subreddit = reddit.subreddit('all')
top_posts = subreddit.top(limit=2000)

# Lưu dữ liệu vào danh sách
posts_data = []
post_count = 0
batch_size = 100  # Số bài viết cần lấy trong mỗi lần gọi API

# Duyệt qua top bài viết theo từng batch
for post in top_posts:
    posts_data.append([post.title, post.score, post.id, post.url, post.num_comments, post.created_utc])
    post_count += 1
    
    # Khi đã lấy đủ một batch, chờ một phút trước khi tiếp tục
    if post_count % batch_size == 0:
        print(f"Đã thu thập {post_count} bài viết. Đang chờ 1 phút...")
        time.sleep(60)  # Chờ 60 giây (1 phút)

# Chuyển đổi danh sách thành DataFrame và lưu vào file CSV
df = pd.DataFrame(posts_data, columns=['Title', 'Score', 'ID', 'URL', 'Num_comments', 'Created_utc'])
df.to_csv('top_posts.csv', index=False)

print(f"Đã thu thập {len(posts_data)} bài viết.")
