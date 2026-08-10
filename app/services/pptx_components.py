from pathlib import Path

import tempfile

from PIL import Image, ImageDraw, ImageFont

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Pt, Inches

# ==========================================================
# CONFIGURAÇÃO GERAL
# ==========================================================

ESCALA = 1.5


def pol(valor: float):
    """
    Converte as medidas do layout-base 13,333 × 7,5
    para o template de 20 × 11,25 polegadas.
    """
    return Inches(valor * ESCALA)


APP_DIR_COMPONENTES = Path(__file__).resolve().parents[1]

ASSETS_CARAVANA = (
    APP_DIR_COMPONENTES
    / "templates"
    / "pptx"
    / "assets_caravana"
)


AZUL_ESCURO = RGBColor(1, 26, 69)
AZUL_HEADER = RGBColor(1, 28, 72)
AZUL_TEXTO = RGBColor(5, 31, 79)
AZUL_CLARO = RGBColor(0, 174, 239)
AZUL_MATRICULAS = RGBColor(13, 55, 151)
AZUL_HORA_ALUNO = RGBColor(0, 101, 129)

VERDE_RECEITA = RGBColor(23, 125, 30)
ROXO_GR = RGBColor(49, 14, 143)

BRANCO = RGBColor(255, 255, 255)
PRETO = RGBColor(20, 20, 20)

FUNDO_META = RGBColor(237, 244, 254)
FUNDO_REGIAO = RGBColor(230, 246, 247)
BORDA_CARD = RGBColor(207, 224, 243)

_CACHE_IMAGENS_RECORTADAS: dict[str, Path] = {}


def _remover_margens_transparentes(
    caminho: Path,
) -> Path:
    """
    Remove as margens transparentes externas de um PNG.

    O arquivo original não é modificado. Uma cópia recortada
    é criada na pasta temporária do sistema.
    """
    if not caminho.exists():
        return caminho

    if caminho.suffix.lower() != ".png":
        return caminho

    chave = str(caminho.resolve())

    if chave in _CACHE_IMAGENS_RECORTADAS:
        return _CACHE_IMAGENS_RECORTADAS[chave]

    try:
        with Image.open(caminho) as imagem:
            imagem = imagem.convert("RGBA")

            canal_alpha = imagem.getchannel("A")
            limite = canal_alpha.getbbox()

            if limite is None:
                return caminho

            largura_original, altura_original = imagem.size

            # O PNG já não possui margens transparentes.
            if limite == (
                0,
                0,
                largura_original,
                altura_original,
            ):
                return caminho

            imagem_recortada = imagem.crop(limite)

            destino = (
                Path(tempfile.gettempdir())
                / f"logo_caravana_{abs(hash(chave))}.png"
            )

            imagem_recortada.save(destino)

            _CACHE_IMAGENS_RECORTADAS[chave] = destino

            return destino

    except Exception:
        # Em caso de falha, usa o PNG original.
        return caminho

def _recortar_icone_programas(
    caminho: Path,
    margem: int = 1,
) -> Path:
    """
    Remove o espaço externo do ícone de Programas.

    Diferentemente do recorte por transparência, identifica
    o círculo azul pelo contraste com a cor dos cantos.
    """
    if not caminho.exists():
        return caminho

    if caminho.suffix.lower() != ".png":
        return caminho

    chave = (
        f"icone_programas_v1::"
        f"{caminho.resolve()}::{margem}"
    )

    if chave in _CACHE_IMAGENS_RECORTADAS:
        return _CACHE_IMAGENS_RECORTADAS[chave]

    try:
        with Image.open(caminho) as imagem:
            imagem = imagem.convert("RGBA")

            largura, altura = imagem.size

            cantos = [
                imagem.getpixel((0, 0)),
                imagem.getpixel((largura - 1, 0)),
                imagem.getpixel((0, altura - 1)),
                imagem.getpixel((largura - 1, altura - 1)),
            ]

            fundo_r = sum(pixel[0] for pixel in cantos) // 4
            fundo_g = sum(pixel[1] for pixel in cantos) // 4
            fundo_b = sum(pixel[2] for pixel in cantos) // 4

            pixels = []

            for vermelho, verde, azul, alpha in imagem.getdata():
                distancia_fundo = max(
                    abs(vermelho - fundo_r),
                    abs(verde - fundo_g),
                    abs(azul - fundo_b),
                )

                # Torna transparente o fundo externo do PNG.
                if alpha < 20 or distancia_fundo <= 20:
                    pixels.append(
                        (vermelho, verde, azul, 0)
                    )
                else:
                    pixels.append(
                        (vermelho, verde, azul, alpha)
                    )

            imagem.putdata(pixels)

            alpha = imagem.getchannel("A")
            limite = alpha.getbbox()

            if limite is None:
                return caminho

            esquerda, topo, direita, inferior = limite

            esquerda = max(0, esquerda - margem)
            topo = max(0, topo - margem)
            direita = min(
                imagem.width,
                direita + margem,
            )
            inferior = min(
                imagem.height,
                inferior + margem,
            )

            imagem_recortada = imagem.crop(
                (
                    esquerda,
                    topo,
                    direita,
                    inferior,
                )
            )

            destino = (
                Path(tempfile.gettempdir())
                / (
                    "icone_programas_recortado_"
                    f"{abs(hash(chave))}.png"
                )
            )

            imagem_recortada.save(destino)

            _CACHE_IMAGENS_RECORTADAS[chave] = destino

            return destino

    except Exception:
        return caminho

def _recortar_icone_transparente(
    caminho: Path,
    limite_alpha: int = 20,
    margem: int = 2,
) -> Path:
    """
    Recorta somente margens transparentes.

    Não remove pixels brancos, pois alguns ícones possuem
    elementos brancos que precisam ser preservados.
    """
    if not caminho.exists():
        return caminho

    if caminho.suffix.lower() != ".png":
        return caminho

    chave = (
        f"icone_alpha_v2::{caminho.resolve()}::"
        f"{limite_alpha}::{margem}"
    )

    if chave in _CACHE_IMAGENS_RECORTADAS:
        return _CACHE_IMAGENS_RECORTADAS[chave]

    try:
        with Image.open(caminho) as imagem:
            imagem = imagem.convert("RGBA")

            alpha = imagem.getchannel("A")

            mascara = alpha.point(
                lambda valor: 255 if valor >= limite_alpha else 0
            )

            limite = mascara.getbbox()

            if limite is None:
                return caminho

            esquerda, topo, direita, inferior = limite

            esquerda = max(0, esquerda - margem)
            topo = max(0, topo - margem)
            direita = min(imagem.width, direita + margem)
            inferior = min(imagem.height, inferior + margem)

            imagem_recortada = imagem.crop(
                (esquerda, topo, direita, inferior)
            )

            destino = (
                Path(tempfile.gettempdir())
                / f"icone_alpha_v2_{abs(hash(chave))}.png"
            )

            imagem_recortada.save(destino)

            _CACHE_IMAGENS_RECORTADAS[chave] = destino

            return destino

    except Exception:
        return caminho

def _recortar_icone_participacao(
    caminho: Path,
    tolerancia: int = 18,
    margem: int = 2,
) -> Path:
    """
    Recorta especificamente o ícone de participação.

    O fundo é identificado pela cor dos cantos da imagem.
    Isso funciona mesmo quando o fundo não é branco puro
    ou quando o PNG não possui transparência verdadeira.
    """
    if not caminho.exists():
        return caminho

    if caminho.suffix.lower() != ".png":
        return caminho

    chave = (
        f"participacao_fundo_v3::{caminho.resolve()}::"
        f"{tolerancia}::{margem}"
    )

    if chave in _CACHE_IMAGENS_RECORTADAS:
        return _CACHE_IMAGENS_RECORTADAS[chave]

    try:
        with Image.open(caminho) as imagem:
            imagem = imagem.convert("RGBA")

            largura, altura = imagem.size

            cantos = [
                imagem.getpixel((0, 0)),
                imagem.getpixel((largura - 1, 0)),
                imagem.getpixel((0, altura - 1)),
                imagem.getpixel((largura - 1, altura - 1)),
            ]

            # Usa a média das cores dos quatro cantos como fundo.
            fundo_r = sum(pixel[0] for pixel in cantos) // 4
            fundo_g = sum(pixel[1] for pixel in cantos) // 4
            fundo_b = sum(pixel[2] for pixel in cantos) // 4

            pixels_tratados = []

            for vermelho, verde, azul, alpha in imagem.getdata():
                distancia_fundo = max(
                    abs(vermelho - fundo_r),
                    abs(verde - fundo_g),
                    abs(azul - fundo_b),
                )

                if alpha < 20 or distancia_fundo <= tolerancia:
                    pixels_tratados.append(
                        (vermelho, verde, azul, 0)
                    )
                else:
                    pixels_tratados.append(
                        (vermelho, verde, azul, alpha)
                    )

            imagem.putdata(pixels_tratados)

            alpha = imagem.getchannel("A")
            limite = alpha.getbbox()

            if limite is None:
                return caminho

            esquerda, topo, direita, inferior = limite

            esquerda = max(0, esquerda - margem)
            topo = max(0, topo - margem)
            direita = min(imagem.width, direita + margem)
            inferior = min(imagem.height, inferior + margem)

            imagem_recortada = imagem.crop(
                (esquerda, topo, direita, inferior)
            )

            destino = (
                Path(tempfile.gettempdir())
                / f"icone_participacao_v3_{abs(hash(chave))}.png"
            )

            imagem_recortada.save(destino)

            _CACHE_IMAGENS_RECORTADAS[chave] = destino

            return destino

    except Exception:
        return caminho

# ==========================================================
# FUNÇÕES BÁSICAS
# ==========================================================

def adicionar_imagem(
    slide,
    caminho: Path,
    esquerda,
    topo,
    largura=None,
    altura=None,
):
    """
    Adiciona uma imagem preservando sua proporção original.

    Informe largura ou altura, nunca as duas medidas.
    """
    if not caminho.exists():
        return None

    parametros = {
        "image_file": str(caminho),
        "left": esquerda,
        "top": topo,
    }

    if largura is not None:
        parametros["width"] = largura
    elif altura is not None:
        parametros["height"] = altura

    return slide.shapes.add_picture(**parametros)


def retangulo(
    slide,
    esquerda,
    topo,
    largura,
    altura,
    cor,
    linha=None,
    raio=True,
):
    tipo = (
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE
        if raio
        else MSO_AUTO_SHAPE_TYPE.RECTANGLE
    )

    shape = slide.shapes.add_shape(
        tipo,
        esquerda,
        topo,
        largura,
        altura,
    )

    shape.fill.solid()
    shape.fill.fore_color.rgb = cor

    if linha is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = linha
        shape.line.width = Pt(1)

    return shape


def texto(
    slide,
    texto: str,
    esquerda,
    topo,
    largura,
    altura,
    tamanho: float,
    cor: RGBColor,
    *,
    negrito=False,
    alinhamento=PP_ALIGN.LEFT,
    vertical=MSO_ANCHOR.MIDDLE,
    fonte="Arial",
):
    caixa = slide.shapes.add_textbox(
        esquerda,
        topo,
        largura,
        altura,
    )

    frame = caixa.text_frame
    frame.clear()
    frame.word_wrap = True

    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    frame.vertical_anchor = vertical

    paragrafo = frame.paragraphs[0]
    paragrafo.alignment = alinhamento
    paragrafo.space_before = Pt(0)
    paragrafo.space_after = Pt(0)
    paragrafo.line_spacing = 1

    run = paragrafo.add_run()
    run.text = str(texto)
    run.font.name = fonte
    run.font.size = Pt(tamanho)
    run.font.bold = negrito
    run.font.color.rgb = cor

    return caixa


def texto_com_runs(
    slide,
    runs: list[dict],
    esquerda,
    topo,
    largura,
    altura,
    *,
    tamanho_padrao=12,
    cor_padrao=AZUL_TEXTO,
    alinhamento=PP_ALIGN.LEFT,
    vertical=MSO_ANCHOR.MIDDLE,
    fonte="Arial",
):
    """
    Adiciona texto com trechos de cores e estilos diferentes.

    Cada elemento de runs aceita:
    {
        "texto": "...",
        "cor": RGBColor(...),
        "negrito": True,
        "tamanho": 12
    }
    """
    caixa = slide.shapes.add_textbox(
        esquerda,
        topo,
        largura,
        altura,
    )

    frame = caixa.text_frame
    frame.clear()
    frame.word_wrap = True

    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    frame.vertical_anchor = vertical

    paragrafo = frame.paragraphs[0]
    paragrafo.alignment = alinhamento
    paragrafo.space_before = Pt(0)
    paragrafo.space_after = Pt(0)
    paragrafo.line_spacing = 1.05

    for configuracao in runs:
        run = paragrafo.add_run()
        run.text = configuracao.get("texto", "")
        run.font.name = fonte
        run.font.size = Pt(
            configuracao.get("tamanho", tamanho_padrao)
        )
        run.font.bold = configuracao.get("negrito", False)
        run.font.color.rgb = configuracao.get(
            "cor",
            cor_padrao,
        )

    return caixa


# ==========================================================
# CABEÇALHO
# ==========================================================

def cabecalho_caravana(
    slide,
    largura_slide,
    nome_regiao: str,
    ano: int,
):
    altura = pol(0.82)

    retangulo(
        slide=slide,
        esquerda=0,
        topo=0,
        largura=largura_slide,
        altura=altura,
        cor=AZUL_HEADER,
        raio=False,
    )

    faixas = [
        (5.85, 1.55, RGBColor(2, 47, 111)),
        (6.40, 1.55, RGBColor(3, 73, 158)),
        (6.95, 1.70, RGBColor(0, 120, 205)),
    ]

    for esquerda, largura, cor in faixas:
        shape = slide.shapes.add_shape(
            MSO_SHAPE.PARALLELOGRAM,
            pol(esquerda),
            0,
            pol(largura),
            altura,
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = cor
        shape.line.fill.background()

    for linha in range(5):
        for coluna in range(15):
            ponto = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.OVAL,
                pol(7.55 + coluna * 0.14),
                pol(0.055 + linha * 0.125),
                pol(0.018),
                pol(0.018),
            )
            ponto.fill.solid()
            ponto.fill.fore_color.rgb = RGBColor(
                0,
                210,
                245,
            )
            ponto.line.fill.background()

    texto(
        slide=slide,
        texto=f"REGIÃO {nome_regiao.upper()}",
        esquerda=pol(0.31),
        topo=pol(0.085),
        largura=pol(5.65),
        altura=pol(0.36),
        tamanho=34,
        cor=BRANCO,
        negrito=True,
    )

    texto(
        slide=slide,
        texto=f"Contribuição para as Metas SENAI-RS | {ano}",
        esquerda=pol(0.31),
        topo=pol(0.45),
        largura=pol(5.80),
        altura=pol(0.24),
        tamanho=20,
        cor=RGBColor(67, 204, 255),
        negrito=True,
    )

    caminho_logo = (
        ASSETS_CARAVANA
        / "senai_branco.png"
    )

    caminho_logo_recortado = (
        _remover_margens_transparentes(
            caminho_logo
        )
    )

    logo = adicionar_imagem(
        slide=slide,
        caminho=caminho_logo_recortado,

        # A posição definitiva será calculada abaixo.
        esquerda=0,
        topo=0,

        # Tamanho do conteúdo real, após retirar as margens.
        largura=pol(1.30),
    )

    if logo is not None:
        margem_direita = pol(0.30)

        # Alinha o conteúdo real do logo à direita.
        logo.left = (
            largura_slide
            - logo.width
            - margem_direita
        )

        # Deixa exatamente o mesmo espaço acima e abaixo.
        logo.top = int(
            (altura - logo.height) / 2
        )

    if logo is None:
        texto(
            slide=slide,
            texto="SENAI",
            esquerda=pol(11.10),
            topo=pol(0.06),
            largura=pol(1.80),
            altura=pol(0.32),
            tamanho=29,
            cor=BRANCO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
        )

        texto(
            slide=slide,
            texto="PELO FUTURO DO TRABALHO",
            esquerda=pol(11.10),
            topo=pol(0.41),
            largura=pol(1.80),
            altura=pol(0.14),
            tamanho=6,
            cor=BRANCO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
        )

# ==========================================================
# PAINEL LATERAL
# ==========================================================

