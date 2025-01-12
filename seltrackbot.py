import asyncio
from telethon.sync import TelegramClient, events
import subprocess
import re
from telethon.sessions import StringSession
import logging
import os
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)
import time

# Telegram API credentials
print('Loading env variables.')
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
botsession = os.getenv('BOTSESSION')
print('Env vars loaded correctly.')


# Initialize Telegram client
thebot = TelegramClient(StringSession(botsession), api_id, api_hash)


def get_audio_tracks(video_file):
    ffprobe_cmd = [
        "ffprobe",
        "-show_entries", "stream=index,codec_type:stream_tags=language",
        "-of", "compact",
        video_file,
        "-v", "0"
    ]

    try:
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
        audio_tracks_info = re.findall(r"stream\|index=(\d+)\|codec_type=audio\|tag:language=(\w+)", result.stdout)
        audio_tracks = [(int(index), language) for index, language in audio_tracks_info]
        return audio_tracks
    except subprocess.CalledProcessError as e:
        print("Error occurred:", e)
        return []


def keep_selected_audio_tracks(input_file, output_file, selected_indexes):
    audio_tracks = get_audio_tracks(input_file)
    if not audio_tracks:
        print("No audio tracks found.")
        return
    if any(index < 0 or index >= len(audio_tracks) for index in selected_indexes):
        print("Invalid track selection.")
        return

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", input_file,
        "-map", "0:v",
    ]

    for selected_index in selected_indexes:
        selected_track_index, _ = audio_tracks[selected_index]
        corrected_track_index = selected_track_index - 1  # Corrected index for FFMPEG
        ffmpeg_cmd.extend(["-map", f"0:a:{corrected_track_index}"])

    ffmpeg_cmd.extend([
        "-map", "0:s",  # Include all subtitle tracks
        "-c:v", "copy",
        "-c:a", "copy",
        "-c:s", "copy",  # Copy subtitle tracks without re-encoding
        output_file
    ])

    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print("Selected audio tracks and all subtitle tracks kept successfully.")
    except subprocess.CalledProcessError as e:
        print("Error occurred:", e)

def upload_progress(current, total):
  # This function is called periodically during upload
  # You can use this to display upload progress to the user (optional)
  print(f"Uploading... {current * 100 / total:.1f}%")

#########################################################
@thebot.on(events.NewMessage(pattern='/process_file'))
async def process_file(event):
    global file
    global new_name
    if event.reply_to_msg_id is None:
        await event.respond("Please reply to a file with this command.")
        return

    message = await event.get_reply_message()
    if message.media is None:
        await event.respond("Please reply to a file with this command.")
        return

    file = await message.download_media()
    new_name = "Cleaned " + str(file)
    print(new_name)
    audio_tracks = get_audio_tracks(file)
    if not audio_tracks:
        await event.respond("No audio tracks found in the file.")
        return

    audio_tracks_list = "\n".join([f"{idx}. {language}" for idx, (_, language) in enumerate(audio_tracks)])
    await event.respond(f"Audio tracks found in the file:\n{audio_tracks_list} \ntype /select followed by the numbers of"
                        f" the tracks you want to keep \nFor example /select 0, 3 [to select the tracks number 0 and 3]")

# @thebot.on(events.NewMessage(incoming=True))
# async def selector(event):
#     if '/select' in event.raw_text: #scrapped part of the bot
#         seleccion = event.raw_text #this one only selected 1 audio track instead of as many as the user wants
#         print(seleccion)
#         selected = seleccion.split(" ")[1]
#         print(selected)
@thebot.on(events.NewMessage(pattern='/select'))
async def handle_select(event):
    try:
        # Extract the numbers from the message
        numbers_str = event.raw_text.split(' ', 1)[1].strip()
        selected_indexes = [int(num.strip()) for num in numbers_str.split(',')]

        # Print the list of numbers
    except Exception as e:
        print("Error processing /select command:", e)
        # selected_index = int(input("Enter the index of the audio track to keep: "))
        # selected_index = int(selected)
    output_file = new_name  # Output file name
    keep_selected_audio_tracks(file, output_file, selected_indexes)

    await event.respond("Processing complete. Uploading the modified file...")
    upload_result = await thebot.send_file(event.chat_id, file=output_file, progress_callback=upload_progress)
    if os.path.isfile(file):
        os.remove(file)
        print("removed original file")
        await asyncio.sleep(2)
        if os.path.isfile(output_file):
            os.remove(output_file)
            print("removed modified file")

            await event.respond("Files deleted from storage")

    else:
        # If it fails, inform the user.
        print("Error: %s file not found" % file)

@thebot.on(events.NewMessage(pattern='/ping'))
async def ping_pong(event):
    start_time = time.time()
    message = await event.respond('Pong!')
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 2)  # Calculate ping time in milliseconds
    await message.edit(f'Pong! (Ping: {ping_time}ms)')


thebot.start()
thebot.run_until_disconnected()
