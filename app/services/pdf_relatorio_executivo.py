from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_SENAI = BASE_DIR / "assets" / "logo.png"

def _desenhar_logo_cabecalho(
    pdf,
    largura,
    altura,
    paisagem=False
):
    """
    Desenha o logotipo do SENAI no canto superior direito
    do cabeçalho azul.
    """

    if not LOGO_SENAI.exists():
        print(f"Logo do SENAI não encontrado: {LOGO_SENAI}")
        return

    if paisagem:
        largura_logo = 82
        altura_logo = 32
        margem_direita = 40
        deslocamento_topo = 23
    else:
        largura_logo = 78
        altura_logo = 31
        margem_direita = 40
        deslocamento_topo = 30

    x_logo = largura - margem_direita - largura_logo
    y_logo = altura - deslocamento_topo - altura_logo

    pdf.drawImage(
        str(LOGO_SENAI),
        x_logo,
        y_logo,
        width=largura_logo,
        height=altura_logo,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto"
    )

def _num(valor):
    return f"{float(valor or 0):,.0f}".replace(",", ".")


def _moeda(valor):
    texto = f"{float(valor or 0):,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _pct(valor):
    return f"{float(valor or 0):.1f}".replace(".", ",") + "%"

def _texto_atingimento(realizado, meta):
    realizado = float(realizado or 0)
    meta = float(meta or 0)

    if meta <= 0 and realizado <= 0:
        return "Não aplicável"

    if meta <= 0 and realizado > 0:
        return "Sem meta definida"

    if realizado <= 0 and meta > 0:
        return "Sem execução"

    return _pct((realizado / meta) * 100)

def _status_pct(valor, meta=1, realizado=1):
    valor = float(valor or 0)
    meta = float(meta or 0)
    realizado = float(realizado or 0)

    if meta == 0 and realizado > 0:
        return "Realizado sem meta"

    if meta == 0 and realizado == 0:
        return "Sem movimento"

    if valor >= 100:
        return "Meta atingida"

    if valor >= 75:
        return "No caminho"

    if valor >= 51:
        return "Atenção"

    return "Crítico"

def _cor_status_pct(valor, meta=1, realizado=1):
    valor = float(valor or 0)
    meta = float(meta or 0)
    realizado = float(realizado or 0)

    if meta <= 0 and realizado > 0:
        return colors.HexColor("#64748b")  # sem meta com realizado

    if meta <= 0 and realizado <= 0:
        return colors.HexColor("#111827")  # sem dados

    if valor >= 100:
        return colors.HexColor("#16a34a")

    if valor >= 75:
        return colors.HexColor("#2563eb")

    if valor >= 51:
        return colors.HexColor("#f59e0b")

    return colors.HexColor("#dc2626")


def _legenda_status(pdf, x, y):
    itens = [
        ("Meta atingida", "≥ 100%", colors.HexColor("#16a34a")),
        ("No caminho", "75%–99,9%", colors.HexColor("#2563eb")),
        ("Atenção", "51%–74,9%", colors.HexColor("#f59e0b")),
        ("Crítico", "< 51%", colors.HexColor("#dc2626")),
        ("*, Sem Meta", "Meta = 0 e realizado > 0", colors.HexColor("#64748b")),
        ("-, Sem Dados", "Meta = 0 e realizado = 0", colors.HexColor("#111827")),
    ]

    pdf.setFont("Helvetica-Bold", 9)
    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.drawString(x, y, "Legenda")

    y -= 18

    pdf.setFont("Helvetica", 7)

    col_w = 180
    linha_h = 18

    for i, (titulo, regra, cor) in enumerate(itens):
        col = i % 3
        lin = i // 3

        x_item = x + (col * col_w)
        y_item = y - (lin * linha_h)

        pdf.setFillColor(cor)
        pdf.roundRect(x_item, y_item - 3, 9, 9, 3, fill=True, stroke=False)

        pdf.setFillColor(colors.HexColor("#334155"))
        pdf.drawString(x_item + 13, y_item - 1, f"{titulo}: {regra}")

def _periodo(meses):
    nomes = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]

    if not meses:
        return "Todos os meses"

    meses = sorted([int(m) for m in meses])

    if len(meses) == 12:
        return "Janeiro a Dezembro"

    if len(meses) == 1:
        return nomes[meses[0]]

    continuo = all(
        meses[i] == meses[i - 1] + 1
        for i in range(1, len(meses))
    )

    if continuo:
        return f"{nomes[meses[0]]} a {nomes[meses[-1]]}"

    return ", ".join(nomes[m] for m in meses)

def _contexto_filtros(preview):
    partes = []

    if preview.get("programa"):
        partes.append(f"Programa: {preview.get('programa')}")

    if preview.get("regiao"):
        partes.append(f"Região: {preview.get('regiao')}")

    if preview.get("subregiao"):
        partes.append(f"Sub-região: {preview.get('subregiao')}")

    if preview.get("uo"):
        partes.append(f"UO: {preview.get('uo')}")

    return " • ".join(partes)

def _desenhar_contexto_cabecalho(
    pdf,
    preview,
    contexto,
    largura,
    altura,
    paisagem=False
):
    if not contexto:
        return

    max_largura = largura - 190

    linhas = simpleSplit(
        contexto,
        "Helvetica",
        8.5 if paisagem else 9,
        max_largura
    )

    pdf.setFont("Helvetica", 8.5 if paisagem else 9)
    pdf.setFillColor(colors.white)

    if paisagem:
        linha = linhas[0]

        if len(linhas) > 1:
            linha = linha[:105] + "..."

        pdf.drawString(40, altura - 72, linha)

    else:
        y_ctx = altura - 80

        programa = preview.get("programa")
        regiao = preview.get("regiao")
        subregiao = preview.get("subregiao")
        uo = preview.get("uo")

        linha1 = []

        if programa:
            linha1.append(f"Programa: {programa}")

        if regiao:
            linha1.append(f"Região: {regiao}")

        if linha1:
            pdf.drawString(
                40,
                y_ctx,
                " • ".join(linha1)
            )
            y_ctx -= 11

        linha2 = []

        if subregiao:
            linha2.append(f"Sub-região: {subregiao}")

        if uo:
            linha2.append(f"UO: {uo}")

        if linha2:
            pdf.drawString(
                40,
                y_ctx,
                " • ".join(linha2)
            )

def _resumo_executivo(preview, kpis):
    contexto = _contexto_filtros(preview)
    periodo = _periodo(preview.get("meses", []))

    return [
        f"No período de {periodo}, os resultados foram analisados {contexto}.",
        f"As matrículas alcançaram {_pct(kpis['matriculas']['atingimento'])} da meta acumulada.",
        f"A hora-aluno atingiu {_pct(kpis['hora_aluno']['atingimento'])}, enquanto a receita alcançou {_pct(kpis['receita']['atingimento'])}.",
    ]

def _gerar_insights(preview, kpis):
    pct_mat = float(kpis["matriculas"]["atingimento"] or 0)
    pct_ha = float(kpis["hora_aluno"]["atingimento"] or 0)
    pct_rec = float(kpis["receita"]["atingimento"] or 0)

    contexto = _contexto_filtros(preview)

    indicadores_criticos = sum(1 for v in [pct_mat, pct_ha, pct_rec] if v < 70)
    indicadores_atencao = sum(1 for v in [pct_mat, pct_ha, pct_rec] if 70 <= v < 100)
    indicadores_acima = sum(1 for v in [pct_mat, pct_ha, pct_rec] if v >= 100)

    insights = []

    if indicadores_criticos >= 2:
        insights.append(
            f"Desempenho crítico: há dois ou mais indicadores abaixo de 70%, {contexto}."
        )
    elif indicadores_criticos == 1:
        insights.append(
            f"Ponto crítico identificado: existe indicador abaixo de 70%, exigindo acompanhamento prioritário {contexto}."
        )
    elif indicadores_atencao > 0:
        insights.append(
            f"Atenção operacional: há indicador entre 70% e 99% da meta, indicando necessidade de ações pontuais {contexto}."
        )
    elif indicadores_acima >= 2:
        insights.append(
            f"Alta performance: os indicadores demonstram desempenho acima do previsto {contexto}."
        )

    if pct_rec >= 100 and (pct_mat < 100 or pct_ha < 100):
        insights.append(
            "Assimetria entre indicadores: a receita superou a meta, mas há indicador acadêmico abaixo do esperado."
        )

    if not insights:
        insights.append(
            f"Os indicadores não apresentam desvios relevantes no período analisado {contexto}."
        )

    return insights[:3]


def _gerar_recomendacoes(preview, kpis):
    pct_mat = float(kpis["matriculas"]["atingimento"] or 0)
    pct_ha = float(kpis["hora_aluno"]["atingimento"] or 0)
    pct_rec = float(kpis["receita"]["atingimento"] or 0)

    contexto = _contexto_filtros(preview)

    abaixo = []
    atencao = []
    acima = []

    if pct_mat < 70:
        abaixo.append("Matrículas")
    elif pct_mat < 100:
        atencao.append("Matrículas")
    else:
        acima.append("Matrículas")

    if pct_ha < 70:
        abaixo.append("Hora-Aluno")
    elif pct_ha < 100:
        atencao.append("Hora-Aluno")
    else:
        acima.append("Hora-Aluno")

    if pct_rec < 70:
        abaixo.append("Receita")
    elif pct_rec < 100:
        atencao.append("Receita")
    else:
        acima.append("Receita")

    recomendacoes = []

    if abaixo:
        recomendacoes.append(
            f"Indicadores abaixo do esperado: {', '.join(abaixo)}. Recomenda-se plano de ação corretivo {contexto}."
        )

    if atencao:
        recomendacoes.append(
            f"Indicadores em atenção: {', '.join(atencao)}. Recomenda-se acompanhamento e ações pontuais para aproximação da meta."
        )

    if acima and not abaixo and not atencao:
        recomendacoes.append(
            f"Indicadores acima da meta: {', '.join(acima)}. Recomenda-se consolidar as práticas de alta performance."
        )

    recomendacoes.append(
        "Relacionar os resultados aos planos de ação cadastrados, priorizando indicadores com menor atingimento."
    )

    return recomendacoes[:4]

def _card(
    pdf,
    x,
    y,
    w,
    h,
    titulo,
    valor,
    detalhe,
    cor_barra,
    espacamento_destaque=False
):
    pdf.setFillColor(
        colors.HexColor("#f8fafc")
    )

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.roundRect(
        x,
        y,
        w,
        h,
        12,
        fill=True,
        stroke=True
    )

    # Barra superior
    pdf.setFillColor(
        cor_barra
    )

    pdf.roundRect(
        x,
        y + h - 5,
        w,
        5,
        3,
        fill=True,
        stroke=False
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        9
    )

    pdf.drawString(
        x + 14,
        y + h - 28,
        titulo.upper()
    )


    # ======================================================
    # VALOR / NOME DA SUB-REGIÃO
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        14
    )

    if espacamento_destaque:
        y_valor = y + h - 47
    else:
        y_valor = y + h - 50

    pdf.drawString(
        x + 14,
        y_valor,
        str(valor)
    )


    # ======================================================
    # DETALHES
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        7.5
    )

    if espacamento_destaque:

        # Nos cards de destaque, os dados ficam mais
        # afastados do nome da sub-região.
        y_detalhe_1 = y + 19
        y_detalhe_2 = y + 8

    else:

        # Mantém o comportamento original nos demais cards.
        y_detalhe_1 = y + 24
        y_detalhe_2 = y + 12


    if " • " in detalhe:

        partes = detalhe.split(" • ")

        pdf.drawString(
            x + 14,
            y_detalhe_1,
            partes[0]
        )

        pdf.drawString(
            x + 14,
            y_detalhe_2,
            partes[1]
        )

    else:

        pdf.drawString(
            x + 14,
            y_detalhe_1,
            detalhe
        )

def _box_texto(pdf, x, y, w, h, titulo, itens, cor_fundo, cor_barra):
    pdf.setFillColor(cor_fundo)
    pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
    pdf.roundRect(x, y, w, h, 12, fill=True, stroke=True)

    pdf.setFillColor(cor_barra)
    pdf.roundRect(x, y + h - 5, w, 5, 3, fill=True, stroke=False)

    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(x + 14, y + h - 28, titulo)

    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.setFont("Helvetica", 10)

    linha_y = y + h - 52
    largura_texto = w - 36

    for item in itens:
        linhas = simpleSplit(
            f"• {item}",
            "Helvetica",
            10,
            largura_texto
        )

        for linha in linhas:
            pdf.drawString(x + 18, linha_y, linha)
            linha_y -= 14

        linha_y -= 5

def _grafico_colunas_comparativo(pdf, x, y, w, h, titulo, realizado, meta, eh_moeda=False):
    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    realizado = realizado or [None] * 12
    meta = meta or [None] * 12

    valores_validos = [
        v for v in realizado + meta
        if v is not None and float(v) > 0
    ]

    max_valor = max(valores_validos) if valores_validos else 1
    max_valor = max_valor * 1.32

    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
    pdf.roundRect(x, y, w, h, 12, fill=True, stroke=True)

    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(x + 16, y + h - 24, titulo)

    plot_x = x + 55
    plot_y = y + 38
    plot_w = w - 85
    plot_h = h - 110

    # Eixos
    pdf.setStrokeColor(colors.HexColor("#dbe2ea"))
    pdf.setLineWidth(1)
    pdf.line(plot_x, plot_y, plot_x + plot_w, plot_y)
    pdf.line(plot_x, plot_y, plot_x, plot_y + plot_h)

    # Eixo Y com 4 marcações
    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 6)

    for i in range(5):
        valor_eixo = (max_valor / 4) * i
        y_tick = plot_y + (plot_h / 4) * i

        pdf.setStrokeColor(colors.HexColor("#eef2f7"))
        pdf.line(plot_x, y_tick, plot_x + plot_w, y_tick)

        texto = _moeda(valor_eixo) if eh_moeda else _num(valor_eixo)
        pdf.drawRightString(plot_x - 6, y_tick - 2, texto)

    step = plot_w / 12
    bar_w = step * 0.26

    def escala(valor):
        return (float(valor or 0) / max_valor) * plot_h
    
    def desenhar_rotulo_vertical(texto, centro_x, topo_y, cor, font="Helvetica", size=5):
        pdf.saveState()
        pdf.translate(centro_x, topo_y)
        pdf.rotate(90)

        pdf.setFillColor(cor)
        pdf.setFont(font, size)

        # Não use largura / 2 aqui.
        # O texto cresce para cima após a rotação.
        pdf.drawString(0, -size / 2, texto)

        pdf.restoreState()

    for i in range(12):
        cx = plot_x + (step * i) + (step / 2)

        valor_real = realizado[i]
        valor_meta = meta[i]

        # Realizado
        if valor_real is not None and float(valor_real) > 0:
            bar_h = escala(valor_real)

            pdf.setFillColor(colors.HexColor("#2563eb"))
            pdf.roundRect(
                cx - bar_w - 1,
                plot_y,
                bar_w,
                bar_h,
                2,
                fill=True,
                stroke=False
            )

            pdf.setFillColor(colors.HexColor("#2563eb"))
            pdf.setFont("Helvetica-Bold", 5.8)
            texto = _moeda(valor_real) if eh_moeda else _num(valor_real)
            desenhar_rotulo_vertical(
                texto,
                cx - bar_w / 2 - 1,
                plot_y + bar_h + 4,
                colors.HexColor("#2563eb"),
                "Helvetica-Bold",
                5
            )

        # Meta
        if valor_meta is not None and float(valor_meta) > 0:
            bar_h = escala(valor_meta)

            pdf.setFillColor(colors.HexColor("#fb7185"))
            pdf.roundRect(
                cx + 1,
                plot_y,
                bar_w,
                bar_h,
                2,
                fill=True,
                stroke=False
            )

            pdf.setFillColor(colors.HexColor("#fb7185"))
            pdf.setFont("Helvetica", 5.8)
            texto = _moeda(valor_meta) if eh_moeda else _num(valor_meta)
            desenhar_rotulo_vertical(
                texto,
                cx + bar_w / 2 + 1,
                plot_y + bar_h + 4,
                colors.HexColor("#fb7185"),
                "Helvetica",
                5
            )

    # Meses
    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 7)

    for i, mes in enumerate(meses):
        cx = plot_x + (step * i) + (step / 2)
        pdf.drawCentredString(cx, y + 18, mes)

    # Legenda
    pdf.setFont("Helvetica", 8)

    pdf.setFillColor(colors.HexColor("#2563eb"))
    pdf.roundRect(x + w - 135, y + h - 27, 10, 7, 2, fill=True, stroke=False)
    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.drawString(x + w - 121, y + h - 26, "Realizado")

    pdf.setFillColor(colors.HexColor("#fb7185"))
    pdf.roundRect(x + w - 66, y + h - 27, 10, 7, 2, fill=True, stroke=False)
    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.drawString(x + w - 52, y + h - 26, "Meta")

def _grafico_colunas_preditivo(
    pdf,
    x,
    y,
    w,
    h,
    titulo,
    realizado,
    futuro,
    meta,
    rotulo_futuro,
    cor_futuro,
    eh_moeda=False
):
    meses = [
        "Jan", "Fev", "Mar", "Abr",
        "Mai", "Jun", "Jul", "Ago",
        "Set", "Out", "Nov", "Dez"
    ]

    realizado = realizado or [None] * 12
    futuro = futuro or [None] * 12
    meta = meta or [None] * 12

    # Garante 12 posições
    realizado = list(realizado)[:12]
    futuro = list(futuro)[:12]
    meta = list(meta)[:12]

    realizado += [None] * (12 - len(realizado))
    futuro += [None] * (12 - len(futuro))
    meta += [None] * (12 - len(meta))

    valores_validos = [
        v
        for v in realizado + futuro + meta
        if v is not None and float(v) > 0
    ]

    max_valor = (
        max(valores_validos)
        if valores_validos
        else 1
    )

    # Folga para os rótulos verticais
    max_valor *= 1.32

    # ======================================================
    # CARD
    # ======================================================

    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.roundRect(
        x,
        y,
        w,
        h,
        12,
        fill=True,
        stroke=True
    )

    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        12
    )

    pdf.drawString(
        x + 16,
        y + h - 24,
        titulo
    )

    # ======================================================
    # ÁREA DO GRÁFICO
    # ======================================================

    plot_x = x + 55
    plot_y = y + 38
    plot_w = w - 85
    plot_h = h - 110

    # Eixos
    pdf.setStrokeColor(
        colors.HexColor("#dbe2ea")
    )

    pdf.setLineWidth(1)

    pdf.line(
        plot_x,
        plot_y,
        plot_x + plot_w,
        plot_y
    )

    pdf.line(
        plot_x,
        plot_y,
        plot_x,
        plot_y + plot_h
    )

    # ======================================================
    # EIXO Y
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        6
    )

    for i in range(5):

        valor_eixo = (
            max_valor / 4
        ) * i

        y_tick = (
            plot_y
            + (plot_h / 4) * i
        )

        pdf.setStrokeColor(
            colors.HexColor("#eef2f7")
        )

        pdf.line(
            plot_x,
            y_tick,
            plot_x + plot_w,
            y_tick
        )

        texto = (
            _moeda(valor_eixo)
            if eh_moeda
            else _num(valor_eixo)
        )

        pdf.drawRightString(
            plot_x - 6,
            y_tick - 2,
            texto
        )

    step = plot_w / 12

    # Temos no máximo três barras por mês
    bar_w = step * 0.20

    def escala(valor):
        return (
            float(valor or 0)
            / max_valor
        ) * plot_h

    def desenhar_rotulo_vertical(
        texto,
        centro_x,
        topo_y,
        cor,
        font="Helvetica",
        size=5
    ):
        pdf.saveState()

        pdf.translate(
            centro_x,
            topo_y
        )

        pdf.rotate(90)

        pdf.setFillColor(cor)
        pdf.setFont(font, size)

        pdf.drawString(
            0,
            -size / 2,
            texto
        )

        pdf.restoreState()

    # ======================================================
    # BARRAS
    # ======================================================

    cor_realizado = colors.HexColor(
        "#2563eb"
    )

    cor_meta = colors.HexColor(
        "#fb7185"
    )

    if isinstance(cor_futuro, str):
        cor_futuro = colors.HexColor(
            cor_futuro
        )

    for i in range(12):

        cx = (
            plot_x
            + (step * i)
            + (step / 2)
        )

        valor_real = realizado[i]
        valor_futuro = futuro[i]
        valor_meta = meta[i]

        # --------------------------------------------------
        # REALIZADO
        # --------------------------------------------------

        if (
            valor_real is not None
            and float(valor_real) > 0
        ):
            bar_h = escala(
                valor_real
            )

            x_barra = (
                cx
                - bar_w
                - 2
            )

            pdf.setFillColor(
                cor_realizado
            )

            pdf.roundRect(
                x_barra,
                plot_y,
                bar_w,
                bar_h,
                2,
                fill=True,
                stroke=False
            )

            texto = (
                _moeda(valor_real)
                if eh_moeda
                else _num(valor_real)
            )

            desenhar_rotulo_vertical(
                texto,
                x_barra
                + bar_w / 2,
                plot_y
                + bar_h
                + 4,
                cor_realizado,
                "Helvetica-Bold",
                5
            )

        # --------------------------------------------------
        # FUTURO
        # Projeção / HA Garantida / Receita Contratada
        # --------------------------------------------------

        if (
            valor_futuro is not None
            and float(valor_futuro) > 0
        ):
            bar_h = escala(
                valor_futuro
            )

            x_barra = cx - 1

            pdf.setFillColor(
                cor_futuro
            )

            pdf.roundRect(
                x_barra,
                plot_y,
                bar_w,
                bar_h,
                2,
                fill=True,
                stroke=False
            )

            texto = (
                _moeda(valor_futuro)
                if eh_moeda
                else _num(valor_futuro)
            )

            desenhar_rotulo_vertical(
                texto,
                x_barra
                + bar_w / 2,
                plot_y
                + bar_h
                + 4,
                cor_futuro,
                "Helvetica-Bold",
                5
            )

        # --------------------------------------------------
        # META
        # --------------------------------------------------

        if (
            valor_meta is not None
            and float(valor_meta) > 0
        ):
            bar_h = escala(
                valor_meta
            )

            x_barra = (
                cx
                + bar_w
                + 1
            )

            pdf.setFillColor(
                cor_meta
            )

            pdf.roundRect(
                x_barra,
                plot_y,
                bar_w,
                bar_h,
                2,
                fill=True,
                stroke=False
            )

            texto = (
                _moeda(valor_meta)
                if eh_moeda
                else _num(valor_meta)
            )

            desenhar_rotulo_vertical(
                texto,
                x_barra
                + bar_w / 2,
                plot_y
                + bar_h
                + 4,
                cor_meta,
                "Helvetica",
                5
            )

    # ======================================================
    # MESES
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        7
    )

    for i, mes in enumerate(meses):

        cx = (
            plot_x
            + (step * i)
            + (step / 2)
        )

        pdf.drawCentredString(
            cx,
            y + 18,
            mes
        )

    # ======================================================
    # LEGENDA
    # ======================================================

    pdf.setFont(
        "Helvetica",
        7.5
    )

    # Trabalhamos da direita para a esquerda
    legenda_y = y + h - 27

    # Meta
    x_meta = x + w - 62

    pdf.setFillColor(
        cor_meta
    )

    pdf.roundRect(
        x_meta,
        legenda_y,
        9,
        7,
        2,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#334155")
    )

    pdf.drawString(
        x_meta + 13,
        legenda_y + 1,
        "Meta"
    )

    # Futuro
    largura_rotulo_futuro = stringWidth(
        rotulo_futuro,
        "Helvetica",
        7.5
    )

    x_futuro = (
        x_meta
        - largura_rotulo_futuro
        - 35
    )

    pdf.setFillColor(
        cor_futuro
    )

    pdf.roundRect(
        x_futuro,
        legenda_y,
        9,
        7,
        2,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#334155")
    )

    pdf.drawString(
        x_futuro + 13,
        legenda_y + 1,
        rotulo_futuro
    )

    # Realizado
    largura_realizado = stringWidth(
        "Realizado",
        "Helvetica",
        7.5
    )

    x_realizado = (
        x_futuro
        - largura_realizado
        - 35
    )

    pdf.setFillColor(
        cor_realizado
    )

    pdf.roundRect(
        x_realizado,
        legenda_y,
        9,
        7,
        2,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#334155")
    )

    pdf.drawString(
        x_realizado + 13,
        legenda_y + 1,
        "Realizado"
    )

def _pontuacao_indicador(realizado, meta):
    """
    Pontuação básica de um indicador:

    >= 100%  = 3 pontos
    75–99%   = 2 pontos
    51–74%   = 1 ponto
    < 51%    = 0 pontos

    Indicadores sem meta ou sem dados não recebem pontuação.
    """

    realizado = float(realizado or 0)
    meta = float(meta or 0)

    if meta <= 0:
        return None

    atingimento = (realizado / meta) * 100

    if atingimento >= 100:
        return 3

    if atingimento >= 75:
        return 2

    if atingimento >= 51:
        return 1

    return 0

def _classificar_score_unidade(score, score_maximo):
    """
    Classifica a unidade proporcionalmente ao total possível.

    O uso proporcional é necessário porque a quantidade de modalidades
    pode variar entre as unidades.
    """

    score = float(score or 0)
    score_maximo = float(score_maximo or 0)

    if score_maximo <= 0:
        return {
            "classificacao": "Sem classificação",
            "nivel": "sem_dados",
            "percentual_score": 0
        }

    percentual_score = (
        score / score_maximo
    ) * 100

    if percentual_score >= 85:
        classificacao = "Desempenho de Excelência"
        nivel = "excelencia"

    elif percentual_score >= 65:
        classificacao = "Desempenho Satisfatório"
        nivel = "satisfatorio"

    elif percentual_score >= 40:
        classificacao = "Desempenho Regular"
        nivel = "regular"

    else:
        classificacao = "Desempenho Crítico"
        nivel = "critico"

    return {
        "classificacao": classificacao,
        "nivel": nivel,
        "percentual_score": percentual_score
    }

def _analisar_indicador_modalidade(
    modalidade,
    realizado,
    meta,
    indicador
):
    """
    Gera a interpretação textual de um indicador por modalidade.

    indicador:
        "matriculas"
        "hora_aluno"
        "receita"
    """

    modalidade = (
        str(modalidade).strip()
        if modalidade
        else "Não informada"
    )

    realizado = float(realizado or 0)
    meta = float(meta or 0)

    # ======================================================
    # SEM META E SEM EXECUÇÃO
    # ======================================================

    if meta <= 0 and realizado <= 0:
        return {
            "modalidade": modalidade,
            "indicador": indicador,
            "realizado": realizado,
            "meta": meta,
            "atingimento": None,
            "pontuacao": None,
            "status": "sem_dados",
            "texto": (
                f"Não houve meta nem execução registrada para a modalidade "
                f"{modalidade} durante o período analisado."
            )
        }

    # ======================================================
    # EXECUÇÃO SEM META
    # ======================================================

    if meta <= 0 and realizado > 0:

        if indicador == "matriculas":
            texto = (
                f"A modalidade {modalidade} registrou "
                f"{_num(realizado)} matrículas, embora não exista meta "
                f"estabelecida para o período. O resultado demonstra "
                f"execução operacional sem referência de planejamento."
            )

        elif indicador == "hora_aluno":
            texto = (
                f"A modalidade {modalidade} registrou "
                f"{_num(realizado)} horas-aluno, embora não exista meta "
                f"estabelecida para o período. O resultado evidencia "
                f"execução formativa sem referência de planejamento."
            )

        else:
            texto = (
                f"A modalidade {modalidade} registrou receita de "
                f"{_moeda(realizado)}, embora não exista meta estabelecida "
                f"para o período. Recomenda-se verificar o alinhamento "
                f"entre a execução financeira e o planejamento."
            )

        return {
            "modalidade": modalidade,
            "indicador": indicador,
            "realizado": realizado,
            "meta": meta,
            "atingimento": None,
            "pontuacao": None,
            "status": "sem_meta",
            "texto": texto
        }

    atingimento = (
        realizado / meta
    ) * 100

    pontuacao = _pontuacao_indicador(
        realizado,
        meta
    )

    # ======================================================
    # MATRÍCULAS
    # ======================================================

    if indicador == "matriculas":

        if atingimento >= 100:
            status = "meta_atingida"
            texto = (
                f"A modalidade {modalidade} superou a meta de matrículas, "
                f"registrando {_num(realizado)} matrículas frente à meta de "
                f"{_num(meta)}, atingindo {_pct(atingimento)}."
            )

        elif atingimento >= 75:
            status = "no_caminho"
            texto = (
                f"A modalidade {modalidade} encontra-se próxima da meta "
                f"prevista, com {_pct(atingimento)} de atingimento. Foram "
                f"realizadas {_num(realizado)} matrículas diante da meta de "
                f"{_num(meta)}, indicando desempenho consistente."
            )

        elif atingimento >= 51:
            status = "atencao"
            texto = (
                f"A modalidade {modalidade} apresenta desempenho abaixo do "
                f"esperado, alcançando {_pct(atingimento)} da meta de "
                f"matrículas. Foram realizadas {_num(realizado)} matrículas "
                f"frente à meta de {_num(meta)}."
            )

        else:
            status = "critico"
            texto = (
                f"A modalidade {modalidade} apresenta desempenho crítico "
                f"nas matrículas, atingindo {_pct(atingimento)} da meta. "
                f"Foram realizadas {_num(realizado)} matrículas diante da "
                f"meta de {_num(meta)}, sendo recomendável acompanhar as "
                f"ações de captação e permanência dos estudantes."
            )

    # ======================================================
    # HORA-ALUNO
    # ======================================================

    elif indicador == "hora_aluno":

        if atingimento >= 100:
            status = "meta_atingida"
            texto = (
                f"A modalidade {modalidade} alcançou "
                f"{_pct(atingimento)} da meta de hora-aluno, registrando "
                f"{_num(realizado)} horas-aluno frente à meta de "
                f"{_num(meta)}. O resultado indica elevada utilização da "
                f"capacidade formativa."
            )

        elif atingimento >= 75:
            status = "no_caminho"
            texto = (
                f"A modalidade {modalidade} apresentou desempenho próximo "
                f"do esperado em hora-aluno, atingindo "
                f"{_pct(atingimento)} da meta. Foram realizadas "
                f"{_num(realizado)} horas-aluno diante da meta de "
                f"{_num(meta)}."
            )

        elif atingimento >= 51:
            status = "atencao"
            texto = (
                f"A modalidade {modalidade} permaneceu abaixo do desempenho "
                f"esperado em hora-aluno, alcançando "
                f"{_pct(atingimento)} da meta. O resultado indica necessidade "
                f"de acompanhamento da execução das cargas horárias previstas."
            )

        else:
            status = "critico"
            texto = (
                f"A modalidade {modalidade} apresenta desempenho crítico em "
                f"hora-aluno, atingindo apenas {_pct(atingimento)} da meta. "
                f"Recomenda-se avaliar a execução das turmas, as cargas "
                f"horárias realizadas e o cronograma de oferta."
            )

    # ======================================================
    # RECEITA
    # ======================================================

    elif indicador == "receita":

        if realizado <= 0:
            status = "critico"
            texto = (
                f"Embora exista meta de receita para a modalidade "
                f"{modalidade}, não houve realização de receita no período "
                f"analisado. Recomenda-se avaliar o cronograma de faturamento, "
                f"os contratos vinculados e o registro da execução financeira."
            )

        elif atingimento >= 100:
            status = "meta_atingida"
            texto = (
                f"A modalidade {modalidade} superou a meta de receita, "
                f"registrando {_moeda(realizado)} frente à meta de "
                f"{_moeda(meta)}, com atingimento de "
                f"{_pct(atingimento)}."
            )

        elif atingimento >= 75:
            status = "no_caminho"
            texto = (
                f"A receita da modalidade {modalidade} encontra-se próxima "
                f"da meta prevista, atingindo {_pct(atingimento)}. Foram "
                f"realizados {_moeda(realizado)} diante da meta de "
                f"{_moeda(meta)}."
            )

        elif atingimento >= 51:
            status = "atencao"
            texto = (
                f"A modalidade {modalidade} apresenta receita abaixo do "
                f"esperado, alcançando {_pct(atingimento)} da meta. Foram "
                f"realizados {_moeda(realizado)} frente à meta de "
                f"{_moeda(meta)}."
            )

        else:
            status = "critico"
            texto = (
                f"A receita da modalidade {modalidade} apresenta desempenho "
                f"crítico, atingindo apenas {_pct(atingimento)} da meta. "
                f"Recomenda-se avaliar fatores como cronograma de faturamento, "
                f"contratos, execução das turmas e características específicas "
                f"da modalidade."
            )

    else:
        raise ValueError(
            f"Indicador não reconhecido: {indicador}"
        )

    return {
        "modalidade": modalidade,
        "indicador": indicador,
        "realizado": realizado,
        "meta": meta,
        "atingimento": atingimento,
        "pontuacao": pontuacao,
        "status": status,
        "texto": texto
    }

