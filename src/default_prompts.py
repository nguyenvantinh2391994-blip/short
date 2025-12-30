"""
Default Prompts - Tất cả các prompt mẫu mặc định theo danh mục

Mỗi danh mục (category) chứa 6 loại prompt:
- extract: Tách sản phẩm khỏi nền
- script: Kịch bản voice cho video
- sora: Prompt cho SORA AI video
- flow_image_1: Ảnh bìa sản phẩm (cover photo)
- flow_image_2: Ảnh lifestyle
- flow_video: Video prompt từ ảnh
"""

# =============================================================================
# 1. EXTRACT PROMPT - Tách sản phẩm khỏi nền
# =============================================================================
DEFAULT_EXTRACT_PROMPT = """IMAGE EDITING TASK — OBJECT EXTRACTION

This is an IMAGE EDITING task.
You must PROCESS the input image and RETURN a NEW IMAGE as output.

Input note:
I may provide MULTIPLE images of the SAME product.
These images are provided ONLY to help you understand
the product's full structure, details, and overall appearance.

Task description:
Extract (cut out) the MAIN PHYSICAL PRODUCT from the image.

Definition of the product:
- The product is the CLOTHING ITEM ITSELF as a standalone physical object.
- The product must NOT be worn by anyone.
- Any human, model, mannequin, body part, face, skin, hair, hands, arms,
  legs, feet, neck, or human silhouette is NOT part of the product
  and must be completely removed.

Editing instructions:
- Remove the entire background
- Remove all people and all body parts completely
- Remove mannequins, body shapes, or human outlines
- Remove all text, logos, and watermarks
- Keep ONLY the clothing item itself as an independent object
- Clothing must NOT appear worn or attached to a body
- Preserve ALL product details including fabric texture,
  patterns, embroidery, decorations, buttons, accessories, and stitching
- Do NOT remove or simplify any visual detail of the product
- Preserve realistic fabric shape and natural folds
- Do NOT flatten the clothing
- Do NOT stylize, beautify, or redesign

Output requirements:
- Output must be an IMAGE
- ONE clothing item only
- Pure white background (#FFFFFF)
- No shadows, no reflections
- No text in the output

Final rule:
Return ONLY the edited product image.
ABSOLUTELY NO humans, NO body parts, and NO text."""


# =============================================================================
# 2. SCRIPT PROMPT - Kịch bản bán hàng (30-40s) cho video AFFILIATE
# =============================================================================
DEFAULT_SCRIPT_PROMPT = """Bạn là người review sản phẩm tự nhiên, chân thực cho video AFFILIATE.

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

CHỈ TRẢ VỀ KỊCH BẢN, KHÔNG GIẢI THÍCH:"""


# =============================================================================
# 3. SORA PROMPT - Prompt cho SORA AI tạo video
# =============================================================================
DEFAULT_SORA_PROMPT = """Tạo prompt NGẮN GỌN cho SORA AI để tạo video người Việt Nam đang mặc/sử dụng sản phẩm.

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


# =============================================================================
# 4. FLOW IMAGE 1 - Ảnh bìa sản phẩm (cover photo)
# =============================================================================
DEFAULT_FLOW_IMAGE_1_PROMPT = """Dựa vào thông tin sản phẩm, hãy tạo prompt để generate ẢNH BÌA SẢN PHẨM cho AI (Google Flow).

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


# =============================================================================
# 5. FLOW IMAGE 2 - Ảnh lifestyle (hoạt động thường ngày)
# =============================================================================
DEFAULT_FLOW_IMAGE_2_PROMPT = """Dựa vào thông tin sản phẩm, hãy tạo prompt để generate ảnh LIFESTYLE cho AI (Google Flow).

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


# =============================================================================
# 6. FLOW VIDEO - Video prompt từ ảnh
# =============================================================================
DEFAULT_FLOW_VIDEO_PROMPT = """Dựa vào thông tin sản phẩm, tạo prompt ngắn gọn để generate video từ ảnh sản phẩm.

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


# =============================================================================
# PROMPT KEYS - Danh sách keys và labels
# =============================================================================
PROMPT_KEYS = {
    "extract": {
        "key": "extract",
        "label": "Tách sản phẩm",
        "description": "Prompt để tách sản phẩm khỏi nền ảnh",
        "default": DEFAULT_EXTRACT_PROMPT
    },
    "script": {
        "key": "script",
        "label": "Kịch bản Voice",
        "description": "Prompt tạo kịch bản bán hàng 30-40 giây",
        "default": DEFAULT_SCRIPT_PROMPT
    },
    "sora": {
        "key": "sora",
        "label": "SORA Video",
        "description": "Prompt cho SORA AI tạo video",
        "default": DEFAULT_SORA_PROMPT
    },
    "flow_image_1": {
        "key": "flow_image_1",
        "label": "Ảnh Bìa",
        "description": "Prompt tạo ảnh bìa sản phẩm (cover photo)",
        "default": DEFAULT_FLOW_IMAGE_1_PROMPT
    },
    "flow_image_2": {
        "key": "flow_image_2",
        "label": "Ảnh Lifestyle",
        "description": "Prompt tạo ảnh lifestyle, hoạt động thường ngày",
        "default": DEFAULT_FLOW_IMAGE_2_PROMPT
    },
    "flow_video": {
        "key": "flow_video",
        "label": "Flow Video",
        "description": "Prompt tạo video từ ảnh",
        "default": DEFAULT_FLOW_VIDEO_PROMPT
    }
}


def get_default_category() -> dict:
    """Trả về category mặc định với tất cả prompts"""
    return {
        "name": "Mặc định",
        "prompts": {
            "extract": DEFAULT_EXTRACT_PROMPT,
            "script": DEFAULT_SCRIPT_PROMPT,
            "sora": DEFAULT_SORA_PROMPT,
            "flow_image_1": DEFAULT_FLOW_IMAGE_1_PROMPT,
            "flow_image_2": DEFAULT_FLOW_IMAGE_2_PROMPT,
            "flow_video": DEFAULT_FLOW_VIDEO_PROMPT
        }
    }


def get_prompt_from_category(category: dict, prompt_type: str) -> str:
    """
    Lấy prompt từ category theo loại.

    Args:
        category: Dict chứa thông tin category
        prompt_type: Loại prompt (extract, script, sora, flow_image_1, flow_image_2, flow_video)

    Returns:
        Prompt string hoặc default nếu không tìm thấy
    """
    prompts = category.get("prompts", {})
    prompt = prompts.get(prompt_type, "")

    if not prompt:
        # Trả về default nếu không có
        return PROMPT_KEYS.get(prompt_type, {}).get("default", "")

    return prompt


def migrate_old_category(old_category: dict) -> dict:
    """
    Chuyển đổi category cũ (chỉ có 1 prompt) sang format mới (6 prompts).

    Args:
        old_category: Category theo format cũ {"name": "...", "prompt": "..."}

    Returns:
        Category mới với đầy đủ 6 prompts
    """
    name = old_category.get("name", "Mặc định")
    old_prompt = old_category.get("prompt", "")

    # Tạo category mới với defaults
    new_category = get_default_category()
    new_category["name"] = name

    # Nếu có prompt cũ, dùng làm script prompt
    if old_prompt:
        new_category["prompts"]["script"] = old_prompt

    return new_category
