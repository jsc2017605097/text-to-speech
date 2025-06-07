import os
import subprocess
import math
from moviepy.editor import VideoFileClip, AudioFileClip
import re

VIDEO_PATH = "video.mp4"
AUDIO_PATH = "audio.mp3"
OUTPUT_PATH = "final_video.mp4"

def make_video_loop_with_ffmpeg(video_path, audio_path, output_path):
    if not os.path.exists(video_path) or not os.path.exists(audio_path):
        print("❌ Không tìm thấy file video hoặc audio.")
        return

    print("🔄 Đang tính toán...")

    # Lấy thông tin duration
    video_clip = VideoFileClip(video_path)
    audio_clip = AudioFileClip(audio_path)

    video_duration = video_clip.duration
    audio_duration = audio_clip.duration
    fps = video_clip.fps or 30

    # Tính số lần loop cần thiết
    num_loops = math.ceil(audio_duration / video_duration)

    print(f"📺 Video duration: {video_duration:.2f}s")
    print(f"🎵 Audio duration: {audio_duration:.2f}s")
    print(f"➡️ Cần lặp video {num_loops} lần")

    video_clip.close()
    audio_clip.close()

    ffmpeg_path = os.path.abspath("ffmpeg.exe")

    # Tạo chuỗi concat input
    input_args = []
    for i in range(num_loops):
        input_args.extend(["-i", video_path])
    input_args.extend(["-i", audio_path])

    # Filter ghép video
    filter_parts = [f"[{i}:v]" for i in range(num_loops)]
    filter_complex = f"{''.join(filter_parts)}concat=n={num_loops}:v=1:a=0,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2[outv]"

    cmd = [
        ffmpeg_path,
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", f"{num_loops}:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "aac",
        "-shortest",
        "-y",
        output_path
    ]

    print("🔄 Đang render video (có thể mất thời gian)...")

    try:
        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        for line in process.stderr:
            line = line.strip()
            if "time=" in line:
                match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
                if match:
                    timestamp = match.group(1)
                    try:
                        h, m, s = map(float, timestamp.replace(":", " ").split())
                        current_time = h * 3600 + m * 60 + s
                        percent = (current_time / audio_duration) * 100
                        print(f"⏳ Render: {percent:.2f}%\r", end="")
                    except:
                        pass

        process.wait()
        if process.returncode == 0:
            print(f"\n✅ Video đã được tạo tại: {output_path}")
        else:
            print(f"\n❌ FFmpeg thất bại.")

    except Exception as e:
        print(f"❌ Lỗi không mong muốn: {e}")


if __name__ == "__main__":
    make_video_loop_with_ffmpeg(VIDEO_PATH, AUDIO_PATH, OUTPUT_PATH)
