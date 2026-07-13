import csv
import os


def load_processed_set(csv_path=""):
    if not csv_path or not os.path.exists(csv_path):
        return set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        return set(row["id"] for row in csv.DictReader(f))


def append_entry(artist, title, bpm, duration, filename, id, csv_path=""):
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Artist", "Title", "BPM", "Duration", "Filename", "id"])
        writer.writerow([artist, title, bpm, duration, filename, id])
