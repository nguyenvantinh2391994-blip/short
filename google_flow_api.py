"""
VE3 Tool - Google Flow API Module
=================================
Tích hợp trực tiếp với Google Flow API để tạo ảnh và video.

Sử dụng Bearer Token authentication.
API Endpoint: aisandbox-pa.googleapis.com

Video Generation:
- Endpoint: /v1/video:batchAsyncGenerateVideoText
- Proxy API support: flow-api.nanoai.pics (bypass captcha)
"""

import json
import time
import random
import base64
import uuid
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# VIDEO ENUMS AND DATA CLASSES
# =============================================================================

class VideoAspectRatio(Enum):
    """Tỷ lệ khung hình cho video."""
    LANDSCAPE = "VIDEO_ASPECT_RATIO_LANDSCAPE"    # 16:9
    PORTRAIT = "VIDEO_ASPECT_RATIO_PORTRAIT"      # 9:16
    SQUARE = "VIDEO_ASPECT_RATIO_SQUARE"          # 1:1


class VideoModel(Enum):
    """Model tạo video Veo 3."""
    # Text-to-Video models (t2v)
    VEO3_FAST = "veo_3_1_t2v_fast_ultra"  # Fast generation
    VEO3_QUALITY = "veo_3_1_t2v"           # Quality generation
    # Image-to-Video models (r2v = reference to video)
    VEO3_I2V_FAST = "veo_3_0_r2v_fast_ultra"  # Fast Image-to-Video
    VEO3_I2V_QUALITY = "veo_3_0_r2v"           # Quality Image-to-Video


class PaygateTier(Enum):
    """User paygate tier - ảnh hưởng đến quyền sử dụng."""
    TIER_ONE = "PAYGATE_TIER_ONE"
    TIER_TWO = "PAYGATE_TIER_TWO"


@dataclass
class VideoGenerationResult:
    """Kết quả video được tạo."""
    video_url: Optional[str] = None
    video_id: Optional[str] = None
    scene_id: Optional[str] = None
    operation_id: Optional[str] = None
    status: str = "pending"  # pending, processing, completed, failed
    prompt: str = ""
    seed: Optional[int] = None
    local_path: Optional[Path] = None
    error: Optional[str] = None

    @property
    def is_completed(self) -> bool:
        return self.status == "completed" and bool(self.video_url)

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"


class AspectRatio(Enum):
    """Tỷ lệ khung hình cho ảnh."""
    LANDSCAPE = "IMAGE_ASPECT_RATIO_LANDSCAPE"    # 16:9
    PORTRAIT = "IMAGE_ASPECT_RATIO_PORTRAIT"      # 9:16
    SQUARE = "IMAGE_ASPECT_RATIO_SQUARE"          # 1:1


class ImageModel(Enum):
    """Model tạo ảnh."""
    GEM_PIX = "GEM_PIX"
    GEM_PIX_2 = "GEM_PIX_2"  # Default model - phiên bản mới hơn


class ImageInputType(Enum):
    """Loại input image cho reference."""
    REFERENCE = "IMAGE_INPUT_TYPE_REFERENCE"
    STYLE = "IMAGE_INPUT_TYPE_STYLE"
    SUBJECT = "IMAGE_INPUT_TYPE_SUBJECT"


@dataclass
class ImageInput:
    """Input image cho reference khi generate."""
    name: str = ""  # Media name từ response trước đó (preferred)
    input_type: ImageInputType = ImageInputType.REFERENCE
    base64_data: str = ""  # Base64 image data (fallback if no name)
    mime_type: str = "image/png"  # MIME type for base64

    def to_dict(self) -> Dict[str, Any]:
        """Convert sang dict format cho API."""
        result = {
            "imageInputType": self.input_type.value
        }
        if self.name:
            # Prefer media_name reference
            result["name"] = self.name
        elif self.base64_data:
            # Fallback: try inline base64 (may not work but worth trying)
            result["rawImageBytes"] = self.base64_data
            result["mimeType"] = self.mime_type
        return result

    @classmethod
    def from_file(cls, file_path: Path, input_type: ImageInputType = ImageInputType.REFERENCE) -> 'ImageInput':
        """Create ImageInput from local file with base64 data."""
        import base64
        with open(file_path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')

        suffix = file_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp"
        }
        mime = mime_types.get(suffix, "image/png")

        return cls(name="", input_type=input_type, base64_data=data, mime_type=mime)


@dataclass
class GeneratedImage:
    """Kết quả ảnh được tạo."""
    url: Optional[str] = None
    base64_data: Optional[str] = None
    media_id: Optional[str] = None
    media_name: Optional[str] = None  # Name để dùng làm reference
    workflow_id: Optional[str] = None
    seed: Optional[int] = None
    prompt: str = ""
    aspect_ratio: str = ""
    local_path: Optional[Path] = None

    @property
    def has_data(self) -> bool:
        return bool(self.url or self.base64_data or self.media_id)

    def as_reference(self, input_type: ImageInputType = ImageInputType.REFERENCE) -> Optional[ImageInput]:
        """Chuyển thành ImageInput để dùng làm reference cho ảnh khác."""
        if self.media_name:
            return ImageInput(name=self.media_name, input_type=input_type)
        return None


