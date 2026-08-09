import tempfile
import unicodedata
import httpx
from pathlib import Path
from datetime import datetime

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn

BASE_DIR = Path(__file__).resolve().parent.parent

LOGO_CAPA = BASE_DIR / "assets" / "logo2.png"
LOGO_SLIDE = BASE_DIR / "assets" / "logo.png"

ICON_PATH = Path("app/static/icons")
SLIDE_FINAL = BASE_DIR / "assets" / "slide_obrigado.png"

# ===== ESTILO INSTITUCIONAL =====
AZUL_TITULO = RGBColor(0, 91, 170)
AZUL_TABELA = RGBColor(0, 59, 143)
CINZA_SUBTITULO = RGBColor(100, 116, 139)
CINZA_RODAPE = RGBColor(100, 100, 100)
TEXTO_ESCURO = RGBColor(30, 41, 59)
LINHA_ZEBRA = RGBColor(245, 247, 250)
BRANCO = RGBColor(255, 255, 255)

PROGRAMAS_EXCLUIR = [
    "ASSESSORIA EM EDUCAÇÃO",
    "CERTIFICAÇÃO PROFISSIONAL",
    "DROPS EAD - PARCERIA EJA SESI",
]

def normalizar_programa_sql(alias="p"):
    return f"""
        CASE
            WHEN UPPER({alias}.nome_programa) IN (
                'RS QUALIFICAÇÃO',
                'RS QUALIFICAÇÃO RECOMEÇAR'
            )
            THEN 'RS QUALIFICAÇÃO'
            ELSE {alias}.nome_programa
        END
    """

FONTE_TITULO = "Arial Black"
FONTE_TEXTO = "Arial"

async def gerar_pptx_carteira_programas(request, filtros: dict):
    ano = filtros.get("ano") or 2026

    dados = await buscar_dados_carteira_programas(
        request,
        ano
    )

    detalhes = await buscar_detalhes_programas(
        request,
        ano
    )

    interlocutores = await buscar_programas_por_interlocutor(
        request,
        ano
    )

    resumo_porta_entrada = await buscar_resumo_porta_entrada(
        request,
        ano
    )

    dados_subregioes = await buscar_distribuicao_subregioes(
        request=request,
        ano=int(ano)
    )

    dados_modalidades = await buscar_distribuicao_modalidades(
        request=request,
        ano=int(ano)
    )

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # Limpa slides existentes do template
    while len(prs.slides) > 0:
        r_id = prs.slides._sldIdLst[0].rId
        prs.part.drop_rel(r_id)
        del prs.slides._sldIdLst[0]

    criar_slide_capa(
        prs,
        ano
    )

    criar_slide_porta_entrada(
        prs,
        resumo_porta_entrada,
        ano
    )

    criar_slide_distribuicao_subregioes(
        prs,
        dados_subregioes,
        ano
    )

    criar_slide_distribuicao_modalidades(
        prs,
        dados_modalidades,
        ano
    )

    criar_slide_tabela(
        prs,
        dados,
        ano
    )

    criar_slide_interlocutores(
        prs,
        interlocutores
    )

    for programa in detalhes:
        criar_slide_programa(
            prs,
            programa,
            ano
        )

    criar_slide_final(prs)

    saida = (
        Path(tempfile.gettempdir())
        / f"carteira_de_programas_{datetime.now().strftime('%Y%m%d%H%M%S')}.pptx"
    )

    for idx, slide in enumerate(prs.slides, start=1):
        if idx != 1 and idx != len(prs.slides):
            adicionar_numero_slide(
                slide,
                idx
            )

    prs.save(saida)

    return str(saida)


async def buscar_dados_carteira_programas(request, ano: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
        SELECT
            CASE
                WHEN UPPER(p.nome_programa) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                THEN 'RS QUALIFICAÇÃO'
                ELSE p.nome_programa
            END AS nome_programa,

            string_agg(
                DISTINCT f.nome_financiamento,
                ' | '
                ORDER BY f.nome_financiamento
            ) AS tipo_financiamento,

            string_agg(
                DISTINCT m.nome,
                ', '
                ORDER BY m.nome
            ) AS modalidades,

            string_agg(
                DISTINCT COALESCE(i.nome, ''),
                ', '
                ORDER BY COALESCE(i.nome, '')
            ) AS interlocutor

        FROM ofertas_programas o

        LEFT JOIN programas p
            ON p.codigo = o.cod_programa

        LEFT JOIN financiamento f
            ON f.codigo = o.cod_financiamento

        LEFT JOIN modalidade m
            ON m.codigo = o.cod_modalidade

        LEFT JOIN interlocutores i
            ON i.codigo = p.cod_interlocutor

        WHERE o.ano = $1::int
            AND p.nome_programa IS NOT NULL
            AND TRIM(p.nome_programa) <> ''
            AND UPPER(p.nome_programa) NOT IN (
                'ASSESSORIA EM EDUCAÇÃO',
                'CERTIFICAÇÃO PROFISSIONAL',
                'DROPS EAD - PARCERIA EJA SESI'
            )

        GROUP BY
            CASE
                WHEN UPPER(p.nome_programa) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                THEN 'RS QUALIFICAÇÃO'
                ELSE p.nome_programa
            END

        ORDER BY
            nome_programa;
        """, int(ano))

    return [dict(r) for r in rows]

async def buscar_detalhes_programas(request, ano: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            WITH base AS (
                SELECT
                    CASE
                        WHEN UPPER(p.nome_programa) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                        THEN 'RS QUALIFICAÇÃO'
                        ELSE p.nome_programa
                    END AS nome_programa,

                    MIN(p.codigo) AS cod_programa,
                    MAX(COALESCE(p.descricao, '')) AS objetivo,
                    string_agg(DISTINCT COALESCE(i.nome, ''), ', ' ORDER BY COALESCE(i.nome, '')) AS interlocutor,

                    COUNT(DISTINCT r.codigo) AS regioes_atendidas,
                    COUNT(DISTINCT o.cod_uo) AS unidades_atendidas,
                    COUNT(DISTINCT o.cod_modalidade) AS modalidades_qtd,

                    string_agg(DISTINCT r.nome, ', ' ORDER BY r.nome) AS regioes,
                    string_agg(DISTINCT m.nome, ', ' ORDER BY m.nome) AS modalidades,
                    string_agg(DISTINCT f.nome_financiamento, ', ' ORDER BY f.nome_financiamento) AS tipo_financiamento

                FROM ofertas_programas o

                LEFT JOIN programas p
                    ON p.codigo = o.cod_programa

                LEFT JOIN modalidade m
                    ON m.codigo = o.cod_modalidade
                
                LEFT JOIN financiamento f
                    ON f.codigo = o.cod_financiamento

                LEFT JOIN uo u
                    ON u.codigo::text = o.cod_uo::text

                LEFT JOIN subregioes s
                    ON s.codigo = u.cod_subregiao

                LEFT JOIN regioes r
                    ON r.codigo = s.codigo_regiao

                LEFT JOIN interlocutores i
                    ON i.codigo = p.cod_interlocutor

                WHERE o.ano = $1::int
                    AND p.nome_programa IS NOT NULL
                    AND TRIM(p.nome_programa) <> ''
                    AND UPPER(p.nome_programa) NOT IN (
                        'ASSESSORIA EM EDUCAÇÃO',
                        'CERTIFICAÇÃO PROFISSIONAL',
                        'DROPS EAD - PARCERIA EJA SESI'
                    )

                GROUP BY
                    CASE
                        WHEN UPPER(p.nome_programa) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                        THEN 'RS QUALIFICAÇÃO'
                        ELSE p.nome_programa
                    END
            ),

            realizado AS (
                SELECT
                    CASE
                        WHEN UPPER(p.nome_programa) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                        THEN 'RS QUALIFICAÇÃO'
                        ELSE p.nome_programa
                    END AS nome_programa,

                    SUM(COALESCE(vmr.matriculas_real, 0)) AS matriculas_realizado,
                    SUM(COALESCE(vmr.ha_real, 0)) AS ha_realizado,
                    SUM(COALESCE(vmr.receita_real, 0)) AS receita_realizado

                FROM ofertas_programas o

                LEFT JOIN programas p
                    ON p.codigo = o.cod_programa

                LEFT JOIN vw_meta_realizado vmr
                    ON vmr.cod_oferta = o.codigo
                   AND vmr.ano = o.ano

                WHERE o.ano = $1::int

                GROUP BY
                    CASE
                        WHEN UPPER(p.nome_programa) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                        THEN 'RS QUALIFICAÇÃO'
                        ELSE p.nome_programa
                    END
            ),

            metas AS (
                SELECT
                    CASE
                        WHEN UPPER(p.nome_programa) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                        THEN 'RS QUALIFICAÇÃO'
                        ELSE p.nome_programa
                    END AS nome_programa,

                    SUM(
                        CASE
                            WHEN mp.mes < EXTRACT(MONTH FROM CURRENT_DATE)
                            THEN COALESCE(mp.matriculas_meta, 0)
                            ELSE 0
                        END
                    ) AS matriculas_meta_atual,

                    SUM(COALESCE(mp.matriculas_meta, 0)) AS matriculas_meta_ano,

                    SUM(
                        CASE
                            WHEN mp.mes < EXTRACT(MONTH FROM CURRENT_DATE)
                            THEN COALESCE(mp.ha_meta, 0)
                            ELSE 0
                        END
                    ) AS ha_meta_atual,

                    SUM(COALESCE(mp.ha_meta, 0)) AS ha_meta_ano,

                    SUM(
                        CASE
                            WHEN mp.mes < EXTRACT(MONTH FROM CURRENT_DATE)
                            THEN COALESCE(mp.receita_meta, 0)
                            ELSE 0
                        END
                    ) AS receita_meta_atual,

                    SUM(COALESCE(mp.receita_meta, 0)) AS receita_meta_ano

                FROM ofertas_programas o

                LEFT JOIN programas p
                    ON p.codigo = o.cod_programa

                LEFT JOIN meta_programas mp
                    ON mp.cod_oferta = o.codigo
                   AND mp.ano = o.ano

                WHERE o.ano = $1::int

                GROUP BY
                    CASE
                        WHEN UPPER(p.nome_programa) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                        THEN 'RS QUALIFICAÇÃO'
                        ELSE p.nome_programa
                    END
            )

            SELECT
                b.cod_programa,
                b.nome_programa,
                b.objetivo,
                b.interlocutor,
                b.regioes_atendidas,
                b.unidades_atendidas,
                b.modalidades_qtd,
                b.regioes,
                b.modalidades,
                b.tipo_financiamento,

                COALESCE(r.matriculas_realizado, 0) AS matriculas_realizado,
                COALESCE(m.matriculas_meta_atual, 0) AS matriculas_meta_atual,
                COALESCE(m.matriculas_meta_ano, 0) AS matriculas_meta_ano,

                COALESCE(r.ha_realizado, 0) AS ha_realizado,
                COALESCE(m.ha_meta_atual, 0) AS ha_meta_atual,
                COALESCE(m.ha_meta_ano, 0) AS ha_meta_ano,

                COALESCE(r.receita_realizado, 0) AS receita_realizado,
                COALESCE(m.receita_meta_atual, 0) AS receita_meta_atual,
                COALESCE(m.receita_meta_ano, 0) AS receita_meta_ano

            FROM base b

            LEFT JOIN realizado r
                ON r.nome_programa = b.nome_programa

            LEFT JOIN metas m
                ON m.nome_programa = b.nome_programa

            ORDER BY
                b.nome_programa;
        """, int(ano))

    return [dict(r) for r in rows]

