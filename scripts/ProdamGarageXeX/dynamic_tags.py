import glob
import html
import json
import os
import re
from html.parser import HTMLParser

INPUT_DIR = r"F:\dictionary_parsing\data\samples_html\Output_1-23_html"

DYNAMIC_TAGS = {
    "SYM_NEW_WORD": "новое слово, вариант или форма",
    "SYM_OBSOLETE": "выпавшее из употребления слово, вариант или форма",
    "SYM_EXPANDED": "слово, расширившее употребление",
    "SYM_OBSOLESCENT": "слово, выходящее из употребления",
    "SYM_OBS_18C": "новое слово, уже вышедшее из употребления в XVIII веке",
    "SYM_STYLE_DIR": "направление изменения стилистической характеристики",
}

PARA_BREAK = "\uE000"
TAG_RE = re.compile(r"⸢(SYM_[A-Z0-9_]+)⸣|Ã¢Â¸Â¢(SYM_[A-Z0-9_]+)Ã¢Â¸Â£")
ITALIC_CHUNK_RE = re.compile(r"\[_I_\](.*?)\[/_I_\]", re.DOTALL)
BOLD_CHUNK_RE = re.compile(r"\[_B_\](.*?)\[/_B_\]", re.DOTALL)
LEADING_JUNK_RE = re.compile(r"^[\s,;:()]+")
TRAILING_JUNK_RE = re.compile(r"[\s,;:()]+$")
SPACE_RE = re.compile(r"\s+")
SENSE_NUMBER_RE = re.compile(r"^\d+\.$")


class ParagraphHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "title":
            self.in_title = True
        elif tag == "p":
            self.parts.append(PARA_BREAK)
        elif tag == "i":
            self.parts.append("[_I_]")
        elif tag == "b":
            self.parts.append("[_B_]")
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "p":
            self.parts.append(PARA_BREAK)
        elif tag == "i":
            self.parts.append("[/_I_]")
        elif tag == "b":
            self.parts.append("[/_B_]")

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        self.parts.append(data)


def normalize_text(text):
    text = html.unescape(text.replace("\xa0", " "))
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def strip_style_markers(text):
    text = text.replace("[_I_]", "").replace("[/_I_]", "")
    text = text.replace("[_B_]", "").replace("[/_B_]", "")
    return normalize_text(text)


def cleanup_fragment(text):
    text = strip_style_markers(text)
    text = LEADING_JUNK_RE.sub("", text)
    text = TRAILING_JUNK_RE.sub("", text)
    text = re.sub(r"\s+(и|или|а)$", "", text)
    text = re.sub(r"[,(]\s*$", "", text)
    return normalize_text(text)


def parse_html(html_content):
    parser = ParagraphHTMLParser()
    parser.feed(html_content)
    full_text = "".join(parser.parts)
    title = normalize_text("".join(parser.title))

    paragraphs = []
    for raw in full_text.split(PARA_BREAK):
        line = normalize_text(raw.replace("\r", " ").replace("\n", " "))
        if line:
            paragraphs.append(line)

    return title, paragraphs


def find_prev_italic(paragraph, pos):
    chunk = ""
    for match in ITALIC_CHUNK_RE.finditer(paragraph[:pos]):
        chunk = cleanup_fragment(match.group(1))
    return chunk


def find_next_italic(paragraph, pos):
    match = ITALIC_CHUNK_RE.search(paragraph[pos:])
    if not match:
        return ""
    return cleanup_fragment(match.group(1))


def find_next_bold(paragraph, pos):
    match = BOLD_CHUNK_RE.search(paragraph[pos:])
    if not match:
        return ""
    return cleanup_fragment(match.group(1))


def extract_bold_fragment(text):
    if not text.startswith("[_B_]"):
        return ""
    end = text.find("[/_B_]")
    if end == -1:
        return ""
    return cleanup_fragment(text[len("[_B_]"):end])


