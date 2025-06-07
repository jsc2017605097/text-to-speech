import requests
import time
import traceback
import re
import asyncio
import edge_tts
import unicodedata
from pydub import AudioSegment
import os
import sys

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
else:
    ffmpeg_path = "ffmpeg.exe"

AudioSegment.converter = ffmpeg_path

def slugify(text):
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

MODEL = "deepseek/deepseek-r1:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

def clean_for_tts(text):
    text = re.sub(r"\*\*.*?\*\*", "", text)
    text = re.sub(r"\*.*?\*", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"Camera.*?\.", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

async def create_audio_from_text(text, output_path, voice="vi-VN-HoaiMyNeural"):
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)

def merge_audio_files(output_file, pattern, num_parts):
    print("\n🔄 Đang gộp các phần âm thanh lại thành 1 file...")
    merged = AudioSegment.empty()

    for i in range(num_parts):
        part_file = pattern.format(i + 1)
        if os.path.exists(part_file):
            audio = AudioSegment.from_file(part_file, format="mp3")
            merged += audio
        else:
            print(f"⚠️ Không tìm thấy: {part_file}, bỏ qua.")

    merged.export(output_file, format="mp3")
    print(f"✅ Đã tạo file gộp: {output_file}")

def run_convert(topic, api_key, num_parts=12, log_func=print, voice="vi-VN-HoaiMyNeural"):
    log_func(f"🚀 Bắt đầu chạy với chủ đề: {topic}")
    log_func(f"🔑 Dùng API key: {api_key[:6]}***")
    log_func(f"📄 Số phần: {num_parts}")

    HEADERS = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    FILENAME_BASE = slugify(topic)
    output_dir = os.path.join("output", FILENAME_BASE)
    os.makedirs(output_dir, exist_ok=True)

    output_script = os.path.join(output_dir, f"{FILENAME_BASE}.txt")
    output_clean = os.path.join(output_dir, f"{FILENAME_BASE}-clean.txt")

    messages = []

    def call_openrouter_with_headers(messages):
        try:
            data = {
                "model": MODEL,
                "messages": messages
            }
            res = requests.post(API_URL, headers=HEADERS, json=data)

            if res.status_code != 200:
                log_func(f"❌ HTTP {res.status_code} - {res.text}")
                return None

            json_data = res.json()
            return json_data["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException:
            log_func("❌ Lỗi kết nối mạng hoặc API:")
            log_func(traceback.format_exc())
            return None
        except Exception:
            log_func("❌ Lỗi xử lý phản hồi từ OpenRouter:")
            log_func(traceback.format_exc())
            return None

    for i in range(num_parts):
        log_func(f"\n🟡 Đang lấy phần {i+1}...")

        if i == 0:
            prompt = (
                f"Viết phần mở đầu của một câu chuyện cảm động với chủ đề: '{topic}'. "
                "Viết bằng giọng văn tự sự, cảm xúc, có thể đọc to bằng giọng nói. "
                "Không dùng dấu * hoặc mô tả điện ảnh. Khoảng 500 từ. Dừng ở đoạn mở bài."
            )
            messages = [{"role": "user", "content": prompt}]
        else:
            if i == num_parts - 1:
                continuation = (
                    "Viết phần kết của câu chuyện. Kết lại bằng cảm xúc sâu lắng, đọng lại trong lòng người nghe. "
                    "Không lặp lại phần trước. Khoảng 500 từ."
                )
            else:
                continuation = (
                    "Viết tiếp phần thân câu chuyện, liền mạch với phần trước. "
                    "Không nhắc lại nội dung cũ. Khoảng 500 từ."
                )
            messages.append({"role": "user", "content": continuation})

        reply = call_openrouter_with_headers(messages)
        if not reply or len(reply.strip()) < 50:
            log_func(f"⚠️ Nội dung phần {i+1} rỗng hoặc quá ngắn, bỏ qua.")
            continue

        log_func(f"✅ Đã nhận phần {i+1}. Đang xử lý...")

        with open(output_script, "a", encoding="utf-8") as f:
            f.write(f"\n--- PHẦN {i+1} ---\n")
            f.write(reply.strip() + "\n")

        cleaned_text = clean_for_tts(reply)
        with open(output_clean, "a", encoding="utf-8") as f:
            f.write(f"\n--- PHẦN {i+1} ---\n")
            f.write(cleaned_text + "\n")

        audio_filename = os.path.join(output_dir, f"{FILENAME_BASE}-part-{i+1}.mp3")
        asyncio.run(create_audio_from_text(cleaned_text, audio_filename, voice=voice))
        log_func(f"🎧 Đã tạo file âm thanh: {audio_filename}")

        messages.append({"role": "assistant", "content": reply})

        time.sleep(10)

    final_audio_file = os.path.join(output_dir, f"{FILENAME_BASE}-final.mp3")
    merge_audio_files(final_audio_file, os.path.join(output_dir, f"{FILENAME_BASE}-part-{{}}.mp3"), num_parts)

    log_func(f"\n🎉 Hoàn tất. Kịch bản và audio đã lưu tại: {output_dir}")

    return final_audio_file

if __name__ == "__main__":
    TEST_API_KEY = "sk-or-v1-your_api_key_here"
    TEST_TOPIC = "Tại Sao Nhật Bản Gần Như Không Có Trộm Cắp?"
    run_convert(TEST_TOPIC, TEST_API_KEY)
