# Round-2 targeted MD corruption fixes for the 3 remaining compile-error files.
# Run in WSL:  python3 /mnt/d/Desktop/shijuan-paiban/scripts/fix_md_corruptions2.py
import os
import shutil

IS_NT = os.name == 'nt'
BASE = (r'D:\Music\试题加题库\高三数学\.math-output' if IS_NT
        else '/mnt/d/Music/试题加题库/高三数学/.math-output')


def load(name):
    with open(os.path.join(BASE, name), encoding='utf-8') as f:
        return f.read()


def save(name, text):
    with open(os.path.join(BASE, name), 'w', encoding='utf-8') as f:
        f.write(text)


def backup(name):
    src = os.path.join(BASE, name)
    dst = src + '.bak2'
    if not os.path.exists(dst):
        shutil.copy2(src, dst)


# ---------------------------------------------------------------
# 1) 附中月考二: delete the garbled 法二 block (alternative method).
#    法一 is complete and concludes with the final answer range;
#    法二's OCR text is unrecoverably corrupted (e^(-i), m'(i),
#    e^{nu_0} hallucinations, unclosed spans).
# ---------------------------------------------------------------
NAME1 = '湖南师范大学附属中学2025届高三上学期月考（二）数学答案.md'
t = load(NAME1)
marker = '法二:由题知'
i = t.find(marker)
assert i > 0, '法二 marker not found'
head = t[:i]
assert head.rstrip().endswith('综上所述,a的取值范围为 \\( (-∞,1] \\) .……………………'), \
    'unexpected line before 法二: ' + head.rstrip()[-80:]
backup(NAME1)
save(NAME1, head.rstrip() + '\n')
print(f'{NAME1}: deleted 法二 block ({len(t) - len(head)} chars)')

# ---------------------------------------------------------------
# 2) 雅礼月考三: close all unclosed \(...\) spans in Q18 ② region
#    and replace the OCR repetition-loop line; fix _\min subscript.
# ---------------------------------------------------------------
NAME2 = '雅礼中学2025届高三月考试卷三数学参考答案.md'
lines = load(NAME2).split('\n')


def set_line(lineno, old_prefix, new_line):
    idx = lineno - 1
    assert lines[idx].startswith(old_prefix), \
        f'L{lineno} mismatch: {lines[idx][:60]}'
    old_len = len(lines[idx])
    lines[idx] = new_line
    print(f'  L{lineno}: rewritten (len {old_len} -> {len(new_line)})')


set_line(107, '联立 \\( \\begin{cases} x^2 = 4y, \\\\ y = k(x - m)',
         r'联立 \( \begin{cases} x^2 = 4y, \\ y = k(x - m) + n, \end{cases} \) 消去 \( y \), 整理得：\( x^2 - 4kx + 4km - 4n = 0 \) (6分)')

set_line(109, '由题可知 \\( Δ',
         r'由题可知 \( \Delta = 16k^2 - 4(4km - 4n) = 0 \), 即 \( k^2 - mk + n = 0 \) (6分)')

set_line(113, '又因为 \\( F(0, 1)',
         r'又因为 \( F(0, 1), 所以 k\_3 = \frac{n-1}{m}, m \neq 0, 由 k\_1 + k\_2 = \frac{2}{k\_3}, 有 k\_1 + k\_2 = \frac{2}{k\_3}, 所以 m/n = \frac{2m}{n-1} \) (9分)')

set_line(117, '②由①知 \\( P(m, -1)',
         r'②由①知 \( P(m, -1), 设 l\_1: y=k\_4(x-m)-1, l\_2: y=k\_5(x-m)-1, m\neq\pm 1且m\neq0 \), …… (9分)')

set_line(119, '联立 \\( \\begin{cases} x^2 = 4y, \\\\ y = k\\_4',
         r'联立 \( \begin{cases} x^2 = 4y, \\ y = k\_4(x-m)-1, \end{cases} \) 消去 \( y \), 整理得 \( x^2 - 4k\_4x + 4k\_4m + 4 = 0 \) (6分)')

set_line(121, '又 \\( A(s\\_1, t\\_1)',
         r'又 \( A(s\_1, t\_1), B(s\_2, t\_2), C(s\_3, t\_3), D(s\_4, t\_4), 同理可得 s\_3s\_4=4k\_5m+4, 所以 s\_3s\_5s\_3s\_4=(4k\_4m+4)(4k\_5m+4)=16k\_4k\_5m^2+16m(k\_4+k\_5)+16 \), \( \dots \) …… (11分)')

set_line(123, '又因为 \\( l\\_1 和以圆心为',
         r'又因为 \( l\_1 \) 和以圆心为 \( Q(0,\lambda)\;(\lambda>0) \), 半径为 1 的圆相切.')

# fix bare \min subscript on L125
assert lines[124].count('|_\\min') == 1, 'L125 |\\_min count != 1'
lines[124] = lines[124].replace('|_\\min', '|_{\\min}')
print('  L125: |\\_min -> |_{\\min}')

backup(NAME2)
save(NAME2, '\n'.join(lines))
print(f'{NAME2}: fixed')

# ---------------------------------------------------------------
# 3) 雅礼五次月考: close the unclosed \( \forall ... span in Q10(2).
# ---------------------------------------------------------------
NAME3 = '雅礼中学2025届高三第五次月考数学试题答案.md'
t = load(NAME3)
old = r'(x\_{i+1}-y\_{i+1})^{2}\neq0. …… 10分'
new = r'(x\_{i+1}-y\_{i+1})^{2}\neq0 \). …… 10分'
assert t.count(old) == 1, f'expected 1 match, got {t.count(old)}'
backup(NAME3)
save(NAME3, t.replace(old, new))
print(f'{NAME3}: closed \\( \\forall span')

print('\nAll round-2 fixes applied.')
