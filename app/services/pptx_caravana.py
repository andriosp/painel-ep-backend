from __future__ import annotations

import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.presentation import Presentation as PresentationType

from pptx.enum.shapes import MSO_SHAPE_TYPE

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

from app.services.pptx_components import (
    AZUL_HEADER,
    AZUL_TEXTO,
    BRANCO,
    bloco_destaques_regiao_executivo,
    bloco_destaques_subregiao,
    bloco_distribuicao_matriculas_executivo,
    bloco_distribuicao_hora_aluno_executivo,
    bloco_receita_executivo,
    bloco_resumo_executivo_panorama,
    cabecalho_caravana,
    caixa_resumo_panorama,
    cards_panorama,
    cards_superiores_panorama_executivo,
    painel_esquerdo_panorama,
    tabela_metas_programas_subregiao,
    pol,
    retangulo,
    rodape_panorama,
    rodape_panorama_executivo,
    rodape_subregiao_executivo,
    texto,
    bloco_desempenho_consolidado,
    bloco_fontes_dados_status,
    bloco_financiamentos_status,
    cabecalho_status_subregiao,
    cards_status_subregiao,
    rodape_status_subregiao,
    tabela_programas_status,
    slide_trilhas_profissionais,
    slide_indicador_fidelizacao,
    slide_proximos_passos,
)

APP_DIR = Path(__file__).resolve().parents[1]

TEMPLATE_PPTX = (
    APP_DIR
    / "templates"
    / "pptx"
    / "caravana_template.pptx"
)


def _remover_slide(
    apresentacao: PresentationType,
    indice: int,
) -> None:
    """
    Remove um slide da apresentação pelo índice.

    Utiliza a estrutura interna do python-pptx porque a biblioteca
    ainda não possui um método público para exclusão de slides.
    """
    slide_id = apresentacao.slides._sldIdLst[indice]
    relacionamento_id = slide_id.rId

    apresentacao.part.drop_rel(relacionamento_id)
    apresentacao.slides._sldIdLst.remove(slide_id)


def _manter_capa_panorama_e_encerramento(
    apresentacao: PresentationType,
) -> None:
    """
    Mantém somente:

    - slide 1: capa;
    - slide 2: panorama regional;
    - último slide: encerramento.
    """
    total_slides = len(apresentacao.slides)

    if total_slides < 3:
        raise ValueError(
            "O template da Caravana precisa possuir pelo menos "
            "três slides."
        )

    # Preserva os índices originais:
    # 0 = capa
    # 1 = panorama regional
    # último = encerramento
    #
    # Remove todos os slides entre o segundo e o último,
    # sempre de trás para frente.
    for indice in range(total_slides - 2, 1, -1):
        _remover_slide(apresentacao, indice)

def _alterar_regiao_capa(
    apresentacao: PresentationType,
    nome_regiao: str,
) -> None:
    """
    Substitui somente o conteúdo textual da região na capa,
    preservando integralmente fonte, tamanho, cor, posição
    e alinhamento existentes no template.
    """
    nome_regiao = str(nome_regiao or "").strip().upper()

    if not nome_regiao:
        return

    slide_capa = apresentacao.slides[0]

    for shape in slide_capa.shapes:
        if not shape.has_text_frame:
            continue

        texto_atual = shape.text.strip().upper()

        if texto_atual != "METROPOLITANA":
            continue

        for paragrafo in shape.text_frame.paragraphs:
            if not paragrafo.runs:
                continue

            # Altera somente o texto do primeiro trecho existente.
            # Toda a formatação original permanece preservada.
            paragrafo.runs[0].text = nome_regiao

            # Limpa eventuais runs adicionais sem recriar a caixa.
            for run_extra in paragrafo.runs[1:]:
                run_extra.text = ""

            return

    raise ValueError(
        "Não foi encontrada na capa a caixa de texto "
        "com o nome METROPOLITANA."
    )

