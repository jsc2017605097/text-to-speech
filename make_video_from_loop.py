import os
import subprocess
import math
import re
from moviepy.editor import VideoFileClip, AudioFileClip


def make_video_loop_with_ffmpeg(video_path, audio_path, output_path, log_func=print, music_path=None, music_volume=30):
    # Kiểm tra tồn tại file đầu vào
    if not os.path.exists(video_path) or not os.path.exists(audio_path):
        log_func("❌ Không tìm thấy file video hoặc audio.")
        return

    log_func("🔄 Đang tính toán...")

    try:
        # Lấy duration của video chính và audio chính
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path)
        video_duration = video_clip.duration
        audio_duration = audio_clip.duration
        video_clip.close()
        audio_clip.close()

        # Tính số lần loop video để đủ dài cho audio chính
        video_loops = math.ceil(audio_duration / video_duration) - 1

        # Nếu có audio nền, tính số lần loop cho nó
        if music_path and os.path.exists(music_path):
            music_clip = AudioFileClip(music_path)
            music_duration = music_clip.duration
            music_clip.close()
            music_loops = math.ceil(audio_duration / music_duration) - 1
        else:
            music_loops = 0

        log_func(f"📺 Video: {video_duration:.2f}s (loop {video_loops + 1} lần)")
        if music_path:
            log_func(f"🎧 Music nền: {music_duration:.2f}s (loop {music_loops + 1} lần), volume: {music_volume}%")
        log_func(f"🎵 Audio chính: {audio_duration:.2f}s")

        ffmpeg_path = os.path.abspath("ffmpeg.exe")

        # Xây dựng command FFmpeg với stream_loop cho video và optional music
        cmd = [
            ffmpeg_path,
            "-stream_loop", str(video_loops), "-i", video_path,
            "-i", audio_path
        ]
        if music_path:
            cmd.extend(["-stream_loop", str(music_loops), "-i", music_path])

        # Filter video: scale + pad
        filter_video = (
            "scale=1280:720:force_original_aspect_ratio=decrease,"  
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2[outv]"
        )

        # Filter audio: mix music và audio chính giữ nguyên volume chính
        if music_path:
            music_vol = music_volume / 100
            filter_audio = (
                f"[2:a]volume={music_vol}[bg];"
                "[1:a][bg]"
                "amix=inputs=2:duration=longest:dropout_transition=2:normalize=0[outa]"
            )
        else:
            filter_audio = "[1:a]anull[outa]"

        filter_complex = f"{filter_video};{filter_audio}"

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "aac",
            "-to", str(audio_duration),  # Cắt đúng bằng độ dài audio chính
            "-y",
            output_path
        ])

        log_func("🎬 Bắt đầu render video...")

        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Đọc stderr để hiển thị tiến độ
        for line in process.stderr:
            line = line.strip()
            if "time=" in line:
                m = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", line)
                if m:
                    h, mi, s = m.groups()
                    current_time = int(h)*3600 + int(mi)*60 + float(s)
                    percent = (current_time / audio_duration) * 100
                    log_func(f"⏳ Render: {percent:.2f}%")

        process.wait()
        if process.returncode == 0:
            log_func(f"\n✅ Video đã tạo tại: {output_path}")
        else:
            log_func("❌ FFmpeg thất bại.")

    except Exception as e:
        log_func(f"❌ Lỗi render video: {e}")


if __name__ == "__main__":
    # Ví dụ gọi hàm
    make_video_loop_with_ffmpeg(
        video_path="video.mp4",
        audio_path="audio.mp3",
        output_path="output.mp4",
        music_path=None,       # Đường dẫn đến audio nền hoặc None
        music_volume=30        # Phần trăm âm lượng nền
    )