def _gerar_analise_unidade(
    nome_uo,
    programa,
    matriculas,
    hora_aluno,
    receita
):
    """
    Consolida a análise textual de uma Unidade Operacional.

    Os parâmetros matriculas, hora_aluno e receita devem ser
    listas no mesmo formato utilizado nas tabelas detalhadas:

    {
        "modalidade": "...",
        "meta_periodo": 0,
        "realizado_periodo": 0,
        "meta_anual": 0,
        "atingimento": 0
    }
    """

    nome_uo = (
        str(nome_uo).strip()
        if nome_uo
        else "Unidade operacional não informada"
    )

    programa = (
        str(programa).strip()
        if programa
        else "programa não informado"
    )

    matriculas = matriculas or []
    hora_aluno = hora_aluno or []
    receita = receita or []

    # ======================================================
    # IDENTIFICA AS MODALIDADES EXISTENTES
    # ======================================================

    modalidades = set()

    for grupo in [
        matriculas,
        hora_aluno,
        receita
    ]:
        for item in grupo:
            modalidade = (
                item.get("modalidade")
                or "Não informada"
            )

            modalidades.add(
                str(modalidade).strip()
            )

    qtd_modalidades = len(modalidades)

    # ======================================================
    # ANALISA CADA INDICADOR
    # ======================================================

    analises_matriculas = []

    for item in matriculas:
        analises_matriculas.append(
            _analisar_indicador_modalidade(
                modalidade=item.get("modalidade"),
                realizado=item.get(
                    "realizado_periodo",
                    0
                ),
                meta=item.get(
                    "meta_periodo",
                    0
                ),
                indicador="matriculas"
            )
        )

    analises_hora_aluno = []

    for item in hora_aluno:
        analises_hora_aluno.append(
            _analisar_indicador_modalidade(
                modalidade=item.get("modalidade"),
                realizado=item.get(
                    "realizado_periodo",
                    0
                ),
                meta=item.get(
                    "meta_periodo",
                    0
                ),
                indicador="hora_aluno"
            )
        )

    analises_receita = []

    for item in receita:
        analises_receita.append(
            _analisar_indicador_modalidade(
                modalidade=item.get("modalidade"),
                realizado=item.get(
                    "realizado_periodo",
                    0
                ),
                meta=item.get(
                    "meta_periodo",
                    0
                ),
                indicador="receita"
            )
        )

    # ======================================================
    # CALCULA O SCORE
    # ======================================================

    todas_analises = (
        analises_matriculas
        + analises_hora_aluno
        + analises_receita
    )

    pontuacoes_validas = [
        item.get("pontuacao")
        for item in todas_analises
        if item.get("pontuacao") is not None
    ]

    score_obtido = sum(
        pontuacoes_validas
    )

    score_maximo = (
        len(pontuacoes_validas) * 3
    )

    classificacao = _classificar_score_unidade(
        score_obtido,
        score_maximo
    )

    # ======================================================
    # CONTAGENS DOS STATUS
    # ======================================================

    status_avaliados = [
        item.get("status")
        for item in todas_analises
    ]

    qtd_meta_atingida = status_avaliados.count(
        "meta_atingida"
    )

    qtd_no_caminho = status_avaliados.count(
        "no_caminho"
    )

    qtd_atencao = status_avaliados.count(
        "atencao"
    )

    qtd_critico = status_avaliados.count(
        "critico"
    )

    qtd_sem_meta = status_avaliados.count(
        "sem_meta"
    )

    qtd_sem_dados = status_avaliados.count(
        "sem_dados"
    )

    # ======================================================
    # RESUMO EXECUTIVO
    # ======================================================

    resumo_executivo = (
        f"No período analisado, a unidade {nome_uo} apresentou "
        f"desempenho em {qtd_modalidades} modalidade"
        f"{'s' if qtd_modalidades != 1 else ''} do programa "
        f"{programa}. A análise evidencia os resultados obtidos "
        f"em matrículas, hora-aluno e receita, destacando os "
        f"indicadores que superaram as metas estabelecidas e "
        f"aqueles que demandam maior atenção para os próximos meses."
    )

    dados_analise = {
        "uo": nome_uo,
        "programa": programa,
        "qtd_modalidades": qtd_modalidades,

        "resumo_executivo": resumo_executivo,

        "matriculas": analises_matriculas,
        "hora_aluno": analises_hora_aluno,
        "receita": analises_receita,

        "score": score_obtido,
        "score_maximo": score_maximo,

        "percentual_score": classificacao.get(
            "percentual_score",
            0
        ),

        "classificacao": classificacao.get(
            "classificacao",
            "Sem classificação"
        ),

        "nivel": classificacao.get(
            "nivel",
            "sem_dados"
        ),

        "resumo_status": {
            "meta_atingida": qtd_meta_atingida,
            "no_caminho": qtd_no_caminho,
            "atencao": qtd_atencao,
            "critico": qtd_critico,
            "sem_meta": qtd_sem_meta,
            "sem_dados": qtd_sem_dados
        }
    }

    conclusao = _gerar_conclusao_unidade(
        dados_analise
    )

    dados_analise["conclusao"] = conclusao.get(
        "texto",
        ""
    )

    dados_analise["medias_atingimento"] = {
        "matriculas": conclusao.get(
            "media_matriculas"
        ),
        "hora_aluno": conclusao.get(
            "media_hora_aluno"
        ),
        "receita": conclusao.get(
            "media_receita"
        )
    }

    return dados_analise

    # ======================================================
    # RESULTADO
    # ======================================================

    return {
        "uo": nome_uo,
        "programa": programa,
        "qtd_modalidades": qtd_modalidades,

        "resumo_executivo": resumo_executivo,

        "matriculas": analises_matriculas,
        "hora_aluno": analises_hora_aluno,
        "receita": analises_receita,

        "score": score_obtido,
        "score_maximo": score_maximo,

        "percentual_score": classificacao.get(
            "percentual_score",
            0
        ),

        "classificacao": classificacao.get(
            "classificacao",
            "Sem classificação"
        ),

        "nivel": classificacao.get(
            "nivel",
            "sem_dados"
        ),

        "resumo_status": {
            "meta_atingida": qtd_meta_atingida,
            "no_caminho": qtd_no_caminho,
            "atencao": qtd_atencao,
            "critico": qtd_critico,
            "sem_meta": qtd_sem_meta,
            "sem_dados": qtd_sem_dados
        }
    }

def _gerar_conclusao_unidade(analise):
    """
    Gera a conclusão executiva da unidade com base no score,
    nos status dos indicadores e no alinhamento entre
    matrículas, hora-aluno e receita.
    """

    classificacao = analise.get(
        "classificacao",
        "Sem classificação"
    )

    resumo_status = analise.get(
        "resumo_status",
        {}
    )

    qtd_meta_atingida = resumo_status.get(
        "meta_atingida",
        0
    )

    qtd_no_caminho = resumo_status.get(
        "no_caminho",
        0
    )

    qtd_atencao = resumo_status.get(
        "atencao",
        0
    )

    qtd_critico = resumo_status.get(
        "critico",
        0
    )

    qtd_sem_meta = resumo_status.get(
        "sem_meta",
        0
    )

    qtd_sem_dados = resumo_status.get(
        "sem_dados",
        0
    )

    matriculas = analise.get(
        "matriculas",
        []
    )

    hora_aluno = analise.get(
        "hora_aluno",
        []
    )

    receita = analise.get(
        "receita",
        []
    )

    # ======================================================
    # MÉDIA DE ATINGIMENTO POR INDICADOR
    # ======================================================

    def calcular_media_atingimento(itens):
        valores = [
            float(item.get("atingimento") or 0)
            for item in itens
            if item.get("atingimento") is not None
        ]

        if not valores:
            return None

        return sum(valores) / len(valores)

    media_matriculas = calcular_media_atingimento(
        matriculas
    )

    media_hora_aluno = calcular_media_atingimento(
        hora_aluno
    )

    media_receita = calcular_media_atingimento(
        receita
    )

    # ======================================================
    # TEXTO INICIAL DA CONCLUSÃO
    # ======================================================

    if classificacao == "Desempenho de Excelência":
        conclusao = (
            "De forma geral, a unidade apresentou desempenho de excelência, "
            "com resultados consistentes e elevada aderência às metas "
            "estabelecidas."
        )

    elif classificacao == "Desempenho Satisfatório":
        conclusao = (
            "De forma geral, a unidade apresentou desempenho satisfatório, "
            "com boa execução operacional e parte significativa dos "
            "indicadores próxima ou acima das metas estabelecidas."
        )

    elif classificacao == "Desempenho Regular":
        conclusao = (
            "A unidade apresentou desempenho regular, com resultados "
            "heterogêneos entre os indicadores e necessidade de "
            "acompanhamento das modalidades com menor atingimento."
        )

    elif classificacao == "Desempenho Crítico":
        conclusao = (
            "A unidade apresentou desempenho crítico no período analisado, "
            "com indicadores relevantes abaixo das metas estabelecidas. "
            "Recomenda-se priorizar a elaboração e o acompanhamento de ações "
            "corretivas."
        )

    else:
        conclusao = (
            "Não foi possível estabelecer uma classificação completa para "
            "a unidade, em razão da ausência de indicadores planejados "
            "suficientes para avaliação."
        )

    # ======================================================
    # COMPLEMENTOS CONFORME O RESULTADO
    # ======================================================

    complementos = []

    if qtd_meta_atingida > 0:
        complementos.append(
            f"{qtd_meta_atingida} indicador"
            f"{'es atingiram' if qtd_meta_atingida != 1 else ' atingiu'} "
            f"ou superaram as metas previstas."
        )

    if qtd_critico > 0:
        complementos.append(
            f"{qtd_critico} indicador"
            f"{'es apresentam' if qtd_critico != 1 else ' apresenta'} "
            f"desempenho crítico e demandam acompanhamento prioritário."
        )

    elif qtd_atencao > 0:
        complementos.append(
            f"{qtd_atencao} indicador"
            f"{'es permanecem' if qtd_atencao != 1 else ' permanece'} "
            f"em nível de atenção."
        )

    elif qtd_no_caminho > 0:
        complementos.append(
            f"{qtd_no_caminho} indicador"
            f"{'es encontram-se' if qtd_no_caminho != 1 else ' encontra-se'} "
            f"próximos das metas estabelecidas."
        )

    # ======================================================
    # ALINHAMENTO ENTRE MATRÍCULAS E RECEITA
    # ======================================================

    if (
        media_matriculas is not None
        and media_receita is not None
    ):
        diferenca_matricula_receita = (
            media_matriculas
            - media_receita
        )

        if (
            media_matriculas >= 75
            and media_receita < 51
        ):
            complementos.append(
                "Apesar do desempenho operacional das matrículas, a receita "
                "permaneceu em nível crítico. Recomenda-se avaliar fatores "
                "como cronograma de faturamento, contratos ou registros da "
                "execução financeira."
            )

        elif diferenca_matricula_receita >= 30:
            complementos.append(
                "Observa-se desalinhamento entre matrículas e receita, com "
                "desempenho financeiro inferior à execução operacional."
            )

        elif (
            media_matriculas < 51
            and media_receita >= 100
        ):
            complementos.append(
                "A receita superou a meta mesmo com desempenho crítico em "
                "matrículas. Recomenda-se verificar se o resultado decorre "
                "de faturamentos de períodos anteriores ou de contratos com "
                "características específicas."
            )

    # ======================================================
    # ALINHAMENTO ENTRE MATRÍCULAS E HORA-ALUNO
    # ======================================================

    if (
        media_matriculas is not None
        and media_hora_aluno is not None
    ):
        diferenca_operacional = abs(
            media_matriculas
            - media_hora_aluno
        )

        if diferenca_operacional >= 30:
            complementos.append(
                "Há diferença relevante entre o desempenho de matrículas e "
                "hora-aluno, indicando necessidade de avaliar a execução das "
                "cargas horárias e o andamento das turmas."
            )

    # ======================================================
    # EXECUÇÃO SEM PLANEJAMENTO
    # ======================================================

    if qtd_sem_meta > 0:
        complementos.append(
            f"Foram identificados {qtd_sem_meta} indicador"
            f"{'es com execução' if qtd_sem_meta != 1 else ' com execução'} "
            f"sem meta definida, o que reduz a comparabilidade entre "
            f"planejamento e resultado."
        )

    if qtd_sem_dados > 0:
        complementos.append(
            f"Também foram encontrados {qtd_sem_dados} indicador"
            f"{'es sem meta e sem execução registrada' if qtd_sem_dados != 1 else ' sem meta e sem execução registrada'}."
        )

    # Limita a conclusão para não gerar texto excessivo
    if complementos:
        conclusao += " " + " ".join(
            complementos[:4]
        )

    return {
        "texto": conclusao,
        "media_matriculas": media_matriculas,
        "media_hora_aluno": media_hora_aluno,
        "media_receita": media_receita
    }