def listar_objetos_slide(apresentacao):
    slide = apresentacao.slides[1]

    print("=" * 80)

    for i, shape in enumerate(slide.shapes):

        print(f"\nShape {i}")

        print("Tipo:", shape.shape_type)

        if hasattr(shape, "text"):
            texto = shape.text.strip()

            if texto:
                print("Texto:")
                print(texto)

        print("Left :", shape.left)
        print("Top  :", shape.top)
        print("Width:", shape.width)
        print("Height:", shape.height)

def _limpar_slide(slide) -> None:
    """
    Remove todos os objetos existentes do slide.
    """
    for shape in list(slide.shapes):
        elemento = shape._element
        elemento.getparent().remove(elemento)

def _criar_base_slide_panorama(
    apresentacao: PresentationType,
    nome_regiao: str,
    ano: int,
    dados_panorama: dict,
) -> None:
    slide = apresentacao.slides[1]

    _limpar_slide(slide)

    nome_regiao = str(nome_regiao or "").strip().upper()
    nome_formatado = nome_regiao.title()

    cabecalho_caravana(
        slide=slide,
        largura_slide=apresentacao.slide_width,
        nome_regiao=nome_regiao,
        ano=ano,
    )

    texto(
        slide,
        (
            f"A força da Região {nome_formatado} "
            f"impulsionando o SENAI-RS em {ano}"
        ),
        pol(1.95),
        pol(0.91),
        pol(10.20),
        pol(0.34),
        22,
        AZUL_TEXTO,
        negrito=True,
        alinhamento=PP_ALIGN.CENTER,
    )

    painel_esquerdo_panorama(
        slide=slide,
        nome_regiao=nome_regiao,
    )

    cards_panorama(
        slide=slide,
        ano=ano,
        dados=dados_panorama,
    )

    caixa_resumo_panorama(
        slide=slide,
        nome_regiao=nome_regiao,
        percentual_matriculas=(
            dados_panorama["matriculas"]["percentual"]
        ),
        percentual_receita=(
            dados_panorama["receita"]["percentual"]
        ),
        percentual_hora_aluno=(
            dados_panorama["hora_aluno"]["percentual"]
        ),
        percentual_gr=(
            dados_panorama["hora_aluno_gr"]["percentual"]
        ),
    )

    rodape_panorama(
        slide=slide,
        nome_regiao=nome_regiao,
        fracao_matriculas=(
            f'1 em cada {dados_panorama["rodape"]["matriculas"]}'
        ),
        fracao_hora_aluno=(
            f'1 em cada {dados_panorama["rodape"]["hora_aluno"]}'
        ),
        fracao_gr=(
            f'1 em cada {dados_panorama["rodape"]["hora_aluno_gr"]}'
        ),
    )

def _mover_slide_para_posicao(
    apresentacao: PresentationType,
    indice_origem: int,
    indice_destino: int,
) -> None:
    """
    Move um slide para outra posição usando a lista interna
    de slides do python-pptx.
    """
    slides = apresentacao.slides._sldIdLst

    slide_id = slides[indice_origem]
    slides.remove(slide_id)
    slides.insert(indice_destino, slide_id)


