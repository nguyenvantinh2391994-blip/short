"""
Video Merger - Ghép video + nhạc + voice + chuyển cảnh
"""

import os
from pathlib import Path
from typing import List, Optional, Callable
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    concatenate_videoclips, vfx, ImageClip
)


class VideoMerger:
    """Ghép nhiều video thành 1, thêm nhạc nền và voice"""

    # Loại chuyển cảnh
    TRANSITION_FADE_BLACK = "fade_black"  # Mờ đen
    TRANSITION_CROSSFADE = "crossfade"    # Mix/hòa trộn

    def __init__(
        self,
        transition_type: str = TRANSITION_FADE_BLACK,
        transition_duration: float = 0.5,
        on_log: Optional[Callable[[str], None]] = None
    ):
        self.transition_type = transition_type
        self.transition_duration = transition_duration
        self.on_log = on_log or print

    def log(self, msg: str):
        """Log message"""
        self.on_log(msg)

    def merge_videos(
        self,
        video_paths: List[str],
        output_path: str,
        music_path: Optional[str] = None,
        voice_path: Optional[str] = None,
        music_volume: float = 0.3,
        voice_volume: float = 1.0,
        mute_original: bool = True
    ) -> bool:
        """
        Ghép nhiều video thành 1

        Args:
            video_paths: Danh sách đường dẫn video
            output_path: Đường dẫn output
            music_path: Đường dẫn file nhạc nền (optional)
            voice_path: Đường dẫn file voice (optional)
            music_volume: Âm lượng nhạc (0-1)
            voice_volume: Âm lượng voice (0-1)
            mute_original: Tắt âm thanh gốc của video (default: True)

        Returns:
            True nếu thành công
        """
        if not video_paths:
            self.log("Không có video để ghép")
            return False

        clips = []

        try:
            self.log(f"Đang load {len(video_paths)} video...")

            # Load tất cả video
            for i, path in enumerate(video_paths):
                if not os.path.exists(path):
                    self.log(f"  Không tìm thấy: {path}")
                    continue

                self.log(f"  [{i+1}/{len(video_paths)}] {Path(path).name}")
                clip = VideoFileClip(path)
                # Tắt âm thanh gốc nếu mute_original=True
                if mute_original:
                    clip = clip.without_audio()
                clips.append(clip)

            if not clips:
                self.log("Không có video hợp lệ")
                return False

            # Áp dụng chuyển cảnh
            self.log(f"Áp dụng chuyển cảnh: {self.transition_type}")

            if len(clips) > 1:
                if self.transition_type == self.TRANSITION_FADE_BLACK:
                    # Fade to black giữa các video
                    processed_clips = []
                    for i, clip in enumerate(clips):
                        # Fade out cuối mỗi clip (trừ clip cuối)
                        if i < len(clips) - 1:
                            clip = clip.fx(vfx.fadeout, self.transition_duration)
                        # Fade in đầu mỗi clip (trừ clip đầu)
                        if i > 0:
                            clip = clip.fx(vfx.fadein, self.transition_duration)
                        processed_clips.append(clip)
                    clips = processed_clips

                elif self.transition_type == self.TRANSITION_CROSSFADE:
                    # Crossfade - ghép với overlap
                    processed_clips = []
                    for i, clip in enumerate(clips):
                        if i > 0:
                            clip = clip.fx(vfx.fadein, self.transition_duration)
                        if i < len(clips) - 1:
                            clip = clip.fx(vfx.fadeout, self.transition_duration)
                        processed_clips.append(clip)
                    clips = processed_clips

            # Ghép video
            self.log("Đang ghép video...")
            if self.transition_type == self.TRANSITION_CROSSFADE and len(clips) > 1:
                # Crossfade với overlap
                final_clip = concatenate_videoclips(
                    clips,
                    method="compose",
                    padding=-self.transition_duration
                )
            else:
                final_clip = concatenate_videoclips(clips, method="compose")

            # Xử lý audio
            audio_clips = []
            target_duration = final_clip.duration  # Mặc định = tổng video

            # Voice (nếu có) - ƯU TIÊN thời lượng voice
            if voice_path and os.path.exists(voice_path):
                self.log(f"Thêm voice: {Path(voice_path).name}")
                voice_audio = AudioFileClip(voice_path)
                voice_duration = voice_audio.duration
                self.log(f"  Thời lượng voice: {voice_duration:.1f}s")
                self.log(f"  Thời lượng video gốc: {final_clip.duration:.1f}s")

                # Nếu voice ngắn hơn video → cắt video
                if voice_duration < final_clip.duration:
                    self.log(f"  → Cắt video theo voice: {voice_duration:.1f}s")
                    final_clip = final_clip.subclip(0, voice_duration)
                    target_duration = voice_duration
                # Nếu voice dài hơn video → LOOP video
                elif voice_duration > final_clip.duration:
                    self.log(f"  → Voice dài hơn video, loop video clips...")

                    # Tính số lần cần loop
                    loops_needed = int(voice_duration / final_clip.duration) + 1
                    self.log(f"  → Loop video {loops_needed} lần")

                    # Tạo list video clips để loop
                    looped_clips = []
                    for i in range(loops_needed):
                        looped_clip = final_clip.copy()
                        looped_clips.append(looped_clip)

                    # Ghép lại
                    final_clip = concatenate_videoclips(looped_clips, method="compose")

                    # Cắt đúng độ dài voice
                    final_clip = final_clip.subclip(0, voice_duration)
                    target_duration = voice_duration
                    self.log(f"  → Video sau loop: {final_clip.duration:.1f}s")
                else:
                    target_duration = voice_duration

                voice_audio = voice_audio.volumex(voice_volume)
                audio_clips.append(voice_audio)
            else:
                self.log("Không có voice - dùng thời lượng video gốc")
                target_duration = final_clip.duration

            # Nhạc nền (nếu có) - cắt theo target_duration
            if music_path and os.path.exists(music_path):
                self.log(f"Thêm nhạc: {Path(music_path).name}")
                music_audio = AudioFileClip(music_path)

                self.log(f"  Thời lượng target: {target_duration:.1f}s")
                self.log(f"  Thời lượng nhạc gốc: {music_audio.duration:.1f}s")

                # Loop nhạc nếu ngắn hơn target
                if music_audio.duration < target_duration:
                    loops_needed = int(target_duration / music_audio.duration) + 1
                    self.log(f"  Loop nhạc {loops_needed} lần")
                    from moviepy.editor import concatenate_audioclips
                    music_clips_list = [music_audio] * loops_needed
                    music_audio = concatenate_audioclips(music_clips_list)

                # Cắt nhạc bằng đúng target_duration
                music_audio = music_audio.subclip(0, target_duration)
                music_audio = music_audio.volumex(music_volume)
                # Fade out nhạc ở cuối (2s)
                music_audio = music_audio.fx(vfx.audio_fadeout, 2)
                audio_clips.append(music_audio)
                self.log(f"  ✓ Đã cắt nhạc = {target_duration:.1f}s")

            # Ghép audio
            if audio_clips:
                self.log("Ghép audio...")
                final_audio = CompositeAudioClip(audio_clips)
                final_clip = final_clip.set_audio(final_audio)

            # Export
            self.log(f"Xuất video: {output_path}")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            final_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=30,
                preset='medium',
                threads=4,
                logger=None  # Tắt log của moviepy
            )

            self.log(f"✓ Hoàn thành: {output_path}")
            return True

        except Exception as e:
            self.log(f"Lỗi ghép video: {e}")
            return False

        finally:
            # Cleanup
            for clip in clips:
                try:
                    clip.close()
                except:
                    pass

    def create_image_clips(
        self,
        image_paths: List[str],
        duration_per_image: float = 1.0,
        target_width: int = 1080,
        target_height: int = 1920
    ) -> List:
        """
        Tạo video clips từ ảnh

        Args:
            image_paths: Danh sách đường dẫn ảnh
            duration_per_image: Thời lượng mỗi ảnh (giây)
            target_width: Chiều rộng video
            target_height: Chiều cao video

        Returns:
            List các ImageClip
        """
        clips = []
        for img_path in image_paths:
            if not os.path.exists(img_path):
                continue
            try:
                clip = ImageClip(img_path, duration=duration_per_image)
                # Resize để fit 9:16
                clip = clip.resize(height=target_height)
                if clip.w > target_width:
                    clip = clip.resize(width=target_width)
                # Center crop nếu cần
                if clip.w != target_width or clip.h != target_height:
                    clip = clip.resize((target_width, target_height))
                clips.append(clip)
            except Exception as e:
                self.log(f"Lỗi load ảnh {img_path}: {e}")
        return clips

    def merge_videos_with_images(
        self,
        video_paths: List[str],
        image_paths: List[str],
        output_path: str,
        music_path: Optional[str] = None,
        voice_path: Optional[str] = None,
        music_volume: float = 0.3,
        voice_volume: float = 1.0,
        mute_original: bool = True,
        image_duration: float = 1.0,
        target_width: int = 1080,
        target_height: int = 1920
    ) -> bool:
        """
        Ghép video + ảnh cuối cùng + nhạc + voice

        Args:
            video_paths: Danh sách video
            image_paths: Danh sách ảnh (hiển thị cuối video)
            output_path: Đường dẫn output
            music_path: Nhạc nền
            voice_path: Voice
            music_volume: Âm lượng nhạc
            voice_volume: Âm lượng voice
            mute_original: Tắt âm thanh gốc
            image_duration: Thời lượng mỗi ảnh (giây)
            target_width: Chiều rộng
            target_height: Chiều cao

        Returns:
            True nếu thành công
        """
        if not video_paths:
            self.log("Không có video để ghép")
            return False

        clips = []
        image_clips = []

        try:
            self.log(f"Đang load {len(video_paths)} video...")

            # Load video clips
            for i, path in enumerate(video_paths):
                if not os.path.exists(path):
                    self.log(f"  Không tìm thấy: {path}")
                    continue

                self.log(f"  [{i+1}/{len(video_paths)}] {Path(path).name}")
                clip = VideoFileClip(path)
                if mute_original:
                    clip = clip.without_audio()
                clips.append(clip)

            if not clips:
                self.log("Không có video hợp lệ")
                return False

            # Tạo image clips (cuối video)
            if image_paths:
                self.log(f"Tạo {len(image_paths)} ảnh cuối video (mỗi ảnh {image_duration}s)...")
                image_clips = self.create_image_clips(
                    image_paths,
                    duration_per_image=image_duration,
                    target_width=target_width,
                    target_height=target_height
                )
                if image_clips:
                    self.log(f"  ✓ Đã tạo {len(image_clips)} ảnh clips")

            # Áp dụng chuyển cảnh cho video
            if len(clips) > 1:
                processed_clips = []
                for i, clip in enumerate(clips):
                    if i < len(clips) - 1:
                        clip = clip.fx(vfx.fadeout, self.transition_duration)
                    if i > 0:
                        clip = clip.fx(vfx.fadein, self.transition_duration)
                    processed_clips.append(clip)
                clips = processed_clips

            # Ghép video
            self.log("Đang ghép video...")
            final_clip = concatenate_videoclips(clips, method="compose")

            # Thêm image clips vào cuối
            if image_clips:
                self.log("Thêm ảnh vào cuối video...")
                # Fade giữa video cuối và ảnh đầu
                image_clips[0] = image_clips[0].fx(vfx.fadein, 0.3)
                # Fade out ảnh cuối
                image_clips[-1] = image_clips[-1].fx(vfx.fadeout, 0.3)

                all_clips = [final_clip] + image_clips
                final_clip = concatenate_videoclips(all_clips, method="compose")
                self.log(f"  Tổng thời lượng: {final_clip.duration:.1f}s")

            # Xử lý audio
            audio_clips = []
            target_duration = final_clip.duration

            # Voice
            if voice_path and os.path.exists(voice_path):
                self.log(f"Thêm voice: {Path(voice_path).name}")
                voice_audio = AudioFileClip(voice_path)
                voice_duration = voice_audio.duration
                self.log(f"  Thời lượng voice: {voice_duration:.1f}s")
                self.log(f"  Thời lượng video: {final_clip.duration:.1f}s")

                # Nếu voice dài hơn video, LOOP video để khớp với voice
                if voice_duration > final_clip.duration:
                    self.log(f"  → Voice dài hơn video, loop video clips...")

                    # Tính số lần cần loop
                    loops_needed = int(voice_duration / final_clip.duration) + 1
                    self.log(f"  → Loop video {loops_needed} lần")

                    # Tạo list video clips để loop
                    looped_clips = []
                    for i in range(loops_needed):
                        # Clone clip cho mỗi lần loop
                        looped_clip = final_clip.copy()
                        looped_clips.append(looped_clip)

                    # Ghép lại
                    final_clip = concatenate_videoclips(looped_clips, method="compose")

                    # Cắt đúng độ dài voice
                    final_clip = final_clip.subclip(0, voice_duration)
                    target_duration = voice_duration
                    self.log(f"  → Video sau loop: {final_clip.duration:.1f}s")

                voice_audio = voice_audio.volumex(voice_volume)
                audio_clips.append(voice_audio)

            # Nhạc nền
            if music_path and os.path.exists(music_path):
                self.log(f"Thêm nhạc: {Path(music_path).name}")
                music_audio = AudioFileClip(music_path)

                # Loop nhạc nếu cần
                if music_audio.duration < target_duration:
                    loops_needed = int(target_duration / music_audio.duration) + 1
                    from moviepy.editor import concatenate_audioclips
                    music_clips_list = [music_audio] * loops_needed
                    music_audio = concatenate_audioclips(music_clips_list)

                music_audio = music_audio.subclip(0, target_duration)
                music_audio = music_audio.volumex(music_volume)
                music_audio = music_audio.fx(vfx.audio_fadeout, 2)
                audio_clips.append(music_audio)

            # Ghép audio
            if audio_clips:
                self.log("Ghép audio...")
                final_audio = CompositeAudioClip(audio_clips)
                final_clip = final_clip.set_audio(final_audio)

            # Export
            self.log(f"Xuất video: {output_path}")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            final_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=30,
                preset='medium',
                threads=4,
                logger=None
            )

            self.log(f"✓ Hoàn thành: {output_path}")
            return True

        except Exception as e:
            self.log(f"Lỗi ghép video: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            for clip in clips + image_clips:
                try:
                    clip.close()
                except:
                    pass


def get_music_for_index(music_folder: str, index: int) -> Optional[str]:
    """Lấy file nhạc theo thứ tự (lặp lại nếu hết)"""
    if not music_folder or not os.path.exists(music_folder):
        return None

    music_files = sorted([
        f for f in os.listdir(music_folder)
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.aac'))
    ])

    if not music_files:
        return None

    # Lấy theo index, lặp lại nếu hết
    music_file = music_files[index % len(music_files)]
    return os.path.join(music_folder, music_file)


def get_voice_for_code(voice_folder: str, product_code: str) -> Optional[str]:
    """Lấy file voice theo mã sản phẩm"""
    if not voice_folder or not os.path.exists(voice_folder):
        return None

    # Tìm file có tên chứa mã sản phẩm
    for f in os.listdir(voice_folder):
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.aac')):
            name = Path(f).stem.upper()
            if product_code.upper() in name or name in product_code.upper():
                return os.path.join(voice_folder, f)

    # Hoặc tìm file có tên chính xác
    for ext in ['.mp3', '.wav', '.m4a', '.aac']:
        path = os.path.join(voice_folder, f"{product_code}{ext}")
        if os.path.exists(path):
            return path

    return None
