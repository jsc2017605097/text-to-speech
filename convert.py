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

MODEL = "deepseek/deepseek-r1:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

def get_mc_info(voice: str) -> dict:
    """
    Trả về thông tin MC dựa trên giọng đọc được chọn
    """
    voice_to_mc = {
        "vi-VN-NamMinhNeural": {
            "name": "Hoàng Minh",
            "gender": "nam",
            "description": "một người dẫn chương trình nam chuyên nghiệp, giọng điệu ấm áp, uy tín"
        },
        "vi-VN-HoaiMyNeural": {
            "name": "Hoài My", 
            "gender": "nữ",
            "description": "một người dẫn chương trình nữ chuyên nghiệp, giọng điệu ngọt ngào, thân thiện"
        }
    }
    
    return voice_to_mc.get(voice, {
        "name": "MC",
        "gender": "chưa xác định", 
        "description": "một người dẫn chương trình chuyên nghiệp"
    })

def generate_dynamic_opening(topic: str, channel_name: str, call_openrouter_func) -> str:
    """
    Tạo lời mở đầu động dựa trên chủ đề cụ thể
    """
    opening_prompt = f"""
Tạo một lời mở đầu cực kỳ hấp dẫn và có cảm xúc cho chủ đề: "{topic}"

YÊU CÁU QUAN TRỌNG:
1. KHÔNG sử dụng tên MC hay giới thiệu kênh một cách cứng nhắc
2. Bắt đầu bằng một câu hỏi gây tò mò HOẶC một tình huống/sự thật gây sốc liên quan trực tiếp đến chủ đề
3. Tạo cảm giác đồng cảm, khiến người nghe cảm thấy: "Đúng rồi, tôi cũng từng thắc mắc về điều này!"
4. Sử dụng ngôn ngữ gần gũi, không quá trang trọng
5. Tối đa 3-4 câu, mỗi câu phải có tác dụng níu chân người xem
6. Kết thúc bằng việc hứa hẹn sẽ tiết lộ điều gì đó thú vị

VÍ DỤ PHONG CÁCH MONG MUỐN:
- "Bạn có bao giờ thắc mắc tại sao...?"
- "Hãy tưởng tượng bạn đang đi trên đường ở Tokyo lúc 2 giờ sáng..."
- "Điều gì khiến một quốc gia có thể..."
- "Có một sự thật mà 99% chúng ta không biết..."

TUYỆT ĐỐI TRÁNH:
- "Xin chào quý vị khán giả..."
- "Tôi là MC..."
- "Chào mừng đến với chương trình..."
- "Hôm nay chúng ta sẽ cùng tìm hiểu..."

Chỉ trả về nội dung lời mở đầu, không giải thích thêm.
"""

    messages = [
        {
            "role": "system", 
            "content": "Bạn là chuyên gia viết lời mở đầu hấp dẫn cho video YouTube, biết cách tạo ra những câu hook mạnh mẽ để giữ chân người xem từ giây đầu tiên."
        },
        {"role": "user", "content": opening_prompt}
    ]
    
    opening = call_openrouter_func(messages)
    return opening.strip() if opening else ""

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
    - Loại bỏ các câu mời xem "tuần sau", "tập tiếp theo"
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
    
    # LOẠI BỎ CÁC CÂU MỜI XEM TUẦN SAU/TẬP TIẾP THEO
    text = re.sub(r".*?(tuần sau|tập tiếp theo|chương trình tuần tới|hẹn gặp lại.*?tuần|xem tiếp.*?tuần).*?[\.\!]", "", text, flags=re.IGNORECASE)
    text = re.sub(r".*?(kính mời.*?xem.*?vào).*?[\.\!]", "", text, flags=re.IGNORECASE)
    text = re.sub(r".*?(đừng quên theo dõi|đăng ký kênh).*?[\.\!]", "", text, flags=re.IGNORECASE)

    # Chỉ giữ lại các ký tự hợp lệ cho TTS: chữ cái (có dấu), số, dấu câu cơ bản và khoảng trắng
    text = re.sub(r"[^a-zA-ZÀ-ỹ0-9\s\.,!?:;\-…]", "", text)

    # Rút gọn khoảng trắng
    text = re.sub(r"\s+", " ", text).strip()

    return text

async def create_audio_from_text(text: str, output_path: str, voice: str = "vi-VN-NamMinhNeural"):
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