def gerar_pdf_relatorio_executivo(preview, orientacao="retrato"):
    buffer = BytesIO()

    pagina = landscape(A4) if orientacao == "paisagem" else A4
    pdf = canvas.Canvas(buffer, pagesize=pagina)

    largura, altura = pagina

    kpis = preview["kpis"]

    # Cabeçalho azul
    pdf.setFillColor(colors.HexColor("#003B8F"))
    pdf.rect(0, altura - 115, largura, 115, fill=True, stroke=False)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(40, altura - 42, "RELATÓRIO EXECUTIVO")

    pdf.setFont("Helvetica", 11)
    pdf.drawString(
        40,
        altura - 66,
        f"Ano: {preview['ano']} • Período: {_periodo(preview.get('meses', []))}"
    )

    contexto = _contexto_filtros(preview)

    _desenhar_contexto_cabecalho(
        pdf,
        preview,
        contexto,
        largura,
        altura,
        paisagem=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=False
    )

    # Bloco de contexto
    y_contexto = altura - 155

    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y_contexto, "Resumo:")

    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.setFont("Helvetica", 10)

    resumo = preview.get(
        "resumo_executivo",
        ""
    )

    y = y_contexto - 22

    linhas_quebradas = simpleSplit(
        resumo,
        "Helvetica",
        10,
        largura - 100
    )

    for linha in linhas_quebradas:
        pdf.drawString(55, y, linha)
        y -= 15

    # Cards
    margem = 25
    gap = 10
    card_h = 92
    card_w = (largura - (margem * 2) - (gap * 3)) / 4
    y_cards = altura - 345

    txt_mat = _texto_atingimento(
        kpis["matriculas"]["realizado"],
        kpis["matriculas"]["meta"]
    )

    txt_ha = _texto_atingimento(
        kpis["hora_aluno"]["realizado"],
        kpis["hora_aluno"]["meta"]
    )

    txt_rec = _texto_atingimento(
        kpis["receita"]["realizado"],
        kpis["receita"]["meta"]
    )

    _card(
        pdf,
        margem,
        y_cards,
        card_w,
        card_h,
        "Matrículas",
        _num(kpis["matriculas"]["realizado"]),
        f"Meta: {_num(kpis['matriculas']['meta'])} • Atingimento: {txt_mat}",
        colors.HexColor("#2563eb")
    )

    _card(
        pdf,
        margem + (card_w + gap),
        y_cards,
        card_w,
        card_h,
        "Hora-Aluno",
        _num(kpis["hora_aluno"]["realizado"]),
        f"Meta: {_num(kpis['hora_aluno']['meta'])} • Atingimento: {txt_ha}",
        colors.HexColor("#16a34a")
    )

    _card(
        pdf,
        margem + (card_w + gap) * 2,
        y_cards,
        card_w,
        card_h,
        "Receita",
        _moeda(kpis["receita"]["realizado"]),
        f"Meta: {_moeda(kpis['receita']['meta'])} • Atingimento: {txt_rec}",
        colors.HexColor("#f59e0b")
    )

    _card(
        pdf,
        margem + (card_w + gap) * 3,
        y_cards,
        card_w,
        card_h,
        "Turmas",
        _num(kpis["turmas"]["total"]),
        "Referência: Período",
        colors.HexColor("#6d5dfc")
    )

    # Blocos executivos
    y_texto = y_cards - 45

    resumo_executivo = preview.get("resumo_executivo", "")

    insights = preview.get(
        "insights_executivos",
        []
    )

    recomendacoes = preview.get(
        "recomendacoes",
        []
    )

    altura_insights = max(
        115,
        80 + (len(insights) * 26)
    )

    altura_recomendacoes = max(
        115,
        80 + (len(recomendacoes) * 26)
    )

    _box_texto(
        pdf,
        40,
        y_texto - altura_insights,
        largura - 80,
        altura_insights,
        "Insights:",
        insights,
        colors.HexColor("#eff6ff"),
        colors.HexColor("#2563eb")
    )

    y_texto -= (altura_insights + 20)

    _box_texto(
        pdf,
        40,
        y_texto - altura_recomendacoes,
        largura - 80,
        altura_recomendacoes,
        "Recomendações:",
        recomendacoes,
        colors.HexColor("#f0fdf4"),
        colors.HexColor("#16a34a")
    )

    # Rodapé
    pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
    pdf.line(40, 42, largura - 40, 42)

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(40, 28, "Painel Executivo SENAI • Relatório gerado automaticamente")
    pdf.drawRightString(largura - 40, 28, "Página 1")

    # Página 2
    pdf.showPage()

    pdf.setFillColor(colors.HexColor("#003B8F"))
    pdf.rect(0, altura - 105, largura, 105, fill=True, stroke=False)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(
        40,
        altura - 42,
        "EVOLUÇÃO MENSAL DOS INDICADORES"
    )

    pdf.setFont("Helvetica", 11)
    pdf.drawString(
        40,
        altura - 66,
        f"Ano: {preview['ano']} • Período: {_periodo(preview.get('meses', []))}"
    )
    contexto = _contexto_filtros(preview)

    _desenhar_contexto_cabecalho(
        pdf,
        preview,
        contexto,
        largura,
        altura,
        paisagem=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=False
    )

    evolucao = preview.get("evolucao_mensal", {})

    graf_matriculas = evolucao.get("matriculas", {})
    graf_ha = evolucao.get("hora_aluno", {})
    graf_receita = evolucao.get("receita", {})

    _grafico_colunas_comparativo(
        pdf,
        40,
        altura - 295,
        largura - 80,
        160,
        "Evolução Mensal • Matrículas",
        graf_matriculas.get("realizado", []),
        graf_matriculas.get("meta", [])
    )

    _grafico_colunas_comparativo(
        pdf,
        40,
        altura - 480,
        largura - 80,
        160,
        "Evolução Mensal • Hora-Aluno",
        graf_ha.get("realizado", []),
        graf_ha.get("meta", [])
    )

    _grafico_colunas_comparativo(
        pdf,
        40,
        altura - 665,
        largura - 80,
        160,
        "Evolução Mensal • Receita",
        graf_receita.get("realizado", []),
        graf_receita.get("meta", []),
        eh_moeda=True
    )

    # Rodapé página 2
    pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
    pdf.line(40, 42, largura - 40, 42)

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(40, 28, "Painel Executivo SENAI • Relatório gerado automaticamente")
    pdf.drawRightString(largura - 40, 28, "Página 2")

    numero_pagina = 3

    modo_relatorio = preview.get("modo_relatorio")

    tem_programa = bool(preview.get("programa"))
    tem_regiao = bool(preview.get("regiao"))
    tem_subregiao = bool(preview.get("subregiao"))
    tem_uo = bool(preview.get("uo"))

    pular_regioes = modo_relatorio in [
        "regiao",
        "subregiao",
        "uo",
        "programa_regiao",
        "programa_subregiao",
    ]

    pular_subregioes = modo_relatorio in [
        "subregiao",
        "uo",
        "programa_subregiao",
    ]

    mostrar_regiao_subregiao_uo = tem_uo

    pular_programas = tem_programa

    # Página 3 — Regiões
    if not pular_regioes:
        pdf.showPage()
        pdf.setPageSize(landscape(A4))
        largura, altura = landscape(A4)

        pdf.setFillColor(colors.HexColor("#003B8F"))
        pdf.rect(0, altura - 80, largura, 80, fill=True, stroke=False)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 17)
        pdf.drawString(40, altura - 35, "DESEMPENHO DAS REGIÕES")

        pdf.setFont("Helvetica", 10)
        pdf.drawString(
            40,
            altura - 58,
            f"Ano: {preview['ano']} • Período: {_periodo(preview.get('meses', []))}"
        )

        contexto = _contexto_filtros(preview)

        _desenhar_contexto_cabecalho(
            pdf,
            preview,
            contexto,
            largura,
            altura,
            paisagem=True
        )

        _desenhar_logo_cabecalho(
            pdf,
            largura,
            altura,
            paisagem=True
        )

        regioes = preview.get("desempenho_regioes", [])

        if not regioes:
            regioes = preview.get("desempenho_regiao_uo", [])

        y3 = altura - 115

        pdf.setFillColor(colors.HexColor("#071b52"))
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(40, y3, "Resumo por Região")

        y3 -= 26

        colunas = [
            ("Região", 120),

            ("Meta Mat.", 65),
            ("Real. Mat.", 65),
            ("%", 50),

            ("Meta HA", 75),
            ("Real. HA", 75),
            ("%", 50),

            ("Meta Receita", 85),
            ("Real. Receita", 85),
            ("%", 55),
        ]

        x_inicio = 35
        altura_linha = 24

        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.roundRect(
            x_inicio,
            y3 - 8,
            largura - 70,
            altura_linha,
            8,
            fill=True,
            stroke=False
        )

        pdf.setFillColor(colors.HexColor("#071b52"))
        pdf.setFont("Helvetica-Bold", 6.5)

        x = x_inicio
        for titulo, w in colunas:
            pdf.drawString(x + 4, y3 + 2, titulo.upper())
            x += w

        y3 -= altura_linha

        for i, item in enumerate(regioes):
            if y3 < 95:
                break

            pdf.setFillColor(
                colors.HexColor("#ffffff") if i % 2 == 0 else colors.HexColor("#f8fafc")
            )
            pdf.roundRect(
                x_inicio,
                y3 - 6,
                largura - 70,
                altura_linha,
                0,
                fill=True,
                stroke=False
            )

            valores = [
                item.get("regiao", "-"),

                _num(item.get("matriculas_meta", 0)),
                _num(item.get("matriculas_real", 0)),
                {
                    "pct": item.get("matriculas_pct", 0),
                    "real": item.get("matriculas_real", 0),
                    "meta": item.get("matriculas_meta", 0),
                },

                _num(item.get("hora_aluno_meta", 0)),
                _num(item.get("hora_aluno_real", 0)),
                {
                    "pct": item.get("hora_aluno_pct", 0),
                    "real": item.get("hora_aluno_real", 0),
                    "meta": item.get("hora_aluno_meta", 0),
                },

                _moeda(item.get("receita_meta", 0)),
                _moeda(item.get("receita_real", 0)),
                {
                    "pct": item.get("receita_pct", 0),
                    "real": item.get("receita_real", 0),
                    "meta": item.get("receita_meta", 0),
                },
            ]

            x = x_inicio

            for idx, (valor, (_, w)) in enumerate(zip(valores, colunas)):
                if idx == 0:
                    pdf.setFillColor(colors.HexColor("#071b52"))
                    pdf.setFont("Helvetica-Bold", 6.8)
                    texto = str(valor)

                    if len(texto) > 23:
                        texto = texto[:20] + "..."

                elif isinstance(valor, dict):
                    pct = valor["pct"]
                    real = valor["real"]
                    meta = valor["meta"]

                    pdf.setFillColor(_cor_status_pct(pct, meta, real))
                    pdf.setFont("Helvetica-Bold", 6.8)

                    if float(meta or 0) <= 0 and float(real or 0) <= 0:
                        texto = "-"
                    elif float(meta or 0) <= 0 and float(real or 0) > 0:
                        texto = "*"
                    else:
                        texto = _pct(pct)

                else:
                    pdf.setFillColor(colors.HexColor("#334155"))
                    pdf.setFont("Helvetica", 6.2)
                    texto = str(valor)

                pdf.drawString(x + 4, y3 + 2, texto)
                x += w

            y3 -= altura_linha

        y3 -= 20
        _legenda_status(pdf, 40, y3)

        pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
        pdf.line(40, 34, largura - 40, 34)

        pdf.setFillColor(colors.HexColor("#64748b"))
        pdf.setFont("Helvetica", 7)
        pdf.drawString(40, 22, "Painel Executivo SENAI • Relatório gerado automaticamente")
        pdf.drawRightString(largura - 40, 22, f"Página {numero_pagina}")

        numero_pagina += 1

    # Página 4 — Sub-regiões
    if not pular_subregioes:
        pdf.showPage()
        pdf.setPageSize(landscape(A4))
        largura, altura = landscape(A4)

        pdf.setFillColor(colors.HexColor("#003B8F"))
        pdf.rect(0, altura - 80, largura, 80, fill=True, stroke=False)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 17)
        pdf.drawString(40, altura - 35, "DESEMPENHO DAS SUB-REGIÕES")

        pdf.setFont("Helvetica", 10)
        pdf.drawString(
            40,
            altura - 58,
            f"Ano: {preview['ano']} • Período: {_periodo(preview.get('meses', []))}"
        )

        contexto = _contexto_filtros(preview)

        _desenhar_contexto_cabecalho(
            pdf,
            preview,
            contexto,
            largura,
            altura,
            paisagem=True
        )

        _desenhar_logo_cabecalho(
            pdf,
            largura,
            altura,
            paisagem=True
        )

        subregioes = preview.get("desempenho_subregioes", [])

        y4 = altura - 115

        pdf.setFillColor(colors.HexColor("#071b52"))
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(40, y4, "Resumo por Sub-região")

        y4 -= 26

        colunas = [
            ("Sub-região", 120),

            ("Meta Mat.", 65),
            ("Real. Mat.", 65),
            ("%", 50),

            ("Meta HA", 75),
            ("Real. HA", 75),
            ("%", 50),

            ("Meta Receita", 85),
            ("Real. Receita", 85),
            ("%", 55),
        ]

        x_inicio = 35
        altura_linha = 18

        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.roundRect(
            x_inicio,
            y4 - 8,
            largura - 70,
            altura_linha,
            8,
            fill=True,
            stroke=False
        )

        pdf.setFillColor(colors.HexColor("#071b52"))
        pdf.setFont("Helvetica-Bold", 6.5)

        x = x_inicio
        for titulo, w in colunas:
            pdf.drawString(x + 4, y4 + 2, titulo.upper())
            x += w

        y4 -= altura_linha

        for i, item in enumerate(subregioes):
            if y4 < 78:
                break

            pdf.setFillColor(
                colors.HexColor("#ffffff") if i % 2 == 0 else colors.HexColor("#f8fafc")
            )

            pdf.roundRect(
                x_inicio,
                y4 - 6,
                largura - 70,
                altura_linha,
                0,
                fill=True,
                stroke=False
            )

            valores = [
                item.get("subregiao", "-"),

                _num(item.get("matriculas_meta", 0)),
                _num(item.get("matriculas_real", 0)),
                {
                    "pct": item.get("matriculas_pct", 0),
                    "real": item.get("matriculas_real", 0),
                    "meta": item.get("matriculas_meta", 0),
                },

                _num(item.get("hora_aluno_meta", 0)),
                _num(item.get("hora_aluno_real", 0)),
                {
                    "pct": item.get("hora_aluno_pct", 0),
                    "real": item.get("hora_aluno_real", 0),
                    "meta": item.get("hora_aluno_meta", 0),
                },

                _moeda(item.get("receita_meta", 0)),
                _moeda(item.get("receita_real", 0)),
                {
                    "pct": item.get("receita_pct", 0),
                    "real": item.get("receita_real", 0),
                    "meta": item.get("receita_meta", 0),
                },
            ]

            x = x_inicio

            for idx, (valor, (_, w)) in enumerate(zip(valores, colunas)):
                if idx == 0:
                    pdf.setFillColor(colors.HexColor("#071b52"))
                    pdf.setFont("Helvetica-Bold", 6.5)
                    texto = str(valor)

                    if len(texto) > 23:
                        texto = texto[:20] + "..."

                elif isinstance(valor, dict):
                    pct = valor["pct"]
                    real = valor["real"]
                    meta = valor["meta"]

                    pdf.setFillColor(_cor_status_pct(pct, meta, real))
                    pdf.setFont("Helvetica-Bold", 6.6)

                    if float(meta or 0) <= 0 and float(real or 0) <= 0:
                        texto = "-"
                    elif float(meta or 0) <= 0 and float(real or 0) > 0:
                        texto = "*"
                    else:
                        texto = _pct(pct)

                else:
                    pdf.setFillColor(colors.HexColor("#334155"))
                    pdf.setFont("Helvetica", 6.1)
                    texto = str(valor)

                pdf.drawString(x + 4, y4 + 2, texto)
                x += w

            y4 -= altura_linha

        y4 -= 12

        if y4 < 72:
            y4 = 72

        _legenda_status(pdf, 40, y4)

        pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
        pdf.line(40, 34, largura - 40, 34)

        pdf.setFillColor(colors.HexColor("#64748b"))
        pdf.setFont("Helvetica", 7)
        pdf.drawString(40, 22, "Painel Executivo SENAI • Relatório gerado automaticamente")
        pdf.drawRightString(largura - 40, 22, f"Página {numero_pagina}")

        numero_pagina += 1
    
    # Página — Região e Sub-região da UO
    if mostrar_regiao_subregiao_uo:
        pdf.showPage()
        pdf.setPageSize(landscape(A4))
        largura, altura = landscape(A4)

        pdf.setFillColor(colors.HexColor("#003B8F"))
        pdf.rect(0, altura - 80, largura, 80, fill=True, stroke=False)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 17)
        pdf.drawString(40, altura - 35, "DESEMPENHO DA REGIÃO E DA SUB-REGIÃO")

        pdf.setFont("Helvetica", 10)
        pdf.drawString(
            40,
            altura - 58,
            f"Ano: {preview['ano']} • Período: {_periodo(preview.get('meses', []))}"
        )

        contexto = _contexto_filtros(preview)

        _desenhar_contexto_cabecalho(
            pdf,
            preview,
            contexto,
            largura,
            altura,
            paisagem=True
        )

        _desenhar_logo_cabecalho(
            pdf,
            largura,
            altura,
            paisagem=True
        )

        colunas = [
            ("Nome", 170),
            ("Meta Mat.", 70),
            ("Real. Mat.", 70),
            ("%", 45),
            ("Meta HA", 80),
            ("Real. HA", 80),
            ("%", 45),
            ("Meta Receita", 90),
            ("Real. Receita", 90),
            ("%", 45),
        ]

        def desenhar_tabela_resumo(titulo, dados, campo_nome, y):
            pdf.setFillColor(colors.HexColor("#071b52"))
            pdf.setFont("Helvetica-Bold", 13)
            pdf.drawString(40, y, titulo)

            y -= 26

            x_inicio = 35
            altura_linha = 24

            pdf.setFillColor(colors.HexColor("#f8fafc"))
            pdf.roundRect(
                x_inicio,
                y - 8,
                largura - 70,
                altura_linha,
                8,
                fill=True,
                stroke=False
            )

            pdf.setFillColor(colors.HexColor("#071b52"))
            pdf.setFont("Helvetica-Bold", 6.5)

            x = x_inicio
            for titulo_coluna, w in colunas:
                pdf.drawString(x + 4, y + 2, titulo_coluna.upper())
                x += w

            y -= altura_linha

            for i, item in enumerate(dados):
                pdf.setFillColor(
                    colors.HexColor("#ffffff") if i % 2 == 0 else colors.HexColor("#f8fafc")
                )

                pdf.roundRect(
                    x_inicio,
                    y - 6,
                    largura - 70,
                    altura_linha,
                    0,
                    fill=True,
                    stroke=False
                )

                valores = [
                    item.get(campo_nome, "-"),

                    _num(item.get("matriculas_meta", 0)),
                    _num(item.get("matriculas_real", 0)),
                    {
                        "pct": item.get("matriculas_pct", 0),
                        "real": item.get("matriculas_real", 0),
                        "meta": item.get("matriculas_meta", 0),
                    },

                    _num(item.get("hora_aluno_meta", 0)),
                    _num(item.get("hora_aluno_real", 0)),
                    {
                        "pct": item.get("hora_aluno_pct", 0),
                        "real": item.get("hora_aluno_real", 0),
                        "meta": item.get("hora_aluno_meta", 0),
                    },

                    _moeda(item.get("receita_meta", 0)),
                    _moeda(item.get("receita_real", 0)),
                    {
                        "pct": item.get("receita_pct", 0),
                        "real": item.get("receita_real", 0),
                        "meta": item.get("receita_meta", 0),
                    },
                ]

                x = x_inicio

                for idx, (valor, (_, w)) in enumerate(zip(valores, colunas)):
                    if idx == 0:
                        pdf.setFillColor(colors.HexColor("#071b52"))
                        pdf.setFont("Helvetica-Bold", 6.8)
                        texto = str(valor)

                    elif isinstance(valor, dict):
                        pct = valor["pct"]
                        real = valor["real"]
                        meta = valor["meta"]

                        pdf.setFillColor(_cor_status_pct(pct, meta, real))
                        pdf.setFont("Helvetica-Bold", 6.8)

                        if float(meta or 0) <= 0 and float(real or 0) <= 0:
                            texto = "-"
                        elif float(meta or 0) <= 0 and float(real or 0) > 0:
                            texto = "*"
                        else:
                            texto = _pct(pct)

                    else:
                        pdf.setFillColor(colors.HexColor("#334155"))
                        pdf.setFont("Helvetica", 6.2)
                        texto = str(valor)

                    pdf.drawString(x + 4, y + 2, texto)
                    x += w

                y -= altura_linha

            return y

        regiao_uo = preview.get("regiao_uo")
        subregiao_uo = preview.get("subregiao_uo")

        regioes = preview.get("desempenho_regiao_uo", [])

        subregioes = preview.get("desempenho_subregiao_uo", [])

        y = altura - 115

        y = desenhar_tabela_resumo(
            "Região Vinculada à UO",
            regioes[:1],
            "regiao",
            y
        )

        y -= 40

        y = desenhar_tabela_resumo(
            "Sub-região Vinculada à UO",
            subregioes[:1],
            "subregiao",
            y
        )

        y -= 30

        if y < 72:
            y = 72

        _legenda_status(pdf, 40, y)

        pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
        pdf.line(40, 34, largura - 40, 34)

        pdf.setFillColor(colors.HexColor("#64748b"))
        pdf.setFont("Helvetica", 7)
        pdf.drawString(40, 22, "Painel Executivo SENAI • Relatório gerado automaticamente")
        pdf.drawRightString(largura - 40, 22, f"Página {numero_pagina}")

        numero_pagina += 1

    # Página 5
    pdf.showPage()
    pdf.setPageSize(landscape(A4))
    largura, altura = landscape(A4)

    pdf.setFillColor(colors.HexColor("#003B8F"))
    pdf.rect(0, altura - 80, largura, 80, fill=True, stroke=False)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(40, altura - 35, "DESEMPENHO DAS MODALIDADES")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        40,
        altura - 58,
        f"Ano: {preview['ano']} • Período: {_periodo(preview.get('meses', []))}"
    )

    contexto = _contexto_filtros(preview)

    _desenhar_contexto_cabecalho(
        pdf,
        preview,
        contexto,
        largura,
        altura,
        paisagem=True
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=True
    )

    modalidades = preview.get("desempenho_modalidades", [])

    y5 = altura - 115

    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, y5, "Resumo por Modalidade")

    y5 -= 26

    colunas = [
        ("Modalidade", 190),

        ("Meta Mat.", 65),
        ("Real. Mat.", 65),
        ("%", 50),

        ("Meta HA", 75),
        ("Real. HA", 75),
        ("%", 50),

        ("Meta Receita", 70),
        ("Real. Receita", 70),
        ("%", 45),
    ]

    x_inicio = 35
    altura_linha = 22

    pdf.setFillColor(colors.HexColor("#f8fafc"))
    pdf.roundRect(
        x_inicio,
        y5 - 8,
        largura - 70,
        altura_linha,
        8,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 6.5)

    x = x_inicio
    for titulo, w in colunas:
        pdf.drawString(x + 4, y5 + 2, titulo.upper())
        x += w

    y5 -= altura_linha

    for i, item in enumerate(modalidades):
        if y5 < 88:
            break

        pdf.setFillColor(
            colors.HexColor("#ffffff") if i % 2 == 0 else colors.HexColor("#f8fafc")
        )

        pdf.roundRect(
            x_inicio,
            y5 - 6,
            largura - 70,
            altura_linha,
            0,
            fill=True,
            stroke=False
        )

        valores = [
            item.get("modalidade", "-"),

            _num(item.get("matriculas_meta", 0)),
            _num(item.get("matriculas_real", 0)),
            {
                "pct": item.get("matriculas_pct", 0),
                "real": item.get("matriculas_real", 0),
                "meta": item.get("matriculas_meta", 0),
            },

            _num(item.get("hora_aluno_meta", 0)),
            _num(item.get("hora_aluno_real", 0)),
            {
                "pct": item.get("hora_aluno_pct", 0),
                "real": item.get("hora_aluno_real", 0),
                "meta": item.get("hora_aluno_meta", 0),
            },

            _moeda(item.get("receita_meta", 0)),
            _moeda(item.get("receita_real", 0)),
            {
                "pct": item.get("receita_pct", 0),
                "real": item.get("receita_real", 0),
                "meta": item.get("receita_meta", 0),
            },
        ]

        x = x_inicio

        for idx, (valor, (_, w)) in enumerate(zip(valores, colunas)):
            if idx == 0:
                pdf.setFillColor(colors.HexColor("#071b52"))
                pdf.setFont("Helvetica-Bold", 6.4)
                texto = str(valor)

            elif isinstance(valor, dict):
                pct = valor["pct"]
                real = valor["real"]
                meta = valor["meta"]

                pdf.setFillColor(_cor_status_pct(pct, meta, real))
                pdf.setFont("Helvetica-Bold", 6.6)

                if float(meta or 0) <= 0 and float(real or 0) <= 0:
                    texto = "-"
                elif float(meta or 0) <= 0 and float(real or 0) > 0:
                    texto = "*"
                else:
                    texto = _pct(pct)

            else:
                pdf.setFillColor(colors.HexColor("#334155"))
                pdf.setFont("Helvetica", 6.1)
                texto = str(valor)

            pdf.drawString(x + 4, y5 + 2, texto)
            x += w

        y5 -= altura_linha

    y5 -= 18

    if y5 < 72:
        y5 = 72

    _legenda_status(pdf, 40, y5)

    pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
    pdf.line(40, 34, largura - 40, 34)

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 7)
    pdf.drawString(40, 22, "Painel Executivo SENAI • Relatório gerado automaticamente")
    pdf.drawRightString(largura - 40, 22, f"Página {numero_pagina}")

    numero_pagina += 1

    # Página 6
    if not pular_programas:
        pdf.showPage()
        pdf.setPageSize(landscape(A4))
        largura, altura = landscape(A4)

        pdf.setFillColor(colors.HexColor("#003B8F"))
        pdf.rect(0, altura - 80, largura, 80, fill=True, stroke=False)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 17)
        pdf.drawString(40, altura - 35, "DESEMPENHO DOS PROGRAMAS")

        pdf.setFont("Helvetica", 10)
        pdf.drawString(
            40,
            altura - 58,
            f"Ano: {preview['ano']} • Período: {_periodo(preview.get('meses', []))}"
        )

        contexto = _contexto_filtros(preview)

        _desenhar_contexto_cabecalho(
            pdf,
            preview,
            contexto,
            largura,
            altura,
            paisagem=True
        )

        _desenhar_logo_cabecalho(
            pdf,
            largura,
            altura,
            paisagem=True
        )

        programas = preview.get("desempenho_programas", [])

        y6 = altura - 115

        pdf.setFillColor(colors.HexColor("#071b52"))
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(40, y6, "Resumo por Programa")

        y6 -= 26

        colunas = [
            ("Programa", 190),

            ("Meta Mat.", 65),
            ("Real. Mat.", 65),
            ("%", 50),

            ("Meta HA", 75),
            ("Real. HA", 75),
            ("%", 50),

            ("Meta Receita", 70),
            ("Real. Receita", 70),
            ("%", 45),
        ]

        x_inicio = 35
        altura_linha = 18

        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.roundRect(
            x_inicio,
            y6 - 8,
            largura - 70,
            altura_linha,
            8,
            fill=True,
            stroke=False
        )

        pdf.setFillColor(colors.HexColor("#071b52"))
        pdf.setFont("Helvetica-Bold", 6.4)

        x = x_inicio
        for titulo, w in colunas:
            pdf.drawString(x + 4, y6 + 1, titulo.upper())
            x += w

        y6 -= altura_linha

        for i, item in enumerate(programas):
            if y6 < 135:
                pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
                pdf.line(40, 34, largura - 40, 34)

                pdf.setFillColor(colors.HexColor("#64748b"))
                pdf.setFont("Helvetica", 7)
                pdf.drawString(40, 22, "Painel Executivo SENAI • Relatório gerado automaticamente")
                pdf.drawRightString(largura - 40, 22, f"Página {numero_pagina}")

                numero_pagina += 1

                pdf.showPage()
                pdf.setPageSize(landscape(A4))
                largura, altura = landscape(A4)

                pdf.setFillColor(colors.HexColor("#003B8F"))
                pdf.rect(0, altura - 80, largura, 80, fill=True, stroke=False)

                pdf.setFillColor(colors.white)
                pdf.setFont("Helvetica-Bold", 17)
                pdf.drawString(40, altura - 35, "DESEMPENHO DOS PROGRAMAS")

                pdf.setFont("Helvetica", 10)
                pdf.drawString(
                    40,
                    altura - 58,
                    f"Ano: {preview['ano']} • Período: {_periodo(preview.get('meses', []))}"
                )

                contexto = _contexto_filtros(preview)

                _desenhar_contexto_cabecalho(
                    pdf,
                    preview,
                    contexto,
                    largura,
                    altura,
                    paisagem=True
                )

                _desenhar_logo_cabecalho(
                    pdf,
                    largura,
                    altura,
                    paisagem=True
                )

                y6 = altura - 115

                pdf.setFillColor(colors.HexColor("#071b52"))
                pdf.setFont("Helvetica-Bold", 13)
                pdf.drawString(40, y6, "Resumo por Programa - continuação")

                y6 -= 26

                pdf.setFillColor(colors.HexColor("#f8fafc"))
                pdf.roundRect(
                    x_inicio,
                    y6 - 8,
                    largura - 70,
                    altura_linha,
                    8,
                    fill=True,
                    stroke=False
                )

                pdf.setFillColor(colors.HexColor("#071b52"))
                pdf.setFont("Helvetica-Bold", 6.4)

                x = x_inicio
                for titulo, w in colunas:
                    pdf.drawString(x + 4, y6 + 1, titulo.upper())
                    x += w

                y6 -= altura_linha

            pdf.setFillColor(
                colors.HexColor("#ffffff") if i % 2 == 0 else colors.HexColor("#f8fafc")
            )

            pdf.roundRect(
                x_inicio,
                y6 - 6,
                largura - 70,
                altura_linha,
                0,
                fill=True,
                stroke=False
            )

            valores = [
                item.get("programa", "-"),

                _num(item.get("matriculas_meta", 0)),
                _num(item.get("matriculas_real", 0)),
                {
                    "pct": item.get("matriculas_pct", 0),
                    "real": item.get("matriculas_real", 0),
                    "meta": item.get("matriculas_meta", 0),
                },

                _num(item.get("hora_aluno_meta", 0)),
                _num(item.get("hora_aluno_real", 0)),
                {
                    "pct": item.get("hora_aluno_pct", 0),
                    "real": item.get("hora_aluno_real", 0),
                    "meta": item.get("hora_aluno_meta", 0),
                },

                _moeda(item.get("receita_meta", 0)),
                _moeda(item.get("receita_real", 0)),
                {
                    "pct": item.get("receita_pct", 0),
                    "real": item.get("receita_real", 0),
                    "meta": item.get("receita_meta", 0),
                },
            ]

            x = x_inicio

            for idx, (valor, (_, w)) in enumerate(zip(valores, colunas)):
                if idx == 0:
                    pdf.setFillColor(colors.HexColor("#071b52"))
                    pdf.setFont("Helvetica-Bold", 5.9)
                    texto = str(valor)

                elif isinstance(valor, dict):
                    pct = valor["pct"]
                    real = valor["real"]
                    meta = valor["meta"]

                    pdf.setFillColor(_cor_status_pct(pct, meta, real))
                    pdf.setFont("Helvetica-Bold", 6.2)

                    if float(meta or 0) <= 0 and float(real or 0) <= 0:
                        texto = "-"
                    elif float(meta or 0) <= 0 and float(real or 0) > 0:
                        texto = "*"
                    else:
                        texto = _pct(pct)

                else:
                    pdf.setFillColor(colors.HexColor("#334155"))
                    pdf.setFont("Helvetica", 5.8)
                    texto = str(valor)

                pdf.drawString(x + 4, y6 + 1, texto)
                x += w

            y6 -= altura_linha

        y6 -= 14

        if y6 < 72:
            y6 = 72

        _legenda_status(pdf, 40, y6)

        pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
        pdf.line(40, 34, largura - 40, 34)

        pdf.setFillColor(colors.HexColor("#64748b"))
        pdf.setFont("Helvetica", 7)
        pdf.drawString(40, 22, "Painel Executivo SENAI • Relatório gerado automaticamente")
        pdf.drawRightString(largura - 40, 22, f"Página {numero_pagina}")

        numero_pagina += 1

    # Página — Ações Executivas da Sub-região
    acoes = preview.get("acoes_executivas", [])

    if preview.get("programa") or preview.get("subregiao") or preview.get("regiao") or preview.get("uo"):
        pdf.showPage()
        pdf.setPageSize(landscape(A4))
        largura, altura = landscape(A4)

        pdf.setFillColor(colors.HexColor("#003B8F"))
        pdf.rect(0, altura - 80, largura, 80, fill=True, stroke=False)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 17)
        pdf.drawString(40, altura - 35, "AÇÕES EXECUTIVAS")

        pdf.setFont("Helvetica", 10)
        pdf.drawString(
            40,
            altura - 58,
            f"Ano: {preview['ano']} • Período: {_periodo(preview.get('meses', []))}"
        )

        contexto = _contexto_filtros(preview)

        _desenhar_contexto_cabecalho(
            pdf,
            preview,
            contexto,
            largura,
            altura,
            paisagem=True
        )

        _desenhar_logo_cabecalho(
            pdf,
            largura,
            altura,
            paisagem=True
        )

        y = altura - 115

        pdf.setFillColor(colors.HexColor("#071b52"))
        pdf.setFont("Helvetica-Bold", 13)

        if preview.get("uo"):
            titulo_acoes = "Ações Vinculadas à UO"
        elif preview.get("subregiao"):
            titulo_acoes = "Ações Vinculadas à Sub-Região"
        elif preview.get("regiao"):
            titulo_acoes = "Ações Vinculadas à Região"
        else:
            titulo_acoes = "Ações Executivas"

        pdf.drawString(40, y, titulo_acoes)

        y -= 26

        colunas = [
            ("Programa", 100),
            ("UO", 110),
            ("Tipo", 70),
            ("Ação", 100),
            ("Responsável", 90),
            ("Prazo", 55),
            ("Status", 70),
            ("Observação", 110),
        ]

        x_inicio = 35
        altura_linha = 34

        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.roundRect(
            x_inicio,
            y - 8,
            largura - 70,
            22,
            8,
            fill=True,
            stroke=False
        )

        pdf.setFillColor(colors.HexColor("#071b52"))
        pdf.setFont("Helvetica-Bold", 6.7)

        x = x_inicio
        for titulo, w in colunas:
            pdf.drawString(x + 4, y, titulo.upper())
            x += w

        y -= 24

        if not acoes:
            pdf.setFillColor(colors.HexColor("#64748b"))
            pdf.setFont("Helvetica", 10)

            if preview.get("uo"):
                mensagem = "Não há ações executivas cadastradas para a UO selecionada."
            elif preview.get("subregiao"):
                mensagem = "Não há ações executivas cadastradas para a sub-região selecionada."
            elif preview.get("regiao"):
                mensagem = "Não há ações executivas cadastradas para a região selecionada."
            elif preview.get("programa"):
                mensagem = "Não há ações executivas cadastradas para o programa selecionado."
            else:
                mensagem = "Não há ações executivas cadastradas para o filtro selecionado."

            pdf.drawString(
                40,
                y,
                mensagem
            )
        else:
            for i, acao in enumerate(acoes):
                if y < 78:
                    break

                pdf.setFillColor(
                    colors.HexColor("#ffffff") if i % 2 == 0 else colors.HexColor("#f8fafc")
                )

                pdf.roundRect(
                    x_inicio,
                    y - 20,
                    largura - 70,
                    altura_linha,
                    0,
                    fill=True,
                    stroke=False
                )

                valores = [
                    acao.get("programa", "-"),
                    acao.get("uo", "-"),
                    acao.get("tipo_acao", "-"),
                    acao.get("titulo", "-"),
                    acao.get("responsavel", "-"),
                    acao.get("data_prevista", "-"),
                    acao.get("status", "-"),
                    acao.get("evidencia") or acao.get("descricao", "-"),
                ]

                x = x_inicio

                for valor, (_, w) in zip(valores, colunas):
                    texto = str(valor or "-")

                    linhas = simpleSplit(
                        texto,
                        "Helvetica",
                        6.2,
                        w - 8
                    )

                    pdf.setFillColor(colors.HexColor("#334155"))
                    pdf.setFont("Helvetica", 6.2)

                    linha_y = y + 2

                    for linha in linhas[:2]:
                        pdf.drawString(x + 4, linha_y, linha)
                        linha_y -= 8

                    x += w

                y -= altura_linha

        pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
        pdf.line(40, 34, largura - 40, 34)

        pdf.setFillColor(colors.HexColor("#64748b"))
        pdf.setFont("Helvetica", 7)
        pdf.drawString(40, 22, "Painel Executivo SENAI • Relatório gerado automaticamente")
        pdf.drawRightString(largura - 40, 22, f"Página {numero_pagina}")

        numero_pagina += 1

    pdf.save()
    buffer.seek(0)

    return buffer

