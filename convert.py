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

# Xác định đường dẫn ffmpeg khi đóng gói
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
else:
    ffmpeg_path = "ffmpeg.exe"
AudioSegment.converter = ffmpeg_path

MODEL = "deepseek/deepseek-r1:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"


def slugify(text: str) -> str:
    # Chuyển Unicode về ASCII, lowercase, thay ký tự không alnum thành dấu '-'
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def clean_for_tts(text: str) -> str:
    """
    Làm sạch văn bản để chuyển sang TTS:
    - Giữ lại chữ cái (cả tiếng Việt), số và dấu câu cơ bản
    - Loại bỏ ký tự đặc biệt, dấu ngoặc, markdown...
    """
    import unicodedata

    # Chuẩn hóa Unicode để tránh ký tự lạ
    text = unicodedata.normalize('NFKC', text)

    # Loại bỏ markdown ** ** hoặc * *
    text = re.sub(r"\*\*.*?\*\*", "", text)
    text = re.sub(r"\*.*?\*", "", text)

    # Xóa nội dung trong ngoặc tròn ( ), vuông [ ], nhọn < >, ngoặc kép
    text = re.sub(r"[\(\)\[\]\{\}<>\"“”‘’']", "", text)

    # Xóa các hướng dẫn như "Camera:..." hoặc "--- PHẦN X ---"
    text = re.sub(r"Camera.*?\.", "", text)
    text = re.split(r"(?m)^(Nếu bạn muốn|---\s*PHẦN\s*\d+\s*---)", text)[0]

    # Chỉ giữ lại các ký tự hợp lệ cho TTS: chữ cái (có dấu), số và dấu câu thường
    text = re.sub(r"[^a-zA-ZÀ-ỹ0-9\s\.,!?:;\-…]", "", text)

    # Rút gọn khoảng trắng
    text = re.sub(r"\s+", " ", text).strip()

    return text



async def create_audio_from_text(text: str, output_path: str, voice: str = "vi-VN-HoaiMyNeural"):
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)


def merge_audio_files(output_file: str, pattern: str, num_parts: int):
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


def run_convert(
    topic: str,
    api_key: str,
    num_parts: int = 12,
    log_func=print,
    voice: str = "vi-VN-HoaiMyNeural"
) -> str:
    log_func(f"🚀 Bắt đầu chạy với chủ đề: {topic}")
    log_func(f"🔑 Dùng API key: {api_key[:6]}***")
    log_func(f"📄 Số phần: {num_parts}")

    HEADERS = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    base = slugify(topic)
    output_dir = os.path.join("output", base)
    os.makedirs(output_dir, exist_ok=True)

    output_script = os.path.join(output_dir, f"{base}.txt")
    output_clean = os.path.join(output_dir, f"{base}-clean.txt")

    def call_openrouter(messages):
        try:
            data = {"model": MODEL, "messages": messages}
            res = requests.post(API_URL, headers=HEADERS, json=data)
            if res.status_code != 200:
                log_func(f"❌ HTTP {res.status_code} - {res.text}")
                return None
            return res.json()["choices"][0]["message"]["content"]
        except Exception:
            log_func("❌ Lỗi khi gọi API:")
            log_func(traceback.format_exc())
            return None

    messages = []
    for i in range(num_parts):
        log_func(f"\n🟡 Đang lấy phần {i+1}...")
        if i == 0:
            # System message để model chỉ viết nội dung kể chuyện
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý chuyên viết kịch bản kể chuyện. "
                        "KHÔNG được thêm bất kỳ phần tóm tắt, phân tích, gợi ý hay meta nào."
                    )
                }
            ]
            prompt = (
                f"Viết phần mở đầu của câu chuyện cảm động với chủ đề: '{topic}'.\n\n"
                "Yêu cầu:\n"
                "- Viết giọng văn tự sự, cảm xúc, khoảng 500 từ.\n"
                "- KHÔNG sử dụng bất kỳ ký hiệu đặc biệt, dấu ngoặc kép, dấu ngoặc đơn, hoặc dấu ngoặc tròn.\n"
                "- KHÔNG dùng markdown (*, **, #, v.v.)\n"
                "- Giữ lại dấu chấm, phẩy, chấm than, chấm hỏi và các dấu câu thông thường.\n"
                "- Trả về nội dung thuần văn bản, sạch, không định dạng hoặc chú thích thêm.\n\n"
                "Chỉ trả lại nội dung kịch bản, không thêm phần meta hoặc hướng dẫn."
            )

            messages.append({"role": "user", "content": prompt})
        else:
            if i == num_parts - 1:
                cont = (
                    "Viết phần kết của câu chuyện, kết bằng cảm xúc sâu lắng, khoảng 500 từ.\n\n"
                    "Yêu cầu giống như phần trước:\n"
                    "- KHÔNG sử dụng dấu ngoặc, markdown hoặc ký hiệu đặc biệt.\n"
                    "- Chỉ trả lại văn bản sạch với dấu câu thông thường."
                )

            else:
                cont = (
                    "Viết tiếp phần thân của câu chuyện (liền mạch, không lặp lại), khoảng 500 từ.\n\n"
                    "Yêu cầu giống như phần trước:\n"
                    "- KHÔNG sử dụng dấu ngoặc, markdown hoặc ký hiệu đặc biệt.\n"
                    "- Chỉ trả lại văn bản sạch với dấu câu thông thường."
                )

            messages.append({"role": "user", "content": cont})

        reply = call_openrouter(messages)
        if not reply or len(reply.strip()) < 50:
            log_func(f"⚠️ Phần {i+1} rỗng hoặc quá ngắn, bỏ qua.")
            continue
        log_func(f"✅ Đã nhận phần {i+1}. Đang xử lý...")
        with open(output_script, "a", encoding="utf-8") as f:
            f.write(f"\n--- PHẦN {i+1} ---\n")
            f.write(reply.strip() + "\n")

        cleaned = clean_for_tts(reply)
        with open(output_clean, "a", encoding="utf-8") as f:
            f.write(f"\n--- PHẦN {i+1} ---\n")
            f.write(cleaned + "\n")

        audio_file = os.path.join(output_dir, f"{base}-part-{i+1}.mp3")
        asyncio.run(create_audio_from_text(cleaned, audio_file, voice))
        log_func(f"🎧 Đã tạo file âm thanh: {audio_file}")

        messages.append({"role": "assistant", "content": reply})
        time.sleep(10)

    final_audio = os.path.join(output_dir, f"{base}-final.mp3")
    merge_audio_files(
        final_audio,
        os.path.join(output_dir, f"{base}-part-{{}}.mp3"),
        num_parts
    )
    log_func(f"\n🎉 Hoàn tất. Audio gộp tại: {final_audio}")
    return final_audio


if __name__ == "__main__":
    TEST_KEY = "sk-or-v1-your_api_key_here"
    TEST_TOPIC = "Tại Sao Nhật Bản Gần Như Không Có Trộm Cắp?"
    run_convert(TEST_TOPIC, TEST_KEY)