async def buscar_programas_por_interlocutor(request, ano: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                COALESCE(i.nome, 'Sem interlocutor') AS interlocutor,

                CASE
                    WHEN UPPER(TRIM(p.nome_programa)) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                    THEN 'RS QUALIFICAÇÃO'
                    ELSE TRIM(p.nome_programa)
                END AS nome_programa,

                CASE
                    WHEN f.nome_financiamento ILIKE '%GRATUIDADE NÃO REGIMENTAL%' THEN 'gnr'
                    WHEN f.nome_financiamento ILIKE '%GRATUIDADE REGIMENTAL%' THEN 'gr'
                    ELSE 'pago'
                END AS grupo

            FROM ofertas_programas o
            LEFT JOIN programas p ON p.codigo = o.cod_programa
            LEFT JOIN financiamento f ON f.codigo = o.cod_financiamento
            LEFT JOIN interlocutores i ON i.codigo = p.cod_interlocutor

            WHERE o.ano = $1::int
              AND p.nome_programa IS NOT NULL
              AND TRIM(p.nome_programa) <> ''
              AND UPPER(TRIM(p.nome_programa)) NOT IN (
                  'ASSESSORIA EM EDUCAÇÃO',
                  'CERTIFICAÇÃO PROFISSIONAL',
                  'DROPS EAD - PARCERIA EJA SESI'
              )

            GROUP BY
                COALESCE(i.nome, 'Sem interlocutor'),

                CASE
                    WHEN UPPER(TRIM(p.nome_programa)) IN ('RS QUALIFICAÇÃO', 'RS QUALIFICAÇÃO RECOMEÇAR')
                    THEN 'RS QUALIFICAÇÃO'
                    ELSE TRIM(p.nome_programa)
                END,

                CASE
                    WHEN f.nome_financiamento ILIKE '%GRATUIDADE NÃO REGIMENTAL%' THEN 'gnr'
                    WHEN f.nome_financiamento ILIKE '%GRATUIDADE REGIMENTAL%' THEN 'gr'
                    ELSE 'pago'
                END

            ORDER BY interlocutor, grupo, nome_programa;
        """, int(ano))

    return [dict(r) for r in rows]


async def buscar_resumo_porta_entrada(request, ano: int):
    """
    Consolida os mesmos indicadores dos cards da porta de entrada (index.html):
    Matrículas, Hora-aluno e Receita, com realizado, meta e percentual.
    """
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
        WITH ultimo_lote AS (
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
        ),
        meta AS (
            SELECT
                COALESCE(SUM(CASE WHEN UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS')
                    THEN COALESCE(ps.jan,0)+COALESCE(ps.fev,0)+COALESCE(ps.mar,0)+COALESCE(ps.abr,0)+COALESCE(ps.mai,0)+COALESCE(ps.jun,0)+COALESCE(ps.jul,0)+COALESCE(ps.ago,0)+COALESCE(ps.set_,0)+COALESCE(ps.out_,0)+COALESCE(ps.nov,0)+COALESCE(ps.dez,0)
                    ELSE 0 END),0) AS matriculas_meta,

                COALESCE(SUM(CASE WHEN UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                    THEN COALESCE(ps.jan,0)+COALESCE(ps.fev,0)+COALESCE(ps.mar,0)+COALESCE(ps.abr,0)+COALESCE(ps.mai,0)+COALESCE(ps.jun,0)+COALESCE(ps.jul,0)+COALESCE(ps.ago,0)+COALESCE(ps.set_,0)+COALESCE(ps.out_,0)+COALESCE(ps.nov,0)+COALESCE(ps.dez,0)
                    ELSE 0 END),0) AS ha_meta,

                COALESCE(SUM(CASE WHEN UPPER(TRIM(ps.conta)) IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                    THEN COALESCE(ps.jan,0)+COALESCE(ps.fev,0)+COALESCE(ps.mar,0)+COALESCE(ps.abr,0)+COALESCE(ps.mai,0)+COALESCE(ps.jun,0)+COALESCE(ps.jul,0)+COALESCE(ps.ago,0)+COALESCE(ps.set_,0)+COALESCE(ps.out_,0)+COALESCE(ps.nov,0)+COALESCE(ps.dez,0)
                    ELSE 0 END),0) AS receita_meta,

                COALESCE(SUM(CASE WHEN UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS') AND UPPER(TRIM(ps.financiamento_raw)) = 'GRATUIDADE REGIMENTAL'
                    THEN COALESCE(ps.jan,0)+COALESCE(ps.fev,0)+COALESCE(ps.mar,0)+COALESCE(ps.abr,0)+COALESCE(ps.mai,0)+COALESCE(ps.jun,0)+COALESCE(ps.jul,0)+COALESCE(ps.ago,0)+COALESCE(ps.set_,0)+COALESCE(ps.out_,0)+COALESCE(ps.nov,0)+COALESCE(ps.dez,0)
                    ELSE 0 END),0) AS meta_gr,
                COALESCE(SUM(CASE WHEN UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS') AND UPPER(TRIM(ps.financiamento_raw)) IN ('GRATUIDADE NÃO REGIMENTAL','GRATUIDADE NAO REGIMENTAL','GRATUITO')
                    THEN COALESCE(ps.jan,0)+COALESCE(ps.fev,0)+COALESCE(ps.mar,0)+COALESCE(ps.abr,0)+COALESCE(ps.mai,0)+COALESCE(ps.jun,0)+COALESCE(ps.jul,0)+COALESCE(ps.ago,0)+COALESCE(ps.set_,0)+COALESCE(ps.out_,0)+COALESCE(ps.nov,0)+COALESCE(ps.dez,0)
                    ELSE 0 END),0) AS meta_g,
                COALESCE(SUM(CASE WHEN UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS') AND UPPER(TRIM(ps.financiamento_raw)) IN ('PAGO POR PESSOA FÍSICA OU EMPRESA','PAGO','NOVO BRASIL + PRODUTIVO')
                    THEN COALESCE(ps.jan,0)+COALESCE(ps.fev,0)+COALESCE(ps.mar,0)+COALESCE(ps.abr,0)+COALESCE(ps.mai,0)+COALESCE(ps.jun,0)+COALESCE(ps.jul,0)+COALESCE(ps.ago,0)+COALESCE(ps.set_,0)+COALESCE(ps.out_,0)+COALESCE(ps.nov,0)+COALESCE(ps.dez,0)
                    ELSE 0 END),0) AS meta_p,

                COALESCE(SUM(CASE WHEN UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO') AND UPPER(TRIM(ps.financiamento_raw)) = 'GRATUIDADE REGIMENTAL'
                    THEN COALESCE(ps.jan,0)+COALESCE(ps.fev,0)+COALESCE(ps.mar,0)+COALESCE(ps.abr,0)+COALESCE(ps.mai,0)+COALESCE(ps.jun,0)+COALESCE(ps.jul,0)+COALESCE(ps.ago,0)+COALESCE(ps.set_,0)+COALESCE(ps.out_,0)+COALESCE(ps.nov,0)+COALESCE(ps.dez,0)
                    ELSE 0 END),0) AS ha_meta_gr,
                COALESCE(SUM(CASE WHEN UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO') AND UPPER(TRIM(ps.financiamento_raw)) IN ('GRATUIDADE NÃO REGIMENTAL','GRATUIDADE NAO REGIMENTAL','GRATUITO')
                    THEN COALESCE(ps.jan,0)+COALESCE(ps.fev,0)+COALESCE(ps.mar,0)+COALESCE(ps.abr,0)+COALESCE(ps.mai,0)+COALESCE(ps.jun,0)+COALESCE(ps.jul,0)+COALESCE(ps.ago,0)+COALESCE(ps.set_,0)+COALESCE(ps.out_,0)+COALESCE(ps.nov,0)+COALESCE(ps.dez,0)
                    ELSE 0 END),0) AS ha_meta_g,
                COALESCE(SUM(CASE WHEN UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO') AND UPPER(TRIM(ps.financiamento_raw)) IN ('PAGO POR PESSOA FÍSICA OU EMPRESA','PAGO','NOVO BRASIL + PRODUTIVO')
                    THEN COALESCE(ps.jan,0)+COALESCE(ps.fev,0)+COALESCE(ps.mar,0)+COALESCE(ps.abr,0)+COALESCE(ps.mai,0)+COALESCE(ps.jun,0)+COALESCE(ps.jul,0)+COALESCE(ps.ago,0)+COALESCE(ps.set_,0)+COALESCE(ps.out_,0)+COALESCE(ps.nov,0)+COALESCE(ps.dez,0)
                    ELSE 0 END),0) AS ha_meta_p
            FROM planejamento_staging ps
            WHERE ps.lote_id = (SELECT id FROM ultimo_lote)
              AND ps.flag_valida = TRUE
              AND ps.tipo = 'META'
        ),
        ofertas_base AS (
            SELECT DISTINCT codigo, cod_financiamento
            FROM ofertas_programas
            WHERE ano = $1
        ),
        realizado AS (
            SELECT
                COALESCE(SUM(rp.matriculas_real),0) AS matriculas_real,
                COALESCE(SUM(rp.ha_real),0) AS ha_real,
                COALESCE(SUM(rp.receita_real),0) AS receita_real,
                COALESCE(SUM(CASE WHEN ob.cod_financiamento = 1 THEN rp.matriculas_real ELSE 0 END),0) AS matriculas_gr,
                COALESCE(SUM(CASE WHEN ob.cod_financiamento = 2 THEN rp.matriculas_real ELSE 0 END),0) AS matriculas_g,
                COALESCE(SUM(CASE WHEN ob.cod_financiamento IN (3,6,7,8,9) THEN rp.matriculas_real ELSE 0 END),0) AS matriculas_p,
                COALESCE(SUM(CASE WHEN ob.cod_financiamento = 1 THEN rp.ha_real ELSE 0 END),0) AS ha_gr,
                COALESCE(SUM(CASE WHEN ob.cod_financiamento = 2 THEN rp.ha_real ELSE 0 END),0) AS ha_g,
                COALESCE(SUM(CASE WHEN ob.cod_financiamento IN (3,6,7,8,9) THEN rp.ha_real ELSE 0 END),0) AS ha_p
            FROM realizado_programas rp
            JOIN ofertas_base ob
                ON ob.codigo = rp.cod_oferta
            WHERE rp.ano = $1
        )
        SELECT * FROM meta, realizado
        """, int(ano))

    d = dict(row or {})

    def f(ch):
        return float(d.get(ch) or 0)

    def pct(real, meta):
        return (real / meta * 100) if meta else 0

    mat_real, mat_meta = f("matriculas_real"), f("matriculas_meta")
    ha_real, ha_meta = f("ha_real"), f("ha_meta")
    rec_real, rec_meta = f("receita_real"), f("receita_meta")

    return {
        "matriculas": {
            "total": mat_real,
            "meta_total": mat_meta,
            "pct_meta": pct(mat_real, mat_meta),
            "gr": f("matriculas_gr"),
            "g": f("matriculas_g"),
            "p": f("matriculas_p"),
            "meta_gr": f("meta_gr"),
            "meta_g": f("meta_g"),
            "meta_p": f("meta_p"),
        },
        "hora_aluno": {
            "total": ha_real,
            "meta_total": ha_meta,
            "pct_meta": pct(ha_real, ha_meta),
            "gr": f("ha_gr"),
            "g": f("ha_g"),
            "p": f("ha_p"),
            "meta_gr": f("ha_meta_gr"),
            "meta_g": f("ha_meta_g"),
            "meta_p": f("ha_meta_p"),
        },
        "receita": {
            "total": rec_real,
            "meta_total": rec_meta,
            "pct_meta": pct(rec_real, rec_meta),
        },
    }

