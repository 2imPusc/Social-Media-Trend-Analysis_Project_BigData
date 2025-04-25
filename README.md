# Social-Media-Trend-Analysis_Project_BigData\Social Media Crawler
This repository contains two Python scripts for crawling data from YouTube (youtube_crawler.py) and Reddit (reddit_crawler.py). The scripts collect trending videos from YouTube and top posts from Reddit, storing the data in CSV files with a unified schema for easy integration and analysis. This README explains the data fields collected in each data type (contents, comments, captions) to help team members understand the output.
Table of Contents

Overview
Data Types and Fields
Contents
Comments
Captions (YouTube only)


How to Run the Scripts
Checking the Data
Merging Data
Notes

Overview
The crawlers collect data from:

YouTube: Trending videos in a specified region (e.g., Vietnam - VN), including video details, comments, and captions.
Reddit: Top posts from predefined subreddits (e.g., r/technology, r/VietNam), including post details and comments.

Output:

Data is saved as CSV files in the Data directory:
contents_<timestamp>.csv: Main content (videos or posts).
comments_<timestamp>.csv: Comments on videos or posts.
captions_<timestamp>.csv: Captions for YouTube videos (Reddit does not have this).


JSON files track crawled items to avoid duplicates:
crawled_video_ids.json (YouTube).
crawled_post_ids.json, checkpoint.json (Reddit).


Logs are saved in youtube_crawler.log and reddit_crawler.log.

The schema is unified across platforms to simplify analysis (e.g., combining YouTube and Reddit data).
Data Types and Fields
Below are the data types and their fields, with explanations for each.
Contents
The contents data type represents the main content: videos (YouTube) or posts (Reddit).
File: contents_<timestamp>.csv
Fields:



Field
Type
Description
YouTube Example
Reddit Example



content_id
String
Unique ID of the content (video ID for YouTube, post ID for Reddit).
dQw4w9WgXcQ
1abc2def


platform
String
Source platform (youtube or reddit).
youtube
reddit


title
String
Title of the video or post.
Never Gonna Give You Up
New Tech Breakthrough


content
String
Description (YouTube) or post body (Reddit). May be empty.
Official music video...
This new gadget is amazing...


created_at
String
Timestamp when content was posted (format: YYYY-MM-DD HH:MM:SS).
2009-10-25 06:57:33
2025-04-01 12:34:56


source_id
String
ID of the channel (YouTube) or subreddit (Reddit).
UCuAXFkgsw1L7xaCfnd5JJoQ
technology


source_name
String
Name of the channel (YouTube) or subreddit (Reddit).
RickAstleyVEVO
technology


category_id
String
Category ID (YouTube) or field name (Reddit, e.g., Technology).
10 (Music)
technology


category_name
String
Category name (YouTube) or field name (Reddit).
Music
Technology


tags
String
JSON array of tags (YouTube) or empty array (Reddit).
["music", "80s"]
[]


views
Integer
Number of views (YouTube) or 0 (Reddit, not available).
1000000000
0


score
Integer
Number of likes (YouTube) or upvotes (Reddit).
20000000
1500


comment_count
Integer
Number of comments.
500000
300


duration
String
Video duration (YouTube, ISO 8601 format) or empty (Reddit).
PT3M33S (3m33s)
``


upvote_ratio
Float
Like ratio (YouTube, always 1.0) or upvote ratio (Reddit).
1.0
0.95


url
String
URL of the content.
https://youtube.com/watch?v=dQw4w9WgXcQ
https://reddit.com/r/technology/comments/1abc2def


author
String
Channel name (YouTube) or post author (Reddit).
RickAstleyVEVO
u/TechLover


Comments
The comments data type represents user comments on videos (YouTube) or posts (Reddit).
File: comments_<timestamp>.csv
Fields:



Field
Type
Description
YouTube Example
Reddit Example



comment_id
String
Unique ID of the comment (generated for YouTube, comment ID for Reddit).
yt_dQw4w9WgXcQ_123456
t1_ghi789


content_id
String
ID of the video or post the comment belongs to.
dQw4w9WgXcQ
1abc2def


platform
String
Source platform (youtube or reddit).
youtube
reddit


content
String
Text of the comment.
Love this song!
This is so cool!


created_at
String
Timestamp when comment was posted (format: YYYY-MM-DD HH:MM:SS).
2025-04-26 10:00:00
2025-04-01 13:00:00


