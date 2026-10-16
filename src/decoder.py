import re
from bs4 import BeautifulSoup, Tag

DEFAULT_D_TABLE = [
    2, 5, 9, 4, 1, 0, 8, 6, 3, 7,
    1, 3, 5, 7, 9, 0, 2, 4, 6, 8,
    0, 2, 4, 6, 8, 1, 3, 5, 7, 9,
    7, 5, 2, 0, 9, 6, 3, 8, 4, 1
]


def extract_d_table(soup_or_html) -> list[int]:
    """Extrae el array de sustitución 'd' del script ntype en la página."""
    html = str(soup_or_html)
    m = re.search(r'd=\[([0-9, ]+)\]', html)
    if m:
        return [int(x.strip()) for x in m.group(1).split(',')]
    return DEFAULT_D_TABLE


def decode_css_unicode(content_val: str) -> str:
    """Convierte secuencias de escape CSS Unicode como '\\0032' o '\\32' a caracter."""
    clean = content_val.strip('\'"')
    if clean.startswith("\\"):
        hex_part = clean.lstrip("\\0")
        try:
            return chr(int(hex_part, 16))
        except ValueError:
            return clean
    return clean


def parse_score_part(element, d_table: list[int] = None) -> str:
    """Extrae un dígito o número de un elemento (span o td) de marcador."""
    if d_table is None:
        d_table = DEFAULT_D_TABLE

    html = str(element)
    
    # 1. Comprobar si hay llamada a ntype("idh...", n, i, ...)
    nt_m = re.search(r'ntype\(["\'](\w+)["\'],\s*(\d+),\s*(\d+)', html)
    if nt_m:
        n = int(nt_m.group(2))
        i = int(nt_m.group(3))
        idx = (i * 10) + n
        if 0 <= idx < len(d_table):
            return str(d_table[idx])

    # 2. Comprobar reglas <style>...</style> asociadas
    # Formato: #idh136224:after{content:"\0032"} o :before
    style_matches = re.findall(
        r'<style[^>]*>[\s\S]*?(:(?:before|after))\s*\{([^}]+)\}[\s\S]*?</style>',
        html,
        re.IGNORECASE
    )
    for pseudo, rule in style_matches:
        # Si la regla pseudo-elemento tiene display:none, ignorar esa regla
        if "display:none" in rule.replace(" ", "").lower():
            continue
        c_m = re.search(r'content:\s*["\'](.*?)["\']', rule, re.IGNORECASE)
        if c_m:
            val = decode_css_unicode(c_m.group(1))
            if val.isdigit():
                return val

    # 3. Extraer contenido visible en el DOM descartando honeypots (display:none)
    if isinstance(element, Tag):
        # Clonar o limpiar elementos ocultos
        clean_soup = BeautifulSoup(str(element), "html.parser")
        for hidden in clean_soup.find_all(style=re.compile(r'display:\s*none', re.I)):
            hidden.decompose()
        for tag in clean_soup.find_all(["script", "style"]):
            tag.decompose()
        text = clean_soup.get_text(strip=True).replace("-", "").strip()
        if text.isdigit():
            return text

    return ""


def decode_marcador(marcador_element, d_table: list[int] = None) -> str:
    """
    Decodifica el marcador de un partido a partir del elemento del DOM (td o h4).
    Devuelve un string en formato 'X - Y' o cadena vacía si no se ha jugado.
    """
    if d_table is None:
        d_table = DEFAULT_D_TABLE

    if not marcador_element:
        return ""

    # Caso directo simple si no hay ofuscación: ej. <b>6</b> - <b>5</b>
    plain_text = re.sub(r'<[^>]+>', ' ', str(marcador_element)).strip()
    direct_m = re.search(r'^(\d+)\s*-\s*(\d+)$', plain_text)
    if direct_m:
        return f"{direct_m.group(1)} - {direct_m.group(2)}"

    # Buscar spans con clase wid2_resultado_* o spans hijos
    spans = marcador_element.select('[class*="wid2_resultado"]')
    if len(spans) >= 2:
        part_local = parse_score_part(spans[0], d_table)
        part_visit = parse_score_part(spans[1], d_table)
        if part_local and part_visit:
            return f"{part_local} - {part_visit}"

    # Si no hay dos spans con wid2_resultado, intentar buscar separador '-'
    raw_html = str(marcador_element)
    if "-" in raw_html:
        parts = raw_html.split("-", 1)
        soup_loc = BeautifulSoup(parts[0], "html.parser")
        soup_vis = BeautifulSoup(parts[1], "html.parser")
        l = parse_score_part(soup_loc, d_table)
        v = parse_score_part(soup_vis, d_table)
        if l and v:
            return f"{l} - {v}"

    return ""
