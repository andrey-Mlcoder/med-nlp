import re
import os
import yaml
from pathlib import Path


PROJECT_ROOT = Path(os.getenv('PROJECT_ROOT',
                              Path(__file__).resolve().parent.parent.parent))
with open( PROJECT_ROOT/ 'data' / 'abbr2term.yaml', 'r', encoding='utf-8') as f:
    abbr2term = yaml.safe_load(f)

def ABBREV_to_term(text: str, abbr2term: dict) -> str:
    """ Метод осуществляющий поиск и замену аббревиатур в строке на их расшифровки.
    На вход получает текст, возвращает текст с расшифрованными аббревиатурами
    """
    abbr_pattern = r'\b[А-Я]{2,8}\b'
    abbrs = re.findall(abbr_pattern, text)
    for abbr in abbrs:
        if abbr in abbr2term:
            text = re.sub(abbr, abbr2term[abbr], text)
    return text