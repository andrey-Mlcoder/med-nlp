import os
from pathlib import Path
from collections import Counter
from parsing_data import parse_dataset


PROJECT_ROOT = Path(os.getenv('PROJECT_ROOT',
                              Path(__file__).resolve().parent.parent.parent))

# --- ВЫЧИСЛЕНИЕ RARITYWEIGHT ---
train_data = parse_dataset(PROJECT_ROOT / 'data' / 'ruccod_train')  # путь к обучающей выборке

code_counter = Counter()
for item in train_data:
    code_counter.update(item['codes'])

print(f'Всего документов: {len(train_data)}')
print(f'Уникальных кодов МКБ-10: {len(code_counter)}')
print('Топ-10 по частоте:')
for code, freq in code_counter.most_common(10):
    print(f'  {code}: {freq}')

# Преобразование частот в веса (логарифмическое)
epsilon = 1.0
freqs = np.array(list(code_counter.values()))
log_freq = np.log(freqs + epsilon)
rarity_raw = 1.0 / (log_freq + epsilon)
rarity_norm = (rarity_raw - rarity_raw.min()) / (rarity_raw.max() - rarity_raw.min())

rarity_weights = dict(zip(code_counter.keys(), rarity_norm))

# Для отсутствующих в обучающей выборке кодов — максимальная редкость (1.0)
def get_rarity_weight(code):
    return rarity_weights.get(code, 1.0)

# --- ИНТЕГРАЦИЯ С SEVERITYWEIGHT ---
with open('data/mkb2descr.yaml', 'r', encoding='utf-8') as f:
    mkb_tree = yaml.safe_load(f)

# Здесь severity_weights — ваш ранее созданный словарь весов тяжести
alpha = 0.6
hybrid_weights = {}

for code in mkb_tree:
    if not isinstance(code, str) or len(code) < 2:
        continue
    sev = severity_weights.get(code, 0.5)     # fallback
    rar = get_rarity_weight(code)
    hybrid_weights[code] = alpha * sev + (1 - alpha) * rar

# hybrid_weights готов для использования в PyTorch Loss