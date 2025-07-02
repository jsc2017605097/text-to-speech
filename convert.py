import asyncio
import edge_tts
import unicodedata
from pydub import AudioSegment
import os
import sys
import re
import time
import random

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
else:
    ffmpeg_path = "ffmpeg.exe"
AudioSegment.converter = ffmpeg_path


def clean_for_tts(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r"\*\*.*?\*\*", "", text)
    text = re.sub(r"\*.*?\*", "", text)
    text = re.sub(r"[\(\)\[\]\{\}<>\"""''']", "", text)
    text = re.sub(r"Camera.*?\.", "", text)
    text = re.sub(r"(?m)^---.*?---", "", text)
    text = re.sub(r"[^a-zA-ZÀ-ỹ0-9\s\.,!?:;\-…#]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_text_by_chapters(text: str) -> list[tuple[str, str]]:
    pattern = r"#\s*(.*?)\s*#"
    matches = list(re.finditer(pattern, text))
    parts = []

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            parts.append((title, content))
    return parts


async def create_audio_from_text(text: str, output_path: str, voice: str = "vi-VN-NamMinhNeural", rate: str = "0%"):
    try:
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"❌ Lỗi khi tạo audio: {e}")
        return False


def merge_audio_files(output_file: str, audio_files: list):
    print(f"\n🔄 Đang gộp {len(audio_files)} file audio...")
    merged = AudioSegment.empty()
    successful_files = 0

    for audio_file in audio_files:
        if os.path.exists(audio_file):
            try:
                audio = AudioSegment.from_file(audio_file, format="mp3")
                merged += audio
                successful_files += 1
                print(f"✅ Đã thêm: {os.path.basename(audio_file)}")
            except Exception as e:
                print(f"⚠️ Lỗi khi đọc {audio_file}: {e}")
        else:
            print(f"⚠️ Không tìm thấy: {audio_file}")

    if successful_files > 0:
        merged.export(output_file, format="mp3")
        print(f"✅ Đã tạo file gộp: {output_file}")
        print(f"📊 Đã gộp {successful_files}/{len(audio_files)} file thành công")
        return True
    else:
        print("❌ Không có file audio nào để gộp")
        return False


def convert_text_file_to_speech(
    input_file: str,
    output_dir: str = None,
    voice: str = "vi-VN-NamMinhNeural",
    rate: str = "0%",
    log_func=print
) -> str:
    if not os.path.exists(input_file):
        log_func(f"❌ Không tìm thấy file: {input_file}")
        return ""

    if output_dir is None:
        output_dir = os.path.dirname(input_file)
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(input_file))[0]

    log_func(f"🚀 Bắt đầu convert: {input_file}")
    log_func(f"🎤 Giọng đọc: {voice} | Tốc độ: {rate}")
    log_func(f"📁 Thư mục output: {output_dir}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            original_text = f.read()
    except Exception as e:
        log_func(f"❌ Lỗi khi đọc file: {e}")
        return ""

    if not original_text.strip():
        log_func("❌ File text rỗng")
        return ""

    cleaned_text = clean_for_tts(original_text)
    log_func(f"🧹 Độ dài text sau làm sạch: {len(cleaned_text)} ký tự")

    cleaned_file = os.path.join(output_dir, f"{base_name}-cleaned.txt")
    with open(cleaned_file, 'w', encoding='utf-8') as f:
        f.write(cleaned_text)
    log_func(f"✅ Đã lưu text làm sạch: {cleaned_file}")

    chapter_parts = split_text_by_chapters(cleaned_text)
    if not chapter_parts:
        log_func("❌ Không phát hiện chương nào. Đảm bảo mỗi chương bắt đầu bằng dòng: # tiêu đề #")
        return ""

    text_parts = [content for _, content in chapter_parts]
    chapter_titles = [title for title, _ in chapter_parts]
    log_func(f"📚 Đã phát hiện {len(chapter_titles)} chương.")

    audio_files = []
    for i, part in enumerate(text_parts, 1):
        log_func(f"\n🟡 Đang xử lý chương {i}/{len(text_parts)}: {chapter_titles[i-1]}")
        part_audio = os.path.join(output_dir, f"{base_name}-part-{i:03d}.mp3")
        success = asyncio.run(create_audio_from_text(part, part_audio, voice, rate))
        if success:
            log_func(f"✅ Đã tạo: {os.path.basename(part_audio)}")
            audio_files.append(part_audio)
        else:
            log_func(f"❌ Lỗi tạo chương {i}")

        delay = random.uniform(1.5, 3.0)
        log_func(f"⏳ Chờ {delay:.1f} giây để tránh spam...")
        time.sleep(delay)

    if not audio_files:
        log_func("❌ Không tạo được file audio nào")
        return ""

    final_audio = os.path.join(output_dir, f"{base_name}-final.mp3")
    if merge_audio_files(final_audio, audio_files):
        log_func(f"\n🎉 Hoàn thành!")
        log_func(f"🎵 File audio cuối cùng: {final_audio}")

        try:
            timestamps = []
            current_time_ms = 0
            for audio_file in audio_files:
                seg = AudioSegment.from_file(audio_file)
                timestamps.append(current_time_ms)
                current_time_ms += len(seg)

            chapter_file = os.path.join(output_dir, f"{base_name}-chapters.txt")
            with open(chapter_file, "w", encoding="utf-8") as f:
                for i, t in enumerate(timestamps):
                    minutes = int(t // 60000)
                    seconds = int((t % 60000) / 1000)
                    f.write(f"{minutes:02}:{seconds:02} {chapter_titles[i]}\n")
            log_func(f"📖 Đã tạo chapter file: {chapter_file}")
        except Exception as e:
            log_func(f"⚠️ Lỗi khi tạo chapter file: {e}")

        return final_audio
    else:
        return ""