def gerar_pdf_relatorio_desempenho_programa(
    preview,
    orientacao="retrato"
):
    """
    Gera o Relatório de Desempenho por Programa.

    Nesta primeira etapa, cria apenas uma página de teste
    para validar a separação da geração do PDF.
    """

    buffer = BytesIO()

    pagina = landscape(A4) if orientacao == "paisagem" else A4
    pdf = canvas.Canvas(buffer, pagesize=pagina)

    largura, altura = pagina

    cabecalho = preview.get(
        "cabecalho_desempenho_programa",
        {}
    )

    modo_programa = preview.get(
        "modo_desempenho_programa"
    )

    if modo_programa == "multiplos_programas":
        programa = "Todos os Programas"
    else:
        programa = (
            cabecalho.get("programa")
            or preview.get("programa")
            or "Não informado"
        )

    # Cabeçalho azul — somente com o logo
    altura_cabecalho = 82

    pdf.setFillColor(colors.HexColor("#003B8F"))
    pdf.rect(
        0,
        altura - altura_cabecalho,
        largura,
        altura_cabecalho,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )

    # Corpo do relatório
    y = altura - 125

    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(
        40,
        y,
        "RELATÓRIO DE DESEMPENHO POR PROGRAMA"
    )

    y -= 30

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        40,
        y,
        f"Ano: {preview.get('ano')} • "
        f"Período: {_periodo(preview.get('meses', []))}"
    )

    y -= 42

    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(
        40,
        y,
        "PROGRAMA"
    )

    y -= 18

    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        40,
        y,
        str(programa)
    )

    # ======================================================
    # REGIÃO / SUB-REGIÃO CONFORME FILTROS SELECIONADOS
    # ======================================================

    if preview.get("regiao"):
        regiao = preview.get("regiao")
    else:
        regiao = "TODAS AS REGIÕES"


    if preview.get("subregiao"):
        subregiao = preview.get("subregiao")
    else:
        subregiao = "TODAS AS SUB-REGIÕES"
    geope = cabecalho.get("geope") or "Não informado"
    uos = sorted(
        [
            str(nome_uo).strip().upper()
            for nome_uo in (cabecalho.get("uos") or [])
            if str(nome_uo).strip()
        ],
        key=lambda nome: nome.casefold()
    )

    # Posição inicial das duas colunas
    y_bloco = y - 42

    x_esquerda = 40
    x_direita = 260

    largura_coluna_esquerda = 180
    largura_coluna_direita = 300

    # ======================================================
    # COLUNA ESQUERDA
    # ======================================================

    y_esquerda = y_bloco

    # Região
    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(
        x_esquerda,
        y_esquerda,
        "REGIÃO"
    )

    y_esquerda -= 16

    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.setFont("Helvetica", 10)

    linhas_regiao = simpleSplit(
        str(regiao),
        "Helvetica",
        10,
        largura_coluna_esquerda
    )

    for linha in linhas_regiao:
        pdf.drawString(
            x_esquerda,
            y_esquerda,
            linha
        )
        y_esquerda -= 14

    y_esquerda -= 24

    # GEOPE
    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(
        x_esquerda,
        y_esquerda,
        "GEOPE"
    )

    y_esquerda -= 16

    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.setFont("Helvetica", 10)

    linhas_geope = simpleSplit(
        str(geope),
        "Helvetica",
        10,
        largura_coluna_esquerda
    )

    for linha in linhas_geope:
        pdf.drawString(
            x_esquerda,
            y_esquerda,
            linha
        )
        y_esquerda -= 14

    # ======================================================
    # COLUNA DIREITA
    # ======================================================

    y_direita = y_bloco

    # Sub-região
    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(
        x_direita,
        y_direita,
        "SUB-REGIÃO"
    )

    y_direita -= 16

    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.setFont("Helvetica", 10)

    linhas_subregiao = simpleSplit(
        str(subregiao),
        "Helvetica",
        10,
        largura_coluna_direita
    )

    for linha in linhas_subregiao:
        pdf.drawString(
            x_direita,
            y_direita,
            linha
        )
        y_direita -= 14

    y_direita -= 24

    # Unidades Operacionais
    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(
        x_direita,
        y_direita,
        "UNIDADES OPERACIONAIS"
    )

    y_direita -= 18

    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.setFont("Helvetica", 9)

    # Guarda as UOs que não couberem na primeira página
    uos_continuacao = []

    # ======================================================
    # CALCULA SE TODAS AS UOs CABEM NA PÁGINA 1
    # JUNTO COM VISÃO GERAL + CARDS
    # ======================================================

    altura_total_uos = 0

    for nome_uo_calculo in uos:

        texto_calculo = f"• {nome_uo_calculo}"

        linhas_calculo = simpleSplit(
            texto_calculo,
            "Helvetica",
            9,
            largura_coluna_direita
        )

        altura_total_uos += (
            len(linhas_calculo) * 14
        ) + 3


    # Se todas as UOs couberem deixando espaço
    # para Visão Geral + cards, mantém o resumo na página 1.
    # Caso contrário, aproveita a página até perto do rodapé.
    espaco_disponivel_com_resumo = y_direita - 300

    if altura_total_uos <= espaco_disponivel_com_resumo:
        limite_inferior_uos = 300
    else:
        limite_inferior_uos = 65

    if uos:
        for indice_uo, nome_uo in enumerate(uos):

            texto = f"• {nome_uo}"

            linhas = simpleSplit(
                texto,
                "Helvetica",
                9,
                largura_coluna_direita
            )

            # Altura necessária para esta UO
            altura_necessaria = (len(linhas) * 14) + 3
            
            if y_direita - altura_necessaria < limite_inferior_uos:

                # Esta UO e todas as seguintes vão para a página seguinte
                uos_continuacao = uos[indice_uo:]
                break

            for linha in linhas:
                pdf.drawString(
                    x_direita,
                    y_direita,
                    linha
                )
                y_direita -= 14

            y_direita -= 3

    else:
        pdf.drawString(
            x_direita,
            y_direita,
            "Nenhuma unidade operacional encontrada."
        )

    # Próxima posição disponível abaixo das duas colunas
    y = min(
        y_esquerda,
        y_direita
    ) - 35

    mover_resumo = bool(uos_continuacao)

    # ======================================================
    # VISÃO GERAL
    # ======================================================

    meses_relatorio = preview.get("meses", []) or []
    periodo_relatorio = _periodo(meses_relatorio)

    texto_periodo = periodo_relatorio.lower()

    if len(meses_relatorio) == 1:
        complemento_periodo = f"em {texto_periodo}"
    else:
        complemento_periodo = f"no período de {texto_periodo}"

    if modo_programa == "multiplos_programas":
        texto_visao_geral = (
            f"Este relatório apresenta uma análise consolidada dos programas "
            f"selecionados, contemplando os principais indicadores de matrículas, "
            f"hora-aluno, receita e turmas {complemento_periodo}. Os resultados "
            f"estão organizados por programa e, posteriormente, por unidade "
            f"operacional."
        )
    else:
        texto_visao_geral = (
            f"Este relatório apresenta a análise dos principais indicadores "
            f"de desempenho do programa {programa}, com base nos dados extraídos "
            f"da Solução Integradora e do Cubo Orçamento, evidenciando a execução "
            f"de matrículas, hora-aluno e receita {complemento_periodo}."
        )

    def desenhar_resumo_e_cards(
        y_inicio,
        largura_pagina
    ):
        y_resumo = y_inicio

        # ======================================================
        # VISÃO GERAL
        # ======================================================

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            10
        )

        pdf.drawString(
            40,
            y_resumo,
            "VISÃO GERAL"
        )

        y_resumo -= 18

        pdf.setFillColor(
            colors.HexColor("#334155")
        )
        pdf.setFont(
            "Helvetica",
            9
        )

        linhas_visao_geral = simpleSplit(
            texto_visao_geral,
            "Helvetica",
            9,
            largura_pagina - 80
        )

        for linha in linhas_visao_geral:
            pdf.drawString(
                40,
                y_resumo,
                linha
            )

            y_resumo -= 12

        y_resumo -= 18

        # ======================================================
        # CARDS
        # ======================================================

        kpis = preview.get("kpis", {})

        matriculas = kpis.get("matriculas", {})
        hora_aluno = kpis.get("hora_aluno", {})
        receita = kpis.get("receita", {})
        turmas = kpis.get("turmas", {})

        margem_cards = 38
        espacamento_cards = 8
        altura_card = 88

        largura_card = (
            largura_pagina
            - (margem_cards * 2)
            - (espacamento_cards * 3)
        ) / 4

        y_cards = y_resumo - altura_card

        texto_matriculas = _texto_atingimento(
            matriculas.get("realizado", 0),
            matriculas.get("meta", 0)
        )

        texto_hora_aluno = _texto_atingimento(
            hora_aluno.get("realizado", 0),
            hora_aluno.get("meta", 0)
        )

        texto_receita = _texto_atingimento(
            receita.get("realizado", 0),
            receita.get("meta", 0)
        )

        _card(
            pdf,
            margem_cards,
            y_cards,
            largura_card,
            altura_card,
            "Matrículas",
            _num(matriculas.get("realizado", 0)),
            (
                f"Meta: {_num(matriculas.get('meta', 0))}"
                f" • Atingimento: {texto_matriculas}"
            ),
            colors.HexColor("#2563eb")
        )

        _card(
            pdf,
            margem_cards + largura_card + espacamento_cards,
            y_cards,
            largura_card,
            altura_card,
            "Hora-Aluno",
            _num(hora_aluno.get("realizado", 0)),
            (
                f"Meta: {_num(hora_aluno.get('meta', 0))}"
                f" • Atingimento: {texto_hora_aluno}"
            ),
            colors.HexColor("#16a34a")
        )

        _card(
            pdf,
            margem_cards + (
                largura_card + espacamento_cards
            ) * 2,
            y_cards,
            largura_card,
            altura_card,
            "Receita",
            _moeda(receita.get("realizado", 0)),
            (
                f"Meta: {_moeda(receita.get('meta', 0))}"
                f" • Atingimento: {texto_receita}"
            ),
            colors.HexColor("#f59e0b")
        )

        _card(
            pdf,
            margem_cards + (
                largura_card + espacamento_cards
            ) * 3,
            y_cards,
            largura_card,
            altura_card,
            "Turmas",
            _num(turmas.get("total", 0)),
            "Referência: período",
            colors.HexColor("#6d5dfc")
        )

        return y_cards - 20

    if not mover_resumo:
        y = desenhar_resumo_e_cards(
            y,
            largura
        )

    # Rodapé
    pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
    pdf.line(40, 42, largura - 40, 42)

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 1"
    )

    # ======================================================
    # CONTINUAÇÃO DAS UNIDADES OPERACIONAIS
    # ======================================================

    paginas_uos_adicionais = 0

    if uos_continuacao:

        indice_uo = 0

        while indice_uo < len(uos_continuacao):

            pdf.showPage()

            paginas_uos_adicionais += 1
            numero_pagina_uos = 1 + paginas_uos_adicionais

            # Cabeçalho azul
            pdf.setFillColor(colors.HexColor("#003B8F"))
            pdf.rect(
                0,
                altura - altura_cabecalho,
                largura,
                altura_cabecalho,
                fill=True,
                stroke=False
            )

            _desenhar_logo_cabecalho(
                pdf,
                largura,
                altura,
                paisagem=orientacao == "paisagem"
            )

            y_cont = altura - 125

            pdf.setFillColor(colors.HexColor("#071b52"))
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(
                40,
                y_cont,
                "UNIDADES OPERACIONAIS — CONTINUAÇÃO"
            )

            y_cont -= 28

            pdf.setFillColor(colors.HexColor("#64748b"))
            pdf.setFont("Helvetica", 9)
            pdf.drawString(
                40,
                y_cont,
                f"Programa: {programa}"
            )

            y_cont -= 28

            pdf.setFillColor(colors.HexColor("#334155"))
            pdf.setFont("Helvetica", 9)

            # Limite seguro antes do rodapé
            limite_rodape = 65

            while indice_uo < len(uos_continuacao):

                nome_uo = uos_continuacao[indice_uo]

                texto = f"• {nome_uo}"

                linhas = simpleSplit(
                    texto,
                    "Helvetica",
                    9,
                    largura - 80
                )

                altura_necessaria = (len(linhas) * 14) + 3

                # Verifica se esta é a última UO da lista
                eh_ultima_uo = (
                    indice_uo == len(uos_continuacao) - 1
                )

                # Se for a última UO, reserva espaço para
                # VISÃO GERAL + CARDS
                reserva_resumo = (
                    180
                    if eh_ultima_uo
                    else 0
                )

                limite_disponivel = (
                    limite_rodape
                    + reserva_resumo
                )

                # Se a próxima UO não couber respeitando
                # o espaço necessário, cria nova página
                if (
                    y_cont
                    - altura_necessaria
                    < limite_disponivel
                ):
                    break

                for linha in linhas:
                    pdf.drawString(
                        40,
                        y_cont,
                        linha
                    )
                    y_cont -= 14

                y_cont -= 3

                indice_uo += 1
            
            # ======================================================
            # VISÃO GERAL + CARDS NA ÚLTIMA PÁGINA DAS UOs
            # ======================================================

            if (
                mover_resumo
                and indice_uo >= len(uos_continuacao)
            ):

                y_cont -= 28

                y_cont = desenhar_resumo_e_cards(
                    y_cont,
                    largura
                )

            # Rodapé desta página
            pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
            pdf.line(
                40,
                42,
                largura - 40,
                42
            )

            pdf.setFillColor(colors.HexColor("#64748b"))
            pdf.setFont("Helvetica", 8)

            pdf.drawString(
                40,
                28,
                "Painel Executivo SENAI • Relatório gerado automaticamente"
            )

            pdf.drawRightString(
                largura - 40,
                28,
                f"Página {numero_pagina_uos}"
            )

    # ======================================================
    # PÁGINAS 2 EM DIANTE
    # DESEMPENHO POR UO E MODALIDADE
    # ======================================================

    desempenho_programas_detalhado = preview.get(
        "desempenho_programas_detalhado",
        []
    ) or []

    desempenho_subregioes_detalhado = preview.get(
        "desempenho_subregioes_detalhado",
        []
    ) or []

    modo_agrupamento = preview.get(
        "modo_agrupamento_desempenho",
        "programa_uo"
    )

    # Compatibilidade temporária com previews antigos
    if not desempenho_programas_detalhado:
        desempenho_uos_legado = preview.get(
            "desempenho_uos",
            []
        ) or []

        desempenho_programas_detalhado = [{
            "programa": programa,
            "uos": desempenho_uos_legado
        }]

    meses_selecionados = preview.get(
        "meses",
        []
    ) or []

    periodo_texto = _periodo(
        meses_selecionados
    )

    programa_texto = (
        programa
        or preview.get("programa")
        or "-"
    )

    numero_pagina = 2 + paginas_uos_adicionais

    # ------------------------------------------------------
    # FUNÇÃO LOCAL: CABEÇALHO DAS PÁGINAS DETALHADAS
    # ------------------------------------------------------

    def desenhar_cabecalho_detalhamento(
        nome_uo,
        numero_pagina,
        programa_atual
    ):
        pagina = landscape(A4)
        pdf.setPageSize(pagina)

        largura_pagina, altura_pagina = pagina

        altura_cabecalho = 82

        pdf.setFillColor(
            colors.HexColor("#003B8F")
        )
        pdf.rect(
            0,
            altura_pagina - altura_cabecalho,
            largura_pagina,
            altura_cabecalho,
            fill=True,
            stroke=False
        )

        _desenhar_logo_cabecalho(
            pdf,
            largura_pagina,
            altura_pagina,
            paisagem=True
        )

        y_titulo = altura_pagina - 116

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            16
        )
        pdf.drawString(
            40,
            y_titulo,
            f"DESEMPENHO — {periodo_texto.upper()}"
        )

        y_titulo -= 24

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            11
        )

        linhas_uo = simpleSplit(
            str(nome_uo),
            "Helvetica-Bold",
            11,
            largura_pagina - 80
        )

        for linha_uo in linhas_uo[:2]:
            pdf.drawString(
                40,
                y_titulo,
                linha_uo
            )
            y_titulo -= 14

        y_titulo -= 3

        pdf.setFillColor(
            colors.HexColor("#64748b")
        )
        pdf.setFont(
            "Helvetica",
            8
        )
        pdf.drawString(
            40,
            y_titulo,
            (
                f"Programa: {programa_atual} • "
                f"Ano: {preview.get('ano', '-')} • "
                f"Período: {periodo_texto}"
            )
        )

        # Rodapé
        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )
        pdf.line(
            40,
            34,
            largura_pagina - 40,
            34
        )

        pdf.setFillColor(
            colors.HexColor("#64748b")
        )
        pdf.setFont(
            "Helvetica",
            7
        )
        pdf.drawString(
            40,
            22,
            (
                "Painel Executivo SENAI • "
                "Relatório gerado automaticamente"
            )
        )

        pdf.drawRightString(
            largura_pagina - 40,
            22,
            f"Página {numero_pagina}"
        )

        return (
            largura_pagina,
            altura_pagina,
            y_titulo - 20
        )
    
    # ------------------------------------------------------
    # FUNÇÃO LOCAL: ABERTURA DE CADA PROGRAMA
    # ------------------------------------------------------

    def desenhar_abertura_programa(
        programa_atual,
        quantidade_uos,
        numero_pagina
    ):
        pagina = landscape(A4)
        pdf.setPageSize(pagina)

        largura_pagina, altura_pagina = pagina

        # Cabeçalho azul
        altura_cabecalho = 82

        pdf.setFillColor(
            colors.HexColor("#003B8F")
        )
        pdf.rect(
            0,
            altura_pagina - altura_cabecalho,
            largura_pagina,
            altura_cabecalho,
            fill=True,
            stroke=False
        )

        _desenhar_logo_cabecalho(
            pdf,
            largura_pagina,
            altura_pagina,
            paisagem=True
        )

        # Identificação da seção
        y = altura_pagina - 155

        pdf.setFillColor(
            colors.HexColor("#64748b")
        )
        pdf.setFont(
            "Helvetica-Bold",
            10
        )
        pdf.drawString(
            40,
            y,
            "PROGRAMA"
        )

        y -= 34

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            22
        )

        linhas_programa = simpleSplit(
            str(programa_atual),
            "Helvetica-Bold",
            22,
            largura_pagina - 80
        )

        for linha in linhas_programa[:3]:
            pdf.drawString(
                40,
                y,
                linha
            )
            y -= 29

        y -= 22

        # Contexto do relatório
        pdf.setFillColor(
            colors.HexColor("#334155")
        )
        pdf.setFont(
            "Helvetica",
            10
        )

        pdf.drawString(
            40,
            y,
            (
                f"Ano: {preview.get('ano', '-')} • "
                f"Período: {periodo_texto}"
            )
        )

        y -= 24

        texto_uos = (
            f"{quantidade_uos} unidade operacional"
            if quantidade_uos == 1
            else f"{quantidade_uos} unidades operacionais"
        )

        pdf.drawString(
            40,
            y,
            f"Escopo do detalhamento: {texto_uos}"
        )

        # Texto explicativo
        y -= 55

        pdf.setFillColor(
            colors.HexColor("#eff6ff")
        )
        pdf.setStrokeColor(
            colors.HexColor("#bfdbfe")
        )
        pdf.roundRect(
            40,
            y - 90,
            largura_pagina - 80,
            90,
            10,
            fill=True,
            stroke=True
        )

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            11
        )
        pdf.drawString(
            56,
            y - 25,
            "DETALHAMENTO POR UNIDADE OPERACIONAL"
        )

        texto_abertura = (
            "As páginas seguintes apresentam os resultados de matrículas, "
            "hora-aluno e receita das unidades operacionais vinculadas a "
            "este programa, incluindo análise por modalidade, score de "
            "desempenho e conclusão executiva."
        )

        linhas_abertura = simpleSplit(
            texto_abertura,
            "Helvetica",
            9,
            largura_pagina - 112
        )

        pdf.setFillColor(
            colors.HexColor("#334155")
        )
        pdf.setFont(
            "Helvetica",
            9
        )

        y_texto = y - 47

        for linha in linhas_abertura:
            pdf.drawString(
                56,
                y_texto,
                linha
            )
            y_texto -= 13

        # Rodapé
        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )
        pdf.line(
            40,
            34,
            largura_pagina - 40,
            34
        )

        pdf.setFillColor(
            colors.HexColor("#64748b")
        )
        pdf.setFont(
            "Helvetica",
            7
        )
        pdf.drawString(
            40,
            22,
            (
                "Painel Executivo SENAI • "
                "Relatório gerado automaticamente"
            )
        )

        pdf.drawRightString(
            largura_pagina - 40,
            22,
            f"Página {numero_pagina}"
        )
    
    # ------------------------------------------------------
    # FUNÇÃO LOCAL: ABERTURA DE CADA SUB-REGIÃO
    # ------------------------------------------------------

    def desenhar_abertura_subregiao(
        subregiao_atual,
        quantidade_programas,
        quantidade_uos,
        numero_pagina
    ):
        pagina = landscape(A4)
        pdf.setPageSize(pagina)

        largura_pagina, altura_pagina = pagina

        altura_cabecalho = 82

        pdf.setFillColor(
            colors.HexColor("#003B8F")
        )
        pdf.rect(
            0,
            altura_pagina - altura_cabecalho,
            largura_pagina,
            altura_cabecalho,
            fill=True,
            stroke=False
        )

        _desenhar_logo_cabecalho(
            pdf,
            largura_pagina,
            altura_pagina,
            paisagem=True
        )

        y = altura_pagina - 155

        pdf.setFillColor(
            colors.HexColor("#64748b")
        )
        pdf.setFont(
            "Helvetica-Bold",
            10
        )
        pdf.drawString(
            40,
            y,
            "SUB-REGIÃO"
        )

        y -= 34

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            22
        )

        linhas_subregiao = simpleSplit(
            str(subregiao_atual),
            "Helvetica-Bold",
            22,
            largura_pagina - 80
        )

        for linha in linhas_subregiao[:3]:
            pdf.drawString(
                40,
                y,
                linha
            )
            y -= 29

        y -= 22

        pdf.setFillColor(
            colors.HexColor("#334155")
        )
        pdf.setFont(
            "Helvetica",
            10
        )

        pdf.drawString(
            40,
            y,
            (
                f"Ano: {preview.get('ano', '-')} • "
                f"Período: {periodo_texto}"
            )
        )

        y -= 24

        texto_programas = (
            f"{quantidade_programas} programa"
            if quantidade_programas == 1
            else f"{quantidade_programas} programas"
        )

        texto_uos = (
            f"{quantidade_uos} unidade operacional"
            if quantidade_uos == 1
            else f"{quantidade_uos} unidades operacionais"
        )

        pdf.drawString(
            40,
            y,
            (
                f"Escopo do detalhamento: "
                f"{texto_programas} • {texto_uos}"
            )
        )

        y -= 55

        pdf.setFillColor(
            colors.HexColor("#eff6ff")
        )
        pdf.setStrokeColor(
            colors.HexColor("#bfdbfe")
        )
        pdf.roundRect(
            40,
            y - 90,
            largura_pagina - 80,
            90,
            10,
            fill=True,
            stroke=True
        )

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            11
        )
        pdf.drawString(
            56,
            y - 25,
            "DETALHAMENTO POR PROGRAMA E UNIDADE OPERACIONAL"
        )

        texto_abertura = (
            "As páginas seguintes apresentam os programas vinculados "
            "a esta sub-região e, em cada programa, os resultados das "
            "respectivas unidades operacionais."
        )

        linhas_abertura = simpleSplit(
            texto_abertura,
            "Helvetica",
            9,
            largura_pagina - 112
        )

        pdf.setFillColor(
            colors.HexColor("#334155")
        )
        pdf.setFont(
            "Helvetica",
            9
        )

        y_texto = y - 47

        for linha in linhas_abertura:
            pdf.drawString(
                56,
                y_texto,
                linha
            )
            y_texto -= 13

        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )
        pdf.line(
            40,
            34,
            largura_pagina - 40,
            34
        )

        pdf.setFillColor(
            colors.HexColor("#64748b")
        )
        pdf.setFont(
            "Helvetica",
            7
        )
        pdf.drawString(
            40,
            22,
            (
                "Painel Executivo SENAI • "
                "Relatório gerado automaticamente"
            )
        )

        pdf.drawRightString(
            largura_pagina - 40,
            22,
            f"Página {numero_pagina}"
        )

    # ------------------------------------------------------
    # FUNÇÃO LOCAL: TABELA DE UM INDICADOR
    # ------------------------------------------------------

    def desenhar_tabela_indicador(
        titulo,
        dados,
        y,
        largura_pagina,
        tipo_valor="numero"
    ):
        x_inicio = 40
        largura_tabela = largura_pagina - 80

        # Alturas compactadas para comportar até três
        # modalidades nos três indicadores sem invadir o rodapé.
        altura_titulo = 20
        altura_cabecalho_tabela = 22
        altura_linha = 20

        colunas = [
            ("Modalidade", 0.40),
            ("Meta período", 0.15),
            ("Realizado período", 0.17),
            ("Meta anual", 0.15),
            ("% atingimento", 0.13),
        ]

        larguras_colunas = [
            largura_tabela * proporcao
            for _, proporcao in colunas
        ]

        # Título do indicador
        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            11
        )
        pdf.drawString(
            x_inicio,
            y,
            titulo.upper()
        )

        y -= altura_titulo

        # Cabeçalho da tabela
        pdf.setFillColor(
            colors.HexColor("#eaf0f8")
        )
        pdf.roundRect(
            x_inicio,
            y - 5,
            largura_tabela,
            altura_cabecalho_tabela,
            6,
            fill=True,
            stroke=False
        )

        x = x_inicio

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            7
        )

        for indice_coluna, (
            titulo_coluna,
            _
        ) in enumerate(colunas):

            largura_coluna = larguras_colunas[
                indice_coluna
            ]

            if indice_coluna == 0:
                pdf.drawString(
                    x + 6,
                    y + 5,
                    titulo_coluna.upper()
                )
            else:
                pdf.drawCentredString(
                    x + largura_coluna / 2,
                    y + 5,
                    titulo_coluna.upper()
                )

            x += largura_coluna

        y -= altura_cabecalho_tabela

        if not dados:
            pdf.setFillColor(
                colors.HexColor("#64748b")
            )
            pdf.setFont(
                "Helvetica",
                8
            )
            pdf.drawString(
                x_inicio + 6,
                y,
                "Nenhuma modalidade encontrada para este indicador."
            )

            return y - 28

        for indice_linha, item in enumerate(dados):

            cor_fundo = (
                colors.white
                if indice_linha % 2 == 0
                else colors.HexColor("#f8fafc")
            )

            pdf.setFillColor(cor_fundo)
            pdf.rect(
                x_inicio,
                y - 5,
                largura_tabela,
                altura_linha,
                fill=True,
                stroke=False
            )

            modalidade = (
                item.get("modalidade")
                or "NÃO INFORMADA"
            )

            meta_periodo = float(
                item.get("meta_periodo", 0)
                or 0
            )

            realizado_periodo = float(
                item.get("realizado_periodo", 0)
                or 0
            )

            meta_anual = float(
                item.get("meta_anual", 0)
                or 0
            )

            atingimento = float(
                item.get("atingimento", 0)
                or 0
            )

            if tipo_valor == "moeda":
                texto_meta_periodo = _moeda(
                    meta_periodo
                )
                texto_realizado = _moeda(
                    realizado_periodo
                )
                texto_meta_anual = _moeda(
                    meta_anual
                )
            else:
                texto_meta_periodo = _num(
                    meta_periodo
                )
                texto_realizado = _num(
                    realizado_periodo
                )
                texto_meta_anual = _num(
                    meta_anual
                )

            if meta_periodo <= 0 and realizado_periodo <= 0:
                texto_pct = "-"

            elif meta_periodo <= 0 and realizado_periodo > 0:
                texto_pct = "*"

            else:
                texto_pct = (
                    f"{atingimento:,.1f}%"
                    .replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )

            valores = [
                modalidade,
                texto_meta_periodo,
                texto_realizado,
                texto_meta_anual,
                texto_pct
            ]

            x = x_inicio

            for indice_coluna, valor in enumerate(valores):

                largura_coluna = larguras_colunas[
                    indice_coluna
                ]

                if indice_coluna == 0:
                    pdf.setFillColor(
                        colors.HexColor("#071b52")
                    )
                    pdf.setFont(
                        "Helvetica-Bold",
                        7
                    )

                    linhas_modalidade = simpleSplit(
                        str(valor),
                        "Helvetica-Bold",
                        7,
                        largura_coluna - 12
                    )

                    if linhas_modalidade:
                        pdf.drawString(
                            x + 6,
                            y + 4,
                            linhas_modalidade[0]
                        )

                    if len(linhas_modalidade) > 1:
                        pdf.drawString(
                            x + 6,
                            y - 4,
                            linhas_modalidade[1]
                        )

                elif indice_coluna == 4:

                    pdf.setFillColor(
                        _cor_status_pct(
                            atingimento,
                            meta_periodo,
                            realizado_periodo
                        )
                    )
                    pdf.setFont(
                        "Helvetica-Bold",
                        7
                    )
                    pdf.drawCentredString(
                        x + largura_coluna / 2,
                        y + 2,
                        str(valor)
                    )

                else:
                    pdf.setFillColor(
                        colors.HexColor("#334155")
                    )
                    pdf.setFont(
                        "Helvetica",
                        7
                    )
                    pdf.drawCentredString(
                        x + largura_coluna / 2,
                        y + 2,
                        str(valor)
                    )

                x += largura_coluna

            y -= altura_linha

        # Espaço entre uma tabela e a próxima
        return y - 14
    
    # ------------------------------------------------------
    # FUNÇÃO LOCAL: PÁGINA DE ANÁLISE EXECUTIVA DA UO
    # ------------------------------------------------------

    def desenhar_analise_executiva_uo(
        nome_uo,
        analise,
        numero_pagina,
        programa_atual
    ):
        analise = analise or {}

        pagina = landscape(A4)
        pdf.setPageSize(pagina)

        largura_pagina, altura_pagina = pagina

        margem_esquerda = 40
        margem_direita = 40
        largura_conteudo = (
            largura_pagina
            - margem_esquerda
            - margem_direita
        )

        def cor_status(status):
            mapa = {
                "meta_atingida": colors.HexColor("#16a34a"),
                "no_caminho": colors.HexColor("#2563eb"),
                "atencao": colors.HexColor("#f59e0b"),
                "critico": colors.HexColor("#dc2626"),
                "sem_meta": colors.HexColor("#64748b"),
                "sem_dados": colors.HexColor("#111827"),
            }

            return mapa.get(
                status,
                colors.HexColor("#64748b")
            )

        def desenhar_cabecalho_pagina(
            titulo_continuacao=None
        ):
            altura_cabecalho = 82

            pdf.setFillColor(
                colors.HexColor("#003B8F")
            )
            pdf.rect(
                0,
                altura_pagina - altura_cabecalho,
                largura_pagina,
                altura_cabecalho,
                fill=True,
                stroke=False
            )

            _desenhar_logo_cabecalho(
                pdf,
                largura_pagina,
                altura_pagina,
                paisagem=True
            )

            pdf.setFillColor(
                colors.HexColor("#071b52")
            )
            pdf.setFont(
                "Helvetica-Bold",
                16
            )

            titulo = (
                titulo_continuacao
                or "ANÁLISE EXECUTIVA DA UNIDADE"
            )

            pdf.drawString(
                margem_esquerda,
                altura_pagina - 116,
                titulo
            )

            pdf.setFillColor(
                colors.HexColor("#071b52")
            )
            pdf.setFont(
                "Helvetica-Bold",
                11
            )

            linhas_nome_uo = simpleSplit(
                str(nome_uo),
                "Helvetica-Bold",
                11,
                largura_conteudo
            )

            y_nome = altura_pagina - 140

            for linha in linhas_nome_uo[:2]:
                pdf.drawString(
                    margem_esquerda,
                    y_nome,
                    linha
                )
                y_nome -= 14

            pdf.setFillColor(
                colors.HexColor("#64748b")
            )
            pdf.setFont(
                "Helvetica",
                8
            )

            pdf.drawString(
                margem_esquerda,
                y_nome - 2,
                (
                    f"Programa: {programa_atual} • "
                    f"Ano: {preview.get('ano', '-')} • "
                    f"Período: {periodo_texto}"
                )
            )

            # Rodapé
            pdf.setStrokeColor(
                colors.HexColor("#e5e7eb")
            )
            pdf.line(
                margem_esquerda,
                34,
                largura_pagina - margem_direita,
                34
            )

            pdf.setFillColor(
                colors.HexColor("#64748b")
            )
            pdf.setFont(
                "Helvetica",
                7
            )

            pdf.drawString(
                margem_esquerda,
                22,
                (
                    "Painel Executivo SENAI • "
                    "Relatório gerado automaticamente"
                )
            )

            pdf.drawRightString(
                largura_pagina - margem_direita,
                22,
                f"Página {numero_pagina}"
            )

            return y_nome - 34

        def nova_pagina_continuacao():
            nonlocal numero_pagina

            numero_pagina += 1

            pdf.showPage()
            pdf.setPageSize(
                landscape(A4)
            )

            return desenhar_cabecalho_pagina(
                "ANÁLISE EXECUTIVA DA UNIDADE — CONTINUAÇÃO"
            )

        def garantir_espaco(
            y_atual,
            altura_necessaria
        ):
            if (
                y_atual
                - altura_necessaria
                < 52
            ):
                return nova_pagina_continuacao()

            return y_atual

        def desenhar_texto(
            texto,
            x,
            y,
            largura_texto,
            fonte="Helvetica",
            tamanho=8.5,
            entrelinha=12
        ):
            linhas = simpleSplit(
                str(texto or ""),
                fonte,
                tamanho,
                largura_texto
            )

            for linha in linhas:
                pdf.setFont(
                    fonte,
                    tamanho
                )
                pdf.drawString(
                    x,
                    y,
                    linha
                )
                y -= entrelinha

            return y
        
        def desenhar_titulo_indicador(
            titulo,
            y,
            continuacao=False
        ):
            """
            Desenha o título de cada grupo de indicadores,
            mantendo distância em relação ao bloco anterior.
            """

            # Espaço antes do título
            y -= 16

            texto_titulo = titulo.upper()

            if continuacao:
                texto_titulo += " - CONTINUAÇÃO"

            pdf.setFillColor(
                colors.HexColor("#071b52")
            )
            pdf.setFont(
                "Helvetica-Bold",
                11
            )
            pdf.drawString(
                margem_esquerda,
                y,
                texto_titulo
            )

            # Espaço entre o título e a primeira caixa
            return y - 24

        y = desenhar_cabecalho_pagina()

        # ==================================================
        # CLASSIFICAÇÃO E SCORE
        # ==================================================

        classificacao = analise.get(
            "classificacao",
            "Sem classificação"
        )

        nivel = analise.get(
            "nivel",
            "sem_dados"
        )

        score = analise.get(
            "score",
            0
        )

        score_maximo = analise.get(
            "score_maximo",
            0
        )

        percentual_score = analise.get(
            "percentual_score",
            0
        )

        cor_nivel = {
            "excelencia": colors.HexColor("#16a34a"),
            "satisfatorio": colors.HexColor("#2563eb"),
            "regular": colors.HexColor("#f59e0b"),
            "critico": colors.HexColor("#dc2626"),
            "sem_dados": colors.HexColor("#64748b"),
        }.get(
            nivel,
            colors.HexColor("#64748b")
        )

        altura_card_score = 62

        pdf.setFillColor(
            colors.HexColor("#f8fafc")
        )
        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )
        pdf.roundRect(
            margem_esquerda,
            y - altura_card_score,
            largura_conteudo,
            altura_card_score,
            10,
            fill=True,
            stroke=True
        )

        pdf.setFillColor(cor_nivel)
        pdf.roundRect(
            margem_esquerda,
            y - altura_card_score,
            7,
            altura_card_score,
            3,
            fill=True,
            stroke=False
        )

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            12
        )
        pdf.drawString(
            margem_esquerda + 20,
            y - 23,
            classificacao
        )

        pdf.setFillColor(
            colors.HexColor("#334155")
        )
        pdf.setFont(
            "Helvetica",
            9
        )
        pdf.drawString(
            margem_esquerda + 20,
            y - 43,
            (
                f"Score: {score} de {score_maximo} pontos • "
                f"Aproveitamento: {_pct(percentual_score)}"
            )
        )

        y -= altura_card_score + 12

        # ==================================================
        # EXPLICAÇÃO DO SCORE
        # ==================================================

        texto_explicacao_score = (
            "Como interpretar o score: cada indicador com meta definida, "
            "em cada modalidade, recebe de 0 a 3 pontos. "
            "3 pontos representam atingimento igual ou superior a 100% da meta; "
            "2 pontos representam atingimento entre 75% e 99,9%; "
            "1 ponto representa atingimento entre 51% e 74,9%; "
            "e 0 ponto representa atingimento inferior a 51%. "
            "Indicadores sem meta definida não entram no cálculo. "
            "O aproveitamento corresponde à divisão dos pontos obtidos "
            "pelo total máximo de pontos possível."
        )

        linhas_explicacao_score = simpleSplit(
            texto_explicacao_score,
            "Helvetica",
            7.5,
            largura_conteudo - 28
        )

        altura_explicacao_score = max(
            58,
            30 + len(linhas_explicacao_score) * 10
        )

        y = garantir_espaco(
            y,
            altura_explicacao_score
        )

        pdf.setFillColor(
            colors.HexColor("#fff7ed")
        )
        pdf.setStrokeColor(
            colors.HexColor("#fed7aa")
        )
        pdf.roundRect(
            margem_esquerda,
            y - altura_explicacao_score,
            largura_conteudo,
            altura_explicacao_score,
            8,
            fill=True,
            stroke=True
        )

        pdf.setFillColor(
            colors.HexColor("#9a3412")
        )
        pdf.setFont(
            "Helvetica-Bold",
            8.5
        )
        pdf.drawString(
            margem_esquerda + 14,
            y - 19,
            "O QUE SIGNIFICA O SCORE?"
        )

        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        desenhar_texto(
            texto_explicacao_score,
            margem_esquerda + 14,
            y - 35,
            largura_conteudo - 28,
            fonte="Helvetica",
            tamanho=7.5,
            entrelinha=10
        )

        y -= altura_explicacao_score + 16

        # ==================================================
        # RESUMO EXECUTIVO
        # ==================================================

        resumo_executivo = analise.get(
            "resumo_executivo",
            ""
        )

        linhas_resumo = simpleSplit(
            resumo_executivo,
            "Helvetica",
            8.5,
            largura_conteudo - 24
        )

        altura_resumo = (
            48
            + len(linhas_resumo) * 12
        )

        y = garantir_espaco(
            y,
            altura_resumo
        )

        pdf.setFillColor(
            colors.HexColor("#eff6ff")
        )
        pdf.setStrokeColor(
            colors.HexColor("#bfdbfe")
        )
        pdf.roundRect(
            margem_esquerda,
            y - altura_resumo,
            largura_conteudo,
            altura_resumo,
            10,
            fill=True,
            stroke=True
        )

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            11
        )
        pdf.drawString(
            margem_esquerda + 14,
            y - 23,
            "Resumo executivo"
        )

        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        y_texto = y - 43

        y_texto = desenhar_texto(
            resumo_executivo,
            margem_esquerda + 14,
            y_texto,
            largura_conteudo - 28,
            tamanho=8.5,
            entrelinha=12
        )

        y -= altura_resumo + 18

        # ==================================================
        # ANÁLISES POR INDICADOR
        # ==================================================

        grupos = [
            (
                "Matrículas",
                analise.get("matriculas", [])
            ),
            (
                "Hora-Aluno",
                analise.get("hora_aluno", [])
            ),
            (
                "Receita",
                analise.get("receita", [])
            ),
        ]

        for titulo_grupo, itens in grupos:

            itens = itens or []

            # ==================================================
            # CALCULA O ESPAÇO MÍNIMO PARA O TÍTULO E O 1º ITEM
            # ==================================================

            altura_primeiro_item = 34

            if itens:
                primeiro_texto = (
                    itens[0].get("texto", "")
                    or ""
                )

                linhas_primeiro_item = simpleSplit(
                    primeiro_texto,
                    "Helvetica",
                    8,
                    largura_conteudo - 42
                )

                altura_primeiro_item = max(
                    42,
                    22 + len(linhas_primeiro_item) * 11
                )

            espaco_minimo_grupo = (
                16
                + 24
                + altura_primeiro_item
                + 10
            )

            # Não permite que o título fique sozinho
            if (
                y - espaco_minimo_grupo
                < 52
            ):
                y = nova_pagina_continuacao()

            y = desenhar_titulo_indicador(
                titulo_grupo,
                y
            )

            # ==================================================
            # GRUPO SEM ANÁLISES
            # ==================================================

            if not itens:
                pdf.setFillColor(
                    colors.HexColor("#64748b")
                )
                pdf.setFont(
                    "Helvetica",
                    8
                )
                pdf.drawString(
                    margem_esquerda + 8,
                    y,
                    "Nenhuma análise disponível."
                )

                y -= 34
                continue

            # ==================================================
            # ITENS DO INDICADOR
            # ==================================================

            for indice_item, item in enumerate(itens):

                texto_item = (
                    item.get("texto", "")
                    or ""
                )

                linhas_item = simpleSplit(
                    texto_item,
                    "Helvetica",
                    8,
                    largura_conteudo - 42
                )

                altura_item = max(
                    42,
                    22 + len(linhas_item) * 11
                )

                # Se o item não couber, cria nova página e
                # repete o título do indicador.
                if (
                    y - altura_item
                    < 52
                ):
                    y = nova_pagina_continuacao()

                    y = desenhar_titulo_indicador(
                        titulo_grupo,
                        y,
                        continuacao=True
                    )

                status = item.get(
                    "status",
                    "sem_dados"
                )

                pdf.setFillColor(
                    colors.HexColor("#ffffff")
                )
                pdf.setStrokeColor(
                    colors.HexColor("#e5e7eb")
                )
                pdf.roundRect(
                    margem_esquerda,
                    y - altura_item,
                    largura_conteudo,
                    altura_item,
                    8,
                    fill=True,
                    stroke=True
                )

                pdf.setFillColor(
                    cor_status(status)
                )
                pdf.roundRect(
                    margem_esquerda,
                    y - altura_item,
                    6,
                    altura_item,
                    3,
                    fill=True,
                    stroke=False
                )

                pdf.setFillColor(
                    colors.HexColor("#334155")
                )

                desenhar_texto(
                    texto_item,
                    margem_esquerda + 18,
                    y - 18,
                    largura_conteudo - 34,
                    tamanho=8,
                    entrelinha=11
                )

                # Mais espaço entre as caixas
                y -= altura_item + 13

            # Espaço após o último item e antes do próximo título
            y -= 10

        # ==================================================
        # CONCLUSÃO
        # ==================================================

        conclusao = analise.get(
            "conclusao",
            ""
        )

        linhas_conclusao = simpleSplit(
            conclusao,
            "Helvetica",
            8.5,
            largura_conteudo - 28
        )

        altura_conclusao = max(
            70,
            45 + len(linhas_conclusao) * 12
        )

        y = garantir_espaco(
            y,
            altura_conclusao
        )

        pdf.setFillColor(
            colors.HexColor("#f0fdf4")
        )
        pdf.setStrokeColor(
            colors.HexColor("#bbf7d0")
        )
        pdf.roundRect(
            margem_esquerda,
            y - altura_conclusao,
            largura_conteudo,
            altura_conclusao,
            10,
            fill=True,
            stroke=True
        )

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )
        pdf.setFont(
            "Helvetica-Bold",
            11
        )
        pdf.drawString(
            margem_esquerda + 14,
            y - 23,
            "Conclusão executiva"
        )

        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        desenhar_texto(
            conclusao,
            margem_esquerda + 14,
            y - 43,
            largura_conteudo - 28,
            tamanho=8.5,
            entrelinha=12
        )

        return numero_pagina
    
    # ------------------------------------------------------
    # FUNÇÃO LOCAL: GERA AS PÁGINAS DAS UOs DE UM PROGRAMA
    # ------------------------------------------------------

    def gerar_paginas_uos(
        uos_programa,
        programa_atual,
        numero_pagina
    ):
        for item_uo in uos_programa:

            pdf.showPage()

            nome_uo = (
                item_uo.get("uo")
                or "UNIDADE OPERACIONAL NÃO INFORMADA"
            )

            (
                largura_detalhe,
                altura_detalhe,
                y
            ) = desenhar_cabecalho_detalhamento(
                nome_uo,
                numero_pagina,
                programa_atual
            )

            y = desenhar_tabela_indicador(
                "Matrículas",
                item_uo.get("matriculas", []),
                y,
                largura_detalhe,
                tipo_valor="numero"
            )

            y = desenhar_tabela_indicador(
                "Hora-Aluno",
                item_uo.get("hora_aluno", []),
                y,
                largura_detalhe,
                tipo_valor="numero"
            )

            y = desenhar_tabela_indicador(
                "Receita",
                item_uo.get("receita", []),
                y,
                largura_detalhe,
                tipo_valor="moeda"
            )

            # Legenda da página de desempenho
            if y > 72:
                _legenda_status(
                    pdf,
                    40,
                    max(y, 72)
                )

            # Redesenha o rodapé depois das tabelas.
            # Assim, nenhum conteúdo fica sobre ele.
            pdf.setFillColor(colors.white)
            pdf.rect(
                0,
                0,
                largura_detalhe,
                43,
                fill=True,
                stroke=False
            )

            pdf.setStrokeColor(
                colors.HexColor("#e5e7eb")
            )
            pdf.line(
                40,
                34,
                largura_detalhe - 40,
                34
            )

            pdf.setFillColor(
                colors.HexColor("#64748b")
            )
            pdf.setFont(
                "Helvetica",
                7
            )
            pdf.drawString(
                40,
                22,
                (
                    "Painel Executivo SENAI • "
                    "Relatório gerado automaticamente"
                )
            )

            pdf.drawRightString(
                largura_detalhe - 40,
                22,
                f"Página {numero_pagina}"
            )

            # A próxima página será a análise executiva
            numero_pagina += 1

            analise_uo = item_uo.get(
                "analise",
                {}
            ) or {}

            pdf.showPage()

            numero_pagina = desenhar_analise_executiva_uo(
                nome_uo=nome_uo,
                analise=analise_uo,
                numero_pagina=numero_pagina,
                programa_atual=programa_atual
            )

            # Prepara a numeração para a próxima UO
            numero_pagina += 1

        return numero_pagina
    
    # ======================================================
    # AGRUPAMENTO POR SUB-REGIÃO
    # ======================================================

    if modo_agrupamento == "subregiao_programa_uo":

        desempenho_subregioes_detalhado = sorted(
            desempenho_subregioes_detalhado,
            key=lambda item: str(
                item.get("subregiao") or ""
            ).strip().casefold()
        )

        for bloco_subregiao in desempenho_subregioes_detalhado:

            pdf.showPage()

            programas_subregiao = (
                bloco_subregiao.get("programas")
                or []
            )

            uos_unicas_subregiao = {
                str(uo.get("uo") or "").strip()
                for programa in programas_subregiao
                for uo in (programa.get("uos") or [])
                if str(uo.get("uo") or "").strip()
            }

            quantidade_uos = len(
                uos_unicas_subregiao
            )

            desenhar_abertura_subregiao(
                subregiao_atual=bloco_subregiao.get("subregiao"),
                quantidade_programas=len(programas_subregiao),
                quantidade_uos=quantidade_uos,
                numero_pagina=numero_pagina
            )

            numero_pagina += 1

            for bloco_programa in programas_subregiao:

                programa_atual = (
                    bloco_programa.get("programa")
                    or "PROGRAMA NÃO INFORMADO"
                )

                uos_programa = (
                    bloco_programa.get("uos")
                    or []
                )

                pdf.showPage()

                desenhar_abertura_programa(
                    programa_atual=programa_atual,
                    quantidade_uos=len(uos_programa),
                    numero_pagina=numero_pagina
                )

                numero_pagina += 1

                numero_pagina = gerar_paginas_uos(
                    uos_programa=uos_programa,
                    programa_atual=programa_atual,
                    numero_pagina=numero_pagina
                )

    # ------------------------------------------------------
    # CRIA UMA PÁGINA PARA CADA UO
    # ------------------------------------------------------

    if (
        modo_agrupamento != "subregiao_programa_uo"
        and desempenho_programas_detalhado
    ):

        for bloco_programa in desempenho_programas_detalhado:

            programa_atual = (
                bloco_programa.get("programa")
                or "PROGRAMA NÃO INFORMADO"
            )

            uos_programa = (
                bloco_programa.get("uos")
                or []
            )

            # Página de abertura do programa
            pdf.showPage()

            desenhar_abertura_programa(
                programa_atual=programa_atual,
                quantidade_uos=len(uos_programa),
                numero_pagina=numero_pagina
            )

            numero_pagina += 1

            numero_pagina = gerar_paginas_uos(
                uos_programa=uos_programa,
                programa_atual=programa_atual,
                numero_pagina=numero_pagina
            )

    elif (
        modo_agrupamento != "subregiao_programa_uo"
        and not desempenho_programas_detalhado
    ):

        pdf.showPage()

        (
            largura_detalhe,
            altura_detalhe,
            y
        ) = desenhar_cabecalho_detalhamento(
            "UNIDADES OPERACIONAIS",
            numero_pagina
        )

        pdf.setFillColor(
            colors.HexColor("#64748b")
        )
        pdf.setFont(
            "Helvetica",
            10
        )
        pdf.drawString(
            40,
            y,
            (
                "Nenhuma unidade operacional foi encontrada "
                "para os filtros selecionados."
            )
        )

    pdf.save()
    buffer.seek(0)

    return buffer