async def buscar_distribuicao_subregioes(request, ano: int):
    """
    Consulta internamente o endpoint utilizado pela página index.html
    e consolida os 12 meses por sub-região e indicador.
    """

    transport = httpx.ASGITransport(app=request.app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://app-interno"
    ) as client:

        response = await client.get(
            "/performance/subregioes/detalhe",
            params={"ano": int(ano)}
        )

        response.raise_for_status()
        dados_mensais = response.json()

    agrupado = {}

    for linha in dados_mensais or []:
        subregiao = str(
            linha.get("subregiao") or "Não vinculada"
        ).strip()

        indicador = str(
            linha.get("indicador") or ""
        ).strip().upper()

        indicador = (
            indicador
            .replace("_", " ")
            .replace("-", " ")
        )

        if indicador in ("MATRICULAS", "MATRÍCULAS"):
            chave_indicador = "matriculas"

        elif indicador in ("HORA ALUNO", "HORAALUNO"):
            chave_indicador = "hora_aluno"

        elif indicador in (
            "RECEITA",
            "RECEITAS",
            "RECEITAS CORRENTES"
        ):
            chave_indicador = "receita"

        else:
            continue

        if subregiao not in agrupado:
            agrupado[subregiao] = {
                "subregiao": subregiao,

                "matriculas_meta": 0.0,
                "matriculas_real": 0.0,

                "hora_aluno_meta": 0.0,
                "hora_aluno_real": 0.0,

                "receita_meta": 0.0,
                "receita_real": 0.0,
            }

        meta_total = 0.0
        real_total = 0.0

        for mes in range(1, 13):
            meta_total += float(
                linha.get(f"meta_mes_{mes}") or 0
            )

            real_total += float(
                linha.get(f"real_mes_{mes}") or 0
            )

        agrupado[subregiao][f"{chave_indicador}_meta"] += meta_total
        agrupado[subregiao][f"{chave_indicador}_real"] += real_total

    resultado = []

    for item in agrupado.values():
        item["matriculas_pct"] = calcular_percentual(
            item["matriculas_real"],
            item["matriculas_meta"]
        )

        item["hora_aluno_pct"] = calcular_percentual(
            item["hora_aluno_real"],
            item["hora_aluno_meta"]
        )

        item["receita_pct"] = calcular_percentual(
            item["receita_real"],
            item["receita_meta"]
        )

        resultado.append(item)

    resultado.sort(
        key=lambda item: (
            -item["matriculas_real"],
            item["subregiao"]
        )
    )

    return resultado

async def buscar_distribuicao_modalidades(request, ano: int):
    """
    Busca os dados da tabela de modalidades utilizada na página
    modalidades.html e padroniza os campos para o PPTX.
    """

    transport = httpx.ASGITransport(app=request.app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://app-interno",
        timeout=120
    ) as client:

        response = await client.get(
            "/modalidades/tabela/modalidades",
            params={"ano": int(ano)}
        )

        response.raise_for_status()
        resposta_json = response.json()

    # Aceita tanto uma lista direta quanto:
    # {"dados": [...]}, {"items": [...]}, {"modalidades": [...]}
    if isinstance(resposta_json, list):
        linhas_api = resposta_json
    elif isinstance(resposta_json, dict):
        linhas_api = (
            resposta_json.get("dados")
            or resposta_json.get("items")
            or resposta_json.get("modalidades")
            or resposta_json.get("resultados")
            or []
        )
    else:
        linhas_api = []

    def numero(item, *chaves):
        for chave in chaves:
            valor = item.get(chave)

            if valor is not None and valor != "":
                try:
                    return float(valor)
                except (TypeError, ValueError):
                    pass

        return 0.0

    resultado = []

    for linha in linhas_api:
        modalidade = str(
            linha.get("modalidade")
            or linha.get("nome_modalidade")
            or linha.get("descricao_modalidade")
            or linha.get("nome")
            or "Não informada"
        ).strip()

        matriculas_meta = numero(
            linha,
            "matriculas_meta",
            "meta_matriculas",
            "mat_meta"
        )

        matriculas_real = numero(
            linha,
            "matriculas_real",
            "matriculas_realizado",
            "realizado_matriculas",
            "mat_real"
        )

        hora_aluno_meta = numero(
            linha,
            "hora_aluno_meta",
            "ha_meta",
            "meta_hora_aluno"
        )

        hora_aluno_real = numero(
            linha,
            "hora_aluno_real",
            "ha_real",
            "ha_realizado",
            "realizado_hora_aluno"
        )

        receita_meta = numero(
            linha,
            "receita_meta",
            "meta_receita",
            "rec_meta"
        )

        receita_real = numero(
            linha,
            "receita_real",
            "receita_realizado",
            "realizado_receita",
            "rec_real"
        )

        resultado.append({
            "modalidade": modalidade,

            "matriculas_meta": matriculas_meta,
            "matriculas_real": matriculas_real,
            "matriculas_pct": calcular_percentual(
                matriculas_real,
                matriculas_meta
            ),

            "hora_aluno_meta": hora_aluno_meta,
            "hora_aluno_real": hora_aluno_real,
            "hora_aluno_pct": calcular_percentual(
                hora_aluno_real,
                hora_aluno_meta
            ),

            "receita_meta": receita_meta,
            "receita_real": receita_real,
            "receita_pct": calcular_percentual(
                receita_real,
                receita_meta
            ),
        })

    resultado.sort(
        key=lambda item: (
            -item["matriculas_real"],
            item["modalidade"]
        )
    )

    return resultado

def definir_borda_celula(
    cell,
    lados,
    cor="D9E1EC",
    espessura=9525
):
    """
    Aplica borda diretamente em lados específicos da célula.

    lados possíveis:
    - "top"
    - "bottom"
    - "left"
    - "right"
    """

    mapa_lados = {
        "top": "a:lnT",
        "bottom": "a:lnB",
        "left": "a:lnL",
        "right": "a:lnR",
    }

    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()

    for lado in lados:
        tag = mapa_lados[lado]

        # Remove uma borda anterior do mesmo lado
        borda_anterior = tc_pr.find(qn(tag))

        if borda_anterior is not None:
            tc_pr.remove(borda_anterior)

        linha = OxmlElement(tag)
        linha.set("w", str(espessura))
        linha.set("cap", "flat")
        linha.set("cmpd", "sng")
        linha.set("algn", "ctr")

        preenchimento = OxmlElement("a:solidFill")
        cor_xml = OxmlElement("a:srgbClr")
        cor_xml.set("val", cor)

        preenchimento.append(cor_xml)
        linha.append(preenchimento)

        tracejado = OxmlElement("a:prstDash")
        tracejado.set("val", "solid")
        linha.append(tracejado)

        tc_pr.append(linha)


def aplicar_borda_externa_tabela(
    tabela,
    total_linhas,
    total_colunas
):
    cor_borda = "D9E1EC"
    espessura = 9525  # aproximadamente 0,75 pt

    ultima_linha = total_linhas - 1
    ultima_coluna = total_colunas - 1

    # Borda superior
    for coluna in range(total_colunas):
        definir_borda_celula(
            tabela.cell(0, coluna),
            ["top"],
            cor_borda,
            espessura
        )

    # Borda inferior
    for coluna in range(total_colunas):
        definir_borda_celula(
            tabela.cell(ultima_linha, coluna),
            ["bottom"],
            cor_borda,
            espessura
        )

    # Borda esquerda
    for linha in range(total_linhas):
        definir_borda_celula(
            tabela.cell(linha, 0),
            ["left"],
            cor_borda,
            espessura
        )

    # Borda direita
    for linha in range(total_linhas):
        definir_borda_celula(
            tabela.cell(linha, ultima_coluna),
            ["right"],
            cor_borda,
            espessura
        )

