import glob
import html
import json
import os
import re
from html.parser import HTMLParser

# INPUT_DIR = r"F:\dictionary_parsing\data\samples_html\Output_1-23_html"
INPUT_DIR = r"C:\Users\vovas\OneDrive\Документы\Coding\Datasets\Output_1-23_html\Выпуск_1_А_Безпристрастие_Отправка"

PARA_BREAK = "\uE000"
SPACE_RE = re.compile(r"\s+")
ITALIC_OPEN = "[_I_]"
ITALIC_CLOSE = "[/_I_]"
BOLD_OPEN = "[_B_]"
BOLD_CLOSE = "[/_B_]"

LANGUAGE_MARKER_RE = re.compile(
    r"\b(?:"
    r"Фр|фр|Лат|лат|Нем|нем|Голл|голл|Итал|итал|Ит|ит|"
    r"Англ|англ|Исп|исп|Пол|пол|Польск|польск|Греч|греч|Гр|гр|"
    r"Тур|тур|Араб|араб|Перс|перс|Малаб|малаб"
    r")\."
)
BRACKETED_ETYM_RE = re.compile(r"\[[^\[\]]*?(?:через|непоср\.|<|[A-Za-zА-Яа-яЁё]).*?\]")
TAG_RE = re.compile(r"⸢SYM_[A-Z0-9_]+⸣|Ã¢Â¸Â¢SYM_[A-Z0-9_]+Ã¢Â¸Â£")
SENSE_START_RE = re.compile(r"^\d+\.$")


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
            self.parts.append(ITALIC_OPEN)
        elif tag == "b":
            self.parts.append(BOLD_OPEN)
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "p":
            self.parts.append(PARA_BREAK)
        elif tag == "i":
            self.parts.append(ITALIC_CLOSE)
        elif tag == "b":
            self.parts.append(BOLD_CLOSE)

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        self.parts.append(data)


def normalize_text(text):
    text = html.unescape(text.replace("\xa0", " "))
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def strip_style_markers(text):
    text = text.replace(ITALIC_OPEN, "").replace(ITALIC_CLOSE, "")
    text = text.replace(BOLD_OPEN, "").replace(BOLD_CLOSE, "")
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


def clean_etymology(text):
    text = TAG_RE.sub("", text)
    text = strip_style_markers(text)
    text = re.sub(r"\s+([,.;:)\]])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return normalize_text(text)


def find_bracketed_etymology(paragraph):
    for match in BRACKETED_ETYM_RE.finditer(paragraph):
        candidate = match.group(0)
        if LANGUAGE_MARKER_RE.search(candidate):
            return clean_etymology(candidate)
    return ""


def looks_like_etymology_start(paragraph, pos):
    left = paragraph[max(0, pos - 40):pos]
    left_plain = strip_style_markers(TAG_RE.sub("", left))
    return bool(
        not left_plain
        or left_plain.endswith(("м.", "ж.", "ср.", "мн.", "ед.", ")"))
        or SENSE_START_RE.search(left_plain.split()[-1]) is None
    )


def find_inline_etymology(paragraph):
    match = LANGUAGE_MARKER_RE.search(paragraph)
    if not match:
        return ""

    start = match.start()
    if not looks_like_etymology_start(paragraph, start):
        return ""

    tail = paragraph[start:]
    boundaries = []
    for token in [ITALIC_OPEN, BOLD_OPEN, " || ", "| ", " — ", " – "]:
        idx = tail.find(token)
        if idx > 0:
            boundaries.append(idx)

    end = min(boundaries) if boundaries else len(tail)
    candidate = tail[:end]
    candidate = clean_etymology(candidate)

    if not LANGUAGE_MARKER_RE.search(candidate):
        return ""

    return candidate


def find_etymology(paragraphs):
    for paragraph_index, paragraph in enumerate(paragraphs, start=1):
        bracketed = find_bracketed_etymology(paragraph)
        if bracketed:
            return paragraph_index, bracketed, strip_style_markers(paragraph)

        inline = find_inline_etymology(paragraph)
        if inline:
            return paragraph_index, inline, strip_style_markers(paragraph)

    return None, "", ""


def parse_etymology(html_content, filename):
    title, paragraphs = parse_html(html_content)
    paragraph_index, etymology, paragraph_text = find_etymology(paragraphs)
    return {
        "file": filename,
        "title": title,
        "superscript_index": "",
        "paragraph_index": paragraph_index,
        "etymology": etymology,
        "paragraph_text": paragraph_text,
    }


def process_files(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    html_files = glob.glob(os.path.join(input_dir, "**", "*.html"), recursive=True)
    print(f"Найдено {len(html_files)} HTML файлов для обработки.")

    processed_count = 0
    etymology_count = 0

    for filepath in html_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                html_content = f.read()

            result = parse_etymology(html_content, os.path.basename(filepath))
            json_filename = os.path.splitext(os.path.basename(filepath))[0] + ".json"
            output_filepath = os.path.join(output_dir, json_filename)

            with open(output_filepath, "w", encoding="utf-8-sig") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)

            processed_count += 1
            if result["etymology"]:
                etymology_count += 1
        except Exception as exc:
            print(f"Ошибка при обработке {filepath}: {exc}")

    print(f"Успешно обработано {processed_count} файлов.")
    print(f"Файлов с этимологией: {etymology_count}.")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")

    print(f"Входная папка: {INPUT_DIR}")
    print(f"Выходная папка: {output_dir}")

    process_files(INPUT_DIR, output_dir)