def bloco_lateral(
    slide,
    *,
    topo,
    altura,
    cor_fundo,
    icone: str,
    texto_bloco: str,
    cor_texto,
    cor_borda=None,
    largura_icone: float = 0.48,
    esquerda_icone: float = 0.13,
    tamanho_texto: float = 17,
    esquerda_texto: float = 0.70,
    crop_left: float = 0.0,
    crop_right: float = 0.0,
    crop_top: float = 0.0,
    crop_bottom: float = 0.0,
    ajuste_vertical_icone: float = 0.0,
):
    """
    Cria um dos três blocos do painel lateral.

    As medidas específicas de cada ícone e texto são recebidas
    por parâmetro para permitir o alinhamento fiel ao modelo.
    """
    esquerda = pol(0.20)
    largura = pol(1.82)

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=cor_fundo,
        linha=cor_borda,
    )

    caminho_icone = (
        ASSETS_CARAVANA
        / icone
    )

    # Os ícones 1 e 2 possuem transparência real.
    # O terceiro será recortado diretamente no PowerPoint.
    if icone != "icone_participacao.png":
        caminho_icone = _recortar_icone_transparente(
            caminho=caminho_icone,
            limite_alpha=20,
            margem=2,
        )

    # ======================================================
    # INSERÇÃO DO ÍCONE
    # ======================================================

    imagem_icone = adicionar_imagem(
        slide=slide,
        caminho=caminho_icone,

        # Usa a posição específica recebida em cada bloco.
        esquerda=esquerda + pol(esquerda_icone),

        # A posição vertical será recalculada abaixo.
        topo=0,

        # Usa a largura específica recebida em cada bloco.
        largura=pol(largura_icone),
    )

    if imagem_icone is not None:
        # Recortes específicos, especialmente para Participação.
        imagem_icone.crop_left = crop_left
        imagem_icone.crop_right = crop_right
        imagem_icone.crop_top = crop_top
        imagem_icone.crop_bottom = crop_bottom

        # Centraliza verticalmente o ícone dentro do card.
        imagem_icone.top = int(
            topo
            + (
                altura
                - imagem_icone.height
            )
            / 2
            + pol(ajuste_vertical_icone)
        )

    texto(
        slide=slide,
        texto=texto_bloco,
        esquerda=esquerda + pol(esquerda_texto),
        topo=topo + pol(0.07),
        largura=largura - pol(esquerda_texto + 0.10),
        altura=altura - pol(0.14),
        tamanho=tamanho_texto,
        cor=cor_texto,
        negrito=True,

        # No modelo, os textos ficam alinhados à esquerda.
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

def painel_esquerdo_panorama(
    slide,
    nome_regiao: str,
) -> None:
    """
    Desenha o painel lateral conforme o padrão visual original.
    """

    # ======================================================
    # BLOCO 1 — SENAI-RS
    # ======================================================

    bloco_lateral(
        slide=slide,
        topo=pol(1.77),
        altura=pol(0.88),
        cor_fundo=RGBColor(3, 52, 137),
        icone="icone_senai_rs.png",
        texto_bloco="SENAI-RS",
        cor_texto=BRANCO,

        # Ícone maior, como no padrão.
        largura_icone=0.48,
        esquerda_icone=0.15,

        # Texto maior e mais próximo do ícone.
        tamanho_texto=18,
        esquerda_texto=0.72,
    )

    # ======================================================
    # BLOCO 2 — REGIÃO
    # ======================================================

    bloco_lateral(
        slide=slide,
        topo=pol(2.77),
        altura=pol(1.00),
        cor_fundo=RGBColor(0, 101, 126),
        icone="icone_regiao.png",
        texto_bloco=(
            f"Região\n"
            f"{nome_regiao.title()}"
        ),
        cor_texto=BRANCO,

        # Marcador de localização maior.
        largura_icone=0.40,
        esquerda_icone=0.17,

        tamanho_texto=17,
        esquerda_texto=0.70,
    )

    # ======================================================
    # BLOCO 3 — PARTICIPAÇÃO
    # ======================================================

    bloco_lateral(
        slide=slide,
        topo=pol(3.91),
        altura=pol(0.86),
        cor_fundo=RGBColor(237, 244, 253),
        icone="icone_participacao.png",
        texto_bloco="Participação\nda Região",
        cor_texto=PRETO,
        cor_borda=BORDA_CARD,

        largura_icone=0.62,
        esquerda_icone=0.08,

        tamanho_texto=17,
        esquerda_texto=0.70,

        crop_left=0.20,
        crop_right=0.10,
        crop_top=0.20,
        crop_bottom=0.12,

        # Desce levemente o ícone.
        ajuste_vertical_icone=0.035,
    )

# ==========================================================
# CARDS
# ==========================================================

def card_panorama(
    slide,
    *,
    esquerda,
    topo,
    largura,
    titulo,
    subtitulo,
    cor,
    icone,
    valor_meta,
    valor_regiao,
    percentual,
    ano,
):
    altura = pol(3.34)

    # ======================================================
    # CONTORNO EXTERNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
    )

    # ======================================================
    # CABEÇALHO DO CARD
    # ======================================================

    topo_cabecalho = topo + pol(0.08)
    altura_cabecalho = pol(0.52)

    # Área fixa reservada ao ícone.
    esquerda_area_icone = esquerda + pol(0.20)
    largura_area_icone = pol(0.62)
    altura_area_icone = pol(0.55)

    caminho_icone = (
        ASSETS_CARAVANA
        / icone
    )

    # Remove margens transparentes reais do PNG.
    caminho_icone = _recortar_icone_transparente(
        caminho=caminho_icone,
        limite_alpha=20,
        margem=1,
    )

    # Todos os ícones terão exatamente a mesma altura visual.
    altura_icone = (
        pol(0.58)
        if titulo == "RECEITA"
        else pol(0.50)
    )

    imagem_icone = adicionar_imagem(
        slide=slide,
        caminho=caminho_icone,
        esquerda=0,
        topo=0,
        altura=pol(0.50),
    )

    if imagem_icone is not None:

        # O PNG de Receita possui espaços internos nos quatro lados.
        # O recorte amplia somente o conteúdo visível do ícone.
        if titulo == "RECEITA":
            imagem_icone.crop_left = 0.14
            imagem_icone.crop_right = 0.14
            imagem_icone.crop_top = 0.14
            imagem_icone.crop_bottom = 0.14

        imagem_icone.left = int(
            esquerda_area_icone
            + (
                largura_area_icone
                - imagem_icone.width
            )
            / 2
        )

        imagem_icone.top = int(
            topo_cabecalho
            + (
                altura_cabecalho
                - imagem_icone.height
            )
            / 2
        )

    # Todos os títulos começam exatamente no mesmo ponto.
    esquerda_titulo = esquerda + pol(0.90)

    texto(
        slide=slide,
        texto=titulo,
        esquerda=esquerda_titulo,
        topo=topo + pol(0.08),
        largura=largura - pol(1.00),
        altura=pol(0.31),
        tamanho=20,
        cor=cor,
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    if subtitulo:
        texto(
            slide=slide,
            texto=subtitulo,
            esquerda=esquerda_titulo,
            topo=topo + pol(0.37),
            largura=largura - pol(1.00),
            altura=pol(0.17),
            tamanho=9,
            cor=cor,
            negrito=True,
            alinhamento=PP_ALIGN.LEFT,
            vertical=MSO_ANCHOR.MIDDLE,
        )

    # ======================================================
    # TRÊS RETÂNGULOS INTERNOS
    # ======================================================

    linhas = [
        {
            "topo": pol(0.70),
            "fundo": FUNDO_META,
            "valor": valor_meta,
            "rotulo": f"Meta {ano}",
            "cor": AZUL_TEXTO,
        },
        {
            "topo": pol(1.59),
            "fundo": FUNDO_REGIAO,
            "valor": valor_regiao,
            "rotulo": f"Meta {ano}",

            # mesma cor utilizada na Hora-Aluno
            "cor": AZUL_HORA_ALUNO,
        },
        {
            "topo": pol(2.48),
            "fundo": FUNDO_META,
            "valor": percentual,
            "rotulo": "de participação",
            "cor": cor,
        },
    ]

    for linha in linhas:
        topo_linha = topo + linha["topo"]

        margem_interna = pol(0.16)

        retangulo(
            slide=slide,
            esquerda=esquerda + margem_interna,
            topo=topo_linha,
            largura=largura - (margem_interna * 2),
            altura=pol(0.76),
            cor=linha["fundo"],
        )

        texto(
            slide=slide,
            texto=linha["valor"],
            esquerda=esquerda + margem_interna,
            topo=topo_linha + pol(0.04),
            largura=largura - (margem_interna * 2),
            altura=pol(0.37),
            tamanho=28,
            cor=linha["cor"],
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
        )

        texto(
            slide=slide,
            texto=linha["rotulo"],
            esquerda=esquerda + margem_interna,
            topo=topo_linha + pol(0.43),
            largura=largura - (margem_interna * 2),
            altura=pol(0.21),
            tamanho=15,
            cor=PRETO,
            alinhamento=PP_ALIGN.CENTER,
        )

def cards_panorama(
    slide,
    ano: int,
    dados: dict,
):
    topo = pol(1.43)

    # Margem esquerda dos cards.
    x_inicial = pol(2.15)

    # Largura dos cards e distância entre eles.
    largura = pol(2.68)
    intervalo = pol(2.77)

    configuracoes = [
        {
            "titulo": "MATRÍCULAS",
            "subtitulo": "",
            "cor": AZUL_MATRICULAS,
            "icone": "icone_matriculas.png",
            "dados": dados["matriculas"],
        },
        {
            "titulo": "RECEITA",
            "subtitulo": "",
            "cor": VERDE_RECEITA,
            "icone": "icone_receita.png",
            "dados": dados["receita"],
        },
        {
            "titulo": "HORA-ALUNO",
            "subtitulo": "",
            "cor": AZUL_HORA_ALUNO,
            "icone": "icone_hora_aluno.png",
            "dados": dados["hora_aluno"],
        },
        {
            "titulo": "HORA-ALUNO GR",
            "subtitulo": "(Gratuidade Regimental)",
            "cor": ROXO_GR,
            "icone": "icone_hora_aluno_gr.png",
            "dados": dados["hora_aluno_gr"],
        },
    ]

    for indice, configuracao in enumerate(configuracoes):
        dados_card = configuracao["dados"]

        card_panorama(
            slide=slide,
            esquerda=(
                x_inicial
                + intervalo * indice
            ),
            topo=topo,
            largura=largura,
            titulo=configuracao["titulo"],
            subtitulo=configuracao["subtitulo"],
            cor=configuracao["cor"],
            icone=configuracao["icone"],
            valor_meta=dados_card["meta"],
            valor_regiao=dados_card["regiao"],
            percentual=dados_card["percentual"],
            ano=ano,
        )

# ==========================================================
# CAIXA EXPLICATIVA
# ==========================================================

def caixa_resumo_panorama(
    slide,
    *,
    nome_regiao,
    percentual_matriculas,
    percentual_receita,
    percentual_hora_aluno,
    percentual_gr,
):
    esquerda = pol(1.05)
    topo = pol(5.12)
    largura = pol(11.18)
    altura = pol(0.95)

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=RGBColor(246, 250, 255),
        linha=RGBColor(20, 74, 215),
    )

    # Círculo azul menor
    circulo = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.OVAL,
        esquerda + pol(0.15),
        topo + pol(0.055),
        pol(0.82),
        pol(0.82),
    )

    circulo.fill.solid()
    circulo.fill.fore_color.rgb = AZUL_ESCURO
    circulo.line.fill.background()

    # Insere o PNG dentro do círculo
    imagem_crescimento = adicionar_imagem(
        slide=slide,
        caminho=ASSETS_CARAVANA / "icone_crescimento.png",
        esquerda=esquerda + pol(0.225),
        topo=topo + pol(0.230),   # antes era 0.125
        largura=pol(0.67),
    )

    if imagem_crescimento is not None:
        # Remove visualmente as margens internas do PNG.
        # O recorte aumenta o desenho branco sem aumentar o círculo.
        imagem_crescimento.crop_left = 0.18
        imagem_crescimento.crop_right = 0.18
        imagem_crescimento.crop_top = 0.18
        imagem_crescimento.crop_bottom = 0.18

    runs = [
        {
            "texto": f"A Região {nome_regiao.title()} representa cerca de ",
            "cor": AZUL_TEXTO,
        },
        {
            "texto": percentual_matriculas,
            "cor": AZUL_MATRICULAS,
            "negrito": True,
        },
        {
            "texto": " das matrículas, ",
            "cor": AZUL_TEXTO,
        },
        {
            "texto": percentual_receita,
            "cor": VERDE_RECEITA,
            "negrito": True,
        },
        {
            "texto": " da receita,\n",
            "cor": AZUL_TEXTO,
        },
        {
            "texto": percentual_hora_aluno,
            "cor": AZUL_HORA_ALUNO,
            "negrito": True,
        },
        {
            "texto": " da Hora-Aluno e ",
            "cor": AZUL_TEXTO,
        },
        {
            "texto": percentual_gr,
            "cor": ROXO_GR,
            "negrito": True,
        },
        {
            "texto": " da Hora-Aluno em Gratuidade Regimental ",
            "cor": AZUL_TEXTO,
            "negrito": True,
        },
        {
            "texto": (
                "do SENAI-RS,\nreforçando sua relevância para o "
                "cumprimento da missão institucional."
            ),
            "cor": AZUL_TEXTO,
        },
    ]

    texto_com_runs(
        slide=slide,
        runs=runs,
        esquerda=esquerda + pol(1.13),
        topo=topo + pol(0.07),
        largura=largura - pol(1.33),
        altura=altura - pol(0.12),
        tamanho_padrao=17,
        vertical=MSO_ANCHOR.MIDDLE,
    )

# ==========================================================
# RODAPÉ
# ==========================================================

def rodape_panorama(
    slide,
    *,
    nome_regiao,
    fracao_matriculas,
    fracao_hora_aluno,
    fracao_gr,
):
    topo = pol(6.28)
    altura = pol(1.22)

    retangulo(
        slide,
        0,
        topo,
        pol(13.333),
        altura,
        AZUL_ESCURO,
        raio=False,
    )

    adicionar_imagem(
        slide,
        ASSETS_CARAVANA / "icone_estrela.png",
        pol(0.34),
        topo + pol(0.13),
        altura=pol(0.74),
    )

    texto(
        slide,
        f"A Região {nome_regiao.title()} responde por aproximadamente",
        pol(1.39),
        topo + pol(0.14),
        pol(5.75),
        pol(0.24),
        17,
        BRANCO,
    )

    texto_com_runs(
        slide,
        [
            {
                "texto": fracao_matriculas,
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 18,
            },
            {
                "texto": " matrículas, ",
                "cor": BRANCO,
                "tamanho": 17,
            },
            {
                "texto": fracao_hora_aluno,
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 18,
            },
            {
                "texto": " horas-aluno e",
                "cor": BRANCO,
                "tamanho": 17,
            },
        ],
        pol(1.39),
        topo + pol(0.43),
        pol(5.90),
        pol(0.27),
        tamanho_padrao=17,
    )

    texto_com_runs(
        slide,
        [
            {
                "texto": fracao_gr,
                "cor": RGBColor(164, 74, 245),
                "negrito": True,
                "tamanho": 18,
            },
            {
                "texto": " horas-aluno de ",
                "cor": BRANCO,
                "tamanho": 17,
            },
            {
                "texto": "Gratuidade Regimental",
                "cor": RGBColor(164, 74, 245),
                "negrito": True,
                "tamanho": 18,
            },
            {
                "texto": " do SENAI-RS.",
                "cor": BRANCO,
                "tamanho": 17,
            },
        ],
        pol(1.39),
        topo + pol(0.72),
        pol(6.20),
        pol(0.27),
        tamanho_padrao=17,
    )

    adicionar_imagem(
        slide,
        ASSETS_CARAVANA / "icone_crescimento.png",
        pol(8.28),
        topo + pol(0.18),
        altura=pol(0.72),
    )

    divisor = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        pol(9.10),
        topo + pol(0.14),
        pol(0.012),
        pol(0.88),
    )
    divisor.fill.solid()
    divisor.fill.fore_color.rgb = BRANCO
    divisor.line.fill.background()

    texto(
        slide,
        "Fontes dos dados:",
        pol(9.42),
        topo + pol(0.25),
        pol(2.00),
        pol(0.22),
        16,
        BRANCO,
    )

    texto(
        slide,
        "Solução Integradora • Cubo Orçamento",
        pol(9.42),
        topo + pol(0.57),
        pol(3.30),
        pol(0.24),
        13,
        BRANCO,
    )