def criar_slide_distribuicao_subregioes(
    prs,
    dados_subregioes,
    ano
):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # =========================================================
    # CABEÇALHO
    # =========================================================
    barra = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0,
        0,
        prs.slide_width,
        Inches(0.75)
    )
    barra.fill.solid()
    barra.fill.fore_color.rgb = AZUL_TABELA
    barra.line.fill.background()

    adicionar_logo(slide)

    add_text(
        slide,
        "DISTRIBUIÇÃO POR SUB-REGIÕES",
        0.35,
        0.18,
        10.4,
        0.40,
        24,
        BRANCO,
        True,
        FONTE_TITULO
    )

    add_text(
        slide,
        f"Indicadores consolidados • Ano {ano}",
        0.42,
        0.92,
        8.5,
        0.25,
        10.5,
        CINZA_SUBTITULO,
        False,
        FONTE_TEXTO
    )

    # =========================================================
    # DADOS
    # =========================================================
    linhas_dados = list(dados_subregioes or [])[:15]

    if not linhas_dados:
        add_text(
            slide,
            "Não foram encontrados dados de sub-regiões para o ano selecionado.",
            0.70,
            2.40,
            11.90,
            0.50,
            16,
            CINZA_SUBTITULO,
            False,
            FONTE_TEXTO
        )
        return

    # =========================================================
    # TABELA DE DADOS — SEM CABEÇALHO MESCLADO
    # =========================================================
    numero_linhas = len(linhas_dados)
    numero_colunas = 10

    x_tabela = 0.34
    y_cabecalho = 1.30

    altura_cabecalho_1 = 0.37
    altura_cabecalho_2 = 0.33
    altura_cabecalho_total = (
        altura_cabecalho_1 + altura_cabecalho_2
    )

    y_dados = y_cabecalho + altura_cabecalho_total

    larguras = [
        2.60,  # Sub-região

        1.10,  # Matrículas Meta
        1.10,  # Matrículas Realizado
        0.70,  # Matrículas %

        1.30,  # Hora-Aluno Meta
        1.30,  # Hora-Aluno Realizado
        0.70,  # Hora-Aluno %

        1.52,  # Receita Meta
        1.52,  # Receita Realizado
        0.71,  # Receita %
    ]

    # Tabela somente com as linhas de dados
    tabela = slide.shapes.add_table(
        numero_linhas,
        numero_colunas,
        Inches(x_tabela),
        Inches(y_dados),
        Inches(sum(larguras)),
        Inches(4.30)
    ).table

    for indice, largura in enumerate(larguras):
        tabela.columns[indice].width = Inches(largura)

    altura_linha = min(
        0.285,
        4.30 / max(len(linhas_dados), 1)
    )

    for linha in range(numero_linhas):
        tabela.rows[linha].height = Inches(altura_linha)


    # =========================================================
    # FUNÇÃO LOCAL PARA DESENHAR CÉLULAS DO CABEÇALHO
    # =========================================================
    def desenhar_celula_cabecalho(
        texto,
        x,
        y,
        largura,
        altura,
        cor_fundo,
        tamanho_fonte=8
    ):
        forma = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(x),
            Inches(y),
            Inches(largura),
            Inches(altura)
        )

        forma.fill.solid()
        forma.fill.fore_color.rgb = cor_fundo

        # Bordas brancas iguais em todo o cabeçalho
        forma.line.color.rgb = BRANCO
        forma.line.width = Pt(0.75)

        tf = forma.text_frame
        tf.clear()
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = False

        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER

        run = p.add_run()
        run.text = texto
        run.font.name = FONTE_TEXTO
        run.font.size = Pt(tamanho_fonte)
        run.font.bold = True
        run.font.color.rgb = BRANCO


    # =========================================================
    # CABEÇALHO: SUB-REGIÃO
    # =========================================================
    desenhar_celula_cabecalho(
        texto="SUB-REGIÃO",
        x=x_tabela,
        y=y_cabecalho,
        largura=larguras[0],
        altura=altura_cabecalho_total,
        cor_fundo=AZUL_TABELA,
        tamanho_fonte=8
    )


    # =========================================================
    # CABEÇALHO: GRUPOS DOS INDICADORES
    # =========================================================
    x_matriculas = x_tabela + larguras[0]

    largura_matriculas = sum(larguras[1:4])
    largura_hora_aluno = sum(larguras[4:7])
    largura_receita = sum(larguras[7:10])

    x_hora_aluno = x_matriculas + largura_matriculas
    x_receita = x_hora_aluno + largura_hora_aluno

    desenhar_celula_cabecalho(
        "MATRÍCULAS",
        x_matriculas,
        y_cabecalho,
        largura_matriculas,
        altura_cabecalho_1,
        AZUL_TABELA,
        8
    )

    desenhar_celula_cabecalho(
        "HORA-ALUNO",
        x_hora_aluno,
        y_cabecalho,
        largura_hora_aluno,
        altura_cabecalho_1,
        AZUL_TABELA,
        8
    )

    desenhar_celula_cabecalho(
        "RECEITA",
        x_receita,
        y_cabecalho,
        largura_receita,
        altura_cabecalho_1,
        AZUL_TABELA,
        8
    )

    # =========================================================
    # CABEÇALHO: META, REALIZADO E %
    # =========================================================
    subcabecalhos = [
        ("META", 1),
        ("REALIZADO", 2),
        ("%", 3),

        ("META", 4),
        ("REALIZADO", 5),
        ("%", 6),

        ("META", 7),
        ("REALIZADO", 8),
        ("%", 9),
    ]

    x_coluna = x_matriculas

    for texto, indice_coluna in subcabecalhos:
        largura_coluna = larguras[indice_coluna]

        desenhar_celula_cabecalho(
            texto=texto,
            x=x_coluna,
            y=y_cabecalho + altura_cabecalho_1,
            largura=largura_coluna,
            altura=altura_cabecalho_2,
            cor_fundo=RGBColor(31, 78, 151),
            tamanho_fonte=6.1
        )

        x_coluna += largura_coluna

    # =========================================================
    # LINHAS DE DADOS
    # =========================================================
    for indice, item in enumerate(linhas_dados):
        cor_linha = (
            BRANCO
            if indice % 2 == 0
            else RGBColor(247, 249, 252)
        )

        valores = [
            item.get("subregiao") or "Não vinculada",

            fmt_num(item.get("matriculas_meta")),
            fmt_num(item.get("matriculas_real")),
            fmt_pct(item.get("matriculas_pct")),

            fmt_num(item.get("hora_aluno_meta")),
            fmt_num(item.get("hora_aluno_real")),
            fmt_pct(item.get("hora_aluno_pct")),

            fmt_num(item.get("receita_meta"), moeda=True),
            fmt_num(item.get("receita_real"), moeda=True),
            fmt_pct(item.get("receita_pct")),
        ]

        campos_percentuais = {
            3: "matriculas_pct",
            6: "hora_aluno_pct",
            9: "receita_pct",
        }

        for coluna, valor in enumerate(valores):
            cell = tabela.cell(indice, coluna)
            cell.text = str(valor)
            cell.fill.solid()
            cell.fill.fore_color.rgb = cor_linha
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE

            cell.margin_left = Inches(0.035)
            cell.margin_right = Inches(0.035)
            cell.margin_top = 0
            cell.margin_bottom = 0

            for paragrafo in cell.text_frame.paragraphs:
                paragrafo.font.name = FONTE_TEXTO
                paragrafo.font.size = Pt(6.3)
                paragrafo.font.color.rgb = TEXTO_ESCURO
                paragrafo.font.bold = False

                if coluna == 0:
                    paragrafo.alignment = PP_ALIGN.LEFT
                    paragrafo.font.bold = True
                else:
                    paragrafo.alignment = PP_ALIGN.RIGHT

                if coluna in campos_percentuais:
                    percentual = item.get(
                        campos_percentuais[coluna]
                    ) or 0

                    paragrafo.font.bold = True
                    paragrafo.font.color.rgb = cor_percentual(
                        percentual
                    )
    
    # =========================================================
    # BORDA DIRETAMENTE NAS CÉLULAS EXTERNAS
    # =========================================================
    aplicar_borda_externa_tabela(
        tabela=tabela,
        total_linhas=numero_linhas,
        total_colunas=numero_colunas
    )

    # =========================================================
    # LEGENDA DOS STATUS
    # =========================================================
    legendas_status = [
        (
            "Meta atingida",
            "≥ 100%",
            RGBColor(22, 163, 74),
            RGBColor(232, 249, 238),
            1.62
        ),
        (
            "No caminho",
            "75%–99,9%",
            RGBColor(37, 99, 235),
            RGBColor(235, 242, 255),
            1.58
        ),
        (
            "Atenção",
            "51%–74,9%",
            RGBColor(217, 119, 6),
            RGBColor(255, 247, 229),
            1.48
        ),
        (
            "Crítico",
            "< 51%",
            RGBColor(220, 38, 38),
            RGBColor(254, 236, 236),
            1.15
        ),
        (
            "Realizado sem meta",
            "Meta = 0 e realizado > 0",
            RGBColor(100, 116, 139),
            RGBColor(241, 245, 249),
            2.45
        ),
        (
            "Sem movimento",
            "Meta = 0 e realizado = 0",
            RGBColor(100, 116, 139),
            RGBColor(241, 245, 249),
            2.15
        ),
    ]

    x_leg = 0.35
    y_leg = 6.57

    for (
        titulo_legenda,
        descricao_legenda,
        cor_texto,
        cor_fundo,
        largura_item
    ) in legendas_status:

        largura_badge = {
            "Meta atingida": 0.82,
            "No caminho": 0.78,
            "Atenção": 0.66,
            "Crítico": 0.55,
            "Realizado sem meta": 1.12,
            "Sem movimento": 0.92,
        }[titulo_legenda]

        badge = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(x_leg),
            Inches(y_leg),
            Inches(largura_badge),
            Inches(0.22)
        )
        badge.fill.solid()
        badge.fill.fore_color.rgb = cor_fundo
        badge.line.fill.background()

        caixa_badge = slide.shapes.add_textbox(
            Inches(x_leg),
            Inches(y_leg),
            Inches(largura_badge),
            Inches(0.22)
        )

        tf_badge = caixa_badge.text_frame
        tf_badge.clear()
        tf_badge.margin_left = 0
        tf_badge.margin_right = 0
        tf_badge.margin_top = 0
        tf_badge.margin_bottom = 0
        tf_badge.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf_badge.word_wrap = False

        p_badge = tf_badge.paragraphs[0]
        p_badge.alignment = PP_ALIGN.CENTER

        run_badge = p_badge.add_run()
        run_badge.text = titulo_legenda
        run_badge.font.name = FONTE_TEXTO
        run_badge.font.size = Pt(5.8)
        run_badge.font.bold = True
        run_badge.font.color.rgb = cor_texto

        caixa_desc = slide.shapes.add_textbox(
            Inches(x_leg + largura_badge + 0.06),
            Inches(y_leg),
            Inches(largura_item - largura_badge - 0.06),
            Inches(0.22)
        )

        tf_desc = caixa_desc.text_frame
        tf_desc.clear()
        tf_desc.margin_left = 0
        tf_desc.margin_right = 0
        tf_desc.margin_top = 0
        tf_desc.margin_bottom = 0
        tf_desc.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf_desc.word_wrap = False

        p_desc = tf_desc.paragraphs[0]
        p_desc.alignment = PP_ALIGN.LEFT

        run_desc = p_desc.add_run()
        run_desc.text = descricao_legenda
        run_desc.font.name = FONTE_TEXTO
        run_desc.font.size = Pt(5.7)
        run_desc.font.color.rgb = CINZA_SUBTITULO

        x_leg += largura_item + 0.10

    # =========================================================
    # RODAPÉ
    # =========================================================
    add_text(
        slide,
        (
            "Meta anual, realizado acumulado no ano e percentual "
            "alcançado por sub-região."
        ),
        0.48,
        7.02,
        11.85,
        0.18,
        7.8,
        CINZA_SUBTITULO,
        False,
        FONTE_TEXTO
    )

