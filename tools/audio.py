import io, os
import math
import logging
import tempfile
import wave
from mutagen import File as MutagenFile
from mutagen.wave import WAVE
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.aac import AAC
from pydub import AudioSegment
import base64  # 新增导入
import soundfile as sf
import librosa

# 设置 ffmpeg 路径（如果 ffmpeg 在项目目录中）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ffmpeg_path = os.path.join(project_root, 'ffmpeg', 'bin')
if os.path.exists(ffmpeg_path):
    os.environ["PATH"] += os.pathsep + ffmpeg_path

logger = logging.getLogger(__name__)

class AudioUtils:
    @staticmethod
    def get_duration(audio_data: bytes) -> float:
        """计算音频时长(秒)"""
        try:
            # 记录文件头信息用于调试
            logger.debug(f"Audio data first 16 bytes: {audio_data[:16].hex()}")
            
            # 1. 首先尝试使用 wave 模块直接读取 WAV 文件
            audio_file = io.BytesIO(audio_data)
            try:
                with wave.open(audio_file, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    duration = math.ceil(frames / float(rate))
                    logger.info(f"Successfully calculated duration using wave module: {duration} seconds")
                    return duration
            except Exception as e:
                logger.debug(f"Failed to read as WAV using wave module: {str(e)}")
                audio_file.seek(0)
            
            # 2. 如果不是标准 WAV，尝试使用 mutagen
            try:
                # 创建临时文件
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_path = temp_file.name

                try:
                    # 尝试作为 WAV 文件读取
                    audio = WAVE(temp_path)
                    if hasattr(audio.info, 'length'):
                        duration = math.ceil(audio.info.length)
                        logger.info(f"Successfully calculated duration using WAVE: {duration} seconds")
                        return duration
                except Exception as e:
                    logger.debug(f"Failed to read as WAVE: {str(e)}")
                    
                    # 尝试其他格式
                    try:
                        audio = MutagenFile(temp_path)
                        if audio is not None and hasattr(audio.info, 'length'):
                            duration = math.ceil(audio.info.length)
                            logger.info(f"Successfully calculated duration using MutagenFile: {duration} seconds")
                            return duration
                    except Exception as e:
                        logger.debug(f"MutagenFile failed: {str(e)}")

            except Exception as e:
                logger.debug(f"Failed to process with mutagen: {str(e)}")
            finally:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

            # 3. 如果前面的方法都失败了，检查是否为原始 PCM 数据
            try:
                # 假设是 16 位单声道 PCM，采样率 48000
                sample_width = 2  # 16 位 = 2 字节
                channels = 1      # 单声道
                frame_rate = 48000
                
                # 计算帧数和时长
                frames = len(audio_data) // (sample_width * channels)
                duration = math.ceil(frames / float(frame_rate))
                
                logger.info(f"Calculated duration as PCM data: {duration} seconds")
                return duration
                
            except Exception as e:
                logger.debug(f"Failed to process as PCM: {str(e)}")
                
            logger.warning("All duration calculation methods failed")
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get audio duration: {str(e)}")
            return 0

    @staticmethod
    def is_audio_file(filename: str) -> bool:
        """判断是否为音频文件"""
        audio_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.aac'}
        ext = os.path.splitext(filename)[1].lower()
        return ext in audio_extensions

    @staticmethod
    def change_sample_rate(base64_audio: str, target_sample_rate: int = 48000) -> str:
        """将 Base64 编码的音频数据的采样率提高到指定值（默认 48000 赫兹）"""
        try:
            # 解码 Base64 数据
            audio_data = base64.b64decode(base64_audio)
            
            # 使用 pydub 处理音频数据
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # 改变采样率
            audio_segment = audio_segment.set_frame_rate(target_sample_rate)
            
            # 将处理后的音频数据转换回 Base64
            buffer = io.BytesIO()
            audio_segment.export(buffer, format="wav")  # 可以根据需要更改格式
            buffer.seek(0)
            new_base64_audio = base64.b64encode(buffer.read()).decode('utf-8')
            
            return new_base64_audio
            
        except Exception as e:
            logger.error(f"Failed to change sample rate: {str(e)}")
            return ""

    @staticmethod
    def change_sample_rate_from_base64(base64_audio: str, target_sample_rate: int = 48000) -> str:
        """将 Base64 编码的音频数据的采样率提高到指定值（默认 48000 赫兹）"""
        try:
            # 1. 解码 Base64 数据
            audio_bytes = base64.b64decode(base64_audio)
            print(f"Decoded audio bytes length: {len(audio_bytes)}")  # 调试信息
            logger.info(f"Decoded audio bytes length: {len(audio_bytes)}")  # 调试信息

            # 保存解码后的音频数据以供检查
            with open("decoded_audio.wav", "wb") as f:
                f.write(audio_bytes)

            # 2. 使用 pydub 读取音频数据
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
            original_sample_rate = audio_segment.frame_rate

            print(f"Original sample rate: {original_sample_rate}")  # 调试信息
            logger.info(f"Original sample rate: {original_sample_rate}")  # 调试信息

            # 3. 使用 pydub 进行采样率转换
            new_audio_segment = audio_segment.set_frame_rate(target_sample_rate)

            print(f"New audio segment: {new_audio_segment}")  # 调试信息
            logger.info(f"New audio segment: {new_audio_segment}")  # 调试信息

            # 4. 将处理后的音频数据写入内存缓冲区
            output_buffer = io.BytesIO()
            new_audio_segment.export(output_buffer, format='wav')

            # 5. 从内存缓冲区获取二进制数据并编码为 Base64
            new_audio_bytes = output_buffer.getvalue()
            new_base64_audio = base64.b64encode(new_audio_bytes).decode('utf-8')

            return new_base64_audio

        except Exception as e:
            logger.error(f"Failed to change sample rate from Base64: {str(e)}")
            logger.error(f"Audio bytes length: {len(audio_bytes)}")  # 调试信息
            return ""