def _criar_slide_panorama_executivo(
    apresentacao: PresentationType,
    nome_regiao: str,
    ano: int,
    dados_panorama: dict,
) -> None:
    """
    Cria o novo slide após o slide 2.

    Neste primeiro passo, criamos apenas o slide vazio
    e reaproveitamos o cabeçalho.
    """
    layout_em_branco = apresentacao.slide_layouts[6]

    slide = apresentacao.slides.add_slide(layout_em_branco)

    # Move o novo slide para a posição 2:
    # 0 = capa
    # 1 = panorama regional
    # 2 = novo panorama executivo
    # 3 = encerramento
    indice_slide_novo = len(apresentacao.slides) - 1
    _mover_slide_para_posicao(
        apresentacao=apresentacao,
        indice_origem=indice_slide_novo,
        indice_destino=2,
    )

    slide = apresentacao.slides[2]

    nome_regiao = str(nome_regiao or "").strip().upper()

    cabecalho_caravana(
        slide=slide,
        largura_slide=apresentacao.slide_width,
        nome_regiao=nome_regiao,
        ano=ano,
    )

    cards_superiores_panorama_executivo(
        slide=slide,
        ano=ano,
        dados=dados_panorama,
    )

    distribuicao_matriculas = dados_panorama.get(
        "distribuicao_matriculas",
        {},
    )

    bloco_distribuicao_matriculas_executivo(
        slide=slide,
        total_matriculas=(
            distribuicao_matriculas.get(
                "total_formatado",
                dados_panorama["matriculas"]["regiao"],
            )
        ),
        distribuicao=distribuicao_matriculas,
    )

    distribuicao_hora_aluno = dados_panorama.get(
        "distribuicao_hora_aluno",
        {},
    )

    bloco_distribuicao_hora_aluno_executivo(
        slide=slide,

        total_hora_aluno=(
            distribuicao_hora_aluno.get(
                "total_formatado",
                dados_panorama["hora_aluno"]["regiao"],
            )
        ),

        distribuicao=distribuicao_hora_aluno,
    )

    bloco_receita_executivo(
        slide=slide,
        total_receita=dados_panorama["receita"]["regiao"],
        ano=ano,
    )

    distribuicao_matriculas = dados_panorama.get(
        "distribuicao_matriculas",
        {},
    )

    distribuicao_hora_aluno = dados_panorama.get(
        "distribuicao_hora_aluno",
        {},
    )

    dados_gr_matriculas = distribuicao_matriculas.get(
        "gr",
        {},
    )

    dados_gr_hora_aluno = distribuicao_hora_aluno.get(
        "gr",
        {},
    )

    programas_destaque = dados_panorama.get(
        "top_programas",
        [],
    )

    programa_principal = (
        programas_destaque[0]
        if programas_destaque
        else "programas da região"
    )

    bloco_destaques_regiao_executivo(
        slide=slide,

        total_programas=str(
            dados_panorama.get(
                "total_programas",
                "—",
            )
        ),

        total_matriculas=str(
            dados_panorama["matriculas"]["regiao"]
        ),

        total_hora_aluno=str(
            dados_panorama["hora_aluno"]["regiao"]
        ),

        matriculas_gr=str(
            dados_gr_matriculas.get(
                "valor_formatado",
                "0",
            )
        ),

        percentual_hora_aluno_gr=str(
            dados_gr_hora_aluno.get(
                "percentual_formatado",
                "0,00%",
            )
        ),

        receita=str(
            dados_panorama["receita"]["regiao"]
        ),

        programa_destaque=programa_principal,
        ano=ano,
    )

    bloco_resumo_executivo_panorama(
        slide=slide,
        nome_regiao=nome_regiao,
        ano=ano,
        programas_destaque=dados_panorama.get(
            "top_programas",
            [],
        ),
    )

    rodape_panorama_executivo(
        slide=slide,
        nome_regiao=nome_regiao,
        ano=ano,
        programas_destaque=dados_panorama.get(
            "top_programas",
            [],
        ),
    )