def criar_slide_distribuicao_modalidades(
    prs,
    dados_modalidades,
    ano
):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # =========================================================
    # CABEÇALHO
    # =========================================================
    barra = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0,
        0,
        prs.slide_width,
        Inches(0.75)
    )
    barra.fill.solid()
    barra.fill.fore_color.rgb = AZUL_TABELA
    barra.line.fill.background()

    adicionar_logo(slide)

    add_text(
        slide,
        "DISTRIBUIÇÃO POR MODALIDADES",
        0.35,
        0.18,
        10.4,
        0.40,
        24,
        BRANCO,
        True,
        FONTE_TITULO
    )

    add_text(
        slide,
        f"Indicadores consolidados • Ano {ano}",
        0.42,
        0.92,
        8.5,
        0.25,
        10.5,
        CINZA_SUBTITULO,
        False,
        FONTE_TEXTO
    )

    # =========================================================
    # DADOS
    # =========================================================
    linhas_dados = list(dados_modalidades or [])[:15]

    if not linhas_dados:
        add_text(
            slide,
            "Não foram encontrados dados de modaldiades para o ano selecionado.",
            0.70,
            2.40,
            11.90,
            0.50,
            16,
            CINZA_SUBTITULO,
            False,
            FONTE_TEXTO
        )
        return

    # =========================================================
    # TABELA DE DADOS — SEM CABEÇALHO MESCLADO
    # =========================================================
    numero_linhas = len(linhas_dados)
    numero_colunas = 10

    x_tabela = 0.34
    y_cabecalho = 1.30

    altura_cabecalho_1 = 0.37
    altura_cabecalho_2 = 0.33
    altura_cabecalho_total = (
        altura_cabecalho_1 + altura_cabecalho_2
    )

    y_dados = y_cabecalho + altura_cabecalho_total

    larguras = [
        2.60,  # Sub-região

        1.10,  # Matrículas Meta
        1.10,  # Matrículas Realizado
        0.70,  # Matrículas %

        1.30,  # Hora-Aluno Meta
        1.30,  # Hora-Aluno Realizado
        0.70,  # Hora-Aluno %

        1.52,  # Receita Meta
        1.52,  # Receita Realizado
        0.71,  # Receita %
    ]

    # Tabela somente com as linhas de dados
    tabela = slide.shapes.add_table(
        numero_linhas,
        numero_colunas,
        Inches(x_tabela),
        Inches(y_dados),
        Inches(sum(larguras)),
        Inches(4.30)
    ).table

    for indice, largura in enumerate(larguras):
        tabela.columns[indice].width = Inches(largura)

    altura_linha = min(
        0.285,
        4.30 / max(len(linhas_dados), 1)
    )

    for linha in range(numero_linhas):
        tabela.rows[linha].height = Inches(altura_linha)


    # =========================================================
    # FUNÇÃO LOCAL PARA DESENHAR CÉLULAS DO CABEÇALHO
    # =========================================================
    def desenhar_celula_cabecalho(
        texto,
        x,
        y,
        largura,
        altura,
        cor_fundo,
        tamanho_fonte=8
    ):
        forma = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(x),
            Inches(y),
            Inches(largura),
            Inches(altura)
        )

        forma.fill.solid()
        forma.fill.fore_color.rgb = cor_fundo

        # Bordas brancas iguais em todo o cabeçalho
        forma.line.color.rgb = BRANCO
        forma.line.width = Pt(0.75)

        tf = forma.text_frame
        tf.clear()
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = False

        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER

        run = p.add_run()
        run.text = texto
        run.font.name = FONTE_TEXTO
        run.font.size = Pt(tamanho_fonte)
        run.font.bold = True
        run.font.color.rgb = BRANCO


    # =========================================================
    # CABEÇALHO: MODALIDADE
    # =========================================================
    desenhar_celula_cabecalho(
        texto="MODALIDADE",
        x=x_tabela,
        y=y_cabecalho,
        largura=larguras[0],
        altura=altura_cabecalho_total,
        cor_fundo=AZUL_TABELA,
        tamanho_fonte=8
    )


    # =========================================================
    # CABEÇALHO: GRUPOS DOS INDICADORES
    # =========================================================
    x_matriculas = x_tabela + larguras[0]

    largura_matriculas = sum(larguras[1:4])
    largura_hora_aluno = sum(larguras[4:7])
    largura_receita = sum(larguras[7:10])

    x_hora_aluno = x_matriculas + largura_matriculas
    x_receita = x_hora_aluno + largura_hora_aluno

    desenhar_celula_cabecalho(
        "MATRÍCULAS",
        x_matriculas,
        y_cabecalho,
        largura_matriculas,
        altura_cabecalho_1,
        AZUL_TABELA,
        8
    )

    desenhar_celula_cabecalho(
        "HORA-ALUNO",
        x_hora_aluno,
        y_cabecalho,
        largura_hora_aluno,
        altura_cabecalho_1,
        AZUL_TABELA,
        8
    )

    desenhar_celula_cabecalho(
        "RECEITA",
        x_receita,
        y_cabecalho,
        largura_receita,
        altura_cabecalho_1,
        AZUL_TABELA,
        8
    )

    # =========================================================
    # CABEÇALHO: META, REALIZADO E %
    # =========================================================
    subcabecalhos = [
        ("META", 1),
        ("REALIZADO", 2),
        ("%", 3),

        ("META", 4),
        ("REALIZADO", 5),
        ("%", 6),

        ("META", 7),
        ("REALIZADO", 8),
        ("%", 9),
    ]

    x_coluna = x_matriculas

    for texto, indice_coluna in subcabecalhos:
        largura_coluna = larguras[indice_coluna]

        desenhar_celula_cabecalho(
            texto=texto,
            x=x_coluna,
            y=y_cabecalho + altura_cabecalho_1,
            largura=largura_coluna,
            altura=altura_cabecalho_2,
            cor_fundo=RGBColor(31, 78, 151),
            tamanho_fonte=6.1
        )

        x_coluna += largura_coluna

    # =========================================================
    # LINHAS DE DADOS
    # =========================================================
    for indice, item in enumerate(linhas_dados):
        cor_linha = (
            BRANCO
            if indice % 2 == 0
            else RGBColor(247, 249, 252)
        )

        valores = [
            item.get("modalidade") or "Não informada",

            fmt_num(item.get("matriculas_meta")),
            fmt_num(item.get("matriculas_real")),
            fmt_pct(item.get("matriculas_pct")),

            fmt_num(item.get("hora_aluno_meta")),
            fmt_num(item.get("hora_aluno_real")),
            fmt_pct(item.get("hora_aluno_pct")),

            fmt_num(item.get("receita_meta"), moeda=True),
            fmt_num(item.get("receita_real"), moeda=True),
            fmt_pct(item.get("receita_pct")),
        ]

        campos_percentuais = {
            3: "matriculas_pct",
            6: "hora_aluno_pct",
            9: "receita_pct",
        }

        for coluna, valor in enumerate(valores):
            cell = tabela.cell(indice, coluna)
            cell.text = str(valor)
            cell.fill.solid()
            cell.fill.fore_color.rgb = cor_linha
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE

            cell.margin_left = Inches(0.035)
            cell.margin_right = Inches(0.035)
            cell.margin_top = 0
            cell.margin_bottom = 0

            for paragrafo in cell.text_frame.paragraphs:
                paragrafo.font.name = FONTE_TEXTO
                paragrafo.font.size = Pt(6.3)
                paragrafo.font.color.rgb = TEXTO_ESCURO
                paragrafo.font.bold = False

                if coluna == 0:
                    paragrafo.alignment = PP_ALIGN.LEFT
                    paragrafo.font.bold = True
                else:
                    paragrafo.alignment = PP_ALIGN.RIGHT

                if coluna in campos_percentuais:
                    percentual = item.get(
                        campos_percentuais[coluna]
                    ) or 0

                    paragrafo.font.bold = True
                    paragrafo.font.color.rgb = cor_percentual(
                        percentual
                    )
    
    # =========================================================
    # BORDA DIRETAMENTE NAS CÉLULAS EXTERNAS
    # =========================================================
    aplicar_borda_externa_tabela(
        tabela=tabela,
        total_linhas=numero_linhas,
        total_colunas=numero_colunas
    )

    # =========================================================
    # LEGENDA DOS STATUS
    # =========================================================
    legendas_status = [
        (
            "Meta atingida",
            "≥ 100%",
            RGBColor(22, 163, 74),
            RGBColor(232, 249, 238),
            1.62
        ),
        (
            "No caminho",
            "75%–99,9%",
            RGBColor(37, 99, 235),
            RGBColor(235, 242, 255),
            1.58
        ),
        (
            "Atenção",
            "51%–74,9%",
            RGBColor(217, 119, 6),
            RGBColor(255, 247, 229),
            1.48
        ),
        (
            "Crítico",
            "< 51%",
            RGBColor(220, 38, 38),
            RGBColor(254, 236, 236),
            1.15
        ),
        (
            "Realizado sem meta",
            "Meta = 0 e realizado > 0",
            RGBColor(100, 116, 139),
            RGBColor(241, 245, 249),
            2.45
        ),
        (
            "Sem movimento",
            "Meta = 0 e realizado = 0",
            RGBColor(100, 116, 139),
            RGBColor(241, 245, 249),
            2.15
        ),
    ]

    x_leg = 0.35
    y_leg = 6.57

    for (
        titulo_legenda,
        descricao_legenda,
        cor_texto,
        cor_fundo,
        largura_item
    ) in legendas_status:

        largura_badge = {
            "Meta atingida": 0.82,
            "No caminho": 0.78,
            "Atenção": 0.66,
            "Crítico": 0.55,
            "Realizado sem meta": 1.12,
            "Sem movimento": 0.92,
        }[titulo_legenda]

        badge = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(x_leg),
            Inches(y_leg),
            Inches(largura_badge),
            Inches(0.22)
        )
        badge.fill.solid()
        badge.fill.fore_color.rgb = cor_fundo
        badge.line.fill.background()

        caixa_badge = slide.shapes.add_textbox(
            Inches(x_leg),
            Inches(y_leg),
            Inches(largura_badge),
            Inches(0.22)
        )

        tf_badge = caixa_badge.text_frame
        tf_badge.clear()
        tf_badge.margin_left = 0
        tf_badge.margin_right = 0
        tf_badge.margin_top = 0
        tf_badge.margin_bottom = 0
        tf_badge.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf_badge.word_wrap = False

        p_badge = tf_badge.paragraphs[0]
        p_badge.alignment = PP_ALIGN.CENTER

        run_badge = p_badge.add_run()
        run_badge.text = titulo_legenda
        run_badge.font.name = FONTE_TEXTO
        run_badge.font.size = Pt(5.8)
        run_badge.font.bold = True
        run_badge.font.color.rgb = cor_texto

        caixa_desc = slide.shapes.add_textbox(
            Inches(x_leg + largura_badge + 0.06),
            Inches(y_leg),
            Inches(largura_item - largura_badge - 0.06),
            Inches(0.22)
        )

        tf_desc = caixa_desc.text_frame
        tf_desc.clear()
        tf_desc.margin_left = 0
        tf_desc.margin_right = 0
        tf_desc.margin_top = 0
        tf_desc.margin_bottom = 0
        tf_desc.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf_desc.word_wrap = False

        p_desc = tf_desc.paragraphs[0]
        p_desc.alignment = PP_ALIGN.LEFT

        run_desc = p_desc.add_run()
        run_desc.text = descricao_legenda
        run_desc.font.name = FONTE_TEXTO
        run_desc.font.size = Pt(5.7)
        run_desc.font.color.rgb = CINZA_SUBTITULO

        x_leg += largura_item + 0.10

    # =========================================================
    # RODAPÉ
    # =========================================================
    add_text(
        slide,
        (
            "Meta anual, realizado acumulado no ano e percentual "
            "alcançado por modalidade."
        ),
        0.48,
        7.02,
        11.85,
        0.18,
        7.8,
        CINZA_SUBTITULO,
        False,
        FONTE_TEXTO
    )

def cor_percentual(percentual):
    percentual = float(percentual or 0)

    if percentual >= 100:
        return RGBColor(22, 163, 74)

    if percentual >= 75:
        return RGBColor(37, 99, 235)

    if percentual >= 51:
        return RGBColor(217, 119, 6)

    return RGBColor(220, 38, 38)

def calcular_percentual(realizado, meta):
    realizado = float(realizado or 0)
    meta = float(meta or 0)

    if meta <= 0:
        return 0.0

    return realizado / meta * 100

def criar_slide_porta_entrada(prs, resumo, ano):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # =========================================================
    # CABEÇALHO INSTITUCIONAL
    # =========================================================
    barra = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0, 0,
        prs.slide_width,
        Inches(0.75)
    )
    barra.fill.solid()
    barra.fill.fore_color.rgb = AZUL_TABELA
    barra.line.fill.background()

    adicionar_logo(slide)

    add_text(
        slide,
        "VISÃO EXECUTIVA",
        0.35, 0.18, 8.5, 0.40,
        24, BRANCO, True, FONTE_TITULO
    )

    add_text(
        slide,
        f"Indicadores consolidados • Ano {ano}",
        0.42, 0.92, 8.5, 0.25,
        10.5, CINZA_SUBTITULO, False, FONTE_TEXTO
    )

    # Data de atualização
    add_text(
        slide,
        f"Atualizado em {datetime.now().strftime('%d/%m/%Y')}",
        10.45, 0.92, 2.30, 0.25,
        9, CINZA_SUBTITULO, False, FONTE_TEXTO
    )

    # =========================================================
    # CARDS
    # =========================================================
    cards = [
        (
            "MATRÍCULAS",
            "M",
            resumo.get("matriculas", {}),
            False,
            True
        ),
        (
            "HORA-ALUNO",
            "HA",
            resumo.get("hora_aluno", {}),
            False,
            True
        ),
        (
            "RECEITA",
            "R$",
            resumo.get("receita", {}),
            True,
            False
        ),
    ]

    x_inicial = 0.45
    y_inicial = 1.34

    largura_card = 3.95
    altura_card = 4.55
    espacamento = 0.28

    for indice, (
        titulo,
        icone,
        dados_card,
        moeda,
        mostrar_financiamento
    ) in enumerate(cards):

        x = x_inicial + indice * (largura_card + espacamento)

        criar_card_porta_entrada(
            slide=slide,
            titulo=titulo,
            icone=icone,
            dados_card=dados_card,
            x=x,
            y=y_inicial,
            w=largura_card,
            h=altura_card,
            moeda=moeda,
            mostrar_financiamento=mostrar_financiamento
        )
    
    # =========================================================
    # LEGENDA DOS TIPOS DE FINANCIAMENTO
    # =========================================================
    legendas = [
        (
            "GR",
            RGBColor(24, 121, 45),
            "Gratuidade Regimental",
            2.05
        ),
        (
            "GNR",
            RGBColor(80, 35, 140),
            "Gratuidade Não Regimental",
            2.55
        ),
        (
            "PG",
            AZUL_TABELA,
            "Pago",
            1.05
        ),
    ]

    # Posição inicial da legenda, abaixo dos cards
    x_leg = 0.72
    y_leg = 6.02

    for sigla, cor, descricao, largura_item in legendas:

        largura_sigla = 0.46
        altura_legenda = 0.24

        # Marcador colorido
        marcador = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(x_leg),
            Inches(y_leg),
            Inches(largura_sigla),
            Inches(altura_legenda)
        )
        marcador.fill.solid()
        marcador.fill.fore_color.rgb = cor
        marcador.line.fill.background()

        # Sigla centralizada
        caixa_sigla = slide.shapes.add_textbox(
            Inches(x_leg),
            Inches(y_leg),
            Inches(largura_sigla),
            Inches(altura_legenda)
        )

        tf_sigla = caixa_sigla.text_frame
        tf_sigla.clear()
        tf_sigla.margin_left = 0
        tf_sigla.margin_right = 0
        tf_sigla.margin_top = 0
        tf_sigla.margin_bottom = 0
        tf_sigla.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf_sigla.word_wrap = False

        p_sigla = tf_sigla.paragraphs[0]
        p_sigla.alignment = PP_ALIGN.CENTER

        run_sigla = p_sigla.add_run()
        run_sigla.text = sigla
        run_sigla.font.name = FONTE_TEXTO
        run_sigla.font.size = Pt(6.8)
        run_sigla.font.bold = True
        run_sigla.font.color.rgb = BRANCO

        # Descrição
        caixa_descricao = slide.shapes.add_textbox(
            Inches(x_leg + largura_sigla + 0.08),
            Inches(y_leg),
            Inches(largura_item - largura_sigla - 0.08),
            Inches(altura_legenda)
        )

        tf_descricao = caixa_descricao.text_frame
        tf_descricao.clear()
        tf_descricao.margin_left = 0
        tf_descricao.margin_right = 0
        tf_descricao.margin_top = 0
        tf_descricao.margin_bottom = 0
        tf_descricao.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf_descricao.word_wrap = False

        p_descricao = tf_descricao.paragraphs[0]
        p_descricao.alignment = PP_ALIGN.LEFT

        run_descricao = p_descricao.add_run()
        run_descricao.text = descricao
        run_descricao.font.name = FONTE_TEXTO
        run_descricao.font.size = Pt(7.6)
        run_descricao.font.color.rgb = CINZA_SUBTITULO

        # Espaço fixo entre os três conjuntos
        x_leg += largura_item + 0.35

    # =========================================================
    # FAIXA INFERIOR
    # =========================================================
    faixa = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.45),
        Inches(6.48),
        Inches(12.35),
        Inches(0.55)
    )
    faixa.fill.solid()
    faixa.fill.fore_color.rgb = RGBColor(245, 248, 252)
    faixa.line.fill.background()

    add_text(
        slide,
        (
            "Leitura dos indicadores: resultados realizados acumulados "
            "no período em comparação com as respectivas metas anuais."
        ),
        0.72, 6.66, 11.80, 0.20,
        9.2, CINZA_SUBTITULO, False, FONTE_TEXTO
    )

