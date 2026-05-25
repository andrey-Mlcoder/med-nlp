import re
import os
import yaml
from pathlib import Path
from abbr_converter import ABBREV_to_term


PROJECT_ROOT = Path(os.getenv('PROJECT_ROOT',
                              Path(__file__).resolve().parent.parent.parent))
with open( PROJECT_ROOT/ 'data' / 'abbr2term.yaml', 'r', encoding='utf-8') as f:
    abbr2term = yaml.safe_load(f)


# --- ПАРСИНГ BRAT-ФАЙЛОВ ---
def parse_ann_file(ann_path):
    """Извлекает коды МКБ-10 из одного .ann файла"""
    codes = set()
    with open(ann_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) >= 3 and parts[1].startswith('Reference'):
                code = parts[2].strip()
                # Дополнительная проверка формата кода (буква + цифры + опционально точка с цифрами)
                if re.match(r'^[A-Z][0-9]+(?:\.[0-9]+)?$', code):
                    codes.add(code)
    return list(codes)

def parse_dataset(data_dir):
    """Проходит по всем парам .txt/.ann в указанной папке."""
    data = []
    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith('.txt'):
            base = fname[:-4]
            ann_file = base + '.ann'
            ann_path = os.path.join(data_dir, ann_file)
            if not os.path.exists(ann_path):
                continue
            txt_path = os.path.join(data_dir, fname)
            with open(txt_path, 'r', encoding='utf-8') as f:
                text = f.read()
            clean_text = ABBREV_to_term(text, abbr2term)
            codes = parse_ann_file(ann_path)
            data.append({'text': clean_text, 'codes': codes})
    return data