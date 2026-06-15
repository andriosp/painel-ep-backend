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

    sql_debug_turmas = f"""
        WITH ofertas_base AS (
            SELECT DISTINCT
                o.codigo,
                o.cod_programa,
                o.cod_uo
            FROM ofertas_programas o
            WHERE {where_oferta}
            AND ${idx_mes}::int[] IS NOT NULL
        )

        SELECT
            t.codigo_sge,
            t.cod_programa,
            t.cod_uo,
            t.data_inicio,
            t.data_ini_contratoapr,
            t.ano_referencia
        FROM turmas t
        JOIN ofertas_base ob
            ON ob.cod_programa = t.cod_programa
        AND ob.cod_uo = t.cod_uo
        WHERE t.ano_referencia = $1
        ORDER BY
            t.data_inicio NULLS LAST,
            t.data_ini_contratoapr NULLS LAST
    """

    debug_turmas = await conn.fetch(sql_debug_turmas, *params)

    print("\nDEBUG TURMAS")
    print("TOTAL TURMAS ENCONTRADAS SEM FILTRO DE DATA:", len(debug_turmas))

    for t in debug_turmas:
        print(
            t["codigo_sge"],
            "cod_programa:", t["cod_programa"],
            "cod_uo:", t["cod_uo"],
            "data_inicio:", t["data_inicio"],
            "data_ini_contratoapr:", t["data_ini_contratoapr"],
            "ano:", t["ano_referencia"],
        )

    sql_evolucao = f"""
    WITH ofertas_base AS (
        SELECT DISTINCT
            o.codigo
        FROM ofertas_programas o
        WHERE {where_oferta}
            AND $2::int[] IS NOT NULL
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

        WHERE {where_planejamento}

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

        evolucao_mensal["matriculas"]["realizado"].append(
            float(row_evo["matriculas_real"] or 0) if mes in meses_selecionados else None
        )
        evolucao_mensal["matriculas"]["meta"].append(
            float(row_evo["matriculas_meta"] or 0)
        )

        evolucao_mensal["hora_aluno"]["realizado"].append(
            float(row_evo["ha_real"] or 0) if mes in meses_selecionados else None
        )
        evolucao_mensal["hora_aluno"]["meta"].append(
            float(row_evo["ha_meta"] or 0)
        )

        evolucao_mensal["receita"]["realizado"].append(
            float(row_evo["receita_real"] or 0) if mes in meses_selecionados else None
        )
        evolucao_mensal["receita"]["meta"].append(
            float(row_evo["receita_meta"] or 0)
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

    print("DEBUG REGIÕES")
    print("Programa:", filtros.programa)
    print("Região:", filtros.regiao)

    for r in regioes_rows:
        print(
            r["regiao"],
            r["matriculas_real"],
            r["matriculas_meta"]
        )

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

    print("DEBUG SUBREGIÕES")
    for r in subregioes_rows:
        print(
            r["subregiao"],
            "MAT:",
            r["matriculas_real"],
            "/",
            r["matriculas_meta"],
            "HA:",
            r["ha_real"],
            "/",
            r["ha_meta"],
            "REC:",
            r["receita_real"],
            "/",
            r["receita_meta"],
        )

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

    print("\n========================")
    print("DEBUG SQL MODALIDADES")
    print("========================")
    print("WHERE_OFERTA:", where_oferta)
    print("WHERE_PLANEJAMENTO:", where_planejamento)
    print("PARAMS:", params)

    sql_debug_ofertas = f"""
        SELECT
            COUNT(*) AS total_ofertas
        FROM ofertas_programas o
        WHERE {where_oferta}
        AND ${idx_mes}::int[] IS NOT NULL
    """

    debug_ofertas = await conn.fetchrow(sql_debug_ofertas, *params)

    print("TOTAL OFERTAS_BASE:", debug_ofertas["total_ofertas"])

    modalidades_rows = await conn.fetch(sql_modalidades, *params)

    print("\nDEBUG MODALIDADES")

    for r in modalidades_rows:
        print(
            r["modalidade"],
            "MAT:",
            r["matriculas_real"],
            "/",
            r["matriculas_meta"]
        )

    print("TOTAL MODALIDADES:", len(modalidades_rows))


    for r in modalidades_rows:
        print(
            r["modalidade"],
            "MAT:",
            r["matriculas_real"],
            "/",
            r["matriculas_meta"]
        )

    print("TOTAL MODALIDADES:", len(modalidades_rows))


    for r in modalidades_rows:
        print(
            r["modalidade"],
            "MAT:",
            r["matriculas_real"],
            "/",
            r["matriculas_meta"]
        )

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

            print("\nDEBUG REGIAO UO")
            print("REGIAO_UO:", regiao_uo)
            print("ROW_REG_CTX:", row_reg_ctx)

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
            
            print(
                "MAT:",
                row_reg_ctx["matriculas_real"],
                "/",
                row_reg_ctx["matriculas_meta"]
            )

            print(
                "HA:",
                row_reg_ctx["ha_real"],
                "/",
                row_reg_ctx["ha_meta"]
            )

            print(
                "REC:",
                row_reg_ctx["receita_real"],
                "/",
                row_reg_ctx["receita_meta"]
            )
        
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