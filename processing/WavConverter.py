from pydub import AudioSegment


def convert_to_wav(input_path, client_ip):
    """
    Converts raw browser audio to a standard 16kHz Mono WAV.
    Deletes the input_path file immediately after successful conversion.
    """
    output_path = input_path.parent / f"{client_ip}.wav"

    # 1. Perform conversion
    audio = AudioSegment.from_file(str(input_path))
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(str(output_path), format="wav")

    # 2. DELETE ORIGINAL IMMEDIATELY
    if input_path.exists():
        input_path.unlink()
        print(f"Temporary upload {input_path.name} deleted.")

    return output_path

