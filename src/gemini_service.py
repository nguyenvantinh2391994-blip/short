"""
Gemini Service - Tạo kịch bản bán hàng và voice sử dụng Google Gemini API
"""

import os
import json
import base64
import time
import tempfile
import subprocess
import struct
import wave
import shutil
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

import requests
from rich.console import Console

console = Console()


@dataclass
class ScriptResult:
    """Kết quả tạo kịch bản"""
    success: bool
    script: str = ""
    sora_prompt: str = ""  # Prompt cho SORA video
    error: str = ""


@dataclass
class VoiceResult:
    """Kết quả tạo voice"""
    success: bool
    audio_path: str = ""
    error: str = ""


def create_wav_from_pcm(pcm_data: bytes, output_path: str, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bool:
    """
    Tạo file WAV từ raw PCM data

    Args:
        pcm_data: Raw PCM audio data
        output_path: Đường dẫn file output
        sample_rate: Sample rate (Hz), Gemini TTS dùng 24000
        channels: Số kênh (1 = mono, 2 = stereo)
        sample_width: Bytes per sample (2 = 16-bit)

    Returns:
        True nếu thành công
    """
    try:
        with wave.open(output_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        return True
    except Exception as e:
        console.print(f"[red]Lỗi tạo WAV: {e}[/]")
        return False


class GeminiService:
    """Service để tương tác với Google Gemini API"""

    # API endpoints
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    # Prompt template cho kịch bản bán hàng TỰ NHIÊN (30-40s) - AFFILIATE
    SCRIPT_PROMPT_TEMPLATE = """Bạn là người review sản phẩm tự nhiên, chân thực cho video AFFILIATE.

SẢN PHẨM:
- Tên: {product_name}
- Mô tả chi tiết: {product_description}

NHIỆM VỤ: Từ mô tả sản phẩm, LỌC RA các TÍNH NĂNG NỔI BẬT và viết kịch bản 30-40 giây.

BỐI CẢNH VIDEO:
- Phần đầu (SORA): Đã có hình ảnh bắt mắt của người mặc/dùng sản phẩm (5-10s)
- Phần voice này: Tiếp nối, giải thích TẠI SAO sản phẩm này tốt
- Video có GẮN GIỎ HÀNG (icon giỏ hàng màu vàng trong video)

CẤU TRÚC KỊCH BẢN (4 phần):

1. HOOK NHẸ (1-2 câu): Thu hút tiếp sau hình ảnh
   - "Mình biết nhiều bạn đang thắc mắc về..."
   - "Đây là món mình hay được hỏi nhất..."
   - "Nếu bạn đang tìm [loại sản phẩm] thì xem tiếp nha..."

2. TÍNH NĂNG (2-3 điểm): Trích từ mô tả, nói ngắn gọn
   - Chất liệu gì? (cotton, lụa, thun...)
   - Thiết kế như thế nào? (form, kiểu dáng...)
   - Điểm đặc biệt? (co giãn, thoáng mát, không nhăn...)

3. LÝ DO MUA (kích thích nhu cầu):
   - Phù hợp với ai? Dịp nào?
   - Giải quyết vấn đề gì cho người mua?
   - So sánh nhẹ (giá tốt, chất lượng...)

4. CALL TO ACTION (cho video AFFILIATE - chọn 1):
   - "Bấm vào giỏ hàng màu vàng trong video để mua nha"
   - "Ai thích thì bấm giỏ hàng để xem giá nha"
   - "Comment 'muốn' để mình gửi link nha"
   - "Bấm vào giỏ hàng hoặc comment để mình tư vấn"

YÊU CẦU:
- Độ dài: 90-120 từ (30-40 giây)
- Giọng điệu: Tự nhiên như nói chuyện, KHÔNG giả tạo
- Tập trung TÍNH NĂNG thực tế từ mô tả sản phẩm
- KHÔNG bịa thông tin không có trong mô tả

PHONG CÁCH:
- Như đang review cho bạn bè xem
- Dùng từ đời thường: "thật sự", "nói thật", "mình thấy"
- Có thể dùng: "xịn", "ưng", "đáng tiền" (tự nhiên)
- KHÔNG dùng quá mức: "siêu cấp", "đỉnh của chóp"

VÍ DỤ TỐT (cho áo thun cotton):
"Đây là mẫu áo mình hay được hỏi nhất nè. Chất cotton 100% nên mặc mát lắm, đi làm cả ngày không bí. Form áo vừa vặn, không quá rộng cũng không bó. Màu này dễ phối đồ, mình hay mặc với quần jean hoặc chân váy đều được. Giá cũng mềm, dưới 200k thôi. Ai thích thì bấm vào giỏ hàng màu vàng trong video nha."

TUYỆT ĐỐI KHÔNG ĐƯỢC có:
- Ghi chú thời gian: "(0-5 giây)", "(Mở đầu - 3s)"
- Hướng dẫn hành động: "(quay cận...)", "(bé cười...)"
- Tiêu đề: "Kịch bản TikTok:", "Video bắt đầu"
- Định dạng: **in đậm**, *nghiêng*
- Ghi chú: "MC:", "Người nói:", ghi chú sân khấu

CHỈ TRẢ VỀ VĂN BẢN ĐỌC VOICE TRỰC TIẾP:"""

    # Prompt template cho SORA video (đơn giản, nhân vật mặc/dùng sản phẩm)
    SORA_PROMPT_TEMPLATE = """Tạo prompt NGẮN GỌN cho SORA AI để tạo video người Việt Nam đang mặc/sử dụng sản phẩm.

SẢN PHẨM:
- Tên: {product_name}
- Mô tả: {product_description}

QUAN TRỌNG - PHẢI XÁC ĐỊNH NHÂN VẬT CỤ THỂ:
1. Dựa vào tên và mô tả sản phẩm, xác định:
   - ĐỘ TUỔI cụ thể (ví dụ: 6-year-old, 25-year-old, 35-year-old...)
   - GIỚI TÍNH (boy/girl/man/woman)
   - Ví dụ: "áo dài bé gái" → "6-year-old Vietnamese girl"
   - Ví dụ: "váy nữ" → "25-year-old Vietnamese woman"
   - Ví dụ: "áo sơ mi nam" → "30-year-old Vietnamese man"

2. Tạo prompt với format:
   [TUỔI]-year-old Vietnamese [GIỚI TÍNH] wearing [SẢN PHẨM], [HÀNH ĐỘNG ĐƠN GIẢN], [BỐI CẢNH VIỆT NAM]

YÊU CẦU:
- KHÔNG phải video review, KHÔNG giới thiệu sản phẩm
- CHỈ CẦN nhân vật đang mặc/dùng sản phẩm tự nhiên
- Bối cảnh Việt Nam phù hợp
- Video 5-10 giây, như quay bằng điện thoại
- Prompt NGẮN 15-25 từ tiếng Anh

VÍ DỤ:
- "6-year-old Vietnamese girl wearing ao dai, walking happily in garden, natural phone footage"
- "25-year-old Vietnamese woman in elegant dress, gentle walk in park, warm daylight"
- "8-year-old Vietnamese boy wearing shirt, playing in backyard, candid moment"

CHỈ TRẢ VỀ 1 CÂU PROMPT TIẾNG ANH (15-25 từ):"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        """
        Khởi tạo GeminiService

        Args:
            api_key: Google AI API key
            model: Model để dùng (default: gemini-2.0-flash)
        """
        self.api_key = api_key
        self.model = model
        self.tts_model = "gemini-2.5-flash-preview-tts"

    def _clean_script_text(self, script: str) -> str:
        """
        Loại bỏ các ghi chú, định dạng thừa trong kịch bản

        Args:
            script: Kịch bản gốc

        Returns:
            Kịch bản đã được làm sạch, chỉ còn văn bản đọc voice
        """
        import re

        if not script:
            return ""

        lines = script.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Bỏ các dòng tiêu đề/header/intro/ghi chú
            skip_patterns = [
                r'^Kịch bản',
                r'^Video bắt đầu',
                r'^\*\*Kịch bản',
                r'^\*\*Video',
                r'^\[Video',
                r'^#+ ',  # Markdown headers
                r'^Tuyệt vời',
                r'^Dưới đây là',
                r'^Đây là kịch bản',
                r'^\(Hình ảnh',
                r'^\(Video',
                r'^\(Nhạc',
                r'^\(Kết thúc',
                r'^\(Chèn',
                r'^\(Text',
                r'^\(giọng',
                r'^\*\*\(.*\)\*\*',
                r'^\(.*giây\)',
                r'^\*\*\[.*\]\*\*',
                r'^\* Hình ảnh',
                r'^\* Âm thanh',
                r'^\* Lời thoại',
                r'^\* Chữ trên',
                r'^Lưu ý',
                r'^\* Sử dụng',
                r'^Text trên màn hình',
                r'^\(Text trên màn hình\)',
                r'^#\w+',  # Dòng bắt đầu bằng hashtag
            ]
            should_skip = False
            for pattern in skip_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    should_skip = True
                    break
            if should_skip:
                continue

            # Loại bỏ bullet points đầu dòng: *, -, •, ***
            line = re.sub(r'^[\*\-•]+\s*', '', line)

            # Loại bỏ ghi chú thời gian
            line = re.sub(r'\*?\*?\[?\(?\d+[-–]\d+\s*(s|giây|seconds?)?\)?]?\*?\*?\s*:?', '', line)
            line = re.sub(r'\[?\(?(Mở đầu|Review|Kết|Hook|CTA|MC|Người nói|Chi tiết|Giới thiệu)[\s\-–:]*\d*\s*(s|giây)?\)?]?\s*:?', '', line, flags=re.IGNORECASE)

            # Loại bỏ các ngoặc với nội dung ghi chú
            line = re.sub(r'\([^)]*quay[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*cười[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*hình ảnh[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*video[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*chèn[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*nhạc[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*giơ[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*mặc[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*chỉ tay[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*bé gái[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*bé trai[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*xoay[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*tạo dáng[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\([^)]*giọng[^)]*\)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\[[^\]]*hình ảnh[^\]]*\]', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\[[^\]]*video[^\]]*\]', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\[[^\]]*Kho Sỉ[^\]]*\]', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\[[^\]]*Tặng[^\]]*\]', '', line, flags=re.IGNORECASE)

            # Loại bỏ định dạng markdown: **bold**, *italic*, ""text""
            line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
            line = re.sub(r'\*([^*]+)\*', r'\1', line)
            line = re.sub(r'""([^"]+)""', r'\1', line)

            # Loại bỏ MC:, Người nói:, Lời thoại:, etc.
            line = re.sub(r'^(MC|Người nói|Speaker|Host|Lời thoại)\s*[:\-–]\s*', '', line, flags=re.IGNORECASE)

            # Loại bỏ emoji
            line = re.sub(r'[\U0001F300-\U0001F9FF]', '', line)
            line = re.sub(r'[\u2600-\u26FF\u2700-\u27BF]', '', line)

            # Loại bỏ hashtag
            line = re.sub(r'#\w+\s*', '', line)

            # Loại bỏ khoảng trắng thừa
            line = re.sub(r'\s+', ' ', line).strip()

            # Bỏ dòng chỉ có dấu ngoặc hoặc quá ngắn
            if line and len(line) > 3 and not re.match(r'^[\(\)\[\]\*\s\.\:]+$', line):
                cleaned_lines.append(line)

        result = '\n'.join(cleaned_lines)

        # Gộp các dòng thành đoạn văn liền mạch
        result = re.sub(r'\n+', '\n\n', result)

        return result.strip()

    def generate_script(
        self,
        product_name: str,
        product_description: str,
        custom_prompt: str = None,
        sora_custom_prompt: str = None
    ) -> ScriptResult:
        """
        Tạo kịch bản bán hàng từ tên và mô tả sản phẩm

        Args:
            product_name: Tên sản phẩm
            product_description: Mô tả sản phẩm
            custom_prompt: Prompt tùy chỉnh cho script (nếu có)
            sora_custom_prompt: Prompt tùy chỉnh cho SORA (nếu có)

        Returns:
            ScriptResult với kịch bản hoặc lỗi
        """
        if not self.api_key:
            return ScriptResult(False, error="API key không được cung cấp")

        if not product_name:
            return ScriptResult(False, error="Tên sản phẩm trống")

        # Tạo prompt
        if custom_prompt:
            prompt = custom_prompt.format(
                product_name=product_name,
                product_description=product_description or "Không có mô tả"
            )
        else:
            prompt = self.SCRIPT_PROMPT_TEMPLATE.format(
                product_name=product_name,
                product_description=product_description or "Không có mô tả chi tiết"
            )

        try:
            # Gọi Gemini API với retry
            url = f"{self.GEMINI_API_URL}/{self.model}:generateContent?key={self.api_key}"

            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.85,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 350,  # Tăng cho kịch bản 90-120 từ
                }
            }

            # Retry logic cho rate limit
            max_retries = 3
            for attempt in range(max_retries):
                response = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )

                if response.status_code == 200:
                    break
                elif response.status_code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                        console.print(f"[yellow]Rate limit, chờ {wait_time}s...[/]")
                        time.sleep(wait_time)
                        continue
                    else:
                        error_msg = "Đã hết quota API. Vui lòng chờ hoặc kiểm tra billing."
                        return ScriptResult(False, error=error_msg)
                else:
                    break

            if response.status_code != 200:
                error_msg = response.json().get("error", {}).get("message", response.text)
                return ScriptResult(False, error=f"API error: {error_msg}")

            data = response.json()

            # Extract text từ response
            candidates = data.get("candidates", [])
            if not candidates:
                return ScriptResult(False, error="Không có kết quả từ API")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return ScriptResult(False, error="Response không có nội dung")

            script = parts[0].get("text", "").strip()

            # Clean up script - remove quotes if wrapped
            if script.startswith('"') and script.endswith('"'):
                script = script[1:-1]
            if script.startswith("'") and script.endswith("'"):
                script = script[1:-1]

            # Clean up script - loại bỏ ghi chú, định dạng thừa
            script = self._clean_script_text(script)

            if not script:
                return ScriptResult(False, error="Kịch bản trống")

            console.print(f"[green]✓ Đã tạo kịch bản ({len(script)} ký tự)[/]")

            # Tạo SORA prompt
            sora_prompt = ""
            try:
                sora_prompt = self._generate_sora_prompt_internal(
                    product_name, product_description, sora_custom_prompt
                )
                if sora_prompt:
                    console.print(f"[green]✓ Đã tạo SORA prompt[/]")
            except Exception as e:
                console.print(f"[yellow]⚠️ Không tạo được SORA prompt: {e}[/]")

            return ScriptResult(True, script=script, sora_prompt=sora_prompt)

        except requests.RequestException as e:
            return ScriptResult(False, error=f"Lỗi kết nối: {e}")
        except Exception as e:
            return ScriptResult(False, error=f"Lỗi: {e}")

    def _generate_sora_prompt_internal(
        self,
        product_name: str,
        product_description: str,
        custom_prompt: str = None
    ) -> str:
        """
        Tạo prompt cho SORA video (internal method)

        Args:
            product_name: Tên sản phẩm
            product_description: Mô tả sản phẩm
            custom_prompt: Custom prompt template (nếu có)

        Returns:
            SORA prompt string hoặc empty string nếu lỗi
        """
        template = custom_prompt if custom_prompt else self.SORA_PROMPT_TEMPLATE
        prompt = template.format(
            product_name=product_name,
            product_description=product_description or "Sản phẩm chất lượng cao"
        )

        url = f"{self.GEMINI_API_URL}/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.8,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 150,
            }
        }

        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if response.status_code != 200:
            return ""

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            return ""

        sora_prompt = parts[0].get("text", "").strip()

        # Clean up - remove quotes
        if sora_prompt.startswith('"') and sora_prompt.endswith('"'):
            sora_prompt = sora_prompt[1:-1]
        if sora_prompt.startswith("'") and sora_prompt.endswith("'"):
            sora_prompt = sora_prompt[1:-1]

        return sora_prompt

    def generate_sora_prompt(
        self,
        product_name: str,
        product_description: str,
        custom_prompt: str = None
    ) -> str:
        """
        Tạo prompt cho SORA video (public method)

        Args:
            product_name: Tên sản phẩm
            product_description: Mô tả sản phẩm
            custom_prompt: Custom prompt template (nếu có)

        Returns:
            SORA prompt string
        """
        try:
            return self._generate_sora_prompt_internal(product_name, product_description, custom_prompt)
        except Exception as e:
            console.print(f"[red]❌ Lỗi tạo SORA prompt: {e}[/]")
            return ""

    # =========================================================================
    # FLOW IMAGE & VIDEO PROMPTS
    # =========================================================================

    # Template cho Flow image prompt 1 - ẢNH BÌA SẢN PHẨM (thể hiện rõ sản phẩm)
    FLOW_IMAGE_PROMPT_1_TEMPLATE = """Dựa vào thông tin sản phẩm, hãy tạo prompt để generate ẢNH BÌA SẢN PHẨM cho AI (Google Flow).

SẢN PHẨM:
- Tên: {product_name}
- Mô tả: {product_description}

MỤC ĐÍCH: Tạo ẢNH BÌA cho sản phẩm - ảnh thể hiện RÕ RÀNG sản phẩm, như ảnh chụp mẫu chuyên nghiệp.

QUAN TRỌNG:
- Nhân vật PHẢI là người Việt Nam (da vàng, tóc đen, khuôn mặt châu Á)
- Sản phẩm PHẢI được thể hiện RÕ RÀNG, CHÍNH DIỆN, nhìn thấy TOÀN BỘ sản phẩm
- Người mẫu ĐỨNG hoặc NGỒI đẹp, TƯ THẾ tự nhiên nhưng thể hiện trọn vẹn sản phẩm
- BỐI CẢNH đơn giản, tôn sản phẩm (không rối mắt)

YÊU CẦU:
1. Xác định đối tượng NGƯỜI VIỆT NAM phù hợp với sản phẩm:
   - Tuổi phù hợp (trẻ em, người lớn...)
   - Giới tính phù hợp

2. Điền vào template sau (CHỈ TRẢ VỀ PROMPT, KHÔNG GIẢI THÍCH):

Create a photorealistic product showcase photograph, as if taken by a professional photographer.

A [TUỔI]-year-old [GIỚI TÍNH] Vietnamese person with typical Vietnamese features (dark hair, warm skin tone, Asian facial features) wearing/holding [TÊN SẢN PHẨM].

PRODUCT VISIBILITY (CRITICAL):
- The product must be FULLY VISIBLE and CLEARLY DISPLAYED
- Person standing or sitting in a pose that SHOWCASES THE ENTIRE PRODUCT
- Front-facing view showing complete product details
- Product is the MAIN FOCUS of the image

Pose requirements:
- Natural but elegant standing/sitting pose
- Body position that displays the full product
- Relaxed, confident expression
- May look at camera with gentle smile OR look slightly to the side

Background:
- Simple, clean background that complements the product
- Soft neutral colors (light gray, beige, soft white)
- Vietnamese context: simple Vietnamese home corner, plain wall, garden edge
- NO distracting elements - background should enhance product visibility

Lighting:
- Soft, even lighting that highlights the product
- Natural daylight feel
- No harsh shadows on the product

Photography style:
- Product photography quality, 85mm lens, f/4
- Full body or 3/4 shot showing complete product
- Sharp focus on both person and product
- Clean, professional but natural look

STRICTLY AVOID:
- Cropped or partially hidden product
- Person doing activities that hide the product
- Busy or distracting backgrounds
- Side angles that don't show product clearly
- AI-generated or overly perfect look

The image should look like a professional product photo for e-commerce cover image.

CHỈ TRẢ VỀ PROMPT ĐÃ ĐIỀN ĐẦY ĐỦ, KHÔNG GIẢI THÍCH:"""

    # Template cho Flow image prompt 2 - LIFESTYLE (hoạt động thường ngày)
    FLOW_IMAGE_PROMPT_2_TEMPLATE = """Dựa vào thông tin sản phẩm, hãy tạo prompt để generate ảnh LIFESTYLE cho AI (Google Flow).

SẢN PHẨM:
- Tên: {product_name}
- Mô tả: {product_description}

MỤC ĐÍCH: Tạo ảnh LIFESTYLE - người Việt Nam đang sử dụng sản phẩm trong sinh hoạt thường ngày.

QUAN TRỌNG:
- Nhân vật PHẢI là người Việt Nam (da vàng, tóc đen, khuôn mặt châu Á)
- Bối cảnh VIỆT NAM: nhà Việt Nam, sân vườn, công viên...
- Hoạt động TỰ NHIÊN, đời thường

YÊU CẦU:
1. Xác định đối tượng NGƯỜI VIỆT NAM phù hợp:
   - Tuổi (ví dụ: 25, 30, 4, 8...)
   - Giới tính (male/female)

2. Xác định BỐI CẢNH và HOẠT ĐỘNG phù hợp Việt Nam

3. Điền vào template sau (CHỈ TRẢ VỀ PROMPT, KHÔNG GIẢI THÍCH):

Create a photorealistic lifestyle photograph, as if taken by a real DSLR camera.

A [TUỔI]-year-old [GIỚI TÍNH] Vietnamese person with typical Vietnamese features (dark hair, warm skin tone, Asian facial features) naturally using or wearing [TÊN SẢN PHẨM].
Captured in a candid moment — not posing, not looking at the camera.
Setting: [BỐI CẢNH VIỆT NAM - ví dụ: cozy Vietnamese living room, typical Vietnamese home interior, Vietnamese apartment balcony, local Vietnamese park]

Vietnamese context requirements:
- Person must look authentically Vietnamese (not Korean, Japanese, or Western)
- Setting should feel like a real Vietnamese home or outdoor space
- Background may include typical Vietnamese household items

Realism requirements:
- Realistic human proportions and facial features
- Natural skin texture with small imperfections
- Natural lighting from one side (window light or outdoor shade)
- Slight motion blur and imperfect framing
- Shallow depth of field, realistic background blur
- Everyday real-life environment related to normal daily activities
- Product shows natural usage, folds, or wear (not perfectly displayed)

Photography style:
- Real camera look, 35mm or 50mm lens, f/2.8
- Natural color grading, slightly warm, not oversaturated
- No studio lighting, no artificial glow
- Not commercial, not advertisement style

STRICTLY AVOID:
- AI-generated look
- Overly smooth or plastic skin
- Perfect symmetry
- Catalog or fashion pose
- Studio background
- Illustration, cartoon, or 3D style
- Non-Vietnamese or Western-looking person

The image should look like a spontaneous real-life photo taken by a Vietnamese family member or friend.

CHỈ TRẢ VỀ PROMPT ĐÃ ĐIỀN ĐẦY ĐỦ, KHÔNG GIẢI THÍCH:"""

    # Template cho video prompt (đơn giản, chân thực, bối cảnh Việt Nam)
    FLOW_VIDEO_PROMPT_TEMPLATE = """Dựa vào thông tin sản phẩm, tạo prompt ngắn gọn để generate video từ ảnh sản phẩm.

SẢN PHẨM:
- Tên: {product_name}
- Mô tả: {product_description}

YÊU CẦU:
- Video 5-10 giây, chân thực như quay bằng điện thoại
- Nhân vật là người Việt Nam trong bối cảnh Việt Nam
- Chỉ mô tả 1-2 hành động đơn giản, tự nhiên
- KHÔNG dùng từ ngữ quảng cáo
- Phong cách: video đời thường, không dàn dựng

VÍ DỤ PROMPT TỐT:
- "Vietnamese person gently adjusting the product, natural hand movement, cozy home setting"
- "Vietnamese child playing happily, casual home environment, natural daylight"
- "Vietnamese woman smiling while using the product, candid moment, warm indoor lighting"

CHỈ TRẢ VỀ 1 CÂU PROMPT TIẾNG ANH (15-25 từ), KHÔNG GIẢI THÍCH:"""

    def generate_flow_image_prompt(
        self,
        product_name: str,
        product_description: str,
        variant: int = 1,
        custom_prompt_1: str = None,
        custom_prompt_2: str = None
    ) -> str:
        """
        Tạo prompt cho Flow image generation.

        Args:
            product_name: Tên sản phẩm
            product_description: Mô tả sản phẩm
            variant: Biến thể (1 hoặc 2) để tạo prompt khác nhau
            custom_prompt_1: Custom prompt cho variant 1 (ảnh bìa)
            custom_prompt_2: Custom prompt cho variant 2 (lifestyle)

        Returns:
            Flow image prompt string
        """
        if not self.api_key:
            return ""

        # Chọn template theo variant
        # Variant 1: Ảnh bìa sản phẩm (cover photo) - thể hiện rõ sản phẩm
        # Variant 2: Ảnh lifestyle - hoạt động thường ngày
        if variant == 1:
            template = custom_prompt_1 if custom_prompt_1 else self.FLOW_IMAGE_PROMPT_1_TEMPLATE
        else:
            template = custom_prompt_2 if custom_prompt_2 else self.FLOW_IMAGE_PROMPT_2_TEMPLATE

        prompt = template.format(
            product_name=product_name,
            product_description=product_description or "Sản phẩm chất lượng cao"
        )

        try:
            url = f"{self.GEMINI_API_URL}/{self.model}:generateContent?key={self.api_key}"

            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.9 if variant == 2 else 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 500,
                }
            }

            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                return ""

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return ""

            result = parts[0].get("text", "").strip()

            # Clean up
            if result.startswith('"') and result.endswith('"'):
                result = result[1:-1]

            console.print(f"[green]✓ Đã tạo Flow image prompt {variant}[/]")
            return result

        except Exception as e:
            console.print(f"[red]❌ Lỗi tạo Flow image prompt: {e}[/]")
            return ""

    def generate_video_prompt(
        self,
        product_name: str,
        product_description: str,
        variant: int = 1,
        custom_prompt: str = None
    ) -> str:
        """
        Tạo prompt cho video generation từ ảnh.

        Args:
            product_name: Tên sản phẩm
            product_description: Mô tả sản phẩm
            variant: Biến thể (1 hoặc 2)
            custom_prompt: Custom prompt template (nếu có)

        Returns:
            Video prompt string
        """
        if not self.api_key:
            return ""

        variant_note = ""
        if variant == 2:
            variant_note = "\n\nLƯU Ý: Tạo prompt với hành động KHÁC với prompt trước."

        template = custom_prompt if custom_prompt else self.FLOW_VIDEO_PROMPT_TEMPLATE
        prompt = template.format(
            product_name=product_name,
            product_description=product_description or "Sản phẩm chất lượng cao"
        ) + variant_note

        try:
            url = f"{self.GEMINI_API_URL}/{self.model}:generateContent?key={self.api_key}"

            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.8 if variant == 2 else 0.6,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 100,
                }
            }

            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                return ""

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return ""

            result = parts[0].get("text", "").strip()

            # Clean up
            if result.startswith('"') and result.endswith('"'):
                result = result[1:-1]

            console.print(f"[green]✓ Đã tạo video prompt {variant}[/]")
            return result

        except Exception as e:
            console.print(f"[red]❌ Lỗi tạo video prompt: {e}[/]")
            return ""

    def generate_flow_prompts(
        self,
        product_name: str,
        product_description: str,
        custom_prompts: dict = None
    ) -> dict:
        """
        Tạo tất cả 4 prompts cho Flow (2 image + 2 video).

        Args:
            product_name: Tên sản phẩm
            product_description: Mô tả sản phẩm
            custom_prompts: Dict chứa custom prompts (flow_image_1, flow_image_2, flow_video)

        Returns:
            Dict với keys: image_prompt_1 (I), video_prompt_1 (J),
                          image_prompt_2 (K), video_prompt_2 (L)
        """
        result = {
            "image_prompt_1": "",  # Column I
            "video_prompt_1": "",  # Column J
            "image_prompt_2": "",  # Column K
            "video_prompt_2": "",  # Column L
        }

        # Get custom prompts if provided
        custom_image_1 = custom_prompts.get("flow_image_1") if custom_prompts else None
        custom_image_2 = custom_prompts.get("flow_image_2") if custom_prompts else None
        custom_video = custom_prompts.get("flow_video") if custom_prompts else None

        # Generate image prompt 1
        result["image_prompt_1"] = self.generate_flow_image_prompt(
            product_name, product_description, variant=1,
            custom_prompt_1=custom_image_1, custom_prompt_2=custom_image_2
        )
        time.sleep(0.5)  # Small delay to avoid rate limit

        # Generate video prompt 1
        result["video_prompt_1"] = self.generate_video_prompt(
            product_name, product_description, variant=1,
            custom_prompt=custom_video
        )
        time.sleep(0.5)

        # Generate image prompt 2 (different variant)
        result["image_prompt_2"] = self.generate_flow_image_prompt(
            product_name, product_description, variant=2,
            custom_prompt_1=custom_image_1, custom_prompt_2=custom_image_2
        )
        time.sleep(0.5)

        # Generate video prompt 2
        result["video_prompt_2"] = self.generate_video_prompt(
            product_name, product_description, variant=2,
            custom_prompt=custom_video
        )

        return result

    def generate_voice(
        self,
        text: str,
        output_path: str,
        voice_name: str = "Kore",
        output_format: str = "mp3"
    ) -> VoiceResult:
        """
        Tạo voice từ text sử dụng Gemini TTS

        Args:
            text: Nội dung cần đọc
            output_path: Đường dẫn file output (.mp3 hoặc .wav)
            voice_name: Tên giọng đọc (Aoede, Charon, Fenrir, Kore, Puck)
                        - Kore: Giọng nữ vui tươi, năng động (mặc định)
                        - Puck: Giọng vui vẻ, linh hoạt
                        - Aoede: Giọng nữ trầm ấm
            output_format: Format output (mp3 hoặc wav)

        Returns:
            VoiceResult với đường dẫn file hoặc lỗi
        """
        if not self.api_key:
            return VoiceResult(False, error="API key không được cung cấp")

        if not text:
            return VoiceResult(False, error="Nội dung trống")

        try:
            # Gemini 2.5 Flash TTS API
            url = f"{self.GEMINI_API_URL}/{self.tts_model}:generateContent?key={self.api_key}"

            payload = {
                "contents": [{
                    "parts": [{"text": text}]
                }],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": voice_name
                            }
                        }
                    }
                }
            }

            console.print(f"[dim]Đang tạo voice với giọng {voice_name}...[/]")

            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", response.text)
                return VoiceResult(False, error=f"API error: {error_msg}")

            data = response.json()

            # Extract audio data
            candidates = data.get("candidates", [])
            if not candidates:
                return VoiceResult(False, error="Không có kết quả từ API")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            if not parts:
                return VoiceResult(False, error="Response không có audio")

            # Tìm inline_data chứa audio
            audio_data = None
            for part in parts:
                if "inlineData" in part:
                    audio_data = part["inlineData"].get("data")
                    break

            if not audio_data:
                return VoiceResult(False, error="Không tìm thấy audio trong response")

            # Decode base64
            audio_bytes = base64.b64decode(audio_data)

            # Tạo thư mục nếu chưa có
            output_file = Path(output_path)
            # Đảm bảo extension đúng
            if output_format == "mp3" and not str(output_file).endswith(".mp3"):
                output_file = output_file.with_suffix(".mp3")
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Tạo file WAV từ raw PCM data (Gemini TTS trả về raw PCM 24kHz 16-bit mono)
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            if not create_wav_from_pcm(audio_bytes, tmp_wav, sample_rate=24000, channels=1, sample_width=2):
                return VoiceResult(False, error="Không thể tạo file WAV từ dữ liệu audio")

            # Nếu cần MP3, convert từ WAV
            if output_format == "mp3":
                try:
                    # Convert sang MP3 bằng ffmpeg
                    result = subprocess.run(
                        ["ffmpeg", "-y", "-i", tmp_wav, "-acodec", "libmp3lame", "-q:a", "2", str(output_file)],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        # Nếu ffmpeg fail, giữ lại file WAV
                        console.print(f"[yellow]⚠️ ffmpeg convert thất bại, lưu WAV[/]")
                        output_file = output_file.with_suffix(".wav")
                        shutil.copy(tmp_wav, str(output_file))
                except FileNotFoundError:
                    # ffmpeg không được cài đặt - lưu WAV thay vì MP3
                    console.print(f"[yellow]⚠️ ffmpeg không được cài đặt, lưu WAV thay vì MP3[/]")
                    output_file = output_file.with_suffix(".wav")
                    shutil.copy(tmp_wav, str(output_file))
                except Exception as e:
                    # Lỗi khác - vẫn lưu WAV
                    console.print(f"[yellow]⚠️ Lỗi convert MP3: {e}, lưu WAV[/]")
                    output_file = output_file.with_suffix(".wav")
                    shutil.copy(tmp_wav, str(output_file))
                finally:
                    # Xóa file tạm
                    if os.path.exists(tmp_wav):
                        os.unlink(tmp_wav)
            else:
                # Nếu không cần MP3, vẫn convert sang WAV chuẩn
                shutil.move(tmp_wav, str(output_file))

            console.print(f"[green]✓ Đã tạo voice: {output_file.name}[/]")
            return VoiceResult(True, audio_path=str(output_file))

        except requests.RequestException as e:
            return VoiceResult(False, error=f"Lỗi kết nối: {e}")
        except Exception as e:
            return VoiceResult(False, error=f"Lỗi: {e}")

    def create_product_voice(
        self,
        product_code: str,
        product_name: str,
        product_description: str,
        voice_folder: str,
        voice_name: str = "Aoede"
    ) -> Tuple[ScriptResult, VoiceResult]:
        """
        Quy trình đầy đủ: tạo kịch bản -> tạo voice

        Args:
            product_code: Mã sản phẩm (dùng làm tên file)
            product_name: Tên sản phẩm
            product_description: Mô tả sản phẩm
            voice_folder: Thư mục lưu voice
            voice_name: Tên giọng đọc

        Returns:
            Tuple (ScriptResult, VoiceResult)
        """
        # Bước 1: Tạo kịch bản
        console.print(f"[cyan]📝 Đang tạo kịch bản cho {product_code}...[/]")
        script_result = self.generate_script(product_name, product_description)

        if not script_result.success:
            return script_result, VoiceResult(False, error="Chưa có kịch bản")

        console.print(f"[dim]Kịch bản: {script_result.script[:100]}...[/]")

        # Bước 2: Tạo voice (MP3)
        console.print(f"[cyan]🎙️ Đang tạo voice...[/]")
        voice_path = Path(voice_folder) / f"{product_code}.mp3"
        voice_result = self.generate_voice(
            text=script_result.script,
            output_path=str(voice_path),
            voice_name=voice_name,
            output_format="mp3"
        )

        return script_result, voice_result


class ScriptProcessor:
    """Xử lý batch tạo kịch bản và voice từ Google Sheet"""

    def __init__(
        self,
        gemini_service: GeminiService,
        voice_folder: str = "voice",
        name_column: str = "C",
        description_column: str = "D",
        script_column: str = "G",
        sora_prompt_column: str = "E",
    ):
        """
        Args:
            gemini_service: GeminiService instance
            voice_folder: Thư mục lưu voice
            name_column: Cột tên sản phẩm
            description_column: Cột mô tả
            script_column: Cột ghi kịch bản
            sora_prompt_column: Cột ghi SORA prompt
        """
        self.gemini = gemini_service
        self.voice_folder = Path(voice_folder)
        self.name_column = name_column
        self.description_column = description_column
        self.script_column = script_column
        self.sora_prompt_column = sora_prompt_column

        # Tạo thư mục voice nếu chưa có
        self.voice_folder.mkdir(parents=True, exist_ok=True)

    def process_sheet(
        self,
        sheet,  # gspread.Worksheet
        code_column: str = "A",
        skip_existing: bool = True,
        delay_between: float = 1.0,
        voice_name: str = "Aoede",
    ) -> dict:
        """
        Xử lý toàn bộ sheet: tạo kịch bản và voice cho từng sản phẩm

        Args:
            sheet: gspread Worksheet object
            code_column: Cột mã sản phẩm
            skip_existing: Bỏ qua nếu đã có voice
            delay_between: Delay giữa các request
            voice_name: Tên giọng đọc

        Returns:
            Dict với kết quả xử lý
        """
        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }

        try:
            all_values = sheet.get_all_values()

            if not all_values:
                console.print("[yellow]⚠️ Sheet trống[/]")
                return results

            # Tìm index các cột
            code_col_idx = ord(code_column.upper()) - ord('A')
            name_col_idx = ord(self.name_column.upper()) - ord('A')
            desc_col_idx = ord(self.description_column.upper()) - ord('A')
            script_col_idx = ord(self.script_column.upper()) - ord('A')

            # Bỏ qua header
            data_rows = all_values[1:] if len(all_values) > 1 else []

            console.print(f"[cyan]📋 Tìm thấy {len(data_rows)} dòng dữ liệu[/]")

            for row_idx, row in enumerate(data_rows, start=2):
                # Lấy thông tin
                code = row[code_col_idx].strip() if len(row) > code_col_idx else ""
                name = row[name_col_idx].strip() if len(row) > name_col_idx else ""
                description = row[desc_col_idx].strip() if len(row) > desc_col_idx else ""
                existing_script = row[script_col_idx].strip() if len(row) > script_col_idx else ""

                if not code or not name:
                    continue

                # Kiểm tra đã có voice chưa (check cả .mp3 và .wav)
                voice_path_mp3 = self.voice_folder / f"{code}.mp3"
                voice_path_wav = self.voice_folder / f"{code}.wav"
                voice_exists = voice_path_mp3.exists() or voice_path_wav.exists()

                if skip_existing and voice_exists:
                    console.print(f"[dim]⏭️ {code}: đã có voice[/]")
                    results["skipped"].append(code)
                    continue

                # Kiểm tra đã có script trong sheet chưa
                if skip_existing and existing_script:
                    console.print(f"[dim]⏭️ {code}: đã có kịch bản[/]")
                    # Nếu có script nhưng chưa có voice -> tạo voice
                    if not voice_exists:
                        console.print(f"[cyan]🎙️ Tạo voice từ kịch bản có sẵn...[/]")
                        voice_result = self.gemini.generate_voice(
                            text=existing_script,
                            output_path=str(voice_path_mp3),
                            voice_name=voice_name,
                            output_format="mp3"
                        )
                        if voice_result.success:
                            results["success"].append(code)
                        else:
                            results["failed"].append((code, voice_result.error))
                    else:
                        results["skipped"].append(code)
                    continue

                console.print(f"\n[bold]📦 [{row_idx}] {code}[/]")
                console.print(f"[dim]Tên: {name[:50]}...[/]" if len(name) > 50 else f"[dim]Tên: {name}[/]")

                # Tạo kịch bản và voice
                script_result, voice_result = self.gemini.create_product_voice(
                    product_code=code,
                    product_name=name,
                    product_description=description,
                    voice_folder=str(self.voice_folder),
                    voice_name=voice_name
                )

                # Ghi kịch bản vào sheet
                if script_result.success:
                    try:
                        cell = f"{self.script_column}{row_idx}"
                        sheet.update_acell(cell, script_result.script)
                        console.print(f"[green]✓ Đã ghi kịch bản vào {cell}[/]")

                        # Ghi SORA prompt vào cột E nếu có
                        if script_result.sora_prompt:
                            sora_cell = f"{self.sora_prompt_column}{row_idx}"
                            sheet.update_acell(sora_cell, script_result.sora_prompt)
                            console.print(f"[green]✓ Đã ghi SORA prompt vào {sora_cell}[/]")
                    except Exception as e:
                        console.print(f"[yellow]⚠️ Lỗi ghi sheet: {e}[/]")

                if voice_result.success:
                    results["success"].append(code)
                else:
                    results["failed"].append((code, voice_result.error))

                # Delay
                if delay_between > 0:
                    time.sleep(delay_between)

            return results

        except Exception as e:
            console.print(f"[red]❌ Lỗi: {e}[/]")
            return results


def create_voice_for_product(
    api_key: str,
    product_code: str,
    product_name: str,
    product_description: str,
    voice_folder: str = "voice",
    voice_name: str = "Aoede"
) -> Tuple[ScriptResult, VoiceResult]:
    """
    Utility function để tạo voice cho 1 sản phẩm

    Args:
        api_key: Gemini API key
        product_code: Mã sản phẩm
        product_name: Tên sản phẩm
        product_description: Mô tả
        voice_folder: Thư mục lưu voice
        voice_name: Tên giọng đọc

    Returns:
        Tuple (ScriptResult, VoiceResult)
    """
    service = GeminiService(api_key)
    return service.create_product_voice(
        product_code=product_code,
        product_name=product_name,
        product_description=product_description,
        voice_folder=voice_folder,
        voice_name=voice_name
    )