def gerar_pdf_relatorio_desempenho_subregiao(
    preview,
    orientacao="retrato"
):
    """
    Gera o Relatório de Desempenho por Sub-região.
    """

    buffer = BytesIO()

    pagina = (
        landscape(A4)
        if orientacao == "paisagem"
        else A4
    )

    pdf = canvas.Canvas(
        buffer,
        pagesize=pagina
    )

    largura, altura = pagina


    # ======================================================
    # DADOS DO CABEÇALHO
    # ======================================================

    cabecalho = preview.get(
        "cabecalho_desempenho_subregiao",
        {}
    )

    regiao = (
        cabecalho.get("regiao")
        or "TODAS AS REGIÕES"
    )

    subregiao = (
        cabecalho.get("subregiao")
        or "TODAS AS SUB-REGIÕES"
    )

    geope = (
        cabecalho.get("geope")
        or "Não informado"
    )

    uos = (
        cabecalho.get("uos")
        or []
    )

    # ======================================================
    # ANO E PERÍODO
    # ======================================================

    ano = (
        preview.get("ano")
        or "-"
    )

    meses = (
        preview.get("meses")
        or []
    )

    nomes_meses = {
        1: "Jan",
        2: "Fev",
        3: "Mar",
        4: "Abr",
        5: "Mai",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Set",
        10: "Out",
        11: "Nov",
        12: "Dez",
    }

    if not meses:

        periodo = "-"

    elif len(meses) == 1:

        periodo = nomes_meses.get(
            int(meses[0]),
            str(meses[0])
        )

    else:

        meses_ordenados = sorted(
            int(m) for m in meses
        )

        periodo = (
            f"{nomes_meses.get(meses_ordenados[0], meses_ordenados[0])}-"
            f"{nomes_meses.get(meses_ordenados[-1], meses_ordenados[-1])}"
        )


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    altura_cabecalho = 82

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - altura_cabecalho,
        largura,
        altura_cabecalho,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    y = altura - 125

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        18
    )

    pdf.drawString(
        40,
        y,
        "RELATÓRIO DE DESEMPENHO POR SUB-REGIÃO"
    )

    y -= 24


    # ======================================================
    # PERÍODO
    # ======================================================

    ano = preview.get("ano")

    meses = preview.get("meses") or []

    nomes_meses = {
        1: "Jan",
        2: "Fev",
        3: "Mar",
        4: "Abr",
        5: "Mai",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Set",
        10: "Out",
        11: "Nov",
        12: "Dez",
    }

    if not meses:

        periodo = "Anual"

    elif len(meses) == 1:

        periodo = nomes_meses.get(
            meses[0],
            str(meses[0])
        )

    else:

        meses_ordenados = sorted(meses)

        periodo = (
            f"{nomes_meses.get(meses_ordenados[0])}"
            f"-"
            f"{nomes_meses.get(meses_ordenados[-1])}"
        )


    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        y,
        f"Ano: {ano} • Período: {periodo}"
    )

    y -= 30


    # ======================================================
    # REGIÃO / SUB-REGIÃO
    # ======================================================

    largura_coluna = (
        largura - 100
    ) / 2

    x_esquerda = 40
    x_direita = 60 + largura_coluna


    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica-Bold",
        8
    )

    pdf.drawString(
        x_esquerda,
        y,
        "REGIÃO"
    )

    pdf.drawString(
        x_direita,
        y,
        "SUB-REGIÃO"
    )

    y -= 15


    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        x_esquerda,
        y,
        str(regiao).upper()
    )

    pdf.drawString(
        x_direita,
        y,
        str(subregiao).upper()
    )

    y -= 28


    # ======================================================
    # GEOPE
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica-Bold",
        8
    )

    pdf.drawString(
        40,
        y,
        "GEOPE"
    )

    y -= 15

    pdf.setFillColor(
        colors.HexColor("#334155")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    linhas_geope = simpleSplit(
        str(geope),
        "Helvetica",
        9,
        largura - 80
    )

    for linha in linhas_geope:
        pdf.drawString(
            40,
            y,
            linha
        )

        y -= 13

    y -= 16


    # ======================================================
    # UNIDADES OPERACIONAIS
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y,
        "UNIDADES OPERACIONAIS"
    )

    y -= 18

    pdf.setFillColor(
        colors.HexColor("#334155")
    )

    pdf.setFont(
        "Helvetica",
        8.5
    )


    # Duas colunas
    coluna_esquerda = []
    coluna_direita = []

    metade = (
        len(uos) + 1
    ) // 2

    coluna_esquerda = uos[:metade]
    coluna_direita = uos[metade:]

    y_uos_inicio = y

    y_esq = y_uos_inicio
    y_dir = y_uos_inicio

    largura_uo = (
        largura - 110
    ) / 2


    for nome_uo in coluna_esquerda:

        linhas = simpleSplit(
            f"• {nome_uo}",
            "Helvetica",
            8.5,
            largura_uo
        )

        for linha in linhas:

            pdf.drawString(
                40,
                y_esq,
                linha
            )

            y_esq -= 12

        y_esq -= 2


    for nome_uo in coluna_direita:

        linhas = simpleSplit(
            f"• {nome_uo}",
            "Helvetica",
            8.5,
            largura_uo
        )

        for linha in linhas:

            pdf.drawString(
                x_direita,
                y_dir,
                linha
            )

            y_dir -= 12

        y_dir -= 2


    y = min(
        y_esq,
        y_dir
    )

    y -= 24


    # ======================================================
    # VISÃO EXECUTIVA
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y,
        "VISÃO EXECUTIVA"
    )

    y -= 22


    # ======================================================
    # CARDS
    # ======================================================

    kpis = preview.get(
        "kpis",
        {}
    )

    matriculas = kpis.get(
        "matriculas",
        {}
    )

    hora_aluno = kpis.get(
        "hora_aluno",
        {}
    )

    receita = kpis.get(
        "receita",
        {}
    )

    turmas = kpis.get(
        "turmas",
        {}
    )


    margem_cards = 38
    espacamento_cards = 8
    altura_card = 88

    largura_card = (
        largura
        - (margem_cards * 2)
        - (espacamento_cards * 3)
    ) / 4

    y_cards = y - altura_card


    texto_matriculas = _texto_atingimento(
        matriculas.get(
            "realizado",
            0
        ),
        matriculas.get(
            "meta",
            0
        )
    )

    texto_hora_aluno = _texto_atingimento(
        hora_aluno.get(
            "realizado",
            0
        ),
        hora_aluno.get(
            "meta",
            0
        )
    )

    texto_receita = _texto_atingimento(
        receita.get(
            "realizado",
            0
        ),
        receita.get(
            "meta",
            0
        )
    )


    _card(
        pdf,
        margem_cards,
        y_cards,
        largura_card,
        altura_card,
        "Matrículas",
        _num(
            matriculas.get(
                "realizado",
                0
            )
        ),
        (
            f"Meta: "
            f"{_num(matriculas.get('meta', 0))}"
            f" • Atingimento: {texto_matriculas}"
        ),
        colors.HexColor("#2563eb")
    )


    _card(
        pdf,
        margem_cards
        + largura_card
        + espacamento_cards,
        y_cards,
        largura_card,
        altura_card,
        "Hora-Aluno",
        _num(
            hora_aluno.get(
                "realizado",
                0
            )
        ),
        (
            f"Meta: "
            f"{_num(hora_aluno.get('meta', 0))}"
            f" • Atingimento: {texto_hora_aluno}"
        ),
        colors.HexColor("#16a34a")
    )


    _card(
        pdf,
        margem_cards
        + (
            largura_card
            + espacamento_cards
        ) * 2,
        y_cards,
        largura_card,
        altura_card,
        "Receita",
        _moeda(
            receita.get(
                "realizado",
                0
            )
        ),
        (
            f"Meta: "
            f"{_moeda(receita.get('meta', 0))}"
            f" • Atingimento: {texto_receita}"
        ),
        colors.HexColor("#f59e0b")
    )


    _card(
        pdf,
        margem_cards
        + (
            largura_card
            + espacamento_cards
        ) * 3,
        y_cards,
        largura_card,
        altura_card,
        "Turmas",
        _num(
            turmas.get(
                "total",
                0
            )
        ),
        "Referência: período",
        colors.HexColor("#6d5dfc")
    )


    # ======================================================
    # RODAPÉ
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 1"
    )

    # ======================================================
    # PÁGINA 2 — EVOLUÇÃO MENSAL DOS INDICADORES
    # ======================================================

    pdf.showPage()

    # Garante novamente o tamanho correto da página
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "EVOLUÇÃO MENSAL DOS INDICADORES"
    )


    # ======================================================
    # IDENTIFICAÇÃO DO RECORTE
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        (
            f"Ano: {ano} • Período: {periodo}"
        )
    )


    pdf.setFont(
        "Helvetica-Bold",
        9
    )

    pdf.drawString(
        40,
        altura - 165,
        (
            f"{str(regiao).upper()} • "
            f"{str(subregiao).upper()}"
        )
    )


    # ======================================================
    # DADOS PREDITIVOS
    # Mesmas regras utilizadas na Análise Preditiva
    # ======================================================

    preditivo = preview.get(
        "preditivo",
        {}
    )

    graf_matriculas = preditivo.get(
        "matriculas",
        {}
    )

    graf_hora_aluno = preditivo.get(
        "hora_aluno",
        {}
    )

    graf_receita = preditivo.get(
        "receita",
        {}
    )


    # ======================================================
    # GRÁFICO — MATRÍCULAS
    # ======================================================

    realizado_matriculas = (
        graf_matriculas.get("realizado", [])
        or [None] * 12
    )

    previsao_matriculas = (
        graf_matriculas.get("previsao", [])
        or [None] * 12
    )

    for i in range(12):

        realizado = (
            realizado_matriculas[i]
            if i < len(realizado_matriculas)
            else None
        )

        previsao = (
            previsao_matriculas[i]
            if i < len(previsao_matriculas)
            else None
        )
    
    _grafico_colunas_preditivo(
        pdf,
        40,
        altura - 335,
        largura - 80,
        145,
        "Matrículas • Realizadas e Projetadas",
        realizado_matriculas,
        previsao_matriculas,
        graf_matriculas.get(
            "meta",
            []
        ),
        "Projeção",
        "#f59e0b"
    )


    # ======================================================
    # GRÁFICO — HORA-ALUNO
    # ======================================================

    realizado_ha = (
        graf_hora_aluno.get("realizado", [])
        or [None] * 12
    )

    garantida_ha = (
        graf_hora_aluno.get("garantida", [])
        or graf_hora_aluno.get("previsao", [])
        or [None] * 12
    )

    for i in range(12):

        realizado = (
            realizado_ha[i]
            if i < len(realizado_ha)
            else None
        )

        garantida = (
            garantida_ha[i]
            if i < len(garantida_ha)
            else None
        )
    
    _grafico_colunas_preditivo(
        pdf,
        40,
        altura - 515,
        largura - 80,
        145,
        "Hora-Aluno • Realizada e Garantida",
        realizado_ha,
        garantida_ha,
        graf_hora_aluno.get(
            "meta",
            []
        ),
        "HA Garantida",
        "#16a34a"
    )


    # ======================================================
    # GRÁFICO — RECEITA
    # ======================================================

    realizado_receita = (
        graf_receita.get("realizado", [])
        or [None] * 12
    )

    contratada_receita = (
        graf_receita.get("contratada", [])
        or [None] * 12
    )

    for i in range(12):

        realizado = (
            realizado_receita[i]
            if i < len(realizado_receita)
            else None
        )

        contratada = (
            contratada_receita[i]
            if i < len(contratada_receita)
            else None
        )
    
    _grafico_colunas_preditivo(
        pdf,
        40,
        altura - 695,
        largura - 80,
        145,
        "Receita • Realizada e Contratada",
        realizado_receita,
        contratada_receita,
        graf_receita.get(
            "meta",
            []
        ),
        "Receita Contratada",
        "#16a34a",
        eh_moeda=True
    )


    # ======================================================
    # RODAPÉ — PÁGINA 2
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 2"
    )

    # ======================================================
    # PÁGINA 3 — ANÁLISE PREDITIVA
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina

    # ======================================================
    # CABEÇALHO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )

    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "ANÁLISE PREDITIVA"
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )

    pdf.setFont(
        "Helvetica-Bold",
        9
    )

    pdf.drawString(
        40,
        altura - 165,
        (
            f"{str(regiao).upper()} • "
            f"{str(subregiao).upper()}"
        )
    )

    # ======================================================
    # DADOS
    # ======================================================

    preditivo = preview.get(
        "preditivo",
        {}
    )

    dados_mat = preditivo.get(
        "matriculas",
        {}
    )

    dados_ha = preditivo.get(
        "hora_aluno",
        {}
    )

    dados_rec = preditivo.get(
        "receita",
        {}
    )

    def soma_lista(lista):
        return sum(
            float(v or 0)
            for v in (lista or [])
        )

    # Matrículas
    mat_realizado = soma_lista(
        dados_mat.get("realizado")
    )

    mat_futuro = soma_lista(
        dados_mat.get("previsao")
    )

    mat_meta = soma_lista(
        dados_mat.get("meta")
    )

    mat_fechamento = (
        mat_realizado
        + mat_futuro
    )

    mat_pct = (
        mat_fechamento / mat_meta * 100
        if mat_meta > 0
        else 0
    )

    mat_gap = (
        mat_meta
        - mat_fechamento
    )

    # Hora-Aluno
    ha_realizado = soma_lista(
        dados_ha.get("realizado")
    )

    ha_futuro = soma_lista(
        dados_ha.get("garantida")
        or dados_ha.get("previsao")
    )

    ha_meta = soma_lista(
        dados_ha.get("meta")
    )

    ha_fechamento = (
        ha_realizado
        + ha_futuro
    )

    ha_pct = (
        ha_fechamento / ha_meta * 100
        if ha_meta > 0
        else 0
    )

    ha_gap = (
        ha_meta
        - ha_fechamento
    )

    # Receita
    rec_realizado = soma_lista(
        dados_rec.get("realizado")
    )

    rec_futuro = soma_lista(
        dados_rec.get("contratada")
    )

    rec_meta = soma_lista(
        dados_rec.get("meta")
    )

    rec_fechamento = (
        rec_realizado
        + rec_futuro
    )

    rec_pct = (
        rec_fechamento / rec_meta * 100
        if rec_meta > 0
        else 0
    )

    rec_gap = (
        rec_meta
        - rec_fechamento
    )

    # ======================================================
    # CARDS EXECUTIVOS — FECHAMENTO PROJETADO
    # ======================================================

    y_cards = altura - 270

    margem_cards = 40
    espacamento_cards = 10

    largura_card = (
        largura
        - (margem_cards * 2)
        - (espacamento_cards * 2)
    ) / 3

    altura_card = 92


    # ------------------------------------------------------
    # CARD MATRÍCULAS
    # ------------------------------------------------------

    _card(
        pdf,
        margem_cards,
        y_cards,
        largura_card,
        altura_card,
        "Matrículas",
        _num(mat_fechamento),
        (
            f"Fechamento previsto • "
            f"{mat_pct:.1f}% da meta"
        ).replace(".", ","),
        colors.HexColor("#2563eb")
    )


    # ------------------------------------------------------
    # CARD HORA-ALUNO
    # ------------------------------------------------------

    _card(
        pdf,
        margem_cards
        + largura_card
        + espacamento_cards,
        y_cards,
        largura_card,
        altura_card,
        "Hora-Aluno",
        _num(ha_fechamento),
        (
            f"Realizado + garantida • "
            f"{ha_pct:.1f}% da meta"
        ).replace(".", ","),
        colors.HexColor("#16a34a")
    )


    # ------------------------------------------------------
    # CARD RECEITA
    # ------------------------------------------------------

    _card(
        pdf,
        margem_cards
        + (
            largura_card
            + espacamento_cards
        ) * 2,
        y_cards,
        largura_card,
        altura_card,
        "Receita",
        _moeda(rec_fechamento),
        (
            f"Realizado + contratada • "
            f"{rec_pct:.1f}% da meta"
        ).replace(".", ","),
        colors.HexColor("#f59e0b")
    )

    # ======================================================
    # TABELA — CENÁRIO DE FECHAMENTO
    # ======================================================

    y_tabela = y_cards - 55

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        11
    )

    pdf.drawString(
        40,
        y_tabela,
        "CENÁRIO DE FECHAMENTO"
    )

    y_tabela -= 24


    # ======================================================
    # CONFIGURAÇÃO DA TABELA
    # ======================================================

    x0 = 40

    # A tabela deve terminar na mesma margem direita
    # utilizada pelos cards.
    largura_tabela = largura - 80

    colunas_base = [
        92,   # Indicador
        78,   # Realizado
        78,   # Futuro
        92,   # Fechamento
        82,   # Meta
        52,   # % Meta
        72,   # Gap
    ]

    fator_colunas = (
        largura_tabela
        / sum(colunas_base)
    )

    colunas = [
        largura_coluna * fator_colunas
        for largura_coluna in colunas_base
    ]

    cabecalhos = [
        "INDICADOR",
        "REALIZADO",
        "FUTURO",
        "FECHAMENTO",
        "META",
        "% META",
        "GAP"
    ]

    altura_linha = 30


    # ======================================================
    # CABEÇALHO DA TABELA
    # ======================================================

    x_atual = x0

    pdf.setFillColor(
        colors.HexColor("#f1f5f9")
    )

    pdf.rect(
        x0,
        y_tabela - altura_linha,
        sum(colunas),
        altura_linha,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#475569")
    )

    pdf.setFont(
        "Helvetica-Bold",
        6.5
    )

    for titulo_coluna, largura_col in zip(
        cabecalhos,
        colunas
    ):

        pdf.drawString(
            x_atual + 8,
            y_tabela - 19,
            titulo_coluna
        )

        x_atual += largura_col


    y_tabela -= altura_linha


    # ======================================================
    # DADOS DAS LINHAS
    # ======================================================

    linhas_tabela = [
        {
            "indicador": "Matrículas",
            "realizado": _num(mat_realizado),
            "futuro": _num(mat_futuro),
            "fechamento": _num(mat_fechamento),
            "meta": _num(mat_meta),
            "pct": f"{mat_pct:.1f}%".replace(".", ","),
            "gap": _num(abs(mat_gap)),
            "saldo": mat_gap,
        },
        {
            "indicador": "Hora-Aluno",
            "realizado": _num(ha_realizado),
            "futuro": _num(ha_futuro),
            "fechamento": _num(ha_fechamento),
            "meta": _num(ha_meta),
            "pct": f"{ha_pct:.1f}%".replace(".", ","),
            "gap": _num(abs(ha_gap)),
            "saldo": ha_gap,
        },
        {
            "indicador": "Receita",
            "realizado": _moeda(rec_realizado),
            "futuro": _moeda(rec_futuro),
            "fechamento": _moeda(rec_fechamento),
            "meta": _moeda(rec_meta),
            "pct": f"{rec_pct:.1f}%".replace(".", ","),
            "gap": _moeda(abs(rec_gap)),
            "saldo": rec_gap,
        },
    ]


    for indice, linha in enumerate(
        linhas_tabela
    ):

        # fundo alternado
        if indice % 2 == 0:
            pdf.setFillColor(
                colors.HexColor("#ffffff")
            )
        else:
            pdf.setFillColor(
                colors.HexColor("#f8fafc")
            )

        pdf.rect(
            x0,
            y_tabela - altura_linha,
            sum(colunas),
            altura_linha,
            fill=True,
            stroke=False
        )


        # linha separadora
        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )

        pdf.line(
            x0,
            y_tabela - altura_linha,
            x0 + sum(colunas),
            y_tabela - altura_linha
        )


        valores = [
            linha["indicador"],
            linha["realizado"],
            linha["futuro"],
            linha["fechamento"],
            linha["meta"],
            linha["pct"],
            linha["gap"],
        ]

        x_atual = x0


        for i, (
            valor,
            largura_col
        ) in enumerate(
            zip(
                valores,
                colunas
            )
        ):

            # Indicador
            if i == 0:

                pdf.setFillColor(
                    colors.HexColor("#071b52")
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7.5
                )

                pdf.drawString(
                    x_atual + 8,
                    y_tabela - 19,
                    str(valor)
                )

            else:

                pdf.setFont(
                    "Helvetica",
                    7
                )

                # Percentual
                if i == 5:

                    pct_valor = float(
                        str(
                            linha["pct"]
                        )
                        .replace("%", "")
                        .replace(",", ".")
                    )

                    pdf.setFillColor(
                        _cor_status_pct(
                            pct_valor,
                            meta=1,
                            realizado=1
                        )
                    )

                # Gap
                elif i == 6:

                    pdf.setFillColor(
                        colors.HexColor("#334155")
                    )


                pdf.drawString(
                    x_atual + 8,
                    y_tabela - 19,
                    str(valor)
                )


            x_atual += largura_col


        y_tabela -= altura_linha

    # ======================================================
    # LEGENDA — STATUS DOS INDICADORES
    # ======================================================

    y_legenda = y_tabela - 28

    _legenda_status(
        pdf,
        40,
        y_legenda
    )

    # Como a legenda ocupa duas linhas,
    # posicionamos a leitura executiva abaixo dela.
    y_legenda -= 58
    
    # ======================================================
    # LEITURA EXECUTIVA
    # ======================================================

    y_leitura = y_legenda - 18

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_leitura,
        "LEITURA EXECUTIVA"
    )

    y_leitura -= 20


    # ======================================================
    # TEXTOS AUTOMÁTICOS
    # ======================================================

    leituras = []


    # ------------------------------------------------------
    # MATRÍCULAS
    # ------------------------------------------------------

    if mat_meta <= 0:

        texto_mat = (
            "Matrículas: não há meta anual definida para o "
            "recorte analisado."
        )

    elif mat_fechamento >= mat_meta:

        superacao_mat = (
            mat_fechamento
            - mat_meta
        )

        texto_mat = (
            f"Matrículas: o fechamento projetado é de "
            f"{_num(mat_fechamento)}, equivalente a "
            f"{_pct(mat_pct)} da meta anual, com superação "
            f"estimada de {_num(superacao_mat)} matrículas."
        )

    else:

        texto_mat = (
            f"Matrículas: o fechamento projetado é de "
            f"{_num(mat_fechamento)}, equivalente a "
            f"{_pct(mat_pct)} da meta anual. Para atingir "
            f"100%, ainda serão necessárias "
            f"{_num(mat_gap)} matrículas."
        )

    leituras.append(
        texto_mat
    )


    # ------------------------------------------------------
    # HORA-ALUNO
    # ------------------------------------------------------

    if ha_meta <= 0:

        texto_ha = (
            "Hora-Aluno: não há meta anual definida para o "
            "recorte analisado."
        )

    elif ha_fechamento >= ha_meta:

        superacao_ha = (
            ha_fechamento
            - ha_meta
        )

        texto_ha = (
            f"Hora-Aluno: o realizado somado à HA garantida "
            f"totaliza {_num(ha_fechamento)}, cobrindo "
            f"{_pct(ha_pct)} da meta anual, com superação "
            f"estimada de {_num(superacao_ha)} horas-aluno."
        )

    else:

        texto_ha = (
            f"Hora-Aluno: o realizado somado à HA garantida "
            f"totaliza {_num(ha_fechamento)}, cobrindo "
            f"{_pct(ha_pct)} da meta anual. Permanecem "
            f"{_num(ha_gap)} horas-aluno a gerar além da "
            f"carga já garantida."
        )

    leituras.append(
        texto_ha
    )


    # ------------------------------------------------------
    # RECEITA
    # ------------------------------------------------------

    if rec_meta <= 0:

        texto_rec = (
            "Receita: não há meta anual definida para o "
            "recorte analisado."
        )

    elif rec_fechamento >= rec_meta:

        superacao_rec = (
            rec_fechamento
            - rec_meta
        )

        texto_rec = (
            f"Receita: o realizado somado à receita contratada "
            f"totaliza {_moeda(rec_fechamento)}, equivalente a "
            f"{_pct(rec_pct)} da meta anual, com superação "
            f"estimada de {_moeda(superacao_rec)}."
        )

    else:

        texto_rec = (
            f"Receita: o realizado somado à receita contratada "
            f"totaliza {_moeda(rec_fechamento)}, equivalente a "
            f"{_pct(rec_pct)} da meta anual. Para atingir "
            f"100%, ainda será necessário realizar "
            f"{_moeda(rec_gap)}."
        )

    leituras.append(
        texto_rec
    )


    # ======================================================
    # BOX — LEITURA EXECUTIVA
    # ======================================================

    largura_box = largura - 80
    x_box = 40

    padding_x = 18
    padding_top = 18
    padding_bottom = 16

    largura_texto_box = (
        largura_box
        - (padding_x * 2)
        - 8
    )

    # ------------------------------------------------------
    # PREPARA AS LINHAS ANTES DE DESENHAR O BOX
    # ------------------------------------------------------

    leituras_formatadas = []

    for texto in leituras:

        # Separa "Indicador:" do restante do texto
        if ":" in texto:

            indicador, corpo = texto.split(
                ":",
                1
            )

        else:

            indicador = ""
            corpo = texto

        linhas_corpo = simpleSplit(
            corpo.strip(),
            "Helvetica",
            8,
            largura_texto_box
        )

        leituras_formatadas.append(
            (
                indicador.upper(),
                linhas_corpo
            )
        )

    # ------------------------------------------------------
    # CALCULA ALTURA NECESSÁRIA DO BOX
    # ------------------------------------------------------

    altura_conteudo = 0

    for indicador, linhas_corpo in leituras_formatadas:

        # título do indicador
        altura_conteudo += 12

        # linhas do texto
        altura_conteudo += (
            len(linhas_corpo) * 11
        )

        # espaço entre indicadores
        altura_conteudo += 10

    altura_box = (
        padding_top
        + altura_conteudo
        + padding_bottom
    )

    # ------------------------------------------------------
    # POSIÇÃO
    # ------------------------------------------------------

    y_box_topo = y_leitura + 8

    y_box = (
        y_box_topo
        - altura_box
    )

    # ------------------------------------------------------
    # FUNDO
    # ------------------------------------------------------

    pdf.setFillColor(
        colors.HexColor("#f8fafc")
    )

    pdf.setStrokeColor(
        colors.HexColor("#e2e8f0")
    )

    pdf.roundRect(
        x_box,
        y_box,
        largura_box,
        altura_box,
        8,
        fill=True,
        stroke=True
    )

    # ------------------------------------------------------
    # BARRA LATERAL AZUL
    # ------------------------------------------------------

    pdf.setFillColor(
        colors.HexColor("#2563eb")
    )

    pdf.roundRect(
        x_box,
        y_box,
        4,
        altura_box,
        2,
        fill=True,
        stroke=False
    )

    # ------------------------------------------------------
    # CONTEÚDO
    # ------------------------------------------------------

    y_texto = (
        y_box
        + altura_box
        - padding_top
    )

    for indicador, linhas_corpo in leituras_formatadas:

        # Nome do indicador
        pdf.setFillColor(
            colors.HexColor("#071b52")
        )

        pdf.setFont(
            "Helvetica-Bold",
            8.2
        )

        pdf.drawString(
            x_box + padding_x,
            y_texto,
            indicador
        )

        y_texto -= 13

        # Texto
        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        pdf.setFont(
            "Helvetica",
            8
        )

        for linha in linhas_corpo:

            pdf.drawString(
                x_box + padding_x,
                y_texto,
                linha
            )

            y_texto -= 11

        y_texto -= 10

    # ======================================================
    # RODAPÉ — PÁGINA 3
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 3"
    )


    pdf.save()

    buffer.seek(0)

    return buffer

