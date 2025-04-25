import os
import json
import time
import pandas as pd
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io

# Thư mục dữ liệu
DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)

# Scopes bắt buộc để truy cập YouTube Captions và bình luận
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# Tên file OAuth
CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = "token.json"

def authenticate():
    """Xác thực người dùng và lấy access token"""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return creds

def get_trending_videos(youtube, region_code="US", max_videos=10):
    """Lấy danh sách video thịnh hành từ YouTube"""
    try:
        request = youtube.videos().list(
            part="id,snippet,statistics",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=max_videos
        )
        response = request.execute()
        return response.get("items", [])
    except HttpError as e:
        print(f"❌ Lỗi khi lấy video thịnh hành: {e}")
        return []

def get_caption_list(youtube, video_id):
    """Lấy danh sách phụ đề của video"""
    try:
        request = youtube.captions().list(part="snippet", videoId=video_id)
        response = request.execute()
        return response.get("items", [])
    except HttpError as e:
        print(f"❌ Lỗi khi lấy danh sách phụ đề của video {video_id}: {e}")
        return []

def download_caption(youtube, caption_id):
    """Tải phụ đề của video theo caption_id"""
    try:
        request = youtube.captions().download(id=caption_id)
        response = request.execute()
        return response
    except HttpError as e:
        print(f"❌ Lỗi khi tải phụ đề ID {caption_id}: {e}")
        return None

def save_to_csv(data, data_type):
    """Lưu dữ liệu vào file CSV"""
    if not data:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(DATA_DIR, f"{data_type}_{timestamp}.csv")
    pd.DataFrame(data).to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"✅ Đã lưu {data_type} vào {filename}")

def get_video_comments(youtube, video_id, max_comments=100):
    """Lấy bình luận video"""
    comments = []
    next_page_token = None
    try:
        while max_comments > 0:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token
            )
            response = request.execute()
            for item in response["items"]:
                comment = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "video_id": video_id,
                    "author": comment["authorDisplayName"],
                    "comment": comment["textDisplay"],
                    "published_at": comment["publishedAt"],
                    "like_count": comment["likeCount"]
                })
            max_comments -= len(response["items"])
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
            time.sleep(1)  # Tránh gửi quá nhiều request
    except HttpError as e:
        print(f"❌ Lỗi khi lấy bình luận video {video_id}: {e}")
    return comments

def process_video_data(youtube, video, max_comments=100):
    """Xử lý video: lấy thông tin bình luận và phụ đề"""
    video_id = video["id"]
    video_data = {
        "video_id": video_id,
        "title": video["snippet"]["title"],
        "description": video["snippet"].get("description", ""),
        "published_at": video["snippet"]["publishedAt"],
        "view_count": video["statistics"].get("viewCount", 0),
        "like_count": video["statistics"].get("likeCount", 0),
        "comment_count": video["statistics"].get("commentCount", 0),
    }

    # Lấy bình luận video
    comments = get_video_comments(youtube, video_id, max_comments)

    # Lấy phụ đề
    captions_data = []
    captions = get_caption_list(youtube, video_id)
    for caption in captions:
        caption_id = caption["id"]
        caption_lang = caption["snippet"].get("language", "unknown")
        caption_text = download_caption(youtube, caption_id)
        if caption_text:
            captions_data.append({
                "video_id": video_id,
                "language": caption_lang,
                "caption": caption_text
            })
    
    return video_data, comments, captions_data

def crawl_youtube_data(region_code="US", max_videos=10, max_comments=100):
    """Chạy chương trình thu thập video, bình luận và phụ đề"""
    creds = authenticate()
    youtube = build("youtube", "v3", credentials=creds)
    
    trending_videos = get_trending_videos(youtube, region_code, max_videos)
    
    all_video_data = []
    all_comments_data = []
    all_captions_data = []
    
    for video in trending_videos:
        video_data, comments, captions_data = process_video_data(youtube, video, max_comments)
        all_video_data.append(video_data)
        all_comments_data.extend(comments)
        all_captions_data.extend(captions_data)

    # Lưu dữ liệu vào CSV
    save_to_csv(all_video_data, "video_metadata")
    save_to_csv(all_comments_data, "comments")
    save_to_csv(all_captions_data, "captions")

# Chạy chương trình
if __name__ == "__main__":
    crawl_youtube_data(region_code="US", max_videos=10, max_comments=100)
