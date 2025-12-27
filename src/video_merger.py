"""
Video Merger - Ghép video + nhạc + voice + chuyển cảnh
"""

import os
import random
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
    TRANSITION_NONE = "none"              # Không chuyển cảnh

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
        target_width: int = None,
        target_height: int = None
    ) -> List:
        """
        Tạo video clips từ ảnh

        Args:
            image_paths: Danh sách đường dẫn ảnh
            duration_per_image: Thời lượng mỗi ảnh (giây)
            target_width: Chiều rộng video (None = giữ nguyên)
            target_height: Chiều cao video (None = giữ nguyên)

        Returns:
            List các ImageClip
        """
        clips = []
        for img_path in image_paths:
            if not os.path.exists(img_path):
                continue
            try:
                clip = ImageClip(img_path, duration=duration_per_image)
                # Giữ nguyên kích thước gốc, không resize
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


    def merge_with_sora(
        self,
        sora_video: str,
        grok_videos: List[str],
        output_path: str,
        music_path: Optional[str] = None,
        voice_path: Optional[str] = None,
        music_volume: float = 0.3,
        voice_volume: float = 1.0,
        mute_original: bool = True
    ) -> bool:
        """
        Ghép video SORA + Grok, voice/music bắt đầu từ Grok

        Args:
            sora_video: Đường dẫn video SORA (ở đầu)
            grok_videos: Danh sách video Grok
            output_path: Đường dẫn output
            music_path: Nhạc nền (bắt đầu từ Grok)
            voice_path: Voice (bắt đầu từ Grok)
            music_volume: Âm lượng nhạc
            voice_volume: Âm lượng voice
            mute_original: Tắt âm thanh gốc

        Flow:
            [SORA video - không có audio] + [Grok videos + voice + music]
        """
        clips = []
        sora_duration = 0

        try:
            # 1. Load SORA video (ở đầu, không audio)
            if sora_video and os.path.exists(sora_video):
                self.log(f"Load SORA: {Path(sora_video).name}")
                sora_clip = VideoFileClip(sora_video).without_audio()
                sora_duration = sora_clip.duration
                self.log(f"  SORA duration: {sora_duration:.1f}s")

                # Fade out cuối SORA
                sora_clip = sora_clip.fx(vfx.fadeout, self.transition_duration)
                clips.append(sora_clip)
            else:
                self.log("Không có video SORA")

            # 2. Load Grok videos
            if not grok_videos:
                self.log("Không có video Grok")
                if not clips:
                    return False

            grok_clips = []
            for i, path in enumerate(grok_videos):
                if not os.path.exists(path):
                    continue
                self.log(f"Load Grok [{i+1}/{len(grok_videos)}]: {Path(path).name}")
                clip = VideoFileClip(path)
                if mute_original:
                    clip = clip.without_audio()

                # Fade in đầu clip đầu tiên (nối với SORA)
                if i == 0 and sora_duration > 0:
                    clip = clip.fx(vfx.fadein, self.transition_duration)
                # Fade giữa các Grok clips
                if i > 0:
                    clip = clip.fx(vfx.fadein, self.transition_duration)
                if i < len(grok_videos) - 1:
                    clip = clip.fx(vfx.fadeout, self.transition_duration)

                grok_clips.append(clip)

            clips.extend(grok_clips)

            if not clips:
                self.log("Không có video hợp lệ")
                return False

            # 3. Ghép video
            self.log("Ghép video...")
            final_clip = concatenate_videoclips(clips, method="compose")
            total_duration = final_clip.duration
            grok_duration = total_duration - sora_duration

            self.log(f"  Tổng: {total_duration:.1f}s (SORA: {sora_duration:.1f}s + Grok: {grok_duration:.1f}s)")

            # 4. Xử lý audio (bắt đầu từ Grok, offset = sora_duration)
            audio_clips = []
            audio_offset = sora_duration  # Voice/music bắt đầu sau SORA

            # Voice
            if voice_path and os.path.exists(voice_path):
                self.log(f"Thêm voice (offset {audio_offset:.1f}s): {Path(voice_path).name}")
                voice_audio = AudioFileClip(voice_path)
                voice_audio = voice_audio.volumex(voice_volume)
                # Offset voice để bắt đầu sau SORA
                voice_audio = voice_audio.set_start(audio_offset)
                audio_clips.append(voice_audio)

            # Nhạc nền
            if music_path and os.path.exists(music_path):
                self.log(f"Thêm nhạc (offset {audio_offset:.1f}s): {Path(music_path).name}")
                music_audio = AudioFileClip(music_path)

                # Loop nhạc nếu cần (cho phần Grok)
                if music_audio.duration < grok_duration:
                    loops_needed = int(grok_duration / music_audio.duration) + 1
                    from moviepy.editor import concatenate_audioclips
                    music_clips_list = [music_audio] * loops_needed
                    music_audio = concatenate_audioclips(music_clips_list)

                # Cắt nhạc = độ dài Grok
                music_audio = music_audio.subclip(0, grok_duration)
                music_audio = music_audio.volumex(music_volume)
                music_audio = music_audio.fx(vfx.audio_fadeout, 2)
                # Offset music để bắt đầu sau SORA
                music_audio = music_audio.set_start(audio_offset)
                audio_clips.append(music_audio)

            # 5. Ghép audio
            if audio_clips:
                self.log("Ghép audio...")
                final_audio = CompositeAudioClip(audio_clips)
                final_clip = final_clip.set_audio(final_audio)

            # 6. Export
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

            self.log(f"Hoàn thành: {output_path}")
            return True

        except Exception as e:
            self.log(f"Lỗi merge_with_sora: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            for clip in clips:
                try:
                    clip.close()
                except:
                    pass

    def _get_random_transition(self) -> str:
        """Chọn ngẫu nhiên 1 trong 3 loại transition"""
        return random.choice([
            self.TRANSITION_FADE_BLACK,
            self.TRANSITION_CROSSFADE,
            self.TRANSITION_NONE
        ])

    def _apply_transition_to_clip(
        self,
        clip,
        transition_type: str,
        is_first: bool = False,
        is_last: bool = False
    ):
        """
        Áp dụng transition cho clip

        Args:
            clip: Video clip
            transition_type: Loại transition
            is_first: Là clip đầu tiên
            is_last: Là clip cuối cùng

        Returns:
            Clip đã xử lý
        """
        if transition_type == self.TRANSITION_NONE:
            return clip

        duration = self.transition_duration

        if transition_type == self.TRANSITION_FADE_BLACK:
            if not is_first:
                clip = clip.fx(vfx.fadein, duration)
            if not is_last:
                clip = clip.fx(vfx.fadeout, duration)
        elif transition_type == self.TRANSITION_CROSSFADE:
            if not is_first:
                clip = clip.fx(vfx.fadein, duration)
            if not is_last:
                clip = clip.fx(vfx.fadeout, duration)

        return clip

    def merge_full(
        self,
        sora_videos: List[str],
        grok_videos: List[str],
        flow_images: List[str],
        output_path: str,
        music_path: Optional[str] = None,
        voice_path: Optional[str] = None,
        music_volume: float = 0.6,
        voice_volume: float = 1.0,
        image_duration: float = 0.5,
        mute_original: bool = True
    ) -> bool:
        """
        Ghép video hoàn chỉnh theo thứ tự:
        1. SORA videos (đầu tiên)
        2. Grok videos (voice bắt đầu từ đây)
        3. Flow images (cuối cùng, mỗi ảnh 0.5s)

        Chuyển cảnh: Random giữa fade_black, crossfade, none
        Music: Random từ thư mục music, 60% volume, BẮT ĐẦU TỪ ĐẦU VIDEO
        Voice: Bắt đầu từ Grok video (sau SORA)

        Args:
            sora_videos: Danh sách video SORA
            grok_videos: Danh sách video Grok
            flow_images: Danh sách ảnh Flow
            output_path: Đường dẫn output
            music_path: Đường dẫn file nhạc (random từ music folder)
            voice_path: Đường dẫn file voice
            music_volume: Âm lượng nhạc (default 0.6 = 60%)
            voice_volume: Âm lượng voice
            image_duration: Thời lượng mỗi ảnh (default 0.5s)
            mute_original: Tắt âm thanh gốc của video

        Returns:
            True nếu thành công
        """
        all_clips = []
        sora_clips = []
        grok_clips = []
        image_clips = []
        sora_total_duration = 0

        try:
            # ===== 1. Load SORA videos =====
            if sora_videos:
                self.log(f"Đang load {len(sora_videos)} video SORA...")
                for i, path in enumerate(sora_videos):
                    if not os.path.exists(path):
                        continue
                    self.log(f"  SORA [{i+1}]: {Path(path).name}")
                    clip = VideoFileClip(path)
                    if mute_original:
                        clip = clip.without_audio()

                    # Random transition
                    transition = self._get_random_transition()
                    is_first = (i == 0)
                    is_last = (i == len(sora_videos) - 1) and not grok_videos and not flow_images
                    clip = self._apply_transition_to_clip(clip, transition, is_first, is_last)

                    sora_clips.append(clip)
                    sora_total_duration += clip.duration

                self.log(f"  Tổng SORA: {sora_total_duration:.1f}s")

            # ===== 2. Load Grok videos =====
            if grok_videos:
                self.log(f"Đang load {len(grok_videos)} video Grok...")
                for i, path in enumerate(grok_videos):
                    if not os.path.exists(path):
                        continue
                    self.log(f"  Grok [{i+1}]: {Path(path).name}")
                    clip = VideoFileClip(path)
                    if mute_original:
                        clip = clip.without_audio()

                    # Random transition
                    transition = self._get_random_transition()
                    is_first = (i == 0) and not sora_clips
                    is_last = (i == len(grok_videos) - 1) and not flow_images
                    clip = self._apply_transition_to_clip(clip, transition, is_first, is_last)

                    grok_clips.append(clip)

            # ===== 3. Tạo image clips từ Flow images =====
            if flow_images:
                self.log(f"Tạo {len(flow_images)} ảnh Flow (mỗi ảnh {image_duration}s)...")
                for i, img_path in enumerate(flow_images):
                    if not os.path.exists(img_path):
                        continue
                    try:
                        clip = ImageClip(img_path, duration=image_duration)

                        # Random transition cho ảnh
                        transition = self._get_random_transition()
                        is_first = (i == 0) and not sora_clips and not grok_clips
                        is_last = (i == len(flow_images) - 1)
                        # Transition ngắn hơn cho ảnh (0.2s)
                        orig_duration = self.transition_duration
                        self.transition_duration = min(0.2, image_duration / 2)
                        clip = self._apply_transition_to_clip(clip, transition, is_first, is_last)
                        self.transition_duration = orig_duration

                        image_clips.append(clip)
                    except Exception as e:
                        self.log(f"  Lỗi load ảnh {img_path}: {e}")

                if image_clips:
                    self.log(f"  Tổng ảnh: {len(image_clips)} x {image_duration}s = {len(image_clips) * image_duration:.1f}s")

            # ===== Ghép tất cả clips =====
            all_clips = sora_clips + grok_clips + image_clips

            if not all_clips:
                self.log("Không có video/ảnh hợp lệ để ghép")
                return False

            self.log("Ghép video...")
            final_clip = concatenate_videoclips(all_clips, method="compose")
            total_duration = final_clip.duration

            # Tính thời lượng các phần
            grok_start = sora_total_duration  # Voice bắt đầu từ đây
            grok_duration = sum(c.duration for c in grok_clips)
            image_total = sum(c.duration for c in image_clips)

            self.log(f"  Tổng: {total_duration:.1f}s")
            self.log(f"    SORA: {sora_total_duration:.1f}s")
            self.log(f"    Grok: {grok_duration:.1f}s (voice bắt đầu từ đây)")
            self.log(f"    Flow images: {image_total:.1f}s")

            # ===== 4. Xử lý audio =====
            # Music: bắt đầu từ ĐẦU video
            # Voice: bắt đầu từ Grok (sau SORA)
            audio_clips = []
            voice_offset = grok_start  # Voice bắt đầu sau SORA

            # Nhạc nền (từ đầu video, 60% volume)
            if music_path and os.path.exists(music_path):
                self.log(f"Thêm nhạc (từ đầu, volume {int(music_volume*100)}%): {Path(music_path).name}")
                music_audio = AudioFileClip(music_path)

                # Loop nhạc nếu cần (cho toàn bộ video)
                if music_audio.duration < total_duration:
                    loops_needed = int(total_duration / music_audio.duration) + 1
                    self.log(f"  Loop nhạc {loops_needed} lần")
                    from moviepy.editor import concatenate_audioclips
                    music_clips_list = [music_audio] * loops_needed
                    music_audio = concatenate_audioclips(music_clips_list)

                # Cắt nhạc = tổng thời lượng video
                music_audio = music_audio.subclip(0, total_duration)
                music_audio = music_audio.volumex(music_volume)
                # Fade out nhạc ở cuối (2s)
                music_audio = music_audio.fx(vfx.audio_fadeout, 2)
                # Music bắt đầu từ đầu (offset = 0)
                audio_clips.append(music_audio)

            # Voice (bắt đầu từ Grok, sau SORA)
            if voice_path and os.path.exists(voice_path):
                self.log(f"Thêm voice (offset {voice_offset:.1f}s): {Path(voice_path).name}")
                voice_audio = AudioFileClip(voice_path)
                voice_audio = voice_audio.volumex(voice_volume)
                # Offset voice để bắt đầu sau SORA
                voice_audio = voice_audio.set_start(voice_offset)
                audio_clips.append(voice_audio)

            # ===== 5. Ghép audio =====
            if audio_clips:
                self.log("Ghép audio...")
                final_audio = CompositeAudioClip(audio_clips)
                final_clip = final_clip.set_audio(final_audio)

            # ===== 6. Export =====
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
            self.log(f"Lỗi merge_full: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            for clip in all_clips:
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


def get_random_music(music_folder: str) -> Optional[str]:
    """Lấy file nhạc ngẫu nhiên từ thư mục music"""
    import random

    if not music_folder or not os.path.exists(music_folder):
        return None

    music_files = [
        f for f in os.listdir(music_folder)
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.aac'))
    ]

    if not music_files:
        return None

    # Random chọn 1 file
    music_file = random.choice(music_files)
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
