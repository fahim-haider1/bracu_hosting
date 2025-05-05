import json

def clean_json(filename):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)

        # Remove invalid entries (missing file_id or file_type)
        cleaned_data = {
            k: v for k, v in data.items()
            if 'file_id' in v and 'file_type' in v
        }

        with open(filename, 'w') as f:
            json.dump(cleaned_data, f, indent=2)

        print(f"[Cleaner] Cleaned {filename}. Removed bad entries.")

    except Exception as e:
        print(f"[Cleaner] Error cleaning {filename}: {e}")