def generate_chapter_timestamps(outline_sections: list, output_dir: str, base_filename: str):
    chapter_lines = []
    current_time_ms = 0

    for idx, section in enumerate(outline_sections):
        # Load thời lượng audio tương ứng
        audio_file = os.path.join(output_dir, f"{base_filename}-part-{idx+1}.mp3")
        if not os.path.exists(audio_file):
            continue

        audio = AudioSegment.from_file(audio_file)
        timestamp = time.strftime('%M:%S', time.gmtime(current_time_ms // 1000))
        
        # Lấy tiêu đề ngắn gọn
        title_line = section.get('title', f"Phần {idx+1}")
        chapter_lines.append(f"{timestamp} - {title_line.strip()}")

        current_time_ms += len(audio)

    chapter_text = '\n'.join(chapter_lines)
    chapter_file = os.path.join(output_dir, f"{base_filename}-chapters.txt")
    with open(chapter_file, "w", encoding="utf-8") as f:
        f.write(chapter_text)

    return chapter_file


def run_convert(
    topic: str,
    api_key: str,
    num_parts: int = 12,
    log_func=print,
    voice: str = "vi-VN-NamMinhNeural",
    channel_name: str = "Tinh Hoa Á Đông"
) -> str:
    log_func(f"🚀 Bắt đầu chạy với chủ đề: {topic}")
    log_func(f"🔑 Dùng API key: {api_key[:6]}***")
    log_func(f"📄 Số phần dự kiến: {num_parts}")
    log_func(f"🎤 Giọng đọc: {voice}")
    log_func(f"📺 Kênh: {channel_name}")

    # Lấy thông tin MC dựa trên giọng đọc
    mc_info = get_mc_info(voice)
    mc_name = mc_info["name"]
    mc_gender = mc_info["gender"]
    mc_description = mc_info["description"]
    
    log_func(f"🎭 MC được chọn: {mc_name} ({mc_gender})")

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

QUAN TRỌNG: Đây là một chương trình LIỀN MẠCH được ghép thành 1 file audio duy nhất, KHÔNG phải {num_parts} tập riêng biệt.

Mỗi phân đoạn phải có:
1. Tiêu đề rõ ràng
2. Nội dung cụ thể cần kể (3-5 câu mô tả chi tiết)
3. Cảm xúc chính cần truyền tải
4. Cách chuyển tiếp sang phần tiếp theo (LIỀN MẠCH, không có "tuần sau")
5. Nhân vật và tình huống cụ thể (nếu có)

Định dạng trả về:
```
1. [Tiêu đề phần 1]
   Nội dung: [Mô tả cụ thể 3-5 câu về những gì sẽ kể trong phần này]
   Cảm xúc: [Cảm xúc chính cần truyền tải]
   Chuyển tiếp: [Cách dẫn dắt sang phần tiếp theo NGAY LẬP TỨC]

2. [Tiêu đề phần 2]
   Nội dung: [Mô tả cụ thể...]
   Cảm xúc: [...]
   Chuyển tiếp: [...]

...và tiếp tục cho đến phần {num_parts}
```

Đảm bảo:
- Logic liên kết chặt chẽ giữa các phần LIỀN MẠCH
- Mỗi phần chuyển tiếp tự nhiên sang phần tiếp theo trong cùng 1 chương trình
- Cung cấp đủ chi tiết để viết từng phần mà không bị lạc chủ đề
- Cốt truyện có cung bậc cảm xúc rõ ràng (mở đầu → phát triển → cao trào → kết thúc)
"""

    outline_messages = [
        {
            "role": "system",
            "content": (
                "Bạn là trợ lý chuyên tạo dàn ý kịch bản chi tiết cho chương trình LIỀN MẠCH. "
                "Phải tạo dàn ý CỰC KỲ CHI TIẾT để người viết có thể dễ dàng triển khai từng phần "
                "mà không bị lạc chủ đề hoặc thiếu logic liên kết. "
                "KHÔNG được có bất kỳ mention nào về 'tuần sau', 'tập tiếp theo' vì đây là 1 chương trình liền mạch."
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
        f.write(f"KÊNH: {channel_name}\n")
        f.write(f"MC: {mc_name} ({mc_gender})\n")
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
    
    # Generate dynamic opening
    log_func("\n🎭 Đang tạo lời mở đầu động và hấp dẫn...")
    dynamic_opening = generate_dynamic_opening(topic, channel_name, call_openrouter)
    if dynamic_opening:
        log_func("✅ Đã tạo lời mở đầu động")
    else:
        log_func("⚠️ Không thể tạo lời mở đầu động, sẽ dùng mặc định")
        dynamic_opening = ""
    
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
            # Use dynamic opening for first part
            opening_instruction = f"""
SỬ DỤNG LỜI MỞ ĐẦU ĐỘNG SAU ĐÂY:
"{dynamic_opening}"

Sau đó tiếp tục phát triển nội dung theo hướng dẫn bên dưới.
""" if dynamic_opening else """
Tạo lời mở đầu hấp dẫn bằng cách:
- Bắt đầu với câu hỏi gây tò mò hoặc tình huống thú vị
- KHÔNG dùng "Xin chào quý vị khán giả" hay giới thiệu cứng nhắc
- Tạo cảm giác đồng cảm ngay từ câu đầu tiên
"""

            user_prompt_content = f"""
Viết phần mở đầu của chương trình dựa trên chủ đề: '{topic}'

{opening_instruction}

HƯỚNG DẪN CHI TIẾT CHO PHẦN NÀY:
{section_guide}

YÊU CẦU VIẾT:
- Khoảng 500 từ
- Giọng điệu chuyên nghiệp nhưng gần gũi, tạo kết nối với khán giả
- TUÂN THỦ CHẶT CHẼ nội dung trong hướng dẫn trên
- KHÔNG lệch khỏi chủ đề hoặc thêm thông tin không liên quan
- KHÔNG sử dụng ký hiệu đặc biệt, dấu ngoặc, markdown
- Chỉ dùng dấu câu thông thường: . , ! ? : ;
- ĐÂY LÀ CHƯƠNG TRÌNH LIỀN MẠCH, KHÔNG được có "tuần sau", "tập tiếp theo"
- Có thể nhắc đến "{channel_name}" một cách tự nhiên nếu phù hợp, nhưng không bắt buộc

Chỉ trả về nội dung câu chuyện, không thêm giải thích hay meta.
"""
        elif i == num_parts - 1:
            user_prompt_content = f"""
Viết phần kết thúc của chương trình dựa trên chủ đề: '{topic}'

HƯỚNG DẪN CHI TIẾT CHO PHẦN NÀY:
{section_guide}

NỐI TIẾP TỪ PHẦN TRƯỚC:
{context_text}

YÊU CẦU VIẾT:
- Khoảng 500 từ
- Kết thúc có ý nghĩa, cảm động
- Có lời cảm ơn khán giả ấm áp và tự nhiên: "Cảm ơn các bạn đã dành thời gian lắng nghe. Hy vọng những chia sẻ hôm nay đã mang lại cho các bạn những góc nhìn thú vị. Hẹn gặp lại các bạn trong những chương trình tiếp theo!"
- Giọng điệu chuyên nghiệp, ấm áp, chân thành
- TUÂN THỦ CHẶT CHẾ nội dung trong hướng dẫn
- Nối tiếp tự nhiên từ phần trước, KHÔNG lặp lại nội dung
- KHÔNG sử dụng ký hiệu đặc biệt, dấu ngoặc, markdown
- Chỉ dùng dấu câu thông thường
- ĐÂY LÀ KẾT THÚC CHƯƠNG TRÌNH, KHÔNG có "tuần sau"

Chỉ trả về nội dung câu chuyện, không thêm giải thích hay meta.
"""
        else:
            user_prompt_content = f"""
Viết tiếp phần {i+1} của chương trình dựa trên chủ đề: '{topic}'

HƯỚNG DẪN CHI TIẾT CHO PHẦN NÀY:
{section_guide}

NỐI TIẾP TỪ PHẦN TRƯỚC:
{context_text}

YÊU CẦU VIẾT:
- Khoảng 500 từ
- Giọng điệu chuyên nghiệp, hấp dẫn, tạo kết nối với khán giả
- TUÂN THỦ CHẶT CHẾ nội dung trong hướng dẫn trên
- Nối tiếp tự nhiên từ phần trước, KHÔNG lặp lại nội dung
- Phát triển câu chuyện theo đúng hướng đã định
- Có thể sử dụng các câu giao tiếp với khán giả như "Bạn có biết rằng...", "Điều thú vị là...", "Hãy cùng khám phá..."
- KHÔNG sử dụng ký hiệu đặc biệt, dấu ngoặc, markdown
- Chỉ dùng dấu câu thông thường
- ĐÂY LÀ CHƯƠNG TRÌNH LIỀN MẠCH, TUYỆT ĐỐI KHÔNG được có "tuần sau", "tập tiếp theo", "kính mời xem tiếp"
- Chuyển tiếp tự nhiên sang phần tiếp theo TRONG CÙNG CHƯƠNG TRÌNH

Chỉ trả về nội dung câu chuyện, không thêm giải thích hay meta.
"""

        messages = [
            {
                "role": "system",
                "content": (
                    f"Bạn là một người dẫn chương trình chuyên nghiệp của kênh '{channel_name}', "
                    "có khả năng kể chuyện hấp dẫn và tạo kết nối mạnh mẽ với khán giả. "
                    "PHẢI tuân thủ chặt chẽ hướng dẫn được cung cấp. "
                    "KHÔNG được lệch chủ đề hoặc tự ý thêm nội dung không liên quan. "
                    "ĐÂY LÀ CHƯƠNG TRÌNH LIỀN MẠCH, TUYỆT ĐỐI KHÔNG được mention 'tuần sau', 'tập tiếp theo'. "
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
            if i == 0 and dynamic_opening:
                f.write(f"[Lời mở đầu động: {dynamic_opening}]\n\n")
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

        # Tạo chương trình chapter YouTube
    chapter_file = generate_chapter_timestamps(outline_sections, output_dir, base)
    log_func(f"📍 Đã tạo file chapter: {chapter_file}")

    
    log_func(f"\n🎉 Hoàn tất!")
    log_func(f"📺 Kênh: {channel_name}")
    log_func(f"📄 Dàn ý chi tiết: {output_outline}")
    log_func(f"📝 Kịch bản gốc: {output_script}")
    log_func(f"🧹 Kịch bản clean: {output_clean}")
    log_func(f"🎵 Audio hoàn chỉnh: {final_audio}")
    
    return final_audio