def criar_card_porta_entrada( 
    slide,
    titulo,
    icone,
    dados_card,
    x,
    y,
    w,
    h,
    moeda=False,
    mostrar_financiamento=True
):
    # =========================================================
    # FUNDO DO CARD
    # =========================================================
    card = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x),
        Inches(y),
        Inches(w),
        Inches(h)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = BRANCO

    # Sem contorno cinza pesado
    card.line.color.rgb = RGBColor(238, 242, 247)
    card.line.width = Pt(0.5)

    # =========================================================
    # CABEÇALHO AZUL DO CARD
    # =========================================================
    topo = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x),
        Inches(y),
        Inches(w),
        Inches(0.68)
    )
    topo.fill.solid()
    topo.fill.fore_color.rgb = AZUL_TABELA
    topo.line.fill.background()

    # Retângulo sobreposto para deixar a base do cabeçalho reta
    base_topo = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(x),
        Inches(y + 0.40),
        Inches(w),
        Inches(0.28)
    )
    base_topo.fill.solid()
    base_topo.fill.fore_color.rgb = AZUL_TABELA
    base_topo.line.fill.background()

    # =========================================================
    # ÍCONES DOS INDICADORES — CENTRALIZADOS
    # =========================================================
    icone_x = x + 0.22
    icone_y = y + 0.15
    tamanho_box = 0.42

    icone_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(icone_x),
        Inches(icone_y),
        Inches(tamanho_box),
        Inches(tamanho_box)
    )
    icone_box.fill.solid()
    icone_box.fill.fore_color.rgb = RGBColor(235, 239, 245)
    icone_box.line.fill.background()

    if titulo == "MATRÍCULAS":
        simbolo = "🎓"
        tamanho_fonte = 13

    elif titulo == "HORA-ALUNO":
        simbolo = "⏱️"
        tamanho_fonte = 13

    elif titulo == "RECEITA":
        simbolo = "💰"
        tamanho_fonte = 13

    else:
        simbolo = "📊"
        tamanho_fonte = 13

    tb = slide.shapes.add_textbox(
        Inches(icone_x),
        Inches(icone_y),
        Inches(tamanho_box),
        Inches(tamanho_box)
    )

    tf = tb.text_frame
    tf.clear()
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER

    run = p.add_run()
    run.text = simbolo
    run.font.name = "Segoe UI Emoji"
    run.font.size = Pt(tamanho_fonte)
    run.font.color.rgb = TEXTO_ESCURO

    # Nome do indicador ao lado do ícone
    add_text(
        slide,
        titulo,
        x + 0.70,
        y + 0.225,
        w - 0.95,
        0.22,
        12.5,
        BRANCO,
        True,
        FONTE_TITULO
    )

    # =========================================================
    # DADOS PRINCIPAIS
    # =========================================================
    total = float(dados_card.get("total") or 0)
    meta = float(dados_card.get("meta_total") or 0)
    pct_meta = float(dados_card.get("pct_meta") or 0)

    tamanho_total = 25

    if moeda:
        tamanho_total = 22

    add_text(
        slide,
        fmt_num(total, moeda),
        x + 0.28,
        y + 0.95,
        w - 0.56,
        0.48,
        tamanho_total,
        TEXTO_ESCURO,
        True,
        FONTE_TITULO
    )

    # Meta em duas linhas
    add_text(
        slide,
        "Meta anual",
        x + 0.30,
        y + 1.57,
        1.25,
        0.17,
        8.4,
        CINZA_SUBTITULO,
        False,
        FONTE_TEXTO
    )

    add_text(
        slide,
        fmt_num(meta, moeda),
        x + 0.30,
        y + 1.77,
        2.45,
        0.24,
        11.5 if not moeda else 10.5,
        TEXTO_ESCURO,
        True,
        FONTE_TEXTO
    )

    add_text(
        slide,
        fmt_pct(pct_meta),
        x + w - 1.12,
        y + 1.76,
        0.82,
        0.24,
        10.5,
        AZUL_TABELA,
        True,
        FONTE_TEXTO
    )

    # =========================================================
    # BARRA DE PROGRESSO
    # =========================================================
    barra_x = x + 0.30
    barra_y = y + 2.11
    barra_w = w - 0.60
    barra_h = 0.13

    barra_bg = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(barra_x),
        Inches(barra_y),
        Inches(barra_w),
        Inches(barra_h)
    )
    barra_bg.fill.solid()
    barra_bg.fill.fore_color.rgb = RGBColor(226, 232, 240)
    barra_bg.line.fill.background()

    largura_percentual = max(0, min(pct_meta, 100)) / 100

    if largura_percentual > 0:
        barra_fg = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(barra_x),
            Inches(barra_y),
            Inches(barra_w * largura_percentual),
            Inches(barra_h)
        )
        barra_fg.fill.solid()
        barra_fg.fill.fore_color.rgb = AZUL_TABELA
        barra_fg.line.fill.background()

    # =========================================================
    # DIVISOR
    # =========================================================
    divisor = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(x + 0.30),
        Inches(y + 2.51),
        Inches(w - 0.60),
        Inches(0.01)
    )
    divisor.fill.solid()
    divisor.fill.fore_color.rgb = RGBColor(226, 232, 240)
    divisor.line.fill.background()

    # =========================================================
    # MATRÍCULAS E HORA-ALUNO
    # =========================================================
    if mostrar_financiamento:
        coluna_financiamento_x = x + 0.30
        coluna_valores_x = x + 1.75

        add_text(
            slide,
            "Financiamento",
            coluna_financiamento_x,
            y + 2.72,
            1.30,
            0.18,
            8.2,
            CINZA_SUBTITULO,
            True,
            FONTE_TEXTO
        )

        add_text(
            slide,
            "Realizado / Meta",
            coluna_valores_x,
            y + 2.72,
            1.83,
            0.18,
            8.2,
            CINZA_SUBTITULO,
            True,
            FONTE_TEXTO
        )

        linhas = [
            (
                "GR",
                RGBColor(24, 121, 45),
                dados_card.get("gr"),
                dados_card.get("meta_gr")
            ),
            (
                "GNR",
                RGBColor(80, 35, 140),
                dados_card.get("g"),
                dados_card.get("meta_g")
            ),
            (
                "PG",
                AZUL_TABELA,
                dados_card.get("p"),
                dados_card.get("meta_p")
            ),
        ]

        y_linha = y + 3.14

        for sigla, cor, realizado, meta_financiamento in linhas:
            largura_sigla = 0.46
            altura_sigla = 0.24

            marcador = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(coluna_financiamento_x),
                Inches(y_linha),
                Inches(largura_sigla),
                Inches(altura_sigla)
            )
            marcador.fill.solid()
            marcador.fill.fore_color.rgb = cor
            marcador.line.fill.background()

            caixa_sigla = slide.shapes.add_textbox(
                Inches(coluna_financiamento_x),
                Inches(y_linha),
                Inches(largura_sigla),
                Inches(altura_sigla)
            )

            tf_sigla = caixa_sigla.text_frame
            tf_sigla.clear()
            tf_sigla.margin_left = 0
            tf_sigla.margin_right = 0
            tf_sigla.margin_top = 0
            tf_sigla.margin_bottom = 0
            tf_sigla.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf_sigla.word_wrap = False

            p_sigla = tf_sigla.paragraphs[0]
            p_sigla.alignment = PP_ALIGN.CENTER

            run_sigla = p_sigla.add_run()
            run_sigla.text = sigla
            run_sigla.font.name = FONTE_TEXTO
            run_sigla.font.size = Pt(6.8)
            run_sigla.font.bold = True
            run_sigla.font.color.rgb = BRANCO

            # O valor fica rigorosamente abaixo da coluna
            # "Realizado / Meta"
            add_text(
                slide,
                (
                    f"{fmt_num(realizado)} / "
                    f"{fmt_num(meta_financiamento)}"
                ),
                coluna_valores_x,
                y_linha + 0.035,
                1.83,
                0.20,
                8.5,
                TEXTO_ESCURO,
                False,
                FONTE_TEXTO
            )

            y_linha += 0.47

    # =========================================================
    # RECEITA
    # =========================================================
    else:
        add_text(
            slide,
            (
                "Receita acumulada no exercício em relação "
                "à meta anual prevista."
            ),
            x + 0.30,
            y + 3.60,
            w - 0.60,
            0.42,
            9.2,
            CINZA_SUBTITULO,
            False,
            FONTE_TEXTO
        )

def fmt_num(valor, moeda=False):
    valor = float(valor or 0)
    if moeda:
        return f"R$ {valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{valor:,.0f}".replace(",", ".")


def fmt_pct(valor):
    return f"{float(valor or 0):.1f}%".replace(".", ",")

def criar_slide_capa(prs, ano):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Fundo branco/azulado
    fundo = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0, 0,
        prs.slide_width,
        prs.slide_height
    )
    fundo.fill.solid()
    fundo.fill.fore_color.rgb = RGBColor(248, 251, 255)
    fundo.line.fill.background()

    # Logo SENAI
    adicionar_logo(slide, capa=True)

    # Elemento azul grande inferior direito
    forma_azul = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(9.0),
        Inches(4.15),
        Inches(5.6),
        Inches(3.8)
    )
    forma_azul.fill.solid()
    forma_azul.fill.fore_color.rgb = AZUL_TABELA
    forma_azul.line.fill.background()
    forma_azul.rotation = -45

    # Linha diagonal decorativa
    linha = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(9.35),
        Inches(2.65),
        Inches(0.02),
        Inches(4.6)
    )
    linha.fill.solid()
    linha.fill.fore_color.rgb = RGBColor(96, 150, 255)
    linha.line.fill.background()
    linha.rotation = -45

    # Losangos claros
    losango1 = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(7.9),
        Inches(-0.75),
        Inches(2.3),
        Inches(2.3)
    )
    losango1.fill.solid()
    losango1.fill.fore_color.rgb = RGBColor(224, 234, 250)
    losango1.line.fill.background()
    losango1.rotation = 45

    losango2 = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(7.0),
        Inches(5.95),
        Inches(2.1),
        Inches(2.1)
    )
    losango2.fill.solid()
    losango2.fill.fore_color.rgb = RGBColor(236, 242, 252)
    losango2.line.fill.background()
    losango2.rotation = 45

    # Pontilhado superior esquerdo
    for i in range(6):
        for j in range(6):
            ponto = slide.shapes.add_shape(
                MSO_SHAPE.OVAL,
                Inches(0.32 + i * 0.18),
                Inches(0.35 + j * 0.18),
                Inches(0.025),
                Inches(0.025)
            )
            ponto.fill.solid()
            ponto.fill.fore_color.rgb = RGBColor(90, 140, 220)
            ponto.line.fill.background()

    # Título
    titulo = slide.shapes.add_textbox(
        Inches(0.75),
        Inches(2.55),
        Inches(7.5),
        Inches(1.45)
    )
    tf = titulo.text_frame
    tf.clear()

    p = tf.paragraphs[0]
    p.text = "CARTEIRA DE"
    p.font.name = FONTE_TITULO
    p.font.size = Pt(46)
    p.font.bold = True
    p.font.color.rgb = AZUL_TABELA

    p = tf.add_paragraph()
    p.text = "PROGRAMAS"
    p.font.name = FONTE_TITULO
    p.font.size = Pt(46)
    p.font.bold = True
    p.font.color.rgb = AZUL_TABELA

    # Subtítulo
    subtitulo = slide.shapes.add_textbox(
        Inches(0.78),
        Inches(4.75),
        Inches(7.5),
        Inches(0.45)
    )
    p = subtitulo.text_frame.paragraphs[0]
    p.text = f"Portfólio institucional • Ano {ano}"
    p.font.name = FONTE_TEXTO
    p.font.size = Pt(20)
    p.font.color.rgb = RGBColor(55, 65, 81)

    # Data com ícone
    add_icon(slide, "calendario.png", 0.78, 6.55, 0.45)

    data = slide.shapes.add_textbox(
        Inches(1.45),
        Inches(6.64),
        Inches(4.8),
        Inches(0.3)
    )
    p = data.text_frame.paragraphs[0]
    p.text = f"Gerado automaticamente em {datetime.now().strftime('%d/%m/%Y')}"
    p.font.name = FONTE_TEXTO
    p.font.size = Pt(10)
    p.font.color.rgb = CINZA_SUBTITULO