def gerar_pdf_relatorio_desempenho_regiao(
    preview,
    orientacao="retrato"
):
    # ======================================================
    # CONFIGURAÇÃO
    # ======================================================

    if orientacao == "paisagem":
        pagina = landscape(A4)
    else:
        pagina = A4

    largura, altura = pagina

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=pagina
    )


    # ======================================================
    # DADOS
    # ======================================================

    cabecalho = preview.get(
        "cabecalho_desempenho_regiao",
        {}
    )

    regiao = (
        cabecalho.get("regiao")
        or "REGIÃO"
    )

    subregioes = (
        cabecalho.get("subregioes")
        or []
    )

    uos = (
        cabecalho.get("uos")
        or []
    )

    geope = (
        cabecalho.get("geope")
        or "-"
    )

    # ======================================================
    # CONTEXTO — ANO E PERÍODO
    # ======================================================

    contexto = preview.get(
        "contexto_desempenho_regiao",
        {}
    )

    ano = (
        contexto.get("ano")
        or "-"
    )

    periodo = (
        contexto.get("periodo")
        or "-"
    )


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "DESEMPENHO POR REGIÃO"
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # INFORMAÇÕES TERRITORIAIS
    # ======================================================

    y = altura - 178

    coluna_esq_x = 40
    coluna_dir_x = largura / 2 + 20


    # ======================================================
    # REGIÃO E GEOPE(S) — MESMA LINHA
    # ======================================================

    y = altura - 178

    coluna_esq_x = 40
    coluna_dir_x = largura / 2 + 20


    # ======================================================
    # TÍTULOS
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        9
    )

    pdf.drawString(
        coluna_esq_x,
        y,
        "REGIÃO"
    )

    pdf.drawString(
        coluna_dir_x,
        y,
        "GEOPE(S)"
    )

    y -= 20


    # ======================================================
    # VALOR — REGIÃO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#334155")
    )

    pdf.setFont(
        "Helvetica",
        8.5
    )

    pdf.drawString(
        coluna_esq_x,
        y,
        f"• {str(regiao).upper()}"
    )


    # ======================================================
    # VALORES — GEOPE(S)
    # ======================================================

    if isinstance(geope, str):

        lista_geope = [
            nome.strip()
            for nome in geope.split(",")
            if nome.strip()
        ]

    elif isinstance(geope, (list, tuple)):

        lista_geope = [
            str(nome).strip()
            for nome in geope
            if nome
        ]

    else:

        lista_geope = []


    largura_maxima_geope = (
        largura
        - coluna_dir_x
        - 40
    )

    y_geope = y

    pdf.setFillColor(
        colors.HexColor("#334155")
    )

    pdf.setFont(
        "Helvetica",
        8.5
    )

    for nome_geope in lista_geope:

        texto_geope = (
            f"• {nome_geope.upper()}"
        )

        linhas_geope = simpleSplit(
            texto_geope,
            "Helvetica",
            8.5,
            largura_maxima_geope
        )

        for linha_geope in linhas_geope:

            pdf.drawString(
                coluna_dir_x,
                y_geope,
                linha_geope
            )

            y_geope -= 12

        y_geope -= 3


    # ======================================================
    # SUB-REGIÕES E UNIDADES OPERACIONAIS
    # ======================================================

    y_lista = min(
        y - 40,
        y_geope - 28
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        9
    )

    pdf.drawString(
        coluna_esq_x,
        y_lista,
        "SUB-REGIÕES"
    )

    pdf.drawString(
        coluna_dir_x,
        y_lista,
        "UNIDADES OPERACIONAIS"
    )


    # ======================================================
    # LISTAS
    # ======================================================

    y_lista -= 20

    pdf.setFillColor(
        colors.HexColor("#334155")
    )

    pdf.setFont(
        "Helvetica",
        8.5
    )

    y_sub = y_lista
    y_uo = y_lista


    # SUB-REGIÕES — COLUNA ESQUERDA

    for nome_subregiao in subregioes:

        pdf.drawString(
            coluna_esq_x,
            y_sub,
            f"• {str(nome_subregiao).upper()}"
        )

        y_sub -= 15


    # UNIDADES OPERACIONAIS — COLUNA DIREITA

    largura_maxima_uo = (
        largura
        - coluna_dir_x
        - 40
    )

    for nome_uo in uos:

        texto_uo = (
            f"• {str(nome_uo).upper()}"
        )

        linhas_uo = simpleSplit(
            texto_uo,
            "Helvetica",
            8.5,
            largura_maxima_uo
        )

        for linha_uo in linhas_uo:

            pdf.drawString(
                coluna_dir_x,
                y_uo,
                linha_uo
            )

            y_uo -= 12

        y_uo -= 3


    # ======================================================
    # POSIÇÃO FINAL DO BLOCO TERRITORIAL
    # ======================================================

    y = min(
        y_sub,
        y_uo
    )

    # ======================================================
    # VISÃO EXECUTIVA
    # ======================================================

    y -= 28

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y,
        "VISÃO EXECUTIVA"
    )

    y -= 22


    # ======================================================
    # KPIs
    # ======================================================

    kpis = preview.get(
        "kpis",
        {}
    )

    matriculas = kpis.get(
        "matriculas",
        {}
    )

    hora_aluno = kpis.get(
        "hora_aluno",
        {}
    )

    receita = kpis.get(
        "receita",
        {}
    )

    turmas = kpis.get(
        "turmas",
        {}
    )


    # ======================================================
    # CONFIGURAÇÃO DOS CARDS
    # ======================================================

    margem_cards = 38
    espacamento_cards = 8
    altura_card = 88

    largura_card = (
        largura
        - (margem_cards * 2)
        - (espacamento_cards * 3)
    ) / 4

    y_cards = (
        y
        - altura_card
    )


    # ======================================================
    # TEXTOS DE ATINGIMENTO
    # ======================================================

    texto_matriculas = _texto_atingimento(
        matriculas.get(
            "realizado",
            0
        ),
        matriculas.get(
            "meta",
            0
        )
    )

    texto_hora_aluno = _texto_atingimento(
        hora_aluno.get(
            "realizado",
            0
        ),
        hora_aluno.get(
            "meta",
            0
        )
    )

    texto_receita = _texto_atingimento(
        receita.get(
            "realizado",
            0
        ),
        receita.get(
            "meta",
            0
        )
    )


    # ======================================================
    # CARD — MATRÍCULAS
    # ======================================================

    _card(
        pdf,
        margem_cards,
        y_cards,
        largura_card,
        altura_card,
        "Matrículas",
        _num(
            matriculas.get(
                "realizado",
                0
            )
        ),
        (
            f"Meta: "
            f"{_num(matriculas.get('meta', 0))}"
            f" • Atingimento: {texto_matriculas}"
        ),
        colors.HexColor("#2563eb")
    )


    # ======================================================
    # CARD — HORA-ALUNO
    # ======================================================

    _card(
        pdf,
        margem_cards
        + largura_card
        + espacamento_cards,
        y_cards,
        largura_card,
        altura_card,
        "Hora-Aluno",
        _num(
            hora_aluno.get(
                "realizado",
                0
            )
        ),
        (
            f"Meta: "
            f"{_num(hora_aluno.get('meta', 0))}"
            f" • Atingimento: {texto_hora_aluno}"
        ),
        colors.HexColor("#16a34a")
    )


    # ======================================================
    # CARD — RECEITA
    # ======================================================

    _card(
        pdf,
        margem_cards
        + (
            largura_card
            + espacamento_cards
        ) * 2,
        y_cards,
        largura_card,
        altura_card,
        "Receita",
        _moeda(
            receita.get(
                "realizado",
                0
            )
        ),
        (
            f"Meta: "
            f"{_moeda(receita.get('meta', 0))}"
            f" • Atingimento: {texto_receita}"
        ),
        colors.HexColor("#f59e0b")
    )


    # ======================================================
    # CARD — TURMAS
    # ======================================================

    _card(
        pdf,
        margem_cards
        + (
            largura_card
            + espacamento_cards
        ) * 3,
        y_cards,
        largura_card,
        altura_card,
        "Turmas",
        _num(
            turmas.get(
                "total",
                0
            )
        ),
        "Referência: período",
        colors.HexColor("#6d5dfc")
    )


    # ======================================================
    # RODAPÉ
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 1"
    )

    # ======================================================
    # PÁGINA 2 — COMPARATIVO ENTRE SUB-REGIÕES
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "COMPARATIVO ENTRE SUB-REGIÕES"
    )


    # ======================================================
    # CONTEXTO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    pdf.drawString(
        40,
        altura - 165,
        str(regiao).upper()
    )


    # ======================================================
    # DADOS DAS SUB-REGIÕES
    # ======================================================

    desempenho_subregioes = (
        preview.get(
            "desempenho_subregioes",
            []
        )
        or []
    )

    # Mantém apenas as sub-regiões da região selecionada
    # O preview já foi gerado com o filtro de Região.
    desempenho_subregioes = sorted(
        desempenho_subregioes,
        key=lambda item: str(
            item.get("subregiao") or ""
        ).casefold()
    )


    # ======================================================
    # TÍTULO DA TABELA
    # ======================================================

    y_tabela = altura - 205

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_tabela,
        "DESEMPENHO DAS SUB-REGIÕES"
    )

    y_tabela -= 24


    # ======================================================
    # CONFIGURAÇÃO DA TABELA
    # ======================================================

    x0 = 40
    largura_tabela = largura - 80

    colunas_base = [
        115,  # Sub-região
        65,   # Matrículas
        52,   # % Meta
        72,   # Hora-Aluno
        52,   # % Meta
        92,   # Receita
        52,   # % Meta
    ]

    fator_colunas = (
        largura_tabela
        / sum(colunas_base)
    )

    colunas = [
        largura_col * fator_colunas
        for largura_col in colunas_base
    ]

    cabecalhos = [
        "SUB-REGIÃO",
        "MATRÍCULAS",
        "% META",
        "HORA-ALUNO",
        "% META",
        "RECEITA",
        "% META",
    ]

    altura_linha = 34


    # ======================================================
    # CABEÇALHO DA TABELA
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#f1f5f9")
    )

    pdf.rect(
        x0,
        y_tabela - altura_linha,
        largura_tabela,
        altura_linha,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#475569")
    )

    pdf.setFont(
        "Helvetica-Bold",
        6.5
    )

    x_atual = x0

    for titulo_coluna, largura_col in zip(
        cabecalhos,
        colunas
    ):

        pdf.drawString(
            x_atual + 6,
            y_tabela - 21,
            titulo_coluna
        )

        x_atual += largura_col

    y_tabela -= altura_linha


    # ======================================================
    # FUNÇÃO PARA COR DO PERCENTUAL
    # ======================================================

    def cor_percentual(valor):

        valor = float(valor or 0)

        if valor >= 100:
            return colors.HexColor("#16a34a")

        if valor >= 75:
            return colors.HexColor("#2563eb")

        if valor >= 51:
            return colors.HexColor("#f59e0b")

        return colors.HexColor("#dc2626")


    # ======================================================
    # LINHAS DA TABELA
    # ======================================================

    for indice, item in enumerate(
        desempenho_subregioes
    ):

        subregiao_nome = (
            item.get("subregiao")
            or "-"
        )

        mat_real = float(
            item.get(
                "matriculas_real",
                0
            )
            or 0
        )

        mat_pct = float(
            item.get(
                "matriculas_pct",
                0
            )
            or 0
        )

        ha_real = float(
            item.get(
                "hora_aluno_real",
                0
            )
            or 0
        )

        ha_pct = float(
            item.get(
                "hora_aluno_pct",
                0
            )
            or 0
        )

        rec_real = float(
            item.get(
                "receita_real",
                0
            )
            or 0
        )

        rec_pct = float(
            item.get(
                "receita_pct",
                0
            )
            or 0
        )


        # Fundo alternado

        if indice % 2 == 0:

            pdf.setFillColor(
                colors.white
            )

        else:

            pdf.setFillColor(
                colors.HexColor("#f8fafc")
            )

        pdf.rect(
            x0,
            y_tabela - altura_linha,
            largura_tabela,
            altura_linha,
            fill=True,
            stroke=False
        )


        # Linha inferior

        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )

        pdf.line(
            x0,
            y_tabela - altura_linha,
            x0 + largura_tabela,
            y_tabela - altura_linha
        )


        x_atual = x0


        # --------------------------------------------------
        # SUB-REGIÃO
        # --------------------------------------------------

        pdf.setFillColor(
            colors.HexColor("#071b52")
        )

        pdf.setFont(
            "Helvetica-Bold",
            7
        )

        pdf.drawString(
            x_atual + 6,
            y_tabela - 21,
            str(subregiao_nome).upper()
        )

        x_atual += colunas[0]


        # --------------------------------------------------
        # MATRÍCULAS
        # --------------------------------------------------

        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        pdf.setFont(
            "Helvetica",
            7
        )

        pdf.drawString(
            x_atual + 6,
            y_tabela - 21,
            _num(mat_real)
        )

        x_atual += colunas[1]


        # % MATRÍCULAS

        pdf.setFillColor(
            cor_percentual(
                mat_pct
            )
        )

        pdf.setFont(
            "Helvetica-Bold",
            7
        )

        pdf.drawString(
            x_atual + 6,
            y_tabela - 21,
            _pct(mat_pct)
        )

        x_atual += colunas[2]


        # --------------------------------------------------
        # HORA-ALUNO
        # --------------------------------------------------

        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        pdf.setFont(
            "Helvetica",
            7
        )

        pdf.drawString(
            x_atual + 6,
            y_tabela - 21,
            _num(ha_real)
        )

        x_atual += colunas[3]


        # % HA

        pdf.setFillColor(
            cor_percentual(
                ha_pct
            )
        )

        pdf.setFont(
            "Helvetica-Bold",
            7
        )

        pdf.drawString(
            x_atual + 6,
            y_tabela - 21,
            _pct(ha_pct)
        )

        x_atual += colunas[4]


        # --------------------------------------------------
        # RECEITA
        # --------------------------------------------------

        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        pdf.setFont(
            "Helvetica",
            6.6
        )

        pdf.drawString(
            x_atual + 6,
            y_tabela - 21,
            _moeda(rec_real)
        )

        x_atual += colunas[5]


        # % RECEITA

        pdf.setFillColor(
            cor_percentual(
                rec_pct
            )
        )

        pdf.setFont(
            "Helvetica-Bold",
            7
        )

        pdf.drawString(
            x_atual + 6,
            y_tabela - 21,
            _pct(rec_pct)
        )


        y_tabela -= altura_linha

    # ======================================================
    # LEGENDA — STATUS DOS INDICADORES
    # ======================================================

    y_legenda = y_tabela - 16

    _legenda_status(
        pdf,
        40,
        y_legenda
    )
    
    # ======================================================
    # DESTAQUES DO DESEMPENHO
    # ======================================================

    y_destaques = y_legenda - 72

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_destaques,
        "DESTAQUES DO DESEMPENHO"
    )

    y_destaques -= 22


    # ======================================================
    # IDENTIFICA OS MELHORES RESULTADOS
    # ======================================================

    subregioes_mat_validas = [
        item
        for item in desempenho_subregioes
        if float(
            item.get("matriculas_meta", 0)
            or 0
        ) > 0
    ]

    subregioes_ha_validas = [
        item
        for item in desempenho_subregioes
        if float(
            item.get("hora_aluno_meta", 0)
            or 0
        ) > 0
    ]

    subregioes_rec_validas = [
        item
        for item in desempenho_subregioes
        if float(
            item.get("receita_meta", 0)
            or 0
        ) > 0
    ]


    melhor_mat = (
        max(
            subregioes_mat_validas,
            key=lambda item: float(
                item.get("matriculas_pct", 0)
                or 0
            )
        )
        if subregioes_mat_validas
        else None
    )

    melhor_ha = (
        max(
            subregioes_ha_validas,
            key=lambda item: float(
                item.get("hora_aluno_pct", 0)
                or 0
            )
        )
        if subregioes_ha_validas
        else None
    )

    melhor_rec = (
        max(
            subregioes_rec_validas,
            key=lambda item: float(
                item.get("receita_pct", 0)
                or 0
            )
        )
        if subregioes_rec_validas
        else None
    )


    # ======================================================
    # CONFIGURAÇÃO DOS 3 CARDS
    # ======================================================

    margem_cards_destaque = 40
    espacamento_destaque = 10

    largura_card_destaque = (
        largura
        - (margem_cards_destaque * 2)
        - (espacamento_destaque * 2)
    ) / 3

    altura_card_destaque = 82

    y_cards_destaque = (
        y_destaques
        - altura_card_destaque
    )


    # ======================================================
    # MATRÍCULAS
    # ======================================================

    if melhor_mat:

        nome = str(
            melhor_mat.get("subregiao")
            or "-"
        ).upper()

        pct = float(
            melhor_mat.get(
                "matriculas_pct",
                0
            )
            or 0
        )

        valor = _num(
            melhor_mat.get(
                "matriculas_real",
                0
            )
        )

        detalhe = (
            f"{valor} matrículas"
            f" • {_pct(pct)} da meta"
        )

    else:

        nome = "-"
        detalhe = "Sem meta para comparação"


    _card(
        pdf,
        margem_cards_destaque,
        y_cards_destaque,
        largura_card_destaque,
        altura_card_destaque,
        "Melhor em Matrículas",
        nome,
        detalhe,
        colors.HexColor("#2563eb"),
        espacamento_destaque=True
    )


    # ======================================================
    # HORA-ALUNO
    # ======================================================

    if melhor_ha:

        nome = str(
            melhor_ha.get("subregiao")
            or "-"
        ).upper()

        pct = float(
            melhor_ha.get(
                "hora_aluno_pct",
                0
            )
            or 0
        )

        valor = _num(
            melhor_ha.get(
                "hora_aluno_real",
                0
            )
        )

        detalhe = (
            f"{valor} HA"
            f" • {_pct(pct)} da meta"
        )

    else:

        nome = "-"
        detalhe = "Sem meta para comparação"


    _card(
        pdf,
        margem_cards_destaque
        + largura_card_destaque
        + espacamento_destaque,
        y_cards_destaque,
        largura_card_destaque,
        altura_card_destaque,
        "Melhor em Hora-Aluno",
        nome,
        detalhe,
        colors.HexColor("#16a34a"),
        espacamento_destaque=True
    )


    # ======================================================
    # RECEITA
    # ======================================================

    if melhor_rec:

        nome = str(
            melhor_rec.get("subregiao")
            or "-"
        ).upper()

        pct = float(
            melhor_rec.get(
                "receita_pct",
                0
            )
            or 0
        )

        valor = _moeda(
            melhor_rec.get(
                "receita_real",
                0
            )
        )

        detalhe = (
            f"{valor}"
            f" • {_pct(pct)} da meta"
        )

    else:

        nome = "-"
        detalhe = "Sem meta para comparação"


    _card(
        pdf,
        margem_cards_destaque
        + (
            largura_card_destaque
            + espacamento_destaque
        ) * 2,
        y_cards_destaque,
        largura_card_destaque,
        altura_card_destaque,
        "Melhor em Receita",
        nome,
        detalhe,
        colors.HexColor("#f59e0b"),
        espacamento_destaque=True
    )

    # ======================================================
    # PONTOS DE ATENÇÃO
    # ======================================================

    y_atencao = (
        y_cards_destaque
        - 42
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_atencao,
        "PONTOS DE ATENÇÃO"
    )

    y_atencao -= 22


    # ======================================================
    # MONTA AS LEITURAS AUTOMÁTICAS
    # ======================================================

    pontos_atencao = []

    for item in desempenho_subregioes:

        nome = str(
            item.get("subregiao")
            or "-"
        ).upper()

        mat_meta = float(
            item.get("matriculas_meta", 0)
            or 0
        )

        mat_pct = float(
            item.get("matriculas_pct", 0)
            or 0
        )

        ha_meta = float(
            item.get("hora_aluno_meta", 0)
            or 0
        )

        ha_pct = float(
            item.get("hora_aluno_pct", 0)
            or 0
        )

        rec_meta = float(
            item.get("receita_meta", 0)
            or 0
        )

        rec_pct = float(
            item.get("receita_pct", 0)
            or 0
        )


        indicadores_abaixo = []

        if (
            mat_meta > 0
            and mat_pct < 100
        ):
            indicadores_abaixo.append(
                f"Matrículas ({_pct(mat_pct)})"
            )

        if (
            ha_meta > 0
            and ha_pct < 100
        ):
            indicadores_abaixo.append(
                f"Hora-Aluno ({_pct(ha_pct)})"
            )

        if (
            rec_meta > 0
            and rec_pct < 100
        ):
            indicadores_abaixo.append(
                f"Receita ({_pct(rec_pct)})"
            )


        if indicadores_abaixo:

            pontos_atencao.append(
                f"{nome}: "
                + ", ".join(
                    indicadores_abaixo
                )
            )


    # ======================================================
    # DESENHA O BOX
    # ======================================================

    if pontos_atencao:

        altura_box_atencao = (
            36
            + (
                len(pontos_atencao)
                * 24
            )
        )

        _box_texto(
            pdf,
            40,
            y_atencao
            - altura_box_atencao,
            largura - 80,
            altura_box_atencao,
            "Indicadores abaixo de 100% da meta",
            pontos_atencao,
            colors.HexColor("#fff7ed"),
            colors.HexColor("#f59e0b")
        )

    else:

        _box_texto(
            pdf,
            40,
            y_atencao - 72,
            largura - 80,
            72,
            "Resultado Regional",
            [
                (
                    "Todas as sub-regiões atingiram ou "
                    "superaram as metas nos três indicadores."
                )
            ],
            colors.HexColor("#f0fdf4"),
            colors.HexColor("#16a34a")
        )

    # ======================================================
    # RODAPÉ — PÁGINA 2
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 2"
    )

    # ======================================================
    # PÁGINA 3 — CONTRIBUIÇÃO PARA O RESULTADO REGIONAL
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "CONTRIBUIÇÃO PARA O RESULTADO REGIONAL"
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    pdf.drawString(
        40,
        altura - 165,
        str(regiao).upper()
    )


    # ======================================================
    # TOTAIS REGIONAIS
    # ======================================================

    total_mat = sum(
        float(
            item.get("matriculas_real", 0)
            or 0
        )
        for item in desempenho_subregioes
    )

    total_ha = sum(
        float(
            item.get("hora_aluno_real", 0)
            or 0
        )
        for item in desempenho_subregioes
    )

    total_rec = sum(
        float(
            item.get("receita_real", 0)
            or 0
        )
        for item in desempenho_subregioes
    )


    # ======================================================
    # FUNÇÃO AUXILIAR — PARTICIPAÇÃO
    # ======================================================

    def participacao(valor, total):

        valor = float(valor or 0)
        total = float(total or 0)

        if total <= 0:
            return 0

        return (
            valor / total
        ) * 100


    # ======================================================
    # PREPARA OS DADOS
    # ======================================================

    dados_contribuicao = []

    for item in desempenho_subregioes:

        dados_contribuicao.append({

            "subregiao": (
                item.get("subregiao")
                or "-"
            ),

            "mat_valor": float(
                item.get(
                    "matriculas_real",
                    0
                )
                or 0
            ),

            "mat_pct": participacao(
                item.get(
                    "matriculas_real",
                    0
                ),
                total_mat
            ),

            "ha_valor": float(
                item.get(
                    "hora_aluno_real",
                    0
                )
                or 0
            ),

            "ha_pct": participacao(
                item.get(
                    "hora_aluno_real",
                    0
                ),
                total_ha
            ),

            "rec_valor": float(
                item.get(
                    "receita_real",
                    0
                )
                or 0
            ),

            "rec_pct": participacao(
                item.get(
                    "receita_real",
                    0
                ),
                total_rec
            ),
        })

    # ======================================================
    # MATRÍCULAS
    # ======================================================

    y_secao = altura - 215

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        11
    )

    pdf.drawString(
        40,
        y_secao,
        "MATRÍCULAS"
    )

    y_secao -= 24


    ranking_mat = sorted(
        dados_contribuicao,
        key=lambda item: item["mat_pct"],
        reverse=True
    )

    for item in ranking_mat:

        nome = str(
            item["subregiao"]
        ).upper()

        pct = item["mat_pct"]

        valor = item["mat_valor"]


        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        pdf.setFont(
            "Helvetica-Bold",
            8
        )

        pdf.drawString(
            40,
            y_secao,
            nome
        )


        pdf.setFont(
            "Helvetica",
            8
        )

        pdf.drawRightString(
            largura - 40,
            y_secao,
            (
                f"{_num(valor)}"
                f" • {_pct(pct)}"
            )
        )


        y_secao -= 13


        # Barra de participação

        largura_barra_max = (
            largura - 80
        )

        largura_barra = (
            largura_barra_max
            * pct
            / 100
        )

        pdf.setFillColor(
            colors.HexColor("#e2e8f0")
        )

        pdf.roundRect(
            40,
            y_secao - 3,
            largura_barra_max,
            7,
            3,
            fill=True,
            stroke=False
        )

        pdf.setFillColor(
            colors.HexColor("#2563eb")
        )

        pdf.roundRect(
            40,
            y_secao - 3,
            largura_barra,
            7,
            3,
            fill=True,
            stroke=False
        )

        y_secao -= 24

    # ======================================================
    # HORA-ALUNO
    # ======================================================

    y_secao -= 8

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        11
    )

    pdf.drawString(
        40,
        y_secao,
        "HORA-ALUNO"
    )

    y_secao -= 24


    ranking_ha = sorted(
        dados_contribuicao,
        key=lambda item: item["ha_pct"],
        reverse=True
    )

    for item in ranking_ha:

        nome = str(
            item["subregiao"]
        ).upper()

        pct = item["ha_pct"]

        valor = item["ha_valor"]


        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        pdf.setFont(
            "Helvetica-Bold",
            8
        )

        pdf.drawString(
            40,
            y_secao,
            nome
        )


        pdf.setFont(
            "Helvetica",
            8
        )

        pdf.drawRightString(
            largura - 40,
            y_secao,
            (
                f"{_num(valor)}"
                f" • {_pct(pct)}"
            )
        )


        y_secao -= 13


        largura_barra_max = (
            largura - 80
        )

        largura_barra = (
            largura_barra_max
            * pct
            / 100
        )

        pdf.setFillColor(
            colors.HexColor("#e2e8f0")
        )

        pdf.roundRect(
            40,
            y_secao - 3,
            largura_barra_max,
            7,
            3,
            fill=True,
            stroke=False
        )

        pdf.setFillColor(
            colors.HexColor("#16a34a")
        )

        pdf.roundRect(
            40,
            y_secao - 3,
            largura_barra,
            7,
            3,
            fill=True,
            stroke=False
        )

        y_secao -= 24

    # ======================================================
    # RECEITA
    # ======================================================

    y_secao -= 8

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        11
    )

    pdf.drawString(
        40,
        y_secao,
        "RECEITA"
    )

    y_secao -= 24


    ranking_rec = sorted(
        dados_contribuicao,
        key=lambda item: item["rec_pct"],
        reverse=True
    )

    for item in ranking_rec:

        nome = str(
            item["subregiao"]
        ).upper()

        pct = item["rec_pct"]

        valor = item["rec_valor"]


        pdf.setFillColor(
            colors.HexColor("#334155")
        )

        pdf.setFont(
            "Helvetica-Bold",
            8
        )

        pdf.drawString(
            40,
            y_secao,
            nome
        )


        pdf.setFont(
            "Helvetica",
            8
        )

        pdf.drawRightString(
            largura - 40,
            y_secao,
            (
                f"{_moeda(valor)}"
                f" • {_pct(pct)}"
            )
        )


        y_secao -= 13


        largura_barra_max = (
            largura - 80
        )

        largura_barra = (
            largura_barra_max
            * pct
            / 100
        )

        pdf.setFillColor(
            colors.HexColor("#e2e8f0")
        )

        pdf.roundRect(
            40,
            y_secao - 3,
            largura_barra_max,
            7,
            3,
            fill=True,
            stroke=False
        )

        pdf.setFillColor(
            colors.HexColor("#f59e0b")
        )

        pdf.roundRect(
            40,
            y_secao - 3,
            largura_barra,
            7,
            3,
            fill=True,
            stroke=False
        )

        y_secao -= 24

    # ======================================================
    # RODAPÉ — PÁGINA 3
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 3"
    )

    # ======================================================
    # PÁGINA 4 — EVOLUÇÃO MENSAL DOS INDICADORES
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "EVOLUÇÃO MENSAL DOS INDICADORES"
    )


    # ======================================================
    # ANO / PERÍODO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # REGIÃO
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        9
    )

    pdf.drawString(
        40,
        altura - 165,
        str(regiao).upper()
    )


    # ======================================================
    # DADOS DOS GRÁFICOS
    # ======================================================

    preditivo = preview.get(
        "preditivo",
        {}
    )

    graf_matriculas = preditivo.get(
        "matriculas",
        {}
    )

    graf_hora_aluno = preditivo.get(
        "hora_aluno",
        {}
    )

    graf_receita = preditivo.get(
        "receita",
        {}
    )


    # ======================================================
    # MATRÍCULAS
    # ======================================================

    realizado_matriculas = (
        graf_matriculas.get(
            "realizado",
            []
        )
        or [None] * 12
    )

    previsao_matriculas = (
        graf_matriculas.get(
            "previsao",
            []
        )
        or [None] * 12
    )

    meta_matriculas = (
        graf_matriculas.get(
            "meta",
            []
        )
        or [None] * 12
    )


    _grafico_colunas_preditivo(
        pdf,
        40,
        altura - 335,
        largura - 80,
        145,
        "Matrículas • Realizadas e Projetadas",
        realizado_matriculas,
        previsao_matriculas,
        meta_matriculas,
        "Projeção",
        "#f59e0b"
    )


    # ======================================================
    # HORA-ALUNO
    # ======================================================

    realizado_ha = (
        graf_hora_aluno.get(
            "realizado",
            []
        )
        or [None] * 12
    )

    garantida_ha = (
        graf_hora_aluno.get(
            "garantida",
            []
        )
        or graf_hora_aluno.get(
            "previsao",
            []
        )
        or [None] * 12
    )

    meta_ha = (
        graf_hora_aluno.get(
            "meta",
            []
        )
        or [None] * 12
    )


    _grafico_colunas_preditivo(
        pdf,
        40,
        altura - 515,
        largura - 80,
        145,
        "Hora-Aluno • Realizada e Garantida",
        realizado_ha,
        garantida_ha,
        meta_ha,
        "HA Garantida",
        "#16a34a"
    )


    # ======================================================
    # RECEITA
    # ======================================================

    realizado_receita = (
        graf_receita.get(
            "realizado",
            []
        )
        or [None] * 12
    )

    contratada_receita = (
        graf_receita.get(
            "contratada",
            []
        )
        or [None] * 12
    )

    meta_receita = (
        graf_receita.get(
            "meta",
            []
        )
        or [None] * 12
    )


    _grafico_colunas_preditivo(
        pdf,
        40,
        altura - 695,
        largura - 80,
        145,
        "Receita • Realizada e Contratada",
        realizado_receita,
        contratada_receita,
        meta_receita,
        "Receita Contratada",
        "#16a34a",
        eh_moeda=True
    )


    # ======================================================
    # RODAPÉ — PÁGINA 4
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 4"
    )

    # ======================================================
    # FINALIZA
    # ======================================================

    pdf.save()

    buffer.seek(0)

    return buffer

