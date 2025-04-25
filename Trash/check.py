import pandas as pd

# Đọc file CSV vào DataFrame
df = pd.read_csv('top_posts.csv')

# Kiểm tra trùng lặp dựa trên cột 'ID'
duplicates = df[df.duplicated(subset=['ID'], keep=False)]

# Hiển thị kết quả
if not duplicates.empty:
    print(f"Có {len(duplicates)} hàng trùng lặp trong file 'top_posts.csv':")
    print(duplicates)
else:
    print("Không có bài viết trùng lặp trong file 'top_posts.csv'.")

# Tùy chọn: Lưu các hàng trùng lặp vào file riêng để kiểm tra
if not duplicates.empty:
    duplicates.to_csv('duplicate_posts.csv', index=False)
    print("Đã lưu các hàng trùng lặp vào file 'duplicate_posts.csv'.")