def classificar_financiamento(item):
    txt = (item.get("tipo_financiamento") or "").upper()

    if "PAGO POR PESSOA FÍSICA OU EMPRESA" in txt:
        return "pago"

    if "GRATUIDADE NÃO REGIMENTAL" in txt:
        return "gnr"

    if "GRATUIDADE REGIMENTAL" in txt:
        return "gr"

    return "pago"

def desenhar_tabela_programas_financiamento(slide, titulo, cor, itens, x, y, w, h):
    card = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = BRANCO
    card.line.color.rgb = RGBColor(226, 232, 240)
    card.line.width = Pt(0.75)

    # Faixa de título
    faixa = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(0.55)
    )
    faixa.fill.solid()
    faixa.fill.fore_color.rgb = cor
    faixa.line.fill.background()

    add_text(
        slide, titulo,
        x + 0.55, y + 0.15, w - 0.75, 0.25,
        11, BRANCO, True
    )

    linhas = len(itens)

    altura_tabela = 0.32 + (linhas * 0.28)

    tabela = slide.shapes.add_table(
        linhas + 1,
        3,
        Inches(x),
        Inches(y + 0.55),
        Inches(w),
        Inches(altura_tabela)
    ).table

    # A tabela não possui cabeçalho interno.
    # Impede o PowerPoint de formatar a primeira linha como cabeçalho.
    tabela.first_row = False
    tabela.last_row = False
    tabela.first_col = False
    tabela.last_col = False

    tabela.rows[0].height = Inches(0.32)

    larguras = [0.45, w - 2.25, 1.80]
    for i, largura in enumerate(larguras):
        tabela.columns[i].width = Inches(largura)

    headers = ["Nº", "Nome do Programa", "Interlocutor"]

    for c, texto in enumerate(headers):
        cell = tabela.cell(0, c)
        cell.text = texto.upper()
        cell.fill.solid()
        cell.fill.fore_color.rgb = cor
        cell.vertical_anchor = 3

        for p in cell.text_frame.paragraphs:
            p.font.name = FONTE_TEXTO
            p.font.size = Pt(6.8)
            p.font.bold = True
            p.font.color.rgb = BRANCO
            p.alignment = PP_ALIGN.CENTER

    for idx in range(1, linhas + 1):
        item = itens[idx - 1] if idx - 1 < len(itens) else {}

        row = idx
        tabela.rows[row].height = Inches(0.28)

        cor_linha = BRANCO if idx % 2 == 1 else RGBColor(245, 248, 252)

        valores = [
            f"{idx:02d}" if item else "",
            item.get("nome_programa", "") if item else "",
            item.get("interlocutor", "") if item else ""
        ]

        for c, valor in enumerate(valores):
            cell = tabela.cell(row, c)
            cell.text = str(valor or "")
            cell.fill.solid()
            cell.fill.fore_color.rgb = cor_linha
            cell.vertical_anchor = 3

            for p in cell.text_frame.paragraphs:
                p.font.name = FONTE_TEXTO
                p.font.size = Pt(6.7)
                p.font.color.rgb = TEXTO_ESCURO
                p.alignment = PP_ALIGN.CENTER if c == 0 else PP_ALIGN.LEFT

                if c == 1 and item:
                    p.font.bold = True

def desenhar_legenda_financiamento(slide, titulo, texto, cor, icone, x, y):
    add_icon(slide, icone, x, y - 0.04, 0.52)

    add_text(slide, titulo, x + 0.65, y + 0.02, 2.4, 0.20, 9, cor, True)
    add_text(slide, texto, x + 0.65, y + 0.28, 3.2, 0.35, 7.4, TEXTO_ESCURO)

def criar_slide_tabela(prs, dados, ano):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Cabeçalho
    barra = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.75)
    )
    barra.fill.solid()
    barra.fill.fore_color.rgb = AZUL_TABELA
    barra.line.fill.background()

    adicionar_logo(slide)

    add_text(
        slide, "PROGRAMAS VIGENTES",
        0.35, 0.18, 8.5, 0.4,
        24, BRANCO, True, FONTE_TITULO
    )

    grupos = {
        "pago": {
            "titulo": "PAGO",
            "cor": AZUL_TABELA,
            "x": 0.25,
            "w": 4.25,
            "itens": []
        },
        "gr": {
            "titulo": "GRATUIDADE REGIMENTAL",
            "cor": RGBColor(24, 121, 45),
            "x": 4.65,
            "w": 4.25,
            "itens": []
        },
        "gnr": {
            "titulo": "GRATUIDADE NÃO REGIMENTAL",
            "cor": RGBColor(80, 35, 140),
            "x": 9.05,
            "w": 4.00,
            "itens": []
        }
    }

    for item in dados:
        grupos[classificar_financiamento(item)]["itens"].append(item)

    for grupo in grupos.values():
        desenhar_tabela_programas_financiamento(
            slide,
            titulo=grupo["titulo"],
            cor=grupo["cor"],
            itens=grupo["itens"],
            x=grupo["x"],
            y=1.05,
            w=grupo["w"],
            h=4.95
        )

    # Legenda inferior
    add_card(slide, 0.25, 6.18, 12.80, 0.75)

    desenhar_legenda_financiamento(
        slide, "PAGO",
        "Programas com cobrança de mensalidade ou contraprestação financeira.",
        AZUL_TABELA,
        "pg.png",
        0.65, 6.32
    )

    desenhar_legenda_financiamento(
        slide, "GRATUIDADE REGIMENTAL",
        "Programas ofertados gratuitamente conforme previsão da gratuidade regimental.",
        RGBColor(24, 121, 45),
        "gr.png",
        4.85, 6.32
    )

    desenhar_legenda_financiamento(
        slide, "GRATUIDADE NÃO REGIMENTAL",
        "Programas gratuitos não enquadrados na gratuidade regimental.",
        RGBColor(80, 35, 140),
        "gnr.png",
        9.15, 6.32
    )

def adicionar_logo(slide, capa=False):

    logo = LOGO_CAPA if capa else LOGO_SLIDE

    if not logo.exists():
        return

    if capa:
        slide.shapes.add_picture(
            str(logo),
            Inches(10.85),
            Inches(0.45),
            width=Inches(1.75)
        )
    else:
        slide.shapes.add_picture(
            str(logo),
            Inches(11.15),
            Inches(0.13),
            width=Inches(1.55)
        )

def criar_lista_texto(valor):
    if not valor:
        return "—"

    itens = [
        x.strip()
        for x in str(valor).split(",")
        if x.strip()
    ]

    return "\n".join([f"• {x}" for x in itens]) if itens else "—"

def add_text(slide, text, x, y, w, h, size=10, color=TEXTO_ESCURO, bold=False, font=FONTE_TEXTO):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = None

    p = tf.paragraphs[0]
    p.text = str(text or "")
    p.font.name = font
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color

    return box


def add_card(slide, x, y, w, h):
    card = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = BRANCO
    card.line.color.rgb = RGBColor(226, 232, 240)
    card.line.width = Pt(0.75)
    return card


def add_icon(slide, arquivo, x, y, size=0.72):
    slide.shapes.add_picture(
        str(ICON_PATH / arquivo),
        Inches(x),
        Inches(y),
        width=Inches(size)
    )


def criar_card_indicador_exec(slide, titulo, icon, realizado, meta_atual, meta_ano, x, y, moeda=False):
    add_card(slide, x, y, 3.95, 1.35)
    add_icon(slide, icon, x + 0.22, y + 0.18)

    def fmt(v):
        v = float(v or 0)
        if moeda:
            return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{v:,.0f}".replace(",", ".")

    add_text(slide, "Realizado", x + 0.90, y + 0.74, 2.6, 0.25, 14, AZUL_TABELA, True, FONTE_TITULO)
    add_text(slide, fmt(realizado), x + 0.90, y + 0.50, 2.6, 0.30, 16, TEXTO_ESCURO, True)
    add_text(slide, "Realizado", x + 0.90, y + 0.78, 2.6, 0.30, 17, AZUL_TABELA, True, FONTE_TITULO)

    linha = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(x + 0.90), Inches(y + 1.02), Inches(2.85), Inches(0.01)
    )
    linha.fill.solid()
    linha.fill.fore_color.rgb = RGBColor(226, 232, 240)
    linha.line.fill.background()

    add_text(slide, "Meta até o momento", x + 0.90, y + 1.10, 1.8, 0.18, 8, TEXTO_ESCURO)
    add_text(slide, fmt(meta_atual), x + 2.90, y + 1.10, 0.8, 0.18, 8, TEXTO_ESCURO)

    add_text(slide, "Meta anual", x + 0.90, y + 1.25, 1.8, 0.18, 8, TEXTO_ESCURO)
    add_text(slide, fmt(meta_ano), x + 2.90, y + 1.25, 0.8, 0.18, 8, TEXTO_ESCURO)

def adicionar_numero_slide(slide, numero):
    box = slide.shapes.add_textbox(
        Inches(12.55),
        Inches(7.08),
        Inches(0.45),
        Inches(0.25)
    )
    p = box.text_frame.paragraphs[0]
    p.text = str(numero)
    p.font.name = FONTE_TEXTO
    p.font.size = Pt(8)
    p.font.color.rgb = CINZA_SUBTITULO
    p.alignment = PP_ALIGN.RIGHT

