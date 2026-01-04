import os
import sys
import subprocess
import requests
import shutil
import logging
import time
import numpy as np
from pydub import AudioSegment
from scipy.io import wavfile

# PyTorch 2.6+ のセーフガード（weights_only=True）による互換性問題を解決
import torch
try:
    from fairseq.data.dictionary import Dictionary
    if hasattr(torch.serialization, 'add_safe_globals'):
        torch.serialization.add_safe_globals([Dictionary])
except ImportError:
    pass

# audio-separator と rvc-python は実行時に動的にチェック
try:
    from audio_separator.separator import Separator
except ImportError:
    Separator = None

try:
    from rvc_python.infer import RVCInference
except ImportError:
    RVCInference = None

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        self.input_dir = os.path.join(self.base_dir, "input")
        self.output_dir = os.path.join(self.base_dir, "output")
        self.models_dir = os.path.join(self.base_dir, "models")

        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)

    def download_file(self, url, dest_path):
        if os.path.exists(dest_path):
            logger.info(f"File already exists: {dest_path}")
            return
        logger.info(f"Downloading {url} to {dest_path}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def phase1_normalize(self, input_wav):
        logger.info("--- Phase 1: Normalization ---")
        output_wav = os.path.join(self.output_dir, "radio-calisthenics_norm.wav")
        audio = AudioSegment.from_wav(input_wav)
        # 44.1kHz / 16bit / ステレオ維持
        audio = audio.set_frame_rate(44100).set_sample_width(2)
        audio.export(output_wav, format="wav")
        logger.info(f"Normalized audio saved to {output_wav}")
        return output_wav

    def phase2_separate(self, input_wav):
        logger.info("--- Phase 2: Vocal Separation ---")
        if not Separator:
            raise ImportError("audio-separator is not installed.")

        separator = Separator(model_file_dir=self.models_dir, output_dir=self.output_dir)
        separator.load_model('UVR-MDX-NET-Voc_FT.onnx')

        output_files = separator.separate(input_wav)

        vocals_path = os.path.join(self.output_dir, "vocals.wav")
        inst_path = os.path.join(self.output_dir, "instrumental.wav")

        for f in output_files:
            full_f = os.path.join(self.output_dir, f)
            if "Vocals" in f:
                shutil.move(full_f, vocals_path)
            elif "Instrumental" in f:
                shutil.move(full_f, inst_path)

        logger.info(f"Vocals saved to {vocals_path}")
        logger.info(f"Instrumental saved to {inst_path}")
        return vocals_path, inst_path

    def phase3_rvc_inference(self, vocals_wav, model_pth, index_file=None, f0_method="crepe", protect=0.33, pitch_shift=0):
        logger.info(f"--- Phase 3: RVC Inference (Method: {f0_method}, Protect: {protect}, Shift: {pitch_shift}) ---")
        if not RVCInference:
            raise ImportError("rvc-python is not installed.")

        output_wav = os.path.join(self.output_dir, "converted_vocals.wav")

        # モデル読み込み時の weights_only 問題を解決するための環境変数設定 (念のため)
        os.environ["TORCH_LOAD_WEIGHTS_ONLY"] = "0"

        rvc = RVCInference(device="cpu")
        rvc.load_model(model_pth, version="v2", index_path=index_file or "")

        rvc.set_params(
            f0method=f0_method,
            f0up_key=pitch_shift,
            index_rate=0.6,
            protect=protect
        )

        logger.info("Starting inference via direct vc_single call...")
        file_index = rvc.models[rvc.current_model].get("index", "")

        result = rvc.vc.vc_single(
            sid=0,
            input_audio_path=vocals_wav,
            f0_up_key=rvc.f0up_key,
            f0_file="",
            f0_method=rvc.f0method,
            file_index=file_index,
            file_index2="",
            index_rate=rvc.index_rate,
            filter_radius=rvc.filter_radius,
            resample_sr=rvc.resample_sr,
            rms_mix_rate=rvc.rms_mix_rate,
            protect=rvc.protect
        )

        if isinstance(result, tuple):
            error_info = result[0]
            raise RuntimeError(f"RVC Inference failed internally: {error_info}")

        wavfile.write(output_wav, rvc.vc.tgt_sr, result)

        logger.info(f"Converted vocals saved to {output_wav}")
        return output_wav

    def phase4_mix(self, vocals_wav, inst_wav):
        logger.info("--- Phase 4: Remixing ---")
        output_wav = os.path.join(self.output_dir, "radio-calisthenics_converted.wav")

        vocal = AudioSegment.from_wav(vocals_wav)
        inst = AudioSegment.from_wav(inst_wav)

        # ボーカル音量を instrumental に対し -6dB 目安
        vocal = vocal - 6

        combined = inst.overlay(vocal)
        combined.export(output_wav, format="wav")

        logger.info(f"Final mixed audio saved to {output_wav}")
        return output_wav

    def run_full_process(self, input_file, rvc_model_info):
        # Phase 1
        norm_wav = self.phase1_normalize(input_file)

        # Phase 2
        vocals_wav, inst_wav = self.phase2_separate(norm_wav)

        # Phase 3 Prepare Models
        model_pth = os.path.join(self.models_dir, f"{rvc_model_info['name']}.pth")
        model_index = os.path.join(self.models_dir, f"{rvc_model_info['name']}.index")

        self.download_file(rvc_model_info['pth_url'], model_pth)
        self.download_file(rvc_model_info['index_url'], model_index)

        # Phase 3 Inference
        try:
            converted_vocals = self.phase3_rvc_inference(vocals_wav, model_pth, model_index)
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            logger.info("Retrying with f0_method='harvest' and protect=0.4...")
            converted_vocals = self.phase3_rvc_inference(vocals_wav, model_pth, model_index, f0_method="harvest", protect=0.4)

        # Phase 4
        final_output = self.phase4_mix(converted_vocals, inst_wav)

        # Move to root_out (Docker map)
        final_dest = "/app/root_out/radio-calisthenics_converted.wav"
        shutil.copy(final_output, final_dest)
        logger.info(f"Success! Process completed. File: {final_dest}")

def main():
    processor = AudioProcessor(os.path.dirname(__file__))

    input_file = os.path.join(processor.input_dir, "radio-calisthenics.wav")
    if not os.path.exists(input_file):
        root_input = "/app/input/radio-calisthenics.wav"
        if os.path.exists(root_input):
            shutil.copy(root_input, input_file)
        else:
            logger.error(f"Input file not found: {root_input}")
            return

    # デフォルトのRVCモデル
    rvc_model_info = {
        "name": "zundamon",
        "pth_url": "https://huggingface.co/kuwacom/RVC-Models/resolve/main/zundamon-1/zundamon-1.pth",
        "index_url": "https://huggingface.co/kuwacom/RVC-Models/resolve/main/zundamon-1/zundamon-1.index"
    }

    processor.run_full_process(input_file, rvc_model_info)

if __name__ == "__main__":
    main()
