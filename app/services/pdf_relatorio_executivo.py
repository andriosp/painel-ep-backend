from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas


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

def _card(pdf, x, y, w, h, titulo, valor, detalhe, cor_barra):
    pdf.setFillColor(colors.HexColor("#f8fafc"))
    pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
    pdf.roundRect(x, y, w, h, 12, fill=True, stroke=True)

    pdf.setFillColor(cor_barra)
    pdf.roundRect(x, y + h - 5, w, 5, 3, fill=True, stroke=False)

    # Título
    pdf.setFillColor(colors.HexColor("#071b52"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(x + 14, y + h - 28, titulo.upper())

    # Valor
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(x + 14, y + h - 52, str(valor))

    # Detalhes
    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 7)

    if " • " in detalhe:
        partes = detalhe.split(" • ")

        pdf.drawString(x + 14, y + 24, partes[0])
        pdf.drawString(x + 14, y + 12, partes[1])
    else:
        pdf.drawString(x + 14, y + 24, detalhe)

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
    pdf.setFont("Helvetica-Bold", 22)
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

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawRightString(largura - 40, altura - 48, "SENAI")

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
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(40, altura - 42, "EVOLUÇÃO MENSAL DOS INDICADORES")

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

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawRightString(largura - 40, altura - 48, "SENAI")

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
        pdf.setFont("Helvetica-Bold", 20)
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

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawRightString(largura - 40, altura - 42, "SENAI")

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
        pdf.setFont("Helvetica-Bold", 20)
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

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawRightString(largura - 40, altura - 42, "SENAI")

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
        pdf.setFont("Helvetica-Bold", 20)
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

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawRightString(largura - 40, altura - 42, "SENAI")

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
    pdf.setFont("Helvetica-Bold", 20)
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

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawRightString(largura - 40, altura - 42, "SENAI")

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
        pdf.setFont("Helvetica-Bold", 20)
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

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawRightString(largura - 40, altura - 42, "SENAI")

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
                pdf.setFont("Helvetica-Bold", 20)
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

                pdf.setFont("Helvetica-Bold", 13)
                pdf.drawRightString(largura - 40, altura - 42, "SENAI")

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
        pdf.setFont("Helvetica-Bold", 20)
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

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawRightString(largura - 40, altura - 42, "SENAI")

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