import os
import re
import sys
import unicodedata
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

# Полные теги-пометы в обработанных версиях статей
# Формат: ⸢SYM_NAME⸣ (U+2E22 ... U+2E23)
SYM_TAG_PATTERN = re.compile(r'^((?:⸢[^⸣]+⸣\s*)+)', re.UNICODE)

# Все допустимые имена SYM-тегов
ALLOWED_SYM_NAMES = {
    'SYM_COLLOCATION',
    'SYM_SYNTAX',
    'SYM_GRAM_ADD',
    'SYM_GRAM_CHANGE',
    'SYM_NEW_WORD',
    'SYM_OBSOLETE',
    'SYM_EXPANDED',
    'SYM_OBSOLESCENT',
    'SYM_OBS_18C',
    'SYM_STYLE_DIR',
}

def is_uppercase_heading(text):
    """Проверяет, является ли текст заголовком (все буквы — прописные)."""
    text_no_accents = text.replace('\u0301', '').replace('́', '')  # убираем знак ударения

    #Римские цифры не являются заголовком статьи
    roman_pattern = r'^[IVXLCDM]+[\.\,\s]*$'
    if re.match(roman_pattern, text_no_accents.strip()):
        return False

    letters = [c for c in text_no_accents if c.isalpha()]

    if not letters:
        return False

    if len(letters) == 1:
        #Одиночная буква допустимый заголовок раздела
        return True

    for letter in letters:
        if letter.islower():
            return False

    return True

def extract_headword(text):
    result = text.strip('., \n\r\t')
    return result if result else "UNKNOWN"

def sanitize_filename(filename):
    #Очищает строку для использования в имени файла
    # Убираем знаки ударения (комбинируемый и самостоятельный)
    filename = filename.replace('\u0301', '').replace('́', '')
    
    filename = unicodedata.normalize('NFC', filename)
    # Убираем управляющие символы (переносы строк, табуляции — артефакты Word HTML)
    filename = re.sub(r'[\r\n\t]', '', filename)
    # Убираем угловые скобки (артефакты типа <АВТОМЕДОН>)
    filename = filename.replace('<', '').replace('>', '')
    # Убираем SYM-теги на случай, если они попали в имя
    filename = re.sub(r'⸢[^⸣]*⸣', '', filename)
    unsafe_chars = ':\"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    # Убираем лишние пробелы и подчёркивания по краям
    filename = filename.strip('_ ')
    return filename[:200]

def extract_sym_prefix_from_paragraph(p_tag):
    """
    Извлекает теги, стоящие в начале параграфа перед заголовочным словом.
    В обработанных файлах они находятся в тексте <span> до <b>
    Возвращает строку вида '⸢SYM_NEW_WORD⸣ ' или '', если тегов нет.
    """
    full_text = p_tag.get_text()
    m = SYM_TAG_PATTERN.match(full_text.lstrip())
    if not m:
        return ''

    # Проверяем, что все найденные теги — допустимые SYM-имена
    raw_prefix = m.group(1)
    tag_names = re.findall(r'⸢([^⸣]+)⸣', raw_prefix)
    for name in tag_names:
        if name not in ALLOWED_SYM_NAMES:
            return ''

    return raw_prefix

def extract_headword_text(p_tag):
    """
    Собирает заголовочное слово по всем дочерним тегам, так как при конвертации Wordом в HTML
    часто разбивает текст внутри <b> на отдельные узлы, особенно для символов с ударениями
    или при смене шрифта
    """
    bold_text_parts = []
    pending_nonbold = ""
    pending_spaces = ""
    started_bold = False

    for element in p_tag.descendants:
        if type(element).__name__ not in ['NavigableString']:
            continue
            
        text = str(element)
        
        is_bold = False
        is_sup = False
        parent = element.parent
        while parent and parent.name != 'p':
            if parent.name in ['b', 'strong']:
                is_bold = True
            if parent.name == 'span' and parent.has_attr('style'):
                style = parent['style'].replace(' ', '').lower()
                if 'font-weight:bold' in style or 'font-weight:700' in style:
                    is_bold = True
            if parent.name in ['sup', 'sub']:
                is_sup = True
            parent = parent.parent
        
        if is_bold or is_sup:
            if started_bold:
                if pending_spaces:
                    bold_text_parts.append(pending_spaces)
                    pending_spaces = ""
                if pending_nonbold:
                    bold_text_parts.append(pending_nonbold)
                    pending_nonbold = ""
            bold_text_parts.append(text)
            started_bold = True
        else:
            if started_bold:
                clean_text = text.strip()
                if not clean_text:
                    if not pending_nonbold:
                        pending_spaces += text
                    else:
                        pending_nonbold += text
                else:
                    # Если встречаем нижний регистр или знаки препинания - конец заголовка
                    if re.search(r'[.,;a-zа-яё]', text): 
                        break
                    else:
                        pending_nonbold += text

    return "".join(bold_text_parts)

