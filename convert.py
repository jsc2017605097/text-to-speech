import requests
import time
import traceback
import re
import asyncio
import edge_tts
import unicodedata
from pydub import AudioSegment
import os

# === Cấu hình chủ đề và số phần ===
TOPIC = "Người mẹ bán rau già nuôi con đỗ đại học"
NUM_PARTS = 2  # <== Số phần muốn tạo

# === Slugify để tạo tên thư mục an toàn ===
def slugify(text):
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

FILENAME_BASE = slugify(TOPIC)

# === Cấu hình OpenRouter ===
API_KEY = "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"
MODEL = "deepseek/deepseek-r1:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

INITIAL_PROMPT = (
    f"Viết phần đầu tiên của một câu chuyện cảm động với chủ đề: '{TOPIC}'. "
    "Hãy viết bằng văn phong tự sự, có thể đọc to bằng giọng nói. "
    "Tránh dùng dấu * hoặc mô tả điện ảnh như Camera, không có lời thoại dạng kịch bản. "
    "Viết khoảng 500 từ, dừng đúng đoạn. Tôi sẽ yêu cầu phần tiếp theo sau."
)

# === Làm sạch văn bản cho TTS ===
def clean_for_tts(text):
    text = re.sub(r"\*\*.*?\*\*", "", text)
    text = re.sub(r"\*.*?\*", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"Camera.*?\.", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# === Gọi OpenRouter ===
def call_openrouter(messages):
    try:
        data = {
            "model": MODEL,
            "messages": messages
        }
        res = requests.post(API_URL, headers=HEADERS, json=data)

        if res.status_code != 200:
            print(f"❌ HTTP {res.status_code} - {res.text}")
            return None

        json_data = res.json()
        return json_data["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException:
        print("❌ Lỗi kết nối mạng hoặc API:")
        print(traceback.format_exc())
        return None
    except Exception:
        print("❌ Lỗi xử lý phản hồi từ OpenRouter:")
        print(traceback.format_exc())
        return None

# === Chuyển văn bản thành file âm thanh ===
async def create_audio_from_text(text, output_path):
    communicate = edge_tts.Communicate(text=text, voice="vi-VN-HoaiMyNeural")
    await communicate.save(output_path)

# === Gộp các file âm thanh ===
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

# === Luồng chính ===
def main():
    messages = [{"role": "user", "content": INITIAL_PROMPT}]

    # Tạo thư mục riêng cho mỗi chủ đề
    output_dir = os.path.join("output", FILENAME_BASE)
    os.makedirs(output_dir, exist_ok=True)

    output_script = os.path.join(output_dir, f"{FILENAME_BASE}.txt")
    output_clean = os.path.join(output_dir, f"{FILENAME_BASE}-clean.txt")

    for i in range(NUM_PARTS):
        print(f"\n🟡 Đang lấy phần {i+1}...")

        reply = call_openrouter(messages)
        if not reply or len(reply.strip()) < 50:
            print(f"⚠️ Nội dung phần {i+1} rỗng hoặc quá ngắn, bỏ qua.")
            continue

        print(f"✅ Đã nhận phần {i+1}. Đang xử lý...")

        # Ghi bản gốc
        with open(output_script, "a", encoding="utf-8") as f:
            f.write(f"\n--- PHẦN {i+1} ---\n")
            f.write(reply.strip() + "\n")

        # Ghi bản sạch
        cleaned_text = clean_for_tts(reply)
        with open(output_clean, "a", encoding="utf-8") as f:
            f.write(f"\n--- PHẦN {i+1} ---\n")
            f.write(cleaned_text + "\n")

        # Ghi file âm thanh
        audio_filename = os.path.join(output_dir, f"{FILENAME_BASE}-part-{i+1}.mp3")
        asyncio.run(create_audio_from_text(cleaned_text, audio_filename))
        print(f"🎧 Đã tạo file âm thanh: {audio_filename}")

        # Chuỗi hội thoại tiếp nối
        messages.append({"role": "assistant", "content": reply})
        messages.append({
            "role": "user",
            "content": "Viết tiếp phần sau, liền mạch cảm xúc và nội dung, không lặp lại phần trước."
        })

        time.sleep(10)

    # Gộp audio cuối cùng
    final_audio_file = os.path.join(output_dir, f"{FILENAME_BASE}-final.mp3")
    merge_audio_files(final_audio_file, os.path.join(output_dir, f"{FILENAME_BASE}-part-{{}}.mp3"), NUM_PARTS)

    print(f"\n🎉 Hoàn tất. Kịch bản và audio đã lưu tại: {output_dir}")

if __name__ == "__main__":
    main()
