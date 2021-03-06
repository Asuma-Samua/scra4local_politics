import sys
import re
from typing import List, Dict, Any

from chardet import UniversalDetector
import nkf
import mojimoji


def replace_empty_line(lines: str) -> str:
    r"""
    :param lines: 文字列
    :return: lines 内の空行を取り除いた文字列
    """
    # 改行文字が LF か CR+LF かはデータによるが，ここで LF に統一する
    lines = lines.replace('\r\n', '\n')

    # 空行 = "\n\n" のように，改行コードが2つ以上連続した部分
    lines = re.sub(r'\n{2,}', '\n', lines)
    return lines


def remove_number_honorific(person_string: str) -> Dict[str, Any]:
    r"""
    :param person_string: 「番」や「議員」「くん」などを含む，氏名情報
    :return: 辞書(議員番号, 氏名)
    """
    re_res = re.search(r'[0-9|０-９]+番', person_string)
    number = mojimoji.zen_to_han(person_string[re_res.start(): re_res.end() - 1])  # '番'を落とす -1
    name = person_string[re_res.end():]

    if name.endswith('議員') or name.endswith('さん'):
        name = name[:-2]
    elif name.endswith('君'):
        name = name[:-1]

    return {'number': number, 'name': name}


def parse(html_string: str) -> List[dict]:
    r"""
    :param html_string: htmlのソース
    :return: list(dict(number: 議員番号, name: 氏名), …)

    作戦：和歌山市のようなフォーマットに一度揃える
        要件1: 空行を含まないこと
        要件2: <br>タグではなく，改行コードで行の終わりを表す
    """
    # フォーマット変更ここから
    br_line_pattern = re.compile(r'( |　)*<(br|BR|br /|BR /)>( |　)*')  # 改行タグと空白のみ
    html_string = re.sub(br_line_pattern, '', html_string)  # からなる行を取り除く
    html_string = replace_empty_line(html_string)
    # フォーマット変更終わり

    re_res = re.search(r'出席.*', html_string)
    html_string = html_string[re_res.start():]  # 「出席」が含まれる行を開始地点とする

    member_list = []
    for row in html_string.split('\n')[1:]:  # 最初の行はいらない
        if '番' not in row or re.fullmatch(r'　*(―|－)+', row):
            break  # '番'が含まれない行，全角または半角のハイフン用いた水平線が終わりを表すと仮定

        ban_count = row.count('番')  # 1行に何人分の氏名がある？番の数で判断
        if ban_count == 2:
            pivot = row.rfind('番') - 2  # 2番目の「番」より2文字前まであたりを境界に，前後に名前がある
            member_list.append(row[:pivot])
            member_list.append(row[pivot:])
        elif ban_count == 1:
            member_list.append(row)
        else:  # 1行に3個以上の氏名がある場合は，ひとまず考えない
            sys.stderr.write('「番」の数が %d 個あり，対処できない\n' % ban_count)
            assert True

    member_list = [remove_number_honorific(member.replace('　', '').replace(' ', ''))
                   for member in member_list]
    return member_list


def det_encoding(file_path: str) -> str:
    r"""
    :param file_path: 文字コードを判定したいファイルのパス
    :return: 判定結果の文字コード
    """
    # 2つの方法で文字コード判定
    # 1. chardet.UniversalDetector
    detector = UniversalDetector()
    with open(file_path, mode='rb') as f:
        for binary in f:
            detector.feed(binary)
            if detector.done:
                break
    detector.close()
    chardet_res = detector.result['encoding'].lower()

    # 2. nkf
    with open(file_path, mode='rb') as f:
        nkf_res = nkf.guess(f.read()).lower()

    # 時々，2つの結果が食い違っていたりするが，どうにかして片方を選ぶ
    if chardet_res != nkf_res:
        sys.stderr.write('[warning] conflict char_codes: %s vs %s\n' % (chardet_res,  nkf_res))
        if 'cp932' in {chardet_res, nkf_res}:
            return 'CP932'  # 暫定的に，CP932の可能性がある時はCP932にしておく
        else:
            raise ValueError("現在扱えない文字コードで書かれたファイル：", file_path)
    return chardet_res


if __name__ == '__main__':
    # path = 'res/ibaraki.html'
    # path = 'res/takatsuki.html'
    # path = 'res/wakayama.html'
    # path = 'res/otsu.html'
    # path = 'res/hikone.html'
    path = 'res/higashiomi.html'
    # path = 'res/kusatsu.html'

    enc = det_encoding(path)

    with open(path, 'r', encoding=enc) as f:
        print(parse(f.read()))
