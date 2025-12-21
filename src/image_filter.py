"""
Image Filter - Lọc ảnh sản phẩm
- Chỉ giữ ảnh có người (thật)
- Loại bỏ ảnh ghép/collage
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False

from rich.console import Console

console = Console()


@dataclass
class ImageFilterResult:
    """Kết quả lọc ảnh"""
    path: str
    has_person: bool
    is_collage: bool
    should_keep: bool
    reason: str = ""


class ImageFilter:
    """Bộ lọc ảnh sản phẩm"""

    def __init__(
        self,
        require_person: bool = True,
        reject_collage: bool = True,
        min_person_confidence: float = 0.5,
        collage_threshold: float = 0.25,  # Giảm threshold để nhạy hơn
    ):
        """
        Args:
            require_person: Yêu cầu ảnh phải có người
            reject_collage: Loại bỏ ảnh ghép
            min_person_confidence: Độ tin cậy tối thiểu để nhận diện người
            collage_threshold: Ngưỡng để coi là ảnh ghép (lower = stricter)
        """
        self.require_person = require_person
        self.reject_collage = reject_collage
        self.min_person_confidence = min_person_confidence
        self.collage_threshold = collage_threshold

        # Khởi tạo mediapipe pose detector (nhận diện người)
        self._pose = None
        self._face_cascade = None

        if HAS_MEDIAPIPE:
            try:
                self.mp_pose = mp.solutions.pose
                self._pose = self.mp_pose.Pose(
                    static_image_mode=True,
                    model_complexity=1,
                    min_detection_confidence=min_person_confidence
                )
            except Exception as e:
                console.print(f"[yellow]Không khởi tạo được MediaPipe Pose: {e}[/]")

        # Fallback: OpenCV face detection
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self._face_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            console.print(f"[yellow]Không load được face cascade: {e}[/]")

    def detect_person(self, image: np.ndarray) -> Tuple[bool, float]:
        """
        Phát hiện người trong ảnh

        Returns:
            Tuple (có_người, độ_tin_cậy)
        """
        if image is None:
            return False, 0.0

        # Thử MediaPipe Pose trước (nhận diện toàn thân)
        if self._pose is not None:
            try:
                # Convert BGR to RGB
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = self._pose.process(rgb_image)

                if results.pose_landmarks:
                    # Có pose landmarks -> có người
                    # Tính confidence dựa trên visibility của các điểm
                    visibilities = [lm.visibility for lm in results.pose_landmarks.landmark]
                    avg_visibility = sum(visibilities) / len(visibilities)
                    return True, avg_visibility
            except Exception as e:
                console.print(f"[dim]MediaPipe error: {e}[/]")

        # Fallback: OpenCV face detection
        if self._face_cascade is not None:
            try:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = self._face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(30, 30)
                )

                if len(faces) > 0:
                    # Có ít nhất 1 khuôn mặt
                    # Confidence dựa trên kích thước face so với ảnh
                    max_area = max(w * h for (x, y, w, h) in faces)
                    img_area = image.shape[0] * image.shape[1]
                    confidence = min(max_area / img_area * 10, 1.0)  # Scale up, max 1.0
                    return True, confidence
            except Exception as e:
                console.print(f"[dim]Face detection error: {e}[/]")

        return False, 0.0

    def detect_collage(self, image: np.ndarray) -> Tuple[bool, float]:
        """
        Phát hiện ảnh ghép/collage

        Ảnh ghép thường có:
        - Đường biên thẳng rõ ràng chia ảnh (viền màu)
        - Nhiều vùng có histogram khác nhau rõ rệt
        - Grid pattern (chia đều thành 2, 3, 4... phần)
        - Sự thay đổi đột ngột của màu sắc theo chiều dọc/ngang

        Returns:
            Tuple (là_ảnh_ghép, độ_tin_cậy)
        """
        if image is None:
            return False, 0.0

        try:
            h, w = image.shape[:2]
            scores = []

            # 1. Phát hiện đường biên dọc (viền màu giữa các ảnh)
            vertical_score = self._detect_color_borders_vertical(image)
            scores.append(("vertical_border", vertical_score))

            # 2. Phát hiện sự thay đổi đột ngột của histogram theo chiều dọc
            histogram_score = self._detect_histogram_jumps(image)
            scores.append(("histogram_jump", histogram_score))

            # 3. Kiểm tra nhiều khuôn mặt cách đều nhau (grid pattern)
            face_grid_score = self._detect_face_grid(image)
            scores.append(("face_grid", face_grid_score))

            # 4. Phát hiện viền màu (colored border)
            border_score = self._detect_colored_border(image)
            scores.append(("colored_border", border_score))

            # 5. Kiểm tra region khác nhau
            region_score = self._detect_region_differences(image)
            scores.append(("region_diff", region_score))

            # Tổng hợp - lấy max của các scores
            max_score = max(s[1] for s in scores)

            # Nếu có bất kỳ score nào cao -> là collage
            is_collage = max_score >= self.collage_threshold

            # Debug
            if max_score > 0.1:
                reason = ", ".join([f"{name}={val:.2f}" for name, val in scores if val > 0.1])
                console.print(f"[dim]Collage scores: {reason}[/]")

            return is_collage, max_score

        except Exception as e:
            console.print(f"[dim]Collage detection error: {e}[/]")
            return False, 0.0

    def _detect_color_borders_vertical(self, image: np.ndarray) -> float:
        """
        Phát hiện đường biên dọc có màu (viền giữa các ảnh ghép)
        """
        h, w = image.shape[:2]

        # Các vị trí có thể có đường chia (1/2, 1/3, 2/3, 1/4, 3/4)
        check_positions = [w // 2, w // 3, 2 * w // 3, w // 4, 3 * w // 4]

        max_score = 0.0

        for pos in check_positions:
            if pos <= 20 or pos >= w - 20:
                continue

            # Lấy cột pixel tại vị trí này (rộng 10px)
            col_strip = image[:, pos-5:pos+5]

            # Tính độ đồng nhất của màu trong strip này
            # Nếu strip có màu đồng nhất (viền) -> là collage
            std_per_channel = np.std(col_strip, axis=(0, 1))
            avg_std = np.mean(std_per_channel)

            # So sánh với vùng bên cạnh
            left_strip = image[:, pos-30:pos-10] if pos > 30 else None
            right_strip = image[:, pos+10:pos+30] if pos < w - 30 else None

            if left_strip is not None and right_strip is not None:
                left_std = np.mean(np.std(left_strip, axis=(0, 1)))
                right_std = np.mean(np.std(right_strip, axis=(0, 1)))

                # Nếu strip giữa đồng nhất hơn 2 bên -> có viền
                if avg_std < min(left_std, right_std) * 0.5:
                    max_score = max(max_score, 0.8)
                    continue

            # Kiểm tra sự khác biệt màu giữa 2 bên
            if left_strip is not None and right_strip is not None:
                left_mean = np.mean(left_strip, axis=(0, 1))
                right_mean = np.mean(right_strip, axis=(0, 1))
                color_diff = np.linalg.norm(left_mean - right_mean)

                # Nếu 2 bên khác màu nhiều -> có thể là collage
                if color_diff > 50:  # Threshold cho sự khác biệt màu
                    score = min(color_diff / 100, 1.0)
                    max_score = max(max_score, score * 0.6)

        return max_score

    def _detect_histogram_jumps(self, image: np.ndarray) -> float:
        """
        Phát hiện sự thay đổi đột ngột của histogram theo chiều dọc
        (ảnh ghép thường có sự thay đổi đột ngột tại đường nối)
        """
        h, w = image.shape[:2]

        # Chia ảnh thành các cột và tính histogram mỗi cột
        num_strips = 6
        strip_width = w // num_strips
        histograms = []

        for i in range(num_strips):
            start = i * strip_width
            end = start + strip_width
            strip = image[:, start:end]

            hist = cv2.calcHist([strip], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            histograms.append(hist)

        # So sánh histogram giữa các cột liền kề
        max_diff = 0.0
        for i in range(len(histograms) - 1):
            diff = cv2.compareHist(histograms[i], histograms[i + 1], cv2.HISTCMP_BHATTACHARYYA)
            max_diff = max(max_diff, diff)

        # Nếu có sự khác biệt lớn -> có thể là collage
        # Bhattacharyya distance > 0.5 là khá khác nhau
        if max_diff > 0.4:
            return min((max_diff - 0.3) / 0.4, 1.0)

        return 0.0

    def _detect_face_grid(self, image: np.ndarray) -> float:
        """
        Phát hiện nhiều khuôn mặt cách đều nhau (dấu hiệu của ảnh ghép)
        """
        if self._face_cascade is None:
            return 0.0

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self._face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,  # Giảm để detect nhiều hơn
                minSize=(20, 20)
            )

            if len(faces) < 2:
                return 0.0

            # Nếu có >= 2 faces với khoảng cách x tương tự -> grid
            h, w = image.shape[:2]
            face_centers_x = sorted([(x + fw // 2) for x, y, fw, fh in faces])

            if len(face_centers_x) >= 2:
                # Tính khoảng cách giữa các face
                gaps = []
                for i in range(len(face_centers_x) - 1):
                    gaps.append(face_centers_x[i + 1] - face_centers_x[i])

                # Nếu khoảng cách gần bằng nhau -> grid pattern
                if len(gaps) >= 1:
                    avg_gap = sum(gaps) / len(gaps)
                    expected_gap = w / (len(face_centers_x))

                    # Nếu gap gần với chia đều -> collage
                    if abs(avg_gap - expected_gap) < expected_gap * 0.3:
                        return 0.7

            # Nếu có >= 3 faces -> khả năng cao là collage
            if len(faces) >= 3:
                return 0.5

            return 0.0

        except Exception:
            return 0.0

    def _detect_colored_border(self, image: np.ndarray) -> float:
        """
        Phát hiện viền màu (border) xung quanh hoặc ở giữa ảnh
        """
        h, w = image.shape[:2]

        # Kiểm tra viền trái
        left_border = image[:, 0:min(20, w//10)]
        left_std = np.std(left_border, axis=(0, 1))

        # Kiểm tra viền phải
        right_border = image[:, max(0, w - 20):]
        right_std = np.std(right_border, axis=(0, 1))

        # Nếu viền có màu đồng nhất (std thấp) và khác với phần còn lại
        score = 0.0

        # Viền đồng nhất = std thấp
        if np.mean(left_std) < 30:
            # Kiểm tra màu viền có khác với phần trong không
            inner = image[:, 30:w//3]
            inner_mean = np.mean(inner, axis=(0, 1))
            border_mean = np.mean(left_border, axis=(0, 1))
            diff = np.linalg.norm(inner_mean - border_mean)
            if diff > 40:
                score = max(score, 0.6)

        if np.mean(right_std) < 30:
            inner = image[:, 2*w//3:w-30]
            inner_mean = np.mean(inner, axis=(0, 1))
            border_mean = np.mean(right_border, axis=(0, 1))
            diff = np.linalg.norm(inner_mean - border_mean)
            if diff > 40:
                score = max(score, 0.6)

        return score

    def _detect_region_differences(self, image: np.ndarray) -> float:
        """Phát hiện sự khác biệt giữa các vùng trong ảnh (chia theo chiều dọc)"""
        h, w = image.shape[:2]

        # Chia thành 3 phần theo chiều dọc (cho ảnh ghép 3 cột)
        third_w = w // 3
        regions = [
            image[:, 0:third_w],           # Left
            image[:, third_w:2*third_w],   # Middle
            image[:, 2*third_w:w],         # Right
        ]

        # Tính histogram cho mỗi vùng
        histograms = []
        for region in regions:
            if region.size == 0:
                continue
            hist = cv2.calcHist([region], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            histograms.append(hist)

        if len(histograms) < 3:
            return 0.0

        # So sánh histogram giữa các vùng liền kề
        diff_01 = cv2.compareHist(histograms[0], histograms[1], cv2.HISTCMP_BHATTACHARYYA)
        diff_12 = cv2.compareHist(histograms[1], histograms[2], cv2.HISTCMP_BHATTACHARYYA)
        diff_02 = cv2.compareHist(histograms[0], histograms[2], cv2.HISTCMP_BHATTACHARYYA)

        # Nếu cả 3 vùng đều khác nhau -> collage
        avg_diff = (diff_01 + diff_12 + diff_02) / 3

        if avg_diff > 0.35:
            return min((avg_diff - 0.2) / 0.4, 1.0)

        return 0.0

    def filter_image(self, image_path: str) -> ImageFilterResult:
        """
        Lọc một ảnh

        Args:
            image_path: Đường dẫn ảnh

        Returns:
            ImageFilterResult
        """
        path = Path(image_path)

        if not path.exists():
            return ImageFilterResult(
                path=str(path),
                has_person=False,
                is_collage=False,
                should_keep=False,
                reason="File không tồn tại"
            )

        # Đọc ảnh
        image = cv2.imread(str(path))
        if image is None:
            return ImageFilterResult(
                path=str(path),
                has_person=False,
                is_collage=False,
                should_keep=False,
                reason="Không đọc được ảnh"
            )

        # Detect person
        has_person, person_conf = self.detect_person(image)

        # Detect collage
        is_collage, collage_conf = self.detect_collage(image)

        # Quyết định giữ hay bỏ
        should_keep = True
        reason = ""

        # Ưu tiên check collage trước
        if self.reject_collage and is_collage:
            should_keep = False
            reason = f"Ảnh ghép (conf: {collage_conf:.2f})"
        elif self.require_person and not has_person:
            should_keep = False
            reason = "Không có người trong ảnh"
        elif has_person:
            reason = f"Có người (conf: {person_conf:.2f})"
        else:
            reason = "Không phát hiện đặc điểm đặc biệt"

        return ImageFilterResult(
            path=str(path),
            has_person=has_person,
            is_collage=is_collage,
            should_keep=should_keep,
            reason=reason
        )

    def filter_folder(
        self,
        folder_path: str,
        output_folder: str = None,
        move_rejected: bool = False,
        on_progress: callable = None
    ) -> Tuple[List[ImageFilterResult], List[ImageFilterResult]]:
        """
        Lọc tất cả ảnh trong thư mục

        Args:
            folder_path: Thư mục chứa ảnh
            output_folder: Thư mục output (nếu muốn copy ảnh tốt)
            move_rejected: Di chuyển ảnh bị loại vào thư mục _rejected
            on_progress: Callback (current, total, image_name)

        Returns:
            Tuple (ảnh_giữ, ảnh_loại)
        """
        folder = Path(folder_path)
        if not folder.exists():
            return [], []

        # Tìm tất cả ảnh
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        images = []
        for ext in image_extensions:
            images.extend(folder.glob(f'*{ext}'))
            images.extend(folder.glob(f'*{ext.upper()}'))

        images = sorted(set(images))
        total = len(images)

        if total == 0:
            return [], []

        kept = []
        rejected = []

        for i, img_path in enumerate(images):
            if on_progress:
                on_progress(i + 1, total, img_path.name)

            result = self.filter_image(str(img_path))

            if result.should_keep:
                kept.append(result)
            else:
                rejected.append(result)

                # Di chuyển ảnh bị loại nếu cần
                if move_rejected:
                    rejected_folder = folder / "_rejected"
                    rejected_folder.mkdir(exist_ok=True)
                    try:
                        import shutil
                        shutil.move(str(img_path), str(rejected_folder / img_path.name))
                    except Exception as e:
                        console.print(f"[yellow]Không di chuyển được {img_path.name}: {e}[/]")

        # Copy ảnh tốt vào output folder nếu có
        if output_folder and kept:
            out = Path(output_folder)
            out.mkdir(parents=True, exist_ok=True)
            for i, result in enumerate(kept, 1):
                try:
                    import shutil
                    src = Path(result.path)
                    dst = out / f"{i:02d}{src.suffix}"
                    shutil.copy2(str(src), str(dst))
                except Exception as e:
                    console.print(f"[yellow]Không copy được {src.name}: {e}[/]")

        return kept, rejected

    def close(self):
        """Đóng resources"""
        if self._pose:
            self._pose.close()
            self._pose = None


def filter_product_images(
    folder_path: str,
    require_person: bool = True,
    reject_collage: bool = True,
    move_rejected: bool = True,
    on_log: callable = None
) -> Tuple[int, int]:
    """
    Utility function để lọc ảnh sản phẩm trong thư mục

    Args:
        folder_path: Thư mục chứa ảnh
        require_person: Yêu cầu có người
        reject_collage: Loại ảnh ghép
        move_rejected: Di chuyển ảnh bị loại vào _rejected
        on_log: Callback log

    Returns:
        Tuple (số_ảnh_giữ, số_ảnh_loại)
    """
    log = on_log or console.print

    filter_obj = ImageFilter(
        require_person=require_person,
        reject_collage=reject_collage
    )

    try:
        log(f"[cyan]🔍 Đang lọc ảnh trong {folder_path}...[/]")

        kept, rejected = filter_obj.filter_folder(
            folder_path,
            move_rejected=move_rejected,
            on_progress=lambda c, t, n: log(f"  [{c}/{t}] {n}")
        )

        log(f"[green]✓ Giữ {len(kept)} ảnh, loại {len(rejected)} ảnh[/]")

        for r in rejected:
            log(f"  [dim]❌ {Path(r.path).name}: {r.reason}[/]")

        return len(kept), len(rejected)

    finally:
        filter_obj.close()
