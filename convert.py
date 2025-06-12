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
import json

# Xác định đường dẫn ffmpeg khi đóng gói
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
else:
    # Cần đảm bảo ffmpeg.exe có trong PATH hoặc cùng thư mục với script
    ffmpeg_path = "ffmpeg.exe"
AudioSegment.converter = ffmpeg_path

MODEL = "deepseek/deepseek-r1:free" # Sử dụng model mà bạn đã chỉ định
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
    text = re.sub(r"[\(\)\[\]\{\}<>\"""''']", "", text)

    # Xóa các hướng dẫn như "Camera:..." hoặc "--- PHẦN X ---"
    text = re.sub(r"Camera.*?\.", "", text)
    text = re.split(r"(?m)^(Nếu bạn muốn|---\s*PHẦN\s*\d+\s*---)", text)[0]

    # Chỉ giữ lại các ký tự hợp lệ cho TTS: chữ cái (có dấu), số và dấu câu thường
    # Regex này giữ lại các ký tự tiếng Việt, chữ cái Latin, số, dấu câu cơ bản và khoảng trắng
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

def parse_detailed_outline(outline_content: str) -> list:
    """
    Parse detailed outline from JSON format or fallback to simple parsing
    """
    try:
        # Try to parse as JSON first
        outline_data = json.loads(outline_content)
        if isinstance(outline_data, list):
            return outline_data
        elif isinstance(outline_data, dict) and 'outline' in outline_data:
            return outline_data['outline']
    except:
        pass
    
    # Fallback to simple parsing
    outline_points = []
    lines = outline_content.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if it's a numbered section (1., 2., etc.)
        if re.match(r'^\d+\.', line):
            if current_section:
                outline_points.append(current_section)
            current_section = {
                'title': line,
                'content': '',
                'key_points': [],
                'emotion': '',
                'transition': ''
            }
        elif current_section and line:
            # Add content to current section
            if current_section['content']:
                current_section['content'] += ' ' + line
            else:
                current_section['content'] = line
    
    # Add the last section
    if current_section:
        outline_points.append(current_section)
    
    return outline_points

