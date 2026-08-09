from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

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
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(x + 14, y + h - 50, str(valor))

    # Detalhes
    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 7.5)

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

    regiao = cabecalho.get("regiao") or "Não informada"
    if preview.get("regiao") and not preview.get("subregiao"):
        subregiao = "Todas as Sub-regiões"
    else:
        subregiao = (
            cabecalho.get("subregiao")
            or preview.get("subregiao")
            or "Não informada"
        )
    geope = cabecalho.get("geope") or "Não informado"
    uos = cabecalho.get("uos") or []

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

    if uos:
        for nome_uo in uos:

            texto = f"• {nome_uo}"

            largura_texto = pdf.stringWidth(
                texto,
                "Helvetica",
                9
            )

            # Só quebra se realmente ultrapassar a largura disponível
            if largura_texto <= largura_coluna_direita:

                pdf.drawString(
                    x_direita,
                    y_direita,
                    texto
                )

                y_direita -= 14

            else:

                linhas = simpleSplit(
                    texto,
                    "Helvetica",
                    9,
                    largura_coluna_direita
                )

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
        "VISÃO GERAL"
    )

    y -= 18

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
        largura - 80
    )

    for linha in linhas_visao_geral:
        pdf.drawString(
            40,
            y,
            linha
        )
        y -= 12

    y -= 18

    # ======================================================
    # CARDS DE INDICADORES
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
        largura
        - (margem_cards * 2)
        - (espacamento_cards * 3)
    ) / 4

    y_cards = y - altura_card

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

    numero_pagina = 2

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