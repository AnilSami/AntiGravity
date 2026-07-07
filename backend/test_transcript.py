from youtube_transcript_api import YouTubeTranscriptApi

def test():
    video_id = "aAPpQC-3EyE"
    print(f"Testing transcript fetch for video {video_id}")
    try:
        api = YouTubeTranscriptApi()
        t_list = api.list(video_id)
        print("Successfully retrieved transcript list!")
        for t in t_list:
            print(f"- Language: {t.language}, Code: {t.language_code}, Is Generated: {t.is_generated}")
        
        # Try finding one
        t = t_list.find_transcript(['en', 'en-US'])
        print(f"Found transcript for {t.language_code}!")
        data = t.fetch()
        print(f"Fetched {len(data)} transcript lines. First line: {data[0]}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test()
