from bs4 import BeautifulSoup
from src.decoder import (
    extract_d_table,
    decode_css_unicode,
    decode_marcador,
    DEFAULT_D_TABLE,
)


def test_decode_css_unicode():
    assert decode_css_unicode(r'"\0032"') == "2"
    assert decode_css_unicode(r'"\32"') == "2"
    assert decode_css_unicode(r'"\0037"') == "7"
    assert decode_css_unicode('"5"') == "5"


def test_extract_d_table():
    html_sample = '<script>var d=[1,2,3,4,5];</script>'
    table = extract_d_table(html_sample)
    assert table == [1, 2, 3, 4, 5]

    # Fallback to default
    assert extract_d_table("<div>no scripts</div>") == DEFAULT_D_TABLE


def test_decode_marcador_direct():
    html = '<td align="center"><h4><b>7</b> - <b>2</b></h4></td>'
    soup = BeautifulSoup(html, "html.parser")
    assert decode_marcador(soup.select_one("td")) == "7 - 2"


def test_decode_marcador_empty():
    html = '<td align="center"><h4><strong> </strong></h4></td>'
    soup = BeautifulSoup(html, "html.parser")
    assert decode_marcador(soup.select_one("td")) == ""


def test_decode_efro_b_match_jornada_2():
    # Fragmento extraído de la jornada 2 para Efro B vs San Ignacio
    snippet = """
    <td width="20%" align=center style="white-space:nowrap;border-bottom: 0px; line-height: 1;">
      <h4><strong>
        <span class="wid2_resultado_cerrada ntype">
          <i class=fa-solid><i id=idh136221 style="font-style:normal" class=fa-10>
          <script>ntype("idh136221",9,0,"fa-10");</script>
          <span style="display:none;">10</span></i></i> -</span>
        <span class="wid2_resultado_cerrada ntype">
          <i class=fa-solid><style>#idh136222:after{content:"\\0032"}</style>
          <span id=idh136222><span style="display:none;">3</span></span></i>
        </span>
      </strong></h4>
    </td>
    """
    soup = BeautifulSoup(snippet, "html.parser")
    marcador = decode_marcador(soup.select_one("td"), DEFAULT_D_TABLE)
    assert marcador == "7 - 2"