def gerar_pdf_relatorio_indicadores_detalhados(
    preview,
    orientacao="retrato"
):
    # ======================================================
    # CONFIGURAÇÃO
    # ======================================================

    if orientacao == "paisagem":
        pagina = landscape(A4)
    else:
        pagina = A4

    largura, altura = pagina

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=pagina
    )


    # ======================================================
    # DADOS
    # ======================================================

    cabecalho = preview.get(
        "cabecalho_indicadores_detalhados",
        {}
    )

    indicadores = preview.get(
        "indicadores_detalhados",
        {}
    )

    matriculas = indicadores.get(
        "matriculas",
        {}
    )

    hora_aluno = indicadores.get(
        "hora_aluno",
        {}
    )

    receita = indicadores.get(
        "receita",
        {}
    )


    # ======================================================
    # ANO E PERÍODO
    # ======================================================

    ano = (
        cabecalho.get("ano")
        or preview.get("ano")
        or "-"
    )

    meses = (
        cabecalho.get("meses")
        or preview.get("meses")
        or []
    )

    nomes_meses = {
        1: "Jan",
        2: "Fev",
        3: "Mar",
        4: "Abr",
        5: "Mai",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Set",
        10: "Out",
        11: "Nov",
        12: "Dez",
    }

    if not meses:

        periodo = "Anual"

    elif len(meses) == 1:

        periodo = nomes_meses.get(
            int(meses[0]),
            str(meses[0])
        )

    else:

        meses_ordenados = sorted(
            int(m)
            for m in meses
        )

        periodo = (
            f"{nomes_meses.get(meses_ordenados[0], meses_ordenados[0])}-"
            f"{nomes_meses.get(meses_ordenados[-1], meses_ordenados[-1])}"
        )


    # ======================================================
    # CONTEXTO DOS FILTROS
    # ======================================================

    contexto_partes = []

    regiao = cabecalho.get("regiao")
    subregiao = cabecalho.get("subregiao")
    uo = cabecalho.get("uo")
    programa = cabecalho.get("programa")
    modalidade = cabecalho.get("modalidade")

    if regiao:
        contexto_partes.append(
            f"Região: {regiao}"
        )

    if subregiao:
        contexto_partes.append(
            f"Sub-região: {subregiao}"
        )

    if uo:
        contexto_partes.append(
            f"UO: {uo}"
        )

    if programa:
        contexto_partes.append(
            f"Programa: {programa}"
        )

    if modalidade:
        contexto_partes.append(
            f"Modalidade: {modalidade}"
        )

    contexto = (
        " • ".join(contexto_partes)
        if contexto_partes
        else "Todos os recortes"
    )


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "INDICADORES DETALHADOS"
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # CONTEXTO
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    linhas_contexto = simpleSplit(
        contexto.upper(),
        "Helvetica-Bold",
        8.5,
        largura - 80
    )

    y_contexto = altura - 165

    for linha in linhas_contexto:

        pdf.drawString(
            40,
            y_contexto,
            linha
        )

        y_contexto -= 11


    # ======================================================
    # VISÃO GERAL
    # ======================================================

    y_secao = y_contexto - 28

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_secao,
        "VISÃO GERAL DOS INDICADORES"
    )


    # ======================================================
    # CARDS
    # ======================================================

    margem_cards = 40
    espacamento_cards = 10

    largura_card = (
        largura
        - (margem_cards * 2)
        - (espacamento_cards * 2)
    ) / 3

    altura_card = 92

    y_cards = (
        y_secao
        - 22
        - altura_card
    )


    # ======================================================
    # CARD MATRÍCULAS
    # ======================================================

    mat_real = float(
        matriculas.get("realizado", 0)
        or 0
    )

    mat_meta = float(
        matriculas.get("meta", 0)
        or 0
    )

    mat_pct = matriculas.get(
        "percentual"
    )

    if mat_pct is None:

        texto_mat = (
            "Sem meta definida"
            if mat_real > 0
            else "Sem movimento"
        )

    else:

        texto_mat = (
            f"{_pct(mat_pct)} da meta"
        )


    _card(
        pdf,
        margem_cards,
        y_cards,
        largura_card,
        altura_card,
        "Matrículas",
        _num(mat_real),
        (
            f"Meta: {_num(mat_meta)}"
            f" • {texto_mat}"
        ),
        colors.HexColor("#2563eb")
    )


    # ======================================================
    # CARD HORA-ALUNO
    # ======================================================

    ha_real = float(
        hora_aluno.get("realizado", 0)
        or 0
    )

    ha_meta = float(
        hora_aluno.get("meta", 0)
        or 0
    )

    ha_pct = hora_aluno.get(
        "percentual"
    )

    if ha_pct is None:

        texto_ha = (
            "Sem meta definida"
            if ha_real > 0
            else "Sem movimento"
        )

    else:

        texto_ha = (
            f"{_pct(ha_pct)} da meta"
        )


    _card(
        pdf,
        margem_cards
        + largura_card
        + espacamento_cards,
        y_cards,
        largura_card,
        altura_card,
        "Hora-Aluno",
        _num(ha_real),
        (
            f"Meta: {_num(ha_meta)}"
            f" • {texto_ha}"
        ),
        colors.HexColor("#16a34a")
    )


    # ======================================================
    # CARD RECEITA
    # ======================================================

    rec_real = float(
        receita.get("realizado", 0)
        or 0
    )

    rec_meta = float(
        receita.get("meta", 0)
        or 0
    )

    rec_pct = receita.get(
        "percentual"
    )

    if rec_pct is None:

        texto_rec = (
            "Sem meta definida"
            if rec_real > 0
            else "Sem movimento"
        )

    else:

        texto_rec = (
            f"{_pct(rec_pct)} da meta"
        )


    _card(
        pdf,
        margem_cards
        + (
            largura_card
            + espacamento_cards
        ) * 2,
        y_cards,
        largura_card,
        altura_card,
        "Receita",
        _moeda(rec_real),
        (
            f"Meta: {_moeda(rec_meta)}"
            f" • {texto_rec}"
        ),
        colors.HexColor("#f59e0b")
    )


    # ======================================================
    # TABELA — RESUMO DOS INDICADORES
    # ======================================================

    y_tabela = y_cards - 52

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_tabela,
        "RESUMO DOS INDICADORES"
    )

    y_tabela -= 24


    x0 = 40

    largura_tabela = (
        largura - 80
    )

    colunas_base = [
        110,  # Indicador
        105,  # Realizado
        105,  # Meta
        75,   # % Meta
        105,  # Gap
    ]

    fator_colunas = (
        largura_tabela
        / sum(colunas_base)
    )

    colunas = [
        valor * fator_colunas
        for valor in colunas_base
    ]

    cabecalhos = [
        "INDICADOR",
        "REALIZADO",
        "META",
        "% META",
        "GAP",
    ]

    altura_linha = 30


    # ======================================================
    # CABEÇALHO DA TABELA
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#f1f5f9")
    )

    pdf.rect(
        x0,
        y_tabela - altura_linha,
        sum(colunas),
        altura_linha,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#475569")
    )

    pdf.setFont(
        "Helvetica-Bold",
        6.5
    )

    x_atual = x0

    for titulo_coluna, largura_col in zip(
        cabecalhos,
        colunas
    ):

        pdf.drawString(
            x_atual + 8,
            y_tabela - 19,
            titulo_coluna
        )

        x_atual += largura_col


    y_tabela -= altura_linha


    # ======================================================
    # PREPARA AS LINHAS
    # ======================================================

    def calcular_gap(
        realizado,
        meta
    ):
        realizado = float(
            realizado or 0
        )

        meta = float(
            meta or 0
        )

        if meta <= 0:
            return None

        return (
            meta - realizado
        )


    linhas = [
        {
            "indicador": "Matrículas",
            "realizado": mat_real,
            "meta": mat_meta,
            "pct": mat_pct,
            "gap": calcular_gap(
                mat_real,
                mat_meta
            ),
            "tipo": "numero",
        },

        {
            "indicador": "Hora-Aluno",
            "realizado": ha_real,
            "meta": ha_meta,
            "pct": ha_pct,
            "gap": calcular_gap(
                ha_real,
                ha_meta
            ),
            "tipo": "numero",
        },

        {
            "indicador": "Receita",
            "realizado": rec_real,
            "meta": rec_meta,
            "pct": rec_pct,
            "gap": calcular_gap(
                rec_real,
                rec_meta
            ),
            "tipo": "moeda",
        },
    ]


    # ======================================================
    # DESENHA AS LINHAS
    # ======================================================

    for indice, linha in enumerate(
        linhas
    ):

        if indice % 2 == 0:

            pdf.setFillColor(
                colors.HexColor("#ffffff")
            )

        else:

            pdf.setFillColor(
                colors.HexColor("#f8fafc")
            )

        pdf.rect(
            x0,
            y_tabela - altura_linha,
            sum(colunas),
            altura_linha,
            fill=True,
            stroke=False
        )

        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )

        pdf.line(
            x0,
            y_tabela - altura_linha,
            x0 + sum(colunas),
            y_tabela - altura_linha
        )


        realizado = linha["realizado"]
        meta = linha["meta"]
        pct = linha["pct"]
        gap = linha["gap"]
        tipo = linha["tipo"]


        if tipo == "moeda":

            texto_realizado = _moeda(
                realizado
            )

            texto_meta = _moeda(
                meta
            )

            texto_gap = (
                _moeda(abs(gap))
                if gap is not None
                else "-"
            )

        else:

            texto_realizado = _num(
                realizado
            )

            texto_meta = _num(
                meta
            )

            texto_gap = (
                _num(abs(gap))
                if gap is not None
                else "-"
            )


        if pct is None:

            texto_pct = (
                "*"
                if realizado > 0
                else "-"
            )

        else:

            texto_pct = _pct(
                pct
            )


        valores = [
            linha["indicador"],
            texto_realizado,
            texto_meta,
            texto_pct,
            texto_gap,
        ]


        x_atual = x0

        for i, (
            valor,
            largura_col
        ) in enumerate(
            zip(
                valores,
                colunas
            )
        ):

            if i == 0:

                pdf.setFillColor(
                    colors.HexColor("#071b52")
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7.5
                )

            elif i == 3:

                pdf.setFillColor(
                    _cor_status_pct(
                        pct or 0,
                        meta=meta,
                        realizado=realizado
                    )
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7
                )

            else:

                pdf.setFillColor(
                    colors.HexColor("#334155")
                )

                pdf.setFont(
                    "Helvetica",
                    7
                )


            pdf.drawString(
                x_atual + 8,
                y_tabela - 19,
                str(valor)
            )

            x_atual += largura_col


        y_tabela -= altura_linha


    # ======================================================
    # LEGENDA
    # ======================================================

    y_legenda = (
        y_tabela - 24
    )

    _legenda_status(
        pdf,
        40,
        y_legenda
    )


    # ======================================================
    # RODAPÉ — PÁGINA 1
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 1"
    )

    # ======================================================
    # PÁGINA 2 — MATRÍCULAS EM DETALHE
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "MATRÍCULAS — ANÁLISE DETALHADA"
    )


    # ======================================================
    # ANO / PERÍODO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # CONTEXTO DOS FILTROS
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    linhas_contexto_pag2 = simpleSplit(
        contexto.upper(),
        "Helvetica-Bold",
        8.5,
        largura - 80
    )

    y_contexto_pag2 = altura - 165

    for linha in linhas_contexto_pag2:

        pdf.drawString(
            40,
            y_contexto_pag2,
            linha
        )

        y_contexto_pag2 -= 11


    # ======================================================
    # RESUMO — MATRÍCULAS
    # ======================================================

    y_resumo_mat = y_contexto_pag2 - 28

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_resumo_mat,
        "RESUMO DO INDICADOR"
    )


    # ======================================================
    # CARDS
    # ======================================================

    margem_cards_mat = 40
    espacamento_cards_mat = 10

    largura_card_mat = (
        largura
        - (margem_cards_mat * 2)
        - (espacamento_cards_mat * 2)
    ) / 3

    altura_card_mat = 78

    y_cards_mat = (
        y_resumo_mat
        - 20
        - altura_card_mat
    )


    # CARD — REALIZADO

    _card(
        pdf,
        margem_cards_mat,
        y_cards_mat,
        largura_card_mat,
        altura_card_mat,
        "Realizado",
        _num(mat_real),
        "Matrículas no período",
        colors.HexColor("#2563eb"),
        espacamento_destaque=True
    )


    # CARD — META

    _card(
        pdf,
        margem_cards_mat
        + largura_card_mat
        + espacamento_cards_mat,
        y_cards_mat,
        largura_card_mat,
        altura_card_mat,
        "Meta",
        _num(mat_meta),
        "Meta do período",
        colors.HexColor("#64748b"),
        espacamento_destaque=True
    )


    # CARD — % DA META

    if mat_pct is None:

        texto_pct_mat_card = (
            "*"
            if mat_real > 0
            else "-"
        )

    else:

        texto_pct_mat_card = _pct(
            mat_pct
        )


    cor_pct_mat = _cor_status_pct(
        mat_pct or 0,
        meta=mat_meta,
        realizado=mat_real
    )


    _card(
        pdf,
        margem_cards_mat
        + (
            largura_card_mat
            + espacamento_cards_mat
        ) * 2,
        y_cards_mat,
        largura_card_mat,
        altura_card_mat,
        "% da Meta",
        texto_pct_mat_card,
        (
            "Atingimento do período"
        ),
        cor_pct_mat,
        espacamento_destaque=True
    )


    # ======================================================
    # EVOLUÇÃO MENSAL
    # ======================================================

    evolucao = preview.get(
        "evolucao_mensal",
        {}
    )

    evolucao_mat = evolucao.get(
        "matriculas",
        {}
    )

    realizado_mensal_mat = (
        evolucao_mat.get(
            "realizado",
            []
        )
        or [None] * 12
    )

    meta_mensal_mat = (
        evolucao_mat.get(
            "meta",
            []
        )
        or [None] * 12
    )


    _grafico_colunas_comparativo(
        pdf,
        40,
        y_cards_mat - 195,
        largura - 80,
        155,
        "Evolução Mensal • Matrículas",
        realizado_mensal_mat,
        meta_mensal_mat
    )


    # ======================================================
    # RODAPÉ — PÁGINA 2
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 2"
    )


    # ======================================================
    # PÁGINA 3 — MATRÍCULAS POR MODALIDADE
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "MATRÍCULAS — COMPOSIÇÃO POR MODALIDADE"
    )


    # ======================================================
    # ANO / PERÍODO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # CONTEXTO DOS FILTROS
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    linhas_contexto_mat_mod = simpleSplit(
        contexto.upper(),
        "Helvetica-Bold",
        8.5,
        largura - 80
    )

    y_contexto_mat_mod = altura - 165

    for linha in linhas_contexto_mat_mod:

        pdf.drawString(
            40,
            y_contexto_mat_mod,
            linha
        )

        y_contexto_mat_mod -= 11


    # ======================================================
    # DADOS DAS MODALIDADES
    # ======================================================

    modalidades = (
        preview.get(
            "desempenho_modalidades",
            []
        )
        or []
    )

    modalidades_mat = []

    total_matriculas_modalidades = sum(
        float(
            item.get(
                "matriculas_real",
                0
            )
            or 0
        )
        for item in modalidades
    )


    for item in modalidades:

        realizado_mod = float(
            item.get(
                "matriculas_real",
                0
            )
            or 0
        )

        if realizado_mod <= 0:
            continue


        meta_mod = float(
            item.get(
                "matriculas_meta",
                0
            )
            or 0
        )


        pct_meta_mod = item.get(
            "matriculas_pct"
        )

        if pct_meta_mod is not None:
            pct_meta_mod = float(
                pct_meta_mod
            )


        participacao_mod = (
            realizado_mod
            / total_matriculas_modalidades
            * 100
            if total_matriculas_modalidades > 0
            else 0
        )


        modalidades_mat.append(
            {
                "modalidade": (
                    item.get("modalidade")
                    or "NÃO INFORMADA"
                ),
                "realizado": realizado_mod,
                "meta": meta_mod,
                "pct_meta": pct_meta_mod,
                "participacao": participacao_mod,
            }
        )


    modalidades_mat = sorted(
        modalidades_mat,
        key=lambda item: item["realizado"],
        reverse=True
    )


    # ======================================================
    # TÍTULO DA TABELA
    # ======================================================

    y_secao_mat_mod = (
        y_contexto_mat_mod - 30
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_secao_mat_mod,
        "COMPOSIÇÃO DAS MATRÍCULAS POR MODALIDADE"
    )


    # ======================================================
    # CONFIGURAÇÃO DA TABELA
    # ======================================================

    y_tabela_mod = (
        y_secao_mat_mod - 24
    )

    x0_mod = 40

    largura_tabela_mod = (
        largura - 80
    )

    colunas_base_mod = [
        190,
        85,
        85,
        80,
    ]

    fator_mod = (
        largura_tabela_mod
        / sum(colunas_base_mod)
    )

    colunas_mod = [
        valor * fator_mod
        for valor in colunas_base_mod
    ]

    cabecalhos_mod = [
        "MODALIDADE",
        "MATRÍCULAS",
        "PARTICIPAÇÃO",
        "% META",
    ]

    altura_linha_mod = 28


    # ======================================================
    # CABEÇALHO DA TABELA
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#f1f5f9")
    )

    pdf.rect(
        x0_mod,
        y_tabela_mod - altura_linha_mod,
        sum(colunas_mod),
        altura_linha_mod,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#475569")
    )

    pdf.setFont(
        "Helvetica-Bold",
        6.5
    )

    x_atual_mod = x0_mod

    for titulo_coluna, largura_col in zip(
        cabecalhos_mod,
        colunas_mod
    ):

        pdf.drawString(
            x_atual_mod + 7,
            y_tabela_mod - 18,
            titulo_coluna
        )

        x_atual_mod += largura_col


    y_tabela_mod -= altura_linha_mod


    # ======================================================
    # LINHAS
    # ======================================================

    for indice, item in enumerate(
        modalidades_mat
    ):

        if indice % 2 == 0:

            pdf.setFillColor(
                colors.HexColor("#ffffff")
            )

        else:

            pdf.setFillColor(
                colors.HexColor("#f8fafc")
            )


        pdf.rect(
            x0_mod,
            y_tabela_mod - altura_linha_mod,
            sum(colunas_mod),
            altura_linha_mod,
            fill=True,
            stroke=False
        )


        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )

        pdf.line(
            x0_mod,
            y_tabela_mod - altura_linha_mod,
            x0_mod + sum(colunas_mod),
            y_tabela_mod - altura_linha_mod
        )


        realizado_mod = item[
            "realizado"
        ]

        meta_mod = item[
            "meta"
        ]

        pct_meta_mod = item[
            "pct_meta"
        ]

        participacao_mod = item[
            "participacao"
        ]


        if meta_mod > 0:

            texto_pct_mod = (
                _pct(pct_meta_mod)
                if pct_meta_mod is not None
                else "-"
            )

        else:

            texto_pct_mod = (
                "*"
                if realizado_mod > 0
                else "-"
            )


        valores_mod = [
            str(
                item["modalidade"]
            ).upper(),

            _num(
                realizado_mod
            ),

            _pct(
                participacao_mod
            ),

            texto_pct_mod,
        ]


        x_atual_mod = x0_mod

        for i, (
            valor,
            largura_col
        ) in enumerate(
            zip(
                valores_mod,
                colunas_mod
            )
        ):

            if i == 0:

                pdf.setFillColor(
                    colors.HexColor("#071b52")
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7
                )


            elif i == 3:

                pdf.setFillColor(
                    _cor_status_pct(
                        pct_meta_mod or 0,
                        meta=meta_mod,
                        realizado=realizado_mod
                    )
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7
                )


            else:

                pdf.setFillColor(
                    colors.HexColor("#334155")
                )

                pdf.setFont(
                    "Helvetica",
                    7
                )


            pdf.drawString(
                x_atual_mod + 7,
                y_tabela_mod - 18,
                str(valor)
            )

            x_atual_mod += largura_col


        y_tabela_mod -= altura_linha_mod


    # ======================================================
    # LEGENDA
    # ======================================================

    y_legenda_mod = (
        y_tabela_mod - 22
    )

    _legenda_status(
        pdf,
        40,
        y_legenda_mod
    )


    # ======================================================
    # RODAPÉ — PÁGINA 3
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 3"
    )


    # ======================================================
    # PÁGINA 4 — HORA-ALUNO EM DETALHE
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "HORA-ALUNO — ANÁLISE DETALHADA"
    )


    # ======================================================
    # ANO / PERÍODO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # CONTEXTO DOS FILTROS
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    linhas_contexto_pag3 = simpleSplit(
        contexto.upper(),
        "Helvetica-Bold",
        8.5,
        largura - 80
    )

    y_contexto_pag3 = altura - 165

    for linha in linhas_contexto_pag3:

        pdf.drawString(
            40,
            y_contexto_pag3,
            linha
        )

        y_contexto_pag3 -= 11


    # ======================================================
    # RESUMO — HORA-ALUNO
    # ======================================================

    y_resumo_ha = (
        y_contexto_pag3 - 28
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_resumo_ha,
        "RESUMO DO INDICADOR"
    )


    # ======================================================
    # CARDS
    # ======================================================

    margem_cards_ha = 40
    espacamento_cards_ha = 10

    largura_card_ha = (
        largura
        - (margem_cards_ha * 2)
        - (espacamento_cards_ha * 2)
    ) / 3

    altura_card_ha = 78

    y_cards_ha = (
        y_resumo_ha
        - 20
        - altura_card_ha
    )


    # ------------------------------------------------------
    # CARD — REALIZADO
    # ------------------------------------------------------

    _card(
        pdf,
        margem_cards_ha,
        y_cards_ha,
        largura_card_ha,
        altura_card_ha,
        "Realizado",
        _num(ha_real),
        "Hora-Aluno realizada",
        colors.HexColor("#2563eb"),
        espacamento_destaque=True
    )


    # ------------------------------------------------------
    # CARD — META
    # ------------------------------------------------------

    _card(
        pdf,
        margem_cards_ha
        + largura_card_ha
        + espacamento_cards_ha,
        y_cards_ha,
        largura_card_ha,
        altura_card_ha,
        "Meta",
        _num(ha_meta),
        "Meta do período",
        colors.HexColor("#64748b"),
        espacamento_destaque=True
    )


    # ------------------------------------------------------
    # CARD — % DA META
    # ------------------------------------------------------

    if ha_pct is None:

        texto_pct_ha_card = (
            "*"
            if ha_real > 0
            else "-"
        )

    else:

        texto_pct_ha_card = _pct(
            ha_pct
        )


    cor_pct_ha = _cor_status_pct(
        ha_pct or 0,
        meta=ha_meta,
        realizado=ha_real
    )


    _card(
        pdf,
        margem_cards_ha
        + (
            largura_card_ha
            + espacamento_cards_ha
        ) * 2,
        y_cards_ha,
        largura_card_ha,
        altura_card_ha,
        "% da Meta",
        texto_pct_ha_card,
        "Atingimento do período",
        cor_pct_ha,
        espacamento_destaque=True
    )


    # ======================================================
    # EVOLUÇÃO MENSAL
    # ======================================================

    evolucao_ha = evolucao.get(
        "hora_aluno",
        {}
    )

    realizado_mensal_ha = (
        evolucao_ha.get(
            "realizado",
            []
        )
        or [None] * 12
    )

    meta_mensal_ha = (
        evolucao_ha.get(
            "meta",
            []
        )
        or [None] * 12
    )


    _grafico_colunas_comparativo(
        pdf,
        40,
        y_cards_ha - 195,
        largura - 80,
        155,
        "Evolução Mensal • Hora-Aluno",
        realizado_mensal_ha,
        meta_mensal_ha
    )


    # ======================================================
    # RODAPÉ — PÁGINA 4
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 4"
    )


    # ======================================================
    # PÁGINA 5 — HORA-ALUNO POR MODALIDADE
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "HORA-ALUNO — COMPOSIÇÃO POR MODALIDADE"
    )


    # ======================================================
    # ANO / PERÍODO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # CONTEXTO DOS FILTROS
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    linhas_contexto_ha_mod = simpleSplit(
        contexto.upper(),
        "Helvetica-Bold",
        8.5,
        largura - 80
    )

    y_contexto_ha_mod = altura - 165

    for linha in linhas_contexto_ha_mod:

        pdf.drawString(
            40,
            y_contexto_ha_mod,
            linha
        )

        y_contexto_ha_mod -= 11


    # ======================================================
    # COMPOSIÇÃO DA HORA-ALUNO POR MODALIDADE
    # ======================================================

    y_composicao_ha = (
        y_contexto_ha_mod - 30
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_composicao_ha,
        "COMPOSIÇÃO DA HORA-ALUNO POR MODALIDADE"
    )


    # ======================================================
    # PREPARA MODALIDADES
    # ======================================================

    modalidades_ha = []

    total_ha_modalidades = sum(
        float(
            item.get(
                "hora_aluno_real",
                0
            )
            or 0
        )
        for item in modalidades
    )


    for item in modalidades:

        realizado_mod_ha = float(
            item.get(
                "hora_aluno_real",
                0
            )
            or 0
        )

        if realizado_mod_ha <= 0:
            continue


        meta_mod_ha = float(
            item.get(
                "hora_aluno_meta",
                0
            )
            or 0
        )


        pct_meta_mod_ha = item.get(
            "hora_aluno_pct"
        )

        if pct_meta_mod_ha is not None:

            pct_meta_mod_ha = float(
                pct_meta_mod_ha
            )


        participacao_ha = (
            (
                realizado_mod_ha
                / total_ha_modalidades
            ) * 100
            if total_ha_modalidades > 0
            else 0
        )


        modalidades_ha.append({

            "modalidade": (
                item.get("modalidade")
                or "NÃO INFORMADA"
            ),

            "realizado": realizado_mod_ha,

            "meta": meta_mod_ha,

            "pct_meta": pct_meta_mod_ha,

            "participacao": participacao_ha,
        })


    modalidades_ha = sorted(
        modalidades_ha,
        key=lambda item: item["realizado"],
        reverse=True
    )



    modalidades_ha_exibidas = modalidades_ha


    # ======================================================
    # TABELA — MODALIDADES
    # ======================================================

    y_tabela_ha = (
        y_composicao_ha - 22
    )

    x0_ha = 40

    largura_tabela_ha = (
        largura - 80
    )

    colunas_base_ha = [
        190,  # Modalidade
        85,   # Hora-Aluno
        85,   # Participação
        80,   # % Meta
    ]

    fator_ha = (
        largura_tabela_ha
        / sum(colunas_base_ha)
    )

    colunas_ha = [
        valor * fator_ha
        for valor in colunas_base_ha
    ]

    cabecalhos_ha = [
        "MODALIDADE",
        "HORA-ALUNO",
        "PARTICIPAÇÃO",
        "% META",
    ]

    altura_linha_ha = 25


    # ------------------------------------------------------
    # CABEÇALHO DA TABELA
    # ------------------------------------------------------

    pdf.setFillColor(
        colors.HexColor("#f1f5f9")
    )

    pdf.rect(
        x0_ha,
        y_tabela_ha - altura_linha_ha,
        sum(colunas_ha),
        altura_linha_ha,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#475569")
    )

    pdf.setFont(
        "Helvetica-Bold",
        6.5
    )

    x_atual_ha = x0_ha

    for titulo_coluna, largura_col in zip(
        cabecalhos_ha,
        colunas_ha
    ):

        pdf.drawString(
            x_atual_ha + 7,
            y_tabela_ha - 16,
            titulo_coluna
        )

        x_atual_ha += largura_col


    y_tabela_ha -= altura_linha_ha


    # ------------------------------------------------------
    # LINHAS DA TABELA
    # ------------------------------------------------------

    for indice, item in enumerate(
        modalidades_ha_exibidas
    ):

        if indice % 2 == 0:

            pdf.setFillColor(
                colors.HexColor("#ffffff")
            )

        else:

            pdf.setFillColor(
                colors.HexColor("#f8fafc")
            )


        pdf.rect(
            x0_ha,
            y_tabela_ha - altura_linha_ha,
            sum(colunas_ha),
            altura_linha_ha,
            fill=True,
            stroke=False
        )


        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )

        pdf.line(
            x0_ha,
            y_tabela_ha - altura_linha_ha,
            x0_ha + sum(colunas_ha),
            y_tabela_ha - altura_linha_ha
        )


        nome_modalidade_ha = str(
            item["modalidade"]
        ).upper()

        realizado_mod_ha = (
            item["realizado"]
        )

        participacao_mod_ha = (
            item["participacao"]
        )

        pct_meta_mod_ha = (
            item["pct_meta"]
        )

        meta_mod_ha = (
            item["meta"]
        )


        if meta_mod_ha > 0:

            texto_pct_mod_ha = (
                _pct(pct_meta_mod_ha)
                if pct_meta_mod_ha is not None
                else "-"
            )

        else:

            texto_pct_mod_ha = (
                "*"
                if realizado_mod_ha > 0
                else "-"
            )


        valores_ha = [
            nome_modalidade_ha,
            _num(realizado_mod_ha),
            _pct(participacao_mod_ha),
            texto_pct_mod_ha,
        ]


        x_atual_ha = x0_ha

        for i, (
            valor,
            largura_col
        ) in enumerate(
            zip(
                valores_ha,
                colunas_ha
            )
        ):

            if i == 0:

                pdf.setFillColor(
                    colors.HexColor("#071b52")
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7
                )


            elif i == 3:

                pdf.setFillColor(
                    _cor_status_pct(
                        pct_meta_mod_ha or 0,
                        meta=meta_mod_ha,
                        realizado=realizado_mod_ha
                    )
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7
                )


            else:

                pdf.setFillColor(
                    colors.HexColor("#334155")
                )

                pdf.setFont(
                    "Helvetica",
                    7
                )


            pdf.drawString(
                x_atual_ha + 7,
                y_tabela_ha - 16,
                str(valor)
            )

            x_atual_ha += largura_col


        y_tabela_ha -= altura_linha_ha


    # ======================================================
    # LEGENDA — STATUS DOS INDICADORES
    # ======================================================

    y_legenda_ha = (
        y_tabela_ha - 18
    )

    _legenda_status(
        pdf,
        40,
        y_legenda_ha
    )


    # ======================================================
    # RODAPÉ — PÁGINA 5
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 5"
    )


    # ======================================================
    # PÁGINA 6 — RECEITA EM DETALHE
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "RECEITA — ANÁLISE DETALHADA"
    )


    # ======================================================
    # ANO / PERÍODO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # CONTEXTO DOS FILTROS
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    linhas_contexto_pag6 = simpleSplit(
        contexto.upper(),
        "Helvetica-Bold",
        8.5,
        largura - 80
    )

    y_contexto_pag6 = altura - 165

    for linha in linhas_contexto_pag6:

        pdf.drawString(
            40,
            y_contexto_pag6,
            linha
        )

        y_contexto_pag6 -= 11


    # ======================================================
    # RESUMO — RECEITA
    # ======================================================

    y_resumo_rec = (
        y_contexto_pag6 - 28
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_resumo_rec,
        "RESUMO DO INDICADOR"
    )


    # ======================================================
    # CARDS
    # ======================================================

    margem_cards_rec = 40
    espacamento_cards_rec = 10

    largura_card_rec = (
        largura
        - (margem_cards_rec * 2)
        - (espacamento_cards_rec * 2)
    ) / 3

    altura_card_rec = 78

    y_cards_rec = (
        y_resumo_rec
        - 20
        - altura_card_rec
    )


    # ------------------------------------------------------
    # CARD — REALIZADO
    # ------------------------------------------------------

    _card(
        pdf,
        margem_cards_rec,
        y_cards_rec,
        largura_card_rec,
        altura_card_rec,
        "Realizado",
        _moeda(rec_real),
        "Receita realizada",
        colors.HexColor("#2563eb"),
        espacamento_destaque=True
    )


    # ------------------------------------------------------
    # CARD — META
    # ------------------------------------------------------

    _card(
        pdf,
        margem_cards_rec
        + largura_card_rec
        + espacamento_cards_rec,
        y_cards_rec,
        largura_card_rec,
        altura_card_rec,
        "Meta",
        _moeda(rec_meta),
        "Meta do período",
        colors.HexColor("#64748b"),
        espacamento_destaque=True
    )


    # ------------------------------------------------------
    # CARD — % DA META
    # ------------------------------------------------------

    if rec_pct is None:

        texto_pct_rec_card = (
            "*"
            if rec_real > 0
            else "-"
        )

    else:

        texto_pct_rec_card = _pct(
            rec_pct
        )


    cor_pct_rec = _cor_status_pct(
        rec_pct or 0,
        meta=rec_meta,
        realizado=rec_real
    )


    _card(
        pdf,
        margem_cards_rec
        + (
            largura_card_rec
            + espacamento_cards_rec
        ) * 2,
        y_cards_rec,
        largura_card_rec,
        altura_card_rec,
        "% da Meta",
        texto_pct_rec_card,
        "Atingimento do período",
        cor_pct_rec,
        espacamento_destaque=True
    )


    # ======================================================
    # EVOLUÇÃO MENSAL
    # ======================================================

    evolucao_rec = evolucao.get(
        "receita",
        {}
    )

    realizado_mensal_rec = (
        evolucao_rec.get(
            "realizado",
            []
        )
        or [None] * 12
    )

    meta_mensal_rec = (
        evolucao_rec.get(
            "meta",
            []
        )
        or [None] * 12
    )


    _grafico_colunas_comparativo(
        pdf,
        40,
        y_cards_rec - 195,
        largura - 80,
        155,
        "Evolução Mensal • Receita",
        realizado_mensal_rec,
        meta_mensal_rec,
        eh_moeda=True
    )


    # ======================================================
    # RODAPÉ — PÁGINA 6
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 6"
    )



    # ======================================================
    # PÁGINA 7 — RECEITA POR MODALIDADE
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "RECEITA — COMPOSIÇÃO POR MODALIDADE"
    )


    # ======================================================
    # ANO / PERÍODO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # CONTEXTO DOS FILTROS
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    linhas_contexto_rec_mod = simpleSplit(
        contexto.upper(),
        "Helvetica-Bold",
        8.5,
        largura - 80
    )

    y_contexto_rec_mod = altura - 165

    for linha in linhas_contexto_rec_mod:

        pdf.drawString(
            40,
            y_contexto_rec_mod,
            linha
        )

        y_contexto_rec_mod -= 11


    # ======================================================
    # DADOS DAS MODALIDADES
    # ======================================================

    modalidades_rec = []

    total_receita_modalidades = sum(
        float(
            item.get(
                "receita_real",
                0
            )
            or 0
        )
        for item in modalidades
    )


    for item in modalidades:

        realizado_mod_rec = float(
            item.get(
                "receita_real",
                0
            )
            or 0
        )

        if realizado_mod_rec <= 0:
            continue


        meta_mod_rec = float(
            item.get(
                "receita_meta",
                0
            )
            or 0
        )


        pct_meta_mod_rec = item.get(
            "receita_pct"
        )

        if pct_meta_mod_rec is not None:

            pct_meta_mod_rec = float(
                pct_meta_mod_rec
            )


        participacao_rec = (
            (
                realizado_mod_rec
                / total_receita_modalidades
            ) * 100
            if total_receita_modalidades > 0
            else 0
        )


        modalidades_rec.append({

            "modalidade": (
                item.get("modalidade")
                or "NÃO INFORMADA"
            ),

            "realizado": realizado_mod_rec,

            "meta": meta_mod_rec,

            "pct_meta": pct_meta_mod_rec,

            "participacao": participacao_rec,
        })


    modalidades_rec = sorted(
        modalidades_rec,
        key=lambda item: item["realizado"],
        reverse=True
    )


    # ======================================================
    # TÍTULO DA TABELA
    # ======================================================

    y_secao_rec_mod = (
        y_contexto_rec_mod - 30
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_secao_rec_mod,
        "COMPOSIÇÃO DA RECEITA POR MODALIDADE"
    )


    # ======================================================
    # CONFIGURAÇÃO DA TABELA
    # ======================================================

    y_tabela_rec = (
        y_secao_rec_mod - 24
    )

    x0_rec = 40

    largura_tabela_rec = (
        largura - 80
    )

    colunas_base_rec = [
        180,  # Modalidade
        105,  # Receita
        75,   # Participação
        80,   # % Meta
    ]

    fator_rec = (
        largura_tabela_rec
        / sum(colunas_base_rec)
    )

    colunas_rec = [
        valor * fator_rec
        for valor in colunas_base_rec
    ]

    cabecalhos_rec = [
        "MODALIDADE",
        "RECEITA",
        "PARTICIPAÇÃO",
        "% META",
    ]

    altura_linha_rec = 28


    # ======================================================
    # CABEÇALHO DA TABELA
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#f1f5f9")
    )

    pdf.rect(
        x0_rec,
        y_tabela_rec - altura_linha_rec,
        sum(colunas_rec),
        altura_linha_rec,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#475569")
    )

    pdf.setFont(
        "Helvetica-Bold",
        6.5
    )

    x_atual_rec = x0_rec

    for titulo_coluna, largura_col in zip(
        cabecalhos_rec,
        colunas_rec
    ):

        pdf.drawString(
            x_atual_rec + 7,
            y_tabela_rec - 18,
            titulo_coluna
        )

        x_atual_rec += largura_col


    y_tabela_rec -= altura_linha_rec


    # ======================================================
    # LINHAS
    # ======================================================

    for indice, item in enumerate(
        modalidades_rec
    ):

        if indice % 2 == 0:

            pdf.setFillColor(
                colors.HexColor("#ffffff")
            )

        else:

            pdf.setFillColor(
                colors.HexColor("#f8fafc")
            )


        pdf.rect(
            x0_rec,
            y_tabela_rec - altura_linha_rec,
            sum(colunas_rec),
            altura_linha_rec,
            fill=True,
            stroke=False
        )


        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )

        pdf.line(
            x0_rec,
            y_tabela_rec - altura_linha_rec,
            x0_rec + sum(colunas_rec),
            y_tabela_rec - altura_linha_rec
        )


        realizado_mod_rec = item[
            "realizado"
        ]

        meta_mod_rec = item[
            "meta"
        ]

        pct_meta_mod_rec = item[
            "pct_meta"
        ]

        participacao_mod_rec = item[
            "participacao"
        ]


        if meta_mod_rec > 0:

            texto_pct_rec = (
                _pct(pct_meta_mod_rec)
                if pct_meta_mod_rec is not None
                else "-"
            )

        else:

            texto_pct_rec = (
                "*"
                if realizado_mod_rec > 0
                else "-"
            )


        valores_rec = [
            str(
                item["modalidade"]
            ).upper(),

            _moeda(
                realizado_mod_rec
            ),

            _pct(
                participacao_mod_rec
            ),

            texto_pct_rec,
        ]


        x_atual_rec = x0_rec

        for i, (
            valor,
            largura_col
        ) in enumerate(
            zip(
                valores_rec,
                colunas_rec
            )
        ):

            if i == 0:

                pdf.setFillColor(
                    colors.HexColor("#071b52")
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7
                )


            elif i == 3:

                pdf.setFillColor(
                    _cor_status_pct(
                        pct_meta_mod_rec or 0,
                        meta=meta_mod_rec,
                        realizado=realizado_mod_rec
                    )
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7
                )


            else:

                pdf.setFillColor(
                    colors.HexColor("#334155")
                )

                pdf.setFont(
                    "Helvetica",
                    7
                )


            pdf.drawString(
                x_atual_rec + 7,
                y_tabela_rec - 18,
                str(valor)
            )

            x_atual_rec += largura_col


        y_tabela_rec -= altura_linha_rec


    # ======================================================
    # LEGENDA
    # ======================================================

    y_legenda_rec = (
        y_tabela_rec - 22
    )

    _legenda_status(
        pdf,
        40,
        y_legenda_rec
    )


    # ======================================================
    # RODAPÉ — PÁGINA 7
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 7"
    )


    # ======================================================
    # PÁGINA 8 — SÍNTESE EXECUTIVA
    # ======================================================

    pdf.showPage()
    pdf.setPageSize(pagina)

    largura, altura = pagina


    # ======================================================
    # CABEÇALHO AZUL
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#003B8F")
    )

    pdf.rect(
        0,
        altura - 82,
        largura,
        82,
        fill=True,
        stroke=False
    )

    _desenhar_logo_cabecalho(
        pdf,
        largura,
        altura,
        paisagem=orientacao == "paisagem"
    )


    # ======================================================
    # TÍTULO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        17
    )

    pdf.drawString(
        40,
        altura - 125,
        "SÍNTESE EXECUTIVA DOS INDICADORES"
    )


    # ======================================================
    # ANO / PERÍODO
    # ======================================================

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        40,
        altura - 145,
        f"Ano: {ano} • Período: {periodo}"
    )


    # ======================================================
    # CONTEXTO DOS FILTROS
    # ======================================================

    pdf.setFont(
        "Helvetica-Bold",
        8.5
    )

    linhas_contexto_pag8 = simpleSplit(
        contexto.upper(),
        "Helvetica-Bold",
        8.5,
        largura - 80
    )

    y_contexto_pag8 = altura - 165

    for linha in linhas_contexto_pag8:

        pdf.drawString(
            40,
            y_contexto_pag8,
            linha
        )

        y_contexto_pag8 -= 11


    # ======================================================
    # DESEMPENHO CONSOLIDADO
    # ======================================================

    y_secao_sintese = (
        y_contexto_pag8 - 28
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_secao_sintese,
        "DESEMPENHO CONSOLIDADO"
    )


    # ======================================================
    # CARDS
    # ======================================================

    margem_cards_sintese = 40
    espacamento_cards_sintese = 10

    largura_card_sintese = (
        largura
        - (margem_cards_sintese * 2)
        - (espacamento_cards_sintese * 2)
    ) / 3

    altura_card_sintese = 92

    y_cards_sintese = (
        y_secao_sintese
        - 20
        - altura_card_sintese
    )


    # MATRÍCULAS

    texto_mat_sintese = (
        _pct(mat_pct)
        if mat_pct is not None
        else (
            "*"
            if mat_real > 0
            else "-"
        )
    )

    _card(
        pdf,
        margem_cards_sintese,
        y_cards_sintese,
        largura_card_sintese,
        altura_card_sintese,
        "Matrículas",
        _num(mat_real),
        (
            f"Meta: {_num(mat_meta)}"
            f" • {texto_mat_sintese} da meta"
        ),
        _cor_status_pct(
            mat_pct or 0,
            meta=mat_meta,
            realizado=mat_real
        )
    )


    # HORA-ALUNO

    texto_ha_sintese = (
        _pct(ha_pct)
        if ha_pct is not None
        else (
            "*"
            if ha_real > 0
            else "-"
        )
    )

    _card(
        pdf,
        margem_cards_sintese
        + largura_card_sintese
        + espacamento_cards_sintese,
        y_cards_sintese,
        largura_card_sintese,
        altura_card_sintese,
        "Hora-Aluno",
        _num(ha_real),
        (
            f"Meta: {_num(ha_meta)}"
            f" • {texto_ha_sintese} da meta"
        ),
        _cor_status_pct(
            ha_pct or 0,
            meta=ha_meta,
            realizado=ha_real
        )
    )


    # RECEITA

    texto_rec_sintese = (
        _pct(rec_pct)
        if rec_pct is not None
        else (
            "*"
            if rec_real > 0
            else "-"
        )
    )

    _card(
        pdf,
        margem_cards_sintese
        + (
            largura_card_sintese
            + espacamento_cards_sintese
        ) * 2,
        y_cards_sintese,
        largura_card_sintese,
        altura_card_sintese,
        "Receita",
        _moeda(rec_real),
        (
            f"Meta: {_moeda(rec_meta)}"
            f" • {texto_rec_sintese} da meta"
        ),
        _cor_status_pct(
            rec_pct or 0,
            meta=rec_meta,
            realizado=rec_real
        )
    )


    # ======================================================
    # SITUAÇÃO DOS INDICADORES
    # ======================================================

    y_situacao = (
        y_cards_sintese - 48
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_situacao,
        "SITUAÇÃO DOS INDICADORES"
    )

    y_situacao -= 24


    # ======================================================
    # TABELA
    # ======================================================

    x0_sit = 40

    largura_tabela_sit = (
        largura - 80
    )

    colunas_base_sit = [
        100,
        110,
        110,
        70,
        110,
    ]

    fator_sit = (
        largura_tabela_sit
        / sum(colunas_base_sit)
    )

    colunas_sit = [
        valor * fator_sit
        for valor in colunas_base_sit
    ]

    cabecalhos_sit = [
        "INDICADOR",
        "REALIZADO",
        "META",
        "% META",
        "SITUAÇÃO",
    ]

    altura_linha_sit = 28


    # Cabeçalho

    pdf.setFillColor(
        colors.HexColor("#f1f5f9")
    )

    pdf.rect(
        x0_sit,
        y_situacao - altura_linha_sit,
        sum(colunas_sit),
        altura_linha_sit,
        fill=True,
        stroke=False
    )

    pdf.setFillColor(
        colors.HexColor("#475569")
    )

    pdf.setFont(
        "Helvetica-Bold",
        6.5
    )

    x_atual_sit = x0_sit

    for titulo_coluna, largura_col in zip(
        cabecalhos_sit,
        colunas_sit
    ):

        pdf.drawString(
            x_atual_sit + 7,
            y_situacao - 18,
            titulo_coluna
        )

        x_atual_sit += largura_col


    y_situacao -= altura_linha_sit


    linhas_situacao = [
        {
            "indicador": "Matrículas",
            "realizado": mat_real,
            "meta": mat_meta,
            "pct": mat_pct,
            "tipo": "numero",
        },
        {
            "indicador": "Hora-Aluno",
            "realizado": ha_real,
            "meta": ha_meta,
            "pct": ha_pct,
            "tipo": "numero",
        },
        {
            "indicador": "Receita",
            "realizado": rec_real,
            "meta": rec_meta,
            "pct": rec_pct,
            "tipo": "moeda",
        },
    ]


    for indice, item in enumerate(
        linhas_situacao
    ):

        if indice % 2 == 0:

            pdf.setFillColor(
                colors.HexColor("#ffffff")
            )

        else:

            pdf.setFillColor(
                colors.HexColor("#f8fafc")
            )


        pdf.rect(
            x0_sit,
            y_situacao - altura_linha_sit,
            sum(colunas_sit),
            altura_linha_sit,
            fill=True,
            stroke=False
        )

        pdf.setStrokeColor(
            colors.HexColor("#e5e7eb")
        )

        pdf.line(
            x0_sit,
            y_situacao - altura_linha_sit,
            x0_sit + sum(colunas_sit),
            y_situacao - altura_linha_sit
        )


        realizado_item = item["realizado"]
        meta_item = item["meta"]
        pct_item = item["pct"]


        if item["tipo"] == "moeda":

            texto_realizado = _moeda(
                realizado_item
            )

            texto_meta = _moeda(
                meta_item
            )

        else:

            texto_realizado = _num(
                realizado_item
            )

            texto_meta = _num(
                meta_item
            )


        if pct_item is None:

            texto_pct_item = (
                "*"
                if realizado_item > 0
                else "-"
            )

        else:

            texto_pct_item = _pct(
                pct_item
            )


        status_item = _status_pct(
            pct_item or 0,
            meta=meta_item,
            realizado=realizado_item
        )


        valores_sit = [
            item["indicador"],
            texto_realizado,
            texto_meta,
            texto_pct_item,
            status_item,
        ]


        x_atual_sit = x0_sit

        for i, (
            valor,
            largura_col
        ) in enumerate(
            zip(
                valores_sit,
                colunas_sit
            )
        ):

            if i == 0:

                pdf.setFillColor(
                    colors.HexColor("#071b52")
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7
                )


            elif i in (3, 4):

                pdf.setFillColor(
                    _cor_status_pct(
                        pct_item or 0,
                        meta=meta_item,
                        realizado=realizado_item
                    )
                )

                pdf.setFont(
                    "Helvetica-Bold",
                    7
                )


            else:

                pdf.setFillColor(
                    colors.HexColor("#334155")
                )

                pdf.setFont(
                    "Helvetica",
                    7
                )


            pdf.drawString(
                x_atual_sit + 7,
                y_situacao - 18,
                str(valor)
            )

            x_atual_sit += largura_col


        y_situacao -= altura_linha_sit


    # ======================================================
    # DESTAQUES DO PERÍODO
    # ======================================================

    y_destaques_sintese = (
        y_situacao - 42
    )

    pdf.setFillColor(
        colors.HexColor("#071b52")
    )

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        40,
        y_destaques_sintese,
        "DESTAQUES DO PERÍODO"
    )


    # ======================================================
    # IDENTIFICA MELHOR DESEMPENHO
    # ======================================================

    indicadores_validos = []

    if mat_pct is not None:
        indicadores_validos.append(
            (
                "MATRÍCULAS",
                mat_pct
            )
        )

    if ha_pct is not None:
        indicadores_validos.append(
            (
                "HORA-ALUNO",
                ha_pct
            )
        )

    if rec_pct is not None:
        indicadores_validos.append(
            (
                "RECEITA",
                rec_pct
            )
        )


    if indicadores_validos:

        melhor_indicador, melhor_pct = max(
            indicadores_validos,
            key=lambda item: item[1]
        )

    else:

        melhor_indicador = "-"
        melhor_pct = 0


    # ======================================================
    # IDENTIFICA MAIOR DISTÂNCIA PERCENTUAL DA META
    # ======================================================

    distancias_meta = []

    if mat_pct is not None and mat_pct < 100:

        distancias_meta.append(
            (
                "MATRÍCULAS",
                100 - mat_pct
            )
        )


    if ha_pct is not None and ha_pct < 100:

        distancias_meta.append(
            (
                "HORA-ALUNO",
                100 - ha_pct
            )
        )


    if rec_pct is not None and rec_pct < 100:

        distancias_meta.append(
            (
                "RECEITA",
                100 - rec_pct
            )
        )


    if distancias_meta:

        indicador_maior_distancia, maior_distancia = max(
            distancias_meta,
            key=lambda item: item[1]
        )

        texto_maior_distancia = (
            f"{_pct(maior_distancia)} para atingir a meta"
        )

    else:

        indicador_maior_distancia = (
            "TODOS OS INDICADORES"
        )

        texto_maior_distancia = (
            "Metas atingidas"
        )


    # ======================================================
    # CARDS DOS DESTAQUES
    # ======================================================

    largura_destaque = (
        largura - 90
    ) / 2

    altura_destaque = 84

    y_cards_destaque = (
        y_destaques_sintese
        - 20
        - altura_destaque
    )


    _card(
        pdf,
        40,
        y_cards_destaque,
        largura_destaque,
        altura_destaque,
        "Melhor desempenho",
        melhor_indicador,
        (
            f"{_pct(melhor_pct)} da meta"
        ),
        colors.HexColor("#16a34a"),
        espacamento_destaque=True
    )


    _card(
        pdf,
        50 + largura_destaque,
        y_cards_destaque,
        largura_destaque,
        altura_destaque,
        "Maior distância da meta",
        indicador_maior_distancia,
        texto_maior_distancia,
        colors.HexColor("#f59e0b"),
        espacamento_destaque=True
    )


    # ======================================================
    # LEGENDA
    # ======================================================

    y_legenda_sintese = (
        y_cards_destaque - 28
    )

    _legenda_status(
        pdf,
        40,
        y_legenda_sintese
    )


    # ======================================================
    # RODAPÉ — PÁGINA 8
    # ======================================================

    pdf.setStrokeColor(
        colors.HexColor("#e5e7eb")
    )

    pdf.line(
        40,
        42,
        largura - 40,
        42
    )

    pdf.setFillColor(
        colors.HexColor("#64748b")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawString(
        40,
        28,
        "Painel Executivo SENAI • Relatório gerado automaticamente"
    )

    pdf.drawRightString(
        largura - 40,
        28,
        "Página 8"
    )


    # ======================================================
    # FINALIZA
    # ======================================================

    pdf.save()

    buffer.seek(0)

    return buffer