def card_superior_panorama_executivo(
    slide,
    *,
    esquerda,
    topo,
    largura,
    titulo: str,
    valor: str,
    rotulo: str,
    cor: RGBColor,
    icone: str,
) -> None:
    """
    Cria um card superior do slide Panorama Executivo.
    """

    altura = pol(1.02)

    # ======================================================
    # CARD EXTERNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
    )

    # ======================================================
    # ÍCONE — usa diretamente o círculo existente no PNG
    # ======================================================

    caminho_icone = ASSETS_CARAVANA / icone

    if titulo == "PROGRAMAS":
        caminho_icone = _recortar_icone_programas(
            caminho=caminho_icone,
            margem=1,
        )
    else:
        caminho_icone = _recortar_icone_transparente(
            caminho=caminho_icone,
            limite_alpha=20,
            margem=1,
        )

    altura_icone = pol(0.64)

    imagem_icone = adicionar_imagem(
        slide=slide,
        caminho=caminho_icone,
        esquerda=0,
        topo=0,
        altura=altura_icone,
    )

    if imagem_icone is not None:
        area_esquerda = esquerda + pol(0.18)
        area_topo = topo + pol(0.12)
        area_largura = pol(0.70)
        area_altura = pol(0.70)

        # Alguns PNGs possuem margens internas.
        # O crop aumenta apenas o conteúdo visível,
        # mantendo todos os ícones exatamente com o mesmo diâmetro.

        if titulo == "RECEITA":
            imagem_icone.crop_left = 0.13
            imagem_icone.crop_right = 0.13
            imagem_icone.crop_top = 0.13
            imagem_icone.crop_bottom = 0.13

        imagem_icone.left = int(
            area_esquerda
            + (
                area_largura
                - imagem_icone.width
            )
            / 2
        )

        imagem_icone.top = int(
            area_topo
            + (
                area_altura
                - imagem_icone.height
            )
            / 2
        )

    # ======================================================
    # TÍTULO
    # ======================================================

    texto(
        slide=slide,
        texto=titulo,
        esquerda=esquerda + pol(1.02),
        topo=topo + pol(0.12),
        largura=largura - pol(1.17),
        altura=pol(0.22),
        tamanho=17,
        cor=AZUL_TEXTO,
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # VALOR
    # ======================================================

    tamanho_valor = 28

    if titulo == "RECEITA":
        tamanho_valor = 24
    elif titulo == "HORA-ALUNO":
        tamanho_valor = 25

    texto(
        slide=slide,
        texto=str(valor),
        esquerda=esquerda + pol(1.02),
        topo=topo + pol(0.34),
        largura=largura - pol(1.17),
        altura=pol(0.36),
        tamanho=tamanho_valor,
        cor=cor,
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # RÓTULO
    # ======================================================

    texto(
        slide=slide,
        texto=rotulo,
        esquerda=esquerda + pol(1.02),
        topo=topo + pol(0.72),
        largura=largura - pol(1.17),
        altura=pol(0.20),
        tamanho=14,
        cor=AZUL_TEXTO,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )


def cards_superiores_panorama_executivo(
    slide,
    *,
    ano: int,
    dados: dict,
) -> None:
    """
    Cria os quatro cards superiores do Panorama Executivo.
    """

    topo = pol(1.00)

    margem_esquerda = 0.20
    margem_direita = 0.20
    espaco = 0.12

    largura_util = (
        13.333
        - margem_esquerda
        - margem_direita
        - espaco * 3
    )

    largura_card = largura_util / 4

    configuracoes = [
        {
            "titulo": "PROGRAMAS",
            "valor": str(
                dados.get(
                    "total_programas",
                    "—",
                )
            ),
            "rotulo": "Total de Programas",
            "cor": AZUL_MATRICULAS,
            "icone": "icone_programas.png",
        },
        {
            "titulo": "MATRÍCULAS",
            "valor": dados["matriculas"]["regiao"],
            "rotulo": f"Meta {ano}",
            "cor": AZUL_MATRICULAS,
            "icone": "icone_matriculas.png",
        },
        {
            "titulo": "HORA-ALUNO",
            "valor": dados["hora_aluno"]["regiao"],
            "rotulo": f"Meta {ano}",
            "cor": AZUL_HORA_ALUNO,
            "icone": "icone_hora_aluno.png",
        },
        {
            "titulo": "RECEITA",
            "valor": dados["receita"]["regiao"],
            "rotulo": f"Meta {ano}",
            "cor": VERDE_RECEITA,
            "icone": "icone_receita.png",
        },
    ]

    for indice, configuracao in enumerate(configuracoes):
        x = (
            margem_esquerda
            + indice * (
                largura_card
                + espaco
            )
        )

        card_superior_panorama_executivo(
            slide=slide,
            esquerda=pol(x),
            topo=topo,
            largura=pol(largura_card),
            titulo=configuracao["titulo"],
            valor=configuracao["valor"],
            rotulo=configuracao["rotulo"],
            cor=configuracao["cor"],
            icone=configuracao["icone"],
        )

def _rgb_para_hex(cor: RGBColor) -> str:
    """
    Converte RGBColor do python-pptx para cor hexadecimal.
    """
    return f"#{cor[0]:02x}{cor[1]:02x}{cor[2]:02x}"


def _gerar_grafico_rosca_matriculas(
    *,
    valor_gr: float,
    valor_gnr: float,
    valor_pg: float,
) -> Path:
    """
    Gera um gráfico de rosca em PNG transparente usando Pillow.
    """

    valores = [
        max(float(valor_gr or 0), 0),
        max(float(valor_gnr or 0), 0),
        max(float(valor_pg or 0), 0),
    ]

    total = sum(valores)

    if total <= 0:
        valores = [1, 0, 0]
        total = 1
        mostrar_percentuais = False
    else:
        mostrar_percentuais = True

    tamanho = 900
    margem = 35

    imagem = Image.new(
        "RGBA",
        (tamanho, tamanho),
        (255, 255, 255, 0),
    )

    desenho = ImageDraw.Draw(imagem)

    caixa_externa = (
        margem,
        margem,
        tamanho - margem,
        tamanho - margem,
    )

    cores = [
        tuple(AZUL_MATRICULAS) + (255,),
        tuple(AZUL_HORA_ALUNO) + (255,),
        (54, 139, 15, 255),
    ]

    angulo_inicial = -90

    fatias = []

    for valor, cor in zip(valores, cores):
        percentual = valor / total
        angulo_final = (
            angulo_inicial
            + percentual * 360
        )

        desenho.pieslice(
            caixa_externa,
            start=angulo_inicial,
            end=angulo_final,
            fill=cor,
            outline=(255, 255, 255, 255),
            width=3,
        )

        fatias.append(
            (
                angulo_inicial,
                angulo_final,
                percentual,
            )
        )

        angulo_inicial = angulo_final

    # Furo central
    diametro_furo = int(tamanho * 0.42)

    esquerda_furo = (
        tamanho - diametro_furo
    ) // 2

    topo_furo = (
        tamanho - diametro_furo
    ) // 2

    desenho.ellipse(
        (
            esquerda_furo,
            topo_furo,
            esquerda_furo + diametro_furo,
            topo_furo + diametro_furo,
        ),
        fill=(255, 255, 255, 255),
    )

    # Fonte dos percentuais
    try:
        fonte = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            54,
        )
    except Exception:
        fonte = ImageFont.load_default()

    if mostrar_percentuais:
        import math

        raio_texto = tamanho * 0.25
        centro = tamanho / 2

        for indice_fatia, (inicio, fim, percentual) in enumerate(fatias):
            # Mostra também fatias pequenas, como 0,58% e 0,73%.
            # Somente valores abaixo de 0,40% serão ocultados.
            if percentual < 0.004:
                continue

            angulo_meio = math.radians(
                (inicio + fim) / 2
            )

            # ======================================================
            # POSIÇÃO DINÂMICA DOS RÓTULOS
            # ======================================================

            # Fatias pequenas precisam ficar um pouco mais afastadas
            # do furo central para o texto não desaparecer.
            if percentual < 0.02:
                raio_rotulo = tamanho * 0.305
            elif percentual < 0.10:
                raio_rotulo = tamanho * 0.285
            else:
                raio_rotulo = tamanho * 0.275

            x = (
                centro
                + raio_rotulo
                * math.cos(angulo_meio)
            )

            y = (
                centro
                + raio_rotulo
                * math.sin(angulo_meio)
            )

            # Ordem:
            # 0 = GR
            # 1 = GNR
            # 2 = PG

            if indice_fatia == 0:
                # GR: afasta o texto do centro para a direita
                # quando a fatia estiver no lado direito.
                direcao_x = (
                    1
                    if math.cos(angulo_meio) >= 0
                    else -1
                )

                x += direcao_x * tamanho * 0.035

            elif indice_fatia == 1:
                # GNR: é justamente a fatia que estava mostrando
                # 17,99% e 27,27% sobre o círculo branco.
                direcao_x = (
                    1
                    if math.cos(angulo_meio) >= 0
                    else -1
                )

                x += direcao_x * tamanho * 0.075

                # Pequeno ajuste vertical para não coincidir
                # com a borda do furo.
                direcao_y = (
                    1
                    if math.sin(angulo_meio) >= 0
                    else -1
                )

                y += direcao_y * tamanho * 0.018

            elif indice_fatia == 2:
                # PG: afasta o texto do centro para o lado
                # em que a fatia estiver posicionada.
                direcao_x = (
                    1
                    if math.cos(angulo_meio) >= 0
                    else -1
                )

                x += direcao_x * tamanho * 0.035
            
            rotulo = (
                f"{percentual * 100:.2f}%"
                .replace(".", ",")
            )

            # Fonte específica do rótulo.
            # Percentuais pequenos precisam de uma fonte menor
            # para caberem na fatia estreita.
            if percentual < 0.01:
                try:
                    fonte_rotulo = ImageFont.truetype(
                        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                        38,
                    )
                except Exception:
                    fonte_rotulo = fonte

            elif percentual < 0.02:
                try:
                    fonte_rotulo = ImageFont.truetype(
                        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                        43,
                    )
                except Exception:
                    fonte_rotulo = fonte

            else:
                fonte_rotulo = fonte

            caixa_texto = desenho.textbbox(
                (0, 0),
                rotulo,
                font=fonte_rotulo,
            )

            largura_texto = (
                caixa_texto[2]
                - caixa_texto[0]
            )

            altura_texto = (
                caixa_texto[3]
                - caixa_texto[1]
            )

            desenho.text(
                (
                    x - largura_texto / 2,
                    y - altura_texto / 2,
                ),
                rotulo,
                fill=(255, 255, 255, 255),
                font=fonte_rotulo,
            )

    chave = (
        round(valor_gr, 4),
        round(valor_gnr, 4),
        round(valor_pg, 4),
    )

    caminho = (
        Path(tempfile.gettempdir())
        / (
            "grafico_rosca_matriculas_v3_"
            f"{abs(hash(chave))}.png"
        )
    )

    imagem.save(caminho)

    return caminho

def bloco_distribuicao_matriculas_executivo(
    slide,
    *,
    total_matriculas: str,
    distribuicao: dict | None = None,
) -> None:
    """
    Cria o bloco Distribuição das Matrículas.

    distribuicao deve possuir:

    {
        "gr": {
            "valor": 100,
            "valor_formatado": "100",
            "percentual": 10.5,
            "percentual_formatado": "10,50%",
        },
        "gnr": {...},
        "pg": {...},
    }
    """

    esquerda = pol(0.20)
    topo = pol(2.18)
    largura = pol(3.12)
    altura = pol(3.18)

    distribuicao = distribuicao or {}

    dados_gr = distribuicao.get("gr", {})
    dados_gnr = distribuicao.get("gnr", {})
    dados_pg = distribuicao.get("pg", {})

    valor_gr = float(dados_gr.get("valor", 0) or 0)
    valor_gnr = float(dados_gnr.get("valor", 0) or 0)
    valor_pg = float(dados_pg.get("valor", 0) or 0)

    # Evita erro do gráfico quando todos os valores forem zero.
    valores_grafico = [
        valor_gr,
        valor_gnr,
        valor_pg,
    ]

    if sum(valores_grafico) <= 0:
        valores_grafico = [1, 0, 0]

    # ======================================================
    # CONTORNO EXTERNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
    )

    # ======================================================
    # FAIXA DO TÍTULO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=pol(0.31),
        cor=AZUL_MATRICULAS,
        raio=False,
    )

    texto(
        slide=slide,
        texto="DISTRIBUIÇÃO DAS MATRÍCULAS",
        esquerda=esquerda + pol(0.10),
        topo=topo + pol(0.035),
        largura=largura - pol(0.20),
        altura=pol(0.23),
        tamanho=16,
        cor=BRANCO,
        negrito=True,
        alinhamento=PP_ALIGN.CENTER,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # GRÁFICO DE ROSCA COMO IMAGEM
    # ======================================================

    caminho_grafico = _gerar_grafico_rosca_matriculas(
        valor_gr=valor_gr,
        valor_gnr=valor_gnr,
        valor_pg=valor_pg,
    )

    adicionar_imagem(
        slide=slide,
        caminho=caminho_grafico,
        esquerda=esquerda + pol(0.12),
        topo=topo + pol(0.43),
        largura=pol(1.78),
    )

    # ======================================================
    # LEGENDA
    # ======================================================

    itens_legenda = [
        {
            "sigla": "GR",
            "valor": dados_gr.get(
                "valor_formatado",
                "0",
            ),
            "percentual": dados_gr.get(
                "percentual_formatado",
                "0,00%",
            ),
            "cor": AZUL_MATRICULAS,
        },
        {
            "sigla": "GNR",
            "valor": dados_gnr.get(
                "valor_formatado",
                "0",
            ),
            "percentual": dados_gnr.get(
                "percentual_formatado",
                "0,00%",
            ),
            "cor": AZUL_HORA_ALUNO,
        },
        {
            "sigla": "PG",
            "valor": dados_pg.get(
                "valor_formatado",
                "0",
            ),
            "percentual": dados_pg.get(
                "percentual_formatado",
                "0,00%",
            ),
            "cor": RGBColor(54, 139, 15),
        },
    ]

    for indice, item in enumerate(itens_legenda):
        y = topo + pol(0.57 + indice * 0.64)

        marcador = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            esquerda + pol(2.00),
            y,
            pol(0.13),
            pol(0.13),
        )

        marcador.fill.solid()
        marcador.fill.fore_color.rgb = item["cor"]
        marcador.line.fill.background()

        texto(
            slide=slide,
            texto=item["sigla"],
            esquerda=esquerda + pol(2.20),
            topo=y - pol(0.03),
            largura=pol(0.65),
            altura=pol(0.20),
            tamanho=15,
            cor=AZUL_TEXTO,
            negrito=True,
        )

        texto(
            slide=slide,
            texto=item["valor"],
            esquerda=esquerda + pol(2.20),
            topo=y + pol(0.17),
            largura=pol(0.72),
            altura=pol(0.19),
            tamanho=13,
            cor=AZUL_TEXTO,
            negrito=True,
        )

        texto(
            slide=slide,
            texto=f"({item['percentual']})",
            esquerda=esquerda + pol(2.20),
            topo=y + pol(0.36),
            largura=pol(0.76),
            altura=pol(0.17),
            tamanho=11,
            cor=AZUL_TEXTO,
        )

    # ======================================================
    # FAIXA INFERIOR
    # ======================================================

    margem_faixa = pol(0.24)

    retangulo(
        slide=slide,
        esquerda=esquerda + margem_faixa,
        topo=topo + pol(2.60),

        # Reduz a largura para não ultrapassar a borda.
        largura=largura - (
            margem_faixa * 2
        ),

        altura=pol(0.46),
        cor=FUNDO_META,
    )

    caminho_icone = (
        ASSETS_CARAVANA
        / "icone_hora_aluno_gr.png"
    )

    caminho_icone = _recortar_icone_transparente(
        caminho=caminho_icone,
        limite_alpha=20,
        margem=1,
    )

    adicionar_imagem(
        slide=slide,
        caminho=caminho_icone,

        # Antes: 0.18
        # Move o ícone para dentro da faixa.
        esquerda=esquerda + pol(0.28),

        topo=topo + pol(2.68),
        altura=pol(0.29),
    )

    texto(
        slide=slide,
        texto=(
            "Total de Matrículas\n"
            "por Financiamento"
        ),
        esquerda=esquerda + pol(0.70),
        topo=topo + pol(2.63),
        largura=pol(1.40),
        altura=pol(0.38),
        tamanho=12,
        cor=AZUL_TEXTO,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    valor_total_matriculas = str(total_matriculas)

    texto(
        slide=slide,
        texto=valor_total_matriculas,
        esquerda=esquerda + pol(1.78),
        topo=topo + pol(2.69),
        largura=pol(0.94),
        altura=pol(0.29),
        tamanho=12,
        cor=AZUL_MATRICULAS,
        negrito=True,
        alinhamento=PP_ALIGN.RIGHT,
    )

def bloco_distribuicao_hora_aluno_executivo(
    slide,
    *,
    total_hora_aluno: str,
    distribuicao: dict | None = None,
) -> None:
    """
    Cria o bloco Distribuição da Hora-Aluno.
    """

    # Fica imediatamente ao lado do bloco de matrículas.
    esquerda = pol(3.44)
    topo = pol(2.18)
    largura = pol(3.12)
    altura = pol(3.18)

    distribuicao = distribuicao or {}

    dados_gr = distribuicao.get("gr", {})
    dados_gnr = distribuicao.get("gnr", {})
    dados_pg = distribuicao.get("pg", {})

    valor_gr = float(
        dados_gr.get("valor", 0)
        or 0
    )

    valor_gnr = float(
        dados_gnr.get("valor", 0)
        or 0
    )

    valor_pg = float(
        dados_pg.get("valor", 0)
        or 0
    )

    # ======================================================
    # CONTORNO EXTERNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
    )

    # ======================================================
    # FAIXA DO TÍTULO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=pol(0.31),
        cor=AZUL_HORA_ALUNO,
        raio=False,
    )

    texto(
        slide=slide,
        texto="DISTRIBUIÇÃO DA HORA-ALUNO",
        esquerda=esquerda + pol(0.10),
        topo=topo + pol(0.035),
        largura=largura - pol(0.20),
        altura=pol(0.23),
        tamanho=16,
        cor=BRANCO,
        negrito=True,
        alinhamento=PP_ALIGN.CENTER,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # GRÁFICO DE ROSCA
    # ======================================================

    caminho_grafico = _gerar_grafico_rosca_matriculas(
        valor_gr=valor_gr,
        valor_gnr=valor_gnr,
        valor_pg=valor_pg,
    )

    adicionar_imagem(
        slide=slide,
        caminho=caminho_grafico,
        esquerda=esquerda + pol(0.12),
        topo=topo + pol(0.43),
        largura=pol(1.78),
    )

    # ======================================================
    # LEGENDA
    # ======================================================

    itens_legenda = [
        {
            "sigla": "GR",
            "valor": dados_gr.get(
                "valor_formatado",
                "0",
            ),
            "percentual": dados_gr.get(
                "percentual_formatado",
                "0,00%",
            ),
            "cor": AZUL_MATRICULAS,
        },
        {
            "sigla": "GNR",
            "valor": dados_gnr.get(
                "valor_formatado",
                "0",
            ),
            "percentual": dados_gnr.get(
                "percentual_formatado",
                "0,00%",
            ),
            "cor": AZUL_HORA_ALUNO,
        },
        {
            "sigla": "PG",
            "valor": dados_pg.get(
                "valor_formatado",
                "0",
            ),
            "percentual": dados_pg.get(
                "percentual_formatado",
                "0,00%",
            ),
            "cor": RGBColor(54, 139, 15),
        },
    ]

    for indice, item in enumerate(itens_legenda):
        y = topo + pol(
            0.57
            + indice * 0.64
        )

        marcador = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            esquerda + pol(2.00),
            y,
            pol(0.13),
            pol(0.13),
        )

        marcador.fill.solid()
        marcador.fill.fore_color.rgb = item["cor"]
        marcador.line.fill.background()

        texto(
            slide=slide,
            texto=item["sigla"],
            esquerda=esquerda + pol(2.20),
            topo=y - pol(0.03),
            largura=pol(0.65),
            altura=pol(0.20),
            tamanho=15,
            cor=AZUL_TEXTO,
            negrito=True,
        )

        texto(
            slide=slide,
            texto=item["valor"],
            esquerda=esquerda + pol(2.20),
            topo=y + pol(0.17),
            largura=pol(0.78),
            altura=pol(0.19),
            tamanho=13,
            cor=AZUL_TEXTO,
            negrito=True,
        )

        texto(
            slide=slide,
            texto=f"({item['percentual']})",
            esquerda=esquerda + pol(2.20),
            topo=y + pol(0.36),
            largura=pol(0.78),
            altura=pol(0.17),
            tamanho=11,
            cor=AZUL_TEXTO,
        )

    # ======================================================
    # FAIXA INFERIOR
    # ======================================================

    margem_faixa = pol(0.24)

    retangulo(
        slide=slide,
        esquerda=esquerda + margem_faixa,
        topo=topo + pol(2.60),
        largura=largura - (
            margem_faixa * 2
        ),
        altura=pol(0.46),
        cor=FUNDO_META,
    )

    caminho_icone = (
        ASSETS_CARAVANA
        / "icone_hora_aluno.png"
    )

    caminho_icone = _recortar_icone_transparente(
        caminho=caminho_icone,
        limite_alpha=20,
        margem=1,
    )

    adicionar_imagem(
        slide=slide,
        caminho=caminho_icone,
        esquerda=esquerda + pol(0.28),
        topo=topo + pol(2.68),
        altura=pol(0.29),
    )

    texto(
        slide=slide,
        texto=(
            "Total de Hora-Aluno\n"
            "por Financiamento"
        ),
        esquerda=esquerda + pol(0.70),
        topo=topo + pol(2.63),
        largura=pol(1.10),
        altura=pol(0.38),
        tamanho=11,
        cor=AZUL_TEXTO,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    valor_total_hora_aluno = str(total_hora_aluno)

    texto(
        slide=slide,
        texto=valor_total_hora_aluno,
        esquerda=esquerda + pol(1.78),
        topo=topo + pol(2.69),
        largura=pol(0.94),
        altura=pol(0.29),
        tamanho=12,
        cor=AZUL_HORA_ALUNO,
        negrito=True,
        alinhamento=PP_ALIGN.RIGHT,
    )

def bloco_receita_executivo(
    slide,
    *,
    total_receita: str,
    ano: int,
) -> None:
    """
    Cria o bloco-resumo de Receita do Panorama Executivo.

    Este bloco não possui distribuição por financiamento.
    """

    esquerda = pol(6.68)
    topo = pol(2.18)
    largura = pol(3.12)
    altura = pol(3.18)

    # ======================================================
    # CONTORNO EXTERNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
    )

    # ======================================================
    # FAIXA SUPERIOR ROXA
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=pol(0.31),
        cor=ROXO_GR,
        raio=False,
    )

    texto(
        slide=slide,
        texto="RECEITA",
        esquerda=esquerda + pol(0.10),
        topo=topo + pol(0.035),
        largura=largura - pol(0.20),
        altura=pol(0.23),
        tamanho=16,
        cor=BRANCO,
        negrito=True,
        alinhamento=PP_ALIGN.CENTER,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # CÍRCULO ROXO CENTRAL
    # ======================================================

    diametro = pol(1.18)

    esquerda_circulo = (
        esquerda
        + (
            largura
            - diametro
        )
        / 2
    )

    topo_circulo = topo + pol(0.79)

    circulo = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.OVAL,
        esquerda_circulo,
        topo_circulo,
        diametro,
        diametro,
    )

    circulo.fill.solid()
    circulo.fill.fore_color.rgb = ROXO_GR
    circulo.line.fill.background()

    # Símbolo de receita dentro do círculo.
    texto(
        slide=slide,
        texto="$",
        esquerda=esquerda_circulo,
        topo=topo_circulo - pol(0.03),
        largura=diametro,
        altura=diametro,
        tamanho=57,
        cor=BRANCO,
        negrito=False,
        alinhamento=PP_ALIGN.CENTER,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # VALOR DA RECEITA
    # ======================================================

    valor_receita = str(total_receita)

    if len(valor_receita) <= 17:
        tamanho_valor = 23
    elif len(valor_receita) <= 20:
        tamanho_valor = 21
    else:
        tamanho_valor = 19

    texto(
        slide=slide,
        texto=valor_receita,
        esquerda=esquerda + pol(0.16),
        topo=topo + pol(2.02),
        largura=largura - pol(0.32),
        altura=pol(0.40),
        tamanho=tamanho_valor,
        cor=ROXO_GR,
        negrito=True,
        alinhamento=PP_ALIGN.CENTER,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # RÓTULO INFERIOR
    # ======================================================

    texto(
        slide=slide,
        texto=f"Meta de Receita {ano}",
        esquerda=esquerda + pol(0.20),
        topo=topo + pol(2.47),
        largura=largura - pol(0.40),
        altura=pol(0.27),
        tamanho=16,
        cor=AZUL_TEXTO,
        negrito=False,
        alinhamento=PP_ALIGN.CENTER,
        vertical=MSO_ANCHOR.MIDDLE,
    )

def bloco_destaques_regiao_executivo(
    slide,
    *,
    total_programas: str,
    total_matriculas: str,
    total_hora_aluno: str,
    matriculas_gr: str,
    percentual_hora_aluno_gr: str,
    receita: str,
    programa_destaque: str,
    ano: int,
) -> None:
    """
    Cria o card Principais Destaques da Região.
    """

    esquerda = pol(9.92)
    topo = pol(2.18)
    largura = pol(3.21)
    altura = pol(3.18)

    programa_destaque = str(
        programa_destaque or "programas da região"
    ).strip()

    # ======================================================
    # CONTORNO EXTERNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
    )

    # ======================================================
    # CABEÇALHO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=pol(0.31),
        cor=AZUL_ESCURO,
        raio=False,
    )

    texto(
        slide=slide,
        texto="PRINCIPAIS DESTAQUES DA REGIÃO",
        esquerda=esquerda + pol(0.08),
        topo=topo + pol(0.035),
        largura=largura - pol(0.16),
        altura=pol(0.23),
        tamanho=14,
        cor=BRANCO,
        negrito=True,
        alinhamento=PP_ALIGN.CENTER,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # DADOS DAS SEIS LINHAS
    # ======================================================

    itens = [
        {
            # Este arquivo possui somente a estrela branca.
            # O círculo azul será criado pelo código.
            "icone": "icone_estrela.png",
            "possui_circulo": False,
            "cor_circulo": AZUL_MATRICULAS,
            "cor": AZUL_MATRICULAS,
            "valor": str(total_programas),
            "complemento": (
                " programas\n"
                "compõem o portfólio da região."
            ),
            "tamanho": 20,
        },
        {
            # Ícone de pessoas com círculo próprio.
            "icone": "icone_hora_aluno_gr.png",
            "possui_circulo": True,
            "cor": AZUL_HORA_ALUNO,
            "valor": str(total_matriculas),
            "complemento": (
                " matrículas\n"
                f"em {programa_destaque} e demais programas."
            ),
            "tamanho": 18,
        },
        {
            # Ícone de formação com círculo próprio.
            "icone": "icone_matriculas.png",
            "possui_circulo": True,
            "cor": RGBColor(54, 139, 15),
            "valor": str(total_hora_aluno),
            "complemento": (
                " horas-aluno\n"
                "distribuídas entre os programas."
            ),
            "tamanho": 16,
        },
        {
            # Novo ícone da maleta.
            "icone": "icone_ha_gr.png",
            "possui_circulo": True,
            "cor": AZUL_HORA_ALUNO,
            "valor": str(matriculas_gr),
            "complemento": (
                " matrículas\n"
                "em Gratuidade Regimental."
            ),
            "tamanho": 18,
        },
        {
            # Este arquivo possui somente o gráfico branco.
            # O círculo roxo será criado pelo código.
            "icone": "icone_crescimento.png",
            "possui_circulo": False,
            "cor_circulo": ROXO_GR,
            "cor": ROXO_GR,
            "valor": str(percentual_hora_aluno_gr),
            "complemento": (
                " da Hora-Aluno concentrada\n"
                "em Gratuidade Regimental."
            ),
            "tamanho": 18,
        },
        {
            # Ícone de receita com círculo próprio.
            "icone": "icone_receita.png",
            "possui_circulo": True,
            "cor": VERDE_RECEITA,
            "valor": str(receita),
            "complemento": (
                f"\nem receita prevista para {ano}."
            ),
            "tamanho": 15,
        },
    ]

    # Altura disponível depois do cabeçalho.
    altura_linha = 0.455

    for indice, item in enumerate(itens):
        topo_linha = topo + pol(
            0.35 + indice * altura_linha
        )

        # ==================================================
        # ÍCONE
        # ==================================================

        area_esquerda = esquerda + pol(0.16)
        area_topo = topo_linha + pol(0.045)
        diametro_icone = pol(0.36)

        caminho_icone = (
            ASSETS_CARAVANA
            / item["icone"]
        )

        caminho_icone = _recortar_icone_transparente(
            caminho=caminho_icone,
            limite_alpha=20,
            margem=1,
        )

        if item.get("possui_circulo", True):
            # O próprio PNG já contém o círculo colorido.
            imagem_icone = adicionar_imagem(
                slide=slide,
                caminho=caminho_icone,
                esquerda=area_esquerda,
                topo=area_topo,
                altura=diametro_icone,
            )

            if imagem_icone is not None:
                # O PNG da Receita possui margens internas.
                if item["icone"] == "icone_receita.png":
                    imagem_icone.crop_left = 0.13
                    imagem_icone.crop_right = 0.13
                    imagem_icone.crop_top = 0.13
                    imagem_icone.crop_bottom = 0.13

        else:
            # Estrela e gráfico de crescimento não possuem círculo
            # no arquivo. Portanto, criamos o círculo no PowerPoint.
            circulo = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.OVAL,
                area_esquerda,
                area_topo,
                diametro_icone,
                diametro_icone,
            )

            circulo.fill.solid()
            circulo.fill.fore_color.rgb = item["cor_circulo"]
            circulo.line.fill.background()

            # Insere somente o desenho branco dentro do círculo.
            altura_desenho = pol(0.23)

            imagem_icone = adicionar_imagem(
                slide=slide,
                caminho=caminho_icone,
                esquerda=0,
                topo=0,
                altura=altura_desenho,
            )

            if imagem_icone is not None:
                imagem_icone.left = int(
                    area_esquerda
                    + (
                        diametro_icone
                        - imagem_icone.width
                    )
                    / 2
                )

                imagem_icone.top = int(
                    area_topo
                    + (
                        diametro_icone
                        - imagem_icone.height
                    )
                    / 2
                )

                # Amplia um pouco o gráfico de crescimento,
                # que possui margens internas no PNG.
                if item["icone"] == "icone_crescimento.png":
                    imagem_icone.crop_left = 0.16
                    imagem_icone.crop_right = 0.16
                    imagem_icone.crop_top = 0.16
                    imagem_icone.crop_bottom = 0.16

        # ==================================================
        # VALOR E COMPLEMENTO
        # ==================================================

        texto_com_runs(
            slide=slide,
            runs=[
                {
                    "texto": item["valor"],
                    "cor": item["cor"],
                    "negrito": True,
                    "tamanho": item["tamanho"],
                },
                {
                    "texto": item["complemento"],
                    "cor": AZUL_TEXTO,
                    "tamanho": 11,
                },
            ],
            esquerda=esquerda + pol(0.70),
            topo=topo_linha,
            largura=largura - pol(0.82),
            altura=pol(0.43),
            tamanho_padrao=11,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        

def bloco_resumo_executivo_panorama(
    slide,
    *,
    nome_regiao: str,
    ano: int,
    programas_destaque: list[str] | None = None,
) -> None:
    """
    Cria o bloco executivo abaixo dos cards de Matrículas,
    Hora-Aluno e Receita.
    """

    esquerda = pol(0.20)
    topo = pol(5.52)
    largura = pol(9.60)
    altura = pol(0.58)

    # ======================================================
    # TRATAMENTO DOS PROGRAMAS
    # ======================================================

    programas = [
        str(programa).strip()
        for programa in (programas_destaque or [])
        if str(programa).strip()
    ][:3]

    while len(programas) < 3:
        programas.append("Programa não informado")

    programa_1, programa_2, programa_3 = programas

    def formatar_nome_programa(nome: str) -> str:
        """
        Coloca as iniciais em maiúsculas,
        preservando artigos, preposições e siglas.
        """

        palavras_minusculas = {
            "a",
            "as",
            "o",
            "os",
            "de",
            "da",
            "das",
            "do",
            "dos",
            "e",
            "em",
            "para",
            "por",
        }

        siglas = {
            "RS",
            "EAD",
            "SENAI",
            "SESI",
            "IEL",
            "EJA",
            "NEJ",
            "GR",
            "GNR",
        }

        resultado = []

        for indice, palavra in enumerate(
            str(nome or "").strip().split()
        ):
            palavra_limpa = palavra.strip()
            palavra_upper = palavra_limpa.upper()

            if palavra_upper in siglas:
                resultado.append(palavra_upper)
                continue

            if (
                indice > 0
                and palavra_limpa.lower() in palavras_minusculas
            ):
                resultado.append(
                    palavra_limpa.lower()
                )
                continue

            resultado.append(
                palavra_limpa.lower().capitalize()
            )

        return " ".join(resultado)

    programa_1 = formatar_nome_programa(programa_1)
    programa_2 = formatar_nome_programa(programa_2)
    programa_3 = formatar_nome_programa(programa_3)

    # ======================================================
    # RETÂNGULO EXTERNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
    )

    # ======================================================
    # ÍCONE DO ALVO
    # ======================================================

    caminho_icone = (
        ASSETS_CARAVANA
        / "icone_alvo.png"
    )

    caminho_icone = _recortar_icone_transparente(
        caminho=caminho_icone,
        limite_alpha=20,
        margem=1,
    )

    diametro_icone = pol(0.48)

    imagem_icone = adicionar_imagem(
        slide=slide,
        caminho=caminho_icone,
        esquerda=0,
        topo=0,
        altura=diametro_icone,
    )

    if imagem_icone is not None:
        area_esquerda = esquerda + pol(0.18)
        area_topo = topo + pol(0.05)
        area_largura = pol(0.50)
        area_altura = pol(0.48)

        imagem_icone.left = int(
            area_esquerda
            + (
                area_largura
                - imagem_icone.width
            )
            / 2
        )

        imagem_icone.top = int(
            area_topo
            + (
                area_altura
                - imagem_icone.height
            )
            / 2
        )

    # ======================================================
    # TEXTO EXECUTIVO
    # ======================================================

    texto_com_runs(
        slide=slide,
        runs=[
            {
                "texto": (
                    f"A Região {nome_regiao.title()} possui metas "
                    f"robustas para {ano}, com destaque para "
                ),
                "cor": AZUL_TEXTO,
                "tamanho": 15,
            },
            {
                "texto": programa_1,
                "cor": AZUL_MATRICULAS,
                "negrito": True,
                "tamanho": 15,
            },
            {
                "texto": ", ",
                "cor": AZUL_TEXTO,
                "tamanho": 15,
            },
            {
                "texto": programa_2,
                "cor": AZUL_MATRICULAS,
                "negrito": True,
                "tamanho": 15,
            },
            {
                "texto": " e ",
                "cor": AZUL_TEXTO,
                "tamanho": 15,
            },
            {
                "texto": programa_3,
                "cor": RGBColor(54, 139, 15),
                "negrito": True,
                "tamanho": 15,
            },
            {
                "texto": (
                    ", forte presença em "
                ),
                "cor": AZUL_TEXTO,
                "tamanho": 15,
            },
            {
                "texto": "Gratuidade Regimental",
                "cor": AZUL_MATRICULAS,
                "negrito": True,
                "tamanho": 15,
            },
            {
                "texto": (
                    " e diversificação do portfólio de programas."
                ),
                "cor": AZUL_TEXTO,
                "tamanho": 15,
            },
        ],
        esquerda=esquerda + pol(0.82),
        topo=topo + pol(0.045),
        largura=largura - pol(1.00),
        altura=altura - pol(0.09),
        tamanho_padrao=15,
        vertical=MSO_ANCHOR.MIDDLE,
    )

