# Social Media Data Crawler

This repository contains Python scripts for crawling data from YouTube and Reddit, focusing on trending videos, comments, captions (YouTube), and posts with their comments (Reddit). The scripts collect data, process it, and save it into CSV files for further analysis. This README explains the purpose of the scripts and provides a detailed mapping of the collected data fields to their real-world equivalents.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Directory Structure](#directory-structure)
- [Scripts Description](#scripts-description)
  - [YouTube Crawler](#youtube-crawler)
  - [Reddit Crawler](#reddit-crawler)
- [Data Fields Explanation](#data-fields-explanation)
  - [YouTube Data Fields](#youtube-data-fields)
  - [Reddit Data Fields](#reddit-data-fields)
- [Setup and Usage](#setup-and-usage)
- [License](#license)

## Overview
The project includes two main scripts:
1. **YouTube Crawler**: Collects trending video metadata, comments, and captions from YouTube using the YouTube Data API v3.
2. **Reddit Crawler**: Collects top posts and their comments from specified subreddits using the PRAW library.

The collected data is stored in CSV files within a `Data` directory, with timestamps for versioning. The scripts are designed to handle API rate limits, errors, and checkpointing to avoid redundant data collection.

## Prerequisites
- Python 3.8+
- Required Python libraries:
  - For YouTube: `google-api-python-client`, `google-auth-oauthlib`, `pandas`
  - For Reddit: `praw`, `pandas`
- A YouTube Data API key and OAuth 2.0 credentials (`client_secret.json`) for YouTube access.
- Reddit API credentials (client ID, client secret, user agent) for Reddit access.
- A Google Cloud project with the YouTube Data API enabled.

Install dependencies using:
```bash
pip install google-api-python-client google-auth-oauthlib pandas praw
```

## Directory Structure
```
├── Data/                    # Directory for storing output CSV files and logs
│   ├── video_metadata_*.csv # YouTube video metadata
│   ├── comments_*.csv       # YouTube and Reddit comments
│   ├── captions_*.csv       # YouTube captions
│   ├── contents_*.csv       # Reddit post metadata
│   ├── checkpoint.json       # Reddit checkpoint file
│   ├── crawled_post_ids.json # Reddit crawled post IDs
│   ├── reddit_crawler.log    # Reddit crawler log
├── youtube_crawler.py       # YouTube data crawler script
├── reddit_crawler.py        # Reddit data crawler script
├── client_secret.json       # YouTube OAuth credentials (not included)
├── README.md                # This file
```

## Scripts Description

### YouTube Crawler
- **File**: `youtube_crawler.py`
- **Purpose**: Collects trending videos, their comments, and captions from YouTube for a specified region (default: US).
- **Functionality**:
  - Authenticates using OAuth 2.0.
  - Fetches up to `max_videos` trending videos.
  - Collects up to `max_comments` comments per video.
  - Downloads available captions for each video.
  - Saves data into three CSV files: `video_metadata`, `comments`, and `captions`.

### Reddit Crawler
- **File**: `reddit_crawler.py`
- **Purpose**: Collects top posts and comments from specified subreddits, categorized by fields (Technology, News, Entertainment, Lifestyle).
- **Functionality**:
  - Uses PRAW to authenticate and access Reddit API.
  - Crawls up to `LIMIT_POSTS` posts per subreddit (default: 1000) and up to `LIMIT_COMMENTS` comments per post (default: 100).
  - Supports multithreading for faster data collection.
  - Implements checkpointing to skip previously crawled subreddits.
  - Saves data into two CSV files: `contents` (posts) and `comments`.

## Data Fields Explanation

Below is a detailed explanation of the fields in the output CSV files and their real-world equivalents.

### YouTube Data Fields

#### 1. `video_metadata_*.csv`
Contains metadata for trending YouTube videos.

| Field            | Description                                      | Real-World Equivalent                     |
|------------------|--------------------------------------------------|-------------------------------------------|
| `video_id`       | Unique ID of the video                           | YouTube video ID (e.g., in video URL)     |
| `title`          | Video title                                      | Title displayed on the video page         |
| `description`    | Video description                                | Description below the video               |
| `published_at`   | Date and time the video was published            | Upload date and time                      |
| `view_count`     | Number of views                                  | Total views shown on the video page       |
| `like_count`     | Number of likes                                  | Total likes shown on the video page       |
| `comment_count`  | Number of comments                               | Total comments shown on the video page    |

#### 2. `comments_*.csv`
Contains comments on trending YouTube videos.

| Field            | Description                                      | Real-World Equivalent                     |
|------------------|--------------------------------------------------|-------------------------------------------|
| `video_id`       | ID of the video the comment belongs to           | Links comment to its parent video         |
| `author`         | Display name of the commenter                    | Username or channel name of the commenter |
| `comment`        | Text content of the comment                      | Comment text as seen below the video      |
| `published_at`   | Date and time the comment was posted             | Timestamp of the comment                   |
| `like_count`     | Number of likes on the comment                   | Likes shown on the comment                |

#### 3. `captions_*.csv`
Contains captions (subtitles) for trending YouTube videos.

| Field            | Description                                      | Real-World Equivalent                     |
|------------------|--------------------------------------------------|-------------------------------------------|
| `video_id`       | ID of the video the caption belongs to           | Links caption to its parent video         |
| `language`       | Language code of the caption (e.g., "en")         | Language of the subtitle track            |
| `caption`        | Text content of the caption                      | Subtitle text displayed during playback   |

### Reddit Data Fields

#### 1. `contents_*.csv`
Contains metadata for Reddit posts.

| Field            | Description                                      | Real-World Equivalent                     |
|------------------|--------------------------------------------------|-------------------------------------------|
| `content_id`     | Unique ID of the post                            | Reddit post ID (e.g., in post URL)        |
| `platform`       | Platform name (always "reddit")                  | Identifies the source as Reddit           |
| `title`          | Post title                                       | Title displayed on the post               |
| `content`        | Text content of the post (selftext)              | Body text of text-based posts             |
| `created_at`     | Date and time the post was created               | Post creation timestamp                   |
| `source_id`      | Subreddit name (e.g., "technology")              | Subreddit ID (e.g., r/technology)         |
| `source_name`    | Subreddit name (same as source_id)               | Subreddit name as displayed               |
| `category_id`    | Field/category lowercase (e.g., "technology")    | Internal category identifier              |
| `category_name`  | Field/category name (e.g., "Technology")         | Human-readable category name              |
| `tags`           | JSON array of tags (currently empty)             | Potential tags for categorization         |
| `views`          | Number of views (always 0, not available)        | Not tracked by Reddit API                 |
| `score`          | Net upvotes (upvotes minus downvotes)            | Score shown on the post                   |
| `comment_count`  | Number of comments                               | Total comments shown on the post          |
| `duration`       | Duration (empty, not applicable)                 | Not relevant for Reddit posts             |
| `upvote_ratio`   | Ratio of upvotes to total votes                  | Upvote percentage shown on the post       |
| `url`            | URL of the post                                  | Direct link to the post                   |
| `author`         | Username of the post author                      | Reddit username of the poster             |

#### 2. `comments_*.csv`
Contains comments on Reddit posts.

| Field            | Description                                      | Real-World Equivalent                     |
|------------------|--------------------------------------------------|-------------------------------------------|
| `comment_id`     | Unique ID of the comment                         | Reddit comment ID                         |
| `content_id`     | ID of the post the comment belongs to            | Links comment to its parent post          |
| `platform`       | Platform name (always "reddit")                  | Identifies the source as Reddit           |
| `content`        | Text content of the comment                      | Comment text as seen below the post       |
| `created_at`     | Date and time the comment was created            | Comment creation timestamp                |
| `score`          | Net upvotes on the comment                       | Score shown on the comment                |
| `author`         | Username of the comment author                   | Reddit username of the commenter          |
| `source_name`    | Subreddit name                                   | Subreddit where the comment was posted    |

## Setup and Usage

1. **YouTube Crawler**:
   - Obtain YouTube API credentials from the Google Cloud Console.
   - Save the OAuth credentials as `client_secret.json` in the project root.
   - Run the script:
     ```bash
     python youtube_crawler.py
     ```
   - Parameters (modify in `crawl_youtube_data`):
     - `region_code`: Region for trending videos (default: "US").
     - `max_videos`: Number of videos to collect (default: 10).
     - `max_comments`: Number of comments per video (default: 100).

2. **Reddit Crawler**:
   - Obtain Reddit API credentials from https://www.reddit.com/prefs/apps.
   - Update `reddit_crawler.py` with your `client_id`, `client_secret`, and `user_agent`.
   - Run the script:
     ```bash
     python reddit_crawler.py
     ```
   - Parameters (modify in the script):
     - `LIMIT_POSTS`: Number of posts per subreddit (default: 1000).
     - `LIMIT_COMMENTS`: Number of comments per post (default: 100).
     - `MAX_THREADS`: Number of concurrent threads (default: 2).
     - `subreddits_by_field`: List of subreddits to crawl.

3. **Output**:
   - CSV files are saved in the `Data` directory with timestamps.
   - Logs for Reddit are saved in `Data/reddit_crawler.log`.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.