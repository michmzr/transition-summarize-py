def string_to_filename(string: str) -> str:
    return string[:20].replace(" ", "_").replace("/", "_")