def run_convert(
    topic: str,
    api_key: str,
    num_parts: int = 12,
    log_func=print,
    voice: str = "vi-VN-HoaiMyNeural"
) -> str:
    log_func(f"🚀 Bắt đầu chạy với chủ đề: {topic}")
    log_func(f"🔑 Dùng API key: {api_key[:6]}***")
    log_func(f"📄 Số phần dự kiến: {num_parts}")

    HEADERS = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    base = slugify(topic)
    output_dir = os.path.join("output", base)
    os.makedirs(output_dir, exist_ok=True)

    output_script = os.path.join(output_dir, f"{base}.txt")
    output_clean = os.path.join(output_dir, f"{base}-clean.txt")
    output_outline = os.path.join(output_dir, f"{base}-outline.txt")

    # Clear previous output files if they exist for a fresh run
    for file_path in [output_script, output_clean, output_outline]:
        if os.path.exists(file_path):
            os.remove(file_path)

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

    # Step 1: Generate a detailed story outline
    log_func("\n📝 Đang tạo dàn ý câu chuyện chi tiết...")
    outline_prompt = f"""
Dựa trên chủ đề: '{topic}', hãy tạo một dàn ý câu chuyện cảm động CỰC KỲ CHI TIẾT để chia thành {num_parts} phân đoạn.

QUAN TRỌNG: Mỗi phân đoạn phải có:
1. Tiêu đề rõ ràng
2. Nội dung cụ thể cần kể (3-5 câu mô tả chi tiết)
3. Cảm xúc chính cần truyền tải
4. Cách chuyển tiếp sang phần tiếp theo
5. Nhân vật và tình huống cụ thể (nếu có)

Định dạng trả về:
```
1. [Tiêu đề phần 1]
   Nội dung: [Mô tả cụ thể 3-5 câu về những gì sẽ kể trong phần này]
   Cảm xúc: [Cảm xúc chính cần truyền tải]
   Chuyển tiếp: [Cách dẫn dắt sang phần tiếp theo]

2. [Tiêu đề phần 2]
   Nội dung: [Mô tả cụ thể...]
   Cảm xúc: [...]
   Chuyển tiếp: [...]

...và tiếp tục cho đến phần {num_parts}
```

Đảm bảo:
- Logic liên kết chặt chẽ giữa các phần
- Mỗi phần có mục đích rõ ràng trong tổng thể câu chuyện
- Cung cấp đủ chi tiết để viết từng phần mà không bị lạc chủ đề
- Cốt truyện phải có cung bậc cảm xúc rõ ràng (mở đầu → phát triển → cao trào → kết thúc)
"""

    outline_messages = [
        {
            "role": "system",
            "content": (
                "Bạn là trợ lý chuyên tạo dàn ý kịch bản chi tiết. "
                "Phải tạo dàn ý CỰC KỲ CHI TIẾT để người viết có thể dễ dàng triển khai từng phần "
                "mà không bị lạc chủ đề hoặc thiếu logic liên kết."
            )
        },
        {"role": "user", "content": outline_prompt}
    ]
    
    outline_content = call_openrouter(outline_messages)
    if not outline_content:
        log_func("❌ Không thể tạo dàn ý. Dừng chương trình.")
        return ""
    
    # Save detailed outline
    with open(output_outline, "w", encoding="utf-8") as f:
        f.write(f"DÀN Ý CHI TIẾT CHO: {topic}\n")
        f.write("="*50 + "\n\n")
        f.write(outline_content)
    
    log_func("✅ Đã tạo dàn ý chi tiết, lưu tại: " + output_outline)
    
    # Parse the detailed outline
    outline_sections = parse_detailed_outline(outline_content)
    if not outline_sections:
        # Fallback parsing for non-JSON format
        sections = re.split(r'\n(?=\d+\.)', outline_content.strip())
        outline_sections = []
        for section in sections:
            if section.strip():
                lines = section.strip().split('\n')
                title = lines[0] if lines else ""
                content = '\n'.join(lines[1:]) if len(lines) > 1 else ""
                outline_sections.append({
                    'title': title,
                    'content': content,
                    'full_text': section.strip()
                })
    
    log_func(f"📋 Đã phân tích {len(outline_sections)} phần trong dàn ý")
    
    # Store the full story text to pass context between parts
    full_story_text = ""
    
    for i in range(num_parts):
        log_func(f"\n🟡 Đang viết phần {i+1}/{num_parts}...")
        
        # Get the specific outline section for this part
        if i < len(outline_sections):
            current_section = outline_sections[i]
            section_guide = current_section.get('full_text', current_section.get('content', ''))
        else:
            # If we have fewer outline sections than num_parts, use the last one
            current_section = outline_sections[-1] if outline_sections else {}
            section_guide = "Tiếp tục phát triển câu chuyện theo logic tự nhiên"
        
        # Prepare context from previous parts (last 1500 chars to manage tokens)
        context_text = full_story_text[-1500:] if full_story_text else ""
        
        # Create detailed prompt based on part position
        if i == 0:
            user_prompt_content = f"""
Viết phần mở đầu của câu chuyện dựa trên chủ đề: '{topic}'

HƯỚNG DẪN CHI TIẾT CHO PHẦN NÀY:
{section_guide}

YÊU CẦU VIẾT:
- Khoảng 500 từ
- Giọng văn tự sự, cảm xúc, thu hút người nghe
- TUÂN THỦ CHẶT CHẼ nội dung trong hướng dẫn trên
- KHÔNG lệch khỏi chủ đề hoặc thêm thông tin không liên quan
- KHÔNG sử dụng ký hiệu đặc biệt, dấu ngoặc, markdown
- Chỉ dùng dấu câu thông thường: . , ! ? : ;

Chỉ trả về nội dung câu chuyện, không thêm giải thích hay meta.
"""
        elif i == num_parts - 1:
            user_prompt_content = f"""
Viết phần kết thúc của câu chuyện dựa trên chủ đề: '{topic}'

HƯỚNG DẪN CHI TIẾT CHO PHẦN NÀY:
{section_guide}

NỐI TIẾP TỪ PHẦN TRƯỚC:
{context_text}

YÊU CẦU VIẾT:
- Khoảng 500 từ
- Kết thúc có ý nghĩa, cảm động
- TUÂN THỦ CHẶT CHẼ nội dung trong hướng dẫn
- Nối tiếp tự nhiên từ phần trước, KHÔNG lặp lại nội dung
- KHÔNG sử dụng ký hiệu đặc biệt, dấu ngoặc, markdown
- Chỉ dùng dấu câu thông thường

Chỉ trả về nội dung câu chuyện, không thêm giải thích hay meta.
"""
        else:
            user_prompt_content = f"""
Viết tiếp phần {i+1} của câu chuyện dựa trên chủ đề: '{topic}'

HƯỚNG DẪN CHI TIẾT CHO PHẦN NÀY:
{section_guide}

NỐI TIẾP TỪ PHẦN TRƯỚC:
{context_text}

YÊU CẦU VIẾT:
- Khoảng 500 từ
- TUÂN THỦ CHẶT CHẼ nội dung trong hướng dẫn trên
- Nối tiếp tự nhiên từ phần trước, KHÔNG lặp lại nội dung
- Phát triển câu chuyện theo đúng hướng đã định
- KHÔNG sử dụng ký hiệu đặc biệt, dấu ngoặc, markdown
- Chỉ dùng dấu câu thông thường

Chỉ trả về nội dung câu chuyện, không thêm giải thích hay meta.
"""

        messages = [
            {
                "role": "system",
                "content": (
                    "Bạn là trợ lý viết kịch bản chuyên nghiệp. "
                    "PHẢI tuân thủ chặt chẽ hướng dẫn được cung cấp. "
                    "KHÔNG được lệch chủ đề hoặc tự ý thêm nội dung không liên quan. "
                    "CHỈ trả về nội dung câu chuyện, không thêm bất kỳ meta hay giải thích nào."
                )
            },
            {"role": "user", "content": user_prompt_content}
        ]

        reply = call_openrouter(messages)
        
        if not reply or len(reply.strip()) < 50:
            log_func(f"⚠️ Phần {i+1} rỗng hoặc quá ngắn, bỏ qua.")
            continue
        
        log_func(f"✅ Đã viết xong phần {i+1}. Đang xử lý...")
        
        # Update full story context
        full_story_text += reply.strip() + "\n"

        # Save raw content
        with open(output_script, "a", encoding="utf-8") as f:
            f.write(f"\n--- PHẦN {i+1} ---\n")
            f.write(reply.strip() + "\n")

        # Clean and save for TTS
        cleaned = clean_for_tts(reply)
        with open(output_clean, "a", encoding="utf-8") as f: 
            f.write(f"\n--- PHẦN {i+1} ---\n")
            f.write(cleaned + "\n")

        # Generate audio
        audio_file = os.path.join(output_dir, f"{base}-part-{i+1}.mp3")
        asyncio.run(create_audio_from_text(cleaned, audio_file, voice))
        log_func(f"🎧 Đã tạo file âm thanh: {audio_file}")

        time.sleep(10)  # Rate limiting

    # Merge all audio files
    final_audio = os.path.join(output_dir, f"{base}-final.mp3")
    merge_audio_files(
        final_audio,
        os.path.join(output_dir, f"{base}-part-{{}}.mp3"),
        num_parts
    )
    
    log_func(f"\n🎉 Hoàn tất!")
    log_func(f"📄 Dàn ý chi tiết: {output_outline}")
    log_func(f"📝 Kịch bản gốc: {output_script}")
    log_func(f"🧹 Kịch bản clean: {output_clean}")
    log_func(f"🎵 Audio hoàn chỉnh: {final_audio}")
    
    return final_audio


if __name__ == "__main__":
    TEST_KEY = "sk-or-v1-your_api_key_here"  # Thay thế bằng API key thật của bạn
    TEST_TOPIC = "Tại Sao Nhật Bản Gần Như Không Có Trộm Cắp?"
    
    # Test với 25 phần như bạn thường yêu cầu
    run_convert(TEST_TOPIC, TEST_KEY, num_parts=25)