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
            result["name"] = self.name
        elif self.base64_data:
            # Google Flow API uses inlineData structure for base64 images
            result["inlineData"] = {
                "mimeType": self.mime_type,
                "data": self.base64_data
            }
        return result

    @classmethod
    def from_file(cls, file_path: Path, input_type: ImageInputType = ImageInputType.REFERENCE) -> 'ImageInput':
        """Create ImageInput from local file with base64 data."""
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
    PROXY_TASK_STATUS_URL = "https://flow-api.nanoai.pics/api/fix/task-status"

    def __init__(
        self,
        bearer_token: str = "",
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
        self.bearer_token = bearer_token.strip() if bearer_token else ""
        self.project_id = project_id or str(uuid.uuid4())
        self.session_id = session_id or f";{int(time.time() * 1000)}"
        self.timeout = timeout
        self.verbose = verbose
        self.proxy_api_token = proxy_api_token
        self.use_proxy = use_proxy
        self.paygate_tier = paygate_tier
        self.extra_headers = extra_headers or {}

        # Validate token format
        if self.bearer_token and not self.bearer_token.startswith("ya29."):
            print("⚠️  Warning: Bearer token should start with 'ya29.'")

        self.session = self._create_session()

    def set_token(self, token: str) -> None:
        """Set Bearer token"""
        if token.startswith("Bearer "):
            token = token[7:]
        self.bearer_token = token
        self.session.headers["Authorization"] = f"Bearer {self.bearer_token}"

    def _create_session(self) -> requests.Session:
        """Tạo HTTP session với headers chuẩn."""
        session = requests.Session()

        headers = {
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://labs.google",
            "Referer": "https://labs.google/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        }

        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        if self.extra_headers:
            for key, value in self.extra_headers.items():
                if value:
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

        Returns:
            Tuple[success, list_of_images, error_message]
        """
        self._log(f"Generating {count} images with prompt: {prompt[:50]}...")

        image_inputs_data = []

        if image_inputs:
            for img_input in image_inputs:
                if isinstance(img_input, ImageInput):
                    image_inputs_data.append(img_input.to_dict())
                elif isinstance(img_input, dict):
                    image_inputs_data.append(img_input)

        if reference_images:
            for ref_img in reference_images:
                if isinstance(ref_img, GeneratedImage) and ref_img.media_name:
                    ref_input = ref_img.as_reference()
                    if ref_input:
                        image_inputs_data.append(ref_input.to_dict())

        if image_inputs_data:
            self._log(f"Using {len(image_inputs_data)} reference image(s)")

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

        if self.use_proxy and self.proxy_api_token:
            return self._generate_images_via_proxy(payload, prompt, aspect_ratio.value)

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

            result = response.json()
            images = self._parse_image_response(result, prompt, aspect_ratio.value)

            if images:
                self._log(f"✓ Generated {len(images)} images successfully")
                return True, images, ""
            else:
                return False, [], "No images in response - check response format"

        except requests.exceptions.Timeout:
            return False, [], f"Request timeout after {self.timeout}s"
        except requests.exceptions.RequestException as e:
            return False, [], f"Network error: {str(e)}"
        except Exception as e:
            return False, [], f"Unexpected error: {str(e)}"

    def _generate_images_via_proxy(
        self,
        payload: Dict[str, Any],
        prompt: str,
        aspect_ratio: str
    ) -> Tuple[bool, List[GeneratedImage], str]:
        """Gọi qua proxy API để bypass captcha."""
        if not self.proxy_api_token:
            return False, [], "Proxy API token required"

        self._log(f"POST {self.PROXY_IMAGE_API_URL} (via proxy)")

        proxy_payload = {
            "body_json": payload,
            "flow_auth_token": self.bearer_token,
            "flow_url": f"{self.BASE_URL}/v1/projects/{self.project_id}/flowMedia:batchGenerateImages"
        }

        try:
            proxy_headers = {
                "Authorization": f"Bearer {self.proxy_api_token}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                self.PROXY_IMAGE_API_URL,
                headers=proxy_headers,
                json=proxy_payload,
                timeout=30
            )

            self._log(f"Proxy response status: {response.status_code}")

            if response.status_code == 401:
                return False, [], "Proxy API authentication failed"

            if response.status_code != 200:
                return False, [], f"Proxy API error: {response.status_code}"

            result = response.json()

            if not result.get("success"):
                return False, [], f"Proxy create task failed: {result.get('error', 'Unknown')}"

            task_id = result.get("taskId")
            if not task_id:
                return False, [], "No taskId in proxy response"

            self._log(f"Task created: {task_id}")
            return self._poll_proxy_task(task_id, prompt, aspect_ratio, proxy_headers)

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
                    time.sleep(poll_interval)
                    continue

                result = response.json()

                if not result.get("success"):
                    time.sleep(poll_interval)
                    continue

                task_result = result.get("result", {})

                if "error" in task_result:
                    error_info = task_result.get("error", {})
                    error_msg = error_info.get("message", str(error_info)) if isinstance(error_info, dict) else str(error_info)
                    return False, [], f"Google API error: {error_msg[:200]}"

                if task_result.get("success") == True:
                    images = self._parse_image_response(task_result, prompt, aspect_ratio)
                    if images:
                        return True, images, ""
                    return False, [], "Task completed but no images found"

                if "media" in task_result or "images" in task_result:
                    images = self._parse_image_response(task_result, prompt, aspect_ratio)
                    if images:
                        return True, images, ""

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
        """Parse response từ API để lấy thông tin ảnh."""
        images = []

        if "media" in response:
            for media_item in response["media"]:
                image_wrapper = media_item.get("image", {})
                gen_image = image_wrapper.get("generatedImage", {})

                media_name = (
                    media_item.get("name") or
                    media_item.get("mediaName") or
                    gen_image.get("name") or
                    gen_image.get("mediaName")
                )
                workflow_id = media_item.get("workflowId")
                media_generation_id = gen_image.get("mediaGenerationId")

                if not media_name and workflow_id:
                    media_name = workflow_id
                elif not media_name and media_generation_id:
                    media_name = media_generation_id

                if gen_image:
                    img = GeneratedImage(
                        url=gen_image.get("fifeUrl"),
                        base64_data=gen_image.get("encodedImage"),
                        media_id=gen_image.get("mediaGenerationId"),
                        media_name=media_name,
                        workflow_id=workflow_id,
                        seed=gen_image.get("seed"),
                        prompt=gen_image.get("prompt", prompt),
                        aspect_ratio=gen_image.get("aspectRatio", aspect_ratio)
                    )
                    if img.has_data:
                        images.append(img)

        if not images and "images" in response:
            for img_data in response["images"]:
                img = GeneratedImage(
                    url=img_data.get("url") or img_data.get("imageUrl") or img_data.get("fifeUrl"),
                    base64_data=img_data.get("base64") or img_data.get("imageBytes") or img_data.get("encodedImage"),
                    media_id=img_data.get("mediaId") or img_data.get("id"),
                    seed=img_data.get("seed"),
                    prompt=prompt,
                    aspect_ratio=aspect_ratio
                )
                if img.has_data:
                    images.append(img)

        return images

    # =========================================================================
    # IMAGE DOWNLOAD
    # =========================================================================

    def download_image(
        self,
        image: GeneratedImage,
        output_dir: Path,
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """Download ảnh về local."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            seed_str = f"_{image.seed}" if image.seed else ""
            filename = f"flow_{timestamp}{seed_str}"

        output_path = output_dir / f"{filename}.png"

        try:
            if image.url:
                self._log(f"Downloading from URL...")
                response = requests.get(image.url, timeout=60)

                if response.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    image.local_path = output_path
                    self._log(f"✓ Saved to {output_path}")
                    return output_path

            if image.base64_data:
                self._log("Decoding base64...")
                b64_data = image.base64_data
                if "," in b64_data:
                    b64_data = b64_data.split(",")[1]

                b64_data = b64_data.strip().replace("\n", "").replace("\r", "")
                img_bytes = base64.b64decode(b64_data)

                with open(output_path, "wb") as f:
                    f.write(img_bytes)

                image.local_path = output_path
                self._log(f"✓ Saved to {output_path}")
                return output_path

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
        """Download tất cả ảnh về local."""
        downloaded = []

        for i, img in enumerate(images):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}_{i+1}"

            path = self.download_image(img, output_dir, filename)
            if path:
                downloaded.append(path)

        return downloaded

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
        """Tạo video từ prompt sử dụng Veo 3."""
        is_i2v = reference_image_id is not None
        self._log(f"Generating video ({'I2V' if is_i2v else 'T2V'}) with prompt: {prompt[:50]}...")

        if seed is None:
            seed = self._generate_seed()
        if scene_id is None:
            scene_id = str(uuid.uuid4())

        if is_i2v and model in [VideoModel.VEO3_FAST, VideoModel.VEO3_QUALITY]:
            model = VideoModel.VEO3_I2V_FAST

        request_data = {
            "aspectRatio": aspect_ratio.value,
            "seed": seed,
            "textInput": {"prompt": prompt},
            "videoModelKey": model.value,
            "metadata": {"sceneId": scene_id}
        }

        if reference_image_id:
            request_data["referenceImages"] = [{
                "imageUsageType": "IMAGE_USAGE_TYPE_ASSET",
                "mediaId": reference_image_id
            }]

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

        if self.use_proxy and self.proxy_api_token:
            return self._generate_video_via_proxy(payload, prompt, seed, scene_id, is_i2v)
        else:
            return self._generate_video_direct(payload, prompt, seed, scene_id)

    def _generate_video_direct(
        self,
        payload: Dict[str, Any],
        prompt: str,
        seed: int,
        scene_id: str
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """Gọi trực tiếp Google API để tạo video."""
        url = f"{self.BASE_URL}/v1/video:batchAsyncGenerateVideoText"

        self._log(f"POST {url} (direct)")

        try:
            response = self.session.post(url, data=json.dumps(payload), timeout=self.timeout)

            if response.status_code == 401:
                return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error="Auth failed"), "Auth failed"

            if response.status_code == 403:
                error_text = response.text[:200]
                if "captcha" in error_text.lower():
                    return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error="Captcha required"), "Captcha required - use proxy"
                return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=error_text), f"Forbidden: {error_text}"

            if response.status_code != 200:
                return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=f"API error: {response.status_code}"), f"API error: {response.status_code}"

            result = response.json()
            return self._parse_video_response(result, prompt, seed, scene_id)

        except Exception as e:
            return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=str(e)), str(e)

    def _generate_video_via_proxy(
        self,
        payload: Dict[str, Any],
        prompt: str,
        seed: int,
        scene_id: str,
        is_i2v: bool = False
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """Gọi qua proxy API để bypass captcha."""
        if not self.proxy_api_token:
            return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error="No proxy token"), "Proxy token required"

        self._log(f"POST {self.PROXY_VIDEO_API_URL} (via proxy)")

        request_data = payload["requests"][0]

        proxy_request = {
            "aspectRatio": request_data.get("aspectRatio", "VIDEO_ASPECT_RATIO_LANDSCAPE"),
            "textInput": {"prompt": prompt},
            "videoModelKey": request_data.get("videoModelKey", "veo_3_1_t2v_fast_ultra"),
            "seed": request_data.get("seed"),
            "metadata": request_data.get("metadata", {})
        }

        if "referenceImages" in request_data:
            proxy_request["referenceImages"] = request_data["referenceImages"]

        proxy_body = {
            "clientContext": {
                "sessionId": self.session_id,
                "projectId": self.project_id,
                "tool": self.TOOL_NAME,
                "userPaygateTier": self.paygate_tier.value
            },
            "requests": [proxy_request]
        }

        flow_url = f"{self.BASE_URL}/v1/video:batchAsyncGenerateVideoReferenceImages" if is_i2v else f"{self.BASE_URL}/v1/video:batchAsyncGenerateVideoText"

        proxy_payload = {
            "body_json": proxy_body,
            "flow_auth_token": self.bearer_token,
            "flow_url": flow_url
        }

        try:
            proxy_headers = {
                "Authorization": f"Bearer {self.proxy_api_token}",
                "Content-Type": "application/json"
            }

            response = requests.post(self.PROXY_VIDEO_API_URL, headers=proxy_headers, json=proxy_payload, timeout=30)

            if response.status_code != 200:
                return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=f"Proxy error: {response.status_code}"), f"Proxy error: {response.status_code}"

            result = response.json()

            if not result.get("success"):
                return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=result.get("error", "Unknown")), result.get("error", "Unknown")

            task_id = result.get("taskId")
            if not task_id:
                return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error="No taskId"), "No taskId in response"

            self._log(f"Video task created: {task_id}")
            return self._poll_proxy_video_task(task_id, prompt, seed, scene_id, proxy_headers)

        except Exception as e:
            return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=str(e)), str(e)

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
        """Poll proxy video task then switch to Google direct polling."""
        self._log(f"Polling video task {task_id}...")

        operations = None
        for attempt in range(30):
            try:
                response = requests.get(f"{self.PROXY_TASK_STATUS_URL}?taskId={task_id}", headers=headers, timeout=30)

                if response.status_code != 200:
                    time.sleep(3)
                    continue

                result = response.json()

                if not result.get("success"):
                    if result.get("code") == "failed":
                        error_msg = result.get("message", "Unknown error")
                        return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=error_msg), error_msg
                    time.sleep(3)
                    continue

                task_result = result.get("result", {})

                if "error" in task_result:
                    error_info = task_result.get("error", {})
                    error_msg = error_info.get("message", str(error_info)) if isinstance(error_info, dict) else str(error_info)
                    return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=error_msg), error_msg

                operations = task_result.get("operations", [])
                if operations:
                    self._log(f"Got operations, switching to Google direct polling...")
                    break

                time.sleep(3)

            except Exception as e:
                self._log(f"Poll error: {e}")
                time.sleep(3)

        if not operations:
            return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error="Timeout waiting for operations"), "Timeout waiting for operations"

        return self._poll_google_with_operations(operations, prompt, seed, scene_id, max_attempts, poll_interval)

    def _poll_google_with_operations(
        self,
        operations: List[Dict],
        prompt: str,
        seed: int,
        scene_id: str,
        max_attempts: int = 60,
        poll_interval: float = 5.0
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """Poll Google API directly with operations array."""
        url = f"{self.BASE_URL}/v1/video:batchCheckAsyncVideoGenerationStatus"
        self._log(f"Google direct polling: {url}")

        for attempt in range(max_attempts):
            try:
                payload = {"operations": operations}
                response = self.session.post(url, json=payload, timeout=30)

                if response.status_code != 200:
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

                if status == "MEDIA_GENERATION_STATUS_SUCCESSFUL":
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

                if "FAILED" in status or "ERROR" in status:
                    error_msg = op.get("error", status)
                    return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=error_msg), error_msg

                time.sleep(poll_interval)

            except Exception as e:
                self._log(f"Google poll error: {e}")
                time.sleep(poll_interval)

        return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error="Polling timeout"), "Polling timeout"

    def _parse_video_response(
        self,
        response: Dict[str, Any],
        prompt: str,
        seed: int,
        scene_id: str
    ) -> Tuple[bool, VideoGenerationResult, str]:
        """Parse response từ video generation API."""
        if "error" in response:
            error_msg = response.get("error", {}).get("message", str(response["error"]))
            return False, VideoGenerationResult(status="failed", prompt=prompt, seed=seed, scene_id=scene_id, error=error_msg), error_msg

        operation_id = response.get("operationId") or response.get("name") or response.get("taskId")

        video_url = None
        if "videos" in response and response["videos"]:
            video_data = response["videos"][0]
            video_url = video_data.get("url") or video_data.get("videoUrl")

        status = "pending"
        if video_url:
            status = "completed"

        result = VideoGenerationResult(
            video_url=video_url,
            scene_id=scene_id,
            operation_id=operation_id,
            status=status,
            prompt=prompt,
            seed=seed
        )

        if status == "completed" and video_url:
            return True, result, ""
        elif operation_id:
            return True, result, ""
        else:
            return False, result, "Unknown response format"

    def download_video(
        self,
        video_result: VideoGenerationResult,
        output_dir: Path,
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """Download video về local."""
        if not video_result.video_url:
            self._log("No video URL available")
            return None

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

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


# Singleton instance
_api_instance: Optional[GoogleFlowAPI] = None


def get_flow_api() -> GoogleFlowAPI:
    """Get singleton instance của GoogleFlowAPI"""
    global _api_instance
    if _api_instance is None:
        _api_instance = GoogleFlowAPI()
    return _api_instance