score
Integer
Number of likes (YouTube) or upvotes (Reddit).
100
50


author
String
Comment author (display name for YouTube, username for Reddit).
User123
u/Commenter


source_name
String
Channel name (YouTube) or subreddit (Reddit).
RickAstleyVEVO
technology


Captions (YouTube only)
The captions data type represents subtitles or captions for YouTube videos. Reddit does not have this data type.
File: captions_<timestamp>.csv
Fields:



Field
Type
Description
YouTube Example



content_id
String
ID of the video the caption belongs to.
dQw4w9WgXcQ


platform
String
Source platform (youtube).
youtube


language
String
Language code of the caption (e.g., en, vi).
en


name
String
Name of the caption track (often empty or descriptive).
English


is_auto
Boolean
Whether the caption is auto-generated (True) or manual (False).
True


content
String
Caption text in SRT format (includes timestamps and text).
1\n00:00:00,000 --> 00:00:02,000\nNever...


How to Run the Scripts
Prerequisites

OS: Ubuntu (tested).
Python: Anaconda with Python 3.9.
Libraries:pip install google-api-python-client pandas python-dotenv requests praw kafka-python


YouTube API Key: Create at Google Cloud Console and add to .env:echo "YOUTUBE_API_KEY=your_api_key_here" > .env


Reddit API Credentials: Update client_id, client_secret, user_agent in reddit_crawler.py (get from Reddit Developer Portal).

Setup

Create the Data directory:mkdir Data
chmod u+w Data


Ensure youtube_crawler.py, reddit_crawler.py, and .env are in the working directory.

Running YouTube Crawler
conda activate social_media_crawler
python youtube_crawler.py --region VN --max-videos 50 --max-comments 10


--region VN: Crawl trending videos in Vietnam.
--max-videos 50: Collect up to 50 videos.
--max-comments 10: Collect up to 10 comments per video.

Running Reddit Crawler
conda activate social_media_crawler
python reddit_crawler.py


Collects up to 2000 posts per subreddit in categories (Technology, News, Entertainment, Lifestyle), with up to 10 comments per post.

Running Both Simultaneously

Open two terminals, activate the environment in each, and run the commands above.
The scripts are designed to avoid conflicts (separate CSV timestamps, independent JSON files).

Checking the Data

View CSV Files:
ls Data

Expected files:

contents_<timestamp>.csv
comments_<timestamp>.csv
captions_<timestamp>.csv (YouTube only)
crawled_video_ids.json, youtube_crawler.log (YouTube)
crawled_post_ids.json, checkpoint.json, reddit_crawler.log (Reddit)


Inspect with Python:
import pandas as pd
contents = pd.read_csv("Data/contents_<timestamp>.csv")
print(contents.columns)
print(contents.head())


Check Logs:
cat Data/youtube_crawler.log
cat Data/reddit_crawler.log



Merging Data
To combine CSV files from YouTube and Reddit, use merge_csv.py:
import pandas as pd
import glob
import os

DATA_DIR = "Data"
OUTPUT_DIR = "Data/merged"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def merge_csv_files(data_type):
    files = glob.glob(os.path.join(DATA_DIR, f"{data_type}_*.csv"))
    if not files:
        print(f"No {data_type} files found")
        return
    dfs = [pd.read_csv(file) for file in files]
    merged_df = pd.concat(dfs, ignore_index=True)
    output_file = os.path.join(OUTPUT_DIR, f"{data_type}.csv")
    merged_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Merged {len(dfs)} files into {output_file}")

merge_csv_files("contents")
merge_csv_files("comments")
merge_csv_files("captions")

Run:
python merge_csv.py

Output: Data/merged/contents.csv, Data/merged/comments.csv, Data/merged/captions.csv.
Notes

Kafka: The scripts can send data to a Kafka topic (social_media_data), but this is optional. If Kafka is not running, data is still saved to CSV.
YouTube API Quota: Limited to 10,000 units/day. Crawling 50 videos with comments and captions uses ~5100-5200 units. Check logs for "quotaExceeded" errors.
Reddit API Limits: 60 requests/minute, handled by check_rate_limit. Check logs for API errors.
Encoding: CSV files use utf-8-sig to support Vietnamese characters.
Duplicates: Avoided using crawled_video_ids.json (YouTube) and crawled_post_ids.json (Reddit).
Issues: If you encounter errors (API, libraries, performance), check logs and contact the team lead with details.

For further assistance, contact the team lead or refer to the logs in Data.
