import os
import subprocess

user = 'dennisporter'

def is_icloud_file_evicted(filepath):
    if not os.path.exists(filepath):
        base_name = os.path.basename(filepath)
        dir_name = os.path.dirname(filepath)
        icloud_name = f".{base_name}.icloud"
        return os.path.exists(os.path.join(dir_name, icloud_name))
    else:
        stat_info = os.stat(filepath)
        return stat_info.st_size == 0

def evict_icloud_file(filepath):
    subprocess.run(["brctl", "evict", filepath], check=False)

def find_and_evict_music_files(root_path):
    music_extensions = ['.mp3', '.m4a', '.flac', '.wav', '.aac', '.ogg', '.wma']
    
    for root, dirs, files in os.walk(root_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in music_extensions):
                filepath = os.path.join(root, file)
                if not is_icloud_file_evicted(filepath):
                    print(f"Evicting: {filepath}")
                    evict_icloud_file(filepath)
                else:
                    print(f"Already evicted: {filepath}")

icloud_path = f"/Users/{user}/Library/Mobile Documents/com~apple~CloudDocs"
find_and_evict_music_files(icloud_path)