class GoogleFlowAPI:
    """
    Client để tương tác với Google Flow API.

    Sử dụng Bearer Token authentication từ browser session.

    Features:
    - Image generation: batchGenerateImages
    - Video generation: batchAsyncGenerateVideoText (Veo 3)
    - Proxy API support: bypass captcha via nanoai.pics
    """

    BASE_URL = "https://aisandbox-pa.googleapis.com"
    TOOL_NAME = "PINHOLE"  # Internal name for Flow

    # Proxy API for bypassing captcha
    PROXY_VIDEO_API_URL = "https://flow-api.nanoai.pics/api/fix/create-video-veo3"
    PROXY_IMAGE_API_URL = "https://flow-api.nanoai.pics/api/fix/create-image-veo3"

    def __init__(
        self,
        bearer_token: str,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        timeout: int = 120,
        verbose: bool = False,
        proxy_api_token: Optional[str] = None,
        use_proxy: bool = False,
        paygate_tier: PaygateTier = PaygateTier.TIER_TWO,
        extra_headers: Optional[Dict[str, str]] = None
    ):
        """
        Khởi tạo Google Flow API client.

        Args:
            bearer_token: OAuth Bearer token (bắt đầu bằng "ya29.")
            project_id: Project ID (nếu không có sẽ tự tạo UUID)
            session_id: Session ID (nếu không có sẽ tự tạo)
            timeout: Request timeout in seconds
            verbose: Print debug info
            proxy_api_token: Token cho proxy API (nanoai.pics) - bypass captcha
            extra_headers: Extra headers (x-browser-validation, etc.) from Chrome capture
            use_proxy: Sử dụng proxy API thay vì gọi trực tiếp
            paygate_tier: User paygate tier (TIER_ONE hoặc TIER_TWO)
        """
        self.bearer_token = bearer_token.strip()
        self.project_id = project_id or str(uuid.uuid4())
        self.session_id = session_id or f";{int(time.time() * 1000)}"
        self.timeout = timeout
        self.verbose = verbose
        self.proxy_api_token = proxy_api_token
        self.use_proxy = use_proxy
        self.paygate_tier = paygate_tier
        self.extra_headers = extra_headers or {}

        # Validate token format
        if not self.bearer_token.startswith("ya29."):
            print("⚠️  Warning: Bearer token should start with 'ya29.'")

        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Tạo HTTP session với headers chuẩn."""
        session = requests.Session()

        # Base headers
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://labs.google",
            "Referer": "https://labs.google/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        }

        # Add extra headers (x-browser-validation, etc.) if provided
        if self.extra_headers:
            for key, value in self.extra_headers.items():
                if value:  # Only add non-empty values
                    headers[key] = value

        session.headers.update(headers)
        return session
    
    def _log(self, message: str) -> None:
        """Print log message if verbose."""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
    
    def _generate_seed(self) -> int:
        """Tạo random seed cho image generation."""
        return random.randint(1, 999999)
    
    # =========================================================================
    # IMAGE GENERATION
    # =========================================================================
    
    def generate_images(
        self,
        prompt: str,
        count: int = 2,
        aspect_ratio: AspectRatio = AspectRatio.LANDSCAPE,
        model: ImageModel = ImageModel.GEM_PIX_2,
        image_inputs: Optional[List[ImageInput]] = None,
        reference_images: Optional[List[GeneratedImage]] = None
    ) -> Tuple[bool, List[GeneratedImage], str]:
        """
        Tạo ảnh từ prompt sử dụng Flow API.

        Args:
            prompt: Text prompt mô tả ảnh
            count: Số lượng ảnh cần tạo (1-4)
            aspect_ratio: Tỷ lệ khung hình
            model: Model tạo ảnh
            image_inputs: List ImageInput objects cho reference images
            reference_images: List GeneratedImage objects để dùng làm reference
                            (sẽ tự động convert sang ImageInput)

        Returns:
            Tuple[success, list_of_images, error_message]
        """
        self._log(f"Generating {count} images with prompt: {prompt[:50]}...")

        # Build imageInputs array từ ImageInput objects hoặc GeneratedImage
        image_inputs_data = []

        # Priority 1: ImageInput objects
        if image_inputs:
            for img_input in image_inputs:
                if isinstance(img_input, ImageInput):
                    image_inputs_data.append(img_input.to_dict())
                elif isinstance(img_input, dict):
                    # Support dict format directly
                    image_inputs_data.append(img_input)

        # Priority 2: Convert GeneratedImage objects to references
        if reference_images:
            for ref_img in reference_images:
                if isinstance(ref_img, GeneratedImage) and ref_img.media_name:
                    ref_input = ref_img.as_reference()
                    if ref_input:
                        image_inputs_data.append(ref_input.to_dict())

        if image_inputs_data:
            self._log(f"Using {len(image_inputs_data)} reference image(s)")
            # Debug: Show actual imageInputs being sent
            for i, inp in enumerate(image_inputs_data):
                name_preview = inp.get("name", "")[:60] if inp.get("name") else "None"
                inp_type = inp.get("imageInputType", "")
                has_b64 = "rawImageBytes" in inp
                self._log(f"  [{i}] name={name_preview} type={inp_type} has_base64={has_b64}")

        # Build requests array
        requests_data = []
        for _ in range(count):
            request_item = {
                "clientContext": {
                    "sessionId": self.session_id,
                    "projectId": self.project_id,
                    "tool": self.TOOL_NAME
                },
                "seed": self._generate_seed(),
                "imageModelName": model.value,
                "imageAspectRatio": aspect_ratio.value,
                "prompt": prompt,
                "imageInputs": image_inputs_data
            }
            requests_data.append(request_item)
        
        payload = {
            "clientContext": {
                "sessionId": self.session_id,
                "projectId": self.project_id,
                "tool": self.TOOL_NAME
            },
            "requests": requests_data
        }

        # Route to proxy if enabled
        if self.use_proxy and self.proxy_api_token:
            return self._generate_images_via_proxy(payload, prompt, aspect_ratio.value)

        # Direct API call
        url = f"{self.BASE_URL}/v1/projects/{self.project_id}/flowMedia:batchGenerateImages"

        self._log(f"POST {url} (direct)")

        try:
            response = self.session.post(
                url,
                data=json.dumps(payload),
                timeout=self.timeout
            )
            
            self._log(f"Response status: {response.status_code}")
            
            if response.status_code == 401:
                return False, [], "Authentication failed - Bearer token may be expired"
            
            if response.status_code == 403:
                return False, [], "Access forbidden - check permissions"
            
            if response.status_code != 200:
                return False, [], f"API error: {response.status_code} - {response.text[:200]}"
            
            # Parse response
            result = response.json()

            if self.verbose:
                self._log(f"Response: {json.dumps(result, indent=2)[:500]}")

            # === DEBUG: Log raw response structure ===
            self._log(f"=== RAW RESPONSE KEYS: {list(result.keys())}")
            if "media" in result and result["media"]:
                first_media = result["media"][0]
                self._log(f"=== MEDIA[0] KEYS: {list(first_media.keys())}")
                self._log(f"=== MEDIA[0].name: {first_media.get('name')}")
                self._log(f"=== MEDIA[0].workflowId: {first_media.get('workflowId')}")
                # Check nested structures
                if "image" in first_media:
                    img_wrapper = first_media["image"]
                    self._log(f"=== MEDIA[0].image KEYS: {list(img_wrapper.keys())}")
                    if "generatedImage" in img_wrapper:
                        gen_img = img_wrapper["generatedImage"]
                        self._log(f"=== generatedImage KEYS: {list(gen_img.keys())}")
                        # Check for any name-like fields
                        for k in gen_img.keys():
                            if 'name' in k.lower() or 'media' in k.lower() or 'id' in k.lower():
                                self._log(f"=== generatedImage.{k}: {gen_img.get(k)}")
            
            # Extract images from response
            images = self._parse_image_response(result, prompt, aspect_ratio.value)
            
            if images:
                self._log(f"✓ Generated {len(images)} images successfully")
                return True, images, ""
            else:
                # Check if we need to poll for results
                if self._needs_polling(result):
                    return self._poll_for_results(result, prompt, aspect_ratio.value)
                
                return False, [], "No images in response - check response format"
            
        except requests.exceptions.Timeout:
            return False, [], f"Request timeout after {self.timeout}s"
        except requests.exceptions.RequestException as e:
            return False, [], f"Network error: {str(e)}"
        except json.JSONDecodeError as e:
            return False, [], f"Invalid JSON response: {str(e)}"
        except Exception as e:
            return False, [], f"Unexpected error: {str(e)}"

    # Proxy task status endpoint
    PROXY_TASK_STATUS_URL = "https://flow-api.nanoai.pics/api/fix/task-status"

    def _generate_images_via_proxy(
        self,
        payload: Dict[str, Any],
        prompt: str,
        aspect_ratio: str
    ) -> Tuple[bool, List[GeneratedImage], str]:
        """
        Gọi qua proxy API để bypass captcha/recaptcha cho image generation.
        Proxy API là async:
        1. POST /create-image-veo3 → {"success": true, "taskId": "xxx"}
        2. GET /task-status?taskId=xxx → Poll cho đến khi có kết quả
        """
        if not self.proxy_api_token:
            return False, [], "Proxy API token required - set proxy_api_token"

        self._log(f"POST {self.PROXY_IMAGE_API_URL} (via proxy)")

        # Build proxy request - format giống direct Google API
        # QUAN TRONG: Dung payload goc de giu nguyen imageInputs (references)
        # Payload da duoc build trong generate_images() voi imageInputs day du
        proxy_body = payload  # Su dung payload goc thay vi rebuild

        proxy_payload = {
            "body_json": proxy_body,
            "flow_auth_token": self.bearer_token,
            "flow_url": f"{self.BASE_URL}/v1/projects/{self.project_id}/flowMedia:batchGenerateImages"
        }

        # Debug: log the full request
        self._log(f"=== PROXY REQUEST ===")
        self._log(f"URL: {self.PROXY_IMAGE_API_URL}")
        self._log(f"flow_url: {proxy_payload['flow_url']}")
        self._log(f"body_json: {json.dumps(proxy_body)[:500]}")

        try:
            proxy_headers = {
                "Authorization": f"Bearer {self.proxy_api_token}",
                "Content-Type": "application/json"
            }

            # Step 1: Create task
            response = requests.post(
                self.PROXY_IMAGE_API_URL,
                headers=proxy_headers,
                json=proxy_payload,
                timeout=30
            )

            self._log(f"Proxy response status: {response.status_code}")

            if response.status_code == 401:
                return False, [], "Proxy API authentication failed - check proxy_api_token"

            if response.status_code != 200:
                error_text = response.text[:200]
                return False, [], f"Proxy API error: {response.status_code} - {error_text}"

            result = response.json()
            self._log(f"Create task response: {json.dumps(result)[:500]}")

            if not result.get("success"):
                return False, [], f"Proxy create task failed: {result.get('error', 'Unknown')}"

            task_id = result.get("taskId")
            if not task_id:
                return False, [], "No taskId in proxy response"

            self._log(f"Task created: {task_id}")

            # Step 2: Poll for result
            return self._poll_proxy_task(task_id, prompt, aspect_ratio, proxy_headers)

        except requests.exceptions.Timeout:
            return False, [], f"Proxy request timeout"
        except requests.exceptions.RequestException as e:
            return False, [], f"Proxy network error: {str(e)}"
        except Exception as e:
            return False, [], f"Proxy error: {str(e)}"

    def _poll_proxy_task(
        self,
        task_id: str,
        prompt: str,
        aspect_ratio: str,
        headers: Dict[str, str],
        max_attempts: int = 60,
        poll_interval: float = 2.0
    ) -> Tuple[bool, List[GeneratedImage], str]:
        """Poll proxy task status until complete."""
        self._log(f"Polling task {task_id}...")

        for attempt in range(max_attempts):
            try:
                response = requests.get(
                    f"{self.PROXY_TASK_STATUS_URL}?taskId={task_id}",
                    headers=headers,
                    timeout=30
                )

                if response.status_code != 200:
                    self._log(f"Poll attempt {attempt+1}: status {response.status_code}")
                    time.sleep(poll_interval)
                    continue

                result = response.json()
                self._log(f"Poll {attempt+1}: {json.dumps(result)[:300]}")

                if not result.get("success"):
                    time.sleep(poll_interval)
                    continue

                # Check if task completed
                task_result = result.get("result", {})

                # Check for error response from Google API
                if "error" in task_result:
                    error_info = task_result.get("error", {})
                    if isinstance(error_info, dict):
                        error_msg = error_info.get("message", str(error_info))
                    else:
                        error_msg = str(error_info)
                    self._log(f"=== GOOGLE API ERROR ===")
                    self._log(f"Error: {error_msg[:500]}")
                    return False, [], f"Google API error: {error_msg[:200]}"

                if task_result.get("success") == True:
                    # Task completed successfully - extract images
                    self._log(f"Task completed! Extracting images...")
                    images = self._parse_image_response(task_result, prompt, aspect_ratio)
                    if images:
                        return True, images, ""
                    else:
                        # Try parsing from different locations
                        self._log(f"Full task result: {json.dumps(task_result)[:1000]}")
                        return False, [], "Task completed but no images found"

                elif task_result.get("success") == False:
                    error = task_result.get("error", "Unknown error")
                    self._log(f"=== TASK FAILED ===")
                    self._log(f"Full result: {json.dumps(result)}")
                    return False, [], f"Task failed: {error}"

                # Check if we have media/images in result (success without explicit flag)
                if "media" in task_result or "images" in task_result:
                    self._log(f"Task completed (implicit)! Extracting images...")
                    # Debug: log first media item structure
                    if "media" in task_result and task_result["media"]:
                        first_media = task_result["media"][0]
                        self._log(f"First media item keys: {list(first_media.keys())}")
                        if "image" in first_media:
                            img_wrapper = first_media["image"]
                            self._log(f"  image keys: {list(img_wrapper.keys())}")
                            if "generatedImage" in img_wrapper:
                                gen_img = img_wrapper["generatedImage"]
                                self._log(f"  generatedImage keys: {list(gen_img.keys())}")
                                if "name" in gen_img:
                                    self._log(f"  generatedImage.name: {gen_img['name'][:80]}...")
                    images = self._parse_image_response(task_result, prompt, aspect_ratio)
                    if images:
                        return True, images, ""

                # Still processing
                time.sleep(poll_interval)

            except Exception as e:
                self._log(f"Poll error: {e}")
                time.sleep(poll_interval)

        return False, [], f"Polling timeout after {max_attempts} attempts"

    def _parse_image_response(
        self,
        response: Dict[str, Any],
        prompt: str,
        aspect_ratio: str
    ) -> List[GeneratedImage]:
        """
        Parse response từ API để lấy thông tin ảnh.
        
        Actual Flow API Response Format:
        {
          "media": [
            {
              "image": {
                "generatedImage": {
                  "aspectRatio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
                  "encodedImage": "iVBORw0KGgo...",  // Base64 PNG
                  "fifeUrl": "https://storage.googleapis.com/...",
                  "mediaGenerationId": "...",
                  "seed": 634312,
                  "prompt": "cute princess pictures",
                  "modelNameType": "GEM_PIX"
                }
              },
              "name": "...",
              "workflowId": "..."
            }
          ],
          "workflows": [...]
        }
        """
        images = []
        
        # =====================================================================
        # PRIMARY FORMAT: Flow API "media" array (ACTUAL FORMAT)
        # =====================================================================
        if "media" in response:
            for media_item in response["media"]:
                # Navigate: media[].image.generatedImage
                image_wrapper = media_item.get("image", {})
                gen_image = image_wrapper.get("generatedImage", {})

                # Extract media name và workflow ID từ media_item level
                # Thu nhieu fields khac nhau vi API co the thay doi
                media_name = (
                    media_item.get("name") or  # Primary field - expected format
                    media_item.get("mediaName") or  # Alternative naming
                    media_item.get("resourceName") or  # GCP style
                    gen_image.get("name") or  # Inside generatedImage
                    gen_image.get("mediaName") or
                    gen_image.get("resourceName")
                )
                workflow_id = media_item.get("workflowId")
                media_generation_id = gen_image.get("mediaGenerationId")

                # Fallback: use workflowId or mediaGenerationId if no name
                if not media_name and workflow_id:
                    media_name = workflow_id
                    self._log(f"  -> Using workflowId as media_name: {workflow_id[:40]}...")
                elif not media_name and media_generation_id:
                    media_name = media_generation_id
                    self._log(f"  -> Using mediaGenerationId as media_name: {media_generation_id[:40]}...")

                if gen_image:
                    img = GeneratedImage(
                        url=gen_image.get("fifeUrl"),  # Direct download URL
                        base64_data=gen_image.get("encodedImage"),  # Base64 PNG
                        media_id=gen_image.get("mediaGenerationId"),
                        media_name=media_name,  # QUAN TRỌNG: name để dùng làm reference
                        workflow_id=workflow_id,
                        seed=gen_image.get("seed"),
                        prompt=gen_image.get("prompt", prompt),
                        aspect_ratio=gen_image.get("aspectRatio", aspect_ratio)
                    )
                    if img.has_data:
                        images.append(img)
                        self._log(f"  ✓ Parsed image: seed={img.seed}, has_url={bool(img.url)}, has_b64={bool(img.base64_data)}")
                        if media_name:
                            self._log(f"  -> media_name (for I2V): {media_name[:80]}..." if len(media_name) > 80 else f"  -> media_name (for I2V): {media_name}")
        
        # =====================================================================
        # FALLBACK FORMATS (for compatibility)
        # =====================================================================
        
        # Format 2: Direct images array
        if not images and "images" in response:
            for img_data in response["images"]:
                img = GeneratedImage(
                    url=img_data.get("url") or img_data.get("imageUrl") or img_data.get("fifeUrl"),
                    base64_data=img_data.get("base64") or img_data.get("imageBytes") or img_data.get("encodedImage"),
                    media_id=img_data.get("mediaId") or img_data.get("id") or img_data.get("mediaGenerationId"),
                    seed=img_data.get("seed"),
                    prompt=prompt,
                    aspect_ratio=aspect_ratio
                )
                if img.has_data:
                    images.append(img)
        
        # Format 3: Nested in responses array
        if not images and "responses" in response:
            for resp in response["responses"]:
                img_data = resp.get("image", {}).get("generatedImage", resp.get("image", resp))
                img = GeneratedImage(
                    url=img_data.get("url") or img_data.get("fifeUrl"),
                    base64_data=img_data.get("base64") or img_data.get("encodedImage"),
                    media_id=img_data.get("mediaId") or img_data.get("mediaGenerationId"),
                    seed=img_data.get("seed") or resp.get("seed"),
                    prompt=prompt,
                    aspect_ratio=aspect_ratio
                )
                if img.has_data:
                    images.append(img)
        
        # Format 4: Media items (alternative naming)
        if not images and "mediaItems" in response:
            for item in response["mediaItems"]:
                gen_image = item.get("generatedImage", item)
                img = GeneratedImage(
                    url=gen_image.get("url") or gen_image.get("fifeUrl"),
                    base64_data=gen_image.get("base64") or gen_image.get("encodedImage"),
                    media_id=gen_image.get("id") or gen_image.get("mediaGenerationId"),
                    prompt=prompt,
                    aspect_ratio=aspect_ratio
                )
                if img.has_data:
                    images.append(img)
        
        return images
    
    def _needs_polling(self, response: Dict[str, Any]) -> bool:
        """Check if response indicates we need to poll for results."""
        # Common indicators for async processing
        indicators = [
            "operationId" in response,
            "taskId" in response,
            "jobId" in response,
            response.get("status") in ["PENDING", "PROCESSING", "IN_PROGRESS"],
            "done" in response and response["done"] == False,
        ]
        return any(indicators)
    
    def _poll_for_results(
        self,
        initial_response: Dict[str, Any],
        prompt: str,
        aspect_ratio: str,
        max_attempts: int = 30,
        poll_interval: float = 2.0
    ) -> Tuple[bool, List[GeneratedImage], str]:
        """
        Poll API để lấy kết quả khi generation là async.
        """
        self._log("Polling for results...")
        
        # Try to find operation/task ID
        operation_id = (
            initial_response.get("operationId") or
            initial_response.get("taskId") or
            initial_response.get("jobId") or
            initial_response.get("name")
        )
        
        if not operation_id:
            return False, [], "No operation ID found for polling"
        
        # Poll endpoint - adjust based on actual API
        poll_url = f"{self.BASE_URL}/v1/projects/{self.project_id}/media.fetchUserHistoryDirectly"
        
        for attempt in range(max_attempts):
            self._log(f"Poll attempt {attempt + 1}/{max_attempts}")
            time.sleep(poll_interval)
            
            try:
                response = self.session.get(poll_url, timeout=30)
                
                if response.status_code != 200:
                    continue
                
                result = response.json()
                
                # Check if complete
                if result.get("done") == True or result.get("status") == "COMPLETED":
                    images = self._parse_image_response(result, prompt, aspect_ratio)
                    if images:
                        return True, images, ""
                
            except Exception as e:
                self._log(f"Poll error: {e}")
                continue
        
        return False, [], f"Polling timeout after {max_attempts} attempts"
    
    # =========================================================================
    # IMAGE DOWNLOAD
    # =========================================================================
    
    def download_image(
        self,
        image: GeneratedImage,
        output_dir: Path,
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Download ảnh về local.
        
        Flow API cung cấp 2 cách lấy ảnh:
        1. fifeUrl: Direct signed URL từ Google Storage (ưu tiên)
        2. encodedImage: Base64 PNG data
        
        Args:
            image: GeneratedImage object
            output_dir: Thư mục lưu ảnh
            filename: Tên file (không có extension)
            
        Returns:
            Path đến file đã download
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            seed_str = f"_{image.seed}" if image.seed else ""
            filename = f"flow_{timestamp}{seed_str}"
        
        output_path = output_dir / f"{filename}.png"
        
        try:
            # Priority 1: Download from fifeUrl (signed Google Storage URL)
            if image.url:
                self._log(f"Downloading from fifeUrl...")
                
                # Use simple GET request (no auth needed - URL is signed)
                response = requests.get(image.url, timeout=60)
                
                if response.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    image.local_path = output_path
                    self._log(f"✓ Saved to {output_path}")
                    return output_path
                else:
                    self._log(f"URL download failed ({response.status_code}), trying base64...")
            
            # Priority 2: Decode from encodedImage (base64)
            if image.base64_data:
                self._log("Decoding base64 encodedImage...")
                
                # Remove data URL prefix if present
                b64_data = image.base64_data
                if "," in b64_data:
                    b64_data = b64_data.split(",")[1]
                
                # Remove any whitespace/newlines
                b64_data = b64_data.strip().replace("\n", "").replace("\r", "")
                
                img_bytes = base64.b64decode(b64_data)
                
                with open(output_path, "wb") as f:
                    f.write(img_bytes)
                
                image.local_path = output_path
                self._log(f"✓ Saved to {output_path}")
                return output_path
            
            self._log("No URL or base64 data available")
            return None
                
        except Exception as e:
            self._log(f"Download error: {e}")
            return None
    
    def download_all_images(
        self,
        images: List[GeneratedImage],
        output_dir: Path,
        prefix: str = "flow"
    ) -> List[Path]:
        """
        Download tất cả ảnh về local.
        
        Args:
            images: List of GeneratedImage objects
            output_dir: Thư mục lưu ảnh
            prefix: Prefix cho tên file
            
        Returns:
            List of paths to downloaded files
        """
        downloaded = []
        
        for i, img in enumerate(images):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}_{i+1}"
            
            path = self.download_image(img, output_dir, filename)
            if path:
                downloaded.append(path)
        
        return downloaded
    
    # =========================================================================
    # IMAGE UPLOAD (Reference Images)
    # =========================================================================

    def upload_image(
        self,
        image_path: Path,
        image_type: ImageInputType = ImageInputType.REFERENCE,
        aspect_ratio: AspectRatio = AspectRatio.LANDSCAPE
    ) -> Tuple[bool, Optional[ImageInput], str]:
        """
        Upload ảnh local lên Flow để dùng làm reference.

        Args:
            image_path: Đường dẫn đến file ảnh local
            image_type: Loại input (REFERENCE, STYLE, SUBJECT)
            aspect_ratio: Tỷ lệ khung hình của ảnh

        Returns:
            Tuple[success, ImageInput object, error_message]
        """
        image_path = Path(image_path)

        if not image_path.exists():
            return False, None, f"File not found: {image_path}"

        self._log(f"Uploading image: {image_path.name}...")

        try:
            # Read and encode image
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            # Detect mime type
            suffix = image_path.suffix.lower()
            mime_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif"
            }
            mime_type = mime_types.get(suffix, "image/png")

            # Build upload request - sử dụng ASSET_MANAGER tool
            # Endpoint có thể là flowMedia:uploadImage hoặc media:upload
            url = f"{self.BASE_URL}/v1/projects/{self.project_id}/flowMedia:uploadImage"

            # Format đúng theo Flow API
            payload = {
                "clientContext": {
                    "sessionId": self.session_id,
                    "tool": "ASSET_MANAGER"  # Upload dùng ASSET_MANAGER, không phải PINHOLE
                },
                "imageInput": {
                    "aspectRatio": aspect_ratio.value,
                    "isUserUploaded": True,
                    "mimeType": mime_type,
                    "rawImageBytes": image_b64
                }
            }

            self._log(f"POST {url}")

            response = self.session.post(
                url,
                data=json.dumps(payload),
                timeout=self.timeout
            )

            self._log(f"Response status: {response.status_code}")

            if response.status_code == 401:
                return False, None, "Authentication failed - Bearer token may be expired"

            if response.status_code == 403:
                return False, None, "Access forbidden - check permissions"

            if response.status_code not in [200, 201]:
                return False, None, f"Upload failed: {response.status_code} - {response.text[:200]}"

            # Parse response to get media name
            result = response.json()

            if self.verbose:
                self._log(f"Upload response: {json.dumps(result, indent=2)[:500]}")

            # Extract name from response - thử nhiều format khác nhau
            media_name = None

            # Format 1: Direct name field
            if "name" in result:
                media_name = result["name"]
            # Format 2: media array
            elif "media" in result:
                media = result["media"]
                if isinstance(media, list) and len(media) > 0:
                    media_name = media[0].get("name")
                elif isinstance(media, dict):
                    media_name = media.get("name")
            # Format 3: imageInput response
            elif "imageInput" in result:
                img_input = result["imageInput"]
                media_name = img_input.get("name") or img_input.get("mediaName")
            # Format 4: mediaName field
            elif "mediaName" in result:
                media_name = result["mediaName"]

            if media_name:
                self._log(f"✓ Upload successful, media_name: {media_name[:50]}...")
                return True, ImageInput(name=media_name, input_type=image_type), ""
            else:
                # Log full response for debugging
                self._log(f"Response without media_name: {json.dumps(result)[:300]}")
                return False, None, "Upload succeeded but no media name in response"

        except requests.exceptions.Timeout:
            return False, None, f"Upload timeout after {self.timeout}s"
        except requests.exceptions.RequestException as e:
            return False, None, f"Network error: {str(e)}"
        except Exception as e:
            return False, None, f"Upload error: {str(e)}"

    def upload_images(
        self,
        image_paths: List[Path],
        image_type: ImageInputType = ImageInputType.REFERENCE
    ) -> Tuple[List[ImageInput], List[str]]:
        """
        Upload nhiều ảnh cùng lúc.

        Args:
            image_paths: List đường dẫn ảnh
            image_type: Loại input

        Returns:
            Tuple[list of ImageInput, list of errors]
        """
        uploaded = []
        errors = []

        for path in image_paths:
            success, img_input, error = self.upload_image(path, image_type)
            if success and img_input:
                uploaded.append(img_input)
            else:
                errors.append(f"{path.name}: {error}")

        return uploaded, errors

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def generate_and_download(
        self,
        prompt: str,
        output_dir: Path,
        count: int = 2,
        aspect_ratio: AspectRatio = AspectRatio.LANDSCAPE,
        prefix: str = "flow",
        reference_images: Optional[List[GeneratedImage]] = None,
        image_inputs: Optional[List[ImageInput]] = None
    ) -> Tuple[bool, List[Path], str]:
        """
        Tạo ảnh và download về local trong một lần gọi.

        Args:
            prompt: Text prompt
            output_dir: Thư mục lưu ảnh
            count: Số lượng ảnh
            aspect_ratio: Tỷ lệ khung hình
            prefix: Prefix cho tên file
            reference_images: List GeneratedImage objects để dùng làm reference
            image_inputs: List ImageInput objects cho reference (KHÔNG phải base64!)

        Returns:
            Tuple[success, list_of_paths, error_message]
        """
        # Generate with reference images
        success, images, error = self.generate_images(
            prompt=prompt,
            count=count,
            aspect_ratio=aspect_ratio,
            reference_images=reference_images,
            image_inputs=image_inputs
        )

        if not success:
            return False, [], error

        # Download
        paths = self.download_all_images(images, output_dir, prefix)

        if not paths:
            return False, [], "Generation succeeded but download failed"

        return True, paths, ""

    def generate_with_references(
        self,
        prompt: str,
        reference_image_paths: List[Path],
        output_dir: Path,
        count: int = 1,
        aspect_ratio: AspectRatio = AspectRatio.LANDSCAPE,
        prefix: str = "flow"
    ) -> Tuple[bool, List[Path], str]:
        """
        Tạo ảnh với reference images từ file local.

        Workflow:
        1. Upload các ảnh reference
        2. Generate ảnh mới với references
        3. Download kết quả

        Args:
            prompt: Text prompt
            reference_image_paths: List đường dẫn ảnh reference
            output_dir: Thư mục lưu ảnh
            count: Số lượng ảnh
            aspect_ratio: Tỷ lệ khung hình
            prefix: Prefix cho tên file

        Returns:
            Tuple[success, list_of_paths, error_message]
        """
        self._log(f"Generate with {len(reference_image_paths)} reference images...")

        # Step 1: Upload reference images
        uploaded_refs, upload_errors = self.upload_images(reference_image_paths)

        if upload_errors:
            for err in upload_errors:
                self._log(f"Upload error: {err}")

        if not uploaded_refs:
            return False, [], "Failed to upload any reference images"

        self._log(f"Uploaded {len(uploaded_refs)} reference images")

        # Step 2: Generate with references
        return self.generate_and_download(
            prompt=prompt,
            output_dir=output_dir,
            count=count,
            aspect_ratio=aspect_ratio,
            prefix=prefix,
            image_inputs=uploaded_refs
        )

    # =========================================================================
    # VIDEO GENERATION (VEO 3)
    # =========================================================================

    def generate_video(
        self,
        prompt: str,
        aspect_ratio: VideoAspectRatio = VideoAspectRatio.LANDSCAPE,
        model: VideoModel = VideoModel.VEO3_FAST,
        seed: Optional[int] = None,
        scene_id: Optional[str] = None,
        recaptcha_token: str = "",
        reference_image_id: Optional[str] = None
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """
        Tạo video từ prompt sử dụng Veo 3.

        Args:
            prompt: Text prompt mô tả video
            aspect_ratio: Tỷ lệ khung hình (LANDSCAPE, PORTRAIT, SQUARE)
            model: Model video (VEO3_FAST hoặc VEO3_QUALITY)
            seed: Seed cho reproducible results
            scene_id: Scene ID (tự tạo UUID nếu không có)
            recaptcha_token: reCAPTCHA token (để trống nếu dùng proxy)
            reference_image_id: Media ID của ảnh để tạo video từ ảnh (Image-to-Video)

        Returns:
            Tuple[success, VideoGenerationResult, error_message]
        """
        # Determine mode: Image-to-Video or Text-to-Video
        is_i2v = reference_image_id is not None
        mode_str = "Image-to-Video" if is_i2v else "Text-to-Video"
        self._log(f"Generating video ({mode_str}) with prompt: {prompt[:50]}...")

        # Auto-generate seed and scene_id if not provided
        if seed is None:
            seed = self._generate_seed()
        if scene_id is None:
            scene_id = str(uuid.uuid4())

        # For Image-to-Video, use I2V model if not explicitly set
        if is_i2v and model in [VideoModel.VEO3_FAST, VideoModel.VEO3_QUALITY]:
            model = VideoModel.VEO3_I2V_FAST
            self._log(f"Using Image-to-Video model: {model.value}")

        # Build request payload theo format mới
        request_data = {
            "aspectRatio": aspect_ratio.value,
            "seed": seed,
            "textInput": {
                "prompt": prompt
            },
            "videoModelKey": model.value,
            "metadata": {
                "sceneId": scene_id
            }
        }

        # Add referenceImages for Image-to-Video
        if reference_image_id:
            request_data["referenceImages"] = [{
                "imageUsageType": "IMAGE_USAGE_TYPE_ASSET",
                "mediaId": reference_image_id
            }]
            self._log(f"Added reference image: {reference_image_id[:50]}...")

        payload = {
            "clientContext": {
                "recaptchaToken": recaptcha_token,
                "sessionId": self.session_id,
                "projectId": self.project_id,
                "tool": self.TOOL_NAME,
                "userPaygateTier": self.paygate_tier.value
            },
            "requests": [request_data]
        }

        # Chọn endpoint: proxy hoặc direct
        if self.use_proxy and self.proxy_api_token:
            return self._generate_video_via_proxy(payload, prompt, seed, scene_id)
        else:
            return self._generate_video_direct(payload, prompt, seed, scene_id)

    def _generate_video_direct(
        self,
        payload: Dict[str, Any],
        prompt: str,
        seed: int,
        scene_id: str
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """
        Gọi trực tiếp Google API để tạo video.
        Có thể bị captcha nếu không có recaptchaToken hợp lệ.
        """
        url = f"{self.BASE_URL}/v1/video:batchAsyncGenerateVideoText"

        self._log(f"POST {url} (direct)")

        try:
            response = self.session.post(
                url,
                data=json.dumps(payload),
                timeout=self.timeout
            )

            self._log(f"Response status: {response.status_code}")

            if response.status_code == 401:
                return False, VideoGenerationResult(
                    status="failed",
                    prompt=prompt,
                    seed=seed,
                    scene_id=scene_id,
                    error="Authentication failed - Bearer token may be expired"
                ), "Authentication failed - Bearer token may be expired"

            if response.status_code == 403:
                error_text = response.text[:200]
                # Check if captcha required
                if "captcha" in error_text.lower() or "recaptcha" in error_text.lower():
                    return False, VideoGenerationResult(
                        status="failed",
                        prompt=prompt,
                        seed=seed,
                        scene_id=scene_id,
                        error="Captcha required - use proxy API"
                    ), "Captcha required - enable use_proxy=True"
                return False, VideoGenerationResult(
                    status="failed",
                    prompt=prompt,
                    seed=seed,
                    scene_id=scene_id,
                    error=f"Access forbidden: {error_text}"
                ), f"Access forbidden: {error_text}"

            if response.status_code != 200:
                error_text = response.text[:200]
                return False, VideoGenerationResult(
                    status="failed",
                    prompt=prompt,
                    seed=seed,
                    scene_id=scene_id,
                    error=f"API error: {response.status_code}"
                ), f"API error: {response.status_code} - {error_text}"

            # Parse response
            result = response.json()
            return self._parse_video_response(result, prompt, seed, scene_id)

        except requests.exceptions.Timeout:
            return False, VideoGenerationResult(
                status="failed",
                prompt=prompt,
                seed=seed,
                scene_id=scene_id,
                error=f"Timeout after {self.timeout}s"
            ), f"Request timeout after {self.timeout}s"
        except requests.exceptions.RequestException as e:
            return False, VideoGenerationResult(
                status="failed",
                prompt=prompt,
                seed=seed,
                scene_id=scene_id,
                error=str(e)
            ), f"Network error: {str(e)}"
        except Exception as e:
            return False, VideoGenerationResult(
                status="failed",
                prompt=prompt,
                seed=seed,
                scene_id=scene_id,
                error=str(e)
            ), f"Unexpected error: {str(e)}"

    def _generate_video_via_proxy(
        self,
        payload: Dict[str, Any],
        prompt: str,
        seed: int,
        scene_id: str
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """
        Gọi qua proxy API để bypass captcha.
        Proxy API là async:
        1. POST /create-video-veo3 → {"success": true, "taskId": "xxx"}
        2. GET /task-status?taskId=xxx → Poll cho đến khi có kết quả
        """
        if not self.proxy_api_token:
            return False, VideoGenerationResult(
                status="failed",
                prompt=prompt,
                seed=seed,
                scene_id=scene_id,
                error="Proxy API token required"
            ), "Proxy API token required"

        self._log(f"POST {self.PROXY_VIDEO_API_URL} (via proxy)")

        # Build proxy request - format theo nanoai.pics API
        # Copy request data from payload (includes referenceImages if Image-to-Video)
        request_data = payload["requests"][0]

        proxy_request = {
            "aspectRatio": request_data.get("aspectRatio", "VIDEO_ASPECT_RATIO_LANDSCAPE"),
            "textInput": {
                "prompt": prompt
            },
            "videoModelKey": request_data.get("videoModelKey", "veo_3_1_t2v_fast_ultra"),
            "seed": request_data.get("seed"),
            "metadata": request_data.get("metadata", {})
        }

        # Add referenceImages for Image-to-Video
        is_i2v = "referenceImages" in request_data
        if is_i2v:
            proxy_request["referenceImages"] = request_data["referenceImages"]
            self._log(f"Image-to-Video mode with reference image")

        proxy_body = {
            "clientContext": {
                "sessionId": self.session_id,
                "projectId": self.project_id,
                "tool": self.TOOL_NAME,
                "userPaygateTier": self.paygate_tier.value
            },
            "requests": [proxy_request]
        }

        # Choose correct endpoint: Image-to-Video or Text-to-Video
        if is_i2v:
            flow_url = f"{self.BASE_URL}/v1/video:batchAsyncGenerateVideoReferenceImages"
        else:
            flow_url = f"{self.BASE_URL}/v1/video:batchAsyncGenerateVideoText"

        proxy_payload = {
            "body_json": proxy_body,
            "flow_auth_token": self.bearer_token,
            "flow_url": flow_url
        }

        # Debug logging
        self._log(f"=== VIDEO PROXY REQUEST ===")
        self._log(f"flow_url: {proxy_payload['flow_url']}")
        self._log(f"body_json: {json.dumps(proxy_body)[:500]}")

        try:
            proxy_headers = {
                "Authorization": f"Bearer {self.proxy_api_token}",
                "Content-Type": "application/json"
            }

            # Step 1: Create task
            response = requests.post(
                self.PROXY_VIDEO_API_URL,
                headers=proxy_headers,
                json=proxy_payload,
                timeout=30
            )

            self._log(f"Proxy response status: {response.status_code}")

            if response.status_code == 401:
                return False, VideoGenerationResult(
                    status="failed",
                    prompt=prompt,
                    seed=seed,
                    scene_id=scene_id,
                    error="Proxy API authentication failed"
                ), "Proxy API authentication failed - check proxy_api_token"

            if response.status_code != 200:
                error_text = response.text[:200]
                return False, VideoGenerationResult(
                    status="failed",
                    prompt=prompt,
                    seed=seed,
                    scene_id=scene_id,
                    error=f"Proxy error: {response.status_code}"
                ), f"Proxy API error: {response.status_code} - {error_text}"

            result = response.json()
            self._log(f"Create video task response: {json.dumps(result)[:500]}")

            if not result.get("success"):
                return False, VideoGenerationResult(
                    status="failed",
                    prompt=prompt,
                    seed=seed,
                    scene_id=scene_id,
                    error=f"Proxy create task failed: {result.get('error', 'Unknown')}"
                ), f"Proxy create task failed: {result.get('error', 'Unknown')}"

            task_id = result.get("taskId")
            if not task_id:
                return False, VideoGenerationResult(
                    status="failed",
                    prompt=prompt,
                    seed=seed,
                    scene_id=scene_id,
                    error="No taskId in proxy response"
                ), "No taskId in proxy response"

            self._log(f"Video task created: {task_id}")

            # Step 2: Poll for result
            return self._poll_proxy_video_task(task_id, prompt, seed, scene_id, proxy_headers)

        except requests.exceptions.Timeout:
            return False, VideoGenerationResult(
                status="failed",
                prompt=prompt,
                seed=seed,
                scene_id=scene_id,
                error="Proxy request timeout"
            ), "Proxy request timeout"
        except Exception as e:
            return False, VideoGenerationResult(
                status="failed",
                prompt=prompt,
                seed=seed,
                scene_id=scene_id,
                error=str(e)
            ), f"Proxy error: {str(e)}"

    def _poll_proxy_video_task(
        self,
        task_id: str,
        prompt: str,
        seed: int,
        scene_id: str,
        headers: Dict[str, str],
        max_attempts: int = 120,
        poll_interval: float = 5.0
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """
        Poll proxy video task then switch to Google direct polling.

        Workflow (same as working testvideo.py):
        1. Poll proxy to get operations array
        2. Poll Google directly with {"operations": operations} until SUCCESSFUL
        """
        self._log(f"Polling video task {task_id}...")

        # STEP 1: Poll proxy to get operations array
        operations = None
        for attempt in range(30):  # Max 30 attempts for proxy
            try:
                response = requests.get(
                    f"{self.PROXY_TASK_STATUS_URL}?taskId={task_id}",
                    headers=headers,
                    timeout=30
                )

                if response.status_code != 200:
                    self._log(f"Poll attempt {attempt+1}: status {response.status_code}")
                    time.sleep(3)
                    continue

                result = response.json()
                self._log(f"Video poll {attempt+1}: {json.dumps(result)[:300]}")

                if not result.get("success"):
                    if result.get("code") == "failed":
                        error_msg = result.get("message", "Unknown error")
                        return False, VideoGenerationResult(
                            status="failed", prompt=prompt, seed=seed,
                            scene_id=scene_id, error=error_msg
                        ), error_msg
                    time.sleep(3)
                    continue

                task_result = result.get("result", {})

                # Check for error
                if "error" in task_result:
                    error_info = task_result.get("error", {})
                    error_msg = error_info.get("message", str(error_info)) if isinstance(error_info, dict) else str(error_info)
                    self._log(f"=== VIDEO API ERROR ===")
                    self._log(f"Error: {error_msg[:500]}")
                    return False, VideoGenerationResult(
                        status="failed", prompt=prompt, seed=seed,
                        scene_id=scene_id, error=f"Google API error: {error_msg[:200]}"
                    ), f"Google API error: {error_msg[:200]}"

                # Got operations - break out to poll Google directly
                operations = task_result.get("operations", [])
                if operations:
                    self._log(f"Got operations from proxy, switching to Google direct polling...")
                    break

                time.sleep(3)

            except Exception as e:
                self._log(f"Poll error: {e}")
                time.sleep(3)

        if not operations:
            return False, VideoGenerationResult(
                status="failed", prompt=prompt, seed=seed,
                scene_id=scene_id, error="Timeout waiting for operations from proxy"
            ), "Timeout waiting for operations from proxy"

        # STEP 2: Poll Google directly with {"operations": operations}
        # This is EXACTLY like the working testvideo.py script
        return self._poll_google_with_operations(
            operations, prompt, seed, scene_id,
            max_attempts=max_attempts, poll_interval=poll_interval
        )

    def _poll_google_with_operations(
        self,
        operations: List[Dict],
        prompt: str,
        seed: int,
        scene_id: str,
        max_attempts: int = 60,
        poll_interval: float = 5.0
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """
        Poll Google API directly with operations array.
        Uses {"operations": operations} format - SAME AS WORKING SCRIPT.
        """
        url = f"{self.BASE_URL}/v1/video:batchCheckAsyncVideoGenerationStatus"
        self._log(f"Google direct polling: {url}")

        for attempt in range(max_attempts):
            try:
                # Use {"operations": operations} - SAME AS WORKING TESTVIDEO.PY
                payload = {"operations": operations}
                response = self.session.post(url, json=payload, timeout=30)

                self._log(f"Google poll {attempt+1}: status={response.status_code}")

                if response.status_code != 200:
                    self._log(f"Response: {response.text[:200]}")
                    time.sleep(poll_interval)
                    continue

                result = response.json()
                ops = result.get("operations", [])

                if not ops:
                    time.sleep(poll_interval)
                    continue

                op = ops[0]
                status = op.get("status", "")
                self._log(f"Status: {status}")

                # Check for success - MEDIA_GENERATION_STATUS_SUCCESSFUL (same as working script)
                if status == "MEDIA_GENERATION_STATUS_SUCCESSFUL":
                    # Extract video URL from op.operation.metadata.video.fifeUrl
                    video_url = op.get("operation", {}).get("metadata", {}).get("video", {}).get("fifeUrl")

                    if video_url:
                        self._log(f"Video completed! URL: {video_url[:80]}...")
                        return True, VideoGenerationResult(
                            video_url=video_url,
                            operation_id=op.get("operation", {}).get("name"),
                            scene_id=scene_id,
                            status="completed",
                            prompt=prompt,
                            seed=seed
                        ), ""
                    else:
                        self._log(f"Video completed but no URL. Full response: {json.dumps(op)[:500]}")

                # Check for failed
                if "FAILED" in status or "ERROR" in status:
                    error_msg = op.get("error", status)
                    return False, VideoGenerationResult(
                        status="failed", prompt=prompt, seed=seed,
                        scene_id=scene_id, error=f"Video generation failed: {error_msg}"
                    ), f"Video generation failed: {error_msg}"

                # Still pending
                time.sleep(poll_interval)

            except Exception as e:
                self._log(f"Google poll error: {e}")
                time.sleep(poll_interval)

        return False, VideoGenerationResult(
            status="failed", prompt=prompt, seed=seed,
            scene_id=scene_id, error="Google polling timeout"
        ), "Google polling timeout"

    def _poll_google_video_status(
        self,
        operation_name: str,
        prompt: str,
        seed: int,
        scene_id: str,
        max_attempts: int = 100,
        poll_interval: float = 5.0
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """Poll Google's video status endpoint directly using bearer token."""
        url = f"{self.BASE_URL}/v1/video:batchCheckAsyncVideoGenerationStatus"
        self._log(f"Direct Google polling: {url}")

        for attempt in range(max_attempts):
            try:
                payload = {
                    "operationNames": [operation_name]
                }

                response = self.session.post(url, json=payload, timeout=30)
                self._log(f"Google poll {attempt+1}: status={response.status_code}")

                if response.status_code != 200:
                    self._log(f"Response: {response.text[:200]}")
                    time.sleep(poll_interval)
                    continue

                result = response.json()
                self._log(f"Google response: {json.dumps(result)[:400]}")

                # Parse operations array
                operations = result.get("operations", [])
                if not operations:
                    time.sleep(poll_interval)
                    continue

                op = operations[0]
                op_status = op.get("status", "")

                # Still pending
                if op_status == "MEDIA_GENERATION_STATUS_PENDING":
                    time.sleep(poll_interval)
                    continue

                # Success - extract video URL
                if op_status in ["MEDIA_GENERATION_STATUS_SUCCEEDED", "MEDIA_GENERATION_STATUS_COMPLETE"]:
                    video_url = None
                    media_list = op.get("media", [])
                    if media_list:
                        video_info = media_list[0].get("video", {})
                        video_url = video_info.get("url") or video_info.get("videoUrl")

                    if not video_url:
                        video_info = op.get("video", {})
                        video_url = video_info.get("url") or video_info.get("videoUrl")

                    if video_url:
                        self._log(f"Video completed! URL: {video_url[:80]}...")
                        return True, VideoGenerationResult(
                            video_url=video_url,
                            operation_id=operation_name,
                            scene_id=scene_id,
                            status="completed",
                            prompt=prompt,
                            seed=seed
                        ), ""

                # Failed
                if "FAILED" in op_status or "ERROR" in op_status:
                    error_msg = op.get("error", op_status)
                    return False, VideoGenerationResult(
                        status="failed",
                        prompt=prompt,
                        seed=seed,
                        scene_id=scene_id,
                        error=f"Video generation failed: {error_msg}"
                    ), f"Video generation failed: {error_msg}"

                time.sleep(poll_interval)

            except Exception as e:
                self._log(f"Google poll error: {e}")
                time.sleep(poll_interval)

        return False, VideoGenerationResult(
            status="failed",
            prompt=prompt,
            seed=seed,
            scene_id=scene_id,
            error="Google polling timeout"
        ), "Google polling timeout"

    def _parse_video_response(
        self,
        response: Dict[str, Any],
        prompt: str,
        seed: int,
        scene_id: str
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """
        Parse response từ video generation API.
        Video generation là async nên response sẽ chứa operation ID.
        """
        self._log(f"Parsing video response: {json.dumps(response)[:300]}...")

        # Check for errors in response
        if "error" in response:
            error_msg = response.get("error", {}).get("message", str(response["error"]))
            return False, VideoGenerationResult(
                status="failed",
                prompt=prompt,
                seed=seed,
                scene_id=scene_id,
                error=error_msg
            ), error_msg

        # Video generation is async - look for operation/task info
        operation_id = (
            response.get("operationId") or
            response.get("name") or
            response.get("taskId") or
            response.get("jobId")
        )

        # Check if video URL is already available (rare for async)
        video_url = None
        video_id = None

        # Try to find video info in response
        if "videos" in response and response["videos"]:
            video_data = response["videos"][0]
            video_url = video_data.get("url") or video_data.get("videoUrl")
            video_id = video_data.get("id") or video_data.get("videoId")
        elif "media" in response and response["media"]:
            media_data = response["media"][0]
            video_info = media_data.get("video", {})
            video_url = video_info.get("url") or video_info.get("videoUrl")
            video_id = media_data.get("name") or media_data.get("id")

        # Determine status
        status = "pending"
        if video_url:
            status = "completed"
        elif response.get("status") == "PROCESSING":
            status = "processing"
        elif response.get("done") is True:
            status = "completed"

        result = VideoGenerationResult(
            video_url=video_url,
            video_id=video_id,
            scene_id=scene_id,
            operation_id=operation_id,
            status=status,
            prompt=prompt,
            seed=seed
        )

        if status == "completed" and video_url:
            self._log(f"✓ Video generated: {video_url[:60]}...")
            return True, result, ""
        elif operation_id:
            self._log(f"Video generation started, operation: {operation_id[:40]}...")
            return True, result, ""
        else:
            return False, result, "Unknown response format"

    def poll_video_status(
        self,
        operation_id: str,
        max_attempts: int = 60,
        poll_interval: float = 5.0
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """
        Poll để kiểm tra trạng thái video generation.

        Args:
            operation_id: Operation ID từ generate_video response
            max_attempts: Số lần poll tối đa
            poll_interval: Thời gian chờ giữa các lần poll (giây)

        Returns:
            Tuple[success, VideoGenerationResult, error_message]
        """
        self._log(f"Polling video status for: {operation_id[:40]}...")

        for attempt in range(max_attempts):
            self._log(f"Poll attempt {attempt + 1}/{max_attempts}")

            try:
                # TODO: Implement actual polling endpoint
                # Endpoint có thể là:
                # - GET /v1/operations/{operation_id}
                # - GET /v1/video/status/{operation_id}
                # Cần xác định endpoint chính xác từ API docs

                poll_url = f"{self.BASE_URL}/v1/operations/{operation_id}"

                response = self.session.get(poll_url, timeout=30)

                if response.status_code == 200:
                    result = response.json()

                    # Check if done
                    if result.get("done") is True:
                        # Extract video info
                        video_url = None
                        if "response" in result:
                            resp = result["response"]
                            if "videos" in resp:
                                video_url = resp["videos"][0].get("url")

                        return True, VideoGenerationResult(
                            video_url=video_url,
                            operation_id=operation_id,
                            status="completed"
                        ), ""

                    # Still processing
                    if result.get("metadata", {}).get("state") == "PROCESSING":
                        time.sleep(poll_interval)
                        continue

                time.sleep(poll_interval)

            except Exception as e:
                self._log(f"Poll error: {e}")
                time.sleep(poll_interval)
                continue

        return False, VideoGenerationResult(
            operation_id=operation_id,
            status="failed",
            error="Polling timeout"
        ), f"Polling timeout after {max_attempts} attempts"

    def generate_videos_batch(
        self,
        prompts: List[Dict[str, Any]],
        aspect_ratio: VideoAspectRatio = VideoAspectRatio.LANDSCAPE,
        model: VideoModel = VideoModel.VEO3_FAST
    ) -> Tuple[int, int, List[VideoGenerationResult]]:
        """
        Tạo nhiều video cùng lúc.

        Args:
            prompts: List of dicts với keys: prompt, seed (optional), scene_id (optional)
            aspect_ratio: Tỷ lệ khung hình
            model: Model video

        Returns:
            Tuple[success_count, failed_count, results]
        """
        results = []
        success_count = 0
        failed_count = 0

        for item in prompts:
            prompt = item.get("prompt", "")
            seed = item.get("seed")
            scene_id = item.get("scene_id") or item.get("sceneId")

            if not prompt:
                continue

            success, result, error = self.generate_video(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                model=model,
                seed=seed,
                scene_id=scene_id
            )

            results.append(result)

            if success:
                success_count += 1
            else:
                failed_count += 1
                self._log(f"Failed: {error}")

            # Small delay between requests
            time.sleep(1)

        return success_count, failed_count, results

    def download_video(
        self,
        video_result: VideoGenerationResult,
        output_dir: Path,
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Download video về local.

        Args:
            video_result: VideoGenerationResult object
            output_dir: Thư mục lưu video
            filename: Tên file (không có extension)

        Returns:
            Path đến file đã download hoặc None
        """
        if not video_result.video_url:
            self._log("No video URL available")
            return None

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            seed_str = f"_{video_result.seed}" if video_result.seed else ""
            filename = f"veo3_{timestamp}{seed_str}"

        output_path = output_dir / f"{filename}.mp4"

        try:
            self._log(f"Downloading video from: {video_result.video_url[:60]}...")

            response = requests.get(video_result.video_url, timeout=120, stream=True)

            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                video_result.local_path = output_path
                self._log(f"✓ Saved to {output_path}")
                return output_path
            else:
                self._log(f"Download failed: {response.status_code}")
                return None

        except Exception as e:
            self._log(f"Download error: {e}")
            return None

    # =========================================================================
    # TOKEN MANAGEMENT
    # =========================================================================
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test API connection với bearer token hiện tại.
        
        Returns:
            Tuple[success, message]
        """
        self._log("Testing API connection...")
        
        try:
            # Simple test: try to generate a minimal image
            success, images, error = self.generate_images(
                prompt="test",
                count=1,
                aspect_ratio=AspectRatio.SQUARE
            )
            
            if success:
                return True, "Connection successful - API is working"
            else:
                return False, f"Connection test failed: {error}"
                
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def update_token(self, new_token: str) -> None:
        """
        Cập nhật Bearer token mới.
        
        Args:
            new_token: Bearer token mới
        """
        self.bearer_token = new_token.strip()
        self.session.headers["Authorization"] = f"Bearer {self.bearer_token}"
        self._log("Bearer token updated")
    
    @staticmethod
    def get_token_guide() -> str:
        """Hướng dẫn lấy Bearer Token."""
        return """
╔══════════════════════════════════════════════════════════════════════════════╗
║               HƯỚNG DẪN LẤY BEARER TOKEN TỪ GOOGLE FLOW                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  1. Mở trình duyệt (Chrome/Edge) và truy cập:                               ║
║     https://labs.google/fx/vi/tools/flow                                     ║
║                                                                              ║
║  2. Đăng nhập Google account nếu cần                                        ║
║                                                                              ║
║  3. Mở DevTools:                                                            ║
║     - Windows/Linux: F12 hoặc Ctrl + Shift + I                              ║
║     - Mac: Cmd + Option + I                                                  ║
║                                                                              ║
║  4. Chọn tab "Network"                                                      ║
║                                                                              ║
║  5. Thực hiện tạo một ảnh bất kỳ trên trang Flow                           ║
║                                                                              ║
║  6. Trong Network tab, tìm request "flowMedia:batchGenerateImages"         ║
║                                                                              ║
║  7. Click vào request đó, chọn tab "Headers"                                ║
║                                                                              ║
║  8. Tìm dòng "authorization" trong Request Headers                          ║
║     Giá trị sẽ có dạng: Bearer ya29.a0Aa7pCA_VG7SzW...                      ║
║                                                                              ║
║  9. Copy TOÀN BỘ giá trị sau "Bearer " (bắt đầu bằng "ya29.")               ║
║                                                                              ║
║  ⚠️  LƯU Ý QUAN TRỌNG:                                                      ║
║     - Token có thời hạn ngắn (~1 giờ), cần refresh thường xuyên            ║
║     - Mỗi lần refresh trang hoặc tạo ảnh mới sẽ có token mới               ║
║     - Không chia sẻ token với người khác                                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_flow_client(
    token: str,
    project_id: Optional[str] = None,
    verbose: bool = False
) -> GoogleFlowAPI:
    """
    Factory function để tạo GoogleFlowAPI client.
    
    Args:
        token: Bearer token
        project_id: Project ID (optional)
        verbose: Enable verbose logging
        
    Returns:
        GoogleFlowAPI instance
    """
    return GoogleFlowAPI(
        bearer_token=token,
        project_id=project_id,
        verbose=verbose
    )


def quick_generate(
    prompt: str,
    token: str,
    output_dir: str = "./output",
    count: int = 2,
    aspect_ratio: str = "landscape"
) -> List[str]:
    """
    Quick function để tạo ảnh với minimal setup.

    Args:
        prompt: Text prompt
        token: Bearer token
        output_dir: Output directory
        count: Number of images
        aspect_ratio: "landscape", "portrait", or "square"

    Returns:
        List of output file paths
    """
    # Map aspect ratio string
    ar_map = {
        "landscape": AspectRatio.LANDSCAPE,
        "portrait": AspectRatio.PORTRAIT,
        "square": AspectRatio.SQUARE,
        "16:9": AspectRatio.LANDSCAPE,
        "9:16": AspectRatio.PORTRAIT,
        "1:1": AspectRatio.SQUARE,
    }
    ar = ar_map.get(aspect_ratio.lower(), AspectRatio.LANDSCAPE)

    client = GoogleFlowAPI(bearer_token=token, verbose=True)
    success, paths, error = client.generate_and_download(
        prompt=prompt,
        output_dir=Path(output_dir),
        count=count,
        aspect_ratio=ar
    )

    if success:
        return [str(p) for p in paths]
    else:
        print(f"❌ Error: {error}")
        return []


def quick_generate_video(
    prompt: str,
    token: str,
    output_dir: str = "./output",
    aspect_ratio: str = "landscape",
    model: str = "fast",
    proxy_token: Optional[str] = None,
    use_proxy: bool = False
) -> Optional[str]:
    """
    Quick function để tạo video với Veo 3.

    Args:
        prompt: Text prompt mô tả video
        token: Bearer token (ya29.xxx)
        output_dir: Output directory
        aspect_ratio: "landscape", "portrait", or "square"
        model: "fast" hoặc "quality"
        proxy_token: Token cho proxy API (nanoai.pics)
        use_proxy: Sử dụng proxy để bypass captcha

    Returns:
        Path đến video đã download hoặc None
    """
    # Map aspect ratio
    ar_map = {
        "landscape": VideoAspectRatio.LANDSCAPE,
        "portrait": VideoAspectRatio.PORTRAIT,
        "square": VideoAspectRatio.SQUARE,
        "16:9": VideoAspectRatio.LANDSCAPE,
        "9:16": VideoAspectRatio.PORTRAIT,
        "1:1": VideoAspectRatio.SQUARE,
    }
    ar = ar_map.get(aspect_ratio.lower(), VideoAspectRatio.LANDSCAPE)

    # Map model
    model_map = {
        "fast": VideoModel.VEO3_FAST,
        "quality": VideoModel.VEO3_QUALITY,
    }
    vm = model_map.get(model.lower(), VideoModel.VEO3_FAST)

    # Create client
    client = GoogleFlowAPI(
        bearer_token=token,
        verbose=True,
        proxy_api_token=proxy_token,
        use_proxy=use_proxy
    )

    # Generate video
    success, result, error = client.generate_video(
        prompt=prompt,
        aspect_ratio=ar,
        model=vm
    )

    if not success:
        print(f"❌ Error: {error}")
        return None

    # If video URL available, download it
    if result.video_url:
        path = client.download_video(result, Path(output_dir))
        if path:
            return str(path)

    # If async, need to poll
    if result.operation_id:
        print(f"⏳ Video generation started, operation: {result.operation_id}")
        print("   Đang đợi... (video generation có thể mất vài phút)")

        poll_success, poll_result, poll_error = client.poll_video_status(
            result.operation_id,
            max_attempts=60,
            poll_interval=5.0
        )

        if poll_success and poll_result.video_url:
            path = client.download_video(poll_result, Path(output_dir))
            if path:
                return str(path)
        else:
            print(f"❌ Polling failed: {poll_error}")

    return None


def create_video_client(
    token: str,
    project_id: Optional[str] = None,
    proxy_token: Optional[str] = None,
    use_proxy: bool = False,
    verbose: bool = False
) -> GoogleFlowAPI:
    """
    Factory function để tạo GoogleFlowAPI client cho video generation.

    Args:
        token: Bearer token (ya29.xxx)
        project_id: Project ID (optional)
        proxy_token: Token cho proxy API
        use_proxy: Sử dụng proxy để bypass captcha
        verbose: Enable verbose logging

    Returns:
        GoogleFlowAPI instance configured for video
    """
    return GoogleFlowAPI(
        bearer_token=token,
        project_id=project_id,
        verbose=verbose,
        proxy_api_token=proxy_token,
        use_proxy=use_proxy
    )


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys

    print(GoogleFlowAPI.get_token_guide())

    print("\n" + "=" * 70)
    print("VE3 Tool - Google Flow API CLI")
    print("=" * 70)

    if len(sys.argv) < 3:
        print("\nUsage:")
        print("  Image: python google_flow_api.py image <token> <prompt>")
        print("  Video: python google_flow_api.py video <token> <prompt> [--proxy <proxy_token>]")
        print("\nExamples:")
        print("  python google_flow_api.py image 'ya29.xxx' 'a cute cat'")
        print("  python google_flow_api.py video 'ya29.xxx' 'a cat walking'")
        print("  python google_flow_api.py video 'ya29.xxx' 'a cat walking' --proxy 'proxy_token'")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "image":
        if len(sys.argv) < 4:
            print("❌ Missing token or prompt for image mode")
            sys.exit(1)

        token = sys.argv[2]
        prompt = sys.argv[3]

        print(f"\n🎨 Generating images for: {prompt}")
        paths = quick_generate(prompt, token)

        if paths:
            print(f"\n✅ Generated {len(paths)} images:")
            for p in paths:
                print(f"   📁 {p}")
        else:
            print("\n❌ Image generation failed")

    elif mode == "video":
        if len(sys.argv) < 4:
            print("❌ Missing token or prompt for video mode")
            sys.exit(1)

        token = sys.argv[2]
        prompt = sys.argv[3]

        # Check for --proxy flag
        proxy_token = None
        use_proxy = False
        if "--proxy" in sys.argv:
            proxy_idx = sys.argv.index("--proxy")
            if proxy_idx + 1 < len(sys.argv):
                proxy_token = sys.argv[proxy_idx + 1]
                use_proxy = True

        print(f"\n🎬 Generating video for: {prompt}")
        if use_proxy:
            print("   (Using proxy API to bypass captcha)")

        path = quick_generate_video(
            prompt=prompt,
            token=token,
            proxy_token=proxy_token,
            use_proxy=use_proxy
        )

        if path:
            print(f"\n✅ Video saved to: {path}")
        else:
            print("\n❌ Video generation failed")

    else:
        print(f"❌ Unknown mode: {mode}")
        print("   Use 'image' or 'video'")
