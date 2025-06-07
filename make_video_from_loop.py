import os
import subprocess
import math
from moviepy.editor import VideoFileClip, AudioFileClip
import re

def make_video_loop_with_ffmpeg(video_path, audio_path, output_path, log_func=print, music_path=None, music_volume=30):
    import os
    import subprocess
    import math
    import re
    from moviepy.editor import VideoFileClip, AudioFileClip

    if not os.path.exists(video_path) or not os.path.exists(audio_path):
        log_func("❌ Không tìm thấy file video hoặc audio.")
        return

    log_func("🔄 Đang tính toán...")

    try:
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path)

        video_duration = video_clip.duration
        audio_duration = audio_clip.duration

        video_clip.close()
        audio_clip.close()

        num_loops = math.ceil(audio_duration / video_duration) - 1

        log_func(f"📺 Video: {video_duration:.2f}s, 🎵 Audio: {audio_duration:.2f}s, 🔁 Loop: {num_loops + 1}")

        ffmpeg_path = os.path.abspath("ffmpeg.exe")

        cmd = [
            ffmpeg_path,
            "-stream_loop", str(num_loops),
            "-i", video_path,
            "-i", audio_path
        ]

        if music_path:
            cmd.extend(["-i", music_path])

        filter_video = (
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2[outv]"
        )

        if music_path:
            music_vol = music_volume / 100
            filter_audio = (
                f"[2:a]volume={music_vol}[bg];"
                f"[1:a][bg]amix=inputs=2:duration=longest:dropout_transition=2[outa]"
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
            "-to", str(audio_duration),   # Cắt video chính xác bằng thời gian audio
            "-y",
            output_path
        ])

        log_func("🎬 Bắt đầu render video...")

        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        for line in process.stderr:
            line = line.strip()
            if "time=" in line:
                match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", line)
                if match:
                    h, m, s = match.groups()
                    current_time = int(h)*3600 + int(m)*60 + float(s)
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
    make_video_loop_with_ffmpeg("video.mp4", "audio.mp3", "output.mp4")