def slide_subregiao_executivo(
    apresentacao: PresentationType,
    *,
    ano: int,
    nome_subregiao: str,
    dados: dict,
) -> None:
    """
    Cria um slide executivo para uma sub-região.

    Nesta etapa, desenha:
    - cabeçalho;
    - quatro cards superiores.
    """

    nome_subregiao = str(
        nome_subregiao or ""
    ).strip().upper()

    layout_em_branco = apresentacao.slide_layouts[6]

    slide = apresentacao.slides.add_slide(
        layout_em_branco
    )

    # O slide acabou de ser criado depois do encerramento.
    # Move para imediatamente antes do slide de encerramento.
    indice_slide_novo = len(
        apresentacao.slides
    ) - 1

    indice_antes_encerramento = len(
        apresentacao.slides
    ) - 2

    _mover_slide_para_posicao(
        apresentacao=apresentacao,
        indice_origem=indice_slide_novo,
        indice_destino=indice_antes_encerramento,
    )

    # Recupera o slide depois da movimentação.
    slide = apresentacao.slides[
        indice_antes_encerramento
    ]

    # ======================================================
    # CABEÇALHO-BASE
    # ======================================================

    # Reaproveita o fundo, as faixas decorativas e o logo.
    cabecalho_caravana(
        slide=slide,
        largura_slide=apresentacao.slide_width,
        nome_regiao=nome_subregiao,
        ano=ano,
    )

    # Cobre somente os textos criados pelo cabeçalho padrão.
    # Não alcança as faixas centrais nem o logo.
    retangulo(
        slide=slide,
        esquerda=0,
        topo=0,
        largura=pol(5.85),
        altura=pol(0.72),
        cor=AZUL_HEADER,
        raio=False,
    )

    # ======================================================
    # TÍTULO
    # ======================================================

    texto(
        slide=slide,
        texto=(
            f"METAS {ano} | "
            f"SUB-REGIÃO {nome_subregiao}"
        ),
        esquerda=pol(0.31),
        topo=pol(0.075),
        largura=pol(6.65),
        altura=pol(0.34),
        tamanho=30,
        cor=BRANCO,
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # SUBTÍTULO
    # ======================================================

    texto(
        slide=slide,
        texto=f"PANORAMA EXECUTIVO | METAS {ano}",
        esquerda=pol(0.31),
        topo=pol(0.42),
        largura=pol(5.60),
        altura=pol(0.23),
        tamanho=19,
        cor=RGBColor(67, 204, 255),
        negrito=True,
        alinhamento=PP_ALIGN.LEFT,
        vertical=MSO_ANCHOR.MIDDLE,
    )

    # ======================================================
    # PROGRAMAS QUE EFETIVAMENTE APARECERÃO NA TABELA
    # ======================================================

    programas_tabela = [
        programa
        for programa in dados.get(
            "programas_detalhados",
            [],
        )
        if str(
            programa.get(
                "programa",
                "",
            )
        ).strip()
    ]

    # Ordem alfabética crescente.
    programas_tabela = sorted(
        programas_tabela,
        key=lambda item: str(
            item.get(
                "programa",
                "",
            )
        ).strip().casefold(),
    )

    # Cria uma cópia para não alterar o dicionário original.
    dados_cards = dict(dados)

    # O card PROGRAMAS terá exatamente a quantidade
    # de linhas de programas apresentadas na tabela.
    dados_cards["total_programas"] = len(
        programas_tabela
    )

    cards_superiores_panorama_executivo(
        slide=slide,
        ano=ano,
        dados=dados_cards,
    )

    distribuicao_matriculas = dados.get(
        "distribuicao_matriculas",
        {},
    )

    bloco_distribuicao_matriculas_executivo(
        slide=slide,
        total_matriculas=(
            distribuicao_matriculas.get(
                "total_formatado",
                dados["matriculas"]["regiao"],
            )
        ),
        distribuicao=distribuicao_matriculas,
    )

    distribuicao_hora_aluno = dados.get(
        "distribuicao_hora_aluno",
        {},
    )

    bloco_distribuicao_hora_aluno_executivo(
        slide=slide,
        total_hora_aluno=(
            distribuicao_hora_aluno.get(
                "total_formatado",
                dados["hora_aluno"]["regiao"],
            )
        ),
        distribuicao=distribuicao_hora_aluno,
    )

    tabela_metas_programas_subregiao(
        slide=slide,
        ano=ano,
        programas=programas_tabela,
    )

    bloco_destaques_subregiao(
        slide=slide,
        nome_subregiao=nome_subregiao,
        ano=ano,
        programas=programas_tabela,

        # Usa exatamente o valor apresentado
        # no card superior Receita.
        receita_total=str(
            dados["receita"]["regiao"]
        ),
    )

    rodape_subregiao_executivo(
        slide=slide,
        nome_subregiao=nome_subregiao,
        ano=ano,
        programas=programas_tabela,
        data_atualizacao=str(
            dados.get(
                "data_atualizacao",
                "",
            )
        ),
    )

def slide_status_metas_subregiao(
    apresentacao: PresentationType,
    *,
    ano: int,
    nome_subregiao: str,
    dados: dict,
) -> None:
    """
    Cria o slide Status das Metas para uma sub-região.

    O slide é inserido imediatamente antes do encerramento,
    depois do Panorama Executivo da respectiva sub-região.
    """

    nome_subregiao = str(
        nome_subregiao or ""
    ).strip().upper()

    layout_em_branco = apresentacao.slide_layouts[6]

    slide = apresentacao.slides.add_slide(
        layout_em_branco
    )

    indice_slide_novo = (
        len(apresentacao.slides) - 1
    )

    indice_antes_encerramento = (
        len(apresentacao.slides) - 2
    )

    _mover_slide_para_posicao(
        apresentacao=apresentacao,
        indice_origem=indice_slide_novo,
        indice_destino=indice_antes_encerramento,
    )

    slide = apresentacao.slides[
        indice_antes_encerramento
    ]

    # Fundo branco.
    retangulo(
        slide=slide,
        esquerda=0,
        topo=0,
        largura=apresentacao.slide_width,
        altura=apresentacao.slide_height,
        cor=BRANCO,
        raio=False,
    )

    # ======================================================
    # CABEÇALHO
    # ======================================================

    cabecalho_status_subregiao(
        slide=slide,
        largura_slide=apresentacao.slide_width,
        nome_subregiao=nome_subregiao,
        ano=ano,
        periodo=dados.get(
            "periodo_titulo",
            "1º SEMESTRE",
        ),
        meses=dados.get(
            "periodo_meses",
            "JAN–JUN",
        ),
    )

    # ======================================================
    # TRÊS CARDS DE INDICADORES
    # ======================================================

    cards_status_subregiao(
        slide=slide,
        indicadores=dados.get(
            "indicadores",
            {},
        ),
    )

    # ======================================================
    # DESEMPENHO CONSOLIDADO
    # ======================================================

    bloco_desempenho_consolidado(
        slide=slide,
        indicadores=dados.get(
            "indicadores",
            {},
        ),
    )

    # ======================================================
    # DESEMPENHO POR FINANCIAMENTO
    # ======================================================

    bloco_financiamentos_status(
        slide=slide,
        distribuicoes=dados.get(
            "financiamentos",
            {},
        ),
    )

    # ======================================================
    # PROGRAMAS PRINCIPAIS
    # ======================================================

    tabela_programas_status(
        slide=slide,
        ano=ano,
        programas=dados.get(
            "programas",
            [],
        ),
        periodo_meses=dados.get(
            "periodo_meses",
            "JAN–JUN",
        ),
    )

    # ======================================================
    # FONTES DOS DADOS
    # ======================================================

    bloco_fontes_dados_status(
        slide=slide,
        data_atualizacao=str(
            dados.get(
                "data_atualizacao",
                "",
            )
        ),
    )

    # ======================================================
    # RODAPÉ
    # ======================================================

    rodape_status_subregiao(
        slide=slide,
        nome_subregiao=nome_subregiao,
        ano=ano,
        indicadores=dados.get(
            "indicadores",
            {},
        ),
        periodo_titulo=dados.get(
            "periodo_titulo",
            "",
        ),
        periodo_meses=dados.get(
            "periodo_meses",
            "",
        ),
    )

def gerar_pptx_caravana_base(
    nome_regiao: str = "METROPOLITANA",
    ano: int = 2026,
    dados_panorama: dict | None = None,
    dados_subregioes: list | None = None,
) -> Path:
    """
    Gera uma cópia da apresentação contendo somente:

    - primeiro slide: capa;
    - último slide: encerramento.

    Retorna o caminho do arquivo temporário gerado.
    """

    if dados_subregioes is None:
        dados_subregioes = []

    if not TEMPLATE_PPTX.exists():
        raise FileNotFoundError(
            "Template da Caravana não encontrado em: "
            f"{TEMPLATE_PPTX}"
        )
    
    if dados_panorama is None:
        raise ValueError(
            "Os dados do panorama regional não foram informados."
        )

    apresentacao = Presentation(str(TEMPLATE_PPTX))

    _manter_capa_panorama_e_encerramento(apresentacao)

    _alterar_regiao_capa(
        apresentacao=apresentacao,
        nome_regiao=nome_regiao,
    )

    _criar_base_slide_panorama(
        apresentacao=apresentacao,
        nome_regiao=nome_regiao,
        ano=ano,
        dados_panorama=dados_panorama,
    )

    _criar_slide_panorama_executivo(
        apresentacao=apresentacao,
        nome_regiao=nome_regiao,
        ano=ano,
        dados_panorama=dados_panorama,
    )

    # ======================================================
    # SLIDES DAS SUB-REGIÕES
    # ======================================================

    for item_subregiao in dados_subregioes:
        nome_subregiao = str(
            item_subregiao.get(
                "nome",
                "",
            )
        ).strip()

        dados_subregiao = item_subregiao.get(
            "dados",
            {},
        )

        if not nome_subregiao:
            continue

        if not dados_subregiao:
            continue

        # Panorama executivo da sub-região.
        slide_subregiao_executivo(
            apresentacao=apresentacao,
            ano=ano,
            nome_subregiao=nome_subregiao,
            dados=dados_subregiao,
        )

        # Status das metas da sub-região.
        dados_status = (
            item_subregiao.get("status")
            or {}
        )

        slide_status_metas_subregiao(
            apresentacao=apresentacao,
            ano=ano,
            nome_subregiao=nome_subregiao,
            dados=dados_status,
        )

    # ======================================================
    # SLIDE TRILHAS PROFISSIONAIS
    # ======================================================

    slide_trilhas_profissionais(
        apresentacao
    )

    # O slide foi criado depois do encerramento.
    # Move imediatamente para antes dele.
    _mover_slide_para_posicao(
        apresentacao=apresentacao,
        indice_origem=len(apresentacao.slides) - 1,
        indice_destino=len(apresentacao.slides) - 2,
    )

    # ======================================================
    # SLIDE INDICADOR DE FIDELIZAÇÃO
    # ======================================================

    slide_indicador_fidelizacao(
        apresentacao
    )

    # Entra depois de Trilhas e antes do encerramento.
    _mover_slide_para_posicao(
        apresentacao=apresentacao,
        indice_origem=len(apresentacao.slides) - 1,
        indice_destino=len(apresentacao.slides) - 2,
    )

    # ======================================================
    # SLIDE PRÓXIMOS PASSOS
    # ======================================================

    slide_proximos_passos(
        apresentacao
    )

    # Entra depois do Indicador e antes do encerramento.
    _mover_slide_para_posicao(
        apresentacao=apresentacao,
        indice_origem=len(apresentacao.slides) - 1,
        indice_destino=len(apresentacao.slides) - 2,
    )

    # ======================================================
    # SALVAMENTO
    # ======================================================

    arquivo_temporario = tempfile.NamedTemporaryFile(
        prefix="caravana_",
        suffix=".pptx",
        delete=False,
    )

    caminho_saida = Path(
        arquivo_temporario.name
    )

    arquivo_temporario.close()

    apresentacao.save(
        str(caminho_saida)
    )

    return caminho_saida

def inspecionar_slide_panorama():
    prs = Presentation(str(TEMPLATE_PPTX))

    slide = prs.slides[1]

    print("\n" + "=" * 100)

    for i, shape in enumerate(slide.shapes):

        print(f"\nSHAPE {i}")
        print("-" * 60)

        print("Tipo:", shape.shape_type)

        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            print("GRUPO")
            print("Quantidade:", len(shape.shapes))

        if shape.has_text_frame:
            print("TEXTO:")
            print(repr(shape.text))

        print(
            "Posição:",
            shape.left,
            shape.top,
            shape.width,
            shape.height,
        )