def is_article_heading(p_tag):
    """
    Определяет, является ли параграф заголовком словарной статьи.
    Возвращает (True, headword_for_filename) или (False, None).
    """
    bold_text = extract_headword_text(p_tag)
    if not bold_text:
        return False, None

    # Убираем переносы строк из Word HTML (длинные слова переносятся внутри тега)
    bold_text = re.sub(r'[\r\n\t]', '', bold_text)

    # Очищаем от SYM-тегов (на случай нестандартной разметки)
    bold_text_clean = re.sub(r'⸢[^⸣]*⸣', '', bold_text)

    # Убираем знаки препинания и пробелы для проверки
    clean_text = bold_text_clean.strip('., ')

    if is_uppercase_heading(clean_text):
        headword = extract_headword(clean_text)
        return True, headword

    return False, None

def create_html_page(headword, content_html):
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{headword}</title>
</head>
<body>
{content_html}
</body>
</html>"""

def process_html_file(html_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    print(f"Reading {html_path}...")
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    word_section = soup.find('div', class_='WordSection1')
    if not word_section:
        word_section = soup.find('body')

    if not word_section:
        print(f"Skipping {html_path} - no body or WordSection1 found")
        return 0

    paragraphs = word_section.find_all('p')

    entries = []
    current_headword = None        # имя для файла (без SYM-тегов)
    current_display_headword = None  # имя для <title> (тоже без тегов)
    current_entry_parts = []

    for p in paragraphs:
        # Пустые параграфы-разделители
        if not p.get_text(strip=True):
            if current_headword:
                current_entry_parts.append(str(p))
            continue

        is_heading, headword = is_article_heading(p)

        if is_heading:
            #Сохраняем предыдущую статью
            if current_headword and current_entry_parts:
                entries.append((current_headword, current_display_headword,
                                '\n'.join(current_entry_parts)))

            #Начинаем новую статью
            current_headword = headword
            current_display_headword = headword
            current_entry_parts = [str(p)]
        else:
            if current_headword:
                current_entry_parts.append(str(p))

    #Последняя статья
    if current_headword and current_entry_parts:
        entries.append((current_headword, current_display_headword,
                        '\n'.join(current_entry_parts)))

    #запись файлов
    processed = 0
    filename_counts = {}

    for idx, (headword, display_headword, content) in enumerate(entries, 1):
        safe_filename = sanitize_filename(headword)

        # Добавляем порядковый номер статьи
        safe_filename = f"{idx}_{safe_filename}"

        # Обработка дублей
        if safe_filename in filename_counts:
            filename_counts[safe_filename] += 1
            safe_filename = f"{safe_filename}_{filename_counts[safe_filename]}"
        else:
            filename_counts[safe_filename] = 1

        file_path = os.path.join(output_dir, f"{safe_filename}.html")

        html_content = create_html_page(display_headword, content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        processed += 1

    return processed

if __name__ == "__main__":
    input_dir  = r"F:\ILS\sources_html_tags"
    output_base_dir = r"F:\ILS\outputv2"

    if not os.path.exists(input_dir):
        print("Входная директория не найдена:", input_dir)
        sys.exit(1)

    htm_files = [fn for fn in os.listdir(input_dir)
                 if fn.lower().endswith(('.html', '.htm'))]

    if not htm_files:
        print("Файлы .html/.htm не найдены в директории:", input_dir)
    else:
        for filename in htm_files:
            file_path = os.path.join(input_dir, filename)

            # Имя подпапки: берём часть до первой точки после номера выпуска
            # Например: "Выпуск 1. А - ..." → "Выпуск_1"
            issue_name = filename.split('.')[0].replace(' ', '_')
            output_dir = os.path.join(output_base_dir, issue_name)

            print(f"\nОбработка: {filename}")
            print(f"→ Вывод в: {output_dir}")
            count = process_html_file(file_path, output_dir)
            print(f"→ Извлечено статей: {count}")
