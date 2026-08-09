def _pct(realizado, meta):
    return (realizado / meta * 100) if meta else 0

def _situacao_indicador(realizado, meta):
    realizado = float(realizado or 0)
    meta = float(meta or 0)

    if meta == 0 and realizado == 0:
        return "nao_aplicavel"

    if meta == 0 and realizado > 0:
        return "sem_meta"

    if meta > 0 and realizado == 0:
        return "sem_execucao"

    return "com_meta"


def _texto_atingimento(realizado, meta):
    situacao = _situacao_indicador(realizado, meta)

    if situacao == "nao_aplicavel":
        return "não aplicável"

    if situacao == "sem_meta":
        return "sem meta definida"

    if situacao == "sem_execucao":
        return "sem execução no período"

    return f"{_pct(realizado, meta):.1f}%"

def _contexto_relatorio(filtros):
    partes = []

    if filtros.programa:
        partes.append(f"programa {filtros.programa}")

    if filtros.regiao:
        partes.append(f"região {filtros.regiao}")

    if filtros.subregiao:
        partes.append(f"sub-região {filtros.subregiao}")

    if filtros.uo:
        partes.append(f"UO {filtros.uo}")

    if partes:
        return " com foco no " + ", ".join(partes)

    return " em âmbito estadual"

def _recomendacao_indicador(nome, realizado, meta):
    pct = _pct(realizado, meta)
    situacao = _situacao_indicador(realizado, meta)

    if situacao == "nao_aplicavel":
        return f"Manter {nome} como indicador informativo neste recorte, pois não há meta nem execução registrada no período."

    if situacao == "sem_meta":
        return f"Avaliar o cadastro de meta para {nome}, permitindo acompanhamento comparativo nos próximos relatórios."

    if situacao == "sem_execucao":
        return f"Verificar a ausência de execução de {nome} frente à meta cadastrada no período analisado."

    if pct >= 100:
        return f"Consolidar as práticas que contribuíram para o atingimento superior da meta de {nome}."

    if pct >= 75:
        return f"Manter acompanhamento periódico de {nome}, pois o indicador está próximo do alcance integral da meta."

    return f"Priorizar plano de ação para recuperação de {nome}, considerando o desempenho abaixo do esperado."

def _pontuacao_indicador(realizado, meta):
    """
    Retorna a pontuação do indicador conforme o percentual
    de atingimento da meta.

    3 pontos: 100% ou mais
    2 pontos: de 75% a 99,99%
    1 ponto: de 51% a 74,99%
    0 ponto: abaixo de 51%
    None: indicador sem meta
    """

    realizado = float(realizado or 0)
    meta = float(meta or 0)

    if meta <= 0:
        return None

    percentual = (realizado / meta) * 100

    if percentual >= 100:
        return 3

    if percentual >= 75:
        return 2

    if percentual >= 51:
        return 1

    return 0