def criar_slide_programa(prs, programa, ano):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Cabeçalho azul
    barra = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0, 0, prs.slide_width, Inches(0.75)
    )
    barra.fill.solid()
    barra.fill.fore_color.rgb = AZUL_TABELA
    barra.line.fill.background()

    adicionar_logo(slide)

    add_text(
        slide,
        programa.get("nome_programa", "Programa"),
        0.45, 0.18, 10.4, 0.42,
        24, BRANCO, True, FONTE_TITULO
    )

    # OBJETIVO
    add_card(slide, 0.30, 0.86, 12.75, 1.03)
    add_icon(slide, "alvo.png", 0.47, 0.97, 0.58)

    add_text(slide, "OBJETIVO", 1.32, 1.02, 3, 0.25, 13, AZUL_TABELA, True)
    add_text(
        slide,
        programa.get("objetivo") or "Objetivo do programa não informado.",
        1.32, 1.25, 11.4, 0.72,
        10.5, TEXTO_ESCURO
    )

    # ABRANGÊNCIA
    add_card(slide, 0.30, 2.00, 12.75, 2.80)
    add_icon(slide, "globo.png", 0.47, 2.10, 0.58)

    add_text(slide, "ABRANGÊNCIA", 1.32, 2.18, 3, 0.25, 13, AZUL_TABELA, True)

    tx = slide.shapes.add_textbox(
        Inches(1.32),
        Inches(2.48),
        Inches(11.3),
        Inches(0.35)
    )

    tf = tx.text_frame
    tf.clear()

    p = tf.paragraphs[0]
    p.font.name = FONTE_TEXTO
    p.font.size = Pt(10)
    p.font.color.rgb = TEXTO_ESCURO

    r = p.add_run()
    r.text = "O programa está presente em "

    r = p.add_run()
    r.text = f"{programa['regioes_atendidas']} regiões do Estado"
    r.font.bold = True

    r = p.add_run()
    r.text = ", abrangendo "

    r = p.add_run()
    r.text = f"{programa['unidades_atendidas']} unidades operacionais"
    r.font.bold = True

    r = p.add_run()
    r.text = " e ofertando "

    r = p.add_run()
    r.text = f"{programa['modalidades_qtd']} modalidade(s)"
    r.font.bold = True

    r = p.add_run()
    r.text = " de educação profissional."

    # Coluna regiões
    add_icon(slide, "mapa.png", 0.47, 2.82, 0.58)
    add_text(slide, "REGIÕES", 1.32, 2.98, 2.5, 0.25, 11, AZUL_TABELA, True)
    add_text(slide, criar_lista_texto(programa.get("regioes")), 1.32, 3.22, 2.70, 1.45, 8.1, TEXTO_ESCURO)

    # Divisor 1
    linha = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(4.45), Inches(2.95), Inches(0.01), Inches(1.65)
    )
    linha.fill.solid()
    linha.fill.fore_color.rgb = RGBColor(226, 232, 240)
    linha.line.fill.background()

    # Divisor 2
    linha = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(8.55), Inches(2.95), Inches(0.01), Inches(1.65)
    )
    linha.fill.solid()
    linha.fill.fore_color.rgb = RGBColor(226, 232, 240)
    linha.line.fill.background()

    # Coluna modalidades
    add_icon(slide, "livro.png", 4.70, 2.82, 0.58)

    add_text(
        slide,
        "MODALIDADES",
        5.55,
        2.98,
        2.6,
        0.25,
        11,
        AZUL_TABELA,
        True
    )

    add_text(
        slide,
        criar_lista_texto(programa.get("modalidades")),
        5.55,
        3.22,
        2.80,
        1.45,
        8.1,
        TEXTO_ESCURO
    )

    # Coluna tipo de financiamento
    add_icon(slide, "financiamento.png", 8.75, 2.82, 0.58)

    add_text(
        slide,
        "TIPO DE FINANCIAMENTO",
        9.60,
        2.98,
        3.0,
        0.25,
        11,
        AZUL_TABELA,
        True
    )

    add_text(
        slide,
        criar_lista_texto(programa.get("tipo_financiamento")),
        9.60,
        3.22,
        2.60,
        1.45,
        8.1,
        TEXTO_ESCURO
    )

    # INTERLOCUTOR
    add_card(slide, 0.30, 4.90, 12.75, 0.70)

    add_icon(slide, "usuario.png", 0.47, 4.92, 0.58)
    add_text(slide, "INTERLOCUTOR", 1.32, 5.08, 3.0, 0.22, 12, AZUL_TABELA, True)
    add_text(slide, programa.get("interlocutor") or "—", 1.32, 5.34, 6.0, 0.22, 9.5, TEXTO_ESCURO)

    # INDICADORES DO PROGRAMA
    add_text(
        slide,
        "INDICADORES DO PROGRAMA",
        0.30, 5.78, 4.0, 0.22,
        11, AZUL_TABELA, True
    )

    tabela = slide.shapes.add_table(
        4,
        4,
        Inches(0.30),
        Inches(6.08),
        Inches(12.75),
        Inches(1.02)
    ).table

    cabecalho = ["Indicador", "Realizado", "Meta até o momento", "Meta anual"]

    for c, texto in enumerate(cabecalho):
        cell = tabela.cell(0, c)
        cell.text = texto
        cell.fill.solid()
        cell.fill.fore_color.rgb = AZUL_TABELA
        cell.vertical_anchor = 3

        for p in cell.text_frame.paragraphs:
            p.font.name = FONTE_TEXTO
            p.font.size = Pt(8)
            p.font.bold = True
            p.font.color.rgb = BRANCO
            p.alignment = PP_ALIGN.CENTER

    def fmt_num(v):
        return f"{float(v or 0):,.0f}".replace(",", ".")

    def fmt_moeda(v):
        return f"R$ {float(v or 0):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

    linhas = [
        [
            "Matrículas",
            fmt_num(programa.get("matriculas_realizado")),
            fmt_num(programa.get("matriculas_meta_atual")),
            fmt_num(programa.get("matriculas_meta_ano")),
        ],
        [
            "Hora-aluno",
            fmt_num(programa.get("ha_realizado")),
            fmt_num(programa.get("ha_meta_atual")),
            fmt_num(programa.get("ha_meta_ano")),
        ],
        [
            "Receita",
            fmt_moeda(programa.get("receita_realizado")),
            fmt_moeda(programa.get("receita_meta_atual")),
            fmt_moeda(programa.get("receita_meta_ano")),
        ],
    ]

    for r, linha in enumerate(linhas, start=1):
        for c, texto in enumerate(linha):
            cell = tabela.cell(r, c)
            cell.text = texto
            cell.fill.solid()
            cell.fill.fore_color.rgb = BRANCO

            for p in cell.text_frame.paragraphs:
                p.font.name = FONTE_TEXTO
                p.font.size = Pt(8)
                p.font.color.rgb = TEXTO_ESCURO
                p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER

                if c == 0:
                    p.font.bold = True

def criar_card_numero(slide, titulo, valor, x, y):
    card = slide.shapes.add_shape(
        1,
        Inches(x),
        Inches(y),
        Inches(1.75),
        Inches(0.85)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = LINHA_ZEBRA
    card.line.color.rgb = RGBColor(226, 232, 240)

    box = slide.shapes.add_textbox(Inches(x + 0.12), Inches(y + 0.12), Inches(1.5), Inches(0.25))
    p = box.text_frame.paragraphs[0]
    p.text = titulo
    p.font.name = FONTE_TEXTO
    p.font.size = Pt(8)
    p.font.bold = True
    p.font.color.rgb = CINZA_SUBTITULO

    box = slide.shapes.add_textbox(Inches(x + 0.12), Inches(y + 0.38), Inches(1.5), Inches(0.35))
    p = box.text_frame.paragraphs[0]
    p.text = f"{int(valor or 0):,}".replace(",", ".")
    p.font.name = FONTE_TITULO
    p.font.size = Pt(18)
    p.font.color.rgb = AZUL_TITULO

def add_text_nowrap(slide, text, x, y, w, h, size=10, color=TEXTO_ESCURO, bold=False, font=FONTE_TEXTO):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = False
    tf.auto_size = None

    p = tf.paragraphs[0]
    p.text = str(text or "")
    p.font.name = font
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color

    return box

def criar_slide_interlocutores(prs, dados):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    barra = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.75)
    )
    barra.fill.solid()
    barra.fill.fore_color.rgb = AZUL_TABELA
    barra.line.fill.background()

    adicionar_logo(slide)

    add_text(
        slide, "PROGRAMAS x INTERLOCUTORES",
        0.35, 0.18, 9.0, 0.42,
        25, BRANCO, True, FONTE_TITULO
    )

    def nome_programa_chave(nome):
        nome = str(nome or "").strip().upper()
        nome = " ".join(nome.split())

        nome_sem_acento = unicodedata.normalize("NFKD", nome)
        nome_sem_acento = "".join(c for c in nome_sem_acento if not unicodedata.combining(c))

        if nome_sem_acento in ("RS QUALIFICACAO", "RS QUALIFICACAO RECOMECAR"):
            return "RS QUALIFICACAO"

        if nome_sem_acento in ("SEJA PRO+", "SEJA PRÓ+"):
            return "SEJA PRO+"

        return nome_sem_acento

    agrupado = {}
    for item in dados:
        nome = item["interlocutor"]
        agrupado.setdefault(nome, {"pago": [], "gr": [], "gnr": []})
        programa_nome = item["nome_programa"]
        programa_chave = nome_programa_chave(programa_nome)

        ja_existe = any(
            nome_programa_chave(p) == programa_chave
            for p in agrupado[nome][item["grupo"]]
        )

        if not ja_existe:
            agrupado[nome][item["grupo"]].append(programa_nome)

    interlocutores = list(agrupado.items())[:5]

    cores = [
        RGBColor(24, 121, 45),
        AZUL_TABELA,
        RGBColor(0, 113, 145),
        RGBColor(80, 35, 140),
        RGBColor(204, 132, 0),
    ]

    largura_card = 2.45
    espacamento = 0.14
    x_inicial = 0.25
    y_card = 1.02

    for idx, (nome, grupos) in enumerate(interlocutores):
        x = x_inicial + idx * (largura_card + espacamento)
        cor = cores[idx % len(cores)]

        add_card(slide, x, y_card, largura_card, 5.12)

        topo = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(x), Inches(y_card),
            Inches(largura_card), Inches(1.25)
        )
        topo.fill.solid()
        topo.fill.fore_color.rgb = cor
        topo.line.fill.background()

        programas_distintos = set()

        for grupo_lista in grupos.values():
            for programa_nome in grupo_lista:
                programas_distintos.add(nome_programa_chave(programa_nome))

        qtd = len(programas_distintos)

        add_text_nowrap(slide, nome.upper(), x + 0.16, y_card + 0.52, largura_card - 0.32, 0.22, 8.2, BRANCO, True)
        add_text(slide, f"{qtd} programa{'s' if qtd != 1 else ''}", x + 0.16, y_card + 0.82, largura_card - 0.32, 0.22, 7.5, BRANCO, True)

        y = y_card + 1.45

        def bloco(titulo, programas, icone, cor_bloco, y):
            if not programas:
                return y

            add_icon(slide, icone, x + 0.15, y, 0.34)
            add_text(slide, titulo, x + 0.52, y + 0.05, largura_card - 0.62, 0.22, 7.3, cor_bloco, True)

            y += 0.36

            for p_nome in programas:
                add_text(slide, f"• {p_nome}", x + 0.52, y, largura_card - 0.62, 0.14, 5.1, TEXTO_ESCURO)
                y += 0.135

            y += 0.07
            return y

        y = bloco("GRATUIDADE REGIMENTAL", grupos["gr"], "gr.png", RGBColor(24, 121, 45), y)
        y = bloco("GRATUIDADE NÃO REGIMENTAL", grupos["gnr"], "gnr.png", RGBColor(80, 35, 140), y)
        y = bloco("PAGO", grupos["pago"], "pg.png", AZUL_TABELA, y)

    add_card(slide, 0.25, 6.33, 12.80, 0.72)

    desenhar_legenda_financiamento(
        slide, "PAGO",
        "Programas com cobrança de mensalidade ou contraprestação financeira.",
        AZUL_TABELA,
        "pg.png",
        0.65, 6.43
    )

    desenhar_legenda_financiamento(
        slide, "GRATUIDADE REGIMENTAL",
        "Programas ofertados gratuitamente conforme previsão da gratuidade regimental.",
        RGBColor(24, 121, 45),
        "gr.png",
        4.85, 6.43
    )

    desenhar_legenda_financiamento(
        slide, "GRATUIDADE NÃO REGIMENTAL",
        "Programas gratuitos não enquadrados na gratuidade regimental.",
        RGBColor(80, 35, 140),
        "gnr.png",
        9.15, 6.43
    )

def criar_slide_final(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    if SLIDE_FINAL.exists():
        slide.shapes.add_picture(
            str(SLIDE_FINAL),
            0,
            0,
            width=prs.slide_width,
            height=prs.slide_height
        )