def bloco_destaques_subregiao(
    slide,
    *,
    nome_subregiao: str,
    ano: int,
    programas: list[dict] | None = None,
    receita_total: str = "R$ 0,00",
) -> None:
    """
    Cria o bloco Destaques abaixo dos gráficos de
    Matrículas e Hora-Aluno.
    """

    programas = [
        programa
        for programa in (programas or [])
        if str(
            programa.get(
                "programa",
                "",
            )
        ).strip()
    ]

    nome_subregiao = str(
        nome_subregiao or ""
    ).strip().title()

    # ======================================================
    # FUNÇÕES DE FORMATAÇÃO
    # ======================================================

    def formatar_inteiro(valor) -> str:
        return (
            f"{float(valor or 0):,.0f}"
            .replace(",", ".")
        )

    def formatar_decimal(valor) -> str:
        return (
            f"{float(valor or 0):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def formatar_percentual(valor) -> str:
        return (
            f"{float(valor or 0):.2f}%"
            .replace(".", ",")
        )

    def formatar_nome_programa(nome: str) -> str:
        palavras_minusculas = {
            "a",
            "as",
            "o",
            "os",
            "de",
            "da",
            "das",
            "do",
            "dos",
            "e",
            "em",
            "para",
            "por",
        }

        siglas = {
            "RS",
            "EAD",
            "SENAI",
            "SESI",
            "IEL",
            "EJA",
            "NEJ",
            "GR",
            "GNR",
        }

        resultado = []

        for indice, palavra in enumerate(
            str(nome or "").strip().split()
        ):
            palavra_upper = palavra.upper()

            if palavra_upper in siglas:
                resultado.append(palavra_upper)
            elif (
                indice > 0
                and palavra.lower()
                in palavras_minusculas
            ):
                resultado.append(
                    palavra.lower()
                )
            else:
                resultado.append(
                    palavra.lower().capitalize()
                )

        return " ".join(resultado)

    # ======================================================
    # CÁLCULO DOS DESTAQUES
    # ======================================================

    programas_por_matriculas = sorted(
        programas,
        key=lambda item: float(
            item.get(
                "matriculas",
                0,
            )
            or 0
        ),
        reverse=True,
    )

    programa_1 = (
        programas_por_matriculas[0]
        if programas_por_matriculas
        else {}
    )

    programa_2 = (
        programas_por_matriculas[1]
        if len(programas_por_matriculas) > 1
        else {}
    )

    programa_maior_ha = max(
        programas,
        key=lambda item: float(
            item.get(
                "hora_aluno",
                0,
            )
            or 0
        ),
        default={},
    )

    total_hora_aluno = sum(
        float(
            programa.get(
                "hora_aluno",
                0,
            )
            or 0
        )
        for programa in programas
    )

    hora_aluno_destaque = float(
        programa_maior_ha.get(
            "hora_aluno",
            0,
        )
        or 0
    )

    percentual_hora_aluno = (
        hora_aluno_destaque
        / total_hora_aluno
        * 100
        if total_hora_aluno > 0
        else 0
    )

    nome_programa_1 = formatar_nome_programa(
        programa_1.get(
            "programa",
            "Programa não informado",
        )
    )

    nome_programa_2 = formatar_nome_programa(
        programa_2.get(
            "programa",
            "Programa não informado",
        )
    )

    nome_programa_ha = formatar_nome_programa(
        programa_maior_ha.get(
            "programa",
            "Programa não informado",
        )
    )

    # ======================================================
    # DIMENSÕES
    # ======================================================

    esquerda = pol(0.20)
    topo = pol(5.48)
    largura = pol(6.24)
    # A tabela possui:
    # - altura-base de 4.02;
    # - 3 linhas de cabeçalho;
    # - uma linha por programa;
    # - 1 linha TOTAL.
    #
    # Depois, a linha TOTAL é alterada para 0.36,
    # aumentando a altura efetiva da tabela.
    total_linhas_tabela = 3 + len(programas) + 1

    altura_linha_original = (
        4.02 / total_linhas_tabela
    )

    base_inferior_tabela = (
        2.18
        + 4.02
        - altura_linha_original
        + 0.36
    )

    # A borda inferior do bloco ficará exatamente
    # na mesma linha da borda inferior da tabela.
    altura = pol(
        base_inferior_tabela - 5.48
    )

    # ======================================================
    # DISTRIBUIÇÃO VERTICAL UNIFORME
    # ======================================================

    # Converte a altura efetiva para a unidade-base utilizada
    # pela função pol().
    altura_base = altura / pol(1.0)

    # A mesma margem será aplicada acima do título
    # e abaixo do último destaque.
    margem_vertical = 0.065

    # Cinco faixas:
    # 0 = título;
    # 1 = programas;
    # 2 = maiores programas;
    # 3 = Hora-Aluno;
    # 4 = receita.
    altura_faixa = (
        altura_base
        - margem_vertical * 2
    ) / 5

    centros_verticais = [
        margem_vertical
        + altura_faixa * (indice + 0.5)
        for indice in range(5)
    ]

    centro_titulo = centros_verticais[0]
    centro_programas = centros_verticais[1]
    centro_matriculas = centros_verticais[2]
    centro_hora_aluno = centros_verticais[3]
    centro_receita = centros_verticais[4]

    altura_texto_linha = min(
        0.11,
        altura_faixa * 0.82,
    )

    altura_icone_titulo = 0.13
    altura_texto_titulo = 0.14

    # ======================================================
    # CONTORNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=RGBColor(71, 122, 235),
    )

    # ======================================================
    # TÍTULO
    # ======================================================

    # Ícone oficial do título DESTAQUES.
    caminho_icone_destaques = (
        ASSETS_CARAVANA
        / "icone_estrela_destaque.png"
    )

    caminho_icone_destaques = (
        _recortar_icone_transparente(
            caminho=caminho_icone_destaques,
            limite_alpha=20,
            margem=1,
        )
    )

    icone_destaques = adicionar_imagem(
        slide=slide,
        caminho=caminho_icone_destaques,
        esquerda=esquerda + pol(0.20),

        # Centraliza o ícone na primeira faixa.
        topo=(
            topo
            + pol(centro_titulo)
            - pol(altura_icone_titulo) / 2
        ),

        altura=pol(altura_icone_titulo),
    )

    texto(
        slide=slide,
        texto="DESTAQUES",
        esquerda=esquerda + pol(0.42),

        # Usa exatamente o mesmo centro vertical do ícone.
        topo=(
            topo
            + pol(centro_titulo)
            - pol(altura_texto_titulo) / 2
        ),

        largura=pol(1.50),
        altura=pol(altura_texto_titulo),
        tamanho=9,
        cor=AZUL_MATRICULAS,
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # AUXILIAR PARA OS ÍCONES DAS LINHAS
    # ======================================================

    def adicionar_icone_linha(
        *,
        nome_arquivo: str,
        centro_vertical: float,
        altura_icone: float = 0.14,
        recorte: float = 0.0,
    ) -> None:
        caminho = ASSETS_CARAVANA / nome_arquivo

        caminho = _recortar_icone_transparente(
            caminho=caminho,
            limite_alpha=20,
            margem=1,
        )

        imagem = adicionar_imagem(
            slide=slide,
            caminho=caminho,
            esquerda=esquerda + pol(0.21),
            topo=0,
            altura=pol(altura_icone),
        )

        if imagem is not None:
            if recorte > 0:
                imagem.crop_left = recorte
                imagem.crop_right = recorte
                imagem.crop_top = recorte
                imagem.crop_bottom = recorte

            imagem.top = int(
                topo
                + pol(centro_vertical)
                - imagem.height / 2
            )

    def adicionar_icone_grafico(
        
        centro_vertical: float,
    ) -> None:
        esquerda_icone = esquerda + pol(0.21)

        # Altura visual total menor, para não alcançar
        # o ícone da Receita.
        altura_total = pol(0.10)

        topo_base = (
            topo
            + pol(centro_vertical)
            + altura_total / 2
        )

        largura_barra = pol(0.023)
        intervalo = pol(0.037)

        alturas = [
            pol(0.038),
            pol(0.065),
            pol(0.095),
        ]

        for indice, altura_barra in enumerate(alturas):
            barra = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.RECTANGLE,
                esquerda_icone + intervalo * indice,
                int(topo_base - altura_barra),
                largura_barra,
                altura_barra,
            )

            barra.fill.solid()
            barra.fill.fore_color.rgb = AZUL_MATRICULAS
            barra.line.fill.background()

    # ======================================================
    # POSIÇÕES E DIMENSÕES DOS TEXTOS
    # ======================================================

    esquerda_textos = esquerda + pol(0.52)
    largura_textos = largura - pol(0.68)

    # ======================================================
    # LINHA 1 — TOTAL DE PROGRAMAS
    # ======================================================

    adicionar_icone_linha(
        nome_arquivo="icone_hora_aluno_gr.png",
        centro_vertical=centro_programas,
        altura_icone=0.12,
    )

    texto_com_runs(
        slide=slide,
        runs=[
            {
                "texto": f"{len(programas)} programas ",
                "cor": AZUL_MATRICULAS,
                "negrito": True,
                "tamanho": 9,
            },
            {
                "texto": (
                    "compõem o portfólio da "
                    f"sub-região {nome_subregiao}."
                ),
                "cor": AZUL_TEXTO,
                "tamanho": 9,
            },
        ],
        esquerda=esquerda_textos,
        topo=(
            topo
            + pol(centro_programas)
            - pol(altura_texto_linha) / 2
        ),
        largura=largura_textos,
        altura=pol(altura_texto_linha),
        tamanho_padrao=9,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # LINHA 2 — DOIS MAIORES PROGRAMAS EM MATRÍCULAS
    # ======================================================

    adicionar_icone_linha(
        nome_arquivo="icone_matriculas.png",
        centro_vertical=centro_matriculas,
        altura_icone=0.12,
    )

    texto_com_runs(
        slide=slide,
        runs=[
            {
                "texto": "Destaque para ",
                "cor": AZUL_TEXTO,
                "tamanho": 9,
            },
            {
                "texto": nome_programa_1,
                "cor": AZUL_MATRICULAS,
                "negrito": True,
                "tamanho": 9,
            },
            {
                "texto": (
                    f" ({formatar_inteiro(programa_1.get('matriculas', 0))} "
                    "matrículas) e "
                ),
                "cor": AZUL_TEXTO,
                "tamanho": 9,
            },
            {
                "texto": nome_programa_2,
                "cor": AZUL_MATRICULAS,
                "negrito": True,
                "tamanho": 9,
            },
            {
                "texto": (
                    f" ({formatar_inteiro(programa_2.get('matriculas', 0))} "
                    "matrículas)."
                ),
                "cor": AZUL_TEXTO,
                "tamanho": 9,
            },
        ],
        esquerda=esquerda_textos,
        topo=(
            topo
            + pol(centro_matriculas)
            - pol(altura_texto_linha) / 2
        ),
        largura=largura_textos,
        altura=pol(altura_texto_linha),
        tamanho_padrao=9,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # LINHA 3 — MAIOR CONCENTRAÇÃO DE HORA-ALUNO
    # ======================================================

    adicionar_icone_grafico(
        centro_vertical=centro_hora_aluno,
    )

    texto_com_runs(
        slide=slide,
        runs=[
            {
                "texto": "A maior concentração da Hora-Aluno está em ",
                "cor": AZUL_TEXTO,
                "tamanho": 9,
            },
            {
                "texto": nome_programa_ha,
                "cor": AZUL_MATRICULAS,
                "negrito": True,
                "tamanho": 9,
            },
            {
                "texto": (
                    f" ({formatar_decimal(hora_aluno_destaque)}"
                    f" – {formatar_percentual(percentual_hora_aluno)})."
                ),
                "cor": AZUL_TEXTO,
                "tamanho": 9,
            },
        ],
        esquerda=esquerda_textos,
        topo=(
            topo
            + pol(centro_hora_aluno)
            - pol(altura_texto_linha) / 2
        ),
        largura=largura_textos,
        altura=pol(altura_texto_linha),
        tamanho_padrao=9,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # LINHA 4 — RECEITA
    # ======================================================

    adicionar_icone_linha(
        nome_arquivo="icone_receita.png",
        centro_vertical=centro_receita,
        altura_icone=0.12,
        recorte=0.12,
    )

    texto_com_runs(
        slide=slide,
        runs=[
            {
                "texto": "Meta financeira prevista de ",
                "cor": AZUL_TEXTO,
                "tamanho": 9,
            },
            {
                "texto": str(receita_total),
                "cor": VERDE_RECEITA,
                "negrito": True,
                "tamanho": 9,
            },
            {
                "texto": ".",
                "cor": AZUL_TEXTO,
                "tamanho": 9,
            },
        ],
        esquerda=esquerda_textos,
        topo=(
            topo
            + pol(centro_receita)
            - pol(altura_texto_linha) / 2
        ),
        largura=largura_textos,
        altura=pol(altura_texto_linha),
        tamanho_padrao=9,
        vertical=MSO_ANCHOR.MIDDLE,
    )

def tabela_metas_programas_subregiao(
    slide,
    *,
    ano: int,
    programas: list[dict] | None = None,
) -> None:
    """
    Cria a tabela de metas por programa da sub-região.
    """

    programas = [
        programa
        for programa in (programas or [])
        if str(
            programa.get(
                "programa",
                "",
            )
        ).strip()
    ]

    programas = sorted(
        programas,
        key=lambda item: str(
            item.get(
                "programa",
                "",
            )
        ).strip().casefold(),
    )

    esquerda = pol(6.68)
    topo = pol(2.18)
    largura = pol(6.45)
    altura = pol(4.02)

    colunas = 13

    # Três linhas de cabeçalho:
    # 0 = título geral;
    # 1 = grupos;
    # 2 = subcolunas.
    linhas_cabecalho = 3

    # Uma linha final para o total.
    total_linhas = (
        linhas_cabecalho
        + len(programas)
        + 1
    )

    shape_tabela = slide.shapes.add_table(
        total_linhas,
        colunas,
        esquerda,
        topo,
        largura,
        altura,
    )

    tabela = shape_tabela.table

    # ======================================================
    # LARGURA DAS COLUNAS
    # ======================================================

    larguras_base = [
        1.48,  # Programa — reduzida
        0.62,  # Matrículas
        0.88,  # Hora-Aluno — ampliada
        0.76,  # Receita

        0.36,  # GR MAT
        0.65,  # GR HA — ampliada
        0.40,  # GR %

        0.36,  # GNR MAT
        0.65,  # GNR HA — ampliada
        0.40,  # GNR %

        0.36,  # PG MAT
        0.65,  # PG HA — ampliada
        0.40,  # PG %
    ]

    soma_larguras = sum(larguras_base)

    for indice, largura_base in enumerate(
        larguras_base
    ):
        tabela.columns[indice].width = int(
            largura
            * largura_base
            / soma_larguras
        )

    # ======================================================
    # FUNÇÕES INTERNAS
    # ======================================================

    def formatar_inteiro(valor) -> str:
        return (
            f"{float(valor or 0):,.0f}"
            .replace(",", ".")
        )

    def formatar_decimal(valor) -> str:
        return (
            f"{float(valor or 0):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def formatar_receita(valor) -> str:
        return (
            f"R$ {float(valor or 0):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def formatar_percentual(valor) -> str:
        return (
            f"{float(valor or 0):,.2f}%"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def configurar_celula(
        celula,
        *,
        texto_celula: str,
        fundo=BRANCO,
        cor=AZUL_TEXTO,
        tamanho=7.5,
        negrito=False,
        alinhamento=PP_ALIGN.CENTER,
        quebra_linha=True,
    ) -> None:
        celula.fill.solid()
        celula.fill.fore_color.rgb = fundo

        celula.margin_left = Pt(2)
        celula.margin_right = Pt(2)
        celula.margin_top = Pt(1)
        celula.margin_bottom = Pt(1)

        # O alinhamento vertical de uma célula deve ser aplicado
        # diretamente na célula, e não apenas no text_frame.
        celula.vertical_anchor = MSO_ANCHOR.MIDDLE

        frame = celula.text_frame
        frame.clear()
        frame.word_wrap = quebra_linha
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE

        paragrafo = frame.paragraphs[0]
        paragrafo.alignment = alinhamento
        paragrafo.space_before = Pt(0)
        paragrafo.space_after = Pt(0)

        run = paragrafo.add_run()
        run.text = str(texto_celula)
        run.font.name = "Arial"
        run.font.size = Pt(tamanho)
        run.font.bold = negrito
        run.font.color.rgb = cor

    # ======================================================
    # CABEÇALHO PRINCIPAL
    # ======================================================

    celula_titulo = tabela.cell(0, 0)

    celula_titulo.merge(
        tabela.cell(
            0,
            colunas - 1,
        )
    )

    configurar_celula(
        celula_titulo,
        texto_celula=(
            f"METAS {ano} POR PROGRAMA"
        ),
        fundo=AZUL_MATRICULAS,
        cor=BRANCO,
        tamanho=13,
        negrito=True,
    )

    # ======================================================
    # CABEÇALHOS FIXOS
    # ======================================================

    cabecalhos_fixos = [
        "PROGRAMA",
        "MATRÍCULAS",
        "HORA-\nALUNO",
        "RECEITA",
    ]

    for coluna, cabecalho in enumerate(
        cabecalhos_fixos
    ):
        celula = tabela.cell(1, coluna)

        celula.merge(
            tabela.cell(2, coluna)
        )

        configurar_celula(
            celula,
            texto_celula=cabecalho,
            fundo=BRANCO,
            cor=AZUL_MATRICULAS,
            tamanho=7.5,
            negrito=True,
        )

    # ======================================================
    # GRUPOS GR, GNR E PG
    # ======================================================

    grupos = [
        (
            "GR",
            4,
            6,
            AZUL_MATRICULAS,
        ),
        (
            "GNR",
            7,
            9,
            AZUL_HORA_ALUNO,
        ),
        (
            "PG",
            10,
            12,
            RGBColor(54, 139, 15),
        ),
    ]

    for nome, inicio, fim, cor_grupo in grupos:
        celula = tabela.cell(1, inicio)
        celula.merge(tabela.cell(1, fim))

        configurar_celula(
            celula,
            texto_celula="",
            fundo=cor_grupo,
            cor=BRANCO,
            tamanho=9,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            quebra_linha=False,
        )

        grupo_esquerda = esquerda + sum(
            tabela.columns[i].width
            for i in range(inicio)
        )

        grupo_largura = sum(
            tabela.columns[i].width
            for i in range(inicio, fim + 1)
        )

        texto(
            slide=slide,
            texto=nome,
            esquerda=grupo_esquerda,
            topo=topo + tabela.rows[0].height,
            largura=grupo_largura,
            altura=tabela.rows[1].height,
            tamanho=9,
            cor=BRANCO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        for coluna, rotulo in zip(
            range(inicio, fim + 1),
            ["MAT", "HA", "% MAT"],
        ):
            configurar_celula(
                tabela.cell(2, coluna),
                texto_celula=rotulo,
                fundo=BRANCO,
                cor=AZUL_MATRICULAS,
                tamanho=7,
                negrito=True,
                alinhamento=PP_ALIGN.CENTER,
                quebra_linha=False,
            )

    # ======================================================
    # LINHAS DOS PROGRAMAS
    # ======================================================

    totais = {
        "matriculas": 0,
        "hora_aluno": 0,
        "receita": 0,
        "gr_matriculas": 0,
        "gr_hora_aluno": 0,
        "gnr_matriculas": 0,
        "gnr_hora_aluno": 0,
        "pg_matriculas": 0,
        "pg_hora_aluno": 0,
    }

    for indice, programa in enumerate(programas):
        linha = linhas_cabecalho + indice

        gr = programa.get("gr", {})
        gnr = programa.get("gnr", {})
        pg = programa.get("pg", {})

        valores = [
            programa.get(
                "programa",
                "Programa não informado",
            ),
            formatar_inteiro(
                programa.get("matriculas", 0)
            ),
            formatar_decimal(
                programa.get("hora_aluno", 0)
            ),
            formatar_receita(
                programa.get("receita", 0)
            ),

            formatar_inteiro(
                gr.get("matriculas", 0)
            ),
            formatar_decimal(
                gr.get("hora_aluno", 0)
            ),
            formatar_percentual(
                gr.get("percentual", 0)
            ),

            formatar_inteiro(
                gnr.get("matriculas", 0)
            ),
            formatar_decimal(
                gnr.get("hora_aluno", 0)
            ),
            formatar_percentual(
                gnr.get("percentual", 0)
            ),

            formatar_inteiro(
                pg.get("matriculas", 0)
            ),
            formatar_decimal(
                pg.get("hora_aluno", 0)
            ),
            formatar_percentual(
                pg.get("percentual", 0)
            ),
        ]

        for coluna, valor in enumerate(valores):
            # As colunas de Hora-Aluno recebem fonte um pouco menor,
            # mas não podem quebrar em duas linhas.
            if coluna in {2, 5, 8, 11}:
                tamanho_celula = 6.0
            elif coluna == 3:
                tamanho_celula = 6.1
            else:
                tamanho_celula = 6.7

            configurar_celula(
                tabela.cell(linha, coluna),
                texto_celula=valor,
                fundo=BRANCO,
                cor=AZUL_TEXTO,
                tamanho=tamanho_celula,
                negrito=True,
                alinhamento=(
                    PP_ALIGN.LEFT
                    if coluna == 0
                    else PP_ALIGN.CENTER
                ),

                # Somente o nome do programa pode quebrar.
                quebra_linha=(
                    coluna == 0
                ),
            )

        totais["matriculas"] += float(
            programa.get("matriculas", 0)
            or 0
        )

        totais["hora_aluno"] += float(
            programa.get("hora_aluno", 0)
            or 0
        )

        totais["receita"] += float(
            programa.get("receita", 0)
            or 0
        )

        totais["gr_matriculas"] += float(
            gr.get("matriculas", 0)
            or 0
        )

        totais["gr_hora_aluno"] += float(
            gr.get("hora_aluno", 0)
            or 0
        )

        totais["gnr_matriculas"] += float(
            gnr.get("matriculas", 0)
            or 0
        )

        totais["gnr_hora_aluno"] += float(
            gnr.get("hora_aluno", 0)
            or 0
        )

        totais["pg_matriculas"] += float(
            pg.get("matriculas", 0)
            or 0
        )

        totais["pg_hora_aluno"] += float(
            pg.get("hora_aluno", 0)
            or 0
        )

    # ======================================================
    # TOTAL
    # ======================================================

    linha_total = total_linhas - 1

    total_matriculas = totais["matriculas"]

    valores_total = [
        "TOTAL",
        formatar_inteiro(
            totais["matriculas"]
        ),
        formatar_decimal(
            totais["hora_aluno"]
        ),
        formatar_receita(
            totais["receita"]
        ),

        formatar_inteiro(
            totais["gr_matriculas"]
        ),
        formatar_decimal(
            totais["gr_hora_aluno"]
        ),
        formatar_percentual(
            (
                totais["gr_matriculas"]
                / total_matriculas
                * 100
            )
            if total_matriculas > 0
            else 0
        ),

        formatar_inteiro(
            totais["gnr_matriculas"]
        ),
        formatar_decimal(
            totais["gnr_hora_aluno"]
        ),
        formatar_percentual(
            (
                totais["gnr_matriculas"]
                / total_matriculas
                * 100
            )
            if total_matriculas > 0
            else 0
        ),

        formatar_inteiro(
            totais["pg_matriculas"]
        ),
        formatar_decimal(
            totais["pg_hora_aluno"]
        ),
        formatar_percentual(
            (
                totais["pg_matriculas"]
                / total_matriculas
                * 100
            )
            if total_matriculas > 0
            else 0
        ),
    ]

    tabela.rows[linha_total].height = pol(0.36)

    for coluna, valor in enumerate(valores_total):
        if coluna in {2, 5, 8, 11}:
            tamanho_total = 5.8
        elif coluna == 3:
            tamanho_total = 5.9
        else:
            tamanho_total = 6.8

        celula_total = tabela.cell(
            linha_total,
            coluna,
        )

        configurar_celula(
            celula_total,
            texto_celula=valor,
            fundo=AZUL_MATRICULAS,
            cor=BRANCO,
            tamanho=tamanho_total,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            quebra_linha=False,
        )

        # Remove qualquer deslocamento provocado pelas margens.
        celula_total.margin_left = 0
        celula_total.margin_right = 0
        celula_total.margin_top = 0
        celula_total.margin_bottom = 0

        # Centralização vertical própria para células de tabela.
        celula_total.vertical_anchor = (
            MSO_ANCHOR.MIDDLE
        )

        frame_total = celula_total.text_frame
        frame_total.vertical_anchor = (
            MSO_ANCHOR.MIDDLE
        )

        for paragrafo in frame_total.paragraphs:
            paragrafo.alignment = PP_ALIGN.CENTER
            paragrafo.level = 0
            paragrafo.space_before = Pt(0)
            paragrafo.space_after = Pt(0)
            paragrafo.line_spacing = 1

def rodape_subregiao_executivo(
    slide,
    *,
    nome_subregiao: str,
    ano: int,
    programas: list[dict] | None = None,
    data_atualizacao: str = "",
) -> None:
    """
    Cria o rodapé dos slides executivos das sub-regiões.

    Estrutura:
    1. Síntese executiva da sub-região;
    2. Fontes dos dados;
    3. Legenda de financiamento.
    """

    programas = [
        programa
        for programa in (programas or [])
        if str(
            programa.get(
                "programa",
                "",
            )
        ).strip()
    ]

    nome_subregiao = str(
        nome_subregiao or ""
    ).strip().title()

    # ======================================================
    # TRATAMENTO DOS PROGRAMAS DE DESTAQUE
    # ======================================================

    programas_por_matriculas = sorted(
        programas,
        key=lambda item: float(
            item.get(
                "matriculas",
                0,
            )
            or 0
        ),
        reverse=True,
    )

    programa_1 = (
        programas_por_matriculas[0]
        if programas_por_matriculas
        else {}
    )

    programa_2 = (
        programas_por_matriculas[1]
        if len(programas_por_matriculas) > 1
        else {}
    )

    # ======================================================
    # DOIS PROGRAMAS COM MAIOR RECEITA
    # ======================================================

    programas_por_receita = sorted(
        programas,
        key=lambda item: float(
            item.get(
                "receita",
                0,
            )
            or 0
        ),
        reverse=True,
    )

    programa_receita_1 = (
        programas_por_receita[0]
        if programas_por_receita
        else {}
    )

    programa_receita_2 = (
        programas_por_receita[1]
        if len(programas_por_receita) > 1
        else {}
    )

    def formatar_nome_programa(nome: str) -> str:
        palavras_minusculas = {
            "a",
            "as",
            "o",
            "os",
            "de",
            "da",
            "das",
            "do",
            "dos",
            "e",
            "em",
            "para",
            "por",
        }

        siglas = {
            "RS",
            "EAD",
            "SENAI",
            "SESI",
            "IEL",
            "EJA",
            "NEJ",
            "GR",
            "GNR",
        }

        resultado = []

        for indice, palavra in enumerate(
            str(nome or "").strip().split()
        ):
            palavra_limpa = palavra.strip()
            palavra_upper = palavra_limpa.upper()

            if palavra_upper in siglas:
                resultado.append(palavra_upper)

            elif (
                indice > 0
                and palavra_limpa.lower()
                in palavras_minusculas
            ):
                resultado.append(
                    palavra_limpa.lower()
                )

            else:
                resultado.append(
                    palavra_limpa.lower().capitalize()
                )

        return " ".join(resultado)

    nome_programa_1 = formatar_nome_programa(
        programa_1.get(
            "programa",
            "Programa não informado",
        )
    )

    nome_programa_2 = formatar_nome_programa(
        programa_2.get(
            "programa",
            "Programa não informado",
        )
    )

    nome_programa_receita_1 = formatar_nome_programa(
        programa_receita_1.get(
            "programa",
            "Programa não informado",
        )
    )

    nome_programa_receita_2 = formatar_nome_programa(
        programa_receita_2.get(
            "programa",
            "Programa não informado",
        )
    )

    # ======================================================
    # DIMENSÕES DO RODAPÉ
    # ======================================================

    topo = pol(6.55)
    altura = pol(0.95)

    retangulo(
        slide=slide,
        esquerda=0,
        topo=topo,
        largura=pol(13.333),
        altura=altura,
        cor=AZUL_ESCURO,
        raio=False,
    )

    # ======================================================
    # FUNÇÃO AUXILIAR — DIVISOR
    # ======================================================

    def adicionar_divisor(
        posicao_x: float,
    ) -> None:
        divisor = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            pol(posicao_x),
            topo + pol(0.12),
            pol(0.012),
            altura - pol(0.24),
        )

        divisor.fill.solid()
        divisor.fill.fore_color.rgb = BRANCO
        divisor.line.fill.background()

    # ======================================================
    # BLOCO 1 — SÍNTESE EXECUTIVA
    # ======================================================

    diametro_circulo = pol(0.62)
    esquerda_circulo = pol(0.27)
    topo_circulo = topo + pol(0.16)

    circulo = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.OVAL,
        esquerda_circulo,
        topo_circulo,
        diametro_circulo,
        diametro_circulo,
    )

    circulo.fill.background()
    circulo.line.color.rgb = BRANCO
    circulo.line.width = Pt(1.5)

    caminho_alvo = (
        ASSETS_CARAVANA
        / "icone_alvo.png"
    )

    caminho_alvo = _recortar_icone_transparente(
        caminho=caminho_alvo,
        limite_alpha=20,
        margem=1,
    )

    imagem_alvo = adicionar_imagem(
        slide=slide,
        caminho=caminho_alvo,
        esquerda=0,
        topo=0,
        altura=pol(0.47),
    )

    if imagem_alvo is not None:
        imagem_alvo.left = int(
            esquerda_circulo
            + (
                diametro_circulo
                - imagem_alvo.width
            )
            / 2
        )

        imagem_alvo.top = int(
            topo_circulo
            + (
                diametro_circulo
                - imagem_alvo.height
            )
            / 2
        )

    texto_com_runs(
        slide=slide,
        runs=[
            {
                "texto": (
                    f"A sub-região {nome_subregiao} possui metas "
                    f"consistentes para {ano}, com destaque em número de matrícula para os programas "
                ),
                "cor": BRANCO,
                "tamanho": 12,
            },
            {
                "texto": nome_programa_1,
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 12,
            },
            {
                "texto": " e ",
                "cor": BRANCO,
                "tamanho": 12,
            },
            {
                "texto": nome_programa_2,
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 12,
            },
            {
                "texto": (
                    ", mantendo forte participação de "
                ),
                "cor": BRANCO,
                "tamanho": 12,
            },
            {
                "texto": "matrículas pagas",
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 12,
            },
            {
                "texto": " nos programas ",
                "cor": BRANCO,
                "tamanho": 12,
            },
            {
                "texto": nome_programa_receita_1,
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 12,
            },
            {
                "texto": " e ",
                "cor": BRANCO,
                "tamanho": 12,
            },
            {
                "texto": nome_programa_receita_2,
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 12,
            },
            {
                "texto": ".",
                "cor": BRANCO,
                "tamanho": 12,
            },
        ],
        esquerda=pol(1.06),
        topo=topo + pol(0.09),
        largura=pol(4.10),
        altura=altura - pol(0.18),
        tamanho_padrao=12,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    adicionar_divisor(5.38)

    # ======================================================
    # BLOCO 2 — FONTES DOS DADOS
    # ======================================================

    texto(
        slide=slide,
        texto="FONTES DOS DADOS:",
        esquerda=pol(5.57),
        topo=topo + pol(0.14),
        largura=pol(2.00),
        altura=pol(0.19),
        tamanho=12,
        cor=BRANCO,
        negrito=True,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    texto(
        slide=slide,
        texto="Solução Integradora • Cubo Orçamento",
        esquerda=pol(5.57),
        topo=topo + pol(0.39),
        largura=pol(2.24),
        altura=pol(0.18),
        tamanho=11,
        cor=BRANCO,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    texto(
        slide=slide,
        texto=(
            f"Dados atualizados até {data_atualizacao}"
            if data_atualizacao
            else "Dados atualizados conforme a base selecionada"
        ),
        esquerda=pol(5.57),
        topo=topo + pol(0.62),
        largura=pol(2.24),
        altura=pol(0.18),
        tamanho=11,
        cor=BRANCO,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    adicionar_divisor(8.06)

    # ======================================================
    # BLOCO 3 — LEGENDA DE FINANCIAMENTO
    # ======================================================

    texto(
        slide=slide,
        texto="LEGENDA DE FINANCIAMENTO",
        esquerda=pol(8.39),
        topo=topo + pol(0.10),
        largura=pol(3.20),
        altura=pol(0.20),
        tamanho=12,
        cor=BRANCO,
        negrito=True,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    itens_financiamento = [
        {
            "sigla": "GR",
            "descricao": "Gratuidade Regimental",
            "cor": AZUL_MATRICULAS,
            "x": 8.39,
            "largura_descricao": 1.42,
        },
        {
            "sigla": "GNR",
            "descricao": "Gratuidade Não Regimental",
            "cor": AZUL_HORA_ALUNO,
            "x": 10.18,
            "largura_descricao": 1.67,
        },
        {
            "sigla": "PG",
            "descricao": "Pago",
            "cor": RGBColor(54, 139, 15),
            "x": 12.08,
            "largura_descricao": 0.90,
        },
    ]

    for item in itens_financiamento:
        circulo_legenda = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            pol(item["x"]),
            topo + pol(0.36),
            pol(0.18),
            pol(0.18),
        )

        circulo_legenda.fill.solid()
        circulo_legenda.fill.fore_color.rgb = item["cor"]
        circulo_legenda.line.fill.background()

        texto(
            slide=slide,
            texto=item["sigla"],
            esquerda=pol(item["x"] + 0.27),
            topo=topo + pol(0.31),
            largura=pol(0.48),
            altura=pol(0.22),
            tamanho=13,
            cor=BRANCO,
            negrito=True,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        texto(
            slide=slide,
            texto=item["descricao"],
            esquerda=pol(item["x"] + 0.27),
            topo=topo + pol(0.58),
            largura=pol(item["largura_descricao"]),
            altura=pol(0.18),
            tamanho=10,
            cor=BRANCO,
            vertical=MSO_ANCHOR.MIDDLE,
        )

# ==========================================================
# SLIDE STATUS DAS METAS — SUB-REGIÃO
# ==========================================================

def cabecalho_status_subregiao(
    slide,
    *,
    largura_slide,
    nome_subregiao: str,
    ano: int,
    periodo: str = "1º SEMESTRE",
    meses: str = "JAN–JUN",
) -> None:
    """
    Cria o cabeçalho do slide Status das Metas.
    """

    nome_subregiao = str(
        nome_subregiao or ""
    ).strip().upper()

    periodo = str(
        periodo or "1º SEMESTRE"
    ).strip().upper()

    meses = str(
        meses or "JAN–JUN"
    ).strip().upper()

    altura = pol(0.82)

    # Fundo azul.
    retangulo(
        slide=slide,
        esquerda=0,
        topo=0,
        largura=largura_slide,
        altura=altura,
        cor=AZUL_HEADER,
        raio=False,
    )

    # Faixas inclinadas centrais.
    faixas = [
        (6.65, 1.40, RGBColor(2, 47, 111)),
        (7.18, 1.45, RGBColor(3, 73, 158)),
        (7.72, 1.52, RGBColor(0, 120, 205)),
    ]

    for esquerda_faixa, largura_faixa, cor_faixa in faixas:
        faixa = slide.shapes.add_shape(
            MSO_SHAPE.PARALLELOGRAM,
            pol(esquerda_faixa),
            0,
            pol(largura_faixa),
            altura,
        )

        faixa.fill.solid()
        faixa.fill.fore_color.rgb = cor_faixa
        faixa.line.fill.background()

    # Pontilhado decorativo.
    for linha in range(5):
        for coluna in range(15):
            ponto = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.OVAL,
                pol(8.38 + coluna * 0.13),
                pol(0.055 + linha * 0.125),
                pol(0.017),
                pol(0.017),
            )

            ponto.fill.solid()
            ponto.fill.fore_color.rgb = RGBColor(
                0,
                210,
                245,
            )
            ponto.line.fill.background()

    # Título.
    texto(
        slide=slide,
        texto=(
            f"{nome_subregiao} | STATUS DAS METAS"
        ),
        esquerda=pol(0.31),
        topo=pol(0.08),
        largura=pol(6.85),
        altura=pol(0.36),
        tamanho=31,
        cor=BRANCO,
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # Período.
    texto(
        slide=slide,
        texto=(
            f"{periodo} {ano} ({meses})"
        ),
        esquerda=pol(0.31),
        topo=pol(0.45),
        largura=pol(6.80),
        altura=pol(0.23),
        tamanho=18,
        cor=RGBColor(67, 204, 255),
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # Logo SENAI.
    caminho_logo = (
        ASSETS_CARAVANA
        / "senai_branco.png"
    )

    caminho_logo = _remover_margens_transparentes(
        caminho_logo
    )

    logo = adicionar_imagem(
        slide=slide,
        caminho=caminho_logo,
        esquerda=0,
        topo=0,
        largura=pol(1.30),
    )

    if logo is not None:
        logo.left = int(
            largura_slide
            - logo.width
            - pol(0.30)
        )

        logo.top = int(
            (
                altura
                - logo.height
            )
            / 2
        )


def cards_status_subregiao(
    slide,
    *,
    indicadores: dict | None = None,
) -> None:
    """
    Cria os cards superiores de Matrículas,
    Hora-Aluno e Receita.
    """

    indicadores = indicadores or {}

    def numero(valor) -> float:
        try:
            return float(valor or 0)
        except (TypeError, ValueError):
            return 0.0

    def formatar_inteiro(valor) -> str:
        return (
            f"{numero(valor):,.0f}"
            .replace(",", ".")
        )

    def formatar_decimal(valor) -> str:
        return (
            f"{numero(valor):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def formatar_receita(valor) -> str:
        return (
            f"R$ {numero(valor):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def obter_percentual(
        dados_indicador: dict,
    ) -> float:
        percentual = dados_indicador.get(
            "percentual"
        )

        if percentual is not None:
            return numero(percentual)

        meta = numero(
            dados_indicador.get("meta")
        )

        realizado = numero(
            dados_indicador.get("realizado")
        )

        if meta <= 0:
            return 0.0

        return realizado / meta * 100

    def obter_status(
        *,
        percentual: float,
        meta: float,
        realizado: float,
    ) -> tuple[str, RGBColor]:
        if meta <= 0 and realizado <= 0:
            return (
                "Sem movimento",
                RGBColor(180, 180, 180),
            )

        if meta <= 0 and realizado > 0:
            return (
                "Realizado sem meta",
                RGBColor(40, 40, 40),
            )

        if percentual >= 100:
            return (
                "Meta atingida",
                RGBColor(23, 125, 30),
            )

        if percentual >= 75:
            return (
                "No caminho",
                RGBColor(255, 166, 0),
            )

        if percentual >= 51:
            return (
                "Atenção",
                RGBColor(255, 126, 0),
            )

        return (
            "Crítico",
            RGBColor(220, 45, 45),
        )

    configuracoes = [
        {
            "chave": "matriculas",
            "titulo": "MATRÍCULAS",
            "icone": "icone_matriculas.png",
            "icone_radar": "icone_radar_azul.png",
            "cor": AZUL_MATRICULAS,
            "formatador": formatar_inteiro,
        },
        {
            "chave": "hora_aluno",
            "titulo": "HORA-ALUNO",
            "icone": "icone_hora_aluno.png",
            "icone_radar": "icone_radar_azul_marinho.png",
            "cor": AZUL_HORA_ALUNO,
            "formatador": formatar_decimal,
        },
        {
            "chave": "receita",
            "titulo": "RECEITA",
            "icone": "icone_receita.png",
            "icone_radar": "icone_radar_roxo.png",
            "cor": ROXO_GR,
            "formatador": formatar_receita,
        },
    ]

    margem_esquerda = 0.20
    topo = 0.95
    largura_card = 3.25
    intervalo = 0.10
    altura_card = 1.97

    for indice, configuracao in enumerate(
        configuracoes
    ):
        dados_indicador = indicadores.get(
            configuracao["chave"],
            {},
        )

        meta = numero(
            dados_indicador.get("meta")
        )

        realizado = numero(
            dados_indicador.get("realizado")
        )

        percentual = obter_percentual(
            dados_indicador
        )

        texto_status, cor_status = obter_status(
            percentual=percentual,
            meta=meta,
            realizado=realizado,
        )

        formatador = configuracao[
            "formatador"
        ]

        esquerda = pol(
            margem_esquerda
            + indice
            * (
                largura_card
                + intervalo
            )
        )

        topo_card = pol(topo)
        largura = pol(largura_card)
        altura = pol(altura_card)

        # Contorno externo.
        retangulo(
            slide=slide,
            esquerda=esquerda,
            topo=topo_card,
            largura=largura,
            altura=altura,
            cor=BRANCO,
            linha=BORDA_CARD,
        )

        # ======================================================
        # ÍCONE PRINCIPAL DO CARD
        # ======================================================

        area_icone_esquerda = esquerda + pol(0.18)
        area_icone_topo = topo_card + pol(0.12)
        diametro_icone = pol(0.52)

        if configuracao["chave"] == "receita":
            # O PNG atual de Receita possui fundo quadrado.
            # Portanto, desenhamos diretamente um círculo roxo.
            circulo_receita = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.OVAL,
                area_icone_esquerda,
                area_icone_topo,
                diametro_icone,
                diametro_icone,
            )

            circulo_receita.fill.solid()
            circulo_receita.fill.fore_color.rgb = ROXO_GR
            circulo_receita.line.fill.background()

            # Símbolo branco centralizado no círculo.
            texto(
                slide=slide,
                texto="$",
                esquerda=area_icone_esquerda,
                topo=area_icone_topo - pol(0.015),
                largura=diametro_icone,
                altura=diametro_icone,
                tamanho=30,
                cor=BRANCO,
                negrito=False,
                alinhamento=PP_ALIGN.CENTER,
                vertical=MSO_ANCHOR.MIDDLE,
            )

        else:
            caminho_icone = (
                ASSETS_CARAVANA
                / configuracao["icone"]
            )

            caminho_icone = _recortar_icone_transparente(
                caminho=caminho_icone,
                limite_alpha=20,
                margem=1,
            )

            imagem_icone = adicionar_imagem(
                slide=slide,
                caminho=caminho_icone,
                esquerda=area_icone_esquerda,
                topo=area_icone_topo,
                altura=diametro_icone,
            )

        # Título.
        texto(
            slide=slide,
            texto=configuracao["titulo"],
            esquerda=esquerda + pol(0.79),
            topo=topo_card + pol(0.16),
            largura=largura - pol(0.95),
            altura=pol(0.28),
            tamanho=18,
            cor=configuracao["cor"],
            negrito=True,
            alinhamento=PP_ALIGN.LEFT,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        # ======================================================
        # RADAR DE DESEMPENHO
        # ======================================================

        caminho_radar = (
            ASSETS_CARAVANA
            / configuracao["icone_radar"]
        )

        caminho_radar = _recortar_icone_transparente(
            caminho=caminho_radar,
            limite_alpha=20,
            margem=1,
        )

        # ======================================================
        # CENTRO HORIZONTAL DO RADAR E DO PERCENTUAL
        # ======================================================
        #
        # IMPORTANTE:
        # esta variável precisa existir independentemente
        # de a imagem do radar ter sido carregada ou não.
        #
        # Tanto o radar quanto o percentual abaixo dele
        # utilizam exatamente este mesmo centro.
        # ======================================================

        centro_radar_percentual = (
            esquerda
            + largura
            - pol(0.67)
        )

        # A largura visual do radar.
        largura_radar = pol(0.70)

        imagem_radar = adicionar_imagem(
            slide=slide,
            caminho=caminho_radar,
            esquerda=0,
            topo=0,
            largura=largura_radar,
        )

        if imagem_radar is not None:
            imagem_radar.left = int(
                centro_radar_percentual
                - imagem_radar.width / 2
            )

            imagem_radar.top = int(
                topo_card + pol(0.17)
            )

        # ======================================================
        # PERCENTUAL
        # ======================================================

        largura_percentual = pol(0.70)

        texto(
            slide=slide,
            texto=(
                f"{percentual:.2f}%"
                .replace(".", ",")
            ),

            # Usa o mesmo centro horizontal do radar.
            esquerda=int(
                centro_radar_percentual
                - largura_percentual / 2
            ),

            topo=topo_card + pol(0.72),
            largura=largura_percentual,
            altura=pol(0.30),
            tamanho=19,
            cor=configuracao["cor"],
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        # Meta.
        texto(
            slide=slide,
            texto="Meta",
            esquerda=esquerda + pol(0.17),
            topo=topo_card + pol(0.96),
            largura=pol(0.72),
            altura=pol(0.18),
            tamanho=11,
            cor=PRETO,
            negrito=True,
        )

        texto(
            slide=slide,
            texto=formatador(meta),
            esquerda=esquerda + pol(0.17),
            topo=topo_card + pol(1.20),
            largura=pol(0.96),
            altura=pol(0.31),
            tamanho=17,
            cor=PRETO,
            negrito=True,
        )

        # Divisor entre meta e realizado.
        divisor = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            esquerda + pol(1.23),
            topo_card + pol(0.97),
            pol(0.012),
            pol(0.56),
        )

        divisor.fill.solid()
        divisor.fill.fore_color.rgb = RGBColor(
            210,
            210,
            210,
        )
        divisor.line.fill.background()

        # Realizado.
        texto(
            slide=slide,
            texto="Realizado",
            esquerda=esquerda + pol(1.40),
            topo=topo_card + pol(0.96),
            largura=pol(0.82),
            altura=pol(0.18),
            tamanho=11,
            cor=PRETO,
            negrito=True,
        )

        texto(
            slide=slide,
            texto=formatador(realizado),
            esquerda=esquerda + pol(1.40),
            topo=topo_card + pol(1.20),
            largura=pol(1.13),
            altura=pol(0.31),
            tamanho=16,
            cor=configuracao["cor"],
            negrito=True,
        )

        # Selo de status.
        largura_status = pol(1.25)
        esquerda_status = (
            esquerda
            + largura
            - largura_status
            - pol(0.16)
        )

        topo_status = (
            topo_card
            + pol(1.56)
        )

        retangulo(
            slide=slide,
            esquerda=esquerda_status,
            topo=topo_status,
            largura=largura_status,
            altura=pol(0.31),
            cor=cor_status,
            raio=True,
        )

        # Símbolo do status.
        circulo_status = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            esquerda_status + pol(0.08),
            topo_status + pol(0.075),
            pol(0.16),
            pol(0.16),
        )

        circulo_status.fill.solid()
        circulo_status.fill.fore_color.rgb = BRANCO
        circulo_status.line.fill.background()

        texto(
            slide=slide,
            texto=(
                "✓"
                if percentual >= 100
                else "!"
            ),
            esquerda=esquerda_status + pol(0.08),
            topo=topo_status + pol(0.057),
            largura=pol(0.16),
            altura=pol(0.18),
            tamanho=9,
            cor=cor_status,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        texto(
            slide=slide,
            texto=texto_status,
            esquerda=esquerda_status + pol(0.30),
            topo=topo_status + pol(0.045),
            largura=largura_status - pol(0.36),
            altura=pol(0.20),
            tamanho=10,
            cor=BRANCO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )


# ==========================================================
# COMPONENTES QUE SERÃO PREENCHIDOS NAS PRÓXIMAS ETAPAS
# ==========================================================

def bloco_desempenho_consolidado(
    slide,
    *,
    indicadores: dict | None = None,
) -> None:
    """
    Cria o bloco lateral de Desempenho Consolidado
    do slide Status das Metas.
    """

    indicadores = indicadores or {}

    # ======================================================
    # FUNÇÕES AUXILIARES
    # ======================================================

    def numero(valor) -> float:
        try:
            return float(valor or 0)
        except (TypeError, ValueError):
            return 0.0

    def obter_percentual(
        dados_indicador: dict,
    ) -> float:
        percentual = dados_indicador.get(
            "percentual"
        )

        if percentual is not None:
            return numero(percentual)

        meta = numero(
            dados_indicador.get("meta")
        )

        realizado = numero(
            dados_indicador.get("realizado")
        )

        if meta <= 0:
            return 0.0

        return realizado / meta * 100

    def formatar_percentual(
        valor: float,
    ) -> str:
        return (
            f"{valor:.2f}%"
            .replace(".", ",")
        )

    def montar_mensagem(
        *,
        nome_indicador: str,
        dados_indicador: dict,
    ) -> tuple[list[dict], RGBColor]:
        meta = numero(
            dados_indicador.get("meta")
        )

        realizado = numero(
            dados_indicador.get("realizado")
        )

        percentual = obter_percentual(
            dados_indicador
        )

        # Meta e realizado zerados.
        if meta <= 0 and realizado <= 0:
            return (
                [
                    {
                        "texto": (
                            f"{nome_indicador} sem movimentação."
                        ),
                        "cor": AZUL_MATRICULAS,
                        "tamanho": 12,
                    },
                ],
                RGBColor(180, 180, 180),
            )

        # Realizado sem meta cadastrada.
        if meta <= 0 and realizado > 0:
            return (
                [
                    {
                        "texto": (
                            f"{nome_indicador} possui realizado "
                            "sem meta cadastrada."
                        ),
                        "cor": AZUL_MATRICULAS,
                        "tamanho": 12,
                    },
                ],
                RGBColor(40, 40, 40),
            )

        diferenca = abs(
            percentual - 100
        )

        diferenca_formatada = (
            formatar_percentual(diferenca)
        )

        # Meta atingida ou superada.
        if percentual >= 100:
            return (
                [
                    {
                        "texto": f"{nome_indicador} superou a meta em ",
                        "cor": AZUL_MATRICULAS,
                        "tamanho": 12,
                    },
                    {
                        "texto": diferenca_formatada,
                        "cor": VERDE_RECEITA,
                        "negrito": True,
                        "tamanho": 12,
                    },
                    {
                        "texto": ".",
                        "cor": AZUL_MATRICULAS,
                        "tamanho": 12,
                    },
                ],
                VERDE_RECEITA,
            )

        # Abaixo da meta.
        cor_destaque = (
            RGBColor(255, 126, 0)
            if percentual >= 51
            else RGBColor(220, 45, 45)
        )

        verbo = (
            "ficam"
            if nome_indicador == "Matrículas"
            else "ficou"
        )

        return (
            [
                {
                    "texto": (
                        f"{nome_indicador} {verbo} "
                    ),
                    "cor": AZUL_MATRICULAS,
                    "tamanho": 12,
                },
                {
                    "texto": diferenca_formatada,
                    "cor": cor_destaque,
                    "negrito": True,
                    "tamanho": 12,
                },
                {
                    "texto": " abaixo da meta.",
                    "cor": AZUL_MATRICULAS,
                    "tamanho": 12,
                },
            ],
            cor_destaque,
        )

    # ======================================================
    # DIMENSÕES
    # ======================================================

    esquerda = pol(10.28)
    topo = pol(0.95)
    largura = pol(2.85)
    altura = pol(2.95)

    # ======================================================
    # CONTORNO EXTERNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
    )

    # ======================================================
    # ÍCONE DO TÍTULO
    # ======================================================

    # O PNG oficial já contém o círculo e o alvo na mesma cor.
    # Portanto, não criamos um segundo círculo no PowerPoint.
    caminho_icone = (
        ASSETS_CARAVANA
        / "icone_alvo_verde.png"
    )

    caminho_icone = _recortar_icone_transparente(
        caminho=caminho_icone,
        limite_alpha=20,
        margem=1,
    )

    diametro_icone = pol(0.48)

    imagem_icone = adicionar_imagem(
        slide=slide,
        caminho=caminho_icone,
        esquerda=0,
        topo=0,
        altura=diametro_icone,
    )

    if imagem_icone is not None:
        area_icone_esquerda = esquerda + pol(0.18)
        area_icone_topo = topo + pol(0.16)
        area_icone_largura = diametro_icone
        area_icone_altura = diametro_icone

        imagem_icone.left = int(
            area_icone_esquerda
            + (
                area_icone_largura
                - imagem_icone.width
            )
            / 2
        )

        imagem_icone.top = int(
            area_icone_topo
            + (
                area_icone_altura
                - imagem_icone.height
            )
            / 2
        )

    # ======================================================
    # TÍTULO
    # ======================================================

    texto(
        slide=slide,
        texto=(
            "DESEMPENHO\n"
            "CONSOLIDADO"
        ),
        esquerda=esquerda + pol(0.78),
        topo=topo + pol(0.12),
        largura=largura - pol(0.94),
        altura=pol(0.55),
        tamanho=17,
        cor=VERDE_RECEITA,
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # LINHAS DOS INDICADORES
    # ======================================================

    configuracoes = [
        {
            "nome": "Matrículas",
            "chave": "matriculas",
        },
        {
            "nome": "Hora-Aluno",
            "chave": "hora_aluno",
        },
        {
            "nome": "Receita",
            "chave": "receita",
        },
    ]

    topo_primeira_linha = 0.88
    intervalo_vertical = 0.70

    for indice, configuracao in enumerate(
        configuracoes
    ):
        dados_indicador = indicadores.get(
            configuracao["chave"],
            {},
        )

        runs_mensagem, cor_status = montar_mensagem(
            nome_indicador=configuracao["nome"],
            dados_indicador=dados_indicador,
        )

        topo_linha = topo + pol(
            topo_primeira_linha
            + indice * intervalo_vertical
        )

        # Ícone circular de status.
        circulo_status = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            esquerda + pol(0.20),
            topo_linha + pol(0.03),
            pol(0.18),
            pol(0.18),
        )

        circulo_status.fill.solid()
        circulo_status.fill.fore_color.rgb = cor_status
        circulo_status.line.fill.background()

        # Símbolo interno.
        percentual = obter_percentual(
            dados_indicador
        )

        meta = numero(
            dados_indicador.get("meta")
        )

        realizado = numero(
            dados_indicador.get("realizado")
        )

        if meta <= 0 and realizado <= 0:
            simbolo = "–"

        elif meta <= 0 and realizado > 0:
            simbolo = "!"

        elif percentual >= 100:
            simbolo = "✓"

        else:
            simbolo = "!"

        texto(
            slide=slide,
            texto=simbolo,
            esquerda=esquerda + pol(0.20),
            topo=topo_linha + pol(0.015),
            largura=pol(0.18),
            altura=pol(0.20),
            tamanho=9,
            cor=BRANCO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        texto_com_runs(
            slide=slide,
            runs=runs_mensagem,
            esquerda=esquerda + pol(0.55),
            topo=topo_linha - pol(0.03),
            largura=largura - pol(0.75),
            altura=pol(0.50),
            tamanho_padrao=12,
            alinhamento=PP_ALIGN.LEFT,
            vertical=MSO_ANCHOR.MIDDLE,
        )

def bloco_fontes_dados_status(
    slide,
    *,
    data_atualizacao: str = "",
) -> None:
    """
    Cria o bloco FONTES DOS DADOS na lateral direita
    do slide Status das Metas.
    """

    esquerda = pol(10.28)
    topo = pol(5.53)
    largura = pol(2.85)
    altura = pol(0.70)

    # ======================================================
    # CARD
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
        raio=True,
    )

    # ======================================================
    # TÍTULO
    # ======================================================

    texto(
        slide=slide,
        texto="FONTES DOS DADOS:",
        esquerda=esquerda + pol(0.18),
        topo=topo + pol(0.12),
        largura=largura - pol(0.36),
        altura=pol(0.18),
        tamanho=13,
        cor=AZUL_MATRICULAS,
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # FONTE
    # ======================================================

    texto(
        slide=slide,
        texto="Solução Integradora • Cubo Orçamento",
        esquerda=esquerda + pol(0.18),
        topo=topo + pol(0.39),
        largura=largura - pol(0.36),
        altura=pol(0.16),
        tamanho=9,
        cor=AZUL_MATRICULAS,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # DATA DE ATUALIZAÇÃO — SOMENTE SE INFORMADA
    # ======================================================

    data_atualizacao = str(
        data_atualizacao or ""
    ).strip()

    if data_atualizacao:
        texto(
            slide=slide,
            texto=f"Dados atualizados até {data_atualizacao}",
            esquerda=esquerda + pol(0.18),
            topo=topo + pol(0.55),
            largura=largura - pol(0.36),
            altura=pol(0.12),
            tamanho=8,
            cor=AZUL_TEXTO,
            alinhamento=PP_ALIGN.LEFT,
            vertical=MSO_ANCHOR.MIDDLE,
        )

def bloco_financiamentos_status(
    slide,
    *,
    distribuicoes: dict | None = None,
) -> None:
    """
    Cria o bloco DESEMPENHO POR FINANCIAMENTO com:

    - Matrículas: GR, GNR e PG;
    - Hora-Aluno: GR, GNR e PG;
    - Receita: GR, GNR e PG.

    Estrutura esperada:

    {
        "matriculas": {
            "gr": {"meta": ..., "realizado": ..., "percentual": ...},
            "gnr": {...},
            "pg": {...},
        },
        "hora_aluno": {...},
        "receita": {...},
    }
    """

    distribuicoes = distribuicoes or {}

    # ======================================================
    # FUNÇÕES AUXILIARES
    # ======================================================

    def numero(valor) -> float:
        try:
            return float(valor or 0)
        except (TypeError, ValueError):
            return 0.0

    def formatar_inteiro(valor) -> str:
        return (
            f"{numero(valor):,.0f}"
            .replace(",", ".")
        )

    def formatar_decimal(valor) -> str:
        return (
            f"{numero(valor):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def formatar_receita(valor) -> str:
        valor_numerico = numero(valor)

        sinal = "- " if valor_numerico < 0 else ""

        valor_absoluto = abs(valor_numerico)

        formatado = (
            f"{valor_absoluto:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

        return f"{sinal}R$ {formatado}"

    def formatar_percentual(valor) -> str:
        return (
            f"{numero(valor):.2f}%"
            .replace(".", ",")
        )

    def calcular_status(
        *,
        meta: float,
        realizado: float,
        percentual: float,
    ) -> tuple[str, RGBColor]:
        """
        Retorna:
        - texto do status;
        - cor do percentual.
        """

        if meta <= 0 and realizado == 0:
            return (
                "Sem movimento",
                RGBColor(150, 150, 150),
            )

        if meta <= 0 and realizado != 0:
            return (
                "Realizado sem meta",
                RGBColor(40, 40, 40),
            )

        if percentual >= 100:
            return (
                "Meta atingida",
                VERDE_RECEITA,
            )

        if percentual >= 75:
            return (
                "No caminho",
                RGBColor(0, 81, 230),
            )

        if percentual >= 51:
            return (
                "Atenção",
                RGBColor(255, 126, 0),
            )

        return (
            "Crítico",
            RGBColor(220, 45, 45),
        )

    # ======================================================
    # DIMENSÕES GERAIS
    # ======================================================

    esquerda_geral = pol(0.20)
    topo_titulo = pol(3.06)

    # O bloco termina antes da coluna lateral.
    largura_total = pol(9.92)

    altura_faixa_titulo = pol(0.30)

    # ======================================================
    # FAIXA: DESEMPENHO POR FINANCIAMENTO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda_geral,
        topo=topo_titulo,
        largura=pol(3.35),
        altura=altura_faixa_titulo,
        cor=AZUL_ESCURO,
        raio=True,
    )

    texto(
        slide=slide,
        texto="DESEMPENHO POR FINANCIAMENTO",
        esquerda=esquerda_geral + pol(0.12),
        topo=topo_titulo + pol(0.025),
        largura=pol(3.10),
        altura=pol(0.23),
        tamanho=14,
        cor=BRANCO,
        negrito=True,
        alinhamento=PP_ALIGN.CENTER,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # Linha horizontal depois do título.
    linha_horizontal = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        esquerda_geral + pol(3.35),
        topo_titulo + pol(0.145),
        largura_total - pol(3.35),
        pol(0.012),
    )

    linha_horizontal.fill.solid()
    linha_horizontal.fill.fore_color.rgb = RGBColor(
        45,
        91,
        230,
    )
    linha_horizontal.line.fill.background()

    # ======================================================
    # CONFIGURAÇÕES DAS TRÊS TABELAS
    # ======================================================

    topo_tabelas = pol(3.40)
    altura_tabela = pol(1.54)

    espaco_tabelas = 0.10
    largura_tabela = 3.24

    configuracoes = [
        {
            "chave": "matriculas",
            "titulo": "MATRÍCULAS",
            "cor": AZUL_MATRICULAS,
            "icone": "icone_matriculas.png",
            "formatador": formatar_inteiro,
        },
        {
            "chave": "hora_aluno",
            "titulo": "HORA-ALUNO",
            "cor": AZUL_HORA_ALUNO,
            "icone": "icone_hora_aluno.png",
            "formatador": formatar_decimal,
        },
        {
            "chave": "receita",
            "titulo": "RECEITA",
            "cor": ROXO_GR,
            "icone": "icone_receita.png",
            "formatador": formatar_receita,
        },
    ]

    # ======================================================
    # FUNÇÃO LOCAL: UMA TABELA
    # ======================================================

    def desenhar_tabela(
        *,
        esquerda,
        configuracao: dict,
    ) -> None:
        chave_indicador = configuracao["chave"]
        dados_indicador = distribuicoes.get(
            chave_indicador,
            {},
        )

        largura = pol(largura_tabela)

        # --------------------------------------------------
        # CONTORNO EXTERNO
        # --------------------------------------------------

        retangulo(
            slide=slide,
            esquerda=esquerda,
            topo=topo_tabelas,
            largura=largura,
            altura=altura_tabela,
            cor=BRANCO,
            linha=BORDA_CARD,
            raio=True,
        )

        # --------------------------------------------------
        # CABEÇALHO COLORIDO
        # --------------------------------------------------

        retangulo(
            slide=slide,
            esquerda=esquerda,
            topo=topo_tabelas,
            largura=largura,
            altura=pol(0.34),
            cor=configuracao["cor"],
            raio=False,
        )

        # Ícone do cabeçalho.
        caminho_icone = (
            ASSETS_CARAVANA
            / configuracao["icone"]
        )

        caminho_icone = _recortar_icone_transparente(
            caminho=caminho_icone,
            limite_alpha=20,
            margem=1,
        )

        if chave_indicador == "receita":
            # Símbolo de receita sem usar o PNG quadrado.
            texto(
                slide=slide,
                texto="$",
                esquerda=esquerda + pol(0.98),
                topo=topo_tabelas + pol(0.015),
                largura=pol(0.23),
                altura=pol(0.28),
                tamanho=18,
                cor=BRANCO,
                alinhamento=PP_ALIGN.CENTER,
                vertical=MSO_ANCHOR.MIDDLE,
            )

            esquerda_titulo = esquerda + pol(1.20)

        else:
            imagem_icone = adicionar_imagem(
                slide=slide,
                caminho=caminho_icone,
                esquerda=esquerda + pol(0.96),
                topo=topo_tabelas + pol(0.055),
                altura=pol(0.22),
            )

            esquerda_titulo = esquerda + pol(1.23)

        texto(
            slide=slide,
            texto=configuracao["titulo"],
            esquerda=esquerda_titulo,
            topo=topo_tabelas + pol(0.035),
            largura=pol(1.20),
            altura=pol(0.25),
            tamanho=15,
            cor=BRANCO,
            negrito=True,
            alinhamento=PP_ALIGN.LEFT,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        # --------------------------------------------------
        # CABEÇALHOS DAS COLUNAS
        # --------------------------------------------------

        topo_cabecalho = topo_tabelas + pol(0.38)

        larguras_colunas = [
            0.65,  # Tipo
            0.78,  # Meta
            0.91,  # Realizado
            0.78,  # % atingido
        ]

        posicoes_x = [0.00]

        for largura_coluna in larguras_colunas[:-1]:
            posicoes_x.append(
                posicoes_x[-1] + largura_coluna
            )

        cabecalhos = [
            "TIPO",
            "META",
            "REALIZADO",
            "% ATINGIDO",
        ]

        for indice, cabecalho in enumerate(cabecalhos):
            texto(
                slide=slide,
                texto=cabecalho,
                esquerda=esquerda + pol(
                    posicoes_x[indice]
                ),
                topo=topo_cabecalho,
                largura=pol(
                    larguras_colunas[indice]
                ),
                altura=pol(0.18),
                tamanho=8,
                cor=AZUL_MATRICULAS,
                negrito=True,
                alinhamento=PP_ALIGN.CENTER,
                vertical=MSO_ANCHOR.MIDDLE,
            )

        # Linha abaixo do cabeçalho.
        linha_cabecalho = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            esquerda + pol(0.06),
            topo_tabelas + pol(0.59),
            largura - pol(0.12),
            pol(0.008),
        )

        linha_cabecalho.fill.solid()
        linha_cabecalho.fill.fore_color.rgb = RGBColor(
            220,
            227,
            238,
        )
        linha_cabecalho.line.fill.background()

        # --------------------------------------------------
        # LINHAS GR, GNR E PG
        # --------------------------------------------------

        grupos = [
            (
                "gr",
                "GR",
                AZUL_MATRICULAS,
            ),
            (
                "gnr",
                "GNR",
                AZUL_HORA_ALUNO,
            ),
            (
                "pg",
                "PG",
                RGBColor(54, 139, 15),
            ),
        ]

        formatador = configuracao["formatador"]

        for indice, (
            chave_grupo,
            nome_grupo,
            cor_grupo,
        ) in enumerate(grupos):

            dados_grupo = dados_indicador.get(
                chave_grupo,
                {},
            )

            meta = numero(
                dados_grupo.get("meta")
            )

            realizado = numero(
                dados_grupo.get("realizado")
            )

            percentual = numero(
                dados_grupo.get("percentual")
            )

            _, cor_percentual = calcular_status(
                meta=meta,
                realizado=realizado,
                percentual=percentual,
            )

            topo_linha = topo_tabelas + pol(
                0.65 + indice * 0.28
            )

            # Marcador de financiamento.
            marcador = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.OVAL,
                esquerda + pol(0.11),
                topo_linha + pol(0.065),
                pol(0.10),
                pol(0.10),
            )

            marcador.fill.solid()
            marcador.fill.fore_color.rgb = cor_grupo
            marcador.line.fill.background()

            texto(
                slide=slide,
                texto=nome_grupo,
                esquerda=esquerda + pol(0.26),
                topo=topo_linha,
                largura=pol(0.36),
                altura=pol(0.22),
                tamanho=11,
                cor=PRETO,
                negrito=True,
                alinhamento=PP_ALIGN.LEFT,
                vertical=MSO_ANCHOR.MIDDLE,
            )

            texto(
                slide=slide,
                texto=formatador(meta),
                esquerda=esquerda + pol(
                    posicoes_x[1]
                ),
                topo=topo_linha,
                largura=pol(
                    larguras_colunas[1]
                ),
                altura=pol(0.22),
                tamanho=10,
                cor=PRETO,
                negrito=True,
                alinhamento=PP_ALIGN.CENTER,
                vertical=MSO_ANCHOR.MIDDLE,
            )

            texto(
                slide=slide,
                texto=formatador(realizado),
                esquerda=esquerda + pol(
                    posicoes_x[2]
                ),
                topo=topo_linha,
                largura=pol(
                    larguras_colunas[2]
                ),
                altura=pol(0.22),
                tamanho=10,
                cor=configuracao["cor"],
                negrito=True,
                alinhamento=PP_ALIGN.CENTER,
                vertical=MSO_ANCHOR.MIDDLE,
            )

            # Meta zero exige texto próprio.
            if meta <= 0 and realizado == 0:
                texto_percentual = "—"

            elif meta <= 0 and realizado != 0:
                texto_percentual = "S/ meta"

            else:
                texto_percentual = formatar_percentual(
                    percentual
                )

            tamanho_percentual = (
                7.5
                if texto_percentual == "S/ meta"
                else 10
            )

            texto(
                slide=slide,
                texto=texto_percentual,
                esquerda=esquerda + pol(
                    posicoes_x[3]
                ),
                topo=topo_linha,
                largura=pol(
                    larguras_colunas[3]
                ),
                altura=pol(0.22),
                tamanho=tamanho_percentual,
                cor=cor_percentual,
                negrito=True,
                alinhamento=PP_ALIGN.CENTER,
                vertical=MSO_ANCHOR.MIDDLE,
            )

    # ======================================================
    # DESENHA AS TRÊS TABELAS
    # ======================================================

    for indice, configuracao in enumerate(
        configuracoes
    ):
        esquerda_tabela = pol(
            0.20
            + indice
            * (
                largura_tabela
                + espaco_tabelas
            )
        )

        desenhar_tabela(
            esquerda=esquerda_tabela,
            configuracao=configuracao,
        )


def tabela_programas_status(
    slide,
    *,
    ano: int,
    programas: list[dict] | None = None,
    periodo_meses: str = "JAN–JUN",
) -> None:
    """
    Cria o bloco DESEMPENHO DOS PRINCIPAIS PROGRAMAS
    no padrão executivo do slide de referência.
    """

    programas = programas or []

    # ======================================================
    # ORDENA PELO % ATINGIDO DE MATRÍCULAS
    # MAIOR → MENOR
    # ======================================================

    def percentual_atingido_programa(item) -> float:
        try:
            dados_matriculas = item.get(
                "matriculas",
                {},
            )

            return float(
                dados_matriculas.get(
                    "percentual",
                    0,
                )
                or 0
            )

        except (TypeError, ValueError):
            return 0.0


    programas_ordenados = sorted(
        programas,
        key=percentual_atingido_programa,
        reverse=True,
    )

    # Exibe somente os seis primeiros
    # depois de ordenar pelo % atingido.
    programas_exibidos = programas_ordenados[:6]

    # ======================================================
    # FUNÇÕES AUXILIARES
    # ======================================================

    def numero(valor) -> float:
        try:
            return float(valor or 0)
        except (TypeError, ValueError):
            return 0.0

    def formatar_inteiro(valor) -> str:
        return (
            f"{numero(valor):,.0f}"
            .replace(",", ".")
        )

    def formatar_percentual(valor) -> str:
        return (
            f"{numero(valor):,.2f}%"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def formatar_nome_programa(nome: str) -> str:
        palavras_minusculas = {
            "a",
            "as",
            "o",
            "os",
            "de",
            "da",
            "das",
            "do",
            "dos",
            "e",
            "em",
            "para",
            "por",
        }

        siglas = {
            "RS",
            "EAD",
            "SENAI",
            "SESI",
            "IEL",
            "EJA",
            "NEJ",
            "GR",
            "GNR",
        }

        resultado = []

        for indice, palavra in enumerate(
            str(nome or "").strip().split()
        ):
            palavra_upper = palavra.upper()

            if palavra_upper in siglas:
                resultado.append(palavra_upper)

            elif (
                indice > 0
                and palavra.lower() in palavras_minusculas
            ):
                resultado.append(palavra.lower())

            else:
                resultado.append(
                    palavra.lower().capitalize()
                )

        return " ".join(resultado)

    def obter_status(
        *,
        meta: float,
        realizado: float,
        percentual: float,
    ) -> tuple[str, RGBColor]:
        if meta <= 0 and realizado <= 0:
            return (
                "Sem movimento",
                RGBColor(170, 170, 170),
            )

        if meta <= 0 and realizado != 0:
            return (
                "Realizado sem meta",
                RGBColor(40, 40, 40),
            )

        if percentual >= 100:
            return (
                "Meta atingida",
                RGBColor(14, 112, 25),
            )

        if percentual >= 75:
            return (
                "No caminho",
                RGBColor(18, 82, 224),
            )

        if percentual >= 51:
            return (
                "Atenção",
                RGBColor(255, 112, 0),
            )

        return (
            "Crítico",
            RGBColor(220, 35, 35),
        )

    # ======================================================
    # DIMENSÕES GERAIS
    # ======================================================

    esquerda = pol(0.20)
    topo = pol(5.03)
    largura = pol(9.92)
    altura = pol(1.60)

    # O bloco termina antes do rodapé, que começa em 6.28.
    base_inferior = topo + altura

    # ======================================================
    # CONTORNO EXTERNO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda,
        topo=topo,
        largura=largura,
        altura=altura,
        cor=BRANCO,
        linha=BORDA_CARD,
        raio=True,
    )

    # ======================================================
    # TÍTULO E SUBTÍTULO
    # ======================================================

    texto(
        slide=slide,
        texto=(
            "DESEMPENHO DOS PRINCIPAIS PROGRAMAS "
            f"({periodo_meses}/{ano})"
        ),
        esquerda=esquerda + pol(0.16),
        topo=topo + pol(0.09),      # antes era 0.035
        largura=largura - pol(0.32),
        altura=pol(0.20),
        tamanho=15,
        cor=RGBColor(18, 63, 215),
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    texto(
        slide=slide,
        texto="Comparativo: Realizado / Meta",
        esquerda=esquerda + pol(0.16),
        topo=topo + pol(0.255),   # antes 0.205
        largura=pol(3.20),
        altura=pol(0.14),
        tamanho=10,
        cor=RGBColor(18, 63, 215),
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # DIMENSÕES DA TABELA MANUAL
    # ======================================================

    topo_cabecalho = topo + pol(0.38)
    altura_cabecalho = pol(0.22)

    topo_linhas = topo_cabecalho + altura_cabecalho
    altura_linha = pol(0.14)

    # Posições das colunas em unidades-base.
    col_programa_x = 0.00
    col_programa_w = 3.45

    col_meta_x = 3.45
    col_meta_w = 0.82

    col_realizado_x = 4.27
    col_realizado_w = 1.02

    col_barra_x = 5.29
    col_barra_w = 2.45

    col_percentual_x = 7.74
    col_percentual_w = 1.10

    col_status_x = 8.84
    col_status_w = 1.08

    # ======================================================
    # CABEÇALHO DA TABELA
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=esquerda + pol(0.08),
        topo=topo_cabecalho,
        largura=largura - pol(0.16),
        altura=altura_cabecalho,
        cor=AZUL_ESCURO,
        raio=False,
    )

    cabecalhos = [
        (
            "PROGRAMA",
            col_programa_x,
            col_programa_w,
        ),
        (
            "META",
            col_meta_x,
            col_meta_w,
        ),
        (
            "REALIZADO",
            col_realizado_x,
            col_realizado_w,
        ),
        (
            "",
            col_barra_x,
            col_barra_w,
        ),
        (
            "% ATINGIDO",
            col_percentual_x,
            col_percentual_w,
        ),
        (
            "STATUS",
            col_status_x,
            col_status_w,
        ),
    ]

    for cabecalho, x, w in cabecalhos:
        texto(
            slide=slide,
            texto=cabecalho,
            esquerda=esquerda + pol(x),
            topo=topo_cabecalho,
            largura=pol(w),
            altura=altura_cabecalho,
            tamanho=10,
            cor=BRANCO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )

    # ======================================================
    # LINHAS DOS PROGRAMAS
    # ======================================================

    for indice, programa in enumerate(
        programas_exibidos
    ):
        dados_matriculas = programa.get(
            "matriculas",
            {},
        )

        meta = numero(
            dados_matriculas.get("meta")
        )

        realizado = numero(
            dados_matriculas.get("realizado")
        )

        percentual = numero(
            dados_matriculas.get("percentual")
        )

        status, cor_status = obter_status(
            meta=meta,
            realizado=realizado,
            percentual=percentual,
        )

        nome_programa = formatar_nome_programa(
            programa.get(
                "programa",
                "Programa não informado",
            )
        )

        topo_linha = (
            topo_linhas
            + altura_linha * indice
        )

        # Fundo alternado.
        cor_fundo_linha = (
            RGBColor(247, 250, 254)
            if indice % 2 == 0
            else BRANCO
        )

        retangulo(
            slide=slide,
            esquerda=esquerda + pol(0.08),
            topo=topo_linha,
            largura=largura - pol(0.16),
            altura=altura_linha,
            cor=cor_fundo_linha,
            raio=False,
        )

        # --------------------------------------------------
        # ÍCONE DO PROGRAMA
        # --------------------------------------------------

        diametro_icone = pol(0.12)

        circulo_programa = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            esquerda + pol(0.18),
            int(
                topo_linha
                + (
                    altura_linha
                    - diametro_icone
                )
                / 2
            ),
            diametro_icone,
            diametro_icone,
        )

        circulo_programa.fill.solid()
        circulo_programa.fill.fore_color.rgb = cor_status
        circulo_programa.line.fill.background()

        # Símbolo interno simples.
        texto(
            slide=slide,
            texto="●",
            esquerda=esquerda + pol(0.18),
            topo=topo_linha,
            largura=diametro_icone,
            altura=altura_linha,
            tamanho=4,
            cor=BRANCO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        # --------------------------------------------------
        # NOME DO PROGRAMA
        # --------------------------------------------------

        texto(
            slide=slide,
            texto=nome_programa.upper(),
            esquerda=esquerda + pol(0.36),
            topo=topo_linha,
            largura=pol(col_programa_w - 0.40),
            altura=altura_linha,
            tamanho=11,
            cor=PRETO,
            negrito=True,
            alinhamento=PP_ALIGN.LEFT,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        # --------------------------------------------------
        # META
        # --------------------------------------------------

        texto(
            slide=slide,
            texto=formatar_inteiro(meta),
            esquerda=esquerda + pol(col_meta_x),
            topo=topo_linha,
            largura=pol(col_meta_w),
            altura=altura_linha,
            tamanho=11,
            cor=PRETO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        # --------------------------------------------------
        # REALIZADO
        # --------------------------------------------------

        texto(
            slide=slide,
            texto=formatar_inteiro(realizado),
            esquerda=esquerda + pol(col_realizado_x),
            topo=topo_linha,
            largura=pol(col_realizado_w),
            altura=altura_linha,
            tamanho=11,
            cor=PRETO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        # --------------------------------------------------
        # BARRA DE DESEMPENHO
        # --------------------------------------------------

        esquerda_barra = (
            esquerda
            + pol(col_barra_x + 0.12)
        )

        largura_barra_total = pol(
            col_barra_w - 0.24
        )

        altura_barra = pol(0.055)

        topo_barra = int(
            topo_linha
            + (
                altura_linha
                - altura_barra
            )
            / 2
        )

        # Fundo cinza da barra.
        retangulo(
            slide=slide,
            esquerda=esquerda_barra,
            topo=topo_barra,
            largura=largura_barra_total,
            altura=altura_barra,
            cor=RGBColor(230, 232, 236),
            raio=True,
        )

        # Preenchimento limitado visualmente a 100%.
        percentual_barra = max(
            0,
            min(
                percentual,
                100,
            ),
        )

        largura_preenchida = int(
            largura_barra_total
            * percentual_barra
            / 100
        )

        if largura_preenchida > 0:
            retangulo(
                slide=slide,
                esquerda=esquerda_barra,
                topo=topo_barra,
                largura=largura_preenchida,
                altura=altura_barra,
                cor=cor_status,
                raio=True,
            )

        # --------------------------------------------------
        # PERCENTUAL
        # --------------------------------------------------

        texto(
            slide=slide,
            texto=formatar_percentual(
                percentual
            ),
            esquerda=esquerda + pol(
                col_percentual_x
            ),
            topo=topo_linha,
            largura=pol(
                col_percentual_w
            ),
            altura=altura_linha,
            tamanho=11,
            cor=PRETO,
            negrito=True,
            alinhamento=PP_ALIGN.CENTER,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        # --------------------------------------------------
        # STATUS
        # --------------------------------------------------

        diametro_status = pol(0.065)

        circulo_status = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            esquerda + pol(col_status_x + 0.10),
            int(
                topo_linha
                + (
                    altura_linha
                    - diametro_status
                )
                / 2
            ),
            diametro_status,
            diametro_status,
        )

        circulo_status.fill.solid()
        circulo_status.fill.fore_color.rgb = cor_status
        circulo_status.line.fill.background()

        texto(
            slide=slide,
            texto=status,
            esquerda=esquerda + pol(
                col_status_x + 0.23
            ),
            topo=topo_linha,
            largura=pol(
                col_status_w - 0.26
            ),
            altura=altura_linha,
            tamanho=10,
            cor=cor_status,
            negrito=False,
            alinhamento=PP_ALIGN.LEFT,
            vertical=MSO_ANCHOR.MIDDLE,
        )


def coluna_lateral_status(
    slide,
    *,
    data_atualizacao: str = "",
) -> None:
    """
    Coluna lateral com legenda de status
    e fontes dos dados.
    """
    return None


def rodape_status_subregiao(
    slide,
    *,
    nome_subregiao: str,
    ano: int,
    indicadores: dict | None = None,
    periodo_titulo: str = "",
    periodo_meses: str = "",
) -> None:
    """
    Cria o rodapé compacto do slide Status das Metas.

    O rodapé começa abaixo do bloco de programas e termina
    exatamente no limite inferior do slide.
    """

    indicadores = indicadores or {}

    # ======================================================
    # FUNÇÕES AUXILIARES
    # ======================================================

    def numero(valor) -> float:
        try:
            return float(valor or 0)
        except (TypeError, ValueError):
            return 0.0

    def percentual_indicador(chave: str) -> float:
        return numero(
            indicadores.get(
                chave,
                {},
            ).get(
                "percentual",
                0,
            )
        )

    # ======================================================
    # TEXTOS
    # ======================================================

    nome_subregiao_formatado = str(
        nome_subregiao or ""
    ).strip().title()

    periodo_titulo = str(
        periodo_titulo or ""
    ).strip()

    periodo_meses = str(
        periodo_meses or ""
    ).strip()

    if periodo_titulo and periodo_meses:
        periodo_formatado = (
            f"{periodo_titulo.lower()} "
            f"({periodo_meses})"
        )

    elif periodo_titulo:
        periodo_formatado = periodo_titulo.lower()

    elif periodo_meses:
        periodo_formatado = periodo_meses

    else:
        periodo_formatado = "período selecionado"

    percentual_matriculas = percentual_indicador(
        "matriculas"
    )

    percentual_hora_aluno = percentual_indicador(
        "hora_aluno"
    )

    percentual_receita = percentual_indicador(
        "receita"
    )

    menor_percentual = min(
        percentual_matriculas,
        percentual_hora_aluno,
        percentual_receita,
    )

    if menor_percentual >= 100:
        texto_situacao = (
            f"A Sub-região {nome_subregiao_formatado} encerra o "
            f"{periodo_formatado} de {ano} com desempenho acima "
            "das metas nos três indicadores: "
        )

    elif menor_percentual >= 90:
        texto_situacao = (
            f"A Sub-região {nome_subregiao_formatado} encerra o "
            f"{periodo_formatado} de {ano} com desempenho acima "
            "de 90% nos três indicadores: "
        )

    elif menor_percentual >= 75:
        texto_situacao = (
            f"A Sub-região {nome_subregiao_formatado} encerra o "
            f"{periodo_formatado} de {ano} com desempenho "
            "consistente nos três indicadores: "
        )

    else:
        texto_situacao = (
            f"A Sub-região {nome_subregiao_formatado} encerra o "
            f"{periodo_formatado} de {ano} com resultados que "
            "exigem atenção nos indicadores: "
        )

    # ======================================================
    # DIMENSÕES DO RODAPÉ
    # ======================================================

    # O bloco de programas termina em aproximadamente 6,63.
    # O rodapé começa em 6,70, deixando um pequeno respiro.
    # 6,70 + 0,80 = 7,50: termina exatamente no fim do slide.
    topo = pol(6.70)
    altura = pol(0.80)
    largura_slide = pol(13.333)

    # ======================================================
    # FUNDO
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=0,
        topo=topo,
        largura=largura_slide,
        altura=altura,
        cor=AZUL_ESCURO,
        raio=False,
    )

    # ======================================================
    # ÍCONE DA TAÇA
    # ======================================================

    caminho_icone = (
        ASSETS_CARAVANA
        / "icone_taca.png"
    )

    caminho_icone = _recortar_icone_transparente(
        caminho=caminho_icone,
        limite_alpha=20,
        margem=1,
    )

    adicionar_imagem(
        slide=slide,
        caminho=caminho_icone,
        esquerda=pol(0.27),
        topo=topo + pol(0.12),
        altura=pol(0.50),
    )

    # ======================================================
    # TEXTO EXECUTIVO
    # ======================================================

    texto_com_runs(
        slide=slide,
        runs=[
            {
                "texto": texto_situacao,
                "cor": BRANCO,
                "tamanho": 11,
            },
            {
                "texto": "matrículas",
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 11,
            },
            {
                "texto": ", ",
                "cor": BRANCO,
                "tamanho": 11,
            },
            {
                "texto": "hora-aluno",
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 11,
            },
            {
                "texto": " e ",
                "cor": BRANCO,
                "tamanho": 11,
            },
            {
                "texto": "receita",
                "cor": RGBColor(214, 66, 226),
                "negrito": True,
                "tamanho": 11,
            },
            {
                "texto": ".",
                "cor": BRANCO,
                "tamanho": 11,
            },
        ],
        esquerda=pol(0.88),
        topo=topo + pol(0.08),
        largura=pol(4.55),
        altura=pol(0.58),
        tamanho_padrao=11,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # DIVISOR
    # ======================================================

    divisor = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        pol(5.58),
        topo + pol(0.08),
        pol(0.010),
        pol(0.62),
    )

    divisor.fill.solid()
    divisor.fill.fore_color.rgb = BRANCO
    divisor.line.fill.background()

    # ======================================================
    # TÍTULO DA LEGENDA
    # ======================================================

    texto(
        slide=slide,
        texto="LEGENDA DE STATUS",
        esquerda=pol(6.08),
        topo=topo + pol(0.04),
        largura=pol(2.10),
        altura=pol(0.15),
        tamanho=10,
        cor=BRANCO,
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # ITENS DA LEGENDA
    # ======================================================

    itens_status = [
        {
            "x": 5.95,
            "cor": RGBColor(17, 128, 34),
            "titulo": "Meta atingida",
            "descricao": "(≥ 100%)",
            "largura": 0.95,
        },
        {
            "x": 7.10,
            "cor": RGBColor(28, 84, 233),
            "titulo": "No caminho",
            "descricao": "(75% – 99,9%)",
            "largura": 0.95,
        },
        {
            "x": 8.25,
            "cor": RGBColor(255, 140, 0),
            "titulo": "Atenção",
            "descricao": "(51% – 74,9%)",
            "largura": 0.85,
        },
        {
            "x": 9.30,
            "cor": RGBColor(224, 32, 32),
            "titulo": "Crítico",
            "descricao": "(< 51%)",
            "largura": 0.80,
        },
        {
            "x": 10.45,
            "cor": RGBColor(205, 205, 205),
            "titulo": "Sem movimento",
            "descricao": "Meta = 0 e\nRealizado = 0",
            "largura": 1.00,
        },
        {
            "x": 11.80,
            "cor": RGBColor(35, 35, 35),
            "titulo": "Realizado sem meta",
            "descricao": "Meta = 0 e\nRealizado > 0",
            "largura": 0.95,
        },
    ]

    for item in itens_status:
        diametro = pol(0.10)

        marcador = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            pol(item["x"]),
            topo + pol(0.27),
            diametro,
            diametro,
        )

        marcador.fill.solid()
        marcador.fill.fore_color.rgb = item["cor"]

        if item["titulo"] == "Realizado sem meta":
            marcador.line.color.rgb = RGBColor(
                110,
                110,
                110,
            )
            marcador.line.width = Pt(0.6)

        else:
            marcador.line.fill.background()

        texto(
            slide=slide,
            texto=item["titulo"],
            esquerda=pol(item["x"] + 0.15),
            topo=topo + pol(0.21),
            largura=pol(item["largura"]),
            altura=pol(0.16),
            tamanho=10,
            cor=BRANCO,
            alinhamento=PP_ALIGN.LEFT,
            vertical=MSO_ANCHOR.MIDDLE,
        )

        texto(
            slide=slide,
            texto=item["descricao"],
            esquerda=pol(item["x"] + 0.15),
            topo=topo + pol(0.43),
            largura=pol(item["largura"]),
            altura=pol(0.25),
            tamanho=8,
            cor=BRANCO,
            alinhamento=PP_ALIGN.LEFT,
            vertical=MSO_ANCHOR.TOP,
        )

def rodape_panorama_executivo(
    slide,
    *,
    nome_regiao: str,
    ano: int,
    programas_destaque: list[str] | None = None,
    data_atualizacao: str = "",
) -> None:
    """
    Desenha o rodapé do slide Panorama Executivo.

    programas_destaque:
        lista com os três programas de maior número de matrículas
        na região selecionada.
    """

    topo = pol(6.28)
    altura = pol(1.22)

    programas = [
        str(programa).strip()
        for programa in (programas_destaque or [])
        if str(programa).strip()
    ][:3]

    while len(programas) < 3:
        programas.append("Programa não informado")

    programa_1, programa_2, programa_3 = programas

    def formatar_nome_programa(nome: str) -> str:
        """
        Coloca as iniciais em maiúsculas, preservando algumas siglas.
        """
        palavras_minusculas = {
            "a",
            "as",
            "o",
            "os",
            "de",
            "da",
            "das",
            "do",
            "dos",
            "e",
            "em",
            "para",
            "por",
        }

        siglas = {
            "RS",
            "EAD",
            "SENAI",
            "SESI",
            "IEL",
            "EJA",
            "NEJ",
            "GR",
            "GNR",
        }

        resultado = []

        for indice, palavra in enumerate(str(nome or "").strip().split()):
            palavra_limpa = palavra.strip()
            palavra_upper = palavra_limpa.upper()

            if palavra_upper in siglas:
                resultado.append(palavra_upper)
                continue

            if indice > 0 and palavra_limpa.lower() in palavras_minusculas:
                resultado.append(palavra_limpa.lower())
                continue

            resultado.append(
                palavra_limpa.lower().capitalize()
            )

        return " ".join(resultado)


    programa_1 = formatar_nome_programa(programa_1)
    programa_2 = formatar_nome_programa(programa_2)
    programa_3 = formatar_nome_programa(programa_3)

    # ======================================================
    # BARRA AZUL
    # ======================================================

    retangulo(
        slide=slide,
        esquerda=0,
        topo=topo,
        largura=pol(13.333),
        altura=altura,
        cor=AZUL_ESCURO,
        raio=False,
    )

    # ======================================================
    # FUNÇÕES AUXILIARES LOCAIS
    # ======================================================

    def adicionar_divisor(x: float) -> None:
        divisor = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            pol(x),
            topo + pol(0.12),
            pol(0.012),
            pol(0.94),
        )

        divisor.fill.solid()
        divisor.fill.fore_color.rgb = BRANCO
        divisor.line.fill.background()

    def adicionar_status(
        *,
        x: float,
        y: float,
        cor: RGBColor,
        descricao: str,
    ) -> None:
        circulo = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            pol(x),
            topo + pol(y),
            pol(0.09),
            pol(0.09),
        )

        circulo.fill.solid()
        circulo.fill.fore_color.rgb = cor
        circulo.line.fill.background()

        texto(
            slide=slide,
            texto=descricao,
            esquerda=pol(x + 0.14),
            topo=topo + pol(y - 0.025),
            largura=pol(2.75),
            altura=pol(0.14),
            tamanho=9,
            cor=BRANCO,
            vertical=MSO_ANCHOR.MIDDLE,
        )

    # ======================================================
    # BLOCO 1 — TEXTO EXECUTIVO
    # ======================================================

    # ======================================================
    # CÍRCULO TRANSPARENTE COM BORDA BRANCA
    # ======================================================

    diametro_circulo = pol(0.74)
    esquerda_circulo = pol(0.20)
    topo_circulo = topo + pol(0.20)

    circulo_icone = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.OVAL,
        esquerda_circulo,
        topo_circulo,
        diametro_circulo,
        diametro_circulo,
    )

    # Fundo totalmente transparente.
    circulo_icone.fill.background()

    # Borda branca.
    circulo_icone.line.color.rgb = BRANCO
    circulo_icone.line.width = Pt(1.5)

    # ======================================================
    # ÍCONE DENTRO DO CÍRCULO
    # ======================================================

    caminho_icone = (
        ASSETS_CARAVANA
        / "icone_crescimento.png"
    )

    caminho_icone = _recortar_icone_transparente(
        caminho=caminho_icone,
        limite_alpha=20,
        margem=1,
    )

    imagem_icone = adicionar_imagem(
        slide=slide,
        caminho=caminho_icone,
        esquerda=0,
        topo=0,
        altura=pol(0.46),
    )

    if imagem_icone is not None:
        imagem_icone.crop_left = 0.12
        imagem_icone.crop_right = 0.12
        imagem_icone.crop_top = 0.12
        imagem_icone.crop_bottom = 0.12

        imagem_icone.left = int(
            esquerda_circulo
            + (
                diametro_circulo
                - imagem_icone.width
            )
            / 2
        )

        imagem_icone.top = int(
            topo_circulo
            + (
                diametro_circulo
                - imagem_icone.height
            )
            / 2
        )

    texto_com_runs(
        slide=slide,
        runs=[
            {
                "texto": (
                    f"A Região {nome_regiao.title()} possui metas "
                    f"consistentes para {ano}, com destaque para "
                ),
                "cor": BRANCO,
                "tamanho": 13,
            },
            {
                "texto": programa_1,
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 13,
            },
            {
                "texto": ", ",
                "cor": BRANCO,
                "tamanho": 13,
            },
            {
                "texto": programa_2,
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 13,
            },
            {
                "texto": " e ",
                "cor": BRANCO,
                "tamanho": 13,
            },
            {
                "texto": programa_3,
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 13,
            },
            {
                "texto": ", mantendo forte participação da ",
                "cor": BRANCO,
                "tamanho": 13,
            },
            {
                "texto": "Gratuidade Regimental.",
                "cor": AZUL_CLARO,
                "negrito": True,
                "tamanho": 13,
            },
        ],
        esquerda=pol(1.08),
        topo=topo + pol(0.08),
        largura=pol(2.68),
        altura=pol(1.04),
        tamanho_padrao=13,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    adicionar_divisor(3.88)

    # ======================================================
    # BLOCO 2 — FONTES DOS DADOS
    # ======================================================

    texto(
        slide=slide,
        texto="Fontes dos dados:",
        esquerda=pol(4.08),
        topo=topo + pol(0.16),
        largura=pol(2.35),
        altura=pol(0.20),
        tamanho=14,
        cor=BRANCO,
        negrito=True,
    )

    texto(
        slide=slide,
        texto="Solução Integradora • Cubo Orçamento",
        esquerda=pol(4.08),
        topo=topo + pol(0.43),
        largura=pol(2.45),
        altura=pol(0.20),
        tamanho=12,
        cor=BRANCO,
    )

    texto(
        slide=slide,
        texto=(
            f"Dados atualizados até {data_atualizacao}"
            if data_atualizacao
            else "Dados atualizados conforme a base selecionada"
        ),
        esquerda=pol(4.08),
        topo=topo + pol(0.69),
        largura=pol(2.45),
        altura=pol(0.25),
        tamanho=12,
        cor=BRANCO,
    )

    adicionar_divisor(6.62)

    # ======================================================
    # BLOCO 3 — LEGENDA DE FINANCIAMENTO
    # ======================================================

    texto(
        slide=slide,
        texto="LEGENDA DE FINANCIAMENTO",
        esquerda=pol(6.82),
        topo=topo + pol(0.11),
        largura=pol(3.20),
        altura=pol(0.20),
        tamanho=13,
        cor=BRANCO,
        negrito=True,
    )

    circulo_gr = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.OVAL,
        pol(6.82),
        topo + pol(0.43),
        pol(0.15),
        pol(0.15),
    )
    circulo_gr.fill.solid()
    circulo_gr.fill.fore_color.rgb = AZUL_MATRICULAS
    circulo_gr.line.fill.background()

    texto(
        slide=slide,
        texto="GR",
        esquerda=pol(7.04),
        topo=topo + pol(0.38),
        largura=pol(0.45),
        altura=pol(0.20),
        tamanho=13,
        cor=BRANCO,
        negrito=True,
    )

    texto(
        slide=slide,
        texto="Gratuidade Regimental",
        esquerda=pol(7.04),
        topo=topo + pol(0.62),
        largura=pol(1.45),
        altura=pol(0.18),
        tamanho=10,
        cor=BRANCO,
    )

    circulo_gnr = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.OVAL,
        pol(8.55),
        topo + pol(0.43),
        pol(0.15),
        pol(0.15),
    )

    circulo_gnr.fill.solid()
    circulo_gnr.fill.fore_color.rgb = AZUL_HORA_ALUNO
    circulo_gnr.line.fill.background()

    texto(
        slide=slide,
        texto="GNR",
        esquerda=pol(8.77),
        topo=topo + pol(0.38),
        largura=pol(0.55),
        altura=pol(0.20),
        tamanho=13,
        cor=BRANCO,
        negrito=True,
    )

    texto(
        slide=slide,
        texto="Gratuidade Não Regimental",
        esquerda=pol(8.77),
        topo=topo + pol(0.62),

        # Termina antes do divisor em 10.28.
        largura=pol(1.40),

        altura=pol(0.18),
        tamanho=10,
        cor=BRANCO,
    )

    adicionar_divisor(10.28)

    # ======================================================
    # BLOCO 4 — LEGENDA DE STATUS
    # ======================================================

    texto(
        slide=slide,
        texto="LEGENDA DE STATUS",
        esquerda=pol(10.45),
        topo=topo + pol(0.035),
        largura=pol(2.75),
        altura=pol(0.18),
        tamanho=12,
        cor=BRANCO,
        negrito=True,
    )

    adicionar_status(
        x=10.45,
        y=0.25,
        cor=RGBColor(92, 175, 45),
        descricao="Meta atingida (≥ 100%)",
    )

    adicionar_status(
        x=10.45,
        y=0.40,
        cor=RGBColor(0, 135, 215),
        descricao="No caminho (75% – 99,9%)",
    )

    adicionar_status(
        x=10.45,
        y=0.55,
        cor=RGBColor(255, 166, 0),
        descricao="Atenção (51% – 74,9%)",
    )

    adicionar_status(
        x=10.45,
        y=0.70,
        cor=RGBColor(220, 45, 45),
        descricao="Crítico (< 51%)",
    )

    adicionar_status(
        x=10.45,
        y=0.85,
        cor=RGBColor(105, 125, 145),
        descricao="Sem movimento (Meta = 0 e Realizado = 0)",
    )

    # Item que estava faltando.
    adicionar_status(
        x=10.45,
        y=1.00,
        cor=RGBColor(70, 104, 133),
        descricao="Realizado sem meta (Meta = 0 e Realizado > 0)",
    )

def slide_trilhas_profissionais(
    prs,
) -> None:
    """
    Adiciona o slide TRILHAS PROFISSIONAIS como imagem inteira.
    """

    slide = prs.slides.add_slide(
        prs.slide_layouts[6]
    )

    caminho_slide = (
        ASSETS_CARAVANA
        / "slide_trilhas_profissionais.png"
    )

    slide.shapes.add_picture(
        str(caminho_slide),
        0,
        0,
        width=prs.slide_width,
        height=prs.slide_height,
    )

def slide_indicador_fidelizacao(
    apresentacao,
) -> None:
    slide = apresentacao.slides.add_slide(
        apresentacao.slide_layouts[6]
    )

    caminho_slide = (
        ASSETS_CARAVANA
        / "slide_indicador_fidelizacao.png"
    )

    slide.shapes.add_picture(
        str(caminho_slide),
        0,
        0,
        width=apresentacao.slide_width,
        height=apresentacao.slide_height,
    )

def slide_proximos_passos(
    apresentacao,
) -> None:
    slide = apresentacao.slides.add_slide(
        apresentacao.slide_layouts[6]
    )

    caminho_slide = (
        ASSETS_CARAVANA
        / "slide_proximos_passos.png"
    )

    slide.shapes.add_picture(
        str(caminho_slide),
        0,
        0,
        width=apresentacao.slide_width,
        height=apresentacao.slide_height,
    )