def _classificar_score_unidade(
    score,
    score_maximo
):
    """
    Classifica o desempenho da unidade proporcionalmente
    ao total máximo de pontos possível.
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
        classificacao = (
            "Desempenho de Excelência"
        )
        nivel = "excelencia"

    elif percentual_score >= 65:
        classificacao = (
            "Desempenho Satisfatório"
        )
        nivel = "satisfatorio"

    elif percentual_score >= 40:
        classificacao = (
            "Desempenho Regular"
        )
        nivel = "regular"

    else:
        classificacao = (
            "Desempenho Crítico"
        )
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
    Analisa um indicador de determinada modalidade e gera
    sua interpretação textual.
    """

    modalidade = (
        str(modalidade).strip()
        if modalidade
        else "Modalidade não informada"
    )

    realizado = float(realizado or 0)
    meta = float(meta or 0)

    nomes_indicadores = {
        "matriculas": "matrículas",
        "hora_aluno": "hora-aluno",
        "receita": "receita"
    }

    nome_indicador = nomes_indicadores.get(
        indicador,
        indicador
    )

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
                f"Na modalidade {modalidade}, o indicador de "
                f"{nome_indicador} não possui meta nem execução "
                f"registrada no período analisado."
            )
        }

    # ======================================================
    # EXECUÇÃO SEM META
    # ======================================================

    if meta <= 0 and realizado > 0:
        return {
            "modalidade": modalidade,
            "indicador": indicador,
            "realizado": realizado,
            "meta": meta,
            "atingimento": None,
            "pontuacao": None,
            "status": "sem_meta",
            "texto": (
                f"Na modalidade {modalidade}, houve execução de "
                f"{nome_indicador}, porém não existe meta definida "
                f"para comparação."
            )
        }

    atingimento = (
        realizado / meta
    ) * 100

    pontuacao = _pontuacao_indicador(
        realizado,
        meta
    )

    # ======================================================
    # META ATINGIDA
    # ======================================================

    if atingimento >= 100:
        status = "meta_atingida"

        if indicador == "matriculas":
            texto = (
                f"A modalidade {modalidade} atingiu "
                f"{atingimento:.1f}% da meta de matrículas, "
                f"demonstrando desempenho superior ao planejado."
            )

        elif indicador == "hora_aluno":
            texto = (
                f"A modalidade {modalidade} atingiu "
                f"{atingimento:.1f}% da meta de hora-aluno, "
                f"evidenciando execução da carga horária acima "
                f"do planejamento."
            )

        elif indicador == "receita":
            texto = (
                f"A modalidade {modalidade} atingiu "
                f"{atingimento:.1f}% da meta de receita, "
                f"apresentando resultado financeiro superior "
                f"ao planejado."
            )

        else:
            texto = (
                f"A modalidade {modalidade} atingiu "
                f"{atingimento:.1f}% da meta de "
                f"{nome_indicador}."
            )

    # ======================================================
    # PRÓXIMO DA META
    # ======================================================

    elif atingimento >= 75:
        status = "no_caminho"

        if indicador == "matriculas":
            texto = (
                f"A modalidade {modalidade} alcançou "
                f"{atingimento:.1f}% da meta de matrículas e "
                f"encontra-se próxima do resultado planejado."
            )

        elif indicador == "hora_aluno":
            texto = (
                f"A modalidade {modalidade} alcançou "
                f"{atingimento:.1f}% da meta de hora-aluno, "
                f"mantendo desempenho próximo do esperado."
            )

        elif indicador == "receita":
            texto = (
                f"A modalidade {modalidade} alcançou "
                f"{atingimento:.1f}% da meta de receita, "
                f"permanecendo em faixa de acompanhamento."
            )

        else:
            texto = (
                f"A modalidade {modalidade} alcançou "
                f"{atingimento:.1f}% da meta de "
                f"{nome_indicador}."
            )

    # ======================================================
    # ATENÇÃO
    # ======================================================

    elif atingimento >= 51:
        status = "atencao"

        if indicador == "matriculas":
            texto = (
                f"A modalidade {modalidade} alcançou somente "
                f"{atingimento:.1f}% da meta de matrículas, "
                f"indicando necessidade de reforço nas ações "
                f"de captação e conversão."
            )

        elif indicador == "hora_aluno":
            texto = (
                f"A modalidade {modalidade} alcançou "
                f"{atingimento:.1f}% da meta de hora-aluno, "
                f"exigindo acompanhamento da execução das "
                f"turmas e cargas horárias."
            )

        elif indicador == "receita":
            texto = (
                f"A modalidade {modalidade} alcançou "
                f"{atingimento:.1f}% da meta de receita, "
                f"indicando atenção ao desempenho financeiro."
            )

        else:
            texto = (
                f"A modalidade {modalidade} alcançou "
                f"{atingimento:.1f}% da meta de "
                f"{nome_indicador}."
            )

    # ======================================================
    # CRÍTICO
    # ======================================================

    else:
        status = "critico"

        if indicador == "matriculas":
            texto = (
                f"A modalidade {modalidade} atingiu apenas "
                f"{atingimento:.1f}% da meta de matrículas, "
                f"configurando desempenho crítico e demandando "
                f"ações prioritárias de recuperação."
            )

        elif indicador == "hora_aluno":
            texto = (
                f"A modalidade {modalidade} atingiu apenas "
                f"{atingimento:.1f}% da meta de hora-aluno, "
                f"indicando baixa execução da carga horária "
                f"planejada."
            )

        elif indicador == "receita" and realizado <= 0:
            texto = (
                f"A modalidade {modalidade} possui meta de "
                f"receita definida, mas não apresentou execução "
                f"financeira no período, configurando situação "
                f"crítica."
            )

        elif indicador == "receita":
            texto = (
                f"A modalidade {modalidade} atingiu apenas "
                f"{atingimento:.1f}% da meta de receita, "
                f"configurando desempenho financeiro crítico."
            )

        else:
            texto = (
                f"A modalidade {modalidade} atingiu apenas "
                f"{atingimento:.1f}% da meta de "
                f"{nome_indicador}."
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
    Consolida a análise da Unidade Operacional, calcula o
    score e gera resumo executivo e conclusão automática.
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
    # MODALIDADES
    # ======================================================

    modalidades = set()

    for grupo in (
        matriculas,
        hora_aluno,
        receita
    ):
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
    # ANÁLISES DOS INDICADORES
    # ======================================================

    analises_matriculas = [
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
        for item in matriculas
    ]

    analises_hora_aluno = [
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
        for item in hora_aluno
    ]

    analises_receita = [
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
        for item in receita
    ]

    todas_analises = (
        analises_matriculas
        + analises_hora_aluno
        + analises_receita
    )

    # ======================================================
    # SCORE
    # ======================================================

    pontuacoes_validas = [
        item["pontuacao"]
        for item in todas_analises
        if item.get("pontuacao") is not None
    ]

    score = sum(pontuacoes_validas)
    score_maximo = len(
        pontuacoes_validas
    ) * 3

    classificacao = _classificar_score_unidade(
        score,
        score_maximo
    )

    # ======================================================
    # CONTAGEM DOS STATUS
    # ======================================================

    resumo_status = {
        "meta_atingida": 0,
        "no_caminho": 0,
        "atencao": 0,
        "critico": 0,
        "sem_meta": 0,
        "sem_dados": 0
    }

    for item in todas_analises:
        status = item.get("status")

        if status in resumo_status:
            resumo_status[status] += 1

    # ======================================================
    # MÉDIAS DE ATINGIMENTO
    # ======================================================

    def calcular_media(itens):
        valores = [
            float(item["atingimento"])
            for item in itens
            if item.get("atingimento") is not None
        ]

        if not valores:
            return None

        return sum(valores) / len(valores)

    media_matriculas = calcular_media(
        analises_matriculas
    )

    media_hora_aluno = calcular_media(
        analises_hora_aluno
    )

    media_receita = calcular_media(
        analises_receita
    )

    # ======================================================
    # RESUMO EXECUTIVO
    # ======================================================

    resumo_executivo = (
        f"No período analisado, a unidade {nome_uo} apresentou "
        f"resultados em {qtd_modalidades} modalidade"
        f"{'s' if qtd_modalidades != 1 else ''} do programa "
        f"{programa}. A avaliação considera o desempenho de "
        f"matrículas, hora-aluno e receita em relação às metas "
        f"estabelecidas para o período."
    )

    # ======================================================
    # CONCLUSÃO
    # ======================================================

    nivel = classificacao["nivel"]

    if nivel == "excelencia":
        conclusao = (
            "A unidade apresentou desempenho de excelência, "
            "com elevada aderência às metas estabelecidas."
        )

    elif nivel == "satisfatorio":
        conclusao = (
            "A unidade apresentou desempenho satisfatório, "
            "com parte significativa dos indicadores próxima "
            "ou acima das metas estabelecidas."
        )

    elif nivel == "regular":
        conclusao = (
            "A unidade apresentou desempenho regular, com "
            "resultados heterogêneos e necessidade de "
            "acompanhamento dos indicadores abaixo da meta."
        )

    elif nivel == "critico":
        conclusao = (
            "A unidade apresentou desempenho crítico, com "
            "indicadores relevantes abaixo das metas. "
            "Recomenda-se priorizar ações corretivas."
        )

    else:
        conclusao = (
            "Não foi possível estabelecer uma classificação "
            "completa devido à ausência de metas suficientes."
        )

    complementos = []

    if resumo_status["meta_atingida"] > 0:
        quantidade = resumo_status[
            "meta_atingida"
        ]

        complementos.append(
            f"{quantidade} indicador"
            f"{'es atingiram' if quantidade != 1 else ' atingiu'} "
            f"ou superaram as metas."
        )

    if resumo_status["critico"] > 0:
        quantidade = resumo_status["critico"]

        complementos.append(
            f"{quantidade} indicador"
            f"{'es demandam' if quantidade != 1 else ' demanda'} "
            f"acompanhamento prioritário."
        )

    elif resumo_status["atencao"] > 0:
        quantidade = resumo_status["atencao"]

        complementos.append(
            f"{quantidade} indicador"
            f"{'es permanecem' if quantidade != 1 else ' permanece'} "
            f"em nível de atenção."
        )

    if (
        media_matriculas is not None
        and media_receita is not None
        and media_matriculas >= 75
        and media_receita < 51
    ):
        complementos.append(
            "Embora as matrículas apresentem desempenho "
            "operacional relevante, a receita permanece em "
            "nível crítico, indicando possível desalinhamento "
            "entre execução educacional e financeira."
        )

    if (
        media_matriculas is not None
        and media_hora_aluno is not None
        and abs(
            media_matriculas
            - media_hora_aluno
        ) >= 30
    ):
        complementos.append(
            "Há diferença relevante entre matrículas e "
            "hora-aluno, recomendando-se verificar o andamento "
            "das turmas e a execução das cargas horárias."
        )

    if complementos:
        conclusao += " " + " ".join(
            complementos[:4]
        )

    # ======================================================
    # RETORNO
    # ======================================================

    return {
        "uo": nome_uo,
        "programa": programa,
        "qtd_modalidades": qtd_modalidades,

        "resumo_executivo": resumo_executivo,

        "matriculas": analises_matriculas,
        "hora_aluno": analises_hora_aluno,
        "receita": analises_receita,

        "score": score,
        "score_maximo": score_maximo,

        "percentual_score": classificacao[
            "percentual_score"
        ],

        "classificacao": classificacao[
            "classificacao"
        ],

        "nivel": classificacao["nivel"],

        "resumo_status": resumo_status,

        "medias_atingimento": {
            "matriculas": media_matriculas,
            "hora_aluno": media_hora_aluno,
            "receita": media_receita
        },

        "conclusao": conclusao
    }

async def montar_preview_relatorio_executivo(conn, filtros, opcoes):
    meses = filtros.meses or list(range(1, 13))

    params = [filtros.ano]
    filtros_oferta = ["o.ano = $1"]

    params.append(meses)
    idx_mes = len(params)

    filtro_mes_real = f"AND rp.mes = ANY(${idx_mes}::int[])"

    idx_programa = None
    idx_subregiao = None
    idx_regiao = None
    idx_uo = None
    foco_programa = bool(filtros.programa)
    foco_regiao = bool(filtros.regiao)
    foco_subregiao = bool(filtros.subregiao)
    foco_uo = bool(filtros.uo)

    if foco_uo:
        modo_relatorio = "uo"

    elif foco_programa and foco_subregiao:
        modo_relatorio = "programa_subregiao"

    elif foco_programa and foco_regiao:
        modo_relatorio = "programa_regiao"

    elif foco_subregiao:
        modo_relatorio = "subregiao"

    elif foco_regiao:
        modo_relatorio = "regiao"

    elif foco_programa:
        modo_relatorio = "programa"

    else:
        modo_relatorio = "geral"

    if filtros.programa:
        params.append(filtros.programa)
        idx_programa = len(params)

        filtros_oferta.append(
            f"""
            EXISTS (
                SELECT 1
                FROM programas p
                WHERE p.codigo = o.cod_programa
                AND UPPER(TRIM(p.nome_programa)) = UPPER(TRIM(${idx_programa}))
            )
            """
        )

    if filtros.subregiao and not foco_uo:
        params.append(filtros.subregiao)
        idx_subregiao = len(params)

        filtros_oferta.append(
            f"""
            EXISTS (
                SELECT 1
                FROM uo u2
                JOIN subregioes s2 ON s2.codigo = u2.cod_subregiao
                WHERE u2.codigo = o.cod_uo
                AND UPPER(TRIM(s2.nome)) = UPPER(TRIM(${idx_subregiao}))
            )
            """
        )

    if filtros.regiao and not foco_uo:
        params.append(filtros.regiao)
        idx_regiao = len(params)

        filtros_oferta.append(
            f"""
            EXISTS (
                SELECT 1
                FROM uo u3
                JOIN subregioes s3 ON s3.codigo = u3.cod_subregiao
                JOIN regioes r3 ON r3.codigo = s3.codigo_regiao
                WHERE u3.codigo = o.cod_uo
                AND UPPER(TRIM(r3.nome)) = UPPER(TRIM(${idx_regiao}))
            )
            """
        )

    if filtros.uo:
        params.append(filtros.uo)
        idx_uo = len(params)

        filtros_oferta.append(
            f"""
            EXISTS (
                SELECT 1
                FROM uo u4
                WHERE u4.codigo = o.cod_uo
                AND UPPER(TRIM(u4.nome)) = UPPER(TRIM(${idx_uo}))
            )
            """
        )

    where_oferta = " AND ".join(filtros_oferta)

    filtros_planejamento = [
        "ps.flag_valida IS DISTINCT FROM FALSE",
        "ps.tipo = 'META'",
    ]

    if filtros.programa:
        filtros_planejamento.append(
            f"UPPER(TRIM(ps.programa_raw)) = UPPER(TRIM(${idx_programa}))"
        )

    if filtros.subregiao and not foco_uo:
        filtros_planejamento.append(
            f"UPPER(TRIM(ps.subregiao)) = UPPER(TRIM(${idx_subregiao}))"
        )

    if filtros.regiao and not foco_uo:
        filtros_planejamento.append(
            f"UPPER(TRIM(ps.regiao)) = UPPER(TRIM(${idx_regiao}))"
        )

    if filtros.uo:
        filtros_planejamento.append(
            f"""
            EXISTS (
                SELECT 1
                FROM uo u_meta
                WHERE u_meta.codigo::text = ps.cod_uo_raw::text
                AND UPPER(TRIM(u_meta.nome)) = UPPER(TRIM(${idx_uo}))
            )
            """
        )

    where_planejamento = " AND ".join(filtros_planejamento)

    meta_periodo = """
        CASE WHEN 1 = ANY($2::int[]) THEN COALESCE(jan,0) ELSE 0 END +
        CASE WHEN 2 = ANY($2::int[]) THEN COALESCE(fev,0) ELSE 0 END +
        CASE WHEN 3 = ANY($2::int[]) THEN COALESCE(mar,0) ELSE 0 END +
        CASE WHEN 4 = ANY($2::int[]) THEN COALESCE(abr,0) ELSE 0 END +
        CASE WHEN 5 = ANY($2::int[]) THEN COALESCE(mai,0) ELSE 0 END +
        CASE WHEN 6 = ANY($2::int[]) THEN COALESCE(jun,0) ELSE 0 END +
        CASE WHEN 7 = ANY($2::int[]) THEN COALESCE(jul,0) ELSE 0 END +
        CASE WHEN 8 = ANY($2::int[]) THEN COALESCE(ago,0) ELSE 0 END +
        CASE WHEN 9 = ANY($2::int[]) THEN COALESCE(set_,0) ELSE 0 END +
        CASE WHEN 10 = ANY($2::int[]) THEN COALESCE(out_,0) ELSE 0 END +
        CASE WHEN 11 = ANY($2::int[]) THEN COALESCE(nov,0) ELSE 0 END +
        CASE WHEN 12 = ANY($2::int[]) THEN COALESCE(dez,0) ELSE 0 END
    """

    sql = f"""
    WITH ofertas_base AS (
        SELECT DISTINCT
            o.codigo,
            o.cod_programa,
            o.cod_financiamento,
            o.cod_uo
        FROM ofertas_programas o
        WHERE {where_oferta}
    ),

    ultimo_lote_planejamento AS (
        SELECT MAX(ps.lote_id) AS lote_id
        FROM planejamento_staging ps
        JOIN planejamento_import_lotes pil
            ON pil.id = ps.lote_id
        WHERE ps.flag_valida IS DISTINCT FROM FALSE
        AND ps.tipo = 'META'
        AND CAST(pil.ano_referencia AS integer) = $1
    ),

    realizado AS (
        SELECT
            COALESCE(SUM(rp.matriculas_real), 0) AS matriculas_real,
            COALESCE(SUM(rp.ha_real), 0) AS ha_real,
            COALESCE(SUM(rp.receita_real), 0) AS receita_real
        FROM realizado_programas rp
        JOIN ofertas_base ob
            ON ob.codigo = rp.cod_oferta
        WHERE rp.ano = $1
        {filtro_mes_real}
    ),

    meta AS (
        SELECT

            COALESCE(
                SUM({meta_periodo}) FILTER (
                
                
                    WHERE UPPER(TRIM(ps.conta)) = 'MATRÍCULAS'
                ),
                0
            ) AS matriculas_meta,

            COALESCE(
                SUM({meta_periodo}) FILTER (
                    WHERE UPPER(TRIM(ps.conta)) = 'HORA-ALUNO'
                ),
                0
            ) AS ha_meta,

            COALESCE(
                SUM({meta_periodo}) FILTER (
                    WHERE UPPER(TRIM(ps.conta)) = 'RECEITAS CORRENTES'
                ),
                0
            ) AS receita_meta

        FROM planejamento_staging ps

        JOIN ultimo_lote_planejamento ul
            ON ul.lote_id = ps.lote_id

        WHERE {where_planejamento}
    ),

    turmas AS (
        SELECT
            COUNT(DISTINCT t.codigo_sge) AS total_turmas
        FROM turmas t
        JOIN ofertas_base ob
            ON ob.cod_programa = t.cod_programa
        AND ob.cod_uo = t.cod_uo
        WHERE (
            t.ano_referencia = $1
            OR EXTRACT(YEAR FROM t.data_inicio)::int = $1
            OR EXTRACT(YEAR FROM t.data_ini_contratoapr)::int = $1
        )
        AND t.data_inicio >= make_date(
                $1,
                (SELECT MIN(x) FROM unnest(${idx_mes}::int[]) x),
                1
        )
        AND t.data_inicio < (
                make_date(
                    $1,
                    (SELECT MAX(x) FROM unnest(${idx_mes}::int[]) x),
                    1
                ) + interval '1 month'
        )
    )

    SELECT
        realizado.matriculas_real,
        realizado.ha_real,
        realizado.receita_real,
        meta.matriculas_meta,
        meta.ha_meta,
        meta.receita_meta,
        turmas.total_turmas
    FROM realizado, meta, turmas
    """

    row = await conn.fetchrow(sql, *params)

    matriculas_real = float(row["matriculas_real"] or 0)
    matriculas_meta = float(row["matriculas_meta"] or 0)

    ha_real = float(row["ha_real"] or 0)
    ha_meta = float(row["ha_meta"] or 0)

    receita_real = float(row["receita_real"] or 0)
    receita_meta = float(row["receita_meta"] or 0)

    turmas_total = int(row["total_turmas"] or 0)

    sql_evolucao = f"""
        WITH ofertas_base AS (
            SELECT DISTINCT
                o.codigo
            FROM ofertas_programas o
            WHERE {where_oferta}
        ),

        ultimo_lote_planejamento AS (
            SELECT MAX(ps.lote_id) AS lote_id
            FROM planejamento_staging ps
            JOIN planejamento_import_lotes pil
                ON pil.id = ps.lote_id
            WHERE ps.flag_valida IS DISTINCT FROM FALSE
            AND ps.tipo = 'META'
            AND CAST(pil.ano_referencia AS integer) = $1
        ),

        realizado_mes AS (
            SELECT
                rp.mes,
                COALESCE(SUM(rp.matriculas_real), 0) AS matriculas_real,
                COALESCE(SUM(rp.ha_real), 0) AS ha_real,
                COALESCE(SUM(rp.receita_real), 0) AS receita_real
            FROM realizado_programas rp
            JOIN ofertas_base ob
                ON ob.codigo = rp.cod_oferta
            WHERE rp.ano = $1
            AND rp.mes = ANY($2::int[])
            GROUP BY rp.mes
        ),

        meta_mes AS (
            SELECT
                m.mes,

                COALESCE(
                    SUM(
                        CASE
                            WHEN UPPER(TRIM(ps.conta)) = 'MATRÍCULAS' THEN
                                CASE m.mes
                                    WHEN 1 THEN COALESCE(ps.jan, 0)
                                    WHEN 2 THEN COALESCE(ps.fev, 0)
                                    WHEN 3 THEN COALESCE(ps.mar, 0)
                                    WHEN 4 THEN COALESCE(ps.abr, 0)
                                    WHEN 5 THEN COALESCE(ps.mai, 0)
                                    WHEN 6 THEN COALESCE(ps.jun, 0)
                                    WHEN 7 THEN COALESCE(ps.jul, 0)
                                    WHEN 8 THEN COALESCE(ps.ago, 0)
                                    WHEN 9 THEN COALESCE(ps.set_, 0)
                                    WHEN 10 THEN COALESCE(ps.out_, 0)
                                    WHEN 11 THEN COALESCE(ps.nov, 0)
                                    WHEN 12 THEN COALESCE(ps.dez, 0)
                                    ELSE 0
                                END
                            ELSE 0
                        END
                    ),
                    0
                ) AS matriculas_meta,

                COALESCE(
                    SUM(
                        CASE
                            WHEN UPPER(TRIM(ps.conta)) = 'HORA-ALUNO' THEN
                                CASE m.mes
                                    WHEN 1 THEN COALESCE(ps.jan, 0)
                                    WHEN 2 THEN COALESCE(ps.fev, 0)
                                    WHEN 3 THEN COALESCE(ps.mar, 0)
                                    WHEN 4 THEN COALESCE(ps.abr, 0)
                                    WHEN 5 THEN COALESCE(ps.mai, 0)
                                    WHEN 6 THEN COALESCE(ps.jun, 0)
                                    WHEN 7 THEN COALESCE(ps.jul, 0)
                                    WHEN 8 THEN COALESCE(ps.ago, 0)
                                    WHEN 9 THEN COALESCE(ps.set_, 0)
                                    WHEN 10 THEN COALESCE(ps.out_, 0)
                                    WHEN 11 THEN COALESCE(ps.nov, 0)
                                    WHEN 12 THEN COALESCE(ps.dez, 0)
                                    ELSE 0
                                END
                            ELSE 0
                        END
                    ),
                    0
                ) AS ha_meta,

                COALESCE(
                    SUM(
                        CASE
                            WHEN UPPER(TRIM(ps.conta)) = 'RECEITAS CORRENTES' THEN
                                CASE m.mes
                                    WHEN 1 THEN COALESCE(ps.jan, 0)
                                    WHEN 2 THEN COALESCE(ps.fev, 0)
                                    WHEN 3 THEN COALESCE(ps.mar, 0)
                                    WHEN 4 THEN COALESCE(ps.abr, 0)
                                    WHEN 5 THEN COALESCE(ps.mai, 0)
                                    WHEN 6 THEN COALESCE(ps.jun, 0)
                                    WHEN 7 THEN COALESCE(ps.jul, 0)
                                    WHEN 8 THEN COALESCE(ps.ago, 0)
                                    WHEN 9 THEN COALESCE(ps.set_, 0)
                                    WHEN 10 THEN COALESCE(ps.out_, 0)
                                    WHEN 11 THEN COALESCE(ps.nov, 0)
                                    WHEN 12 THEN COALESCE(ps.dez, 0)
                                    ELSE 0
                                END
                            ELSE 0
                        END
                    ),
                    0
                ) AS receita_meta

            FROM generate_series(1, 12) m(mes)

            CROSS JOIN planejamento_staging ps

            JOIN ultimo_lote_planejamento ul
                ON ul.lote_id = ps.lote_id

            WHERE {where_planejamento}
            AND m.mes = ANY($2::int[])

            GROUP BY m.mes
        )

        SELECT
            m.mes,

            COALESCE(rm.matriculas_real, 0) AS matriculas_real,
            COALESCE(mm.matriculas_meta, 0) AS matriculas_meta,

            COALESCE(rm.ha_real, 0) AS ha_real,
            COALESCE(mm.ha_meta, 0) AS ha_meta,

            COALESCE(rm.receita_real, 0) AS receita_real,
            COALESCE(mm.receita_meta, 0) AS receita_meta

        FROM generate_series(1, 12) m(mes)

        LEFT JOIN realizado_mes rm
            ON rm.mes = m.mes

        LEFT JOIN meta_mes mm
            ON mm.mes = m.mes

        ORDER BY m.mes
    """

    evolucao_rows = await conn.fetch(
        sql_evolucao,
        *params
    )

    evolucao_mensal = {
        "matriculas": {
            "realizado": [],
            "meta": []
        },
        "hora_aluno": {
            "realizado": [],
            "meta": []
        },
        "receita": {
            "realizado": [],
            "meta": []
        }
    }

    meses_selecionados = set(meses)

    for row_evo in evolucao_rows:
        mes = int(row_evo["mes"])
        mes_selecionado = mes in meses_selecionados

        evolucao_mensal["matriculas"]["realizado"].append(
            float(row_evo["matriculas_real"] or 0)
            if mes_selecionado else None
        )

        evolucao_mensal["matriculas"]["meta"].append(
            float(row_evo["matriculas_meta"] or 0)
            if mes_selecionado else None
        )

        evolucao_mensal["hora_aluno"]["realizado"].append(
            float(row_evo["ha_real"] or 0)
            if mes_selecionado else None
        )

        evolucao_mensal["hora_aluno"]["meta"].append(
            float(row_evo["ha_meta"] or 0)
            if mes_selecionado else None
        )

        evolucao_mensal["receita"]["realizado"].append(
            float(row_evo["receita_real"] or 0)
            if mes_selecionado else None
        )

        evolucao_mensal["receita"]["meta"].append(
            float(row_evo["receita_meta"] or 0)
            if mes_selecionado else None
        )

    sql_regioes = f"""
    WITH ofertas_base AS (
        SELECT DISTINCT
            o.codigo,
            o.cod_programa,
            o.cod_financiamento,
            o.cod_uo
        FROM ofertas_programas o
        WHERE {where_oferta}
    ),

    ultimo_lote_planejamento AS (
        SELECT MAX(ps.lote_id) AS lote_id
        FROM planejamento_staging ps
        JOIN planejamento_import_lotes pil
            ON pil.id = ps.lote_id
        WHERE ps.flag_valida IS DISTINCT FROM FALSE
        AND ps.tipo = 'META'
        AND pil.ano_referencia = $1
    ),

    meta AS (
        SELECT
            UPPER(TRIM(ps.regiao)) AS regiao,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'MATRÍCULAS'
            ) AS matriculas_meta,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'HORA-ALUNO'
            ) AS ha_meta,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'RECEITAS CORRENTES'
            ) AS receita_meta

        FROM planejamento_staging ps
        JOIN ultimo_lote_planejamento ul
            ON ul.lote_id = ps.lote_id
        WHERE {where_planejamento}
            AND ps.regiao IS NOT NULL
        GROUP BY UPPER(TRIM(ps.regiao))
    ),

    realizado AS (
        SELECT
            UPPER(TRIM(r.nome)) AS regiao,

            SUM(COALESCE(rp.matriculas_real, 0)) AS matriculas_real,
            SUM(COALESCE(rp.ha_real, 0)) AS ha_real,
            SUM(COALESCE(rp.receita_real, 0)) AS receita_real

        FROM realizado_programas rp
        JOIN ofertas_base o
            ON o.codigo = rp.cod_oferta
        JOIN uo u
            ON u.codigo = o.cod_uo
        JOIN subregioes s
            ON s.codigo = u.cod_subregiao
        JOIN regioes r
            ON r.codigo = s.codigo_regiao

        WHERE rp.ano = $1
        AND rp.mes = ANY($2::int[])

        GROUP BY UPPER(TRIM(r.nome))
    )

    SELECT
        r.regiao AS regiao,

        COALESCE(realizado.matriculas_real, 0) AS matriculas_real,
        COALESCE(meta.matriculas_meta, 0) AS matriculas_meta,

        COALESCE(realizado.ha_real, 0) AS ha_real,
        COALESCE(meta.ha_meta, 0) AS ha_meta,

        COALESCE(realizado.receita_real, 0) AS receita_real,
        COALESCE(meta.receita_meta, 0) AS receita_meta

    FROM (
        SELECT DISTINCT
            COALESCE(meta.regiao, realizado.regiao) AS regiao
        FROM meta
        FULL JOIN realizado
            ON realizado.regiao = meta.regiao
        WHERE
            COALESCE(meta.matriculas_meta, 0) > 0
            OR COALESCE(realizado.matriculas_real, 0) > 0
            OR COALESCE(meta.ha_meta, 0) > 0
            OR COALESCE(realizado.ha_real, 0) > 0
            OR COALESCE(meta.receita_meta, 0) > 0
            OR COALESCE(realizado.receita_real, 0) > 0
    ) r
    LEFT JOIN meta
        ON meta.regiao = UPPER(TRIM(r.regiao))
    LEFT JOIN realizado
        ON realizado.regiao = UPPER(TRIM(r.regiao))
    ORDER BY r.regiao
    """

    regioes_rows = await conn.fetch(sql_regioes, *params)

    desempenho_regioes = []

    sql_subregioes = f"""
    WITH ofertas_base AS (
        SELECT DISTINCT
            o.codigo,
            o.cod_programa,
            o.cod_financiamento,
            o.cod_uo
        FROM ofertas_programas o
        WHERE {where_oferta}
    ),

    ultimo_lote_planejamento AS (
        SELECT MAX(ps.lote_id) AS lote_id
        FROM planejamento_staging ps
        JOIN planejamento_import_lotes pil
            ON pil.id = ps.lote_id
        WHERE ps.flag_valida IS DISTINCT FROM FALSE
        AND ps.tipo = 'META'
        AND pil.ano_referencia = $1
    ),

    meta AS (
        SELECT
            UPPER(TRIM(ps.subregiao)) AS subregiao,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'MATRÍCULAS'
            ) AS matriculas_meta,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'HORA-ALUNO'
            ) AS ha_meta,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'RECEITAS CORRENTES'
            ) AS receita_meta

        FROM planejamento_staging ps
        JOIN ultimo_lote_planejamento ul
            ON ul.lote_id = ps.lote_id

        WHERE {where_planejamento}
            AND ps.subregiao IS NOT NULL

        GROUP BY UPPER(TRIM(ps.subregiao))
    ),

    realizado AS (
        SELECT
            UPPER(TRIM(s.nome)) AS subregiao,

            SUM(COALESCE(rp.matriculas_real, 0)) AS matriculas_real,
            SUM(COALESCE(rp.ha_real, 0)) AS ha_real,
            SUM(COALESCE(rp.receita_real, 0)) AS receita_real

        FROM realizado_programas rp
        JOIN ofertas_base ob
            ON ob.codigo = rp.cod_oferta
        JOIN uo u
            ON u.codigo = ob.cod_uo
        JOIN subregioes s
            ON s.codigo = u.cod_subregiao

        WHERE rp.ano = $1
        AND rp.mes = ANY($2::int[])

            GROUP BY UPPER(TRIM(s.nome))
    ),

    base_subregioes AS (
        SELECT DISTINCT
            COALESCE(meta.subregiao, realizado.subregiao) AS subregiao
        FROM meta
        FULL JOIN realizado
            ON realizado.subregiao = meta.subregiao
        WHERE
            COALESCE(meta.matriculas_meta, 0) > 0
            OR COALESCE(realizado.matriculas_real, 0) > 0
            OR COALESCE(meta.ha_meta, 0) > 0
            OR COALESCE(realizado.ha_real, 0) > 0
            OR COALESCE(meta.receita_meta, 0) > 0
            OR COALESCE(realizado.receita_real, 0) > 0
    )

    SELECT
        s.subregiao AS subregiao,

        COALESCE(realizado.matriculas_real, 0) AS matriculas_real,
        COALESCE(meta.matriculas_meta, 0) AS matriculas_meta,

        COALESCE(realizado.ha_real, 0) AS ha_real,
        COALESCE(meta.ha_meta, 0) AS ha_meta,

        COALESCE(realizado.receita_real, 0) AS receita_real,
        COALESCE(meta.receita_meta, 0) AS receita_meta

    FROM base_subregioes s
    LEFT JOIN meta
        ON meta.subregiao = UPPER(TRIM(s.subregiao))
    LEFT JOIN realizado
        ON realizado.subregiao = UPPER(TRIM(s.subregiao))
    ORDER BY s.subregiao
    """

    subregioes_rows = await conn.fetch(sql_subregioes, *params)

    desempenho_subregioes = []

    sql_modalidades = f"""
    WITH ofertas_base AS (
        SELECT DISTINCT
            o.codigo,
            o.cod_programa,
            o.cod_financiamento,
            o.cod_uo,
            o.cod_modalidade
        FROM ofertas_programas o
        WHERE {where_oferta}
    ),

    ultimo_lote_planejamento AS (
        SELECT MAX(ps.lote_id) AS lote_id
        FROM planejamento_staging ps
        JOIN planejamento_import_lotes pil
            ON pil.id = ps.lote_id
        WHERE ps.flag_valida IS DISTINCT FROM FALSE
        AND ps.tipo = 'META'
        AND pil.ano_referencia = $1
    ),

    meta AS (
        SELECT
            m.codigo AS cod_modalidade,
            m.nome AS modalidade,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'MATRÍCULAS'
            ) AS matriculas_meta,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'HORA-ALUNO'
            ) AS ha_meta,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'RECEITAS CORRENTES'
            ) AS receita_meta

        FROM planejamento_staging ps
        JOIN ultimo_lote_planejamento ul
            ON ul.lote_id = ps.lote_id
        JOIN modalidade m
            ON m.codigo::text = ps.cod_modalidade_raw::text

        WHERE {where_planejamento}
            AND ps.cod_modalidade_raw IS NOT NULL

        GROUP BY
            m.codigo,
            m.nome
    ),

    realizado AS (
        SELECT
            m.codigo AS cod_modalidade,
            m.nome AS modalidade,

            SUM(COALESCE(rp.matriculas_real, 0)) AS matriculas_real,
            SUM(COALESCE(rp.ha_real, 0)) AS ha_real,
            SUM(COALESCE(rp.receita_real, 0)) AS receita_real

        FROM realizado_programas rp
        JOIN ofertas_base ob
            ON ob.codigo = rp.cod_oferta
        JOIN modalidade m
            ON m.codigo = ob.cod_modalidade

        WHERE rp.ano = $1
        AND rp.mes = ANY($2::int[])

        GROUP BY
            m.codigo,
            m.nome
    ),

    base_modalidades AS (
        SELECT DISTINCT
            COALESCE(meta.cod_modalidade, realizado.cod_modalidade) AS cod_modalidade,
            COALESCE(meta.modalidade, realizado.modalidade) AS modalidade
        FROM meta
        FULL JOIN realizado
            ON realizado.cod_modalidade = meta.cod_modalidade
        WHERE
            COALESCE(meta.matriculas_meta, 0) > 0
            OR COALESCE(realizado.matriculas_real, 0) > 0
            OR COALESCE(meta.ha_meta, 0) > 0
            OR COALESCE(realizado.ha_real, 0) > 0
            OR COALESCE(meta.receita_meta, 0) > 0
            OR COALESCE(realizado.receita_real, 0) > 0
    )

    SELECT
        bm.modalidade AS modalidade,

        COALESCE(r.matriculas_real, 0) AS matriculas_real,
        COALESCE(mt.matriculas_meta, 0) AS matriculas_meta,

        COALESCE(r.ha_real, 0) AS ha_real,
        COALESCE(mt.ha_meta, 0) AS ha_meta,

        COALESCE(r.receita_real, 0) AS receita_real,
        COALESCE(mt.receita_meta, 0) AS receita_meta

    FROM base_modalidades bm
    LEFT JOIN realizado r
        ON r.cod_modalidade = bm.cod_modalidade
    LEFT JOIN meta mt
        ON mt.cod_modalidade = bm.cod_modalidade

    ORDER BY bm.modalidade
    """

    modalidades_rows = await conn.fetch(sql_modalidades, *params)

    desempenho_modalidades = []

    sql_programas = f"""
    WITH ofertas_base AS (
        SELECT DISTINCT
            o.codigo,
            o.cod_programa,
            o.cod_financiamento,
            o.cod_uo,
            o.cod_modalidade
        FROM ofertas_programas o
        WHERE {where_oferta}
    ),

    ultimo_lote_planejamento AS (
        SELECT MAX(ps.lote_id) AS lote_id
        FROM planejamento_staging ps
        JOIN planejamento_import_lotes pil
            ON pil.id = ps.lote_id
        WHERE ps.flag_valida IS DISTINCT FROM FALSE
        AND ps.tipo = 'META'
        AND pil.ano_referencia = $1
    ),

    meta AS (
        SELECT
            UPPER(TRIM(ps.programa_raw)) AS programa,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'MATRÍCULAS'
            ) AS matriculas_meta,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'HORA-ALUNO'
            ) AS ha_meta,

            SUM({meta_periodo}) FILTER (
                WHERE UPPER(TRIM(ps.conta)) = 'RECEITAS CORRENTES'
            ) AS receita_meta

        FROM planejamento_staging ps
        JOIN ultimo_lote_planejamento ul
            ON ul.lote_id = ps.lote_id

        WHERE {where_planejamento}
            AND ps.programa_raw IS NOT NULL

        GROUP BY UPPER(TRIM(ps.programa_raw))
    ),

    realizado AS (
        SELECT
            UPPER(TRIM(p.nome_programa)) AS programa,

            SUM(COALESCE(rp.matriculas_real, 0)) AS matriculas_real,
            SUM(COALESCE(rp.ha_real, 0)) AS ha_real,
            SUM(COALESCE(rp.receita_real, 0)) AS receita_real

        FROM realizado_programas rp
        JOIN ofertas_programas o
            ON o.codigo = rp.cod_oferta
        JOIN ofertas_base ob
            ON ob.codigo = o.codigo
        JOIN programas p
            ON p.codigo = o.cod_programa

        WHERE rp.ano = $1
        AND rp.mes = ANY($2::int[])

        GROUP BY UPPER(TRIM(p.nome_programa))
    )

    SELECT
        COALESCE(meta.programa, realizado.programa) AS programa,

        COALESCE(realizado.matriculas_real, 0) AS matriculas_real,
        COALESCE(meta.matriculas_meta, 0) AS matriculas_meta,

        COALESCE(realizado.ha_real, 0) AS ha_real,
        COALESCE(meta.ha_meta, 0) AS ha_meta,

        COALESCE(realizado.receita_real, 0) AS receita_real,
        COALESCE(meta.receita_meta, 0) AS receita_meta

    FROM meta
    FULL JOIN realizado
        ON realizado.programa = meta.programa

    WHERE COALESCE(meta.programa, realizado.programa) IS NOT NULL

    ORDER BY programa
    """

    programas_rows = await conn.fetch(sql_programas, *params)

    programas_agrupados = {}

    for prog in programas_rows:
        nome_programa = (prog["programa"] or "").strip()

        if nome_programa.upper() in ["SEJA PRO+", "SEJA PRÓ+"]:
            nome_programa = "SEJA PRÓ+"

        chave = nome_programa.upper()

        if chave not in programas_agrupados:
            programas_agrupados[chave] = {
                "programa": nome_programa,
                "matriculas_real": 0,
                "matriculas_meta": 0,
                "hora_aluno_real": 0,
                "hora_aluno_meta": 0,
                "receita_real": 0,
                "receita_meta": 0,
            }

        item = programas_agrupados[chave]

        item["matriculas_real"] += float(prog["matriculas_real"] or 0)
        item["matriculas_meta"] += float(prog["matriculas_meta"] or 0)

        item["hora_aluno_real"] += float(prog["ha_real"] or 0)
        item["hora_aluno_meta"] += float(prog["ha_meta"] or 0)

        item["receita_real"] += float(prog["receita_real"] or 0)
        item["receita_meta"] += float(prog["receita_meta"] or 0)


    desempenho_programas = []

    for item in programas_agrupados.values():
        desempenho_programas.append({
            "programa": item["programa"],

            "matriculas_real": item["matriculas_real"],
            "matriculas_meta": item["matriculas_meta"],
            "matriculas_pct": _pct(
                item["matriculas_real"],
                item["matriculas_meta"]
            ),

            "hora_aluno_real": item["hora_aluno_real"],
            "hora_aluno_meta": item["hora_aluno_meta"],
            "hora_aluno_pct": _pct(
                item["hora_aluno_real"],
                item["hora_aluno_meta"]
            ),

            "receita_real": item["receita_real"],
            "receita_meta": item["receita_meta"],
            "receita_pct": _pct(
                item["receita_real"],
                item["receita_meta"]
            ),
        })

    desempenho_programas.sort(
        key=lambda x: x["programa"]
    )

    for mod in modalidades_rows:
        mat_real = float(mod["matriculas_real"] or 0)
        mat_meta = float(mod["matriculas_meta"] or 0)

        ha_real_mod = float(mod["ha_real"] or 0)
        ha_meta_mod = float(mod["ha_meta"] or 0)

        rec_real_mod = float(mod["receita_real"] or 0)
        rec_meta_mod = float(mod["receita_meta"] or 0)

        desempenho_modalidades.append({
            "modalidade": mod["modalidade"],

            "matriculas_real": mat_real,
            "matriculas_meta": mat_meta,
            "matriculas_pct": _pct(mat_real, mat_meta),

            "hora_aluno_real": ha_real_mod,
            "hora_aluno_meta": ha_meta_mod,
            "hora_aluno_pct": _pct(ha_real_mod, ha_meta_mod),

            "receita_real": rec_real_mod,
            "receita_meta": rec_meta_mod,
            "receita_pct": _pct(rec_real_mod, rec_meta_mod),
        })

    for sr in subregioes_rows:
        mat_real = float(sr["matriculas_real"] or 0)
        mat_meta = float(sr["matriculas_meta"] or 0)

        ha_real_sr = float(sr["ha_real"] or 0)
        ha_meta_sr = float(sr["ha_meta"] or 0)

        rec_real_sr = float(sr["receita_real"] or 0)
        rec_meta_sr = float(sr["receita_meta"] or 0)

        desempenho_subregioes.append({
            "subregiao": sr["subregiao"],

            "matriculas_real": mat_real,
            "matriculas_meta": mat_meta,
            "matriculas_pct": _pct(mat_real, mat_meta),

            "hora_aluno_real": ha_real_sr,
            "hora_aluno_meta": ha_meta_sr,
            "hora_aluno_pct": _pct(ha_real_sr, ha_meta_sr),

            "receita_real": rec_real_sr,
            "receita_meta": rec_meta_sr,
            "receita_pct": _pct(rec_real_sr, rec_meta_sr),
        })

    for r in regioes_rows:
        mat_real = float(r["matriculas_real"] or 0)
        mat_meta = float(r["matriculas_meta"] or 0)

        ha_real_reg = float(r["ha_real"] or 0)
        ha_meta_reg = float(r["ha_meta"] or 0)

        rec_real_reg = float(r["receita_real"] or 0)
        rec_meta_reg = float(r["receita_meta"] or 0)

        desempenho_regioes.append({
            "regiao": r["regiao"],

            "matriculas_real": mat_real,
            "matriculas_meta": mat_meta,
            "matriculas_pct": _pct(mat_real, mat_meta),

            "hora_aluno_real": ha_real_reg,
            "hora_aluno_meta": ha_meta_reg,
            "hora_aluno_pct": _pct(ha_real_reg, ha_meta_reg),

            "receita_real": rec_real_reg,
            "receita_meta": rec_meta_reg,
            "receita_pct": _pct(rec_real_reg, rec_meta_reg),
        })
    
    contexto_txt = _contexto_relatorio(filtros)

    mat_pct = _pct(matriculas_real, matriculas_meta)
    ha_pct = _pct(ha_real, ha_meta)
    rec_pct = _pct(receita_real, receita_meta)

    txt_mat = _texto_atingimento(matriculas_real, matriculas_meta)
    txt_ha = _texto_atingimento(ha_real, ha_meta)
    txt_rec = _texto_atingimento(receita_real, receita_meta)

    resumo_executivo = (
        f"No período selecionado, os resultados foram analisados{contexto_txt}. "
        f"As matrículas apresentaram {txt_mat} em relação à meta acumulada, "
        f"enquanto a hora-aluno apresentou {txt_ha}. "
        f"Para receita, o resultado foi classificado como {txt_rec}. "
        f"Essa leitura considera a existência ou não de meta cadastrada para cada indicador no período."
    )

    insights_executivos = []

    if mat_pct >= 100:
        insights_executivos.append(
            f"O desempenho de matrículas superou a meta planejada, alcançando {mat_pct:.1f}% no período."
        )
    elif mat_pct >= 75:
        insights_executivos.append(
            f"As matrículas estão próximas da meta, com atingimento de {mat_pct:.1f}% no período."
        )
    else:
        insights_executivos.append(
            f"As matrículas ficaram abaixo do esperado, atingindo {mat_pct:.1f}% da meta acumulada."
        )

    if ha_pct >= 100:
        insights_executivos.append(
            f"A execução de hora-aluno superou o previsto, alcançando {ha_pct:.1f}% da meta."
        )
    elif ha_pct >= 75:
        insights_executivos.append(
            f"A hora-aluno apresenta desempenho intermediário, com {ha_pct:.1f}% de atingimento."
        )
    else:
        insights_executivos.append(
            f"A hora-aluno ficou abaixo do esperado, com {ha_pct:.1f}% da meta, indicando atenção à execução da carga horária."
        )

    sit_rec = _situacao_indicador(receita_real, receita_meta)

    if sit_rec == "nao_aplicavel":
        insights_executivos.append(
            "A receita não possui meta nem execução registrada no período, não sendo aplicável a análise de atingimento."
        )
    elif sit_rec == "sem_meta":
        insights_executivos.append(
            "A receita apresentou execução no período, porém não possui meta cadastrada para comparação."
        )
    elif sit_rec == "sem_execucao":
        insights_executivos.append(
            "A receita possui meta definida, mas não apresentou realização no período analisado."
        )
    elif rec_pct >= 100:
        insights_executivos.append(
            f"A receita superou o planejamento, chegando a {rec_pct:.1f}% da meta acumulada."
        )
    elif rec_pct >= 75:
        insights_executivos.append(
            f"A receita está em faixa de acompanhamento, com {rec_pct:.1f}% de atingimento."
        )
    else:
        insights_executivos.append(
            f"A receita apresentou desempenho abaixo do planejado, alcançando {rec_pct:.1f}% da meta."
        )

    recomendacoes = []

    recomendacoes.append(
        _recomendacao_indicador("matrículas", matriculas_real, matriculas_meta)
    )

    recomendacoes.append(
        _recomendacao_indicador("hora-aluno", ha_real, ha_meta)
    )

    recomendacoes.append(
        _recomendacao_indicador("receita", receita_real, receita_meta)
    )

    if mat_pct >= 75 and ha_pct >= 75:
        recomendacoes.append(
            "Compartilhar boas práticas operacionais que vêm contribuindo para o desempenho satisfatório dos indicadores educacionais."
        )

    if matriculas_meta > 0 or ha_meta > 0 or receita_meta > 0:
        recomendacoes.append(
            "Revisar periodicamente os parâmetros de planejamento para assegurar aderência entre metas, capacidade operacional e execução realizada."
        )

    recomendacoes = recomendacoes[:5]
    
    desempenho_subregiao_uo = []
    desempenho_regiao_uo = []
    regiao_uo = None
    subregiao_uo = None

    if filtros.uo:
        sql_contexto_uo = """
            SELECT
                r.nome AS regiao,
                s.nome AS subregiao
            FROM uo u
            JOIN subregioes s
                ON s.codigo = u.cod_subregiao
            JOIN regioes r
                ON r.codigo = s.codigo_regiao
            WHERE UPPER(TRIM(u.nome)) = UPPER(TRIM($1))
            LIMIT 1
        """

        contexto_uo = await conn.fetchrow(
            sql_contexto_uo,
            filtros.uo
        )

        if contexto_uo:
            regiao_uo = contexto_uo["regiao"]
            subregiao_uo = contexto_uo["subregiao"]

        if filtros.uo and regiao_uo:
            sql_regiao_ctx = f"""
                WITH ofertas_regiao AS (
                    SELECT DISTINCT
                        o.codigo
                    FROM ofertas_programas o
                    JOIN uo u
                        ON u.codigo = o.cod_uo
                    JOIN subregioes s
                        ON s.codigo = u.cod_subregiao
                    JOIN regioes r
                        ON r.codigo = s.codigo_regiao
                    WHERE o.ano = $1
                    AND UPPER(TRIM(r.nome)) = UPPER(TRIM($3))
                ),

                meta AS (
                    SELECT
                        COALESCE(
                            SUM({meta_periodo}) FILTER (
                                WHERE UPPER(TRIM(ps.conta)) = 'MATRÍCULAS'
                            ),
                            0
                        ) AS matriculas_meta,

                        COALESCE(
                            SUM({meta_periodo}) FILTER (
                                WHERE UPPER(TRIM(ps.conta)) = 'HORA-ALUNO'
                            ),
                            0
                        ) AS ha_meta,

                        COALESCE(
                            SUM({meta_periodo}) FILTER (
                                WHERE UPPER(TRIM(ps.conta)) = 'RECEITAS CORRENTES'
                            ),
                            0
                        ) AS receita_meta

                    FROM planejamento_staging ps
                    WHERE ps.flag_valida IS DISTINCT FROM FALSE
                    AND ps.tipo = 'META'
                    AND UPPER(TRIM(ps.regiao)) = UPPER(TRIM($3))
                ),

                realizado AS (
                    SELECT
                        COALESCE(SUM(rp.matriculas_real), 0) AS matriculas_real,
                        COALESCE(SUM(rp.ha_real), 0) AS ha_real,
                        COALESCE(SUM(rp.receita_real), 0) AS receita_real
                    FROM realizado_programas rp
                    JOIN ofertas_regiao os
                        ON os.codigo = rp.cod_oferta
                    WHERE rp.ano = $1
                    AND rp.mes = ANY($2::int[])
                )

                SELECT
                    $3::text AS regiao,

                    COALESCE(realizado.matriculas_real, 0) AS matriculas_real,
                    COALESCE(meta.matriculas_meta, 0) AS matriculas_meta,

                    COALESCE(realizado.ha_real, 0) AS ha_real,
                    COALESCE(meta.ha_meta, 0) AS ha_meta,

                    COALESCE(realizado.receita_real, 0) AS receita_real,
                    COALESCE(meta.receita_meta, 0) AS receita_meta

                FROM realizado, meta
            """

            row_reg_ctx = await conn.fetchrow(
                sql_regiao_ctx,
                filtros.ano,
                meses,
                regiao_uo
            )

            if row_reg_ctx:
                mat_real = float(row_reg_ctx["matriculas_real"] or 0)
                mat_meta = float(row_reg_ctx["matriculas_meta"] or 0)

                ha_real_ctx = float(row_reg_ctx["ha_real"] or 0)
                ha_meta_ctx = float(row_reg_ctx["ha_meta"] or 0)

                rec_real_ctx = float(row_reg_ctx["receita_real"] or 0)
                rec_meta_ctx = float(row_reg_ctx["receita_meta"] or 0)

                desempenho_regiao_uo.append({
                    "regiao": row_reg_ctx["regiao"],

                    "matriculas_real": mat_real,
                    "matriculas_meta": mat_meta,
                    "matriculas_pct": _pct(mat_real, mat_meta),

                    "hora_aluno_real": ha_real_ctx,
                    "hora_aluno_meta": ha_meta_ctx,
                    "hora_aluno_pct": _pct(ha_real_ctx, ha_meta_ctx),

                    "receita_real": rec_real_ctx,
                    "receita_meta": rec_meta_ctx,
                    "receita_pct": _pct(rec_real_ctx, rec_meta_ctx),
                })
        
        desempenho_subregiao_uo = []

        if filtros.uo and subregiao_uo:
            filtros_subregiao_ctx = [
                "ps.flag_valida IS DISTINCT FROM FALSE",
                "ps.tipo = 'META'",
                f"UPPER(TRIM(ps.subregiao)) = UPPER(TRIM($3))"
            ]

            where_subregiao_ctx = " AND ".join(filtros_subregiao_ctx)

            sql_subregiao_ctx = f"""
                WITH ofertas_subregiao AS (
                    SELECT DISTINCT
                        o.codigo
                    FROM ofertas_programas o
                    JOIN uo u
                        ON u.codigo = o.cod_uo
                    JOIN subregioes s
                        ON s.codigo = u.cod_subregiao
                    WHERE o.ano = $1
                    AND UPPER(TRIM(s.nome)) = UPPER(TRIM($3))
                ),

                meta AS (
                    SELECT
                        COALESCE(
                            SUM({meta_periodo}) FILTER (
                                WHERE UPPER(TRIM(ps.conta)) = 'MATRÍCULAS'
                            ),
                            0
                        ) AS matriculas_meta,

                        COALESCE(
                            SUM({meta_periodo}) FILTER (
                                WHERE UPPER(TRIM(ps.conta)) = 'HORA-ALUNO'
                            ),
                            0
                        ) AS ha_meta,

                        COALESCE(
                            SUM({meta_periodo}) FILTER (
                                WHERE UPPER(TRIM(ps.conta)) = 'RECEITAS CORRENTES'
                            ),
                            0
                        ) AS receita_meta

                    FROM planejamento_staging ps
                    WHERE {where_subregiao_ctx}
                ),

                realizado AS (
                    SELECT
                        COALESCE(SUM(rp.matriculas_real), 0) AS matriculas_real,
                        COALESCE(SUM(rp.ha_real), 0) AS ha_real,
                        COALESCE(SUM(rp.receita_real), 0) AS receita_real
                    FROM realizado_programas rp
                    JOIN ofertas_subregiao os
                        ON os.codigo = rp.cod_oferta
                    WHERE rp.ano = $1
                    AND rp.mes = ANY($2::int[])
                )

                SELECT
                    $3::text AS subregiao,

                    COALESCE(realizado.matriculas_real, 0) AS matriculas_real,
                    COALESCE(meta.matriculas_meta, 0) AS matriculas_meta,

                    COALESCE(realizado.ha_real, 0) AS ha_real,
                    COALESCE(meta.ha_meta, 0) AS ha_meta,

                    COALESCE(realizado.receita_real, 0) AS receita_real,
                    COALESCE(meta.receita_meta, 0) AS receita_meta

                FROM realizado, meta
            """

            row_sub_ctx = await conn.fetchrow(
                sql_subregiao_ctx,
                filtros.ano,
                meses,
                subregiao_uo
            )

            if row_sub_ctx:
                mat_real = float(row_sub_ctx["matriculas_real"] or 0)
                mat_meta = float(row_sub_ctx["matriculas_meta"] or 0)

                ha_real_ctx = float(row_sub_ctx["ha_real"] or 0)
                ha_meta_ctx = float(row_sub_ctx["ha_meta"] or 0)

                rec_real_ctx = float(row_sub_ctx["receita_real"] or 0)
                rec_meta_ctx = float(row_sub_ctx["receita_meta"] or 0)

                desempenho_subregiao_uo.append({
                    "subregiao": row_sub_ctx["subregiao"],

                    "matriculas_real": mat_real,
                    "matriculas_meta": mat_meta,
                    "matriculas_pct": _pct(mat_real, mat_meta),

                    "hora_aluno_real": ha_real_ctx,
                    "hora_aluno_meta": ha_meta_ctx,
                    "hora_aluno_pct": _pct(ha_real_ctx, ha_meta_ctx),

                    "receita_real": rec_real_ctx,
                    "receita_meta": rec_meta_ctx,
                    "receita_pct": _pct(rec_real_ctx, rec_meta_ctx),
                })
    
    acoes_executivas = []

    if filtros.programa or filtros.subregiao or filtros.regiao or filtros.uo:
        filtros_acoes = ["ano = $1"]
        params_acoes = [filtros.ano]

        if filtros.programa:
            params_acoes.append(filtros.programa)
            filtros_acoes.append(
                f"UPPER(TRIM(programa)) = UPPER(TRIM(${len(params_acoes)}))"
            )

        if filtros.regiao and not foco_uo:
            params_acoes.append(filtros.regiao)
            filtros_acoes.append(
                f"UPPER(TRIM(regiao)) = UPPER(TRIM(${len(params_acoes)}))"
            )

        if filtros.subregiao and not foco_uo:
            params_acoes.append(filtros.subregiao)
            filtros_acoes.append(
                f"UPPER(TRIM(subregiao)) = UPPER(TRIM(${len(params_acoes)}))"
            )
        
        if filtros.uo:
            params_acoes.append(filtros.uo)
            filtros_acoes.append(
                f"UPPER(TRIM(uo)) = UPPER(TRIM(${len(params_acoes)}))"
            )

        where_acoes = " AND ".join(filtros_acoes)

        sql_acoes = f"""
            SELECT
                programa,
                tipo,
                titulo,
                descricao,
                responsavel,
                data_prevista,
                status,
                evidencia,
                uo
            FROM executivo_acoes
            WHERE {where_acoes}
            ORDER BY
                CASE
                    WHEN LOWER(status) LIKE '%andamento%' THEN 1
                    WHEN LOWER(status) LIKE '%planejad%' THEN 2
                    WHEN LOWER(status) LIKE '%conclu%' THEN 3
                    ELSE 4
                END,
                data_prevista NULLS LAST,
                programa,
                titulo
        """

        acoes_rows = await conn.fetch(sql_acoes, *params_acoes)

        for a in acoes_rows:
            acoes_executivas.append({
                "programa": a["programa"] or "-",
                "tipo_acao": a["tipo"] or "-",
                "titulo": a["titulo"] or "-",
                "descricao": a["descricao"] or "",
                "responsavel": a["responsavel"] or "-",
                "data_prevista": a["data_prevista"].strftime("%d/%m/%Y") if a["data_prevista"] else "-",
                "status": a["status"] or "-",
                "evidencia": a["evidencia"] or "",
                "uo": a["uo"] or "-",
            })

    return {
        "titulo": "Relatório Executivo",
        "modo_relatorio": modo_relatorio,
        "ano": filtros.ano,
        "programa": filtros.programa,
        "regiao": filtros.regiao,
        "subregiao": filtros.subregiao,
        "uo": filtros.uo,
        "meses": meses,
        "evolucao_mensal": evolucao_mensal,
        "desempenho_regioes": desempenho_regioes,
        "desempenho_subregioes": desempenho_subregioes,
        "desempenho_modalidades": desempenho_modalidades,
        "desempenho_programas": desempenho_programas,
        "resumo_executivo": resumo_executivo,
        "insights_executivos": insights_executivos,
        "recomendacoes": recomendacoes,
        "acoes_executivas": acoes_executivas,
        "regiao_uo": regiao_uo,
        "subregiao_uo": subregiao_uo,
        "desempenho_subregiao_uo": desempenho_subregiao_uo,
        "desempenho_regiao_uo": desempenho_regiao_uo,
        "kpis": {
            "matriculas": {
                "realizado": matriculas_real,
                "meta": matriculas_meta,
                "atingimento": _pct(matriculas_real, matriculas_meta),
            },
            "hora_aluno": {
                "realizado": ha_real,
                "meta": ha_meta,
                "atingimento": _pct(ha_real, ha_meta),
            },
            "receita": {
                "realizado": receita_real,
                "meta": receita_meta,
                "atingimento": _pct(receita_real, receita_meta),
            },
            "turmas": {
                "total": turmas_total
            }
        },

        "opcoes": {
            "incluir_graficos": opcoes.incluir_graficos,
            "incluir_recomendacoes": opcoes.incluir_recomendacoes,
            "incluir_acoes": opcoes.incluir_acoes
        }
    }

async def montar_preview_relatorio_desempenho_programa(
    conn,
    filtros,
    opcoes
):
    preview = await montar_preview_relatorio_executivo(
        conn,
        filtros,
        opcoes
    )

    sql_cabecalho = """
        SELECT
            r.nome AS regiao,
            s.nome AS subregiao,
            u.nome AS uo,
            u.geope AS geope
        FROM uo u
        LEFT JOIN subregioes s
            ON s.codigo = u.cod_subregiao
        LEFT JOIN regioes r
            ON r.codigo = s.codigo_regiao
        WHERE u.nome IS NOT NULL
          AND TRIM(u.nome) <> ''
          AND (
                $1::text IS NULL
                OR UPPER(TRIM(r.nome)) = UPPER(TRIM($1))
          )
          AND (
                $2::text IS NULL
                OR UPPER(TRIM(s.nome)) = UPPER(TRIM($2))
          )
          AND (
                $3::text IS NULL
                OR UPPER(TRIM(u.nome)) = UPPER(TRIM($3))
          )
        ORDER BY u.nome
    """

    rows_cabecalho = await conn.fetch(
        sql_cabecalho,
        filtros.regiao,
        filtros.subregiao,
        filtros.uo
    )

    uos = []
    geopess = []
    regiao_encontrada = filtros.regiao
    subregiao_encontrada = filtros.subregiao

    for row in rows_cabecalho:
        nome_uo = row["uo"]
        nome_geope = row["geope"]

        if nome_uo and nome_uo not in uos:
            uos.append(nome_uo)

        if nome_geope and nome_geope not in geopess:
            geopess.append(nome_geope)

        if not regiao_encontrada and row["regiao"]:
            regiao_encontrada = row["regiao"]

        if not subregiao_encontrada and row["subregiao"]:
            subregiao_encontrada = row["subregiao"]

    preview["cabecalho_desempenho_programa"] = {
        "programa": filtros.programa,
        "regiao": regiao_encontrada,
        "subregiao": subregiao_encontrada,
        "geope": ", ".join(geopess) if geopess else None,
        "uos": uos
    }

    programa_selecionado = (
        filtros.programa
        if getattr(filtros, "programa", None)
        else None
    )

    preview["modo_desempenho_programa"] = (
        "programa_unico"
        if programa_selecionado
        else "multiplos_programas"
    )

    preview["modo_agrupamento_desempenho"] = (
        "subregiao_programa_uo"
        if filtros.regiao and not filtros.subregiao
        else "programa_uo"
    )

    if programa_selecionado:
        programas_relatorio = [
            programa_selecionado
        ]
    else:
        programas_relatorio = sorted({
            str(item.get("programa")).strip()
            for item in preview.get(
                "desempenho_programas",
                []
            )
            if item.get("programa")
        })

    preview["programas_relatorio"] = programas_relatorio

    # ======================================================
    # MAPEAMENTO DE PROGRAMAS E UNIDADES OPERACIONAIS
    # ======================================================

    sql_programas_uos = """
        WITH ultimo_lote_planejamento AS (
            SELECT MAX(ps.lote_id) AS lote_id
            FROM planejamento_staging ps
            JOIN planejamento_import_lotes pil
                ON pil.id = ps.lote_id
            WHERE ps.flag_valida IS DISTINCT FROM FALSE
              AND ps.tipo = 'META'
              AND CAST(pil.ano_referencia AS integer) = $1
        ),

        relacoes AS (
            -- Relações existentes nas ofertas
            SELECT DISTINCT
                UPPER(TRIM(p.nome_programa)) AS programa,
                o.cod_uo AS cod_uo
            FROM ofertas_programas o
            JOIN programas p
                ON p.codigo = o.cod_programa
            WHERE o.ano = $1
              AND UPPER(TRIM(p.nome_programa))
                    = ANY($2::text[])

            UNION

            -- Relações existentes no planejamento
            SELECT DISTINCT
                UPPER(TRIM(ps.programa_raw)) AS programa,
                u.codigo AS cod_uo
            FROM planejamento_staging ps
            JOIN ultimo_lote_planejamento ul
                ON ul.lote_id = ps.lote_id
            JOIN uo u
                ON u.codigo::text = ps.cod_uo_raw::text
            WHERE ps.flag_valida IS DISTINCT FROM FALSE
              AND ps.tipo = 'META'
              AND ps.programa_raw IS NOT NULL
              AND UPPER(TRIM(ps.programa_raw))
                    = ANY($2::text[])
        )

        SELECT DISTINCT
            rel.programa,
            u.nome AS uo
        FROM relacoes rel
        JOIN uo u
            ON u.codigo = rel.cod_uo
        LEFT JOIN subregioes s
            ON s.codigo = u.cod_subregiao
        LEFT JOIN regioes r
            ON r.codigo = s.codigo_regiao
        WHERE u.nome IS NOT NULL
          AND TRIM(u.nome) <> ''

          AND (
                $3::text IS NULL
                OR UPPER(TRIM(r.nome))
                    = UPPER(TRIM($3))
          )

          AND (
                $4::text IS NULL
                OR UPPER(TRIM(s.nome))
                    = UPPER(TRIM($4))
          )

          AND (
                $5::text IS NULL
                OR UPPER(TRIM(u.nome))
                    = UPPER(TRIM($5))
          )

        ORDER BY
            rel.programa,
            u.nome
    """

    programas_normalizados = [
        str(nome).strip().upper()
        for nome in programas_relatorio
        if nome
    ]

    rows_programas_uos = await conn.fetch(
        sql_programas_uos,
        filtros.ano,
        programas_normalizados,
        filtros.regiao,
        filtros.subregiao,
        filtros.uo
    )

    uos_por_programa = {
        str(nome).strip().upper(): []
        for nome in programas_relatorio
        if nome
    }

    for row in rows_programas_uos:
        chave_programa = (
            str(row["programa"] or "")
            .strip()
            .upper()
        )

        nome_uo = (
            str(row["uo"] or "")
            .strip()
        )

        if (
            chave_programa
            and nome_uo
            and nome_uo not in uos_por_programa.setdefault(
                chave_programa,
                []
            )
        ):
            uos_por_programa[chave_programa].append(
                nome_uo
            )

    preview["uos_por_programa"] = uos_por_programa

    # ======================================================
    # DESEMPENHO POR UO E MODALIDADE
    # ======================================================

    desempenho_uos = []
    desempenho_programas_detalhado = []
    subregioes_detalhadas = {}

    for nome_programa in programas_relatorio:

        chave_programa = (
            str(nome_programa)
            .strip()
            .upper()
        )

        uos_programa = uos_por_programa.get(
            chave_programa,
            []
        )

        desempenho_uos_programa = []

        for nome_uo in uos_programa:

            # ----------------------------------------------
            # Resultado do período selecionado
            # ----------------------------------------------

            filtros_uo_periodo = filtros.model_copy(
                update={
                    "programa": nome_programa,
                    "uo": nome_uo
                }
            )

            preview_uo_periodo = await montar_preview_relatorio_executivo(
                conn,
                filtros_uo_periodo,
                opcoes
            )

            subregiao_nome = (
                preview_uo_periodo.get("subregiao_uo")
                or "SUB-REGIÃO NÃO INFORMADA"
            )

            modalidades_periodo = (
                preview_uo_periodo.get(
                    "desempenho_modalidades",
                    []
                )
                or []
            )

            # ----------------------------------------------
            # Meta anual
            # ----------------------------------------------

            filtros_uo_anual = filtros.model_copy(
                update={
                    "programa": nome_programa,
                    "uo": nome_uo,
                    "meses": list(range(1, 13))
                }
            )

            preview_uo_anual = await montar_preview_relatorio_executivo(
                conn,
                filtros_uo_anual,
                opcoes
            )

            modalidades_anuais = (
                preview_uo_anual.get(
                    "desempenho_modalidades",
                    []
                )
                or []
            )

            # Facilita a busca da meta anual por modalidade
            anual_por_modalidade = {
                str(item.get("modalidade") or "").strip().upper(): item
                for item in modalidades_anuais
            }

            matriculas = []
            hora_aluno = []
            receita = []

            for modalidade_periodo in modalidades_periodo:

                nome_modalidade = (
                    modalidade_periodo.get("modalidade")
                    or "NÃO INFORMADA"
                )

                chave_modalidade = (
                    str(nome_modalidade)
                    .strip()
                    .upper()
                )

                modalidade_anual = anual_por_modalidade.get(
                    chave_modalidade,
                    {}
                )

                # ------------------------------------------
                # Matrículas
                # ------------------------------------------

                matriculas_meta_periodo = float(
                    modalidade_periodo.get(
                        "matriculas_meta",
                        0
                    )
                    or 0
                )

                matriculas_real_periodo = float(
                    modalidade_periodo.get(
                        "matriculas_real",
                        0
                    )
                    or 0
                )

                matriculas_meta_anual = float(
                    modalidade_anual.get(
                        "matriculas_meta",
                        0
                    )
                    or 0
                )

                matriculas.append({
                    "modalidade": nome_modalidade,
                    "meta_periodo": matriculas_meta_periodo,
                    "realizado_periodo": matriculas_real_periodo,
                    "meta_anual": matriculas_meta_anual,
                    "atingimento": _pct(
                        matriculas_real_periodo,
                        matriculas_meta_periodo
                    )
                })

                # ------------------------------------------
                # Hora-Aluno
                # ------------------------------------------

                ha_meta_periodo = float(
                    modalidade_periodo.get(
                        "hora_aluno_meta",
                        0
                    )
                    or 0
                )

                ha_real_periodo = float(
                    modalidade_periodo.get(
                        "hora_aluno_real",
                        0
                    )
                    or 0
                )

                ha_meta_anual = float(
                    modalidade_anual.get(
                        "hora_aluno_meta",
                        0
                    )
                    or 0
                )

                hora_aluno.append({
                    "modalidade": nome_modalidade,
                    "meta_periodo": ha_meta_periodo,
                    "realizado_periodo": ha_real_periodo,
                    "meta_anual": ha_meta_anual,
                    "atingimento": _pct(
                        ha_real_periodo,
                        ha_meta_periodo
                    )
                })

                # ------------------------------------------
                # Receita
                # ------------------------------------------

                receita_meta_periodo = float(
                    modalidade_periodo.get(
                        "receita_meta",
                        0
                    )
                    or 0
                )

                receita_real_periodo = float(
                    modalidade_periodo.get(
                        "receita_real",
                        0
                    )
                    or 0
                )

                receita_meta_anual = float(
                    modalidade_anual.get(
                        "receita_meta",
                        0
                    )
                    or 0
                )

                receita.append({
                    "modalidade": nome_modalidade,
                    "meta_periodo": receita_meta_periodo,
                    "realizado_periodo": receita_real_periodo,
                    "meta_anual": receita_meta_anual,
                    "atingimento": _pct(
                        receita_real_periodo,
                        receita_meta_periodo
                    )
                })

            analise_uo = _gerar_analise_unidade(
                nome_uo=nome_uo,
                programa=nome_programa,
                matriculas=matriculas,
                hora_aluno=hora_aluno,
                receita=receita
            )

            desempenho_uos.append({
                "uo": nome_uo,
                "matriculas": matriculas,
                "hora_aluno": hora_aluno,
                "receita": receita,
                "analise": analise_uo
            })

            desempenho_uos_programa.append({
                "uo": nome_uo,
                "matriculas": matriculas,
                "hora_aluno": hora_aluno,
                "receita": receita,
                "analise": analise_uo
            })

            if subregiao_nome not in subregioes_detalhadas:
                subregioes_detalhadas[subregiao_nome] = {}

            if nome_programa not in subregioes_detalhadas[subregiao_nome]:
                subregioes_detalhadas[subregiao_nome][nome_programa] = []

            subregioes_detalhadas[subregiao_nome][nome_programa].append({
                "uo": nome_uo,
                "matriculas": matriculas,
                "hora_aluno": hora_aluno,
                "receita": receita,
                "analise": analise_uo
            })

        desempenho_programas_detalhado.append({
            "programa": nome_programa,
            "uos": desempenho_uos_programa
        })

    preview["desempenho_uos"] = desempenho_uos

    preview["desempenho_programas_detalhado"] = (
        desempenho_programas_detalhado
    )

    preview["desempenho_subregioes_detalhado"] = [
        {
            "subregiao": nome_subregiao,
            "programas": [
                {
                    "programa": nome_programa,
                    "uos": uos_programa
                }
                for nome_programa, uos_programa
                in programas_subregiao.items()
            ]
        }
        for nome_subregiao, programas_subregiao
        in subregioes_detalhadas.items()
    ]

    return preview