def extract_plain_fragment(text):
    boundaries = []
    for token in [
        "[_B_]",
        "[_I_]",
        "⸢SYM_",
        "Ã¢Â¸Â¢SYM_",
        "||",
        ";",
        ". ",
        ".)",
    ]:
        idx = text.find(token)
        if idx > 0:
            boundaries.append(idx)

    end = min(boundaries) if boundaries else len(text)
    fragment = text[:end]
    return cleanup_fragment(fragment)


def build_sense_fragment(paragraph, match_end):
    bold_fragment = find_next_bold(paragraph, match_end)
    next_italic = find_next_italic(paragraph, match_end)
    if bold_fragment and next_italic:
        return f"{bold_fragment} {next_italic}"
    return bold_fragment or next_italic


def extract_marked_fragment(tag_name, paragraph, match_end):
    tail = paragraph[match_end:].lstrip()

    if tag_name == "SYM_STYLE_DIR":
        source_style = find_prev_italic(paragraph, match_end)
        target_style = find_next_italic(paragraph, match_end)
        marked_fragment = " -> ".join(part for part in [source_style, target_style] if part)
        return {
            "marked_fragment": marked_fragment,
            "source_style": source_style,
            "target_style": target_style,
        }

    bold_fragment = extract_bold_fragment(tail)
    if bold_fragment:
        if SENSE_NUMBER_RE.fullmatch(bold_fragment):
            sense_fragment = build_sense_fragment(paragraph, match_end)
            if sense_fragment:
                bold_fragment = sense_fragment
        return {"marked_fragment": bold_fragment}

    plain_fragment = extract_plain_fragment(tail)
    if SENSE_NUMBER_RE.fullmatch(plain_fragment):
        sense_fragment = build_sense_fragment(paragraph, match_end)
        if sense_fragment:
            plain_fragment = sense_fragment

    return {"marked_fragment": plain_fragment}


def extract_context(paragraph, start, end, window=100):
    left = cleanup_fragment(paragraph[max(0, start - window):start])
    right = cleanup_fragment(paragraph[end:end + window])
    return left, right


def parse_dynamic_tags(html_content, filename):
    title, paragraphs = parse_html(html_content)
    records = []

    for paragraph_index, paragraph in enumerate(paragraphs, start=1):
        for match in TAG_RE.finditer(paragraph):
            tag_name = match.group(1) or match.group(2)
            if tag_name not in DYNAMIC_TAGS:
                continue

            payload = extract_marked_fragment(tag_name, paragraph, match.end())
            left_context, right_context = extract_context(paragraph, match.start(), match.end())

            record = {
                "file": filename,
                "title": title,
                "paragraph_index": paragraph_index,
                "tag": tag_name,
                "tag_description": DYNAMIC_TAGS[tag_name],
                "marked_fragment": payload.get("marked_fragment", ""),
                "left_context": left_context,
                "right_context": right_context,
                "paragraph_text": strip_style_markers(paragraph),
            }

            if "source_style" in payload:
                record["source_style"] = payload["source_style"]
            if "target_style" in payload:
                record["target_style"] = payload["target_style"]

            records.append(record)

    return records


def process_files(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    html_files = glob.glob(os.path.join(input_dir, "**", "*.html"), recursive=True)
    print(f"Найдено {len(html_files)} HTML файлов для обработки.")

    processed_count = 0
    nonempty_count = 0

    for filepath in html_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                html_content = f.read()

            result = parse_dynamic_tags(html_content, os.path.basename(filepath))
            filename = os.path.basename(filepath)
            json_filename = os.path.splitext(filename)[0] + ".json"
            output_filepath = os.path.join(output_dir, json_filename)

            with open(output_filepath, "w", encoding="utf-8-sig") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)

            processed_count += 1
            if result:
                nonempty_count += 1
        except Exception as exc:
            print(f"Ошибка при обработке {filepath}: {exc}")

    print(f"Успешно обработано {processed_count} файлов.")
    print(f"Файлов с динамическими пометами: {nonempty_count}.")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")

    print(f"Входная папка: {INPUT_DIR}")
    print(f"Выходная папка: {output_dir}")

    process_files(INPUT_DIR, output_dir)
