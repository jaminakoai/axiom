"""
Axiom Programming Language (λx) - Canonical Source Code Formatter
"""
import re
from typing import List, Tuple
from axiom.lexer import Lexer
from axiom.parser import Parser

class AxiomFormatter:
    """
    Standart Axiom kod biçimlendirici.
    4 boşluk girintileme, operatör ve anahtar kelime boşluk standardizasyonu sağlar.
    """
    def __init__(self, indent_size: int = 4):
        self.indent_size = indent_size
        self.indent_str = " " * indent_size

    def format(self, source: str) -> str:
        lines = source.splitlines()
        formatted_lines: List[str] = []
        indent_level = 0
        in_multiline_contract = False
        prev_was_empty = False

        for raw_line in lines:
            line = raw_line.strip()
            
            # Boş satır yönetimi
            if not line:
                if not prev_was_empty and formatted_lines:
                    formatted_lines.append("")
                    prev_was_empty = True
                continue
            prev_was_empty = False

            # Tek satır yorum kontrolü
            if line.startswith("//"):
                formatted_lines.append(f"{self.indent_str * indent_level}{line}")
                continue

            # Kapanış parantezi ile başlıyorsa girintiyi hemen düşür
            # Örnek: } veya } else {
            closing_count = 0
            # Satırın başındaki } sayısını say
            temp = line
            while temp.startswith("}"):
                closing_count += 1
                temp = temp[1:].strip()

            current_indent = max(0, indent_level - closing_count)

            # Requires / Ensures satırları fonksiyon girintisinden 1 kademe içeridedir
            is_contract = line.startswith("requires ") or line.startswith("ensures ")
            if is_contract:
                line_indent = (indent_level + 1) * self.indent_str
            else:
                line_indent = current_indent * self.indent_str

            # Satır içi token/operatör normalizasyonu
            normalized_line = self._normalize_line(line)

            formatted_lines.append(f"{line_indent}{normalized_line}")

            # Girinti seviyesi güncellemesi
            # Net açılan/kapanan parantez farkını hesapla (string içindekileri hariç tutarak)
            net_braces = self._count_net_braces(line)
            indent_level = max(0, indent_level + net_braces)

        result = "\n".join(formatted_lines).rstrip() + "\n"
        return result

    def _count_net_braces(self, line: str) -> int:
        in_string = False
        escape = False
        net = 0
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '/' and i + 1 < n and line[i+1] == '/':
                    # Satır sonu yorumu, sonrasını sayma
                    break
                elif ch == '"':
                    in_string = True
                elif ch == '{':
                    net += 1
                elif ch == '}':
                    net -= 1
            i += 1
        return net

    def _normalize_line(self, line: str) -> str:
        # String literal'ları ve yorumları ayırarak koru
        parts = []
        in_string = False
        escape = False
        curr = []
        i = 0
        n = len(line)

        while i < n:
            ch = line[i]
            if in_string:
                curr.append(ch)
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_string = False
                    parts.append(('str', "".join(curr)))
                    curr = []
            else:
                if ch == '/' and i + 1 < n and line[i+1] == '/':
                    if curr:
                        parts.append(('code', "".join(curr)))
                        curr = []
                    parts.append(('comment', line[i:]))
                    break
                elif ch == '"':
                    if curr:
                        parts.append(('code', "".join(curr)))
                        curr = []
                    curr.append(ch)
                    in_string = True
                else:
                    curr.append(ch)
            i += 1

        if curr:
            if in_string:
                parts.append(('str', "".join(curr)))
            else:
                parts.append(('code', "".join(curr)))

        # Kod parçalarını normalize et
        out = []
        for ptype, pval in parts:
            if ptype == 'code':
                out.append(self._format_code_segment(pval))
            else:
                out.append(pval)

        res = "".join(out).strip()
        if res == "{":
            return "{"
        # " { " düzenlemeleri
        res = re.sub(r'\s*\{\s*$', ' {', res)
        # "} else {" düzenlemesi
        res = re.sub(r'\}\s*else\s*\{', '} else {', res)
        return res

    def _format_code_segment(self, code: str) -> str:
        # 1. Fazla boşlukları tek boşluğa indir
        s = re.sub(r'[ \t]+', ' ', code)

        # 2. Virgül boşluğu
        s = re.sub(r'\s*,\s*', ', ', s)

        # 3. İki nokta boşluğu (tip bildirimleri: name: type)
        # Ancak "std:net/http" gibi durumlara dikkat: string içinde zaten korunuyor.
        s = re.sub(r'\s*:\s*', ': ', s)

        # 4. Ok işareti: ->
        s = re.sub(r'\s*->\s*', ' -> ', s)

        # 5. İkili operatörler: ==, !=, <=, >=
        s = re.sub(r'\s*(==|!=|<=|>=)\s*', r' \1 ', s)

        # 6. Tekli = (fakat ==, !=, <=, >= olmayan)
        s = re.sub(r'(?<![!=<>])=(?![=])', ' = ', s)

        # 7. < ve > (fakat <= veya >= veya -> olmayan)
        s = re.sub(r'(?<![-=])<(?!=)', ' < ', s)
        s = re.sub(r'(?<![-=])>(?!=)', ' > ', s)

        # 8. + ve * ve / ve %
        s = re.sub(r'\s*(\+|\*|/|%)\s*', r' \1 ', s)

        # 9. Parantez içleri boşluk temizliği: ( a ) -> (a)
        s = re.sub(r'\(\s+', '(', s)
        s = re.sub(r'\s+\)', ')', s)

        # 10. Köşeli parantez: [ a ] -> [a]
        s = re.sub(r'\[\s+', '[', s)
        s = re.sub(r'\s+\]', ']', s)

        # 11. Range ..
        s = re.sub(r'\s*\.\.\s*', '..', s)

        # Tekrar fazla ardışık boşlukları temizle
        s = re.sub(r'[ \t]+', ' ', s)
        return s

def format_source(source: str) -> str:
    formatter = AxiomFormatter()
    formatted = formatter.format(source)
    # Doğrulama: biçimlendirilmiş kod sözdizimsel olarak geçerli olmalı
    try:
        tokens = Lexer(formatted).tokenize()
        Parser(tokens).parse()
    except Exception:
        # Eğer bir nedenden ötürü parse edilemezse orijinal kodu koru
        return source
    return formatted
