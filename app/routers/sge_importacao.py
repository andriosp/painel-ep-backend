import io
import hashlib
import json
import pandas as pd
import math
import tempfile
import os
import secrets
import asyncpg

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Response
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel
from pathlib import Path
from pydantic import BaseModel

router = APIRouter()

SESSOES_ATIVAS = {}

LOGIN_USUARIO = "admin"
LOGIN_SENHA = "123456"


class LoginPayload(BaseModel):
    usuario: str
    senha: str
    lembrar: bool = False

class EsqueciSenhaPayload(BaseModel):
    identificador: str

class RedefinirSenhaPayload(BaseModel):
    token: str
    senha: str

class AlterarSenhaPayload(BaseModel):
    senha_atual: str
    nova_senha: str

class ResetSolicitacaoAtenderPayload(BaseModel):
    id: int

class ResetDefinirSenhaTemporariaPayload(BaseModel):
    solicitacao_id: int
    nova_senha: str

class CriarUsuarioPayload(BaseModel):
    nome: str
    usuario: str
    email: str | None = None
    perfil_id: int
    ativo: bool = True

class AtualizarUsuarioPayload(BaseModel):
    nome: str
    email: str | None = None
    perfil_id: int
    ativo: bool

ABAS_PLANEJAMENTO = [
    "Consolidado Projetado e Meta",
]

MESES_MAPA = {
    "JAN": "jan",
    "FEV": "fev",
    "MAR": "mar",
    "ABR": "abr",
    "MAI": "mai",
    "JUN": "jun",
    "JUL": "jul",
    "AGO": "ago",
    "SET": "set_",
    "OUT": "out_",
    "NOV": "nov",
    "DEZ": "dez",
    "TOTAL": "total",
}

def norm_decimal(v):
    if pd.isna(v) or v in ("", None):
        return None

    try:
        if isinstance(v, (int, float)):
            return int(math.floor(float(v) + 0.5))

        s = str(v).strip().replace("\xa0", "")

        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")

        return int(math.floor(float(s) + 0.5))

    except Exception:
        return None

def norm_upper(v):
    s = norm_text(v)
    return s.upper() if s else None

def detectar_coluna(df, candidatos):
    def norm_col(s):
        return (
            str(s)
            .replace("\xa0", " ")
            .replace(".", "")
            .strip()
            .upper()
        )

    cols = {norm_col(c): c for c in df.columns}
    for nome in candidatos:
        chave = norm_col(nome)
        if chave in cols:
            return cols[chave]
    return None

COLUNAS_OBRIGATORIAS = [
    "CODFILIAL",
    "NOMEFANTASIA",
    "CODCURSO",
    "CURSO",
    "MODALIDADE",
    "CODTURMA",
    "TIPO_MEDIACAOTURMA",
    "DTINICIAL",
    "DTFINAL",
    "PERIODO_LETIVO",
    "ITEM_CONTABIL_MATRIZ",
    "TURNO_TURMA_DISC",
    "NRO_MAX_PREVISTOS_ALUNOS",
    "QTD_MATRICULAS_MATRICULADO",
    "QTD_MATRICULAS_PRE_MATRICULADO",
    "QTD_MATRICULAS_CANCELADO",
    "QTD_MATRICULAS_DESISTENTE",
    "QTD_MATRICULAS_EVADIDO",
    "QTD_MATRICULAS_FALECIDO",
]

COLUNAS_OBRIGATORIAS_MATRICULAS = [
    "CODTURMA",
    "RA",
    "DTMATRICULA",
    "STATUS_PLETIVO",
    "STATUS_CURSO",
    "SENAI_CONDICAO_ALUNO_CURSO",
]

def norm_cr(v):
    s = norm_text(v)
    if not s:
        return None
    return "".join(ch for ch in s if ch.isdigit())

def norm_text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None

def norm_int(v):
    if pd.isna(v) or v in ("", None):
        return None

    s = str(v).strip().replace("\xa0", "").replace(",", ".")

    try:
        return int(float(s))
    except Exception:
        raise ValueError(f"Valor inválido para inteiro: {v!r}")

def norm_date(v):
    if pd.isna(v) or v in ("", None):
        return None
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None

def hash_linha(payload: dict) -> str:
    bruto = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()

def condicao_aluno_clause(alias: str, idx: int) -> str:
    return f"""
    (
        CASE
            WHEN
                TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) = '1'
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) LIKE '1 - %GRATUIDADE REGIMENTAL%'
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) = 'GRATUIDADE REGIMENTAL'
            THEN 'GRATUIDADE REGIMENTAL'

            WHEN
                TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) = '2'
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) LIKE '2 - %GRATUIDADE NÃO REGIMENTAL%'
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) LIKE '2 - %GRATUIDADE NAO REGIMENTAL%'
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) = 'GRATUIDADE NÃO REGIMENTAL'
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) = 'GRATUIDADE NAO REGIMENTAL'
            THEN 'GRATUIDADE NÃO REGIMENTAL'

            WHEN
                TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) IN ('0', '3', '104')
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) LIKE '0 - %PAGO%'
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) LIKE '104 - %NOVO BRASIL%'
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) = 'PAGO'
            THEN 'PAGO'

            WHEN
                TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) IN ('4', 'INDEFINIDO')
                OR TRIM(UPPER(COALESCE({alias}.condicao_aluno, ''))) LIKE '%INDEFINIDO%'
            THEN 'INDEFINIDO'

            ELSE NULL
        END
    ) = ${idx}
    """

def normalizar_subregiao(v):
    s = norm_text(v)
    if not s:
        return None

    s = s.upper().strip()

    # regra de negócio
    if s.startswith("SUL"):
        return "SUL"

    return s

def aplicar_filtros_turmas_base(
    sql: str,
    params: list,
    idx: int,
    *,
    alias_t: str,
    alias_c: str,
    alias_u: str,
    alias_frm: str,
    alias_trn: str,
    alias_tsr: str,
    uo: str | None = None,
    curso: str | None = None,
    modalidade: str | None = None,
    programa: str | None = None,
    turma: str | None = None,
    condicao_aluno: str | None = None,
    dt_inicio_de: str | None = None,
    dt_inicio_ate: str | None = None,
    formato: str | None = None,
    turno: str | None = None,
    status_matricula: str | None = None,
    faixa_preenchimento: str | None = None,
    dt_mat_de: str | None = None,
    dt_mat_ate: str | None = None,
    usar_filtro_padrao: bool = False,
    data_fim_padrao=None,
):
    if uo:
        sql += f" AND {alias_u}.codigo = ${idx}"
        params.append(int(uo))
        idx += 1

    if curso:
        sql += f" AND UPPER(TRIM({alias_c}.nome_curso)) LIKE UPPER(TRIM(${idx}))"
        params.append(f"%{curso.strip()}%")
        idx += 1

    if turma:
        sql += f" AND {alias_t}.codigo_sge = ${idx}"
        params.append(turma)
        idx += 1

    if condicao_aluno:
        sql += f"""
        AND EXISTS (
            SELECT 1
            FROM sge_turma_detalhe_alunos da_cond
            WHERE TRIM(UPPER(COALESCE(da_cond.cod_turma, ''))) = TRIM(UPPER(COALESCE({alias_t}.codigo_sge, '')))
            AND regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(da_cond.condicao_aluno, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                =
                regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(${idx}, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
        )
        """
        params.append(condicao_aluno)
        idx += 1
    
    if modalidade:
        sql += f" AND {alias_t}.cod_modalidade = ${idx}"
        params.append(int(modalidade))
        idx += 1

    if programa:
        sql += f" AND {alias_t}.cod_programa = ${idx}"
        params.append(int(programa))
        idx += 1

    if dt_inicio_de:
        sql += f" AND {alias_t}.data_inicio >= ${idx}"
        params.append(datetime.fromisoformat(dt_inicio_de).date())
        idx += 1

    if dt_inicio_ate:
        sql += f" AND {alias_t}.data_fim <= ${idx}"
        params.append(datetime.fromisoformat(dt_inicio_ate).date())
        idx += 1

    if formato:
        sql += f" AND UPPER(COALESCE({alias_frm}.nome, '')) = ${idx}"
        params.append(formato.strip().upper())
        idx += 1

    if turno:
        sql += f" AND UPPER(COALESCE({alias_trn}.nome, '')) = ${idx}"
        params.append(turno.strip().upper())
        idx += 1

    if status_matricula:
        status_up = status_matricula.strip().upper()

        if status_up == "MATRICULADO":
            sql += f" AND COALESCE({alias_tsr}.matriculados, 0) > 0"
        elif status_up in ("PRE_MATRICULADO", "PRE-MATRICULADO", "PRÉ-MATRICULADO"):
            sql += f" AND COALESCE({alias_tsr}.pre_matriculados, 0) > 0"
        elif status_up == "CANCELADO":
            sql += f" AND COALESCE({alias_tsr}.cancelados, 0) > 0"
        elif status_up == "DESISTENTE":
            sql += f" AND COALESCE({alias_tsr}.desistentes, 0) > 0"
        elif status_up == "EVADIDO":
            sql += f" AND COALESCE({alias_tsr}.evadidos, 0) > 0"
        elif status_up == "FALECIDO":
            sql += f" AND COALESCE({alias_tsr}.falecidos, 0) > 0"

    if faixa_preenchimento:
        pct_expr = f"""
        CASE
            WHEN COALESCE({alias_t}.vagas_total, 0) = 0 THEN NULL
            ELSE (
                (
                    COALESCE({alias_tsr}.matriculados, 0)
                    + COALESCE({alias_tsr}.pre_matriculados, 0)
                )::numeric / COALESCE({alias_t}.vagas_total, 0)::numeric
            ) * 100
        END
        """

        if faixa_preenchimento == "100":
            sql += f" AND ({pct_expr}) >= 100"
        elif faixa_preenchimento == "90_99":
            sql += f" AND ({pct_expr}) >= 90 AND ({pct_expr}) < 100"
        elif faixa_preenchimento == "80_89":
            sql += f" AND ({pct_expr}) >= 80 AND ({pct_expr}) < 90"
        elif faixa_preenchimento == "70_79":
            sql += f" AND ({pct_expr}) >= 70 AND ({pct_expr}) < 80"
        elif faixa_preenchimento == "lt_70":
            sql += f" AND ({pct_expr}) < 70"

    if dt_mat_de or dt_mat_ate or status_matricula:
        sql += f"""
        AND EXISTS (
            SELECT 1
            FROM sge_turma_detalhe_alunos da2
            WHERE TRIM(UPPER(COALESCE(da2.cod_turma, ''))) = TRIM(UPPER(COALESCE({alias_t}.codigo_sge, '')))
        """

        if dt_mat_de:
            sql += f" AND da2.data_matricula >= ${idx}"
            params.append(datetime.fromisoformat(dt_mat_de).date())
            idx += 1

        if dt_mat_ate:
            sql += f" AND da2.data_matricula <= ${idx}"
            params.append(datetime.fromisoformat(dt_mat_ate).date())
            idx += 1

        if status_matricula:
            status_up = status_matricula.strip().upper()

            if status_up in ("PRE_MATRICULADO", "PRE-MATRICULADO", "PRÉ-MATRICULADO"):
                sql += """
                AND TRIM(UPPER(COALESCE(da2.status_matricula, ''))) IN (
                    'PRE_MATRICULADO',
                    'PRE-MATRICULADO',
                    'PRÉ-MATRICULADO'
                )
                """
            else:
                sql += f" AND TRIM(UPPER(COALESCE(da2.status_matricula, ''))) = ${idx}"
                params.append(status_up)
                idx += 1

        sql += ")"

    if usar_filtro_padrao and data_fim_padrao:
        sql += f" AND {alias_t}.data_fim >= ${idx}"
        params.append(data_fim_padrao)
        idx += 1

    return sql, params, idx

@router.post("/importacoes/planejamento")
async def importar_planejamento(request: Request, arquivo: UploadFile = File(...), ano_referencia: int = 2026):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo não informado.")

    nome = arquivo.filename.lower()
    if not (nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Envie um arquivo Excel .xlsx ou .xls.")

    conteudo = await arquivo.read()
    hash_arquivo = hashlib.sha256(conteudo).hexdigest()

    try:
        xls = pd.ExcelFile(io.BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler Excel: {e}")

    abas_encontradas = [a for a in ABAS_PLANEJAMENTO if a in xls.sheet_names]
    if not abas_encontradas:
        raise HTTPException(
            status_code=400,
            detail=f"Nenhuma das abas esperadas foi encontrada. Abas esperadas: {ABAS_PLANEJAMENTO}"
        )

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote = await conn.fetchrow(
                """
                INSERT INTO planejamento_import_lotes (
                    nome_arquivo, hash_arquivo, ano_referencia, status_processamento
                )
                VALUES ($1, $2, $3, 'importado')
                RETURNING id
                """,
                arquivo.filename,
                hash_arquivo,
                ano_referencia,
            )
            lote_id = lote["id"]

            registros = []
            total_validas = 0
            total_invalidas = 0

            for aba in abas_encontradas:
                df = pd.read_excel(io.BytesIO(conteudo), sheet_name=aba)
                df.columns = [str(c).replace("\xa0", " ").strip() for c in df.columns]
                ##df = df.drop_duplicates()
                print("COLUNAS NORMALIZADAS:")
                for c in df.columns:
                    print(repr(c))
                print("COLUNAS DA ABA:", aba)
                for c in df.columns:
                    print(">>", c)

                col_tipo = detectar_coluna(df, ["TIPO"])
                col_conta = detectar_coluna(df, ["CONTA"])
                col_regiao = detectar_coluna(df, ["REGIÃO", "REGIAO"])
                col_subregiao = detectar_coluna(df, ["SUB-REGIÃO", "SUBREGIÃO", "SUBREGIAO", "SUB REGIAO"])
                col_modalidade = detectar_coluna(df, ["MODALIDADE"])
                col_formato = detectar_coluna(df, ["FORMATO"])
                col_uo = detectar_coluna(df, ["CÓD. UO", "CÓD UO", "Cód UO", "COD. UO", "COD_UO", "COD UO", "UO"])
                col_cod_modalidade = detectar_coluna(df, ["COD_MODALIDADE", "COD MODALIDADE"])
                col_cod_cr = detectar_coluna(df, ["COD_CR", "COD CR"])
                col_cod_programa = detectar_coluna(df, ["COD_PROGRAMA", "COD PROGRAMA"])
                col_cod_formato = detectar_coluna(df, ["COD_FORMATO", "COD FORMATO"])
                col_cod_fin = detectar_coluna(df, ["COD_FIN", "COD FIN"])
                col_desc_uo = detectar_coluna(df, ["DESC. UO", "DESCRIÇÃO UO", "DESCRICAO UO", "UNIDADE OPERACIONAL"])
                col_cr = detectar_coluna(df, [
                    "CR",
                    "C.R.",
                    "CENTRO DE RESPONSABILIDADE",
                    "CENTRO DE CUSTO",
                    "CENTRO RESPONSABILIDADE",
                    "COD CR",
                    "CODIGO CR",
                    "CÓD. CR",
                    "CÓDIGO CR",
                    "CÓD. CENTRO DE CUSTO",
                    "COD. CENTRO DE CUSTO",
                    "Cód. Centro de custo",
                    "Cód Centro de Responsabilidade"  # 👈 ESSA É A CORRETA
                ])
                col_cr_desc = detectar_coluna(df, [
                    "DESC. CR",
                    "DESCRIÇÃO CR",
                    "DESCRICAO CR",
                    "DESCRIÇÃO DO CENTRO DE CUSTO",
                    "DESCRICAO DO CENTRO DE CUSTO"
                ])
                col_programa = detectar_coluna(df, ["PROGRAMA"])
                col_financiamento = detectar_coluna(df, ["FINANCIAMENTO"])

                colunas_obrigatorias = {
                    "TIPO": col_tipo,
                    "CONTA": col_conta,
                    "PROGRAMA": col_programa,
                }
                faltantes = [k for k, v in colunas_obrigatorias.items() if v is None]
                if faltantes:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Aba '{aba}' sem colunas obrigatórias: {faltantes}"
                    )

                for idx, row in df.iterrows():
                    payload = {
                        "tipo": norm_upper(row.get(col_tipo)) if col_tipo else None,
                        "conta": norm_upper(row.get(col_conta)) if col_conta else None,
                        "regiao": norm_text(row.get(col_regiao)) if col_regiao else None,
                        "subregiao": normalizar_subregiao(row.get(col_subregiao)),
                        "modalidade_raw": norm_text(row.get(col_modalidade)) if col_modalidade else None,
                        "formato_raw": norm_text(row.get(col_formato)) if col_formato else None,
                        "cod_uo_raw": norm_text(row.get(col_uo)) if col_uo else None,
                        "desc_uo_raw": norm_text(row.get(col_desc_uo)) if col_desc_uo else None,
                        "cr_raw": norm_cr(row.get(col_cr)) if col_cr else None,
                        "cr_desc_raw": norm_text(row.get(col_cr_desc)) if col_cr_desc else None,
                        "programa_raw": norm_text(row.get(col_programa)) if col_programa else None,
                        "financiamento_raw": norm_text(row.get(col_financiamento)) if col_financiamento else None,
                        "cod_modalidade_raw": norm_text(row.get(col_cod_modalidade)) if col_cod_modalidade else None,
                        "cod_cr_raw": norm_text(row.get(col_cod_cr)) if col_cod_cr else None,
                        "cod_programa_raw": norm_text(row.get(col_cod_programa)) if col_cod_programa else None,
                        "cod_formato_raw": norm_text(row.get(col_cod_formato)) if col_cod_formato else None,
                        "cod_fin_raw": norm_text(row.get(col_cod_fin)) if col_cod_fin else None,
                        "jan": norm_decimal(row.get(detectar_coluna(df, ["JAN"]))),
                        "fev": norm_decimal(row.get(detectar_coluna(df, ["FEV"]))),
                        "mar": norm_decimal(row.get(detectar_coluna(df, ["MAR"]))),
                        "abr": norm_decimal(row.get(detectar_coluna(df, ["ABR"]))),
                        "mai": norm_decimal(row.get(detectar_coluna(df, ["MAI"]))),
                        "jun": norm_decimal(row.get(detectar_coluna(df, ["JUN"]))),
                        "jul": norm_decimal(row.get(detectar_coluna(df, ["JUL"]))),
                        "ago": norm_decimal(row.get(detectar_coluna(df, ["AGO"]))),
                        "set_": norm_decimal(row.get(detectar_coluna(df, ["SET"]))),
                        "out_": norm_decimal(row.get(detectar_coluna(df, ["OUT"]))),
                        "nov": norm_decimal(row.get(detectar_coluna(df, ["NOV"]))),
                        "dez": norm_decimal(row.get(detectar_coluna(df, ["DEZ"]))),
                        "total": norm_decimal(row.get(detectar_coluna(df, ["TOTAL"]))),
                    }

                    erros = []

                    if not payload["tipo"] or payload["tipo"] not in ("META", "PROJETADO"):
                        erros.append("TIPO inválido")
                    if not payload["conta"]:
                        erros.append("CONTA vazia")
                    if not payload["programa_raw"]:
                        erros.append("PROGRAMA vazio")

                    linha_vazia = (
                        not payload["programa_raw"]
                        and not payload["modalidade_raw"]
                        and not payload["formato_raw"]
                        and not payload["cr_raw"]
                        and not payload["cod_uo_raw"]
                        and not payload["total"]
                    )
                    if linha_vazia:
                        continue

                    flag_valida = len(erros) == 0
                    if flag_valida:
                        total_validas += 1
                    else:
                        total_invalidas += 1

                    registros.append((
                        lote_id,
                        aba,
                        idx + 2,
                        payload["tipo"],
                        payload["conta"],
                        payload["regiao"],
                        payload["subregiao"],
                        payload["modalidade_raw"],
                        payload["cod_modalidade_raw"],
                        payload["formato_raw"],
                        payload["cod_uo_raw"],
                        payload["desc_uo_raw"],
                        payload["cr_raw"],
                        payload["cr_desc_raw"],
                        payload["programa_raw"],
                        payload["financiamento_raw"],
                        payload["jan"],
                        payload["fev"],
                        payload["mar"],
                        payload["abr"],
                        payload["mai"],
                        payload["jun"],
                        payload["jul"],
                        payload["ago"],
                        payload["set_"],
                        payload["out_"],
                        payload["nov"],
                        payload["dez"],
                        payload["total"],
                        flag_valida,
                        "; ".join(erros) if erros else None,
                    ))

            # ⬇️ INSERT NO BANCO
            
            if registros:
                await conn.executemany(
                    """
                    INSERT INTO planejamento_staging (
                        lote_id, aba_origem, linha_numero, tipo, conta,
                        regiao, subregiao, modalidade_raw, cod_modalidade_raw, formato_raw,
                        cod_uo_raw, desc_uo_raw, cr_raw, cr_desc_raw,
                        programa_raw, financiamento_raw,
                        jan, fev, mar, abr, mai, jun, jul, ago, set_, out_, nov, dez, total,
                        flag_valida, erro_validacao
                    )
                    VALUES (
                        $1,$2,$3,$4,$5,
                        $6,$7,$8,$9,
                        $10,$11,$12,$13,
                        $14,$15,
                        $16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,
                        $29,$30,$31
                    )
                    """,
                    registros
                )

            await conn.execute(
                """
                UPDATE planejamento_import_lotes
                SET total_linhas = $2,
                    total_validas = $3,
                    total_invalidas = $4
                WHERE id = $1
                """,
                lote_id,
                len(registros),
                total_validas,
                total_invalidas
            )

    return {
        "ok": True,
        "lote_id": lote_id,
        "arquivo": arquivo.filename,
        "abas_processadas": abas_encontradas,
        "linhas_importadas": len(registros),
        "validas": total_validas,
        "invalidas": total_invalidas,
    }

@router.get("/importacoes/planejamento/lotes")
async def listar_lotes_planejamento(request: Request):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                nome_arquivo,
                ano_referencia,
                data_importacao,
                status_processamento,
                total_linhas,
                total_validas,
                total_invalidas
            FROM planejamento_import_lotes
            ORDER BY id DESC
            LIMIT 20
            """
        )

    return [dict(r) for r in rows]

@router.get("/importacoes/planejamento/resumo/{lote_id}")
async def resumo_lote_planejamento(request: Request, lote_id: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT *
            FROM planejamento_import_lotes
            WHERE id = $1
            """,
            lote_id
        )

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado.")

        resumo = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE flag_valida = TRUE) AS validas,
                COUNT(*) FILTER (WHERE flag_valida = FALSE) AS invalidas
            FROM planejamento_staging
            WHERE lote_id = $1
            """,
            lote_id
        )

        erros = await conn.fetch(
            """
            SELECT
                aba_origem,
                linha_numero,
                tipo,
                conta,
                programa_raw,
                erro_validacao
            FROM planejamento_staging
            WHERE lote_id = $1
              AND flag_valida = FALSE
            ORDER BY aba_origem, linha_numero
            LIMIT 100
            """,
            lote_id
        )

    return {
        "lote": dict(lote),
        "resumo": dict(resumo),
        "erros": [dict(r) for r in erros],
    }

@router.post("/importacoes/planejamento/processar/{lote_id}")
async def processar_planejamento(request: Request, lote_id: int):
    print(f"🚀 INICIANDO PROCESSAMENTO DO PLANEJAMENTO - LOTE {lote_id}", flush=True)
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT *
            FROM planejamento_import_lotes
            WHERE id = $1
            """,
            lote_id
        )

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado.")

        total_validas = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM planejamento_staging
            WHERE lote_id = $1
              AND flag_valida = TRUE
            """,
            lote_id
        )

        if not total_validas:
            raise HTTPException(status_code=400, detail="Lote sem linhas válidas para processar.")
        
        ano_ref = lote["ano_referencia"]

        # limpa dados já processados do ano antes de recriar tudo
        await conn.execute(
            """
            DELETE FROM meta_programas
            WHERE ano = $1
            """,
            ano_ref
        )

        await conn.execute(
            """
            DELETE FROM projetado_programas
            WHERE ano = $1
            """,
            ano_ref
        )

        batch_size = 100
        offset = 0
        linhas_avaliadas = 0
        problemas = []

        programas_map = {
            row["nome_programa"].strip().upper(): row["codigo"]
            for row in await conn.fetch("SELECT codigo, nome_programa FROM programas")
        }

        financiamentos_map = {
            row["nome_financiamento"].strip().upper(): row["codigo"]
            for row in await conn.fetch("SELECT codigo, nome_financiamento FROM financiamento")
        }

        cr_uo_map = {
            row["cr"]: row["cod_uo"]
            for row in await conn.fetch("SELECT cr, cod_uo FROM cr_planejamento")
        }

        ofertas_map = {}

        rows_uo = await conn.fetch(
            """
            SELECT codigo_sge, codigo
            FROM uo
            WHERE codigo_sge IS NOT NULL
            """
        )
        uo_map = {str(r["codigo_sge"]).strip(): r["codigo"] for r in rows_uo}

        rows_modalidade = await conn.fetch(
            """
            SELECT codigo, UPPER(nome) AS nome
            FROM modalidade
            """
        )
        modalidade_map = {r["nome"]: r["codigo"] for r in rows_modalidade}
        print("🔄 Entrando no loop de processamento do planejamento", flush=True)
        while True:
            rows = await conn.fetch(
                """
                SELECT *
                FROM planejamento_staging
                WHERE lote_id = $1
                  AND flag_valida = TRUE
                ORDER BY id
                LIMIT $2 OFFSET $3
                """,
                lote_id,
                batch_size,
                offset
            )

            print(f"📦 Lote {lote_id} - offset {offset} - linhas carregadas: {len(rows)}", flush=True)

            if not rows:
                break

            linhas_avaliadas += len(rows)

            meta_buffer = {}
            proj_buffer = {}

            for i, r in enumerate(rows, start=1):
                print(
                    f"➡️ Processando linha {i} | id={r['id']} | "
                    f"tipo={r['tipo']} | conta={r['conta']} | "
                    f"programa={r['programa_raw']} | subregiao={r['subregiao']}",
                    flush=True
                )

                # -----------------------------
                # PROGRAMA
                # -----------------------------
                programa_nome = r["programa_raw"].strip().upper()

                cod_programa = programas_map.get(programa_nome)

                if cod_programa is None:
                    row_prog = await conn.fetchrow(
                        """
                        INSERT INTO programas (nome_programa)
                        VALUES ($1)
                        RETURNING codigo
                        """,
                        r["programa_raw"].strip()
                    )
                    cod_programa = row_prog["codigo"]
                    programas_map[programa_nome] = cod_programa

                # -----------------------------
                # FINANCIAMENTO
                # -----------------------------
                cod_financiamento = None

                if r["financiamento_raw"]:
                    fin_nome = r["financiamento_raw"].strip().upper()

                    cod_financiamento = financiamentos_map.get(fin_nome)

                    if cod_financiamento is None:
                        row_fin = await conn.fetchrow(
                            """
                            INSERT INTO financiamento (nome_financiamento)
                            VALUES ($1)
                            RETURNING codigo
                            """,
                            r["financiamento_raw"].strip()
                        )
                        cod_financiamento = row_fin["codigo"]
                        financiamentos_map[fin_nome] = cod_financiamento

                ano = lote["ano_referencia"]
                cr = r["cr_raw"]

                # -----------------------------
                # UO VIA ARQUIVO (prioridade) / CR (fallback)
                # -----------------------------
                cod_uo = None
                valor_uo_raw = r["cod_uo_raw"]

                if valor_uo_raw is not None:
                    s_uo = str(valor_uo_raw).strip()
                    if s_uo and s_uo.lower() != "nan":
                        chave_uo = str(int(float(s_uo)))
                        cod_uo = uo_map.get(chave_uo)
                
                # -----------------------------
                # MODALIDADE
                # -----------------------------

                cod_modalidade_raw = r["cod_modalidade_raw"] if "cod_modalidade_raw" in r else None

                if cod_modalidade_raw is not None:
                    try:
                        cod_modalidade_tmp = int(float(str(cod_modalidade_raw).strip()))
                        existe_mod = await conn.fetchval(
                            "SELECT codigo FROM modalidade WHERE codigo = $1",
                            cod_modalidade_tmp
                        )
                        if existe_mod:
                            cod_modalidade = cod_modalidade_tmp
                    except Exception:
                        pass

                # 2) se não conseguiu pelo código, tenta pelo nome
                if cod_modalidade is None:
                    modalidade_nome = (r["modalidade_raw"] or "").strip().upper()

                    if modalidade_nome:
                        cod_modalidade = modalidade_map.get(modalidade_nome)

                        if cod_modalidade is None:
                            row_mod = await conn.fetchrow(
                                """
                                INSERT INTO modalidade (nome)
                                VALUES ($1)
                                RETURNING codigo
                                """,
                                modalidade_nome
                            )
                            cod_modalidade = row_mod["codigo"]
                            modalidade_map[modalidade_nome] = cod_modalidade

                # -----------------------------
                # OFERTA
                # -----------------------------
                chave_oferta = (
                    cod_programa,
                    cod_financiamento,
                    ano,
                    cr,
                    cod_uo or 0,
                    cod_modalidade or 0,
                )

                cod_oferta = ofertas_map.get(chave_oferta)

                if cod_oferta is None:
                    oferta_existente = await conn.fetchrow(
                        """
                        SELECT codigo
                        FROM ofertas_programas
                        WHERE cod_programa = $1
                        AND COALESCE(cod_financiamento, 0) = COALESCE($2, 0)
                        AND ano = $3
                        AND COALESCE(cr, '') = COALESCE($4, '')
                        AND COALESCE(cod_uo, 0) = COALESCE($5, 0)
                        AND COALESCE(cod_modalidade, 0) = COALESCE($6, 0)
                        LIMIT 1
                        """,
                        cod_programa,
                        cod_financiamento,
                        ano,
                        cr,
                        cod_uo,
                        cod_modalidade
                    )

                    if oferta_existente:
                        cod_oferta = oferta_existente["codigo"]
                    else:
                        oferta = await conn.fetchrow(
                            """
                            INSERT INTO ofertas_programas (
                                cod_programa,
                                cod_financiamento,
                                ano,
                                cr,
                                cod_uo,
                                cod_modalidade
                            )
                            VALUES ($1, $2, $3, $4, $5, $6)
                            RETURNING codigo
                            """,
                            cod_programa,
                            cod_financiamento,
                            ano,
                            cr,
                            cod_uo,
                            cod_modalidade
                        )
                        cod_oferta = oferta["codigo"]

                    ofertas_map[chave_oferta] = cod_oferta

                # -----------------------------
                # MESES
                # -----------------------------
                meses = [
                    ("jan", 1), ("fev", 2), ("mar", 3), ("abr", 4),
                    ("mai", 5), ("jun", 6), ("jul", 7), ("ago", 8),
                    ("set_", 9), ("out_", 10), ("nov", 11), ("dez", 12),
                ]

                for campo_mes, num_mes in meses:
                    valor = r[campo_mes]

                    if not valor or valor == 0:
                        continue

                    matriculas = 0
                    ha = 0
                    receita = 0
                    despesa = 0

                    conta = (r["conta"] or "").strip().upper()

                    if conta in ("MATRÍCULAS", "MATRICULAS"):
                        matriculas = valor
                    elif conta in ("HORA ALUNO", "HORA-ALUNO", "HORA_ALUNO"):
                        ha = valor
                    elif conta in ("RECEITAS CORRENTES", "RECEITA", "RECEITAS"):
                        receita = valor
                    elif conta in ("DESPESAS CORRENTES", "DESPESA", "DESPESAS"):
                        despesa = valor

                    if r["tipo"] == "META":
                        chave = (cod_oferta, ano, num_mes)

                        if chave not in meta_buffer:
                            meta_buffer[chave] = [0, 0, 0, 0]

                        meta_buffer[chave][0] += matriculas or 0
                        meta_buffer[chave][1] += ha or 0
                        meta_buffer[chave][2] += receita or 0
                        meta_buffer[chave][3] += despesa or 0

                    elif r["tipo"] == "PROJETADO":
                        chave = (cod_oferta, ano, num_mes)

                        if chave not in proj_buffer:
                            proj_buffer[chave] = [0, 0, 0, 0]

                        proj_buffer[chave][0] += matriculas or 0
                        proj_buffer[chave][1] += ha or 0
                        proj_buffer[chave][2] += receita or 0
                        proj_buffer[chave][3] += despesa or 0

            meta_rows = [
                (cod_oferta, ano, mes, vals[0], vals[1], vals[2], vals[3])
                for (cod_oferta, ano, mes), vals in meta_buffer.items()
            ]
            if meta_rows:
                await conn.executemany(
                    """
                    INSERT INTO meta_programas (
                        cod_oferta, ano, mes,
                        matriculas_meta, ha_meta, receita_meta, despesa_meta
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT (cod_oferta, ano, mes)
                    DO UPDATE SET
                        matriculas_meta = meta_programas.matriculas_meta + EXCLUDED.matriculas_meta,
                        ha_meta = meta_programas.ha_meta + EXCLUDED.ha_meta,
                        receita_meta = meta_programas.receita_meta + EXCLUDED.receita_meta,
                        despesa_meta = meta_programas.despesa_meta + EXCLUDED.despesa_meta
                    """,
                    meta_rows
                )

            proj_rows = [
                (cod_oferta, ano, mes, vals[0], vals[1], vals[2], vals[3])
                for (cod_oferta, ano, mes), vals in proj_buffer.items()
            ]

            if proj_rows:
                await conn.executemany(
                    """
                    INSERT INTO projetado_programas (
                        cod_oferta, ano, mes,
                        matriculas_proj, ha_proj, receita_proj, despesa_proj
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT (cod_oferta, ano, mes)
                    DO UPDATE SET
                        matriculas_proj = projetado_programas.matriculas_proj + EXCLUDED.matriculas_proj,
                        ha_proj = projetado_programas.ha_proj + EXCLUDED.ha_proj,
                        receita_proj = projetado_programas.receita_proj + EXCLUDED.receita_proj,
                        despesa_proj = projetado_programas.despesa_proj + EXCLUDED.despesa_proj
                    """,
                    proj_rows
                )

            offset += batch_size

        # -----------------------------
        # ATUALIZAR AGREGADOS
        # -----------------------------
        await conn.execute(
            """
            UPDATE ofertas_programas o
            SET
                qtd_matriculas = COALESCE((
                    SELECT SUM(m.matriculas_meta)
                    FROM meta_programas m
                    WHERE m.cod_oferta = o.codigo
                    AND m.ano = o.ano
                ), 0),
                qtd_hora_aluno = COALESCE((
                    SELECT SUM(m.ha_meta)
                    FROM meta_programas m
                    WHERE m.cod_oferta = o.codigo
                    AND m.ano = o.ano
                ), 0),
                valor_receita = COALESCE((
                    SELECT SUM(m.receita_meta)
                    FROM meta_programas m
                    WHERE m.cod_oferta = o.codigo
                    AND m.ano = o.ano
                ), 0),
                valor_despesa = COALESCE((
                    SELECT SUM(m.despesa_meta)
                    FROM meta_programas m
                    WHERE m.cod_oferta = o.codigo
                    AND m.ano = o.ano
                ), 0)
            WHERE o.ano = $1
            """,
            lote["ano_referencia"]
        )

        await conn.execute(
            """
            UPDATE planejamento_import_lotes
            SET status_processamento = 'processado'
            WHERE id = $1
            """,
            lote_id
        )

        return {
            "ok": True,
            "lote_id": lote_id,
            "linhas_avaliadas": linhas_avaliadas,
            "problemas": problemas[:100]
        }

def padronizar_nome(v):
    s = norm_text(v)
    return s.upper() if s else None

async def obter_ou_criar_dimensao(conn, tabela: str, coluna_nome: str, valor: str):
    if not valor:
        return None

    row = await conn.fetchrow(
        f"SELECT codigo FROM {tabela} WHERE {coluna_nome} = $1 LIMIT 1",
        valor
    )
    if row:
        return row["codigo"]

    row = await conn.fetchrow(
        f"INSERT INTO {tabela} ({coluna_nome}) VALUES ($1) RETURNING codigo",
        valor
    )
    return row["codigo"]

async def obter_ou_criar_dimensao_cache(conn, cache: dict, tabela: str, coluna_nome: str, valor: str):
    if not valor:
        return None

    chave = valor.strip().upper()
    if chave in cache:
        return cache[chave]

    row = await conn.fetchrow(
        f"SELECT codigo FROM {tabela} WHERE {coluna_nome} = $1 LIMIT 1",
        chave
    )
    if row:
        cache[chave] = row["codigo"]
        return cache[chave]

    row = await conn.fetchrow(
        f"INSERT INTO {tabela} ({coluna_nome}) VALUES ($1) RETURNING codigo",
        chave
    )
    cache[chave] = row["codigo"]
    return cache[chave]

@router.post("/importacoes/matriculas-realizadas")
async def importar_matriculas_realizadas(
    request: Request,
    arquivo: UploadFile = File(...),
    ano_referencia: int = 2026
):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo não informado.")

    nome = arquivo.filename.lower()
    if not (nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Envie um arquivo Excel .xlsx ou .xls.")

    conteudo = await arquivo.read()

    try:
        df = pd.read_excel(io.BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler Excel: {e}")

    df.columns = [str(c).replace("\xa0", " ").strip().lower() for c in df.columns]

    colunas_obrigatorias = [
        "cr",
        "descricao_cr",
        "valor",
        "mes",
        "ano",
        "cod_uo",
        "cod_modalidade",
        "cod_programa",
        "programa",
    ]

    faltantes = [c for c in colunas_obrigatorias if c not in df.columns]
    if faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"Colunas obrigatórias ausentes no Excel: {', '.join(faltantes)}"
        )

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote = await conn.fetchrow(
                """
                INSERT INTO importacao_matriculas_lotes (
                    nome_arquivo, ano_referencia, status,
                    linhas_importadas, validas, invalidas, processadas
                )
                VALUES ($1, $2, 'IMPORTADO', 0, 0, 0, 0)
                RETURNING id
                """,
                arquivo.filename,
                ano_referencia,
            )

            lote_id = lote["id"]

            registros = []
            total_validas = 0
            total_invalidas = 0

            for idx, row in df.iterrows():
                linha_numero = idx + 2

                cr = norm_cr(row.get("cr"))
                descricao_cr = norm_text(row.get("descricao_cr"))
                valor_raw = row.get("valor")
                mes_raw = row.get("mes")
                ano_raw = row.get("ano")
                cod_uo_raw = row.get("cod_uo")
                cod_modalidade_raw = row.get("cod_modalidade")
                cod_programa_raw = row.get("cod_programa")
                programa = norm_text(row.get("programa"))

                linha_vazia = (
                    not cr
                    and not descricao_cr
                    and pd.isna(valor_raw)
                    and pd.isna(mes_raw)
                    and pd.isna(ano_raw)
                    and pd.isna(cod_uo_raw)
                    and pd.isna(cod_modalidade_raw)
                    and pd.isna(cod_programa_raw)
                    and not programa
                )

                if linha_vazia:
                    continue

                erros = []

                valor = None
                mes = None
                ano = None
                cod_uo = None
                cod_modalidade = None
                cod_programa = None

                if not cr:
                    erros.append("CR não informado")

                try:
                    valor = norm_int(valor_raw)
                    if valor is None:
                        continue
                except Exception:
                    erros.append("Valor inválido")

                try:
                    mes = norm_int(mes_raw)
                    if mes is None or mes < 1 or mes > 12:
                        erros.append("Mês inválido")
                except Exception:
                    erros.append("Mês inválido")

                try:
                    ano = norm_int(ano_raw) if not pd.isna(ano_raw) else ano_referencia
                    if ano is None:
                        ano = ano_referencia
                except Exception:
                    erros.append("Ano inválido")

                try:
                    cod_uo = norm_int(cod_uo_raw) if not pd.isna(cod_uo_raw) else None
                except Exception:
                    erros.append("cod_uo inválido")

                try:
                    cod_modalidade = norm_int(cod_modalidade_raw) if not pd.isna(cod_modalidade_raw) else None
                except Exception:
                    erros.append("cod_modalidade inválido")

                try:
                    cod_programa = norm_int(cod_programa_raw) if not pd.isna(cod_programa_raw) else None
                except Exception:
                    erros.append("cod_programa inválido")

                status = "PENDENTE" if not erros else "ERRO"

                if status == "PENDENTE":
                    total_validas += 1
                else:
                    total_invalidas += 1

                registros.append((
                    lote_id,
                    linha_numero,
                    cr,
                    descricao_cr,
                    valor,
                    mes,
                    ano,
                    cod_uo,
                    cod_modalidade,
                    cod_programa,
                    programa,
                    None,
                    status,
                    "; ".join(erros) if erros else None,
                ))

            if registros:
                await conn.executemany(
                    """
                    INSERT INTO importacao_matriculas_staging (
                        lote_id,
                        linha_origem,
                        cr,
                        descricao_cr,
                        valor,
                        mes,
                        ano,
                        cod_uo,
                        cod_modalidade,
                        cod_programa,
                        programa,
                        cod_oferta_resolvido,
                        status,
                        erro
                    )
                    VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14
                    )
                    """,
                    registros
                )

            await conn.execute(
                """
                UPDATE importacao_matriculas_lotes
                SET linhas_importadas = $2,
                    validas = $3,
                    invalidas = $4
                WHERE id = $1
                """,
                lote_id,
                len(registros),
                total_validas,
                total_invalidas
            )

    return {
        "ok": True,
        "lote_id": lote_id,
        "arquivo": arquivo.filename,
        "linhas_importadas": len(registros),
        "validas": total_validas,
        "invalidas": total_invalidas,
    }


@router.post("/importacoes/matriculas-realizadas/processar/{lote_id}")
async def processar_matriculas_realizadas(request: Request, lote_id: int):
    pool = request.app.state.pool
    batch_size = 200

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT *
            FROM importacao_matriculas_lotes
            WHERE id = $1
            """,
            lote_id
        )

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado.")

        await conn.execute(
            """
            UPDATE importacao_matriculas_lotes
            SET status = 'PROCESSANDO',
                processado_em = NULL
            WHERE id = $1
            """,
            lote_id
        )

        ids_rows = await conn.fetch(
            """
            SELECT id
            FROM importacao_matriculas_staging
            WHERE lote_id = $1
              AND status = 'PENDENTE'
            ORDER BY id
            LIMIT $2
            """,
            lote_id,
            batch_size
        )

        ids = [r["id"] for r in ids_rows]

        if not ids:
            processadas = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM importacao_matriculas_staging
                WHERE lote_id = $1
                  AND status IN ('RESOLVIDO', 'AMBIGUO', 'ERRO')
                """,
                lote_id
            )

            erros_total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM importacao_matriculas_staging
                WHERE lote_id = $1
                  AND status = 'ERRO'
                """,
                lote_id
            )

            ambiguas_total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM importacao_matriculas_staging
                WHERE lote_id = $1
                  AND status = 'AMBIGUO'
                """,
                lote_id
            )

            status_final = "PROCESSADO"
            if (erros_total or 0) > 0 or (ambiguas_total or 0) > 0:
                status_final = "PROCESSADO_COM_ERRO"

            await conn.execute(
                """
                UPDATE importacao_matriculas_lotes
                SET status = $2,
                    processadas = $3,
                    processado_em = NOW()
                WHERE id = $1
                """,
                lote_id,
                status_final,
                processadas
            )

            return {
                "ok": True,
                "lote_id": lote_id,
                "linhas_avaliadas": 0,
                "atualizadas": 0,
                "ambiguas": 0,
                "erros": 0
            }

        await conn.execute(
            """
            WITH candidatos AS (
                SELECT
                    s.id AS staging_id,
                    o.codigo AS cod_oferta,
                    COUNT(*) OVER (PARTITION BY s.id) AS qtd
                FROM importacao_matriculas_staging s
                JOIN ofertas_programas o
                  ON o.ano = s.ano
                 AND o.cr = s.cr
                 AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                 AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                 AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                WHERE s.id = ANY($1::bigint[])
                  AND s.status = 'PENDENTE'
            )
            UPDATE importacao_matriculas_staging s
            SET cod_oferta_resolvido = c.cod_oferta,
                status = 'RESOLVIDO',
                erro = NULL
            FROM candidatos c
            WHERE s.id = c.staging_id
              AND c.qtd = 1
            """,
            ids
        )

        await conn.execute(
            """
            WITH candidatos AS (
                SELECT
                    s.id AS staging_id,
                    COUNT(*) AS qtd
                FROM importacao_matriculas_staging s
                JOIN ofertas_programas o
                  ON o.ano = s.ano
                 AND o.cr = s.cr
                 AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                 AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                 AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                WHERE s.id = ANY($1::bigint[])
                  AND s.status = 'PENDENTE'
                GROUP BY s.id
            )
            UPDATE importacao_matriculas_staging s
            SET status = 'AMBIGUO',
                erro = 'Mais de uma oferta encontrada para a combinação exata informada.'
            FROM candidatos c
            WHERE s.id = c.staging_id
              AND c.qtd > 1
              AND s.status = 'PENDENTE'
            """,
            ids
        )

        await conn.execute(
            """
            INSERT INTO ofertas_programas (
                cr,
                ano,
                cod_uo,
                cod_modalidade,
                cod_programa
            )
            SELECT DISTINCT
                s.cr,
                s.ano,
                s.cod_uo,
                s.cod_modalidade,
                s.cod_programa
            FROM importacao_matriculas_staging s
            WHERE s.id = ANY($1::bigint[])
            AND s.status = 'PENDENTE'
            ON CONFLICT DO NOTHING
            """,
            ids
        )

        await conn.execute(
            """
            UPDATE importacao_matriculas_staging s
            SET
                cod_oferta_resolvido = o.codigo,
                status = 'RESOLVIDO',
                erro = NULL
            FROM ofertas_programas o
            WHERE s.id = ANY($1::bigint[])
            AND s.status = 'PENDENTE'
            AND o.ano = s.ano
            AND o.cr = s.cr
            AND COALESCE(o.cod_uo,0)=COALESCE(s.cod_uo,0)
            AND COALESCE(o.cod_modalidade,0)=COALESCE(s.cod_modalidade,0)
            AND COALESCE(o.cod_programa,0)=COALESCE(s.cod_programa,0)
            """,
            ids
        )

        await conn.execute(
            """
            UPDATE realizado_programas rp
            SET matriculas_real = NULL
            WHERE EXISTS (
                SELECT 1
                FROM importacao_matriculas_staging s
                WHERE s.lote_id = $1
                AND s.status = 'RESOLVIDO'
                AND s.cod_oferta_resolvido = rp.cod_oferta
                AND s.ano = rp.ano
                AND s.mes = rp.mes
            )
            """,
            lote_id
        )

        await conn.execute(
            """
            INSERT INTO realizado_programas (
                cod_oferta,
                ano,
                mes,
                matriculas_real,
                ha_real,
                receita_real,
                despesa_real,
                cod_programa
            )
            SELECT
                cod_oferta_resolvido,
                ano,
                mes,
                SUM(valor) AS matriculas_real,
                0,
                0,
                0,
                MAX(cod_programa)
            FROM importacao_matriculas_staging
            WHERE lote_id = $1
            AND status = 'RESOLVIDO'
            AND cod_oferta_resolvido IS NOT NULL
            GROUP BY
                cod_oferta_resolvido,
                ano,
                mes
            ON CONFLICT (cod_oferta, ano, mes)
            DO UPDATE SET
                matriculas_real = EXCLUDED.matriculas_real,
                cod_programa = COALESCE(realizado_programas.cod_programa, EXCLUDED.cod_programa);
            """,
            lote_id
        )

        resumo = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'RESOLVIDO') AS resolvidos,
                COUNT(*) FILTER (WHERE status = 'AMBIGUO') AS ambiguos,
                COUNT(*) FILTER (WHERE status = 'ERRO') AS erros
            FROM importacao_matriculas_staging
            WHERE id = ANY($1::bigint[])
            """,
            ids
        )

        processadas = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM importacao_matriculas_staging
            WHERE lote_id = $1
              AND status IN ('RESOLVIDO', 'AMBIGUO', 'ERRO')
            """,
            lote_id
        )

        await conn.execute(
            """
            UPDATE importacao_matriculas_lotes
            SET processadas = $2
            WHERE id = $1
            """,
            lote_id,
            processadas
        )

    return {
        "ok": True,
        "lote_id": lote_id,
        "linhas_avaliadas": len(ids),
        "atualizadas": resumo["resolvidos"] or 0,
        "ambiguas": resumo["ambiguos"] or 0,
        "erros": resumo["erros"] or 0,
    }

@router.post("/importacoes/receita")
async def importar_receita(request: Request, arquivo: UploadFile = File(...), ano_referencia: int = 2026):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo não informado.")

    nome = arquivo.filename.lower()
    if not (nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Envie um arquivo Excel .xlsx ou .xls.")

    conteudo = await arquivo.read()

    try:
        df = pd.read_excel(io.BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler Excel: {e}")

    df.columns = [str(c).replace("\xa0", " ").strip().lower() for c in df.columns]

    colunas_obrigatorias = [
        "cr",
        "descricao_cr",
        "valor",
        "mes",
        "ano",
        "cod_uo",
        "cod_modalidade",
        "cod_programa",
        "programa",
    ]

    faltantes = [c for c in colunas_obrigatorias if c not in df.columns]
    if faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"Colunas obrigatórias ausentes no Excel: {', '.join(faltantes)}"
        )

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote = await conn.fetchrow(
                """
                INSERT INTO importacao_receita_lotes (
                    nome_arquivo, ano_referencia, status,
                    linhas_importadas, validas, invalidas, processadas
                )
                VALUES ($1, $2, 'IMPORTADO', 0, 0, 0, 0)
                RETURNING id
                """,
                arquivo.filename,
                ano_referencia,
            )
            lote_id = lote["id"]

            registros = []
            total_validas = 0
            total_invalidas = 0

            for idx, row in df.iterrows():
                linha_numero = idx + 2

                cr = norm_cr(row.get("cr"))
                descricao_cr = norm_text(row.get("descricao_cr"))
                valor_raw = row.get("valor")
                mes_raw = row.get("mes")
                ano_raw = row.get("ano")
                cod_uo_raw = row.get("cod_uo")
                cod_modalidade_raw = row.get("cod_modalidade")
                cod_programa_raw = row.get("cod_programa")
                programa = norm_text(row.get("programa"))

                linha_vazia = (
                    not cr
                    and not descricao_cr
                    and pd.isna(valor_raw)
                    and pd.isna(mes_raw)
                    and pd.isna(ano_raw)
                    and pd.isna(cod_uo_raw)
                    and pd.isna(cod_modalidade_raw)
                    and pd.isna(cod_programa_raw)
                    and not programa
                )
                if linha_vazia:
                    continue

                erros = []

                valor = None
                mes = None
                ano = None
                cod_uo = None
                cod_modalidade = None
                cod_programa = None

                if not cr:
                    erros.append("CR não informado")

                try:
                    if pd.isna(valor_raw) or valor_raw in ("", None):
                        continue
                    else:
                        if isinstance(valor_raw, (int, float)):
                            valor = Decimal(str(valor_raw))
                        else:
                            s_valor = str(valor_raw).strip().replace("\xa0", "")
                            if "," in s_valor and "." in s_valor:
                                s_valor = s_valor.replace(".", "").replace(",", ".")
                            elif "," in s_valor:
                                s_valor = s_valor.replace(",", ".")
                            valor = Decimal(s_valor)
                except Exception:
                    erros.append("Valor inválido")

                try:
                    mes = norm_int(mes_raw)
                    if mes is None or mes < 1 or mes > 12:
                        erros.append("Mês inválido")
                except Exception:
                    erros.append("Mês inválido")

                try:
                    ano = norm_int(ano_raw) if not pd.isna(ano_raw) else ano_referencia
                    if ano is None:
                        ano = ano_referencia
                except Exception:
                    erros.append("Ano inválido")

                try:
                    cod_uo = norm_int(cod_uo_raw) if not pd.isna(cod_uo_raw) else None
                except Exception:
                    erros.append("cod_uo inválido")

                try:
                    cod_modalidade = norm_int(cod_modalidade_raw) if not pd.isna(cod_modalidade_raw) else None
                except Exception:
                    erros.append("cod_modalidade inválido")

                try:
                    cod_programa = norm_int(cod_programa_raw) if not pd.isna(cod_programa_raw) else None
                except Exception:
                    erros.append("cod_programa inválido")

                status = "PENDENTE" if not erros else "ERRO"

                if status == "PENDENTE":
                    total_validas += 1
                else:
                    total_invalidas += 1

                registros.append((
                    lote_id,
                    linha_numero,
                    cr,
                    descricao_cr,
                    valor,
                    mes,
                    ano,
                    cod_uo,
                    cod_modalidade,
                    cod_programa,
                    programa,
                    None,  # cod_oferta_resolvido
                    status,
                    "; ".join(erros) if erros else None,
                ))

            if registros:
                await conn.executemany(
                    """
                    INSERT INTO importacao_receita_staging (
                        lote_id,
                        linha_origem,
                        cr,
                        descricao_cr,
                        valor,
                        mes,
                        ano,
                        cod_uo,
                        cod_modalidade,
                        cod_programa,
                        programa,
                        cod_oferta_resolvido,
                        status,
                        erro
                    )
                    VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14
                    )
                    """,
                    registros
                )

            await conn.execute(
                """
                UPDATE importacao_receita_lotes
                SET linhas_importadas = $2,
                    validas = $3,
                    invalidas = $4
                WHERE id = $1
                """,
                lote_id,
                len(registros),
                total_validas,
                total_invalidas
            )

    return {
        "ok": True,
        "lote_id": lote_id,
        "arquivo": arquivo.filename,
        "linhas_importadas": len(registros),
        "validas": total_validas,
        "invalidas": total_invalidas,
    }

@router.post("/importacoes/receita/processar/{lote_id}")
async def processar_receita(request: Request, lote_id: int):
    pool = request.app.state.pool
    batch_size = 200

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT *
            FROM importacao_receita_lotes
            WHERE id = $1
            """,
            lote_id
        )

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado.")

        await conn.execute(
            """
            UPDATE importacao_receita_lotes
            SET status = 'PROCESSANDO',
                processado_em = NULL
            WHERE id = $1
            """,
            lote_id
        )

        ids_rows = await conn.fetch(
            """
            SELECT id
            FROM importacao_receita_staging
            WHERE lote_id = $1
                AND status = 'PENDENTE'
            ORDER BY id
            LIMIT $2
            """,
            lote_id,
            batch_size
        )

        ids = [r["id"] for r in ids_rows]

        if not ids:
            processadas = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM importacao_receita_staging
                WHERE lote_id = $1
                    AND status IN ('RESOLVIDO', 'AMBIGUO', 'ERRO')
                """,
                lote_id
            )

            erros_total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM importacao_receita_staging
                WHERE lote_id = $1
                    AND status = 'ERRO'
                """,
                lote_id
            )

            ambiguas_total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM importacao_receita_staging
                WHERE lote_id = $1
                    AND status = 'AMBIGUO'
                """,
                lote_id
            )

            status_final = "PROCESSADO"
            if (erros_total or 0) > 0 or (ambiguas_total or 0) > 0:
                status_final = "PROCESSADO_COM_ERRO"

            await conn.execute(
                """
                UPDATE importacao_receita_lotes
                SET status = $2,
                    processadas = $3,
                    processado_em = NOW()
                WHERE id = $1
                """,
                lote_id,
                status_final,
                processadas
            )

            return {
                "ok": True,
                "lote_id": lote_id,
                "linhas_avaliadas": 0,
                "atualizadas": 0,
                "ambiguas": 0,
                "erros": 0
            }

        # NÍVEL 1: ano + cr + cod_uo + cod_modalidade + cod_programa
        await conn.execute(
            """
            WITH candidatos AS (
                SELECT
                    s.id AS staging_id,
                    o.codigo AS cod_oferta,
                    COUNT(*) OVER (PARTITION BY s.id) AS qtd
                FROM importacao_receita_staging s
                JOIN ofertas_programas o
                    ON o.ano = s.ano
                    AND o.cr = s.cr
                    AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                    AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                    AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                WHERE s.id = ANY($1::bigint[])
                    AND s.status = 'PENDENTE'
            )
            UPDATE importacao_receita_staging s
            SET cod_oferta_resolvido = c.cod_oferta,
                status = 'RESOLVIDO',
                erro = NULL
            FROM candidatos c
            WHERE s.id = c.staging_id
                AND c.qtd = 1
            """,
            ids
        )

        await conn.execute(
            """
            INSERT INTO ofertas_programas (
                cr,
                ano,
                cod_uo,
                cod_modalidade,
                cod_programa
            )
            SELECT DISTINCT
                s.cr,
                s.ano,
                s.cod_uo,
                s.cod_modalidade,
                s.cod_programa
            FROM importacao_receita_staging s
            WHERE s.id = ANY($1::bigint[])
            AND s.status = 'PENDENTE'
            AND NOT EXISTS (
                SELECT 1
                FROM ofertas_programas o
                WHERE o.ano = s.ano
                    AND o.cr = s.cr
                    AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                    AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                    AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                )
            """,
            ids
        )

        await conn.execute(
            """
            WITH candidatos AS (
                SELECT
                    s.id AS staging_id,
                    o.codigo AS cod_oferta,
                    COUNT(*) OVER (PARTITION BY s.id) AS qtd
                FROM importacao_receita_staging s
                JOIN ofertas_programas o
                ON o.ano = s.ano
                AND o.cr = s.cr
                AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                WHERE s.id = ANY($1::bigint[])
                AND s.status = 'PENDENTE'
            )
            UPDATE importacao_receita_staging s
            SET cod_oferta_resolvido = c.cod_oferta,
                status = 'RESOLVIDO',
                erro = NULL
            FROM candidatos c
            WHERE s.id = c.staging_id
            AND c.qtd = 1
            """,
            ids
        )

        # AMBÍGUO: mais de uma oferta para a combinação exata
        await conn.execute(
            """
            WITH candidatos AS (
                SELECT
                    s.id AS staging_id,
                    COUNT(*) AS qtd
                FROM importacao_receita_staging s
                JOIN ofertas_programas o
                    ON o.ano = s.ano
                    AND o.cr = s.cr
                    AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                    AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                    AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                WHERE s.id = ANY($1::bigint[])
                    AND s.status = 'PENDENTE'
                GROUP BY s.id
            )
            UPDATE importacao_receita_staging s
            SET status = 'AMBIGUO',
                erro = 'Mais de uma oferta encontrada para a combinação exata informada.'
            FROM candidatos c
            WHERE s.id = c.staging_id
                AND c.qtd > 1
                AND s.status = 'PENDENTE'
            """,
            ids
        )

        # ERRO: ainda pendente e sem match
        await conn.execute(
            """
            UPDATE importacao_receita_staging
            SET status = 'ERRO',
                erro = 'Nenhuma oferta encontrada para os critérios informados.'
            WHERE id = ANY($1::bigint[])
                AND status = 'PENDENTE'
            """,
            ids
        )

        # CONSOLIDA O BATCH ATUAL POR OFERTA EXATA
        await conn.execute(
            """
            INSERT INTO realizado_programas (
                cod_oferta,
                ano,
                mes,
                matriculas_real,
                ha_real,
                receita_real,
                despesa_real,
                cod_programa
            )
            SELECT
                cod_oferta_resolvido AS cod_oferta,
                ano,
                mes,
                0,
                0,
                SUM(valor) AS receita_total,
                0,
                MAX(cod_programa) AS cod_programa
            FROM importacao_receita_staging
            WHERE id = ANY($1::bigint[])
            AND status = 'RESOLVIDO'
            AND cod_oferta_resolvido IS NOT NULL
            GROUP BY cod_oferta_resolvido, ano, mes
            ON CONFLICT (cod_oferta, ano, mes)
            DO UPDATE SET
                receita_real = COALESCE(realizado_programas.receita_real, 0) + COALESCE(EXCLUDED.receita_real, 0),
                cod_programa = COALESCE(realizado_programas.cod_programa, EXCLUDED.cod_programa)
            """,
            ids
        )

        resumo = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'RESOLVIDO') AS resolvidos,
                COUNT(*) FILTER (WHERE status = 'AMBIGUO') AS ambiguos,
                COUNT(*) FILTER (WHERE status = 'ERRO') AS erros
            FROM importacao_receita_staging
            WHERE id = ANY($1::bigint[])
            """,
            ids
        )

        processadas = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM importacao_receita_staging
            WHERE lote_id = $1
                AND status IN ('RESOLVIDO', 'AMBIGUO', 'ERRO')
            """,
            lote_id
        )

        await conn.execute(
            """
            UPDATE importacao_receita_lotes
            SET status = 'PROCESSANDO',
                processadas = $2,
                processado_em = NULL
            WHERE id = $1
            """,
            lote_id,
            processadas
        )

        return {
            "ok": True,
            "lote_id": lote_id,
            "linhas_avaliadas": len(ids),
            "atualizadas": int(resumo["resolvidos"] or 0),
            "ambiguas": int(resumo["ambiguos"] or 0),
            "erros": int(resumo["erros"] or 0),
        }
    
@router.post("/importacoes/hora-aluno")
async def importar_hora_aluno(request: Request, arquivo: UploadFile = File(...), ano_referencia: int = 2026):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo não informado.")

    nome = arquivo.filename.lower()
    if not (nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Envie um arquivo Excel .xlsx ou .xls.")

    conteudo = await arquivo.read()

    try:
        df = pd.read_excel(io.BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler Excel: {e}")

    df.columns = [str(c).replace("\xa0", " ").strip().lower() for c in df.columns]

    colunas_obrigatorias = [
        "cod_regiao",
        "regiao",
        "cod_subregiao",
        "subregiao",
        "cod_uo",
        "uo",
        "cr",
        "descricao_cr",
        "valor",
        "mes",
        "ano",
        "cod_modalidade",
        "modalidade",
        "cod_programa",
        "programa",
    ]

    faltantes = [c for c in colunas_obrigatorias if c not in df.columns]
    if faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"Colunas obrigatórias ausentes no Excel: {', '.join(faltantes)}"
        )

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote = await conn.fetchrow(
                """
                INSERT INTO importacao_ha_lotes (
                    nome_arquivo, ano_referencia, status,
                    linhas_importadas, validas, invalidas, processadas
                )
                VALUES ($1, $2, 'IMPORTADO', 0, 0, 0, 0)
                RETURNING id
                """,
                arquivo.filename,
                ano_referencia,
            )
            lote_id = lote["id"]

            registros = []
            total_validas = 0
            total_invalidas = 0

            for idx, row in df.iterrows():
                linha_numero = idx + 2

                cod_regiao_raw = row.get("cod_regiao")
                regiao = norm_text(row.get("regiao"))
                cod_subregiao_raw = row.get("cod_subregiao")
                subregiao = norm_text(row.get("subregiao"))
                cod_uo_raw = row.get("cod_uo")
                uo = norm_text(row.get("uo"))
                cr = norm_cr(row.get("cr"))
                descricao_cr = norm_text(row.get("descricao_cr"))
                valor_raw = row.get("valor")
                mes_raw = row.get("mes")
                ano_raw = row.get("ano")
                cod_modalidade_raw = row.get("cod_modalidade")
                modalidade = norm_text(row.get("modalidade"))
                cod_programa_raw = row.get("cod_programa")
                programa = norm_text(row.get("programa"))

                linha_vazia = (
                    not cr
                    and not descricao_cr
                    and pd.isna(valor_raw)
                    and pd.isna(mes_raw)
                    and pd.isna(ano_raw)
                    and pd.isna(cod_uo_raw)
                    and pd.isna(cod_modalidade_raw)
                    and pd.isna(cod_programa_raw)
                    and not programa
                )
                if linha_vazia:
                    continue

                erros = []

                cod_regiao = None
                valor = None
                mes = None
                ano = None
                cod_subregiao = None
                cod_uo = None
                cod_modalidade = None
                cod_programa = None

                if not cr:
                    erros.append("CR não informado")

                try:
                    if pd.isna(valor_raw) or valor_raw in ("", None):
                        continue
                    else:
                        if isinstance(valor_raw, (int, float)):
                            valor = Decimal(str(valor_raw))
                        else:
                            s_valor = str(valor_raw).strip().replace("\xa0", "")
                            if "," in s_valor and "." in s_valor:
                                s_valor = s_valor.replace(".", "").replace(",", ".")
                            elif "," in s_valor:
                                s_valor = s_valor.replace(",", ".")
                            valor = Decimal(s_valor)
                except Exception:
                    erros.append("Valor inválido")

                try:
                    mes = norm_int(mes_raw)
                    if mes is None or mes < 1 or mes > 12:
                        erros.append("Mês inválido")
                except Exception:
                    erros.append("Mês inválido")

                try:
                    ano = norm_int(ano_raw) if not pd.isna(ano_raw) else ano_referencia
                    if ano is None:
                        ano = ano_referencia
                except Exception:
                    erros.append("Ano inválido")

                try:
                    cod_regiao = norm_int(cod_regiao_raw) if not pd.isna(cod_regiao_raw) else None
                except Exception:
                    erros.append("cod_regiao inválido")

                try:
                    cod_subregiao = norm_int(cod_subregiao_raw) if not pd.isna(cod_subregiao_raw) else None
                except Exception:
                    erros.append("cod_subregiao inválido")

                try:
                    cod_uo = norm_int(cod_uo_raw) if not pd.isna(cod_uo_raw) else None
                except Exception:
                    erros.append("cod_uo inválido")

                try:
                    cod_modalidade = norm_int(cod_modalidade_raw) if not pd.isna(cod_modalidade_raw) else None
                except Exception:
                    erros.append("cod_modalidade inválido")

                try:
                    cod_programa = norm_int(cod_programa_raw) if not pd.isna(cod_programa_raw) else None
                except Exception:
                    erros.append("cod_programa inválido")

                status = "PENDENTE" if not erros else "ERRO"

                if status == "PENDENTE":
                    total_validas += 1
                else:
                    total_invalidas += 1

                registros.append((
                lote_id,
                linha_numero,
                cod_regiao,
                regiao,
                cod_subregiao,
                subregiao,
                cr,
                descricao_cr,
                valor,
                mes,
                ano,
                cod_uo,
                uo,
                cod_modalidade,
                modalidade,
                cod_programa,
                programa,
                None,  # cod_oferta_resolvido
                status,
                "; ".join(erros) if erros else None,
            ))

            if registros:
                await conn.executemany(
                    """
                    INSERT INTO importacao_ha_staging (
                        lote_id,
                        linha_origem,
                        cod_regiao,
                        regiao,
                        cod_subregiao,
                        subregiao,
                        cr,
                        descricao_cr,
                        valor,
                        mes,
                        ano,
                        cod_uo,
                        uo,
                        cod_modalidade,
                        modalidade,
                        cod_programa,
                        programa,
                        cod_oferta_resolvido,
                        status,
                        erro
                    )
                    VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                        $11,$12,$13,$14,$15,$16,$17,$18,$19,$20
                    )
                    """,
                    registros
                )

            await conn.execute(
                """
                UPDATE importacao_ha_lotes
                SET linhas_importadas = $2,
                    validas = $3,
                    invalidas = $4
                WHERE id = $1
                """,
                lote_id,
                len(registros),
                total_validas,
                total_invalidas
            )

    return {
        "ok": True,
        "lote_id": lote_id,
        "arquivo": arquivo.filename,
        "linhas_importadas": len(registros),
        "validas": total_validas,
        "invalidas": total_invalidas,
    }

@router.post("/importacoes/hora-aluno/processar/{lote_id}")
async def processar_hora_aluno(request: Request, lote_id: int):
    pool = request.app.state.pool
    batch_size = 200

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT *
            FROM importacao_ha_lotes
            WHERE id = $1
            """,
            lote_id
        )

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado.")

        await conn.execute(
            """
            UPDATE importacao_ha_lotes
            SET status = 'PROCESSANDO',
                processado_em = NULL
            WHERE id = $1
            """,
            lote_id
        )

        ids_rows = await conn.fetch(
            """
            SELECT id
            FROM importacao_ha_staging
            WHERE lote_id = $1
                AND status = 'PENDENTE'
            ORDER BY id
            LIMIT $2
            """,
            lote_id,
            batch_size
        )

        ids = [r["id"] for r in ids_rows]

        if not ids:
            processadas = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM importacao_ha_staging
                WHERE lote_id = $1
                    AND status IN ('RESOLVIDO', 'AMBIGUO', 'ERRO')
                """,
                lote_id
            )

            erros_total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM importacao_ha_staging
                WHERE lote_id = $1
                    AND status = 'ERRO'
                """,
                lote_id
            )

            ambiguas_total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM importacao_ha_staging
                WHERE lote_id = $1
                    AND status = 'AMBIGUO'
                """,
                lote_id
            )

            status_final = "PROCESSADO"
            if (erros_total or 0) > 0 or (ambiguas_total or 0) > 0:
                status_final = "PROCESSADO_COM_ERRO"

            await conn.execute(
                """
                UPDATE importacao_ha_lotes
                SET status = $2,
                    processadas = $3,
                    processado_em = NOW()
                WHERE id = $1
                """,
                lote_id,
                status_final,
                processadas
            )

            return {
                "ok": True,
                "lote_id": lote_id,
                "linhas_avaliadas": 0,
                "atualizadas": 0,
                "ambiguas": 0,
                "erros": 0
            }

        # NÍVEL 1: ano + cr + cod_uo + cod_modalidade + cod_programa
        await conn.execute(
            """
            WITH candidatos AS (
                SELECT
                    s.id AS staging_id,
                    o.codigo AS cod_oferta,
                    COUNT(*) OVER (PARTITION BY s.id) AS qtd
                FROM importacao_ha_staging s
                JOIN ofertas_programas o
                    ON o.ano = s.ano
                    AND o.cr = s.cr
                    AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                    AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                    AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                WHERE s.id = ANY($1::bigint[])
                    AND s.status = 'PENDENTE'
            )
            UPDATE importacao_ha_staging s
            SET cod_oferta_resolvido = c.cod_oferta,
                status = 'RESOLVIDO',
                erro = NULL
            FROM candidatos c
            WHERE s.id = c.staging_id
                AND c.qtd = 1
            """,
            ids
        )

        await conn.execute(
            """
            INSERT INTO ofertas_programas (
                cr,
                ano,
                cod_uo,
                cod_modalidade,
                cod_programa
            )
            SELECT DISTINCT
                s.cr,
                s.ano,
                s.cod_uo,
                s.cod_modalidade,
                s.cod_programa
            FROM importacao_ha_staging s
            WHERE s.id = ANY($1::bigint[])
            AND s.status = 'PENDENTE'
            AND NOT EXISTS (
                SELECT 1
                FROM ofertas_programas o
                WHERE o.ano = s.ano
                    AND o.cr = s.cr
                    AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                    AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                    AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                )
            """,
            ids
        )

        await conn.execute(
            """
            WITH candidatos AS (
                SELECT
                    s.id AS staging_id,
                    o.codigo AS cod_oferta,
                    COUNT(*) OVER (PARTITION BY s.id) AS qtd
                FROM importacao_ha_staging s
                JOIN ofertas_programas o
                ON o.ano = s.ano
                AND o.cr = s.cr
                AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                WHERE s.id = ANY($1::bigint[])
                AND s.status = 'PENDENTE'
            )
            UPDATE importacao_ha_staging s
            SET cod_oferta_resolvido = c.cod_oferta,
                status = 'RESOLVIDO',
                erro = NULL
            FROM candidatos c
            WHERE s.id = c.staging_id
            AND c.qtd = 1
            """,
            ids
        )

        # AMBÍGUO: mais de uma oferta para a combinação exata
        await conn.execute(
            """
            WITH candidatos AS (
                SELECT
                    s.id AS staging_id,
                    COUNT(*) AS qtd
                FROM importacao_ha_staging s
                JOIN ofertas_programas o
                    ON o.ano = s.ano
                    AND o.cr = s.cr
                    AND COALESCE(o.cod_uo, 0) = COALESCE(s.cod_uo, 0)
                    AND COALESCE(o.cod_modalidade, 0) = COALESCE(s.cod_modalidade, 0)
                    AND COALESCE(o.cod_programa, 0) = COALESCE(s.cod_programa, 0)
                WHERE s.id = ANY($1::bigint[])
                    AND s.status = 'PENDENTE'
                GROUP BY s.id
            )
            UPDATE importacao_ha_staging s
            SET status = 'AMBIGUO',
                erro = 'Mais de uma oferta encontrada para a combinação exata informada.'
            FROM candidatos c
            WHERE s.id = c.staging_id
                AND c.qtd > 1
                AND s.status = 'PENDENTE'
            """,
            ids
        )

        # ERRO: ainda pendente e sem match
        await conn.execute(
            """
            UPDATE importacao_ha_staging
            SET status = 'ERRO',
                erro = 'Nenhuma oferta encontrada para os critérios informados.'
            WHERE id = ANY($1::bigint[])
                AND status = 'PENDENTE'
            """,
            ids
        )

        # CONSOLIDA O BATCH ATUAL POR OFERTA EXATA
        await conn.execute(
            """
            INSERT INTO realizado_programas (
                cod_oferta,
                ano,
                mes,
                matriculas_real,
                ha_real,
                receita_real,
                despesa_real,
                cod_programa
            )
            SELECT
                cod_oferta_resolvido AS cod_oferta,
                ano,
                mes,
                0,
                SUM(valor) AS ha_total,
                0,
                0,
                MAX(cod_programa) AS cod_programa
            FROM importacao_ha_staging
            WHERE id = ANY($1::bigint[])
            AND status = 'RESOLVIDO'
            AND cod_oferta_resolvido IS NOT NULL
            GROUP BY cod_oferta_resolvido, ano, mes
            ON CONFLICT (cod_oferta, ano, mes)
            DO UPDATE SET
                ha_real = COALESCE(realizado_programas.ha_real, 0) + COALESCE(EXCLUDED.ha_real, 0),
                cod_programa = COALESCE(realizado_programas.cod_programa, EXCLUDED.cod_programa)
            """,
            ids
        )

        resumo = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'RESOLVIDO') AS resolvidos,
                COUNT(*) FILTER (WHERE status = 'AMBIGUO') AS ambiguos,
                COUNT(*) FILTER (WHERE status = 'ERRO') AS erros
            FROM importacao_ha_staging
            WHERE id = ANY($1::bigint[])
            """,
            ids
        )

        processadas = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM importacao_ha_staging
            WHERE lote_id = $1
                AND status IN ('RESOLVIDO', 'AMBIGUO', 'ERRO')
            """,
            lote_id
        )

        await conn.execute(
            """
            UPDATE importacao_ha_lotes
            SET status = 'PROCESSANDO',
                processadas = $2,
                processado_em = NULL
            WHERE id = $1
            """,
            lote_id,
            processadas
        )

        return {
            "ok": True,
            "lote_id": lote_id,
            "linhas_avaliadas": len(ids),
            "atualizadas": int(resumo["resolvidos"] or 0),
            "ambiguas": int(resumo["ambiguos"] or 0),
            "erros": int(resumo["erros"] or 0),
        }

@router.get("/sge_turmas/summary")
async def sge_turmas_summary(
    request: Request,
    uo: str | None = None,
    curso: str | None = None,
    modalidade: str | None = None,
    programa: str | None = None,
    turma: str | None = None,
    condicao_aluno: str | None = None,
    dt_inicio_de: str | None = None,
    dt_inicio_ate: str | None = None,
    formato: str | None = None,
    turno: str | None = None,
    status_matricula: str | None = None,
    faixa_preenchimento: str | None = None,
    dt_mat_de: str | None = None,
    dt_mat_ate: str | None = None,
):
    pool = request.app.state.pool
    data_fim_padrao = date(2026, 1, 1)
    usar_filtro_padrao = not dt_inicio_de and not dt_inicio_ate

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT id
            FROM data_import_lotes
            WHERE status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        if not lote:
            return {
                "lote_id": None,
                "total_turmas": 0,
                "total_vagas": 0,
                "total_matriculados": 0,
                "total_pre_matriculados": 0,
                "total_cancelados": 0,
                "total_desistentes": 0,
                "total_evadidos": 0,
                "total_falecidos": 0,
            }

        # -----------------------------
        # QUERY 1: cards por turma
        # ----------------------------- 
        sql = """
        SELECT
            COUNT(DISTINCT t.codigo) AS total_turmas,
            COALESCE(SUM(t.vagas_total), 0) AS total_vagas,
            COALESCE(SUM(COALESCE(tsr.matriculados, 0)), 0) AS total_matriculados,
            COALESCE(SUM(COALESCE(tsr.pre_matriculados, 0)), 0) AS total_pre_matriculados,
            COALESCE(SUM(COALESCE(tsr.cancelados, 0)), 0) AS total_cancelados,
            COALESCE(SUM(COALESCE(tsr.desistentes, 0)), 0) AS total_desistentes,
            COALESCE(SUM(COALESCE(tsr.evadidos, 0)), 0) AS total_evadidos,
            COALESCE(SUM(COALESCE(tsr.falecidos, 0)), 0) AS total_falecidos
        FROM turmas t
        LEFT JOIN curso c
          ON c.codigo = t.cod_curso
        LEFT JOIN uo u
          ON u.codigo = t.cod_uo
        LEFT JOIN formato frm
          ON frm.codigo = t.cod_formato
        LEFT JOIN turnos trn
          ON trn.codigo = t.cod_turno
        LEFT JOIN (
            SELECT
                cod_turma,
                SUM(matriculados) AS matriculados,
                SUM(pre_matriculados) AS pre_matriculados,
                SUM(cancelados) AS cancelados,
                SUM(desistentes) AS desistentes,
                SUM(evadidos) AS evadidos,
                SUM(falecidos) AS falecidos
            FROM turmas_status_resumo
            GROUP BY cod_turma
        ) tsr
        ON tsr.cod_turma = t.codigo
        WHERE t.lote_origem_data_id = $1
        """

        params = [lote["id"]]
        idx = 2

        sql, params, idx = aplicar_filtros_turmas_base(
            sql,
            params,
            idx,
            alias_t="t",
            alias_c="c",
            alias_u="u",
            alias_frm="frm",
            alias_trn="trn",
            alias_tsr="tsr",
            uo=uo,
            curso=curso,
            turma=turma,
            condicao_aluno=condicao_aluno,
            modalidade=modalidade,
            programa=programa,
            dt_inicio_de=dt_inicio_de,
            dt_inicio_ate=dt_inicio_ate,
            formato=formato,
            turno=turno,
            status_matricula=status_matricula,
            faixa_preenchimento=faixa_preenchimento,
            dt_mat_de=dt_mat_de,
            dt_mat_ate=dt_mat_ate,
            usar_filtro_padrao=usar_filtro_padrao,
            data_fim_padrao=data_fim_padrao,
        )

        resumo = await conn.fetchrow(sql, *params)

        if condicao_aluno or dt_mat_de or dt_mat_ate:
            sql_cond = """
            WITH base_da AS (
                SELECT
                    da.*,
                    t.codigo AS turma_id,
                    t.vagas_total
                FROM sge_turma_detalhe_alunos da
                JOIN turmas t
                ON TRIM(UPPER(t.codigo_sge)) = TRIM(UPPER(da.cod_turma))
                LEFT JOIN curso c ON c.codigo = t.cod_curso
                LEFT JOIN uo u ON u.codigo = t.cod_uo
                LEFT JOIN formato frm ON frm.codigo = t.cod_formato
                LEFT JOIN turnos trn ON trn.codigo = t.cod_turno
                LEFT JOIN turmas_status_resumo tsr ON tsr.cod_turma = t.codigo
                WHERE da.lote_id = $1
                AND t.lote_origem_data_id = $1
                AND ($2::text IS NULL OR regexp_replace(translate(UPPER(TRIM(COALESCE(da.condicao_aluno, ''))),'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ','AAAAEEEIIIOOOOUUUC'),'\\s+',' ','g')
                    = regexp_replace(translate(UPPER(TRIM(COALESCE($2, ''))),'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ','AAAAEEEIIIOOOOUUUC'),'\\s+',' ','g'))
                AND ($3::date IS NULL OR da.data_matricula >= $3::date)
                AND ($4::date IS NULL OR da.data_matricula <= $4::date)
            """

            params_cond = [
                lote["id"],
                condicao_aluno,
                datetime.fromisoformat(dt_mat_de).date() if dt_mat_de else None,
                datetime.fromisoformat(dt_mat_ate).date() if dt_mat_ate else None,
            ]
            idx_cond = 5

            sql_cond, params_cond, idx_cond = aplicar_filtros_turmas_base(
                sql_cond, params_cond, idx_cond,
                alias_t="t", alias_c="c", alias_u="u", alias_frm="frm", alias_trn="trn", alias_tsr="tsr",
                uo=uo, curso=curso, turma=turma, condicao_aluno=None,
                dt_inicio_de=dt_inicio_de, dt_inicio_ate=dt_inicio_ate,
                formato=formato, turno=turno, status_matricula=status_matricula,
                modalidade=modalidade,
                programa=programa,
                faixa_preenchimento=faixa_preenchimento,
                dt_mat_de=None, dt_mat_ate=None,
                usar_filtro_padrao=usar_filtro_padrao,
                data_fim_padrao=data_fim_padrao,
            )

            sql_cond += """
            )
            SELECT
                COUNT(DISTINCT turma_id) AS total_turmas,
                COALESCE((
                    SELECT SUM(vagas_total)
                    FROM (
                        SELECT DISTINCT turma_id, vagas_total
                        FROM base_da
                    ) x
                ), 0) AS total_vagas,
                COUNT(*) FILTER (WHERE TRIM(UPPER(COALESCE(status_matricula, ''))) = 'MATRICULADO') AS total_matriculados,
                COUNT(*) FILTER (WHERE TRIM(UPPER(COALESCE(status_matricula, ''))) IN ('PRE_MATRICULADO','PRE-MATRICULADO','PRÉ-MATRICULADO')) AS total_pre_matriculados,
                COUNT(*) FILTER (WHERE TRIM(UPPER(COALESCE(status_matricula, ''))) = 'CANCELADO') AS total_cancelados,
                COUNT(*) FILTER (WHERE TRIM(UPPER(COALESCE(status_matricula, ''))) = 'DESISTENTE') AS total_desistentes,
                COUNT(*) FILTER (WHERE TRIM(UPPER(COALESCE(status_matricula, ''))) = 'EVADIDO') AS total_evadidos,
                COUNT(*) FILTER (WHERE TRIM(UPPER(COALESCE(status_matricula, ''))) = 'FALECIDO') AS total_falecidos
            FROM base_da
            """

            resumo = await conn.fetchrow(sql_cond, *params_cond)

    return {
        "lote_id": lote["id"],
        "total_turmas": int(resumo["total_turmas"] or 0),
        "total_vagas": int(resumo["total_vagas"] or 0),
        "total_matriculados": int(resumo["total_matriculados"] or 0),
        "total_pre_matriculados": int(resumo["total_pre_matriculados"] or 0),
        "total_cancelados": int(resumo["total_cancelados"] or 0),
        "total_desistentes": int(resumo["total_desistentes"] or 0),
        "total_evadidos": int(resumo["total_evadidos"] or 0),
        "total_falecidos": int(resumo["total_falecidos"] or 0),
    }

@router.get("/sge_turmas/modalidades")
async def sge_turmas_modalidades(request: Request):
    pool = request.app.state.pool

    sql = """
    SELECT
        codigo,
        nome
    FROM modalidade
    ORDER BY nome
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)

    return [dict(r) for r in rows]

@router.get("/sge_turmas/programas")
async def sge_turmas_programas(request: Request):
    pool = request.app.state.pool

    sql = """
    SELECT
        codigo,
        nome_programa AS nome
    FROM programas
    ORDER BY nome_programa
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)

    return [dict(r) for r in rows]

@router.get("/sge_turmas/grafico/resumo")
async def grafico_resumo(
    request: Request,
    uo: str | None = None,
    curso: str | None = None,
    modalidade: str | None = None,
    programa: str | None = None,
    turma: str | None = None,
    condicao_aluno: str | None = None,
    dt_inicio_de: str | None = None,
    dt_inicio_ate: str | None = None,
    formato: str | None = None,
    turno: str | None = None,
    status_matricula: str | None = None,
    faixa_preenchimento: str | None = None,
    dt_mat_de: str | None = None,
    dt_mat_ate: str | None = None,
):
    pool = request.app.state.pool

    data_fim_padrao = date(2026, 1, 1)
    usar_filtro_padrao = not dt_inicio_de and not dt_inicio_ate

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT id
            FROM data_import_lotes
            WHERE status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        if not lote:
            return {}

        sql = """
        SELECT
            0 AS matriculados,
            0 AS pre_matriculados,
            0 AS cancelados,
            COALESCE(SUM(base.vagas_total), 0) AS vagas_total
        FROM (
            SELECT
                t.codigo,
                t.codigo_sge,
                t.vagas_total,
                t.lote_origem_data_id,
                t.data_inicio,
                t.data_fim,
                t.ano_referencia,
                t.cod_uo,
                t.cod_curso,
                t.cod_modalidade,
                t.cod_programa,
                t.cod_formato,
                t.cod_turno
            FROM turmas t
        ) base
        LEFT JOIN curso c
        ON c.codigo = base.cod_curso
        LEFT JOIN uo u
        ON u.codigo = base.cod_uo
        LEFT JOIN formato frm
        ON frm.codigo = base.cod_formato
        LEFT JOIN turnos trn
        ON trn.codigo = base.cod_turno
        LEFT JOIN turmas_status_resumo tsr
        ON tsr.cod_turma = base.codigo
        WHERE base.lote_origem_data_id = $1
        """

        params = [lote["id"]]
        idx = 2

        sql, params, idx = aplicar_filtros_turmas_base(
            sql,
            params,
            idx,
            alias_t="base",
            alias_c="c",
            alias_u="u",
            alias_frm="frm",
            alias_trn="trn",
            alias_tsr="tsr",
            uo=uo,
            curso=curso,
            modalidade=modalidade,
            programa=programa,
            turma=turma,
            condicao_aluno=condicao_aluno,
            dt_inicio_de=dt_inicio_de,
            dt_inicio_ate=dt_inicio_ate,
            formato=formato,
            turno=turno,
            status_matricula=status_matricula,
            faixa_preenchimento=faixa_preenchimento,
            dt_mat_de=dt_mat_de,
            dt_mat_ate=dt_mat_ate,
            usar_filtro_padrao=usar_filtro_padrao,
            data_fim_padrao=data_fim_padrao,
        )
        
        row = await conn.fetchrow(sql, *params)

        if condicao_aluno or dt_mat_de or dt_mat_ate:
            sql_status = """
            SELECT
                COUNT(*) FILTER (
                    WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) = 'MATRICULADO'
                ) AS matriculados,

                COUNT(*) FILTER (
                    WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) IN (
                        'PRE_MATRICULADO',
                        'PRE-MATRICULADO',
                        'PRÉ-MATRICULADO'
                    )
                ) AS pre_matriculados
            FROM sge_turma_detalhe_alunos da
            JOIN turmas t
            ON TRIM(UPPER(t.codigo_sge)) = TRIM(UPPER(da.cod_turma))
            LEFT JOIN curso c
            ON c.codigo = t.cod_curso
            LEFT JOIN uo u
            ON u.codigo = t.cod_uo
            LEFT JOIN formato frm
            ON frm.codigo = t.cod_formato
            LEFT JOIN turnos trn
            ON trn.codigo = t.cod_turno
            LEFT JOIN turmas_status_resumo tsr
            ON tsr.cod_turma = t.codigo
            WHERE da.lote_id = $1
            AND t.lote_origem_data_id = $1
            """

            params_status = [lote["id"]]
            idx_status = 2

            if condicao_aluno:
                sql_status += f"""
                AND regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(da.condicao_aluno, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                =
                regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(${idx_status}, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                """
                params_status.append(condicao_aluno)
                idx_status += 1
            
            if dt_mat_de:
                sql_status += f" AND da.data_matricula >= ${idx_status}"
                params_status.append(datetime.fromisoformat(dt_mat_de).date())
                idx_status += 1

            if dt_mat_ate:
                sql_status += f" AND da.data_matricula <= ${idx_status}"
                params_status.append(datetime.fromisoformat(dt_mat_ate).date())
                idx_status += 1

            sql_status, params_status, idx_status = aplicar_filtros_turmas_base(
                sql_status,
                params_status,
                idx_status,
                alias_t="t",
                alias_c="c",
                alias_u="u",
                alias_frm="frm",
                alias_trn="trn",
                alias_tsr="tsr",
                uo=uo,
                curso=curso,
                turma=turma,
                modalidade=modalidade,
                programa=programa,
                condicao_aluno=None,
                dt_inicio_de=dt_inicio_de,
                dt_inicio_ate=dt_inicio_ate,
                formato=formato,
                turno=turno,
                status_matricula=status_matricula,
                faixa_preenchimento=faixa_preenchimento,
                dt_mat_de=None,
                dt_mat_ate=None,
                usar_filtro_padrao=usar_filtro_padrao,
                data_fim_padrao=data_fim_padrao,
            )

            row_status = await conn.fetchrow(sql_status, *params_status)

            sql_vagas = """
            SELECT
                COALESCE(SUM(x.vagas_total), 0) AS vagas_total
            FROM (
                SELECT DISTINCT
                    t.codigo,
                    t.vagas_total
                FROM sge_turma_detalhe_alunos da
                JOIN turmas t
                  ON TRIM(UPPER(t.codigo_sge)) = TRIM(UPPER(da.cod_turma))
                LEFT JOIN curso c ON c.codigo = t.cod_curso
                LEFT JOIN uo u ON u.codigo = t.cod_uo
                LEFT JOIN formato frm ON frm.codigo = t.cod_formato
                LEFT JOIN turnos trn ON trn.codigo = t.cod_turno
                LEFT JOIN turmas_status_resumo tsr ON tsr.cod_turma = t.codigo
                WHERE da.lote_id = $1
                  AND t.lote_origem_data_id = $1
            """

            params_vagas = [lote["id"]]
            idx_vagas = 2

            if condicao_aluno:
                sql_vagas += f"""
                AND regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(da.condicao_aluno, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                =
                regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(${idx_vagas}, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                """
                params_vagas.append(condicao_aluno)
                idx_vagas += 1

            if dt_mat_de:
                sql_vagas += f" AND da.data_matricula >= ${idx_vagas}"
                params_vagas.append(datetime.fromisoformat(dt_mat_de).date())
                idx_vagas += 1

            if dt_mat_ate:
                sql_vagas += f" AND da.data_matricula <= ${idx_vagas}"
                params_vagas.append(datetime.fromisoformat(dt_mat_ate).date())
                idx_vagas += 1

            sql_vagas, params_vagas, idx_vagas = aplicar_filtros_turmas_base(
                sql_vagas,
                params_vagas,
                idx_vagas,
                alias_t="t",
                alias_c="c",
                alias_u="u",
                alias_frm="frm",
                alias_trn="trn",
                alias_tsr="tsr",
                uo=uo,
                curso=curso,
                turma=turma,
                modalidade=modalidade,
                programa=programa,
                condicao_aluno=None,
                dt_inicio_de=dt_inicio_de,
                dt_inicio_ate=dt_inicio_ate,
                formato=formato,
                turno=turno,
                status_matricula=status_matricula,
                faixa_preenchimento=faixa_preenchimento,
                dt_mat_de=None,
                dt_mat_ate=None,
                usar_filtro_padrao=usar_filtro_padrao,
                data_fim_padrao=data_fim_padrao,
            )

            sql_vagas += ") x"
            row_vagas = await conn.fetchrow(sql_vagas, *params_vagas)

        else:

            sql_status = """
            SELECT
                COALESCE(SUM(tsr.matriculados), 0) AS matriculados,
                COALESCE(SUM(tsr.pre_matriculados), 0) AS pre_matriculados
            FROM turmas t
            LEFT JOIN curso c
            ON c.codigo = t.cod_curso
            LEFT JOIN uo u
            ON u.codigo = t.cod_uo
            LEFT JOIN formato frm
            ON frm.codigo = t.cod_formato
            LEFT JOIN turnos trn
            ON trn.codigo = t.cod_turno
            LEFT JOIN turmas_status_resumo tsr
            ON tsr.cod_turma = t.codigo
            WHERE t.lote_origem_data_id = $1
            """

            params_status = [lote["id"]]
            idx_status = 2

            sql_status, params_status, idx_status = aplicar_filtros_turmas_base(
                sql_status,
                params_status,
                idx_status,
                alias_t="t",
                alias_c="c",
                alias_u="u",
                alias_frm="frm",
                alias_trn="trn",
                alias_tsr="tsr",
                uo=uo,
                curso=curso,
                turma=turma,
                modalidade=modalidade,
                programa=programa,
                condicao_aluno=condicao_aluno,
                dt_inicio_de=dt_inicio_de,
                dt_inicio_ate=dt_inicio_ate,
                formato=formato,
                turno=turno,
                status_matricula=status_matricula,
                faixa_preenchimento=faixa_preenchimento,
                dt_mat_de=None,
                dt_mat_ate=None,
                usar_filtro_padrao=usar_filtro_padrao,
                data_fim_padrao=data_fim_padrao,
            )

            row_status = await conn.fetchrow(sql_status, *params_status)

    matriculados = (row_status["matriculados"] if row_status else 0) or 0
    pre = (row_status["pre_matriculados"] if row_status else 0) or 0
    cancelados = row["cancelados"] or 0
    if condicao_aluno or dt_mat_de or dt_mat_ate:
        vagas = (row_vagas["vagas_total"] if row_vagas else 0) or 0
    else:
        vagas = row["vagas_total"] or 0

    return {
        "labels": ["Matrículas", "Pré-matrículas", "Vagas restantes"],
        "values": [
            int(matriculados),
            int(pre),
            int(max(vagas - matriculados - pre, 0))
        ]
    }

@router.get("/sge_turmas/grafico/faixas_preenchimento")
async def grafico_faixas_preenchimento(
    request: Request,
    uo: str | None = None,
    curso: str | None = None,
    modalidade: str | None = None,
    programa: str | None = None,
    turma: str | None = None,
    condicao_aluno: str | None = None,
    dt_inicio_de: str | None = None,
    dt_inicio_ate: str | None = None,
    formato: str | None = None,
    turno: str | None = None,
    status_matricula: str | None = None,
    faixa_preenchimento: str | None = None,
    dt_mat_de: str | None = None,
    dt_mat_ate: str | None = None,
):
    pool = request.app.state.pool

    data_fim_padrao = date(2026, 1, 1)
    usar_filtro_padrao = not dt_inicio_de and not dt_inicio_ate

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT id
            FROM data_import_lotes
            WHERE status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        if not lote:
            return []
        
        if condicao_aluno or dt_mat_de or dt_mat_ate:
            sql = """
            WITH base_alunos AS (
                SELECT
                    t.codigo AS cod_turma,
                    MAX(t.vagas_total) AS vagas_total,
                    COUNT(*) FILTER (
                        WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) = 'MATRICULADO'
                    ) AS matriculados,
                    COUNT(*) FILTER (
                        WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) IN (
                            'PRE_MATRICULADO',
                            'PRE-MATRICULADO',
                            'PRÉ-MATRICULADO'
                        )
                    ) AS pre_matriculados
                FROM sge_turma_detalhe_alunos da
                JOIN turmas t
                ON TRIM(UPPER(t.codigo_sge)) = TRIM(UPPER(da.cod_turma))
                LEFT JOIN curso c ON c.codigo = t.cod_curso
                LEFT JOIN uo u ON u.codigo = t.cod_uo
                LEFT JOIN formato frm ON frm.codigo = t.cod_formato
                LEFT JOIN turnos trn ON trn.codigo = t.cod_turno
                LEFT JOIN turmas_status_resumo tsr ON tsr.cod_turma = t.codigo
                WHERE da.lote_id = $1
                AND t.lote_origem_data_id = $1
            """

            params = [lote["id"]]
            idx = 2

            if condicao_aluno:
                sql += f"""
                AND regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(da.condicao_aluno, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                =
                regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(${idx}, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                """
                params.append(condicao_aluno)
                idx += 1

            if dt_mat_de:
                sql += f" AND da.data_matricula >= ${idx}"
                params.append(datetime.fromisoformat(dt_mat_de).date())
                idx += 1

            if dt_mat_ate:
                sql += f" AND da.data_matricula <= ${idx}"
                params.append(datetime.fromisoformat(dt_mat_ate).date())
                idx += 1

            sql, params, idx = aplicar_filtros_turmas_base(
                sql,
                params,
                idx,
                alias_t="t",
                alias_c="c",
                alias_u="u",
                alias_frm="frm",
                alias_trn="trn",
                alias_tsr="tsr",
                uo=uo,
                curso=curso,
                modalidade=modalidade,
                programa=programa,
                turma=turma,
                condicao_aluno=None,
                dt_inicio_de=dt_inicio_de,
                dt_inicio_ate=dt_inicio_ate,
                formato=formato,
                turno=turno,
                status_matricula=status_matricula,
                faixa_preenchimento=None,
                dt_mat_de=None,
                dt_mat_ate=None,
                usar_filtro_padrao=usar_filtro_padrao,
                data_fim_padrao=data_fim_padrao,
            )

            sql += """
                GROUP BY t.codigo
            ),
            faixas AS (
                SELECT
                    CASE
                        WHEN COALESCE(vagas_total, 0) = 0 THEN 'Abaixo de 70%'
                        WHEN ((matriculados + pre_matriculados)::numeric / vagas_total) >= 1 THEN '>= 100%'
                        WHEN ((matriculados + pre_matriculados)::numeric / vagas_total) >= 0.9 THEN '90 a 99%'
                        WHEN ((matriculados + pre_matriculados)::numeric / vagas_total) >= 0.8 THEN '80 a 89%'
                        WHEN ((matriculados + pre_matriculados)::numeric / vagas_total) >= 0.7 THEN '70 a 79%'
                        ELSE 'Abaixo de 70%'
                    END AS faixa
                FROM base_alunos
            )
            SELECT faixa, COUNT(*) AS total
            FROM faixas
            WHERE 1=1
            """

            if faixa_preenchimento:
                if faixa_preenchimento == "100":
                    sql += " AND faixa = '>= 100%'"
                elif faixa_preenchimento == "90_99":
                    sql += " AND faixa = '90 a 99%'"
                elif faixa_preenchimento == "80_89":
                    sql += " AND faixa = '80 a 89%'"
                elif faixa_preenchimento == "70_79":
                    sql += " AND faixa = '70 a 79%'"
                elif faixa_preenchimento == "lt_70":
                    sql += " AND faixa = 'Abaixo de 70%'"

            sql += " GROUP BY faixa"

            rows = await conn.fetch(sql, *params)

            ordem = {
                ">= 100%": 1,
                "90 a 99%": 2,
                "80 a 89%": 3,
                "70 a 79%": 4,
                "Abaixo de 70%": 5,
            }

            saida = [dict(r) for r in rows]
            saida.sort(key=lambda x: ordem.get(x["faixa"], 99))
            return saida

        sql = """
        SELECT
            CASE
                WHEN COALESCE(base.vagas_total, 0) = 0 THEN 'Abaixo de 70%'
                WHEN (
                    (COALESCE(tsr.matriculados, 0) + COALESCE(tsr.pre_matriculados, 0))::numeric
                    / base.vagas_total::numeric
                ) >= 1 THEN '>= 100%'
                WHEN (
                    (COALESCE(tsr.matriculados, 0) + COALESCE(tsr.pre_matriculados, 0))::numeric
                    / base.vagas_total::numeric
                ) >= 0.9 THEN '90 a 99%'
                WHEN (
                    (COALESCE(tsr.matriculados, 0) + COALESCE(tsr.pre_matriculados, 0))::numeric
                    / base.vagas_total::numeric
                ) >= 0.8 THEN '80 a 89%'
                WHEN (
                    (COALESCE(tsr.matriculados, 0) + COALESCE(tsr.pre_matriculados, 0))::numeric
                    / base.vagas_total::numeric
                ) >= 0.7 THEN '70 a 79%'
                ELSE 'Abaixo de 70%'
            END AS faixa,
            COUNT(DISTINCT base.codigo) AS total
        FROM (
            SELECT
                t.codigo,
                t.codigo_sge,
                t.vagas_total,
                t.lote_origem_data_id,
                t.data_inicio,
                t.data_fim,
                t.ano_referencia,
                t.cod_uo,
                t.cod_curso,
                t.cod_modalidade,
                t.cod_programa,
                t.cod_formato,
                t.cod_turno
            FROM turmas t
        ) base
        LEFT JOIN curso c
        ON c.codigo = base.cod_curso
        LEFT JOIN uo u
        ON u.codigo = base.cod_uo
        LEFT JOIN formato frm
        ON frm.codigo = base.cod_formato
        LEFT JOIN turnos trn
        ON trn.codigo = base.cod_turno
        LEFT JOIN turmas_status_resumo tsr
        ON tsr.cod_turma = base.codigo
        WHERE base.lote_origem_data_id = $1
        """

        params = [lote["id"]]
        idx = 2

        sql, params, idx = aplicar_filtros_turmas_base(
            sql,
            params,
            idx,
            alias_t="base",
            alias_c="c",
            alias_u="u",
            alias_frm="frm",
            alias_trn="trn",
            alias_tsr="tsr",
            uo=uo,
            curso=curso,
            modalidade=modalidade,
            programa=programa,
            turma=turma,
            condicao_aluno=condicao_aluno,
            dt_inicio_de=dt_inicio_de,
            dt_inicio_ate=dt_inicio_ate,
            formato=formato,
            turno=turno,
            status_matricula=status_matricula,
            faixa_preenchimento=faixa_preenchimento,
            dt_mat_de=dt_mat_de,
            dt_mat_ate=dt_mat_ate,
            usar_filtro_padrao=usar_filtro_padrao,
            data_fim_padrao=data_fim_padrao,
        )
        
        sql += " GROUP BY 1"

        rows = await conn.fetch(sql, *params)

        rows_mat = []

        if dt_mat_de and dt_mat_ate:
            dt_de = datetime.fromisoformat(dt_mat_de).date()
            dt_ate = datetime.fromisoformat(dt_mat_ate).date()

            if dt_de.year == dt_ate.year and dt_de.month == dt_ate.month:
                sql_mat = """
                SELECT
                    CASE
                        WHEN COALESCE(t.vagas_total, 0) = 0 THEN 'Abaixo de 70%'
                        WHEN (COALESCE(tmm.matriculados, 0)::numeric / t.vagas_total::numeric) >= 1 THEN '>= 100%'
                        WHEN (COALESCE(tmm.matriculados, 0)::numeric / t.vagas_total::numeric) >= 0.9 THEN '90 a 99%'
                        WHEN (COALESCE(tmm.matriculados, 0)::numeric / t.vagas_total::numeric) >= 0.8 THEN '80 a 89%'
                        WHEN (COALESCE(tmm.matriculados, 0)::numeric / t.vagas_total::numeric) >= 0.7 THEN '70 a 79%'
                        ELSE 'Abaixo de 70%'
                    END AS faixa,
                    COUNT(*) AS total
                FROM turmas_movimento_mensal tmm
                JOIN turmas t
                  ON t.codigo = tmm.cod_turma
                LEFT JOIN curso c
                  ON c.codigo = t.cod_curso
                LEFT JOIN uo u
                  ON u.codigo = t.cod_uo
                LEFT JOIN formato frm
                  ON frm.codigo = t.cod_formato
                LEFT JOIN turnos trn
                  ON trn.codigo = t.cod_turno
                WHERE tmm.ano = $1
                  AND tmm.mes = $2
                """
                params_mat = [dt_de.year, dt_de.month]
                idx_mat = 3

                sql_mat, params_mat, idx_mat = aplicar_filtros_turmas_base(
                    sql_mat,
                    params_mat,
                    idx_mat,
                    alias_t="t",
                    alias_c="c",
                    alias_u="u",
                    alias_frm="frm",
                    alias_trn="trn",
                    alias_tsr="tsr",
                    uo=uo,
                    curso=curso,
                    modalidade=modalidade,
                    programa=programa,
                    turma=turma,
                    condicao_aluno=condicao_aluno,
                    dt_inicio_de=dt_inicio_de,
                    dt_inicio_ate=dt_inicio_ate,
                    formato=formato,
                    turno=turno,
                    status_matricula=status_matricula,
                    faixa_preenchimento=None,
                    dt_mat_de=None,
                    dt_mat_ate=None,
                    usar_filtro_padrao=False,
                    data_fim_padrao=data_fim_padrao,
                )

                sql_mat += " GROUP BY 1"

                rows_mat = await conn.fetch(sql_mat, *params_mat)

    ordem = {
        ">= 100%": 1,
        "90 a 99%": 2,
        "80 a 89%": 3,
        "70 a 79%": 4,
        "Abaixo de 70%": 5,
    }

    saida = [dict(r) for r in (rows_mat if rows_mat else rows)]
    saida.sort(key=lambda x: ordem.get(x["faixa"], 99))
    return saida

@router.get("/sge_turmas/grafico/matriculas_mes")
async def grafico_matriculas_mes(
    request: Request,
    uo: str | None = None,
    curso: str | None = None,
    modalidade: str | None = None,
    programa: str | None = None,
    turma: str | None = None,
    condicao_aluno: str | None = None,
    dt_inicio_de: str | None = None,
    dt_inicio_ate: str | None = None,
    formato: str | None = None,
    turno: str | None = None,
    status_matricula: str | None = None,
    faixa_preenchimento: str | None = None,
    dt_mat_de: str | None = None,
    dt_mat_ate: str | None = None,
):
    pool = request.app.state.pool

    data_fim_padrao = date(2026, 1, 1)
    usar_filtro_padrao = not dt_inicio_de and not dt_inicio_ate

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT id
            FROM data_import_lotes
            WHERE status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        if not lote:
            return []
        
        if condicao_aluno:
            sql = """
            SELECT
                TO_CHAR(da.data_matricula, 'YYYY-MM') AS mes,

                COUNT(*) FILTER (
                    WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) = 'MATRICULADO'
                ) AS matriculados,

                COUNT(*) FILTER (
                    WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) IN (
                        'PRE_MATRICULADO',
                        'PRE-MATRICULADO',
                        'PRÉ-MATRICULADO'
                    )
                ) AS pre_matriculados
            FROM sge_turma_detalhe_alunos da
            JOIN turmas t
            ON TRIM(UPPER(t.codigo_sge)) = TRIM(UPPER(da.cod_turma))
            LEFT JOIN curso c
            ON c.codigo = t.cod_curso
            LEFT JOIN turmas_status_resumo tsr
            ON tsr.cod_turma = t.codigo
            LEFT JOIN uo u
            ON u.codigo = t.cod_uo
            LEFT JOIN formato frm
            ON frm.codigo = t.cod_formato
            LEFT JOIN turnos trn
            ON trn.codigo = t.cod_turno
            WHERE da.lote_id = $1
            AND t.lote_origem_data_id = $1
            AND da.data_matricula IS NOT NULL
            AND regexp_replace(
                translate(
                    UPPER(TRIM(COALESCE(da.condicao_aluno, ''))),
                    'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                    'AAAAEEEIIIOOOOUUUC'
                ),
                '\\s+',
                ' ',
                'g'
            )
            =
            regexp_replace(
                translate(
                    UPPER(TRIM(COALESCE($2, ''))),
                    'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                    'AAAAEEEIIIOOOOUUUC'
                ),
                '\\s+',
                ' ',
                'g'
            )
            """

            params = [lote["id"], condicao_aluno]
            idx = 3

            sql, params, idx = aplicar_filtros_turmas_base(
                sql,
                params,
                idx,
                alias_t="t",
                alias_c="c",
                alias_u="u",
                alias_frm="frm",
                alias_trn="trn",
                alias_tsr="tsr",
                uo=uo,
                curso=curso,
                modalidade=modalidade,
                programa=programa,
                turma=turma,
                condicao_aluno=None,
                dt_inicio_de=dt_inicio_de,
                dt_inicio_ate=dt_inicio_ate,
                formato=formato,
                turno=turno,
                status_matricula=status_matricula,
                faixa_preenchimento=faixa_preenchimento,
                dt_mat_de=dt_mat_de,
                dt_mat_ate=dt_mat_ate,
                usar_filtro_padrao=usar_filtro_padrao,
                data_fim_padrao=data_fim_padrao,
            )

            sql += """
            GROUP BY TO_CHAR(da.data_matricula, 'YYYY-MM')
            ORDER BY TO_CHAR(da.data_matricula, 'YYYY-MM')
            """

            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]

        sql = """
        SELECT
            TO_CHAR(MAKE_DATE(tmm.ano, tmm.mes, 1), 'YYYY-MM') AS mes,
            COALESCE(SUM(COALESCE(tmm.matriculados, 0)), 0) AS matriculados,
            COALESCE(SUM(COALESCE(tmm.pre_matriculados, 0)), 0) AS pre_matriculados
        FROM turmas_movimento_mensal tmm
        JOIN turmas t
        ON t.codigo = tmm.cod_turma
        LEFT JOIN curso c
        ON c.codigo = t.cod_curso
        LEFT JOIN turmas_status_resumo tsr
        ON tsr.cod_turma = t.codigo
        LEFT JOIN uo u
        ON u.codigo = t.cod_uo
        LEFT JOIN formato frm
        ON frm.codigo = t.cod_formato
        LEFT JOIN turnos trn
        ON trn.codigo = t.cod_turno
        WHERE t.lote_origem_data_id = $1
        """

        params = [lote["id"]]
        idx = 2

        sql, params, idx = aplicar_filtros_turmas_base(
            sql,
            params,
            idx,
            alias_t="t",
            alias_c="c",
            alias_u="u",
            alias_frm="frm",
            alias_trn="trn",
            alias_tsr="tsr",
            uo=uo,
            curso=curso,
            modalidade=modalidade,
            programa=programa,
            turma=turma,
            condicao_aluno=condicao_aluno,
            dt_inicio_de=dt_inicio_de,
            dt_inicio_ate=dt_inicio_ate,
            formato=formato,
            turno=turno,
            status_matricula=status_matricula,
            faixa_preenchimento=faixa_preenchimento,
            dt_mat_de=None,
            dt_mat_ate=None,
            usar_filtro_padrao=False,
            data_fim_padrao=data_fim_padrao,
        )

        if dt_mat_de and dt_mat_ate:
            dt_de = datetime.fromisoformat(dt_mat_de).date()
            dt_ate = datetime.fromisoformat(dt_mat_ate).date()

            sql += f"""
            AND (
                (tmm.ano > ${idx} OR (tmm.ano = ${idx} AND tmm.mes >= ${idx+1}))
                AND
                (tmm.ano < ${idx+2} OR (tmm.ano = ${idx+2} AND tmm.mes <= ${idx+3}))
            )
            """
            params.extend([dt_de.year, dt_de.month, dt_ate.year, dt_ate.month])
            idx += 4

        sql += """
        GROUP BY tmm.ano, tmm.mes
        ORDER BY tmm.ano, tmm.mes
        """

        rows = await conn.fetch(sql, *params)

    return [dict(r) for r in rows]

@router.get("/sge_turmas/estado")
async def sge_turmas_estado(
    request: Request,
    uo: str | None = None,
    curso: str | None = None,
    modalidade: str | None = None,
    programa: str | None = None,
    turma: str | None = None,
    condicao_aluno: str | None = None,
    dt_inicio_de: str | None = None,
    dt_inicio_ate: str | None = None,
    formato: str | None = None,
    turno: str | None = None,
    status_matricula: str | None = None,
    faixa_preenchimento: str | None = None,
    dt_mat_de: str | None = None,
    dt_mat_ate: str | None = None,
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT id
            FROM data_import_lotes
            WHERE status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        if not lote:
            return []
        
        if condicao_aluno or dt_mat_de or dt_mat_ate:
            sql = """
            SELECT
                t.codigo_sge AS cod_turma,
                COALESCE(NULLIF(TRIM(UPPER(c.nome_curso)), ''), '') AS curso,
                u.nome AS filial,
                t.data_inicio,
                UPPER(COALESCE(trn.nome, '')) AS turno,
                COALESCE(frm.nome, '') AS formato,
                MAX(t.vagas_total) AS vagas,

                COUNT(*) FILTER (
                    WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) = 'MATRICULADO'
                ) AS matriculados,

                COUNT(*) FILTER (
                    WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) IN (
                        'PRE_MATRICULADO',
                        'PRE-MATRICULADO',
                        'PRÉ-MATRICULADO'
                    )
                ) AS pre_matriculados,

                COUNT(*) FILTER (
                    WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) = 'CANCELADO'
                ) AS cancelados,

                COUNT(*) FILTER (
                    WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) = 'DESISTENTE'
                ) AS desistentes,

                COUNT(*) FILTER (
                    WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) = 'EVADIDO'
                ) AS evadidos,

                GREATEST(
                    COALESCE(MAX(t.vagas_total), 0)
                    - COUNT(*) FILTER (
                        WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) = 'MATRICULADO'
                    )
                    - COUNT(*) FILTER (
                        WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) IN (
                            'PRE_MATRICULADO',
                            'PRE-MATRICULADO',
                            'PRÉ-MATRICULADO'
                        )
                    ),
                    0
                ) AS vagas_restantes,

                (
                    COUNT(*) FILTER (
                        WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) = 'MATRICULADO'
                    )
                    +
                    COUNT(*) FILTER (
                        WHERE TRIM(UPPER(COALESCE(da.status_matricula, ''))) IN (
                            'PRE_MATRICULADO',
                            'PRE-MATRICULADO',
                            'PRÉ-MATRICULADO'
                        )
                    )
                ) AS vagas_preenchidas,

                u.cod_subregiao AS cod_subregiao

            FROM sge_turma_detalhe_alunos da
            JOIN turmas t
            ON TRIM(UPPER(t.codigo_sge)) = TRIM(UPPER(da.cod_turma))
            LEFT JOIN curso c
            ON c.codigo = t.cod_curso
            LEFT JOIN uo u
            ON u.codigo = t.cod_uo
            LEFT JOIN turnos trn
            ON trn.codigo = t.cod_turno
            LEFT JOIN formato frm
            ON frm.codigo = t.cod_formato
            LEFT JOIN turmas_status_resumo tsr
            ON tsr.cod_turma = t.codigo
            WHERE da.lote_id = $1
            AND t.lote_origem_data_id = $1
            """

            params = [lote["id"]]
            idx = 2

            if condicao_aluno:
                sql += f"""
                AND regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(da.condicao_aluno, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                =
                regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(${idx}, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                """
                params.append(condicao_aluno)
                idx += 1

            if dt_mat_de:
                sql += f" AND da.data_matricula >= ${idx}"
                params.append(datetime.fromisoformat(dt_mat_de).date())
                idx += 1

            if dt_mat_ate:
                sql += f" AND da.data_matricula <= ${idx}"
                params.append(datetime.fromisoformat(dt_mat_ate).date())
                idx += 1
            
            data_fim_padrao = date(2026, 1, 1)
            usar_filtro_padrao = not dt_inicio_de and not dt_inicio_ate

            sql, params, idx = aplicar_filtros_turmas_base(
                sql,
                params,
                idx,
                alias_t="t",
                alias_c="c",
                alias_u="u",
                alias_frm="frm",
                alias_trn="trn",
                alias_tsr="tsr",
                uo=uo,
                curso=curso,
                modalidade=modalidade,
                programa=programa,
                turma=turma,
                condicao_aluno=None,
                dt_inicio_de=dt_inicio_de,
                dt_inicio_ate=dt_inicio_ate,
                formato=formato,
                turno=turno,
                status_matricula=status_matricula,
                faixa_preenchimento=faixa_preenchimento,
                dt_mat_de=None,
                dt_mat_ate=None,
                usar_filtro_padrao=usar_filtro_padrao,
                data_fim_padrao=data_fim_padrao,
            )

            sql += """
            GROUP BY
                t.codigo_sge,
                c.nome_curso,
                u.nome,
                t.data_inicio,
                trn.nome,
                frm.nome,
                u.cod_subregiao
            ORDER BY u.nome, c.nome_curso, t.codigo_sge
            """

            rows = await conn.fetch(sql, *params)

            dados = [dict(r) for r in rows]

            total_global_matriculas = sum(float(d.get("matriculados") or 0) for d in dados)

            for d in dados:
                matriculados = float(d.get("matriculados") or 0)
                d["pct_rep"] = round((matriculados / total_global_matriculas) * 100, 1) if total_global_matriculas > 0 else 0

            return dados

        sql = """
        SELECT
            base.codigo_sge AS cod_turma,
            COALESCE(NULLIF(TRIM(UPPER(c.nome_curso)), ''), '') AS curso,
            u.nome AS filial,
            base.data_inicio,
            UPPER(COALESCE(trn.nome, '')) AS turno,
            COALESCE(
                frm.nome,
                CASE
                    WHEN base.cod_formato = 4 THEN 'PRESENCIAL'
                    WHEN base.cod_formato = 5 THEN 'EAD'
                    WHEN base.cod_formato = 6 THEN 'SEMIPRESENCIAL'
                    ELSE ''
                END
            ) AS formato,
            base.vagas_total AS vagas,
            COALESCE(SUM(tsr.matriculados), 0) AS matriculados,
            COALESCE(SUM(tsr.pre_matriculados), 0) AS pre_matriculados,
            COALESCE(SUM(tsr.cancelados), 0) AS cancelados,
            COALESCE(SUM(tsr.desistentes), 0) AS desistentes,
            COALESCE(SUM(tsr.evadidos), 0) AS evadidos,
            GREATEST(
                COALESCE(base.vagas_total, 0)
                - COALESCE(SUM(tsr.matriculados), 0)
                - COALESCE(SUM(tsr.pre_matriculados), 0),
                0
            ) AS vagas_restantes,
            (COALESCE(SUM(tsr.matriculados), 0) + COALESCE(SUM(tsr.pre_matriculados), 0)) AS vagas_preenchidas,
            u.cod_subregiao AS cod_subregiao
        FROM (
            SELECT
                t.codigo,
                t.codigo_sge,
                t.vagas_total,
                t.lote_origem_data_id,
                t.data_inicio,
                t.data_fim,
                t.ano_referencia,
                t.cod_uo,
                t.cod_curso,
                t.cod_modalidade,
                t.cod_programa,
                t.cod_formato,
                t.cod_turno
            FROM turmas t
        ) base
        LEFT JOIN curso c
        ON c.codigo = base.cod_curso
        LEFT JOIN uo u
        ON u.codigo = base.cod_uo
        LEFT JOIN turnos trn
        ON trn.codigo = base.cod_turno
        LEFT JOIN formato frm
        ON frm.codigo = base.cod_formato
        LEFT JOIN turmas_status_resumo tsr
        ON tsr.cod_turma = base.codigo
        WHERE base.lote_origem_data_id = $1
        """

        params = [lote["id"]]
        idx = 2

        data_fim_padrao = date(2026, 1, 1)
        usar_filtro_padrao = not dt_inicio_de and not dt_inicio_ate

        sql, params, idx = aplicar_filtros_turmas_base(
            sql,
            params,
            idx,
            alias_t="base",
            alias_c="c",
            alias_u="u",
            alias_frm="frm",
            alias_trn="trn",
            alias_tsr="tsr",
            uo=uo,
            curso=curso,
            modalidade=modalidade,
            programa=programa,
            turma=turma,
            condicao_aluno=None,
            dt_inicio_de=dt_inicio_de,
            dt_inicio_ate=dt_inicio_ate,
            formato=formato,
            turno=turno,
            status_matricula=status_matricula,
            faixa_preenchimento=faixa_preenchimento,
            dt_mat_de=None,
            dt_mat_ate=None,
            usar_filtro_padrao=usar_filtro_padrao,
            data_fim_padrao=data_fim_padrao,
        )

        sql += """
        GROUP BY
            base.codigo_sge,
            c.nome_curso,
            u.nome,
            base.data_inicio,
            trn.nome,
            frm.nome,
            base.cod_formato,
            base.vagas_total,
            u.cod_subregiao
        ORDER BY u.nome, c.nome_curso, base.codigo_sge
        """

        rows = await conn.fetch(sql, *params)

        dados = [dict(r) for r in rows]

        total_global_matriculas = sum(float(d.get("matriculados") or 0) for d in dados)

        for d in dados:
            matriculados = float(d.get("matriculados") or 0)
            d["pct_rep"] = round((matriculados / total_global_matriculas) * 100, 1) if total_global_matriculas > 0 else 0

        return dados

@router.get("/sge_turmas/tabela/uo")
async def sge_turmas_tabela_uo(
    request: Request,
    uo: str | None = None,
    curso: str | None = None,
    modalidade: str | None = None,
    programa: str | None = None,
    turma: str | None = None,
    dt_inicio_de: str | None = None,
    dt_inicio_ate: str | None = None,
    formato: str | None = None,
    turno: str | None = None,
    status_matricula: str | None = None,
    faixa_preenchimento: str | None = None,
    dt_mat_de: str | None = None,
    dt_mat_ate: str | None = None,
    condicao_aluno: str | None = None,
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT id
            FROM data_import_lotes
            WHERE status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        if not lote:
            return []
        
        if condicao_aluno or dt_mat_de or dt_mat_ate:
            sql = """
            WITH base_alunos AS (
                SELECT
                    t.codigo AS cod_turma,
                    t.vagas_total,
                    u.nome AS uo,
                    da.status_matricula,
                    da.condicao_aluno,
                    da.data_matricula
                FROM sge_turma_detalhe_alunos da
                JOIN turmas t
                ON TRIM(UPPER(t.codigo_sge)) = TRIM(UPPER(da.cod_turma))
                LEFT JOIN curso c
                ON c.codigo = t.cod_curso
                LEFT JOIN uo u
                ON u.codigo = t.cod_uo
                LEFT JOIN formato frm
                ON frm.codigo = t.cod_formato
                LEFT JOIN turnos trn
                ON trn.codigo = t.cod_turno
                LEFT JOIN turmas_status_resumo tsr
                ON tsr.cod_turma = t.codigo
                WHERE da.lote_id = $1
                AND t.lote_origem_data_id = $1
                AND TRIM(COALESCE(u.nome, '')) <> ''
            """

            params = [lote["id"]]
            idx = 2

            if condicao_aluno:
                sql += f"""
                AND regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(da.condicao_aluno, ''))),
                        'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                =
                regexp_replace(
                    translate(
                        UPPER(TRIM(COALESCE(${idx}, ''))),
                        'ÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÛÇ',
                        'AAAAEEEIIOOOOUUUC'
                    ),
                    '\\s+',
                    ' ',
                    'g'
                )
                """
                params.append(condicao_aluno)
                idx += 1

            if dt_mat_de:
                sql += f" AND da.data_matricula >= ${idx}"
                params.append(datetime.fromisoformat(dt_mat_de).date())
                idx += 1

            if dt_mat_ate:
                sql += f" AND da.data_matricula <= ${idx}"
                params.append(datetime.fromisoformat(dt_mat_ate).date())
                idx += 1

            sql, params, idx = aplicar_filtros_turmas_base(
                sql,
                params,
                idx,
                alias_t="t",
                alias_c="c",
                alias_u="u",
                alias_frm="frm",
                alias_trn="trn",
                alias_tsr="tsr",
                uo=uo,
                curso=curso,
                modalidade=modalidade,
                programa=programa,
                turma=turma,
                condicao_aluno=None,
                dt_inicio_de=dt_inicio_de,
                dt_inicio_ate=dt_inicio_ate,
                formato=formato,
                turno=turno,
                status_matricula=status_matricula,
                faixa_preenchimento=faixa_preenchimento,
                dt_mat_de=None,
                dt_mat_ate=None,
                usar_filtro_padrao=False,
                data_fim_padrao=None,
            )

            sql += """
            ),
            turmas_unicas AS (
                SELECT DISTINCT
                    cod_turma,
                    vagas_total,
                    uo
                FROM base_alunos
            ),
            vagas_por_uo AS (
                SELECT
                    uo,
                    COUNT(*) AS qtd_turmas,
                    COALESCE(SUM(vagas_total), 0) AS qtd_vagas
                FROM turmas_unicas
                GROUP BY uo
            ),
            alunos_por_uo AS (
                SELECT
                    uo,
                    COUNT(*) FILTER (
                        WHERE TRIM(UPPER(COALESCE(status_matricula, ''))) = 'MATRICULADO'
                    ) AS qtd_matriculados,
                    COUNT(*) FILTER (
                        WHERE TRIM(UPPER(COALESCE(status_matricula, ''))) IN (
                            'PRE_MATRICULADO',
                            'PRE-MATRICULADO',
                            'PRÉ-MATRICULADO'
                        )
                    ) AS qtd_pre_matriculados
                FROM base_alunos
                GROUP BY uo
            )
            SELECT
                v.uo,
                v.qtd_turmas,
                v.qtd_vagas,
                COALESCE(a.qtd_matriculados, 0) AS qtd_matriculados,
                COALESCE(a.qtd_pre_matriculados, 0) AS qtd_pre_matriculados
            FROM vagas_por_uo v
            LEFT JOIN alunos_por_uo a
            ON a.uo = v.uo
            ORDER BY v.uo
            """

            rows_base = await conn.fetch(sql, *params)

            total_global_matriculas = sum(int(r["qtd_matriculados"] or 0) for r in rows_base)

            saida = []
            for r in rows_base:
                d = dict(r)
                qtd_vagas = int(d["qtd_vagas"] or 0)
                qtd_matriculados = int(d["qtd_matriculados"] or 0)
                qtd_pre = int(d["qtd_pre_matriculados"] or 0)

                d["pct_rep"] = round((qtd_matriculados / total_global_matriculas) * 100, 1) if total_global_matriculas > 0 else 0
                d["pct_matriculados"] = round((qtd_matriculados / qtd_vagas) * 100, 1) if qtd_vagas else 0
                d["pct_pre_matriculados"] = round((qtd_pre / qtd_vagas) * 100, 1) if qtd_vagas else 0

                saida.append(d)

            return saida

        sql = """
        SELECT
            u.nome AS uo,
            COUNT(*) AS qtd_turmas,
            COALESCE(SUM(base.vagas_total), 0) AS qtd_vagas,
            COALESCE(SUM(COALESCE(tsr.matriculados, 0)), 0) AS qtd_matriculados,
            COALESCE(SUM(COALESCE(tsr.pre_matriculados, 0)), 0) AS qtd_pre_matriculados
        FROM (
            SELECT
                t.codigo,
                t.codigo_sge,
                t.vagas_total,
                t.data_inicio,
                t.data_fim,
                t.ano_referencia,
                t.cod_uo,
                t.cod_curso,
                t.cod_modalidade,
                t.cod_programa, 
                t.cod_formato,
                t.cod_turno
            FROM turmas t
        ) base
        LEFT JOIN curso c
        ON c.codigo = base.cod_curso
        LEFT JOIN uo u
        ON u.codigo = base.cod_uo
        LEFT JOIN formato frm
        ON frm.codigo = base.cod_formato
        LEFT JOIN turnos trn
        ON trn.codigo = base.cod_turno
        LEFT JOIN turmas_status_resumo tsr
        ON tsr.cod_turma = base.codigo
        WHERE 1=1
        AND TRIM(COALESCE(u.nome, '')) <> ''
        """

        sql_mat = """
        SELECT
            u.nome AS uo,
            COALESCE(SUM(tmm.matriculados), 0) AS qtd_matriculados
        FROM turmas_movimento_mensal tmm
        JOIN turmas t
          ON t.codigo = tmm.cod_turma
        LEFT JOIN curso c
          ON c.codigo = t.cod_curso
        LEFT JOIN uo u
          ON u.codigo = t.cod_uo
        LEFT JOIN formato frm
          ON frm.codigo = t.cod_formato
        LEFT JOIN turnos trn
          ON trn.codigo = t.cod_turno
        LEFT JOIN turmas_status_resumo tsr
          ON tsr.cod_turma = t.codigo
        WHERE 1=1
        AND TRIM(COALESCE(u.nome, '')) <> ''
        """
        
        data_fim_padrao = date(2026, 1, 1)
        usar_filtro_padrao = not dt_inicio_de and not dt_inicio_ate
        params_mat = []
        idx_mat = 1

        sql_mat, params_mat, idx_mat = aplicar_filtros_turmas_base(
            sql_mat,
            params_mat,
            idx_mat,
            alias_t="t",
            alias_c="c",
            alias_u="u",
            alias_frm="frm",
            alias_trn="trn",
            alias_tsr="tsr",
            uo=uo,
            curso=curso,
            modalidade=modalidade,
            programa=programa,
            turma=turma,
            condicao_aluno=condicao_aluno,
            dt_inicio_de=dt_inicio_de,
            dt_inicio_ate=dt_inicio_ate,
            formato=formato,
            turno=turno,
            status_matricula=status_matricula,
            faixa_preenchimento=faixa_preenchimento,
            dt_mat_de=None,
            dt_mat_ate=None,
            usar_filtro_padrao=False,
            data_fim_padrao=data_fim_padrao,
        )

        if dt_mat_de and dt_mat_ate:
            dt_de = datetime.fromisoformat(dt_mat_de).date()
            dt_ate = datetime.fromisoformat(dt_mat_ate).date()

            sql_mat += f"""
            AND (
                (tmm.ano > ${idx_mat} OR (tmm.ano = ${idx_mat} AND tmm.mes >= ${idx_mat+1}))
                AND
                (tmm.ano < ${idx_mat+2} OR (tmm.ano = ${idx_mat+2} AND tmm.mes <= ${idx_mat+3}))
            )
            """
            params_mat.extend([dt_de.year, dt_de.month, dt_ate.year, dt_ate.month])
            idx_mat += 4
        else:
            sql_mat += f" AND tmm.ano = ${idx_mat}"
            params_mat.append(date.today().year)
            idx_mat += 1

        sql_mat += " GROUP BY u.nome ORDER BY u.nome"
        rows_mat = await conn.fetch(sql_mat, *params_mat)

        params = []
        idx = 1

        sql, params, idx = aplicar_filtros_turmas_base(
            sql,
            params,
            idx,
            alias_t="base",
            alias_c="c",
            alias_u="u",
            alias_frm="frm",
            alias_trn="trn",
            alias_tsr="tsr",
            uo=uo,
            curso=curso,
            modalidade=modalidade,
            programa=programa,
            turma=turma,
            condicao_aluno=condicao_aluno,
            dt_inicio_de=dt_inicio_de,
            dt_inicio_ate=dt_inicio_ate,
            formato=formato,
            turno=turno,
            status_matricula=status_matricula,
            faixa_preenchimento=faixa_preenchimento,
            dt_mat_de=dt_mat_de,
            dt_mat_ate=dt_mat_ate,
            usar_filtro_padrao=usar_filtro_padrao,
            data_fim_padrao=data_fim_padrao,
        )

        sql += " GROUP BY u.nome ORDER BY u.nome"

        rows_base = await conn.fetch(sql, *params)

        total_global_matriculas = sum(int(r["qtd_matriculados"] or 0) for r in rows_base)

        saida = []
        for r in rows_base:
            d = dict(r)
            qtd_vagas = int(d["qtd_vagas"] or 0)
            qtd_matriculados = int(d["qtd_matriculados"] or 0)
            qtd_pre = int(d["qtd_pre_matriculados"] or 0)

            d["pct_rep"] = round((qtd_matriculados / total_global_matriculas) * 100, 1) if total_global_matriculas > 0 else 0
            d["pct_matriculados"] = round((qtd_matriculados / qtd_vagas) * 100, 1) if qtd_vagas else 0
            d["pct_pre_matriculados"] = round((qtd_pre / qtd_vagas) * 100, 1) if qtd_vagas else 0

            saida.append(d)

        return saida

@router.get("/sge_turmas/uos")
async def sge_turmas_uos(request: Request):
    pool = request.app.state.pool
    data_fim_padrao = date(2026, 1, 1)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                u.codigo,
                u.nome
            FROM turmas t
            JOIN uo u
              ON u.codigo = t.cod_uo
            WHERE u.nome IS NOT NULL
              AND TRIM(u.nome) <> ''
              AND t.data_fim >= $1
            ORDER BY u.nome
            """,
            data_fim_padrao
        )

    return [dict(r) for r in rows]

@router.get("/condicao_aluno/list")
async def condicao_aluno_list():
    return [
        "GRATUIDADE REGIMENTAL",
        "GRATUIDADE NÃO REGIMENTAL",
        "PAGO POR PESSOA FÍSICA OU EMPRESA",
        "INDEFINIDO",
    ]

@router.get("/sge_turmas/cursos")
async def sge_turmas_cursos(request: Request):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT id
            FROM sge_import_lotes
            WHERE tipo_arquivo = 'relatorio_geral_turmas'
              AND status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        if not lote:
            return []

        rows = await conn.fetch(
            """
            SELECT DISTINCT
                c.nome_curso
            FROM sge_turmas_snapshot s
            JOIN curso c
              ON c.codigo = s.cod_curso
            WHERE s.lote_id = $1
              AND c.nome_curso IS NOT NULL
              AND TRIM(c.nome_curso) <> ''
            ORDER BY c.nome_curso
            """,
            lote["id"]
        )

    return [r["nome_curso"] for r in rows]

@router.get("/sge_turmas/turmas")
async def sge_turmas_list(request: Request, q: str | None = None):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT id
            FROM sge_import_lotes
            WHERE tipo_arquivo = 'relatorio_geral_turmas'
              AND status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        if not lote:
            return []

        sql = """
        SELECT DISTINCT
            t.codigo_sge,
            c.nome_curso
        FROM sge_turmas_snapshot s
        JOIN turmas t ON t.codigo = s.cod_turma
        JOIN sge_turma_detalhe_alunos da
        ON da.cod_turma = t.codigo_sge
        LEFT JOIN curso c ON c.codigo = s.cod_curso
        WHERE s.lote_id = $1
        """

        params = [lote["id"]]
        idx = 2

        if q:
            sql += f"""
            AND (
                t.codigo_sge ILIKE ${idx}
                OR c.nome_curso ILIKE ${idx}
            )
            """
            params.append(f"%{q}%")
            idx += 1

        sql += " ORDER BY t.codigo_sge LIMIT 100"

        rows = await conn.fetch(sql, *params)

    return [dict(r) for r in rows]

def aplicar_filtros_turmas(sql: str, params: list, idx: int, filtros: dict):
    uo = filtros.get("uo")
    curso = filtros.get("curso")
    turma = filtros.get("turma")
    condicao_aluno = filtros.get("condicao_aluno")

    dt_inicio_de = filtros.get("dt_inicio_de")
    dt_inicio_ate = filtros.get("dt_inicio_ate")
    formato = filtros.get("formato")
    turno = filtros.get("turno")
    status_matricula = filtros.get("status_matricula")
    faixa_preenchimento = filtros.get("faixa_preenchimento")
    dt_mat_de = filtros.get("dt_mat_de")
    dt_mat_ate = filtros.get("dt_mat_ate")

    if uo:
        sql += f" AND u.codigo = ${idx}"
        params.append(int(uo))
        idx += 1

    if curso:
        sql += f" AND c.nome_curso = ${idx}"
        params.append(curso)
        idx += 1

    if turma:
        sql += f" AND t.codigo_sge = ${idx}"
        params.append(turma)
        idx += 1

    if condicao_aluno:
        sql += f"""
        AND EXISTS (
            SELECT 1
            FROM sge_turma_detalhe_alunos da
            WHERE da.cod_turma = t.codigo_sge
              AND da.condicao_aluno = ${idx}
        )
        """
        params.append(condicao_aluno)
        idx += 1

    if dt_inicio_de:
        sql += f" AND t.data_inicio >= ${idx}"
        params.append(datetime.fromisoformat(dt_inicio_de).date())
        idx += 1

    if dt_inicio_ate:
        sql += f" AND t.data_inicio <= ${idx}"
        params.append(datetime.fromisoformat(dt_inicio_ate).date())
        idx += 1

    if formato:
        sql += f" AND COALESCE(frm.nome, '') = ${idx}"
        params.append(formato.strip().upper())
        idx += 1

    if turno:
        sql += f" AND COALESCE(trn.nome, '') = ${idx}"
        params.append(turno.strip().upper())
        idx += 1

    if status_matricula:
        status_matricula = status_matricula.strip().upper()

        if status_matricula == "MATRICULADO":
            sql += " AND COALESCE(s.qtd_matriculado, 0) > 0"
        elif status_matricula == "PRE_MATRICULADO":
            sql += " AND COALESCE(s.qtd_pre_matriculado, 0) > 0"
        elif status_matricula == "CANCELADO":
            sql += " AND COALESCE(s.qtd_cancelado, 0) > 0"

    if faixa_preenchimento:
        pct_expr = """
        CASE
            WHEN COALESCE(s.vagas_total, 0) = 0 THEN NULL
            ELSE (COALESCE(s.qtd_matriculado, 0)::numeric / s.vagas_total::numeric) * 100
        END
        """

        if faixa_preenchimento == "100":
            sql += f" AND ({pct_expr}) >= 100"
        elif faixa_preenchimento == "90_99":
            sql += f" AND ({pct_expr}) >= 90 AND ({pct_expr}) < 100"
        elif faixa_preenchimento == "80_89":
            sql += f" AND ({pct_expr}) >= 80 AND ({pct_expr}) < 90"
        elif faixa_preenchimento == "70_79":
            sql += f" AND ({pct_expr}) >= 70 AND ({pct_expr}) < 80"
        elif faixa_preenchimento == "lt_70":
            sql += f" AND ({pct_expr}) < 70"

    if dt_mat_de or dt_mat_ate or status_matricula:
        sql += """
        AND EXISTS (
            SELECT 1
            FROM sge_turma_detalhe_alunos da2
            WHERE da2.cod_turma = t.codigo_sge
        """

        if dt_mat_de:
            sql += f" AND da2.data_matricula >= ${idx}"
            params.append(datetime.fromisoformat(dt_mat_de).date())
            idx += 1

        if dt_mat_ate:
            sql += f" AND da2.data_matricula <= ${idx}"
            params.append(datetime.fromisoformat(dt_mat_ate).date())
            idx += 1

        if status_matricula:
            sql += f" AND UPPER(COALESCE(da2.status_matricula, '')) = ${idx}"
            params.append(status_matricula)
            idx += 1

        sql += ")"

    return sql, params, idx

@router.get("/planejamento/resumo")
async def planejamento_resumo(
    request: Request,
    ano: int = 2026,
    subregioes: str | None = None
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote_id = await conn.fetchval(
            """
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """,
            ano
        )

        if not lote_id:
            return {
                "matriculas_total": 0,
                "gr_matriculas": 0,
                "gnr_matriculas": 0,
                "pago_matriculas": 0,
                "ha_total": 0,
                "gr_ha": 0,
                "gnr_ha": 0,
                "pago_ha": 0,
                "receita_total": 0,
                "gr_receita": 0,
                "gnr_receita": 0,
                "pago_receita": 0,
                "gr_matriculas_pct": 0,
                "gnr_matriculas_pct": 0,
                "pago_matriculas_pct": 0,
                "gr_ha_pct": 0,
                "gnr_ha_pct": 0,
                "pago_ha_pct": 0,
                "gr_receita_pct": 0,
                "gnr_receita_pct": 0,
                "pago_receita_pct": 0,
            }

        params = [lote_id]
        filtro_sub = ""

        if subregioes:
            ids = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
            if ids:
                filtro_sub = f" AND s.codigo = ANY(${len(params)+1}::int[])"
                params.append(ids)

        sql = f"""
        WITH base AS (
            SELECT
                UPPER(TRIM(COALESCE(ps.financiamento_raw, ''))) AS financiamento,
                UPPER(TRIM(COALESCE(ps.conta, ''))) AS conta,
                COALESCE(ps.jan, 0) AS jan,
                COALESCE(ps.fev, 0) AS fev,
                COALESCE(ps.mar, 0) AS mar,
                COALESCE(ps.abr, 0) AS abr,
                COALESCE(ps.mai, 0) AS mai,
                COALESCE(ps.jun, 0) AS jun,
                COALESCE(ps.jul, 0) AS jul,
                COALESCE(ps.ago, 0) AS ago,
                COALESCE(ps.set_, 0) AS set_,
                COALESCE(ps.out_, 0) AS out_,
                COALESCE(ps.nov, 0) AS nov,
                COALESCE(ps.dez, 0) AS dez
            FROM planejamento_staging ps
            JOIN subregioes s
              ON UPPER(TRIM(s.nome)) = UPPER(TRIM(ps.subregiao))
            WHERE ps.lote_id = $1
              AND ps.flag_valida = TRUE
              AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
              {filtro_sub}
        )
        SELECT
            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS matriculas_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gnr_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS pago_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS ha_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_ha,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gnr_ha,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS pago_ha,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS receita_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_receita,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gnr_receita,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS pago_receita
        FROM base
        """

        row = await conn.fetchrow(sql, *params)

    d = dict(row or {})

    def pct(parte, total):
        return round((float(parte or 0) / float(total or 0)) * 100, 2) if float(total or 0) else 0

    d["gr_matriculas_pct"] = pct(d["gr_matriculas"], d["matriculas_total"])
    d["gnr_matriculas_pct"] = pct(d["gnr_matriculas"], d["matriculas_total"])
    d["pago_matriculas_pct"] = pct(d["pago_matriculas"], d["matriculas_total"])

    d["gr_ha_pct"] = pct(d["gr_ha"], d["ha_total"])
    d["gnr_ha_pct"] = pct(d["gnr_ha"], d["ha_total"])
    d["pago_ha_pct"] = pct(d["pago_ha"], d["ha_total"])

    d["gr_receita_pct"] = pct(d["gr_receita"], d["receita_total"])
    d["gnr_receita_pct"] = pct(d["gnr_receita"], d["receita_total"])
    d["pago_receita_pct"] = pct(d["pago_receita"], d["receita_total"])

    return d

@router.get("/planejamento/mensal")
async def planejamento_mensal(request: Request, ano: int = 2026):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                mes,
                COALESCE(SUM(matriculas_meta), 0) AS matriculas_meta,
                COALESCE(SUM(ha_meta), 0) AS ha_meta,
                COALESCE(SUM(receita_meta), 0) AS receita_meta,
                COALESCE(SUM(matriculas_proj), 0) AS matriculas_proj,
                COALESCE(SUM(ha_proj), 0) AS ha_proj,
                COALESCE(SUM(receita_proj), 0) AS receita_proj,
                COALESCE(SUM(matriculas_real), 0) AS matriculas_real,
                COALESCE(SUM(ha_real), 0) AS ha_real,
                COALESCE(SUM(receita_real), 0) AS receita_real
            FROM (
                SELECT
                    m.mes,
                    m.matriculas_meta,
                    m.ha_meta,
                    m.receita_meta,
                    0::numeric AS matriculas_proj,
                    0::numeric AS ha_proj,
                    0::numeric AS receita_proj,
                    0::numeric AS matriculas_real,
                    0::numeric AS ha_real,
                    0::numeric AS receita_real
                FROM meta_programas m
                WHERE m.ano = $1

                UNION ALL

                SELECT
                    p.mes,
                    0::numeric AS matriculas_meta,
                    0::numeric AS ha_meta,
                    0::numeric AS receita_meta,
                    p.matriculas_proj,
                    p.ha_proj,
                    p.receita_proj,
                    0::numeric AS matriculas_real,
                    0::numeric AS ha_real,
                    0::numeric AS receita_real
                FROM projetado_programas p
                WHERE p.ano = $1

                UNION ALL

                SELECT
                    r.mes,
                    0::numeric AS matriculas_meta,
                    0::numeric AS ha_meta,
                    0::numeric AS receita_meta,
                    0::numeric AS matriculas_proj,
                    0::numeric AS ha_proj,
                    0::numeric AS receita_proj,
                    r.matriculas_real,
                    r.ha_real,
                    r.receita_real
                FROM realizado_programas r
                WHERE r.ano = $1
            ) base
            GROUP BY mes
            ORDER BY mes
            """,
            ano
        )

    return [dict(r) for r in rows]

@router.get("/planejamento/programas")
async def planejamento_programas(request: Request, ano: int = 2026):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.nome_programa,
                COALESCE(SUM(m.matriculas_meta), 0) AS matriculas_meta,
                COALESCE(SUM(m.ha_meta), 0) AS ha_meta,
                COALESCE(SUM(m.receita_meta), 0) AS receita_meta,
                COALESCE(SUM(pr.matriculas_proj), 0) AS matriculas_proj,
                COALESCE(SUM(pr.ha_proj), 0) AS ha_proj,
                COALESCE(SUM(pr.receita_proj), 0) AS receita_proj,
                COALESCE(SUM(r.matriculas_real), 0) AS matriculas_real,
                COALESCE(SUM(r.ha_real), 0) AS ha_real,
                COALESCE(SUM(r.receita_real), 0) AS receita_real
            FROM ofertas_programas o
            JOIN programas p
              ON p.codigo = o.cod_programa
            LEFT JOIN meta_programas m
              ON m.cod_oferta = o.codigo
             AND m.ano = o.ano
            LEFT JOIN projetado_programas pr
              ON pr.cod_oferta = o.codigo
             AND pr.ano = o.ano
            LEFT JOIN realizado_programas r
              ON r.cod_oferta = o.codigo
             AND r.ano = o.ano
            WHERE o.ano = $1
            GROUP BY p.nome_programa
            ORDER BY p.nome_programa
            """,
            ano
        )

    return [dict(r) for r in rows]

@router.get("/planejamento/uo")
async def planejamento_uo(request: Request, ano: int = 2026):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                u.nome AS uo,
                COALESCE(SUM(m.matriculas_meta), 0) AS matriculas_meta,
                COALESCE(SUM(m.ha_meta), 0) AS ha_meta,
                COALESCE(SUM(m.receita_meta), 0) AS receita_meta,
                COALESCE(SUM(pr.matriculas_proj), 0) AS matriculas_proj,
                COALESCE(SUM(pr.ha_proj), 0) AS ha_proj,
                COALESCE(SUM(pr.receita_proj), 0) AS receita_proj
            FROM ofertas_programas o
            LEFT JOIN uo u
              ON u.codigo = o.cod_uo
            LEFT JOIN meta_programas m
              ON m.cod_oferta = o.codigo
             AND m.ano = o.ano
            LEFT JOIN projetado_programas pr
              ON pr.cod_oferta = o.codigo
             AND pr.ano = o.ano
            WHERE o.ano = $1
            GROUP BY u.nome
            ORDER BY u.nome
            """,
            ano
        )

    return [dict(r) for r in rows]

@router.get("/planejamento/regioes")
async def planejamento_regioes(
    request: Request,
    ano: int = 2026,
    subregioes: str | None = None
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote_id = await conn.fetchval(
            """
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento IN ('importado', 'processado')
            ORDER BY id DESC
            LIMIT 1
            """,
            ano
        )

        if not lote_id:
            return []

        params = [lote_id]
        filtro_regiao = ""

        if subregioes:
            ids = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
            if ids:
                filtro_regiao = f"""
                AND UPPER(TRIM(ps.regiao)) IN (
                    SELECT DISTINCT UPPER(TRIM(r.nome))
                    FROM subregioes s
                    JOIN regioes r
                      ON r.codigo = s.codigo_regiao
                    WHERE s.codigo = ANY(${len(params)+1}::int[])
                )
                """
                params.append(ids)

        sql = f"""
        WITH base AS (
            SELECT
                UPPER(TRIM(ps.regiao)) AS regiao,
                UPPER(TRIM(COALESCE(ps.financiamento_raw, ''))) AS financiamento,
                UPPER(TRIM(COALESCE(ps.conta, ''))) AS conta,
                COALESCE(ps.jan, 0) AS jan,
                COALESCE(ps.fev, 0) AS fev,
                COALESCE(ps.mar, 0) AS mar,
                COALESCE(ps.abr, 0) AS abr,
                COALESCE(ps.mai, 0) AS mai,
                COALESCE(ps.jun, 0) AS jun,
                COALESCE(ps.jul, 0) AS jul,
                COALESCE(ps.ago, 0) AS ago,
                COALESCE(ps.set_, 0) AS set_,
                COALESCE(ps.out_, 0) AS out_,
                COALESCE(ps.nov, 0) AS nov,
                COALESCE(ps.dez, 0) AS dez
            FROM planejamento_staging ps
            WHERE ps.lote_id = $1
              AND ps.flag_valida = TRUE
              AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
              {filtro_regiao}
        )
        SELECT
            regiao,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS matriculas_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS hora_aluno_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS receita_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('DESPESAS CORRENTES', 'DESPESA', 'DESPESAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS despesa_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_hora_aluno,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_receita,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS g_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS g_hora_aluno,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS g_receita,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS p_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS p_hora_aluno,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS p_receita
        FROM base
        GROUP BY regiao
        ORDER BY regiao
        """

        rows = await conn.fetch(sql, *params)

    resultado = []
    for row in rows:
        d = dict(row)
        total_mat = float(d["matriculas_total"] or 0)
        d["gr_matriculas_pct"] = round((float(d["gr_matriculas"] or 0) / total_mat) * 100, 2) if total_mat else 0
        d["g_matriculas_pct"] = round((float(d["g_matriculas"] or 0) / total_mat) * 100, 2) if total_mat else 0
        d["p_matriculas_pct"] = round((float(d["p_matriculas"] or 0) / total_mat) * 100, 2) if total_mat else 0
        resultado.append(d)

    return resultado

@router.get("/planejamento/subregioes")
async def planejamento_subregioes(
    request: Request,
    ano: int = 2026,
    subregioes: str | None = None
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote_id = await conn.fetchval(
            """
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento IN ('importado', 'processado')
            ORDER BY id DESC
            LIMIT 1
            """,
            ano
        )

        if not lote_id:
            return []

        params = [lote_id]
        filtro_sub = ""

        if subregioes:
            ids = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
            if ids:
                filtro_sub = f" AND s.codigo = ANY(${len(params)+1}::int[])"
                params.append(ids)

        sql = f"""
        WITH base AS (
            SELECT
                UPPER(TRIM(ps.subregiao)) AS subregiao,
                UPPER(TRIM(COALESCE(ps.financiamento_raw, ''))) AS financiamento,
                UPPER(TRIM(COALESCE(ps.conta, ''))) AS conta,
                COALESCE(ps.jan, 0) AS jan,
                COALESCE(ps.fev, 0) AS fev,
                COALESCE(ps.mar, 0) AS mar,
                COALESCE(ps.abr, 0) AS abr,
                COALESCE(ps.mai, 0) AS mai,
                COALESCE(ps.jun, 0) AS jun,
                COALESCE(ps.jul, 0) AS jul,
                COALESCE(ps.ago, 0) AS ago,
                COALESCE(ps.set_, 0) AS set_,
                COALESCE(ps.out_, 0) AS out_,
                COALESCE(ps.nov, 0) AS nov,
                COALESCE(ps.dez, 0) AS dez
            FROM planejamento_staging ps
            JOIN subregioes s
              ON UPPER(TRIM(s.nome)) = UPPER(TRIM(ps.subregiao))
            WHERE ps.lote_id = $1
              AND ps.flag_valida = TRUE
              AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
              {filtro_sub}
        )
        SELECT
            subregiao,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS matriculas_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS hora_aluno_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS receita_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('DESPESAS CORRENTES', 'DESPESA', 'DESPESAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS despesa_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_hora_aluno,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_receita,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS g_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS g_hora_aluno,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS g_receita,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS p_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS p_hora_aluno,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS p_receita
        FROM base
        GROUP BY subregiao
        ORDER BY subregiao
        """

        rows = await conn.fetch(sql, *params)

    resultado = []
    for row in rows:
        d = dict(row)
        total_mat = float(d["matriculas_total"] or 0)
        d["gr_matriculas_pct"] = round((float(d["gr_matriculas"] or 0) / total_mat) * 100, 2) if total_mat else 0
        d["g_matriculas_pct"] = round((float(d["g_matriculas"] or 0) / total_mat) * 100, 2) if total_mat else 0
        d["p_matriculas_pct"] = round((float(d["p_matriculas"] or 0) / total_mat) * 100, 2) if total_mat else 0
        resultado.append(d)

    return resultado

@router.get("/planejamento/filtros/subregioes")
async def planejamento_filtro_subregioes(request: Request, ano: int = 2026):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote_id = await conn.fetchval(
            """
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento IN ('importado', 'processado')
            ORDER BY id DESC
            LIMIT 1
            """,
            ano
        )

        if not lote_id:
            return []

        rows = await conn.fetch(
            """
            SELECT DISTINCT
                s.codigo,
                s.nome
            FROM planejamento_staging ps
            JOIN subregioes s
              ON UPPER(TRIM(s.nome)) = UPPER(TRIM(ps.subregiao))
            WHERE ps.lote_id = $1
              AND ps.flag_valida = TRUE
              AND COALESCE(TRIM(ps.subregiao), '') <> ''
            ORDER BY s.nome
            """,
            lote_id
        )

    return [dict(r) for r in rows]

@router.get("/subregioes")
async def listar_subregioes_programas(request: Request, ano: int = 2026):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                s.codigo,
                s.nome
            FROM ofertas_programas o
            JOIN uo u
              ON u.codigo = o.cod_uo
            JOIN subregioes s
              ON s.codigo = u.cod_subregiao
            WHERE o.ano = $1
            ORDER BY s.nome
            """,
            ano
        )

    return [dict(r) for r in rows]

@router.get("/programas/list")
async def listar_programas(
    request: Request,
    ano: int = 2026,
    subregioes: str | None = None
):
    pool = request.app.state.pool

    params = [ano]
    filtro_sub = ""

    if subregioes:
        ids = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
        if ids:
            filtro_sub = f" AND COALESCE(u.cod_subregiao, s_txt.codigo) = ANY(${len(params)+1}::int[])"
            params.append(ids)

    sql = f"""
    SELECT
        CASE
            WHEN p.codigo = 29 THEN 11
            WHEN p.codigo = 30 THEN 7
            ELSE p.codigo
        END AS codigo,

        CASE
            WHEN p.codigo IN (11, 29) THEN 'CARREIRAS EMPREGABILIDADE'
            WHEN p.codigo IN (7, 30) THEN 'QUALIFIC.AI'
            ELSE p.nome_programa
        END AS nome

    FROM ofertas_programas o
    JOIN programas p
      ON p.codigo = o.cod_programa
    LEFT JOIN uo u
      ON u.codigo = o.cod_uo
    LEFT JOIN subregioes s
      ON s.codigo = u.cod_subregiao

    LEFT JOIN planejamento_staging ps
      ON ps.cr_raw = o.cr
     AND ps.lote_id = (
        SELECT id
        FROM planejamento_import_lotes
        WHERE ano_referencia = $1
          AND status_processamento = 'processado'
        ORDER BY id DESC
        LIMIT 1
     )
    LEFT JOIN subregioes s_txt
      ON UPPER(TRIM(s_txt.nome)) = UPPER(TRIM(ps.subregiao))

    WHERE o.ano = $1
    {filtro_sub}

    GROUP BY
        CASE
            WHEN p.codigo = 29 THEN 11
            WHEN p.codigo = 30 THEN 7
            ELSE p.codigo
        END,
        CASE
            WHEN p.codigo IN (11, 29) THEN 'CARREIRAS EMPREGABILIDADE'
            WHEN p.codigo IN (7, 30) THEN 'QUALIFIC.AI'
            ELSE p.nome_programa
        END
    ORDER BY nome
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [dict(r) for r in rows]

@router.get("/programas/summary")
async def programas_summary(
    request: Request,
    ano: int = 2026,
    subregioes: str | None = None,
    programas: str | None = None,
    meses: str | None = None,
):
    pool = request.app.state.pool

    params = [ano]
    filtros_oferta = ["o.ano = $1"]

    ids_meses = []
    if meses:
        ids_meses = [int(x) for x in meses.split(",") if x.strip().isdigit()]

    if subregioes:
        ids_sub = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
        if ids_sub:
            params.append(ids_sub)
            filtros_oferta.append(f"u.cod_subregiao = ANY(${len(params)}::int[])")

    if programas:
        ids_prog = [int(x) for x in programas.split(",") if x.strip().isdigit()]
        if ids_prog:
            params.append(ids_prog)
            filtros_oferta.append(f"o.cod_programa = ANY(${len(params)}::int[])")

    filtro_mes_meta = ""
    filtro_mes_real = ""

    if ids_meses:
        params.append(ids_meses)
        idx_mes = len(params)
        filtro_mes_meta = f"AND m.mes = ANY(${idx_mes}::int[])"
        filtro_mes_real = f"AND rp.mes = ANY(${idx_mes}::int[])"

    where_oferta = " AND ".join(filtros_oferta)

    sql = f"""
    WITH ofertas_base AS (
        SELECT DISTINCT
            o.codigo,
            o.cod_programa,
            o.cod_financiamento
        FROM ofertas_programas o
        LEFT JOIN uo u
            ON u.codigo = o.cod_uo
        WHERE {where_oferta}
    ),

    meta AS (
        SELECT
            COALESCE(SUM(m.matriculas_meta), 0) AS matriculas_meta,
            COALESCE(SUM(m.ha_meta), 0) AS ha_meta,
            COALESCE(SUM(m.receita_meta), 0) AS receita_meta
        FROM meta_programas m
        JOIN ofertas_base ob
            ON ob.codigo = m.cod_oferta
        WHERE m.ano = $1
        {filtro_mes_meta}
    ),

    realizado AS (
        SELECT
            COALESCE(SUM(rp.matriculas_real),0) AS matriculas_real,
            COALESCE(SUM(rp.ha_real),0) AS ha_real,
            COALESCE(SUM(rp.receita_real),0) AS receita_real,

            -- GR
            COALESCE(SUM(CASE
                WHEN ob.cod_financiamento = 1
                THEN rp.matriculas_real
                ELSE 0
            END),0) AS matriculas_gr,

            -- GNR
            COALESCE(SUM(CASE
                WHEN ob.cod_financiamento = 2
                THEN rp.matriculas_real
                ELSE 0
            END),0) AS matriculas_g,

            -- PG
            COALESCE(SUM(CASE
                WHEN ob.cod_financiamento IN (3,6,7,8,9)
                THEN rp.matriculas_real
                ELSE 0
            END),0) AS matriculas_p,

            -- HA GR
            COALESCE(SUM(CASE
                WHEN ob.cod_financiamento = 1
                THEN rp.ha_real
                ELSE 0
            END),0) AS ha_gr,

            -- HA GNR
            COALESCE(SUM(CASE
                WHEN ob.cod_financiamento = 2
                THEN rp.ha_real
                ELSE 0
            END),0) AS ha_g,

            -- HA PG
            COALESCE(SUM(CASE
                WHEN ob.cod_financiamento IN (3,6,7,8,9)
                THEN rp.ha_real
                ELSE 0
            END),0) AS ha_p

        FROM realizado_programas rp
        JOIN ofertas_base ob
            ON ob.codigo = rp.cod_oferta
        WHERE rp.ano = $1
        {filtro_mes_real}
    )

    SELECT
        (SELECT COUNT(DISTINCT cod_programa) FROM ofertas_base) AS programas_distintos,

        meta.matriculas_meta,
        meta.ha_meta,
        meta.receita_meta,

        realizado.matriculas_real,
        realizado.ha_real,
        realizado.receita_real,
        realizado.matriculas_gr,
        realizado.matriculas_g,
        realizado.matriculas_p,
        realizado.ha_gr,
        realizado.ha_g,
        realizado.ha_p

    FROM meta, realizado
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *params)

    d = dict(row or {})

    mat_meta = float(d.get("matriculas_meta") or 0)
    ha_meta = float(d.get("ha_meta") or 0)
    rec_meta = float(d.get("receita_meta") or 0)

    mat_real = float(d.get("matriculas_real") or 0)
    ha_real = float(d.get("ha_real") or 0)
    rec_real = float(d.get("receita_real") or 0)

    mat_gr = float(d.get("matriculas_gr") or 0)
    mat_g = float(d.get("matriculas_g") or 0)
    mat_p = float(d.get("matriculas_p") or 0)

    ha_gr = float(d.get("ha_gr") or 0)
    ha_g = float(d.get("ha_g") or 0)
    ha_p = float(d.get("ha_p") or 0)

    def pct_parte(parte, total):
        return (parte / total * 100) if total else 0

    def pct(real, meta):
        return (real / meta * 100) if meta else 0

    return {
        "programas_distintos": int(d.get("programas_distintos") or 0),

        "matriculas": {
            "meta_total": mat_meta,
            "total": mat_real,
            "realizado_total": mat_real,
            "pct_meta": pct(mat_real, mat_meta),
            "gr": mat_gr,
            "g": mat_g,
            "p": mat_p,
            "gr_pct": pct_parte(mat_gr, mat_real),
            "g_pct": pct_parte(mat_g, mat_real),
            "p_pct": pct_parte(mat_p, mat_real),
        },

        "hora_aluno": {
            "meta_total": ha_meta,
            "total": ha_real,
            "realizado_total": ha_real,
            "pct_meta": pct(ha_real, ha_meta),
            "gr": ha_gr,
            "g": ha_g,
            "p": ha_p,
            "gr_pct": pct_parte(ha_gr, ha_real),
            "g_pct": pct_parte(ha_g, ha_real),
            "p_pct": pct_parte(ha_p, ha_real),
        },

        "receita": {
            "meta_total": rec_meta,
            "total": rec_real,
            "realizado_total": rec_real,
            "pct_meta": pct(rec_real, rec_meta),
        }
    }

@router.get("/programas/tabela/subregioes")
async def programas_tabela_subregioes(
    request: Request,
    ano: int = 2026,
    subregioes: str | None = None,
    programas: str | None = None
):
    pool = request.app.state.pool

    params = [ano]
    filtros = []

    if subregioes:
        ids_sub = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
        if ids_sub:
            filtros.append(f"COALESCE(s.codigo, s_txt.codigo) = ANY(${len(params)+1}::int[])")
            params.append(ids_sub)

    if programas:
        ids_prog = [int(x) for x in programas.split(",") if x.strip().isdigit()]
        if ids_prog:
            filtros.append(
                f"""
                EXISTS (
                    SELECT 1
                    FROM programas p2
                    WHERE UPPER(TRIM(p2.nome_programa)) = UPPER(TRIM(ps.programa_raw))
                      AND (
                        CASE
                            WHEN p2.codigo = 29 THEN 11
                            WHEN p2.codigo = 30 THEN 7
                            ELSE p2.codigo
                        END
                      ) = ANY(${len(params)+1}::int[])
                )
                """
            )
            params.append(ids_prog)

    where_extra = ""
    if filtros:
        where_extra = " AND " + " AND ".join(filtros)

    sql = f"""
    WITH base AS (
        SELECT
            COALESCE(s.nome, s_txt.nome) AS subregiao,
            UPPER(TRIM(COALESCE(ps.financiamento_raw, ''))) AS financiamento,
            UPPER(TRIM(COALESCE(ps.conta, ''))) AS conta,
            COALESCE(ps.jan, 0) AS jan,
            COALESCE(ps.fev, 0) AS fev,
            COALESCE(ps.mar, 0) AS mar,
            COALESCE(ps.abr, 0) AS abr,
            COALESCE(ps.mai, 0) AS mai,
            COALESCE(ps.jun, 0) AS jun,
            COALESCE(ps.jul, 0) AS jul,
            COALESCE(ps.ago, 0) AS ago,
            COALESCE(ps.set_, 0) AS set_,
            COALESCE(ps.out_, 0) AS out_,
            COALESCE(ps.nov, 0) AS nov,
            COALESCE(ps.dez, 0) AS dez,
            COALESCE(ps.total, 0) AS total
        FROM planejamento_staging ps
        LEFT JOIN uo u
          ON u.codigo_sge::text = ps.cod_uo_raw
        LEFT JOIN subregioes s
          ON s.codigo = u.cod_subregiao
        LEFT JOIN subregioes s_txt
          ON UPPER(TRIM(s_txt.nome)) = UPPER(TRIM(ps.subregiao))
        WHERE ps.lote_id = (
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
        )
          AND ps.flag_valida = TRUE
          AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
          {where_extra}
    )
    SELECT
        subregiao,

        COALESCE(SUM(CASE
            WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
            THEN total ELSE 0
        END), 0) AS matriculas_total,

        COALESCE(SUM(CASE
            WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
            THEN total ELSE 0
        END), 0) AS hora_aluno_total,

        COALESCE(SUM(CASE
            WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
            THEN total ELSE 0
        END), 0) AS receita_total,

        0::numeric AS despesa_total,

        COALESCE(SUM(CASE
            WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
             AND financiamento = 'GRATUIDADE REGIMENTAL'
            THEN total ELSE 0
        END), 0) AS gr_matriculas,

        COALESCE(SUM(CASE
            WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
             AND financiamento = 'GRATUIDADE REGIMENTAL'
            THEN total ELSE 0
        END), 0) AS gr_hora_aluno,

        COALESCE(SUM(CASE
            WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
             AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
            THEN total ELSE 0
        END), 0) AS g_matriculas,

        COALESCE(SUM(CASE
            WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
             AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
            THEN total ELSE 0
        END), 0) AS g_hora_aluno,

        COALESCE(SUM(CASE
            WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
             AND financiamento NOT IN ('GRATUIDADE REGIMENTAL', 'GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
            THEN total ELSE 0
        END), 0) AS p_matriculas,

        COALESCE(SUM(CASE
            WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
             AND financiamento NOT IN ('GRATUIDADE REGIMENTAL', 'GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
            THEN total ELSE 0
        END), 0) AS p_hora_aluno

    FROM base
    GROUP BY subregiao
    ORDER BY subregiao
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    resultado = []
    for row in rows:
        d = dict(row)

        total_mat = float(d["matriculas_total"] or 0)

        d["gr_matriculas_pct"] = (float(d["gr_matriculas"] or 0) / total_mat * 100) if total_mat else 0
        d["g_matriculas_pct"] = (float(d["g_matriculas"] or 0) / total_mat * 100) if total_mat else 0
        d["p_matriculas_pct"] = (float(d["p_matriculas"] or 0) / total_mat * 100) if total_mat else 0

        resultado.append(d)

    return resultado

@router.get("/programas/tabela/programas")
async def programas_tabela(
    request: Request,
    ano: int = 2026,
    subregioes: str | None = None,
    programas: str | None = None
):
    pool = request.app.state.pool

    params = [ano]
    filtros = []

    if subregioes:
        ids_sub = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
        if ids_sub:
            filtros.append(f"COALESCE(s.codigo, s_txt.codigo) = ANY(${len(params)+1}::int[])")
            params.append(ids_sub)

    if programas:
        ids_prog = [int(x) for x in programas.split(",") if x.strip().isdigit()]
        if ids_prog:
            filtros.append(
                f"""
                EXISTS (
                    SELECT 1
                    FROM programas p2
                    WHERE UPPER(TRIM(p2.nome_programa)) = UPPER(TRIM(ps.programa_raw))
                      AND (
                        CASE
                            WHEN p2.codigo = 29 THEN 11
                            WHEN p2.codigo = 30 THEN 7
                            ELSE p2.codigo
                        END
                      ) = ANY(${len(params)+1}::int[])
                )
                """
            )
            params.append(ids_prog)

    where_extra = ""
    if filtros:
        where_extra = " AND " + " AND ".join(filtros)

    sql = f"""
    WITH base AS (
        SELECT
            CASE
                WHEN UPPER(TRIM(ps.programa_raw)) IN (
                    SELECT UPPER(TRIM(nome_programa)) FROM programas WHERE codigo IN (11, 29)
                ) THEN 'CARREIRAS EMPREGABILIDADE'
                WHEN UPPER(TRIM(ps.programa_raw)) IN (
                    SELECT UPPER(TRIM(nome_programa)) FROM programas WHERE codigo IN (7, 30)
                ) THEN 'QUALIFIC.AI'
                ELSE UPPER(TRIM(ps.programa_raw))
            END AS programa,

            UPPER(TRIM(COALESCE(ps.financiamento_raw, ''))) AS financiamento,
            UPPER(TRIM(COALESCE(ps.conta, ''))) AS conta,
            COALESCE(ps.total, 0) AS total

        FROM planejamento_staging ps
        LEFT JOIN uo u
          ON u.codigo_sge::text = ps.cod_uo_raw
        LEFT JOIN subregioes s
          ON s.codigo = u.cod_subregiao
        LEFT JOIN subregioes s_txt
          ON UPPER(TRIM(s_txt.nome)) = UPPER(TRIM(ps.subregiao))

        WHERE ps.lote_id = (
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
        )
          AND ps.flag_valida = TRUE
          AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
          {where_extra}
    )
    SELECT
        programa,

        COALESCE(SUM(CASE
            WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
            THEN total ELSE 0
        END), 0) AS matriculas_total,

        COALESCE(SUM(CASE
            WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
            THEN total ELSE 0
        END), 0) AS hora_aluno_total,

        COALESCE(SUM(CASE
            WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
            THEN total ELSE 0
        END), 0) AS receita_total,

        0::numeric AS despesa_total,

        COALESCE(SUM(CASE
            WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
             AND financiamento = 'GRATUIDADE REGIMENTAL'
            THEN total ELSE 0
        END), 0) AS gr_matriculas,

        COALESCE(SUM(CASE
            WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
             AND financiamento = 'GRATUIDADE REGIMENTAL'
            THEN total ELSE 0
        END), 0) AS gr_hora_aluno,

        COALESCE(SUM(CASE
            WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
             AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL','GRATUIDADE NAO REGIMENTAL','GRATUITO')
            THEN total ELSE 0
        END), 0) AS g_matriculas,

        COALESCE(SUM(CASE
            WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
             AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL','GRATUIDADE NAO REGIMENTAL','GRATUITO')
            THEN total ELSE 0
        END), 0) AS g_hora_aluno,

        COALESCE(SUM(CASE
            WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
             AND financiamento NOT IN ('GRATUIDADE REGIMENTAL','GRATUIDADE NÃO REGIMENTAL','GRATUIDADE NAO REGIMENTAL','GRATUITO')
            THEN total ELSE 0
        END), 0) AS p_matriculas,

        COALESCE(SUM(CASE
            WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
             AND financiamento NOT IN ('GRATUIDADE REGIMENTAL','GRATUIDADE NÃO REGIMENTAL','GRATUIDADE NAO REGIMENTAL','GRATUITO')
            THEN total ELSE 0
        END), 0) AS p_hora_aluno

    FROM base
    GROUP BY programa
    ORDER BY programa
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    resultado = []
    for row in rows:
        d = dict(row)

        total_mat = float(d["matriculas_total"] or 0)
        d["gr_matriculas_pct"] = (float(d["gr_matriculas"] or 0) / total_mat * 100) if total_mat else 0
        d["g_matriculas_pct"] = (float(d["g_matriculas"] or 0) / total_mat * 100) if total_mat else 0
        d["p_matriculas_pct"] = (float(d["p_matriculas"] or 0) / total_mat * 100) if total_mat else 0

        resultado.append(d)

    return resultado

@router.get("/relatorio-programa/resumo")
async def relatorio_programa_resumo(
    request: Request,
    programa: int,
    ano: int,
    mes: int | None = None,
    meses: str | None = None,
):
    pool = request.app.state.pool

    ids_meses = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]

    if not ids_meses and mes:
        ids_meses = [mes]

    if not ids_meses:
        raise HTTPException(status_code=400, detail="Informe ao menos um mês.")

    mes_final = max(ids_meses)

    async with pool.acquire() as conn:
        # descrição / nome do programa
        prog = await conn.fetchrow(
            """
            SELECT
                codigo,
                nome_programa,
                descricao
            FROM programas
            WHERE codigo = $1
            """,
            programa
        )

        if not prog:
            raise HTTPException(status_code=404, detail="Programa não encontrado.")

        # mapeamento legado já usado em outras consultas
        programa_planejamento = 11 if programa == 29 else 7 if programa == 30 else programa

        # indicadores acumulados até o mês
        resumo = await conn.fetchrow(
            """
            WITH ofertas_filtradas AS (
                SELECT o.codigo
                FROM ofertas_programas o
                WHERE o.ano = $1
                  AND o.cod_programa = $2
            ),
            meta_acum AS (
                SELECT
                    COALESCE(SUM(mp.matriculas_meta), 0) AS mat_meta,
                    COALESCE(SUM(mp.ha_meta), 0) AS ha_meta,
                    COALESCE(SUM(mp.receita_meta), 0) AS rec_meta
                FROM meta_programas mp
                JOIN ofertas_filtradas ofi
                  ON ofi.codigo = mp.cod_oferta
                WHERE mp.ano = $1
                  AND mp.mes <= $4
            ),
            meta_anual AS (
                SELECT
                    COALESCE(SUM(mp.matriculas_meta), 0) AS mat_meta_anual,
                    COALESCE(SUM(mp.ha_meta), 0) AS ha_meta_anual,
                    COALESCE(SUM(mp.receita_meta), 0) AS rec_meta_anual
                FROM meta_programas mp
                JOIN ofertas_filtradas ofi
                ON ofi.codigo = mp.cod_oferta
                WHERE mp.ano = $1
            ),
            proj_acum AS (
                SELECT
                    COALESCE(SUM(pp.matriculas_proj), 0) AS mat_proj,
                    COALESCE(SUM(pp.ha_proj), 0) AS ha_proj,
                    COALESCE(SUM(pp.receita_proj), 0) AS rec_proj
                FROM projetado_programas pp
                JOIN ofertas_filtradas ofi
                  ON ofi.codigo = pp.cod_oferta
                WHERE pp.ano = $1
                  AND pp.mes <= $4
            ),
            proj_anual AS (
                SELECT
                    COALESCE(SUM(pp.matriculas_proj), 0) AS mat_proj_anual,
                    COALESCE(SUM(pp.ha_proj), 0) AS ha_proj_anual,
                    COALESCE(SUM(pp.receita_proj), 0) AS rec_proj_anual
                FROM projetado_programas pp
                JOIN ofertas_filtradas ofi
                ON ofi.codigo = pp.cod_oferta
                WHERE pp.ano = $1
            ),
            planejamento_anual AS (
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('MATRÍCULAS', 'MATRICULAS')
                            THEN COALESCE(ps.total, 0)
                            ELSE 0
                        END
                    ), 0) AS mat_meta_planejamento,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                            THEN COALESCE(ps.total, 0)
                            ELSE 0
                        END
                    ), 0) AS ha_meta_planejamento,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                            THEN COALESCE(ps.total, 0)
                            ELSE 0
                        END
                    ), 0) AS rec_meta_planejamento
                FROM planejamento_staging ps
                WHERE ps.lote_id = (
                    SELECT id
                    FROM planejamento_import_lotes
                    WHERE ano_referencia = $1
                    AND status_processamento = 'processado'
                    ORDER BY id DESC
                    LIMIT 1
                )
                AND ps.flag_valida = TRUE
                AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
                AND UPPER(TRIM(COALESCE(ps.programa_raw, ''))) = UPPER(TRIM($5))
            ),
            planejamento_mes_meta AS (
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('MATRÍCULAS', 'MATRICULAS')
                            THEN (
                                CASE WHEN 1 = ANY($3::int[]) THEN COALESCE(ps.jan,0) ELSE 0 END +
                                CASE WHEN 2 = ANY($3::int[]) THEN COALESCE(ps.fev,0) ELSE 0 END +
                                CASE WHEN 3 = ANY($3::int[]) THEN COALESCE(ps.mar,0) ELSE 0 END +
                                CASE WHEN 4 = ANY($3::int[]) THEN COALESCE(ps.abr,0) ELSE 0 END +
                                CASE WHEN 5 = ANY($3::int[]) THEN COALESCE(ps.mai,0) ELSE 0 END +
                                CASE WHEN 6 = ANY($3::int[]) THEN COALESCE(ps.jun,0) ELSE 0 END +
                                CASE WHEN 7 = ANY($3::int[]) THEN COALESCE(ps.jul,0) ELSE 0 END +
                                CASE WHEN 8 = ANY($3::int[]) THEN COALESCE(ps.ago,0) ELSE 0 END +
                                CASE WHEN 9 = ANY($3::int[]) THEN COALESCE(ps.set_,0) ELSE 0 END +
                                CASE WHEN 10 = ANY($3::int[]) THEN COALESCE(ps.out_,0) ELSE 0 END +
                                CASE WHEN 11 = ANY($3::int[]) THEN COALESCE(ps.nov,0) ELSE 0 END +
                                CASE WHEN 12 = ANY($3::int[]) THEN COALESCE(ps.dez,0) ELSE 0 END
                            )
                            ELSE 0
                        END
                    ), 0) AS mat_meta_mes_plan,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                            THEN (
                                CASE WHEN 1 = ANY($3::int[]) THEN COALESCE(ps.jan,0) ELSE 0 END +
                                CASE WHEN 2 = ANY($3::int[]) THEN COALESCE(ps.fev,0) ELSE 0 END +
                                CASE WHEN 3 = ANY($3::int[]) THEN COALESCE(ps.mar,0) ELSE 0 END +
                                CASE WHEN 4 = ANY($3::int[]) THEN COALESCE(ps.abr,0) ELSE 0 END +
                                CASE WHEN 5 = ANY($3::int[]) THEN COALESCE(ps.mai,0) ELSE 0 END +
                                CASE WHEN 6 = ANY($3::int[]) THEN COALESCE(ps.jun,0) ELSE 0 END +
                                CASE WHEN 7 = ANY($3::int[]) THEN COALESCE(ps.jul,0) ELSE 0 END +
                                CASE WHEN 8 = ANY($3::int[]) THEN COALESCE(ps.ago,0) ELSE 0 END +
                                CASE WHEN 9 = ANY($3::int[]) THEN COALESCE(ps.set_,0) ELSE 0 END +
                                CASE WHEN 10 = ANY($3::int[]) THEN COALESCE(ps.out_,0) ELSE 0 END +
                                CASE WHEN 11 = ANY($3::int[]) THEN COALESCE(ps.nov,0) ELSE 0 END +
                                CASE WHEN 12 = ANY($3::int[]) THEN COALESCE(ps.dez,0) ELSE 0 END
                            )
                            ELSE 0
                        END
                    ), 0) AS ha_meta_mes_plan,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                            THEN (
                                CASE WHEN 1 = ANY($3::int[]) THEN COALESCE(ps.jan,0) ELSE 0 END +
                                CASE WHEN 2 = ANY($3::int[]) THEN COALESCE(ps.fev,0) ELSE 0 END +
                                CASE WHEN 3 = ANY($3::int[]) THEN COALESCE(ps.mar,0) ELSE 0 END +
                                CASE WHEN 4 = ANY($3::int[]) THEN COALESCE(ps.abr,0) ELSE 0 END +
                                CASE WHEN 5 = ANY($3::int[]) THEN COALESCE(ps.mai,0) ELSE 0 END +
                                CASE WHEN 6 = ANY($3::int[]) THEN COALESCE(ps.jun,0) ELSE 0 END +
                                CASE WHEN 7 = ANY($3::int[]) THEN COALESCE(ps.jul,0) ELSE 0 END +
                                CASE WHEN 8 = ANY($3::int[]) THEN COALESCE(ps.ago,0) ELSE 0 END +
                                CASE WHEN 9 = ANY($3::int[]) THEN COALESCE(ps.set_,0) ELSE 0 END +
                                CASE WHEN 10 = ANY($3::int[]) THEN COALESCE(ps.out_,0) ELSE 0 END +
                                CASE WHEN 11 = ANY($3::int[]) THEN COALESCE(ps.nov,0) ELSE 0 END +
                                CASE WHEN 12 = ANY($3::int[]) THEN COALESCE(ps.dez,0) ELSE 0 END
                            )
                            ELSE 0
                        END
                    ), 0) AS rec_meta_mes_plan
                FROM planejamento_staging ps
                WHERE ps.lote_id = (
                    SELECT id
                    FROM planejamento_import_lotes
                    WHERE ano_referencia = $1
                    AND status_processamento = 'processado'
                    ORDER BY id DESC
                    LIMIT 1
                )
                AND ps.flag_valida = TRUE
                AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
                AND UPPER(TRIM(COALESCE(ps.programa_raw, ''))) = UPPER(TRIM($5))
            ),
            planejamento_mes_proj AS (
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('MATRÍCULAS', 'MATRICULAS')
                            THEN COALESCE(
                                (
                                    CASE WHEN 1 = ANY($3::int[]) THEN COALESCE(ps.jan,0) ELSE 0 END +
                                    CASE WHEN 2 = ANY($3::int[]) THEN COALESCE(ps.fev,0) ELSE 0 END +
                                    CASE WHEN 3 = ANY($3::int[]) THEN COALESCE(ps.mar,0) ELSE 0 END +
                                    CASE WHEN 4 = ANY($3::int[]) THEN COALESCE(ps.abr,0) ELSE 0 END +
                                    CASE WHEN 5 = ANY($3::int[]) THEN COALESCE(ps.mai,0) ELSE 0 END +
                                    CASE WHEN 6 = ANY($3::int[]) THEN COALESCE(ps.jun,0) ELSE 0 END +
                                    CASE WHEN 7 = ANY($3::int[]) THEN COALESCE(ps.jul,0) ELSE 0 END +
                                    CASE WHEN 8 = ANY($3::int[]) THEN COALESCE(ps.ago,0) ELSE 0 END +
                                    CASE WHEN 9 = ANY($3::int[]) THEN COALESCE(ps.set_,0) ELSE 0 END +
                                    CASE WHEN 10 = ANY($3::int[]) THEN COALESCE(ps.out_,0) ELSE 0 END +
                                    CASE WHEN 11 = ANY($3::int[]) THEN COALESCE(ps.nov,0) ELSE 0 END +
                                    CASE WHEN 12 = ANY($3::int[]) THEN COALESCE(ps.dez,0) ELSE 0 END
                                ), 0
                            )
                            ELSE 0
                        END
                    ), 0) AS mat_proj_mes_plan,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                            THEN COALESCE(
                                (
                                    CASE WHEN 1 = ANY($3::int[]) THEN COALESCE(ps.jan,0) ELSE 0 END +
                                    CASE WHEN 2 = ANY($3::int[]) THEN COALESCE(ps.fev,0) ELSE 0 END +
                                    CASE WHEN 3 = ANY($3::int[]) THEN COALESCE(ps.mar,0) ELSE 0 END +
                                    CASE WHEN 4 = ANY($3::int[]) THEN COALESCE(ps.abr,0) ELSE 0 END +
                                    CASE WHEN 5 = ANY($3::int[]) THEN COALESCE(ps.mai,0) ELSE 0 END +
                                    CASE WHEN 6 = ANY($3::int[]) THEN COALESCE(ps.jun,0) ELSE 0 END +
                                    CASE WHEN 7 = ANY($3::int[]) THEN COALESCE(ps.jul,0) ELSE 0 END +
                                    CASE WHEN 8 = ANY($3::int[]) THEN COALESCE(ps.ago,0) ELSE 0 END +
                                    CASE WHEN 9 = ANY($3::int[]) THEN COALESCE(ps.set_,0) ELSE 0 END +
                                    CASE WHEN 10 = ANY($3::int[]) THEN COALESCE(ps.out_,0) ELSE 0 END +
                                    CASE WHEN 11 = ANY($3::int[]) THEN COALESCE(ps.nov,0) ELSE 0 END +
                                    CASE WHEN 12 = ANY($3::int[]) THEN COALESCE(ps.dez,0) ELSE 0 END
                                ), 0
                            )
                            ELSE 0
                        END
                    ), 0) AS ha_proj_mes_plan,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                            THEN COALESCE(
                                (
                                    CASE WHEN 1 = ANY($3::int[]) THEN COALESCE(ps.jan,0) ELSE 0 END +
                                    CASE WHEN 2 = ANY($3::int[]) THEN COALESCE(ps.fev,0) ELSE 0 END +
                                    CASE WHEN 3 = ANY($3::int[]) THEN COALESCE(ps.mar,0) ELSE 0 END +
                                    CASE WHEN 4 = ANY($3::int[]) THEN COALESCE(ps.abr,0) ELSE 0 END +
                                    CASE WHEN 5 = ANY($3::int[]) THEN COALESCE(ps.mai,0) ELSE 0 END +
                                    CASE WHEN 6 = ANY($3::int[]) THEN COALESCE(ps.jun,0) ELSE 0 END +
                                    CASE WHEN 7 = ANY($3::int[]) THEN COALESCE(ps.jul,0) ELSE 0 END +
                                    CASE WHEN 8 = ANY($3::int[]) THEN COALESCE(ps.ago,0) ELSE 0 END +
                                    CASE WHEN 9 = ANY($3::int[]) THEN COALESCE(ps.set_,0) ELSE 0 END +
                                    CASE WHEN 10 = ANY($3::int[]) THEN COALESCE(ps.out_,0) ELSE 0 END +
                                    CASE WHEN 11 = ANY($3::int[]) THEN COALESCE(ps.nov,0) ELSE 0 END +
                                    CASE WHEN 12 = ANY($3::int[]) THEN COALESCE(ps.dez,0) ELSE 0 END
                                ), 0
                            )
                            ELSE 0
                        END
                    ), 0) AS rec_proj_mes_plan
                FROM planejamento_staging ps
                WHERE ps.lote_id = (
                    SELECT id
                    FROM planejamento_import_lotes
                    WHERE ano_referencia = $1
                    AND status_processamento = 'processado'
                    ORDER BY id DESC
                    LIMIT 1
                )
                AND ps.flag_valida = TRUE
                AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'PROJETADO'
                AND UPPER(TRIM(COALESCE(ps.programa_raw, ''))) = UPPER(TRIM($5))
            ),
            real_mat AS (
                SELECT
                    COALESCE(SUM(rp.matriculas_real),0) AS mat_real
                FROM realizado_programas rp
                JOIN ofertas_filtradas ofi
                ON ofi.codigo = rp.cod_oferta
                WHERE rp.ano = $1
                AND rp.mes = ANY($3::int[])
            ),
            real_fin AS (
                SELECT
                    COALESCE(SUM(rp.ha_real), 0) AS ha_real,
                    COALESCE(SUM(rp.receita_real), 0) AS rec_real
                FROM realizado_programas rp
                JOIN ofertas_filtradas ofi
                  ON ofi.codigo = rp.cod_oferta
                WHERE rp.ano = $1
                  AND rp.mes = ANY($3::int[])
            ),
            meta_mes AS (
                SELECT
                    COALESCE(SUM(mp.matriculas_meta), 0) AS mat_meta_mes,
                    COALESCE(SUM(mp.ha_meta), 0) AS ha_meta_mes,
                    COALESCE(SUM(mp.receita_meta), 0) AS rec_meta_mes
                FROM meta_programas mp
                JOIN ofertas_filtradas ofi
                ON ofi.codigo = mp.cod_oferta
                WHERE mp.ano = $1
                AND mp.mes = ANY($3::int[])
            ),
            proj_mes AS (
                SELECT
                    COALESCE(SUM(pp.matriculas_proj), 0) AS mat_proj_mes,
                    COALESCE(SUM(pp.ha_proj), 0) AS ha_proj_mes,
                    COALESCE(SUM(pp.receita_proj), 0) AS rec_proj_mes
                FROM projetado_programas pp
                JOIN ofertas_filtradas ofi
                ON ofi.codigo = pp.cod_oferta
                WHERE pp.ano = $1
                AND pp.mes = ANY($3::int[])
            ),
            real_mes AS (
                SELECT
                    COALESCE(rp.mat_real_mes,0) AS mat_real_mes,
                    COALESCE(rf.ha_real_mes,0) AS ha_real_mes,
                    COALESCE(rf.rec_real_mes,0) AS rec_real_mes

                FROM (
                    SELECT
                        COALESCE(SUM(r.matriculas_real),0) AS mat_real_mes
                    FROM realizado_programas r
                    JOIN ofertas_filtradas ofi
                    ON ofi.codigo=r.cod_oferta
                    WHERE r.ano=$1
                    AND r.mes=ANY($3::int[])
                ) rp

                CROSS JOIN (

                    SELECT
                        COALESCE(SUM(r.ha_real),0) ha_real_mes,
                        COALESCE(SUM(r.receita_real),0) rec_real_mes

                    FROM realizado_programas r
                    JOIN ofertas_filtradas ofi
                    ON ofi.codigo=r.cod_oferta

                    WHERE r.ano=$1
                    AND r.mes=ANY($3::int[])

                ) rf
            ),
            regioes AS (

            SELECT COUNT(DISTINCT r.codigo)
            AS qtd_regioes

            FROM realizado_programas rp

            JOIN ofertas_programas o
            ON o.codigo=rp.cod_oferta

            JOIN uo u
            ON u.codigo=o.cod_uo

            JOIN subregioes s
            ON s.codigo=u.cod_subregiao

            JOIN regioes r
            ON r.codigo=s.codigo_regiao

            WHERE o.cod_programa=$2
            AND rp.ano=$1
            AND rp.mes=ANY($3::int[])

            AND COALESCE(rp.matriculas_real,0)>0

            ),
            turmas AS (

            SELECT

            COUNT(DISTINCT CASE
            WHEN rp.mes=ANY($3::int[])
            THEN o.codigo
            END) qtd_turmas_ate_mes,

            COUNT(DISTINCT o.codigo)
            AS qtd_turmas_ano

            FROM ofertas_programas o

            LEFT JOIN realizado_programas rp
            ON rp.cod_oferta=o.codigo
            AND rp.ano=$1

            WHERE o.cod_programa=$2

            )
            SELECT
                COALESCE(NULLIF(pmm.mat_meta_mes_plan, 0), mm.mat_meta_mes, 0) AS mat_meta_mes,
                COALESCE(NULLIF(pmp.mat_proj_mes_plan, 0), pm.mat_proj_mes, 0) AS mat_proj_mes,
                rmm.mat_real_mes,
                rmm.ha_real_mes,
                rmm.rec_real_mes,

                ma.mat_meta,
                pa.mat_proj,
                rm.mat_real,

                COALESCE(NULLIF(paan.mat_meta_planejamento, 0), man.mat_meta_anual, 0) AS mat_meta_anual,
                pan.mat_proj_anual,

                COALESCE(NULLIF(pmm.ha_meta_mes_plan, 0), mm.ha_meta_mes, 0) AS ha_meta_mes,
                COALESCE(NULLIF(pmp.ha_proj_mes_plan, 0), pm.ha_proj_mes, 0) AS ha_proj_mes,
                ma.ha_meta,
                pa.ha_proj,
                rf.ha_real,

                COALESCE(NULLIF(paan.ha_meta_planejamento, 0), man.ha_meta_anual, 0) AS ha_meta_anual,
                pan.ha_proj_anual,

                COALESCE(NULLIF(pmm.rec_meta_mes_plan, 0), mm.rec_meta_mes, 0) AS rec_meta_mes,
                COALESCE(NULLIF(pmp.rec_proj_mes_plan, 0), pm.rec_proj_mes, 0) AS rec_proj_mes,
                ma.rec_meta,
                pa.rec_proj,
                rf.rec_real,

                COALESCE(NULLIF(paan.rec_meta_planejamento, 0), man.rec_meta_anual, 0) AS rec_meta_anual,
                pan.rec_proj_anual,

                rg.qtd_regioes,
                tt.qtd_turmas_ate_mes,
                tt.qtd_turmas_ano
            FROM meta_mes mm
            CROSS JOIN proj_mes pm
            CROSS JOIN real_mes rmm
            CROSS JOIN meta_acum ma
            CROSS JOIN meta_anual man
            CROSS JOIN proj_acum pa
            CROSS JOIN proj_anual pan
            CROSS JOIN planejamento_anual paan
            CROSS JOIN planejamento_mes_meta pmm
            CROSS JOIN planejamento_mes_proj pmp
            CROSS JOIN real_mat rm
            CROSS JOIN real_fin rf
            CROSS JOIN regioes rg
            CROSS JOIN turmas tt
            """,
            ano,
            programa_planejamento,
            ids_meses,
            mes_final,
            prog["nome_programa"],
        )

    return {
        "programa": prog["nome_programa"],
        "descricao": prog["descricao"] or "",

        "mat_real_mes": float(resumo["mat_real_mes"] or 0),
        "mat_meta_mes": float(resumo["mat_meta_mes"] or 0),
        "mat_proj_mes": float(resumo["mat_proj_mes"] or 0),
        "mat_real_acum": float(resumo["mat_real"] or 0),
        "mat_meta_acum": float(resumo["mat_meta"] or 0),
        "mat_meta_anual": float(resumo["mat_meta_anual"] or 0),
        "mat_proj_anual": float(resumo["mat_proj_anual"] or 0),

        "ha_real_mes": float(resumo["ha_real_mes"] or 0),
        "ha_meta_mes": float(resumo["ha_meta_mes"] or 0),
        "ha_proj_mes": float(resumo["ha_proj_mes"] or 0),
        "ha_real_acum": float(resumo["ha_real"] or 0),
        "ha_meta_acum": float(resumo["ha_meta"] or 0),
        "ha_meta_anual": float(resumo["ha_meta_anual"] or 0),
        "ha_proj_anual": float(resumo["ha_proj_anual"] or 0),

        "rec_real_mes": float(resumo["rec_real_mes"] or 0),
        "rec_meta_mes": float(resumo["rec_meta_mes"] or 0),
        "rec_proj_mes": float(resumo["rec_proj_mes"] or 0),
        "rec_real_acum": float(resumo["rec_real"] or 0),
        "rec_meta_acum": float(resumo["rec_meta"] or 0),
        "rec_meta_anual": float(resumo["rec_meta_anual"] or 0),
        "rec_proj_anual": float(resumo["rec_proj_anual"] or 0),

        "regioes": int(resumo["qtd_regioes"] or 0),
        "turmas_ate_mes": int(resumo["qtd_turmas_ate_mes"] or 0),
        "turmas_ano": int(resumo["qtd_turmas_ano"] or 0),
    }

@router.get("/relatorio-programa/distribuicao")
async def relatorio_programa_distribuicao(
    request: Request,
    programa: int,
    ano: int,
    mes: int | None = None,
    meses: str | None = None,
):
    pool = request.app.state.pool
    ids_meses = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]

    if not ids_meses and mes:
        ids_meses = [mes]

    if not ids_meses:
        raise HTTPException(status_code=400, detail="Informe ao menos um mês.")

    mes_final = max(ids_meses)
    programa_planejamento = 11 if programa == 29 else 7 if programa == 30 else programa

    async with pool.acquire() as conn:
        prog = await conn.fetchrow(
            """
            SELECT nome_programa
            FROM programas
            WHERE codigo = $1
            """,
            programa
        )

        if not prog:
            raise HTTPException(status_code=404, detail="Programa não encontrado.")

        rows = await conn.fetch(
            """
            WITH metas AS (
                SELECT
                    UPPER(TRIM(ps.regiao)) AS regiao,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('MATRÍCULAS', 'MATRICULAS')
                            THEN (
                                CASE WHEN 1 <= $3 THEN COALESCE(ps.jan,0) ELSE 0 END +
                                CASE WHEN 2 <= $3 THEN COALESCE(ps.fev,0) ELSE 0 END +
                                CASE WHEN 3 <= $3 THEN COALESCE(ps.mar,0) ELSE 0 END +
                                CASE WHEN 4 <= $3 THEN COALESCE(ps.abr,0) ELSE 0 END +
                                CASE WHEN 5 <= $3 THEN COALESCE(ps.mai,0) ELSE 0 END +
                                CASE WHEN 6 <= $3 THEN COALESCE(ps.jun,0) ELSE 0 END +
                                CASE WHEN 7 <= $3 THEN COALESCE(ps.jul,0) ELSE 0 END +
                                CASE WHEN 8 <= $3 THEN COALESCE(ps.ago,0) ELSE 0 END +
                                CASE WHEN 9 <= $3 THEN COALESCE(ps.set_,0) ELSE 0 END +
                                CASE WHEN 10 <= $3 THEN COALESCE(ps.out_,0) ELSE 0 END +
                                CASE WHEN 11 <= $3 THEN COALESCE(ps.nov,0) ELSE 0 END +
                                CASE WHEN 12 <= $3 THEN COALESCE(ps.dez,0) ELSE 0 END
                            )
                            ELSE 0
                        END
                    ), 0) AS matriculas_meta,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                            THEN (
                                CASE WHEN 1 <= $3 THEN COALESCE(ps.jan,0) ELSE 0 END +
                                CASE WHEN 2 <= $3 THEN COALESCE(ps.fev,0) ELSE 0 END +
                                CASE WHEN 3 <= $3 THEN COALESCE(ps.mar,0) ELSE 0 END +
                                CASE WHEN 4 <= $3 THEN COALESCE(ps.abr,0) ELSE 0 END +
                                CASE WHEN 5 <= $3 THEN COALESCE(ps.mai,0) ELSE 0 END +
                                CASE WHEN 6 <= $3 THEN COALESCE(ps.jun,0) ELSE 0 END +
                                CASE WHEN 7 <= $3 THEN COALESCE(ps.jul,0) ELSE 0 END +
                                CASE WHEN 8 <= $3 THEN COALESCE(ps.ago,0) ELSE 0 END +
                                CASE WHEN 9 <= $3 THEN COALESCE(ps.set_,0) ELSE 0 END +
                                CASE WHEN 10 <= $3 THEN COALESCE(ps.out_,0) ELSE 0 END +
                                CASE WHEN 11 <= $3 THEN COALESCE(ps.nov,0) ELSE 0 END +
                                CASE WHEN 12 <= $3 THEN COALESCE(ps.dez,0) ELSE 0 END
                            )
                            ELSE 0
                        END
                    ), 0) AS ha_meta,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                            THEN (
                                CASE WHEN 1 <= $3 THEN COALESCE(ps.jan,0) ELSE 0 END +
                                CASE WHEN 2 <= $3 THEN COALESCE(ps.fev,0) ELSE 0 END +
                                CASE WHEN 3 <= $3 THEN COALESCE(ps.mar,0) ELSE 0 END +
                                CASE WHEN 4 <= $3 THEN COALESCE(ps.abr,0) ELSE 0 END +
                                CASE WHEN 5 <= $3 THEN COALESCE(ps.mai,0) ELSE 0 END +
                                CASE WHEN 6 <= $3 THEN COALESCE(ps.jun,0) ELSE 0 END +
                                CASE WHEN 7 <= $3 THEN COALESCE(ps.jul,0) ELSE 0 END +
                                CASE WHEN 8 <= $3 THEN COALESCE(ps.ago,0) ELSE 0 END +
                                CASE WHEN 9 <= $3 THEN COALESCE(ps.set_,0) ELSE 0 END +
                                CASE WHEN 10 <= $3 THEN COALESCE(ps.out_,0) ELSE 0 END +
                                CASE WHEN 11 <= $3 THEN COALESCE(ps.nov,0) ELSE 0 END +
                                CASE WHEN 12 <= $3 THEN COALESCE(ps.dez,0) ELSE 0 END
                            )
                            ELSE 0
                        END
                    ), 0) AS receita_meta

                FROM planejamento_staging ps
                WHERE ps.lote_id = (
                    SELECT id
                    FROM planejamento_import_lotes
                    WHERE ano_referencia = $2
                      AND status_processamento = 'processado'
                    ORDER BY id DESC
                    LIMIT 1
                )
                AND ps.flag_valida = TRUE
                AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
                AND UPPER(TRIM(COALESCE(ps.programa_raw, ''))) = UPPER(TRIM($4))
                AND ps.regiao IS NOT NULL
                AND TRIM(ps.regiao) <> ''
                GROUP BY UPPER(TRIM(ps.regiao))
            ),

            real_mat AS (

                SELECT

                    UPPER(TRIM(r.nome)) AS regiao,

                    COALESCE(
                        SUM(rp.matriculas_real),
                        0
                    ) AS matriculas_real

                FROM realizado_programas rp

                JOIN ofertas_programas o
                ON o.codigo = rp.cod_oferta

                JOIN uo u
                ON u.codigo = o.cod_uo

                JOIN subregioes s
                ON s.codigo = u.cod_subregiao

                JOIN regioes r
                ON r.codigo = s.codigo_regiao

                WHERE o.cod_programa = $1
                AND o.ano = $2
                AND rp.ano = $2
                AND rp.mes <= $3

                GROUP BY UPPER(TRIM(r.nome))

            ),

            real_fin AS (
                SELECT
                    UPPER(TRIM(r.nome)) AS regiao,
                    COALESCE(SUM(rp.ha_real), 0) AS ha_real,
                    COALESCE(SUM(rp.receita_real), 0) AS receita_real
                FROM realizado_programas rp
                JOIN ofertas_programas o
                  ON o.codigo = rp.cod_oferta
                JOIN uo u
                  ON u.codigo = o.cod_uo
                JOIN subregioes s
                  ON s.codigo = u.cod_subregiao
                JOIN regioes r
                  ON r.codigo = s.codigo_regiao
                WHERE o.cod_programa = $1
                  AND o.ano = $2
                  AND rp.ano = $2
                  AND rp.mes <= $3
                GROUP BY UPPER(TRIM(r.nome))
            )

            SELECT
                COALESCE(m.regiao, rm.regiao, rf.regiao) AS regiao,

                COALESCE(rm.matriculas_real, 0) AS matriculas_real,
                COALESCE(m.matriculas_meta, 0) AS matriculas_meta,

                COALESCE(rf.ha_real, 0) AS ha_real,
                COALESCE(m.ha_meta, 0) AS ha_meta,

                COALESCE(rf.receita_real, 0) AS receita_real,
                COALESCE(m.receita_meta, 0) AS receita_meta

            FROM metas m
            FULL OUTER JOIN real_mat rm
              ON rm.regiao = m.regiao
            FULL OUTER JOIN real_fin rf
              ON rf.regiao = COALESCE(m.regiao, rm.regiao)
            WHERE
              COALESCE(rm.matriculas_real, 0) > 0
              OR COALESCE(m.matriculas_meta, 0) > 0
              OR COALESCE(rf.ha_real, 0) > 0
              OR COALESCE(m.ha_meta, 0) > 0
              OR COALESCE(rf.receita_real, 0) > 0
              OR COALESCE(m.receita_meta, 0) > 0
            ORDER BY COALESCE(rm.matriculas_real, 0) DESC,
                     COALESCE(m.matriculas_meta, 0) DESC,
                     COALESCE(m.regiao, rm.regiao, rf.regiao)
            """,
            programa_planejamento,
            ano,
            mes_final,
            prog["nome_programa"],
        )

    return [
        {
            "regiao": r["regiao"],

            "matriculas_real": float(r["matriculas_real"] or 0),
            "matriculas_meta": float(r["matriculas_meta"] or 0),

            "ha_real": float(r["ha_real"] or 0),
            "ha_meta": float(r["ha_meta"] or 0),

            "receita_real": float(r["receita_real"] or 0),
            "receita_meta": float(r["receita_meta"] or 0),
        }
        for r in rows
    ]

@router.get("/relatorio-programa/distribuicao-subregioes")
async def relatorio_programa_distribuicao_subregioes(
    request: Request,
    programa: int,
    ano: int,
    mes: int | None = None,
    meses: str | None = None,
):
    pool = request.app.state.pool
    programa_planejamento = 11 if programa == 29 else 7 if programa == 30 else programa
    ids_meses = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]

    if not ids_meses and mes:
        ids_meses = [mes]

    if not ids_meses:
        raise HTTPException(status_code=400, detail="Informe ao menos um mês.")

    mes_final = max(ids_meses)

    async with pool.acquire() as conn:
        prog = await conn.fetchrow(
            """
            SELECT nome_programa
            FROM programas
            WHERE codigo = $1
            """,
            programa
        )

        if not prog:
            raise HTTPException(status_code=404, detail="Programa não encontrado.")

        rows = await conn.fetch(
            """
            WITH metas AS (
                SELECT
                    TRIM(ps.subregiao) AS subregiao,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('MATRÍCULAS', 'MATRICULAS')
                            THEN (
                                CASE WHEN 1 <= $3 THEN COALESCE(ps.jan,0) ELSE 0 END +
                                CASE WHEN 2 <= $3 THEN COALESCE(ps.fev,0) ELSE 0 END +
                                CASE WHEN 3 <= $3 THEN COALESCE(ps.mar,0) ELSE 0 END +
                                CASE WHEN 4 <= $3 THEN COALESCE(ps.abr,0) ELSE 0 END +
                                CASE WHEN 5 <= $3 THEN COALESCE(ps.mai,0) ELSE 0 END +
                                CASE WHEN 6 <= $3 THEN COALESCE(ps.jun,0) ELSE 0 END +
                                CASE WHEN 7 <= $3 THEN COALESCE(ps.jul,0) ELSE 0 END +
                                CASE WHEN 8 <= $3 THEN COALESCE(ps.ago,0) ELSE 0 END +
                                CASE WHEN 9 <= $3 THEN COALESCE(ps.set_,0) ELSE 0 END +
                                CASE WHEN 10 <= $3 THEN COALESCE(ps.out_,0) ELSE 0 END +
                                CASE WHEN 11 <= $3 THEN COALESCE(ps.nov,0) ELSE 0 END +
                                CASE WHEN 12 <= $3 THEN COALESCE(ps.dez,0) ELSE 0 END
                            )
                        END
                    ), 0) AS matriculas_meta,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                            THEN (
                                CASE WHEN 1 <= $3 THEN COALESCE(ps.jan,0) ELSE 0 END +
                                CASE WHEN 2 <= $3 THEN COALESCE(ps.fev,0) ELSE 0 END +
                                CASE WHEN 3 <= $3 THEN COALESCE(ps.mar,0) ELSE 0 END +
                                CASE WHEN 4 <= $3 THEN COALESCE(ps.abr,0) ELSE 0 END +
                                CASE WHEN 5 <= $3 THEN COALESCE(ps.mai,0) ELSE 0 END +
                                CASE WHEN 6 <= $3 THEN COALESCE(ps.jun,0) ELSE 0 END +
                                CASE WHEN 7 <= $3 THEN COALESCE(ps.jul,0) ELSE 0 END +
                                CASE WHEN 8 <= $3 THEN COALESCE(ps.ago,0) ELSE 0 END +
                                CASE WHEN 9 <= $3 THEN COALESCE(ps.set_,0) ELSE 0 END +
                                CASE WHEN 10 <= $3 THEN COALESCE(ps.out_,0) ELSE 0 END +
                                CASE WHEN 11 <= $3 THEN COALESCE(ps.nov,0) ELSE 0 END +
                                CASE WHEN 12 <= $3 THEN COALESCE(ps.dez,0) ELSE 0 END
                            )
                        END
                    ), 0) AS ha_meta,

                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.conta, ''))) IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                            THEN (
                                CASE WHEN 1 <= $3 THEN COALESCE(ps.jan,0) ELSE 0 END +
                                CASE WHEN 2 <= $3 THEN COALESCE(ps.fev,0) ELSE 0 END +
                                CASE WHEN 3 <= $3 THEN COALESCE(ps.mar,0) ELSE 0 END +
                                CASE WHEN 4 <= $3 THEN COALESCE(ps.abr,0) ELSE 0 END +
                                CASE WHEN 5 <= $3 THEN COALESCE(ps.mai,0) ELSE 0 END +
                                CASE WHEN 6 <= $3 THEN COALESCE(ps.jun,0) ELSE 0 END +
                                CASE WHEN 7 <= $3 THEN COALESCE(ps.jul,0) ELSE 0 END +
                                CASE WHEN 8 <= $3 THEN COALESCE(ps.ago,0) ELSE 0 END +
                                CASE WHEN 9 <= $3 THEN COALESCE(ps.set_,0) ELSE 0 END +
                                CASE WHEN 10 <= $3 THEN COALESCE(ps.out_,0) ELSE 0 END +
                                CASE WHEN 11 <= $3 THEN COALESCE(ps.nov,0) ELSE 0 END +
                                CASE WHEN 12 <= $3 THEN COALESCE(ps.dez,0) ELSE 0 END
                            )
                        END
                    ), 0) AS receita_meta

                FROM planejamento_staging ps
                WHERE ps.lote_id = (
                    SELECT id
                    FROM planejamento_import_lotes
                    WHERE ano_referencia::int = $2
                      AND status_processamento = 'processado'
                    ORDER BY id DESC
                    LIMIT 1
                )
                AND ps.flag_valida = TRUE
                AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
                AND UPPER(TRIM(COALESCE(ps.programa_raw, ''))) = UPPER(TRIM($4))
                GROUP BY TRIM(ps.subregiao)
            ),

            realizado_mat AS (
                SELECT
                    TRIM(s.nome) AS subregiao,
                    COALESCE(SUM(rp.matriculas_real), 0) AS matriculas_real
                FROM realizado_programas rp
                JOIN ofertas_programas o
                ON o.codigo::text = rp.cod_oferta::text
                JOIN uo u
                ON u.codigo::text = o.cod_uo::text
                JOIN subregioes s
                ON s.codigo::text = u.cod_subregiao::text
                WHERE o.cod_programa = $1
                AND o.ano::int = $2
                AND rp.ano::int = $2
                AND rp.mes::int <= $3
                GROUP BY TRIM(s.nome)
            ),

            realizado_fin AS (
                SELECT
                    TRIM(s.nome) AS subregiao,
                    COALESCE(SUM(rp.ha_real), 0) AS ha_real,
                    COALESCE(SUM(rp.receita_real), 0) AS receita_real
                FROM realizado_programas rp
                JOIN ofertas_programas o
                  ON o.codigo::text = rp.cod_oferta::text
                JOIN uo u
                  ON u.codigo::text = o.cod_uo::text
                JOIN subregioes s
                  ON s.codigo::text = u.cod_subregiao::text
                WHERE o.cod_programa = $1
                  AND o.ano::int = $2
                  AND rp.ano::int = $2
                  AND rp.mes::int <= $3
                GROUP BY TRIM(s.nome)
            )

            SELECT
                COALESCE(m.subregiao, rm.subregiao, rf.subregiao) AS subregiao,

                COALESCE(rm.matriculas_real, 0) AS matriculas_real,
                COALESCE(m.matriculas_meta, 0) AS matriculas_meta,

                COALESCE(rf.ha_real, 0) AS ha_real,
                COALESCE(m.ha_meta, 0) AS ha_meta,

                COALESCE(rf.receita_real, 0) AS receita_real,
                COALESCE(m.receita_meta, 0) AS receita_meta

            FROM metas m
            FULL OUTER JOIN realizado_mat rm
              ON rm.subregiao = m.subregiao
            FULL OUTER JOIN realizado_fin rf
              ON rf.subregiao = COALESCE(m.subregiao, rm.subregiao)
            WHERE
              COALESCE(rm.matriculas_real, 0) > 0
              OR COALESCE(rf.ha_real, 0) > 0
              OR COALESCE(rf.receita_real, 0) > 0
              OR COALESCE(m.matriculas_meta, 0) > 0
              OR COALESCE(m.ha_meta, 0) > 0
              OR COALESCE(m.receita_meta, 0) > 0
            ORDER BY COALESCE(rm.matriculas_real, 0) DESC, subregiao
            """,
            programa_planejamento,
            ano,
            mes_final,
            prog["nome_programa"],
        )

    return [
        {
            "subregiao": r["subregiao"],
            "matriculas_real": float(r["matriculas_real"] or 0),
            "matriculas_meta": float(r["matriculas_meta"] or 0),
            "ha_real": float(r["ha_real"] or 0),
            "ha_meta": float(r["ha_meta"] or 0),
            "receita_real": float(r["receita_real"] or 0),
            "receita_meta": float(r["receita_meta"] or 0),
        }
        for r in rows
    ]

class RelatorioProgramaSalvarIn(BaseModel):
    programa: int
    ano: int
    mes: int
    descricao_programa: str = ""

    mat_real_mes: float = 0
    mat_meta_mes: float = 0
    mat_proj_mes: float = 0
    mat_real_acum: float = 0
    mat_meta_acum: float = 0
    mat_meta_anual: float = 0
    mat_proj_anual: float = 0

    ha_real_mes: float = 0
    ha_meta_mes: float = 0
    ha_proj_mes: float = 0
    ha_real_acum: float = 0
    ha_meta_acum: float = 0
    ha_meta_anual: float = 0
    ha_proj_anual: float = 0

    rec_real_mes: float = 0
    rec_meta_mes: float = 0
    rec_proj_mes: float = 0
    rec_real_acum: float = 0
    rec_meta_acum: float = 0
    rec_meta_anual: float = 0
    rec_proj_anual: float = 0

    regioes: int = 0
    turmas: int = 0

    acoes: List[str] = []

@router.post("/relatorio-programa/salvar")
async def relatorio_programa_salvar(
    request: Request,
    payload: RelatorioProgramaSalvarIn
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO relatorio_programa (
                    cod_programa, ano, mes, descricao_programa,
                    mat_real_mes, mat_meta_mes, mat_proj_mes,
                    mat_real_acum, mat_meta_acum, mat_meta_anual, mat_proj_anual,
                    ha_real_mes, ha_meta_mes, ha_proj_mes,
                    ha_real_acum, ha_meta_acum, ha_meta_anual, ha_proj_anual,
                    rec_real_mes, rec_meta_mes, rec_proj_mes,
                    rec_real_acum, rec_meta_acum, rec_meta_anual, rec_proj_anual,
                    regioes, turmas, atualizado_em
                )
                VALUES (
                    $1,$2,$3,$4,
                    $5,$6,$7,
                    $8,$9,$10,$11,
                    $12,$13,$14,
                    $15,$16,$17,$18,
                    $19,$20,$21,
                    $22,$23,$24,$25,
                    $26,$27, NOW()
                )
                ON CONFLICT (cod_programa, ano, mes)
                DO UPDATE SET
                    descricao_programa = EXCLUDED.descricao_programa,
                    mat_real_mes = EXCLUDED.mat_real_mes,
                    mat_meta_mes = EXCLUDED.mat_meta_mes,
                    mat_proj_mes = EXCLUDED.mat_proj_mes,
                    mat_real_acum = EXCLUDED.mat_real_acum,
                    mat_meta_acum = EXCLUDED.mat_meta_acum,
                    mat_meta_anual = EXCLUDED.mat_meta_anual,
                    mat_proj_anual = EXCLUDED.mat_proj_anual,
                    ha_real_mes = EXCLUDED.ha_real_mes,
                    ha_meta_mes = EXCLUDED.ha_meta_mes,
                    ha_proj_mes = EXCLUDED.ha_proj_mes,
                    ha_real_acum = EXCLUDED.ha_real_acum,
                    ha_meta_acum = EXCLUDED.ha_meta_acum,
                    ha_meta_anual = EXCLUDED.ha_meta_anual,
                    ha_proj_anual = EXCLUDED.ha_proj_anual,
                    rec_real_mes = EXCLUDED.rec_real_mes,
                    rec_meta_mes = EXCLUDED.rec_meta_mes,
                    rec_proj_mes = EXCLUDED.rec_proj_mes,
                    rec_real_acum = EXCLUDED.rec_real_acum,
                    rec_meta_acum = EXCLUDED.rec_meta_acum,
                    rec_meta_anual = EXCLUDED.rec_meta_anual,
                    rec_proj_anual = EXCLUDED.rec_proj_anual,
                    regioes = EXCLUDED.regioes,
                    turmas = EXCLUDED.turmas,
                    atualizado_em = NOW()
                RETURNING id
                """,
                payload.programa, payload.ano, payload.mes, payload.descricao_programa,
                payload.mat_real_mes, payload.mat_meta_mes, payload.mat_proj_mes,
                payload.mat_real_acum, payload.mat_meta_acum, payload.mat_meta_anual, payload.mat_proj_anual,
                payload.ha_real_mes, payload.ha_meta_mes, payload.ha_proj_mes,
                payload.ha_real_acum, payload.ha_meta_acum, payload.ha_meta_anual, payload.ha_proj_anual,
                payload.rec_real_mes, payload.rec_meta_mes, payload.rec_proj_mes,
                payload.rec_real_acum, payload.rec_meta_acum, payload.rec_meta_anual, payload.rec_proj_anual,
                payload.regioes, payload.turmas
            )

            relatorio_id = row["id"]

            await conn.execute(
                "DELETE FROM relatorio_programa_acoes WHERE relatorio_id = $1",
                relatorio_id
            )

            if payload.acoes:
                await conn.executemany(
                    """
                    INSERT INTO relatorio_programa_acoes (relatorio_id, ordem, descricao)
                    VALUES ($1, $2, $3)
                    """,
                    [
                        (relatorio_id, i + 1, acao.strip())
                        for i, acao in enumerate(payload.acoes)
                        if str(acao).strip()
                    ]
                )

    return {"ok": True, "relatorio_id": relatorio_id}

@router.get("/relatorio-programa/carregar")
async def relatorio_programa_carregar(
    request: Request,
    programa: int,
    ano: int,
    mes: int,
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rel = await conn.fetchrow(
            """
            SELECT *
            FROM relatorio_programa
            WHERE cod_programa = $1
              AND ano = $2
              AND mes = $3
            """,
            programa, ano, mes
        )

        if not rel:
            return {"existe": False, "acoes": []}

        acoes = await conn.fetch(
            """
            SELECT ordem, descricao
            FROM relatorio_programa_acoes
            WHERE relatorio_id = $1
            ORDER BY ordem
            """,
            rel["id"]
        )

    return {
        "existe": True,
        "acoes": [r["descricao"] for r in acoes]
    }

@router.get("/performance/cards")
async def performance_cards(
    request: Request,
    indicador: str,
    ano: int,
    meses: str | None = None,
    subregioes: str | None = None,
    programas: str | None = None,
):
    pool = request.app.state.pool

    if indicador not in ("matriculas", "hora_aluno", "receita"):
        raise HTTPException(status_code=400, detail="Indicador inválido.")

    ids_sub = [int(x) for x in (subregioes or "").split(",") if x.strip().isdigit()]
    ids_prog_txt = [str(int(x)) for x in (programas or "").split(",") if x.strip().isdigit()]
    ids_meses = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]

    if not ids_meses:
        ids_meses = list(range(1, 13))

    params = [ano, ids_meses]
    idx = 3

    filtro_stage_sub = ""
    filtro_stage_prog = ""
    filtro_real_sub = ""
    filtro_real_prog = ""
    filtro_real_mat_sub = ""
    filtro_real_mat_prog = ""
    filtro_sem_contrato_sub = ""
    filtro_sem_contrato_prog = ""

    if ids_sub:
        filtro_stage_sub = f" AND bs.subregiao_codigo = ANY(${idx}::int[])"
        filtro_real_sub = f" AND br.subregiao_codigo = ANY(${idx}::int[])"
        filtro_real_mat_sub = f" AND CAST(COALESCE(u.cod_subregiao, 0) AS integer) = ANY(${idx}::int[])"
        filtro_sem_contrato_sub = f" AND CAST(COALESCE(u.cod_subregiao, 0) AS integer) = ANY(${idx}::int[])"
        params.append(ids_sub)
        idx += 1

    if ids_prog_txt:
        filtro_stage_prog = f" AND bs.programa_id_txt = ANY(${idx}::text[])"
        filtro_real_prog = f" AND br.programa_id_txt = ANY(${idx}::text[])"
        filtro_real_mat_prog = f" AND CAST(o.cod_programa AS text) = ANY(${idx}::text[])"
        filtro_sem_contrato_prog = f" AND CAST(t.cod_programa AS text) = ANY(${idx}::text[])"
        params.append(ids_prog_txt)
        idx += 1

    conta_filtro = {
        "matriculas": ("MATRÍCULAS", "MATRICULAS"),
        "hora_aluno": ("HORA ALUNO", "HORA-ALUNO", "HORA_ALUNO"),
        "receita": ("RECEITAS CORRENTES", "RECEITA", "RECEITAS"),
    }[indicador]

    realizado_cte = ""
    sem_contrato_cte = ""
    sem_contrato_select = "0 AS sem_contrato,"
    sem_contrato_join = ""

    if indicador == "matriculas":
        realizado_cte = f"""
        realizado_mes AS (
            SELECT
                CAST(o.cod_programa AS text) AS programa_id_txt,
                COALESCE(SUM(COALESCE(rp.matriculas_real, 0)), 0) AS realizado
            FROM realizado_programas rp
            JOIN ofertas_programas o
                ON o.codigo = rp.cod_oferta
            LEFT JOIN uo u
                ON u.codigo = o.cod_uo
            WHERE rp.ano = $1
            AND rp.mes = ANY($2::int[])
            {filtro_real_mat_sub}
            {filtro_real_mat_prog}
            GROUP BY CAST(o.cod_programa AS text)
        )
        """
        sem_contrato_cte = f"""
        ,
        sem_contrato_mes AS (
            SELECT
                CAST(t.cod_programa AS text) AS programa_id_txt,
                COUNT(*) AS sem_contrato
            FROM turmas_movimento_mensal tmm
            JOIN turmas t
                ON t.codigo = tmm.cod_turma
            JOIN sge_turma_detalhe_alunos da
                ON da.cod_turma = t.codigo_sge
            AND da.status_matricula = 'MATRICULADO'
            LEFT JOIN uo u
                ON u.codigo = t.cod_uo
            WHERE tmm.ano = $1
            AND tmm.mes = ANY($2::int[])
            AND EXTRACT(YEAR FROM da.data_matricula)::int = tmm.ano
            AND EXTRACT(MONTH FROM da.data_matricula)::int = tmm.mes
            AND (
                da.data_ini_contratoapr IS NULL
                OR da.data_fim_contratoapr IS NULL
                OR da.data_ini_contratoapr > make_date($1, tmm.mes, 1)
                OR da.data_fim_contratoapr < (
                    make_date($1, tmm.mes, 1)
                    + interval '1 month'
                    - interval '1 day'
                )::date
            )
            {filtro_sem_contrato_sub}
            {filtro_sem_contrato_prog}
            GROUP BY CAST(t.cod_programa AS text)
        )
        """
        sem_contrato_select = "COALESCE(sc.sem_contrato, 0) AS sem_contrato,"
        sem_contrato_join = """
        LEFT JOIN sem_contrato_mes sc
        ON sc.programa_id_txt = COALESCE(pb.programa_id_txt, rm.programa_id_txt)
        """
    else:
        real_col = {
            "hora_aluno": "COALESCE(rp.ha_real, 0)",
            "receita": "COALESCE(rp.receita_real, 0)",
        }[indicador]

        realizado_cte = f"""
        realizado_mes AS (
            SELECT
                br.programa_id_txt,
                COALESCE(SUM({real_col}), 0) AS realizado
            FROM br
            LEFT JOIN realizado_programas rp
            ON TRIM(COALESCE(rp.cod_oferta::text, '')) = br.oferta_id_txt
            AND CAST(rp.ano AS integer) = $1
            AND CAST(rp.mes AS integer) = ANY($2::int[])
            WHERE 1=1
            {filtro_real_sub}
            {filtro_real_prog}
            GROUP BY br.programa_id_txt
        )
        """

    sql = f"""
    WITH lote_planejamento AS (
        SELECT id
        FROM planejamento_import_lotes
        WHERE CAST(ano_referencia AS integer) = $1
        AND status_processamento = 'processado'
        ORDER BY id DESC
        LIMIT 1
    ),

    programas_norm AS (
        SELECT
            TRIM(COALESCE(codigo::text, '')) AS codigo_txt,
            UPPER(TRIM(COALESCE(nome_programa::text, ''))) AS nome_chave,
            CASE
                WHEN TRIM(COALESCE(codigo::text, '')) = '29' THEN '11'
                WHEN TRIM(COALESCE(codigo::text, '')) = '30' THEN '7'
                ELSE TRIM(COALESCE(codigo::text, ''))
            END AS programa_id_txt,
            CASE
                WHEN TRIM(COALESCE(codigo::text, '')) IN ('11', '29') THEN 'CARREIRAS EMPREGABILIDADE'
                WHEN TRIM(COALESCE(codigo::text, '')) IN ('7', '30') THEN 'QUALIFIC.AI'
                ELSE nome_programa
            END AS programa_nome
        FROM programas
    ),

    subregioes_norm AS (
        SELECT
            CAST(codigo AS integer) AS codigo_int,
            UPPER(TRIM(COALESCE(nome::text, ''))) AS nome_chave
        FROM subregioes
    ),

    bs AS (
        SELECT
            pn.programa_id_txt,
            pn.programa_nome AS programa,
            sn.codigo_int AS subregiao_codigo,
            UPPER(TRIM(COALESCE(ps.tipo::text, ''))) AS tipo,
            (
                CASE WHEN 1 = ANY($2::int[]) THEN COALESCE(ps.jan, 0) ELSE 0 END +
                CASE WHEN 2 = ANY($2::int[]) THEN COALESCE(ps.fev, 0) ELSE 0 END +
                CASE WHEN 3 = ANY($2::int[]) THEN COALESCE(ps.mar, 0) ELSE 0 END +
                CASE WHEN 4 = ANY($2::int[]) THEN COALESCE(ps.abr, 0) ELSE 0 END +
                CASE WHEN 5 = ANY($2::int[]) THEN COALESCE(ps.mai, 0) ELSE 0 END +
                CASE WHEN 6 = ANY($2::int[]) THEN COALESCE(ps.jun, 0) ELSE 0 END +
                CASE WHEN 7 = ANY($2::int[]) THEN COALESCE(ps.jul, 0) ELSE 0 END +
                CASE WHEN 8 = ANY($2::int[]) THEN COALESCE(ps.ago, 0) ELSE 0 END +
                CASE WHEN 9 = ANY($2::int[]) THEN COALESCE(ps.set_, 0) ELSE 0 END +
                CASE WHEN 10 = ANY($2::int[]) THEN COALESCE(ps.out_, 0) ELSE 0 END +
                CASE WHEN 11 = ANY($2::int[]) THEN COALESCE(ps.nov, 0) ELSE 0 END +
                CASE WHEN 12 = ANY($2::int[]) THEN COALESCE(ps.dez, 0) ELSE 0 END
            ) AS valor_mes
        FROM planejamento_staging ps
        JOIN lote_planejamento lp
        ON lp.id = ps.lote_id
        JOIN programas_norm pn
        ON pn.nome_chave = UPPER(TRIM(COALESCE(ps.programa_raw::text, '')))
        JOIN subregioes_norm sn
        ON sn.nome_chave = UPPER(TRIM(COALESCE(ps.subregiao::text, '')))
        WHERE ps.flag_valida = TRUE
        AND UPPER(TRIM(COALESCE(ps.conta::text, ''))) IN {tuple(conta_filtro)}
    ),

    planejamento_base AS (
        SELECT
            bs.programa_id_txt,
            bs.programa,
            COALESCE(SUM(CASE WHEN bs.tipo = 'META' THEN bs.valor_mes ELSE 0 END), 0) AS meta,
            COALESCE(SUM(CASE WHEN bs.tipo = 'PROJETADO' THEN bs.valor_mes ELSE 0 END), 0) AS projetado
        FROM bs
        WHERE 1=1
        {filtro_stage_sub}
        {filtro_stage_prog}
        GROUP BY bs.programa_id_txt, bs.programa
    ),

    br AS (
        SELECT DISTINCT
            TRIM(COALESCE(o.codigo::text, '')) AS oferta_id_txt,
            pn.programa_id_txt,
            COALESCE(
                CASE
                    WHEN TRIM(COALESCE(u.cod_subregiao::text, '')) ~ '^[0-9]+$'
                    THEN CAST(TRIM(u.cod_subregiao::text) AS integer)
                    ELSE NULL
                END,
                sn.codigo_int
            ) AS subregiao_codigo
        FROM ofertas_programas o
        JOIN programas_norm pn
        ON pn.codigo_txt = TRIM(COALESCE(o.cod_programa::text, ''))
        LEFT JOIN uo u
        ON TRIM(COALESCE(u.codigo::text, '')) = TRIM(COALESCE(o.cod_uo::text, ''))
        LEFT JOIN planejamento_staging ps
        ON TRIM(COALESCE(ps.cr_raw::text, '')) = TRIM(COALESCE(o.cr::text, ''))
        AND ps.lote_id = (SELECT id FROM lote_planejamento)
        LEFT JOIN subregioes_norm sn
        ON sn.nome_chave = UPPER(TRIM(COALESCE(ps.subregiao::text, '')))
        WHERE CAST(o.ano AS integer) = $1
    ),

    {realizado_cte}
    {sem_contrato_cte}

    SELECT
        CAST(COALESCE(pb.programa_id_txt, rm.programa_id_txt) AS integer) AS programa_id,
        COALESCE(pb.programa, (
            SELECT p.nome_programa
            FROM programas p
            WHERE TRIM(COALESCE(p.codigo::text, '')) = COALESCE(pb.programa_id_txt, rm.programa_id_txt)
            LIMIT 1
        )) AS programa,
        COALESCE(pb.meta, 0) AS meta,
        COALESCE(pb.projetado, 0) AS projetado,
        COALESCE(rm.realizado, 0) AS realizado,
        {sem_contrato_select}
        CASE
            WHEN COALESCE(pb.meta, 0) = 0 THEN 0
            ELSE ROUND((COALESCE(rm.realizado, 0) / NULLIF(pb.meta, 0)) * 100, 1)
        END AS pct_meta,
        CASE
            WHEN COALESCE(pb.meta, 0) = 0 AND COALESCE(rm.realizado, 0) = 0 THEN 'Ainda não iniciado'
            WHEN COALESCE(pb.meta, 0) = 0 AND COALESCE(rm.realizado, 0) > 0 THEN 'Meta atingida'
            WHEN COALESCE(rm.realizado, 0) >= pb.meta THEN 'Meta atingida'
            WHEN COALESCE(rm.realizado, 0) >= pb.meta * 0.8 THEN 'Atenção'
            ELSE 'Crítico'
        END AS status
    FROM planejamento_base pb
    FULL OUTER JOIN realizado_mes rm
    ON rm.programa_id_txt = pb.programa_id_txt
    {sem_contrato_join}
    ORDER BY COALESCE(pb.programa, rm.programa_id_txt)
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    resultado = []
    for row in rows:
        d = dict(row)
        d["meta"] = float(d["meta"] or 0)
        d["projetado"] = float(d["projetado"] or 0)
        d["realizado"] = float(d["realizado"] or 0)
        d["sem_contrato"] = float(d.get("sem_contrato") or 0)
        d["pct_meta"] = float(d["pct_meta"] or 0)
        resultado.append(d)

    return resultado

@router.get("/performance/preditiva")
async def performance_preditiva(
    request: Request,
    ano: int,
    meses: str | None = None,
    subregioes: str | None = None,
    programas: str | None = None,
):
    pool = request.app.state.pool

    ids_sub = [int(x) for x in (subregioes or "").split(",") if x.strip().isdigit()]
    ids_prog_txt = [str(int(x)) for x in (programas or "").split(",") if x.strip().isdigit()]
    ids_meses = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]

    if not ids_meses:
        ids_meses = list(range(1, 13))

    nomes_meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    async def buscar_serie(indicador: str):
        params = [ano]
        idx = 2
        filtro_prog_oferta = ""
        filtro_prog_turma = ""

        filtro_oferta = ""
        filtro_meta = ""
        filtro_proj = ""
        filtro_real = ""

        if ids_sub:
            filtro_oferta += f" AND u.cod_subregiao = ANY(${idx}::int[])"
            filtro_meta += f" AND u.cod_subregiao = ANY(${idx}::int[])"
            filtro_proj += f" AND u.cod_subregiao = ANY(${idx}::int[])"
            filtro_real += f" AND u.cod_subregiao = ANY(${idx}::int[])"
            params.append(ids_sub)
            idx += 1

        if ids_prog_txt:
            filtro_prog_oferta = f" AND pn.programa_id_txt = ANY(${idx}::text[])"
            filtro_prog_turma = f" AND pn.programa_id_txt = ANY(${idx}::text[])"
            params.append(ids_prog_txt)
            idx += 1

        campo_meta = {
            "matriculas": "matriculas_meta",
            "hora_aluno": "ha_meta",
            "receita": "receita_meta",
        }[indicador]

        campo_proj = {
            "matriculas": "matriculas_proj",
            "hora_aluno": "ha_proj",
            "receita": "receita_proj",
        }[indicador]

        campo_real = {
            "matriculas": "matriculas_real",
            "hora_aluno": "ha_real",
            "receita": "receita_real",
        }[indicador]

        real_cte = f"""
        real AS (
            SELECT
                rp.mes,
                COALESCE(
                    SUM(
                        rp.{campo_real if campo_real else "matriculas_real"}
                    ),
                    0
                ) AS valor

            FROM ofertas_filtradas ofi

            JOIN realizado_programas rp
                ON rp.cod_oferta = ofi.cod_oferta
            AND rp.ano = $1

            JOIN ofertas_programas o
                ON o.codigo = ofi.cod_oferta

            JOIN uo u
                ON u.codigo = o.cod_uo

            WHERE 1=1
            {filtro_real}

            GROUP BY rp.mes
        )
        """
        conta_filtro = {
            "matriculas": ("MATRÍCULAS", "MATRICULAS"),
            "hora_aluno": ("HORA ALUNO", "HORA-ALUNO", "HORA_ALUNO"),
            "receita": ("RECEITAS CORRENTES", "RECEITA", "RECEITAS"),
        }[indicador]

        sql = f"""
        WITH meses AS (
            SELECT generate_series(1, 12) AS mes
        ),
        lote_planejamento AS (
            SELECT id
            FROM planejamento_import_lotes
            WHERE CAST(ano_referencia AS integer) = $1
              AND status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
        ),
        subregioes_norm AS (
            SELECT
                CAST(codigo AS integer) AS codigo_int,
                UPPER(TRIM(COALESCE(nome::text, ''))) AS nome_chave
            FROM subregioes
        ),
        programas_norm AS (
            SELECT
                TRIM(COALESCE(codigo::text, '')) AS codigo_txt,
                CASE
                    WHEN TRIM(COALESCE(codigo::text, '')) = '29' THEN '11'
                    WHEN TRIM(COALESCE(codigo::text, '')) = '30' THEN '7'
                    ELSE TRIM(COALESCE(codigo::text, ''))
                END AS programa_id_txt
            FROM programas
        ),
        ofertas_filtradas AS (
            SELECT
                o.codigo AS cod_oferta,
                o.cod_programa,
                pn.programa_id_txt
            FROM ofertas_programas o
            JOIN uo u
              ON u.codigo = o.cod_uo
            JOIN programas_norm pn
              ON pn.codigo_txt = TRIM(COALESCE(o.cod_programa::text, ''))
            WHERE o.ano = $1
            {filtro_oferta}
            {filtro_prog_oferta}
        ),
        meta AS (
            SELECT
                m.mes,
                COALESCE(SUM(
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
                    END
                ), 0) AS valor
            FROM meses m
            JOIN planejamento_staging ps
              ON ps.lote_id = (SELECT id FROM lote_planejamento)
             AND ps.flag_valida = TRUE
            JOIN programas_norm pn_ps
              ON pn_ps.programa_id_txt = (
                    CASE
                        WHEN UPPER(TRIM(COALESCE(ps.programa_raw::text, ''))) = 'CARREIRAS EMPREGABILIDADE' THEN '11'
                        WHEN UPPER(TRIM(COALESCE(ps.programa_raw::text, ''))) = 'QUALIFIC.AI' THEN '7'
                        ELSE (
                            SELECT pn2.programa_id_txt
                            FROM programas_norm pn2
                            WHERE pn2.codigo_txt IN (
                                SELECT TRIM(COALESCE(codigo::text, ''))
                                FROM programas
                                WHERE UPPER(TRIM(COALESCE(nome_programa::text, ''))) = UPPER(TRIM(COALESCE(ps.programa_raw::text, '')))
                            )
                            LIMIT 1
                        )
                    END
                )
            JOIN subregioes_norm sn
              ON sn.nome_chave = UPPER(TRIM(COALESCE(ps.subregiao::text, '')))
            WHERE UPPER(TRIM(COALESCE(ps.tipo::text, ''))) = 'META'
              AND UPPER(TRIM(COALESCE(ps.conta::text, ''))) IN {tuple(conta_filtro)}
              {filtro_prog_oferta.replace('pn.programa_id_txt', 'pn_ps.programa_id_txt')}
              {filtro_oferta.replace('u.cod_subregiao', 'sn.codigo_int')}
            GROUP BY m.mes
        ),
        proj AS (
            SELECT
                pp.mes,
                COALESCE(SUM(pp.{campo_proj}), 0) AS valor
            FROM ofertas_filtradas ofi
            JOIN projetado_programas pp
              ON pp.cod_oferta = ofi.cod_oferta
             AND pp.ano = $1
            JOIN ofertas_programas o
              ON o.codigo = ofi.cod_oferta
            JOIN uo u
              ON u.codigo = o.cod_uo
            WHERE 1=1
            {filtro_proj}
            GROUP BY pp.mes
        ),
        {real_cte}
        SELECT
            m.mes,
            COALESCE(mt.valor, 0) AS meta,
            COALESCE(rl.valor, 0) AS realizado,
            COALESCE(pj.valor, 0) AS projetado
        FROM meses m
        LEFT JOIN meta mt ON mt.mes = m.mes
        LEFT JOIN real rl ON rl.mes = m.mes
        LEFT JOIN proj pj ON pj.mes = m.mes
        ORDER BY m.mes
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        serie = []
        for row in rows:
            serie.append({
                "mes": int(row["mes"]),
                "meta": float(row["meta"] or 0),
                "realizado": float(row["realizado"] or 0),
                "projetado": float(row["projetado"] or 0),
            })

        return serie

    def calcular_previsao(serie):
        meses_com_real = [r["mes"] for r in serie if r["mes"] in ids_meses and r["realizado"] > 0]
        valores_reais = [r["realizado"] for r in serie if r["mes"] in ids_meses and r["realizado"] > 0]

        previsao = [None] * 12

        if not meses_com_real:
            return previsao

        if len(meses_com_real) < 2:
            return previsao

        media_real = sum(valores_reais) / len(valores_reais)
        ultimo_mes_real = max(meses_com_real)

        for i in range(12):
            mes = i + 1
            if mes > ultimo_mes_real:
                previsao[i] = int(round(media_real))

        return previsao

    async def montar_indicador(indicador: str):
        serie = await buscar_serie(indicador)

        meta = [round(r["meta"], 2) for r in serie]
        realizado = []
        for r in serie:
            if r["mes"] in ids_meses:
                realizado.append(round(r["realizado"], 2))
            else:
                realizado.append(None)

        previsao = calcular_previsao(serie)

        return {
            "meta": meta,
            "realizado": realizado,
            "previsao": previsao,
        }

    return {
        "meses": nomes_meses,
        "matriculas": await montar_indicador("matriculas"),
        "hora_aluno": await montar_indicador("hora_aluno"),
        "receita": await montar_indicador("receita"),
    }

@router.get("/planejamento/filtros/subregioes-por-programa")
async def listar_subregioes_por_programa(
    request: Request,
    ano: int,
    programa_id: int,
    meses: str | None = None,
):
    pool = request.app.state.pool

    ids_meses = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]
    if not ids_meses:
        ids_meses = list(range(1, 13))

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH lote_planejamento AS (
                SELECT id
                FROM planejamento_import_lotes
                WHERE CAST(ano_referencia AS integer) = $1
                  AND status_processamento = 'processado'
                ORDER BY id DESC
                LIMIT 1
            ),
            programas_norm AS (
                SELECT
                    TRIM(COALESCE(codigo::text, '')) AS codigo_txt,
                    CASE
                        WHEN TRIM(COALESCE(codigo::text, '')) = '29' THEN '11'
                        WHEN TRIM(COALESCE(codigo::text, '')) = '30' THEN '7'
                        ELSE TRIM(COALESCE(codigo::text, ''))
                    END AS programa_id_txt,
                    UPPER(TRIM(COALESCE(nome_programa::text, ''))) AS nome_chave
                FROM programas
            ),
            subregioes_norm AS (
                SELECT
                    CAST(codigo AS integer) AS codigo,
                    nome,
                    UPPER(TRIM(COALESCE(nome::text, ''))) AS nome_chave
                FROM subregioes
            ),
            base_planejamento AS (
                SELECT DISTINCT
                    sn.codigo,
                    sn.nome
                FROM planejamento_staging ps
                JOIN lote_planejamento lp
                  ON lp.id = ps.lote_id
                JOIN programas_norm pn
                  ON pn.programa_id_txt = (
                        CASE
                            WHEN UPPER(TRIM(COALESCE(ps.programa_raw::text, ''))) = 'CARREIRAS EMPREGABILIDADE' THEN '11'
                            WHEN UPPER(TRIM(COALESCE(ps.programa_raw::text, ''))) = 'QUALIFIC.AI' THEN '7'
                            ELSE (
                                SELECT pn2.programa_id_txt
                                FROM programas_norm pn2
                                WHERE pn2.nome_chave = UPPER(TRIM(COALESCE(ps.programa_raw::text, '')))
                                LIMIT 1
                            )
                        END
                    )
                JOIN subregioes_norm sn
                  ON sn.nome_chave = UPPER(TRIM(COALESCE(ps.subregiao::text, '')))
                WHERE ps.flag_valida = TRUE
                  AND pn.programa_id_txt = $2::text
                  AND (
                        (1 = ANY($3::int[]) AND COALESCE(ps.jan, 0) <> 0) OR
                        (2 = ANY($3::int[]) AND COALESCE(ps.fev, 0) <> 0) OR
                        (3 = ANY($3::int[]) AND COALESCE(ps.mar, 0) <> 0) OR
                        (4 = ANY($3::int[]) AND COALESCE(ps.abr, 0) <> 0) OR
                        (5 = ANY($3::int[]) AND COALESCE(ps.mai, 0) <> 0) OR
                        (6 = ANY($3::int[]) AND COALESCE(ps.jun, 0) <> 0) OR
                        (7 = ANY($3::int[]) AND COALESCE(ps.jul, 0) <> 0) OR
                        (8 = ANY($3::int[]) AND COALESCE(ps.ago, 0) <> 0) OR
                        (9 = ANY($3::int[]) AND COALESCE(ps.set_, 0) <> 0) OR
                        (10 = ANY($3::int[]) AND COALESCE(ps.out_, 0) <> 0) OR
                        (11 = ANY($3::int[]) AND COALESCE(ps.nov, 0) <> 0) OR
                        (12 = ANY($3::int[]) AND COALESCE(ps.dez, 0) <> 0)
                  )
            )
            SELECT DISTINCT codigo, nome
            FROM base_planejamento
            ORDER BY nome
            """,
            ano,
            str(programa_id),
            ids_meses,
        )

    return [dict(r) for r in rows]

@router.get("/subregioes/nome")
async def subregioes_nome(
    request: Request,
    ids: str
):
    pool = request.app.state.pool

    ids_list = [int(x) for x in str(ids).split(",") if x.strip().isdigit()]
    if not ids_list:
        return {"nomes": []}

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT nome
            FROM subregioes
            WHERE codigo = ANY($1::int[])
            ORDER BY nome
            """,
            ids_list
        )

    return {"nomes": [r["nome"] for r in rows]}

@router.get("/performance/programa/serie")
async def performance_programa_serie(
    request: Request,
    programa_id: int,
    ano: int,
    indicador: str,
    subregioes: str | None = None,
):
    pool = request.app.state.pool

    if indicador not in ("matriculas", "hora_aluno", "receita"):
        raise HTTPException(status_code=400, detail="Indicador inválido.")

    params = [ano, programa_id]
    filtros = []

    if subregioes:
        ids_sub = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
        if ids_sub:
            filtros.append(f"u.cod_subregiao = ANY(${len(params)+1}::int[])")
            params.append(ids_sub)

    where_extra = ""
    if filtros:
        where_extra = " AND " + " AND ".join(filtros)

    if indicador == "matriculas":
        meta_col = "COALESCE(mp.matriculas_meta, 0)"
        proj_col = "COALESCE(pp.matriculas_proj, 0)"
    elif indicador == "hora_aluno":
        meta_col = "COALESCE(mp.ha_meta, 0)"
        proj_col = "COALESCE(pp.ha_proj, 0)"
    else:
        meta_col = "COALESCE(mp.receita_meta, 0)"
        proj_col = "COALESCE(pp.receita_proj, 0)"

    if indicador == "matriculas":
        real_col = "COALESCE(rp.matriculas_real, 0)"
    elif indicador == "hora_aluno":
        real_col = "COALESCE(rp.ha_real, 0)"
    else:
        real_col = "COALESCE(rp.receita_real, 0)"

    sql = f"""
    WITH meses AS (
        SELECT generate_series(1, 12) AS mes
    ),
    ofertas_filtradas AS (
        SELECT DISTINCT
            o.codigo AS cod_oferta
        FROM ofertas_programas o
        JOIN programas p
        ON p.codigo = o.cod_programa
        JOIN uo u
        ON u.codigo = o.cod_uo
        WHERE o.ano = $1
        AND (
                CASE
                    WHEN p.codigo = 29 THEN 11
                    WHEN p.codigo = 30 THEN 7
                    ELSE p.codigo
                END
            ) = $2
        {where_extra}
    ),
    meta_mes AS (
        SELECT
            mp.cod_oferta,
            mp.mes,
            COALESCE(SUM({meta_col}), 0) AS meta
        FROM meta_programas mp
        JOIN ofertas_filtradas o
        ON o.cod_oferta = mp.cod_oferta
        WHERE mp.ano = $1
        GROUP BY mp.cod_oferta, mp.mes
    ),
    proj_mes AS (
        SELECT
            pp.cod_oferta,
            pp.mes,
            COALESCE(SUM({proj_col}), 0) AS projetado
        FROM projetado_programas pp
        JOIN ofertas_filtradas o
        ON o.cod_oferta = pp.cod_oferta
        WHERE pp.ano = $1
        GROUP BY pp.cod_oferta, pp.mes
    ),
    meta_total_mes AS (
        SELECT
            mes,
            COALESCE(SUM(meta), 0) AS meta
        FROM meta_mes
        GROUP BY mes
    ),
    proj_total_mes AS (
        SELECT
            mes,
            COALESCE(SUM(projetado), 0) AS projetado
        FROM proj_mes
        GROUP BY mes
    ),
    base AS (
        SELECT
            m.mes,
            COALESCE(mt.meta, 0) AS meta,
            COALESCE(pt.projetado, 0) AS projetado
        FROM meses m
        LEFT JOIN meta_total_mes mt
        ON mt.mes = m.mes
        LEFT JOIN proj_total_mes pt
        ON pt.mes = m.mes
    )
    SELECT
        base.mes,
        base.meta,
        base.projetado,
        {real_col} AS realizado
    FROM base
    LEFT JOIN realizado_programas rp
    ON (
        CASE
            WHEN rp.cod_programa = 29 THEN 11
            WHEN rp.cod_programa = 30 THEN 7
            ELSE rp.cod_programa
        END
        ) = $2
    AND rp.ano = $1
    AND rp.mes = base.mes
    ORDER BY base.mes
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    resultado = []
    for row in rows:
        d = dict(row)
        d["meta"] = float(d["meta"] or 0)
        d["projetado"] = float(d["projetado"] or 0)
        d["realizado"] = float(d["realizado"] or 0)
        resultado.append(d)

    return resultado

@router.get("/modalidades/list")
async def modalidades_list(
    request: Request,
    ano: int = 2026,
    mes: int = 1,
    meses: str | None = None,
):
    pool = request.app.state.pool

    meses_ids = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]
    if not meses_ids:
        meses_ids = [1]

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                m.codigo,
                m.nome AS modalidade
            FROM ofertas_programas o
            JOIN modalidade m
              ON m.codigo = o.cod_modalidade
            LEFT JOIN meta_programas mp
              ON mp.cod_oferta = o.codigo
             AND mp.ano = $1
             AND mp.mes = ANY($2::int[])
            LEFT JOIN projetado_programas pp
              ON pp.cod_oferta = o.codigo
             AND pp.ano = $1
             AND pp.mes = ANY($2::int[])
            LEFT JOIN realizado_programas rp
              ON rp.cod_programa = o.cod_programa
             AND rp.ano = $1
             AND rp.mes = ANY($2::int[])
            WHERE o.ano = $1
              AND m.nome IS NOT NULL
              AND TRIM(m.nome) <> ''
              AND (
                    COALESCE(mp.matriculas_meta, 0) > 0
                 OR COALESCE(pp.matriculas_proj, 0) > 0
                 OR COALESCE(rp.matriculas_real, 0) > 0
              )
            ORDER BY m.nome
            """,
            ano,
            meses_ids
        )

    return [dict(r) for r in rows]

@router.get("/modalidades/summary")
async def modalidades_summary(
    request: Request,
    ano: int = 2026,
    meses: str | None = None,
    modalidades: str | None = None,
):
    pool = request.app.state.pool

    meses_ids = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]

    if not meses_ids:
        meses_ids = list(range(1, 13))

    params = [ano, meses_ids]
    filtro_modalidades = ""
    ids = []

    if modalidades:
        ids = [int(x) for x in modalidades.split(",") if str(x).strip()]
        if ids:
            filtro_modalidades = f" AND o.cod_modalidade = ANY(${len(params)+1}::int[])"
            params.append(ids)

    sql = f"""
    WITH ofertas_filtradas AS (
        SELECT DISTINCT
            o.codigo AS cod_oferta,
            o.cod_programa,
            o.cod_modalidade,
            UPPER(COALESCE(f.nome_financiamento, '')) AS financiamento
        FROM ofertas_programas o
        LEFT JOIN financiamento f
        ON f.codigo = o.cod_financiamento
        WHERE o.ano = $1
        {filtro_modalidades}
    ),
    programas_filtrados AS (
        SELECT DISTINCT
            cod_programa
        FROM ofertas_filtradas
    ),
    meta_total AS (
        SELECT
            COALESCE(SUM(mp.matriculas_meta), 0) AS mat_meta,
            COALESCE(SUM(mp.ha_meta), 0) AS ha_meta,
            COALESCE(SUM(mp.receita_meta), 0) AS rec_meta
        FROM (
            SELECT DISTINCT cod_oferta
            FROM ofertas_filtradas
        ) of
        LEFT JOIN meta_programas mp
            ON mp.cod_oferta = of.cod_oferta
        AND mp.ano = $1
        AND mp.mes = ANY($2::int[])
    ),

    proj_total AS (
        SELECT
            COALESCE(SUM(pp.matriculas_proj), 0) AS mat_proj,
            COALESCE(SUM(pp.ha_proj), 0) AS ha_proj,
            COALESCE(SUM(pp.receita_proj), 0) AS rec_proj
        FROM (
            SELECT DISTINCT cod_oferta
            FROM ofertas_filtradas
        ) of
        LEFT JOIN projetado_programas pp
            ON pp.cod_oferta = of.cod_oferta
        AND pp.ano = $1
        AND pp.mes = ANY($2::int[])
    ),

    real_total AS (
        SELECT
            COALESCE(SUM(rp.matriculas_real), 0) AS mat_real,
            COALESCE(SUM(rp.ha_real), 0) AS ha_real,
            COALESCE(SUM(rp.receita_real), 0) AS rec_real
        FROM (
            SELECT DISTINCT cod_oferta
            FROM ofertas_filtradas
        ) of
        LEFT JOIN realizado_programas rp
        ON rp.cod_oferta = of.cod_oferta
        AND rp.ano = $1
        AND rp.mes = ANY($2::int[])
    )
    SELECT
        mt.mat_meta,
        pt.mat_proj,
        rt.mat_real,

        mt.ha_meta,
        pt.ha_proj,
        rt.ha_real,

        mt.rec_meta,
        pt.rec_proj,
        rt.rec_real
    FROM meta_total mt
    CROSS JOIN proj_total pt
    CROSS JOIN real_total rt
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *params)

    d = dict(row or {})

    return {
        "matriculas": {
            "meta": float(d.get("mat_meta") or 0),
            "projetado": float(d.get("mat_proj") or 0),
            "realizado": float(d.get("mat_real") or 0),
            "gr": 0.0,
            "g": 0.0,
            "p": 0.0,
        },
        "hora_aluno": {
            "meta": float(d.get("ha_meta") or 0),
            "projetado": float(d.get("ha_proj") or 0),
            "realizado": float(d.get("ha_real") or 0),
            "gr": 0.0,
            "g": 0.0,
            "p": 0.0,
        },
        "receita": {
            "meta": float(d.get("rec_meta") or 0),
            "projetado": float(d.get("rec_proj") or 0),
            "realizado": float(d.get("rec_real") or 0),
            "gr": 0.0,
            "g": 0.0,
            "p": 0.0,
        },
    }

@router.get("/modalidades/tabela/programas")
async def modalidades_tabela_programas(
    request: Request,
    ano: int = 2026,
    meses: str | None = None,
    modalidades: str | None = None,
):
    pool = request.app.state.pool

    meses_ids = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]

    if not meses_ids:
        meses_ids = list(range(1, 13))

    params = [ano, meses_ids]
    filtro_modalidades = ""

    if modalidades:
        ids = [int(x) for x in modalidades.split(",") if str(x).strip()]
        if ids:
            filtro_modalidades = f" AND o.cod_modalidade = ANY(${len(params)+1}::int[])"
            params.append(ids)

    sql = f"""
    WITH ofertas_filtradas AS (
        SELECT DISTINCT
            o.codigo AS cod_oferta,
            o.cod_programa,
            p.nome_programa AS programa
        FROM ofertas_programas o
        JOIN programas p
        ON p.codigo = o.cod_programa
        WHERE o.ano = $1
        {filtro_modalidades}
    ),
    programas_filtrados AS (
        SELECT DISTINCT
            cod_programa,
            programa
        FROM ofertas_filtradas
    ),
    meta_mes AS (
        SELECT
            of.cod_programa,
            SUM(COALESCE(mp.matriculas_meta, 0)) AS matriculas_meta,
            SUM(COALESCE(mp.ha_meta, 0)) AS ha_meta,
            SUM(COALESCE(mp.receita_meta, 0)) AS receita_meta
        FROM ofertas_filtradas of
        LEFT JOIN meta_programas mp
          ON mp.cod_oferta = of.cod_oferta
         AND mp.ano = $1
         AND mp.mes = ANY($2::int[])
        GROUP BY of.cod_programa
    ),
    proj_mes AS (
        SELECT
            of.cod_programa,
            SUM(COALESCE(pp.matriculas_proj, 0)) AS matriculas_proj,
            SUM(COALESCE(pp.ha_proj, 0)) AS ha_proj,
            SUM(COALESCE(pp.receita_proj, 0)) AS receita_proj
        FROM ofertas_filtradas of
        LEFT JOIN projetado_programas pp
          ON pp.cod_oferta = of.cod_oferta
         AND pp.ano = $1
         AND pp.mes = ANY($2::int[])
        GROUP BY of.cod_programa
    ),
    real_mes AS (
        SELECT
            of.cod_programa,
            COALESCE(SUM(rp.matriculas_real), 0) AS matriculas_real,
            COALESCE(SUM(rp.ha_real), 0) AS ha_real,
            COALESCE(SUM(rp.receita_real), 0) AS receita_real
        FROM ofertas_filtradas of
        LEFT JOIN realizado_programas rp
            ON rp.cod_oferta = of.cod_oferta
        AND rp.ano = $1
        AND rp.mes = ANY($2::int[])
        GROUP BY of.cod_programa
    )
    SELECT
        pf.programa,
        COALESCE(m.matriculas_meta, 0) AS matriculas_meta,
        COALESCE(pj.matriculas_proj, 0) AS matriculas_proj,
        COALESCE(r.matriculas_real, 0) AS matriculas_real,
        COALESCE(m.ha_meta, 0) AS ha_meta,
        COALESCE(pj.ha_proj, 0) AS ha_proj,
        COALESCE(r.ha_real, 0) AS ha_real,
        COALESCE(m.receita_meta, 0) AS receita_meta,
        COALESCE(pj.receita_proj, 0) AS receita_proj,
        COALESCE(r.receita_real, 0) AS receita_real
    FROM programas_filtrados pf
    LEFT JOIN meta_mes m
      ON m.cod_programa = pf.cod_programa
    LEFT JOIN proj_mes pj
      ON pj.cod_programa = pf.cod_programa
    LEFT JOIN real_mes r
      ON r.cod_programa = pf.cod_programa
    WHERE
        COALESCE(m.matriculas_meta, 0) <> 0
        OR COALESCE(pj.matriculas_proj, 0) <> 0
        OR COALESCE(r.matriculas_real, 0) <> 0
        OR COALESCE(m.ha_meta, 0) <> 0
        OR COALESCE(pj.ha_proj, 0) <> 0
        OR COALESCE(r.ha_real, 0) <> 0
        OR COALESCE(m.receita_meta, 0) <> 0
        OR COALESCE(pj.receita_proj, 0) <> 0
        OR COALESCE(r.receita_real, 0) <> 0
    ORDER BY pf.programa
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [dict(r) for r in rows]

@router.get("/uo/list")
async def uo_list(
    request: Request,
    ano: int = 2026,
    subregioes: str | None = None,
):
    pool = request.app.state.pool

    params = [ano]
    filtro_sub = ""

    if subregioes:
        ids = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
        if ids:
            filtro_sub = f" AND s.codigo = ANY(${len(params)+1}::int[])"
            params.append(ids)

    sql = f"""
    SELECT DISTINCT
        u.codigo,
        u.nome
    FROM planejamento_staging ps
    JOIN uo u
    ON u.codigo = CASE
        WHEN NULLIF(TRIM(ps.cod_uo_raw), '') IS NULL THEN NULL
        ELSE CAST(REGEXP_REPLACE(TRIM(ps.cod_uo_raw), '\.0+$', '') AS int)
        END
    LEFT JOIN subregioes s
    ON s.codigo = u.cod_subregiao
    WHERE ps.lote_id = (
        SELECT id
        FROM planejamento_import_lotes
        WHERE ano_referencia = $1
        AND status_processamento IN ('importado', 'processado')
        ORDER BY id DESC
        LIMIT 1
    )
    AND ps.flag_valida = TRUE
    AND u.codigo IS NOT NULL
    {filtro_sub}
    ORDER BY u.nome
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [dict(r) for r in rows]

@router.get("/uo/subregioes")
async def uo_subregioes(
    request: Request,
    uos: str
):
    pool = request.app.state.pool

    ids_uo = [int(x) for x in str(uos).split(",") if x.strip().isdigit()]
    if not ids_uo:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT cod_subregiao
            FROM uo
            WHERE codigo = ANY($1::int[])
              AND cod_subregiao IS NOT NULL
            ORDER BY cod_subregiao
            """,
            ids_uo
        )

    return [r["cod_subregiao"] for r in rows]

@router.get("/unidades/summary")
async def unidades_summary(
    request: Request,
    ano: int = 2026,
    mes: int = 1,
    subregioes: str | None = None,
    uos: str | None = None,
):
    pool = request.app.state.pool

    params = [ano, mes]
    filtros_planejamento = []
    filtros_realizado = []

    if subregioes:
        ids_sub = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
        if ids_sub:
            filtros_realizado.append(f"s.codigo = ANY(${len(params)+1}::int[])")
            filtros_planejamento.append(
                f"UPPER(TRIM(ps.subregiao)) IN (SELECT UPPER(TRIM(nome)) FROM subregioes WHERE codigo = ANY(${len(params)+1}::int[]))"
            )
            params.append(ids_sub)

    if uos:
        ids_uo = [int(x) for x in uos.split(",") if x.strip().isdigit()]
        if ids_uo:
            filtros_realizado.append(f"u.codigo = ANY(${len(params)+1}::int[])")
            filtros_planejamento.append(f"u.codigo = ANY(${len(params)+1}::int[])")
            params.append(ids_uo)

    where_extra_planejamento = ""
    if filtros_planejamento:
        where_extra_planejamento = " AND " + " AND ".join(filtros_planejamento)

    where_extra_realizado = ""
    if filtros_realizado:
        where_extra_realizado = " AND " + " AND ".join(filtros_realizado)

    sql = f"""
    WITH planejamento AS (
        SELECT

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'META'
                 AND UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS')
                THEN CASE $2::int
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
            END), 0) AS mat_meta,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'PROJETADO'
                 AND UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS')
                THEN CASE $2::int
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
            END), 0) AS mat_proj,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'META'
                 AND UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                THEN CASE $2::int
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
            END), 0) AS ha_meta,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'PROJETADO'
                 AND UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                THEN CASE $2::int
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
            END), 0) AS ha_proj,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'META'
                 AND UPPER(TRIM(ps.conta)) IN ('RECEITA', 'RECEITAS', 'RECEITAS CORRENTES')
                THEN CASE $2::int
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
            END), 0) AS rec_meta,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'PROJETADO'
                 AND UPPER(TRIM(ps.conta)) IN ('RECEITA', 'RECEITAS', 'RECEITAS CORRENTES')
                THEN CASE $2::int
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
            END), 0) AS rec_proj

        FROM planejamento_staging ps
        LEFT JOIN uo u
          ON u.codigo = CASE
              WHEN NULLIF(TRIM(ps.cod_uo_raw), '') IS NULL THEN NULL
              ELSE CAST(REGEXP_REPLACE(TRIM(ps.cod_uo_raw), '\.0+$', '') AS int)
             END
        WHERE ps.lote_id = (
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento IN ('importado', 'processado')
            ORDER BY id DESC
            LIMIT 1
        )
          AND ps.flag_valida = TRUE
          {where_extra_planejamento}
    ),
    realizado AS (
        SELECT
            COALESCE(SUM(r.matriculas_real), 0) AS mat_real,
            COALESCE(SUM(r.ha_real), 0) AS ha_real,
            COALESCE(SUM(r.receita_real), 0) AS rec_real
        FROM ofertas_programas o
        JOIN uo u
          ON u.codigo = o.cod_uo
        LEFT JOIN subregioes s
          ON s.codigo = u.cod_subregiao
        LEFT JOIN realizado_programas r
          ON r.cod_oferta = o.codigo
         AND r.ano = $1
         AND r.mes = $2
        WHERE o.ano = $1
          {where_extra_realizado}
    )
    SELECT
        p.mat_meta,
        p.mat_proj,
        r.mat_real,
        p.ha_meta,
        p.ha_proj,
        r.ha_real,
        p.rec_meta,
        p.rec_proj,
        r.rec_real
    FROM planejamento p
    CROSS JOIN realizado r
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *params)

    d = dict(row or {})

    return {
        "matriculas": {
            "meta": float(d.get("mat_meta") or 0),
            "projetado": float(d.get("mat_proj") or 0),
            "realizado": float(d.get("mat_real") or 0),
        },
        "hora_aluno": {
            "meta": float(d.get("ha_meta") or 0),
            "projetado": float(d.get("ha_proj") or 0),
            "realizado": float(d.get("ha_real") or 0),
        },
        "receita": {
            "meta": float(d.get("rec_meta") or 0),
            "projetado": float(d.get("rec_proj") or 0),
            "realizado": float(d.get("rec_real") or 0),
        },
    }

@router.get("/unidades/tabela")
async def unidades_tabela(
    request: Request,
    ano: int = 2026,
    meses: str | None = None,
    subregioes: str | None = None,
    uos: str | None = None,
):
    pool = request.app.state.pool

    ids_meses = [int(x) for x in (meses or "").split(",") if x.strip().isdigit()]
    if not ids_meses:
        ids_meses = list(range(1, 13))

    params = [ano, ids_meses]
    filtros_planejamento = []
    filtros_realizado = []

    if subregioes:
        ids_sub = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
        if ids_sub:
            filtros_realizado.append(f"s.codigo = ANY(${len(params)+1}::int[])")
            filtros_planejamento.append(f"UPPER(TRIM(ps.subregiao)) IN (SELECT UPPER(TRIM(nome)) FROM subregioes WHERE codigo = ANY(${len(params)+1}::int[]))")
            params.append(ids_sub)

    if uos:
        ids_uo = [int(x) for x in uos.split(",") if x.strip().isdigit()]
        if ids_uo:
            filtros_realizado.append(f"u.codigo = ANY(${len(params)+1}::int[])")
            filtros_planejamento.append(f"u.codigo = ANY(${len(params)+1}::int[])")
            params.append(ids_uo)

    where_extra_planejamento = ""
    if filtros_planejamento:
        where_extra_planejamento = " AND " + " AND ".join(filtros_planejamento)

    where_extra_realizado = ""
    if filtros_realizado:
        where_extra_realizado = " AND " + " AND ".join(filtros_realizado)

    sql = f"""
    WITH planejamento AS (
        SELECT
            COALESCE(u.nome, NULLIF(TRIM(ps.desc_uo_raw), ''), '—') AS uo,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'META'
                AND UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS')
                THEN (
                    CASE WHEN 1 = ANY($2::int[]) THEN COALESCE(ps.jan, 0) ELSE 0 END +
                    CASE WHEN 2 = ANY($2::int[]) THEN COALESCE(ps.fev, 0) ELSE 0 END +
                    CASE WHEN 3 = ANY($2::int[]) THEN COALESCE(ps.mar, 0) ELSE 0 END +
                    CASE WHEN 4 = ANY($2::int[]) THEN COALESCE(ps.abr, 0) ELSE 0 END +
                    CASE WHEN 5 = ANY($2::int[]) THEN COALESCE(ps.mai, 0) ELSE 0 END +
                    CASE WHEN 6 = ANY($2::int[]) THEN COALESCE(ps.jun, 0) ELSE 0 END +
                    CASE WHEN 7 = ANY($2::int[]) THEN COALESCE(ps.jul, 0) ELSE 0 END +
                    CASE WHEN 8 = ANY($2::int[]) THEN COALESCE(ps.ago, 0) ELSE 0 END +
                    CASE WHEN 9 = ANY($2::int[]) THEN COALESCE(ps.set_, 0) ELSE 0 END +
                    CASE WHEN 10 = ANY($2::int[]) THEN COALESCE(ps.out_, 0) ELSE 0 END +
                    CASE WHEN 11 = ANY($2::int[]) THEN COALESCE(ps.nov, 0) ELSE 0 END +
                    CASE WHEN 12 = ANY($2::int[]) THEN COALESCE(ps.dez, 0) ELSE 0 END
                )
                ELSE 0
            END), 0) AS mat_meta,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'META'
                AND UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS')
                THEN (
                    CASE WHEN 1 = ANY($2::int[]) THEN COALESCE(ps.jan, 0) ELSE 0 END +
                    CASE WHEN 2 = ANY($2::int[]) THEN COALESCE(ps.fev, 0) ELSE 0 END +
                    CASE WHEN 3 = ANY($2::int[]) THEN COALESCE(ps.mar, 0) ELSE 0 END +
                    CASE WHEN 4 = ANY($2::int[]) THEN COALESCE(ps.abr, 0) ELSE 0 END +
                    CASE WHEN 5 = ANY($2::int[]) THEN COALESCE(ps.mai, 0) ELSE 0 END +
                    CASE WHEN 6 = ANY($2::int[]) THEN COALESCE(ps.jun, 0) ELSE 0 END +
                    CASE WHEN 7 = ANY($2::int[]) THEN COALESCE(ps.jul, 0) ELSE 0 END +
                    CASE WHEN 8 = ANY($2::int[]) THEN COALESCE(ps.ago, 0) ELSE 0 END +
                    CASE WHEN 9 = ANY($2::int[]) THEN COALESCE(ps.set_, 0) ELSE 0 END +
                    CASE WHEN 10 = ANY($2::int[]) THEN COALESCE(ps.out_, 0) ELSE 0 END +
                    CASE WHEN 11 = ANY($2::int[]) THEN COALESCE(ps.nov, 0) ELSE 0 END +
                    CASE WHEN 12 = ANY($2::int[]) THEN COALESCE(ps.dez, 0) ELSE 0 END
                )
                ELSE 0
            END), 0) AS mat_proj,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'META'
                AND UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                THEN (
                    CASE WHEN 1 = ANY($2::int[]) THEN COALESCE(ps.jan, 0) ELSE 0 END +
                    CASE WHEN 2 = ANY($2::int[]) THEN COALESCE(ps.fev, 0) ELSE 0 END +
                    CASE WHEN 3 = ANY($2::int[]) THEN COALESCE(ps.mar, 0) ELSE 0 END +
                    CASE WHEN 4 = ANY($2::int[]) THEN COALESCE(ps.abr, 0) ELSE 0 END +
                    CASE WHEN 5 = ANY($2::int[]) THEN COALESCE(ps.mai, 0) ELSE 0 END +
                    CASE WHEN 6 = ANY($2::int[]) THEN COALESCE(ps.jun, 0) ELSE 0 END +
                    CASE WHEN 7 = ANY($2::int[]) THEN COALESCE(ps.jul, 0) ELSE 0 END +
                    CASE WHEN 8 = ANY($2::int[]) THEN COALESCE(ps.ago, 0) ELSE 0 END +
                    CASE WHEN 9 = ANY($2::int[]) THEN COALESCE(ps.set_, 0) ELSE 0 END +
                    CASE WHEN 10 = ANY($2::int[]) THEN COALESCE(ps.out_, 0) ELSE 0 END +
                    CASE WHEN 11 = ANY($2::int[]) THEN COALESCE(ps.nov, 0) ELSE 0 END +
                    CASE WHEN 12 = ANY($2::int[]) THEN COALESCE(ps.dez, 0) ELSE 0 END
                )
                ELSE 0
            END), 0) AS ha_meta,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'PROJETADO'
                AND UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                THEN (
                    CASE WHEN 1 = ANY($2::int[]) THEN COALESCE(ps.jan, 0) ELSE 0 END +
                    CASE WHEN 2 = ANY($2::int[]) THEN COALESCE(ps.fev, 0) ELSE 0 END +
                    CASE WHEN 3 = ANY($2::int[]) THEN COALESCE(ps.mar, 0) ELSE 0 END +
                    CASE WHEN 4 = ANY($2::int[]) THEN COALESCE(ps.abr, 0) ELSE 0 END +
                    CASE WHEN 5 = ANY($2::int[]) THEN COALESCE(ps.mai, 0) ELSE 0 END +
                    CASE WHEN 6 = ANY($2::int[]) THEN COALESCE(ps.jun, 0) ELSE 0 END +
                    CASE WHEN 7 = ANY($2::int[]) THEN COALESCE(ps.jul, 0) ELSE 0 END +
                    CASE WHEN 8 = ANY($2::int[]) THEN COALESCE(ps.ago, 0) ELSE 0 END +
                    CASE WHEN 9 = ANY($2::int[]) THEN COALESCE(ps.set_, 0) ELSE 0 END +
                    CASE WHEN 10 = ANY($2::int[]) THEN COALESCE(ps.out_, 0) ELSE 0 END +
                    CASE WHEN 11 = ANY($2::int[]) THEN COALESCE(ps.nov, 0) ELSE 0 END +
                    CASE WHEN 12 = ANY($2::int[]) THEN COALESCE(ps.dez, 0) ELSE 0 END
                )
                ELSE 0
            END), 0) AS ha_proj,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'META'
                AND UPPER(TRIM(ps.conta)) IN ('RECEITA', 'RECEITAS', 'RECEITAS CORRENTES')
                THEN (
                    CASE WHEN 1 = ANY($2::int[]) THEN COALESCE(ps.jan, 0) ELSE 0 END +
                    CASE WHEN 2 = ANY($2::int[]) THEN COALESCE(ps.fev, 0) ELSE 0 END +
                    CASE WHEN 3 = ANY($2::int[]) THEN COALESCE(ps.mar, 0) ELSE 0 END +
                    CASE WHEN 4 = ANY($2::int[]) THEN COALESCE(ps.abr, 0) ELSE 0 END +
                    CASE WHEN 5 = ANY($2::int[]) THEN COALESCE(ps.mai, 0) ELSE 0 END +
                    CASE WHEN 6 = ANY($2::int[]) THEN COALESCE(ps.jun, 0) ELSE 0 END +
                    CASE WHEN 7 = ANY($2::int[]) THEN COALESCE(ps.jul, 0) ELSE 0 END +
                    CASE WHEN 8 = ANY($2::int[]) THEN COALESCE(ps.ago, 0) ELSE 0 END +
                    CASE WHEN 9 = ANY($2::int[]) THEN COALESCE(ps.set_, 0) ELSE 0 END +
                    CASE WHEN 10 = ANY($2::int[]) THEN COALESCE(ps.out_, 0) ELSE 0 END +
                    CASE WHEN 11 = ANY($2::int[]) THEN COALESCE(ps.nov, 0) ELSE 0 END +
                    CASE WHEN 12 = ANY($2::int[]) THEN COALESCE(ps.dez, 0) ELSE 0 END
                )
                ELSE 0
            END), 0) AS rec_meta,

            COALESCE(SUM(CASE
                WHEN UPPER(TRIM(ps.tipo)) = 'PROJETADO'
                AND UPPER(TRIM(ps.conta)) IN ('RECEITA', 'RECEITAS', 'RECEITAS CORRENTES')
                THEN (
                    CASE WHEN 1 = ANY($2::int[]) THEN COALESCE(ps.jan, 0) ELSE 0 END +
                    CASE WHEN 2 = ANY($2::int[]) THEN COALESCE(ps.fev, 0) ELSE 0 END +
                    CASE WHEN 3 = ANY($2::int[]) THEN COALESCE(ps.mar, 0) ELSE 0 END +
                    CASE WHEN 4 = ANY($2::int[]) THEN COALESCE(ps.abr, 0) ELSE 0 END +
                    CASE WHEN 5 = ANY($2::int[]) THEN COALESCE(ps.mai, 0) ELSE 0 END +
                    CASE WHEN 6 = ANY($2::int[]) THEN COALESCE(ps.jun, 0) ELSE 0 END +
                    CASE WHEN 7 = ANY($2::int[]) THEN COALESCE(ps.jul, 0) ELSE 0 END +
                    CASE WHEN 8 = ANY($2::int[]) THEN COALESCE(ps.ago, 0) ELSE 0 END +
                    CASE WHEN 9 = ANY($2::int[]) THEN COALESCE(ps.set_, 0) ELSE 0 END +
                    CASE WHEN 10 = ANY($2::int[]) THEN COALESCE(ps.out_, 0) ELSE 0 END +
                    CASE WHEN 11 = ANY($2::int[]) THEN COALESCE(ps.nov, 0) ELSE 0 END +
                    CASE WHEN 12 = ANY($2::int[]) THEN COALESCE(ps.dez, 0) ELSE 0 END
                )
                ELSE 0
            END), 0) AS rec_proj

        FROM planejamento_staging ps
        LEFT JOIN uo u
          ON u.codigo = CASE
                WHEN NULLIF(TRIM(ps.cod_uo_raw), '') IS NULL THEN NULL
                ELSE CAST(REGEXP_REPLACE(TRIM(ps.cod_uo_raw), '\.0+$', '') AS int)
              END
        LEFT JOIN subregioes s
        ON s.codigo = u.cod_subregiao
        WHERE ps.lote_id = (
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
            AND status_processamento IN ('importado', 'processado')
            ORDER BY id DESC
            LIMIT 1
        )
        AND ps.flag_valida = TRUE
        {where_extra_planejamento}
        GROUP BY COALESCE(u.nome, NULLIF(TRIM(ps.desc_uo_raw), ''), '—')
    ),
    realizado AS (
        SELECT
            COALESCE(mat.uo, rec.uo) AS uo,
            COALESCE(mat.mat_real, 0) AS mat_real,
            COALESCE(ha.ha_real, 0) AS ha_real,
            COALESCE(rec.rec_real, 0) AS rec_real
        FROM (
            SELECT
                u.nome AS uo,
                COALESCE(SUM(r.matriculas_real), 0) AS mat_real
            FROM realizado_programas r
            JOIN ofertas_programas o
            ON o.codigo = r.cod_oferta
            JOIN uo u
            ON u.codigo = o.cod_uo
            LEFT JOIN subregioes s
            ON s.codigo = u.cod_subregiao
            WHERE r.ano = $1
            AND r.mes = ANY($2::int[])
            {where_extra_realizado}
            GROUP BY u.nome
        ) mat
        FULL OUTER JOIN (
            SELECT
                u.nome AS uo,
                COALESCE(SUM(r.ha_real), 0) AS ha_real
            FROM realizado_programas r
            JOIN ofertas_programas o
            ON o.codigo = r.cod_oferta
            JOIN uo u
            ON u.codigo = o.cod_uo
            LEFT JOIN subregioes s
            ON s.codigo = u.cod_subregiao
            WHERE r.ano = $1
            AND r.mes = ANY($2::int[])
            {where_extra_realizado}
            GROUP BY u.nome
        ) ha
        ON ha.uo = mat.uo
        FULL OUTER JOIN (
            SELECT
                u.nome AS uo,
                COALESCE(SUM(r.receita_real), 0) AS rec_real
            FROM realizado_programas r
            JOIN ofertas_programas o
            ON o.codigo = r.cod_oferta
            JOIN uo u
            ON u.codigo = o.cod_uo
            LEFT JOIN subregioes s
            ON s.codigo = u.cod_subregiao
            WHERE r.ano = $1
            AND r.mes = ANY($2::int[])
            {where_extra_realizado}
            GROUP BY u.nome
        ) rec
        ON rec.uo = COALESCE(mat.uo, ha.uo)
    )
    SELECT
        COALESCE(p.uo, r.uo) AS uo,
        COALESCE(p.mat_meta, 0) AS mat_meta,
        COALESCE(p.mat_proj, 0) AS mat_proj,
        COALESCE(r.mat_real, 0) AS mat_real,
        COALESCE(p.ha_meta, 0) AS ha_meta,
        COALESCE(p.ha_proj, 0) AS ha_proj,
        COALESCE(r.ha_real, 0) AS ha_real,
        COALESCE(p.rec_meta, 0) AS rec_meta,
        COALESCE(p.rec_proj, 0) AS rec_proj,
        COALESCE(r.rec_real, 0) AS rec_real
    FROM planejamento p
    FULL OUTER JOIN realizado r
    ON r.uo = p.uo
    WHERE
        COALESCE(p.mat_meta, 0) <> 0
    OR COALESCE(p.mat_proj, 0) <> 0
    OR COALESCE(r.mat_real, 0) <> 0
    OR COALESCE(p.ha_meta, 0) <> 0
    OR COALESCE(p.ha_proj, 0) <> 0
    OR COALESCE(r.ha_real, 0) <> 0
    OR COALESCE(p.rec_meta, 0) <> 0
    OR COALESCE(p.rec_proj, 0) <> 0
    OR COALESCE(r.rec_real, 0) <> 0
    ORDER BY 1
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    resultado = []
    for row in rows:
        d = dict(row)
        for k in ("mat_meta", "mat_proj", "mat_real", "ha_meta", "ha_proj", "ha_real", "rec_meta", "rec_proj", "rec_real"):
            d[k] = float(d[k] or 0)
        resultado.append(d)

    return resultado

@router.post("/importacoes/matriculas")
async def importar_relatorio_geral_matriculas(request: Request, arquivo: UploadFile = File(...)):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo não informado.")

    nome = arquivo.filename.lower()
    if not (nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Envie um arquivo Excel .xlsx ou .xls.")

    conteudo = await arquivo.read()
    hash_arquivo = hashlib.sha256(conteudo).hexdigest()

    try:
        df = pd.read_excel(io.BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler Excel: {e}")

    df.columns = [str(c).strip().upper() for c in df.columns]

    faltantes = [c for c in COLUNAS_OBRIGATORIAS_MATRICULAS if c not in df.columns]
    if faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"Colunas obrigatórias não encontradas: {faltantes}"
        )

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote = await conn.fetchrow(
                """
                INSERT INTO sge_import_lotes (
                    tipo_arquivo, nome_arquivo, hash_arquivo, status_processamento
                )
                VALUES ($1, $2, $3, 'importado')
                RETURNING id
                """,
                "relatorio_geral_matriculas",
                arquivo.filename,
                hash_arquivo,
            )
            lote_id = lote["id"]

            registros = []
            total_validas = 0
            total_invalidas = 0

            for idx, row in df.iterrows():
                payload = {
                    "codturma": norm_text(row.get("CODTURMA")),
                    "ra": norm_text(row.get("RA")),
                    "dtmatricula": norm_date(row.get("DTMATRICULA")),
                    "status_pletivo": norm_upper(row.get("STATUS_PLETIVO")),
                    "status_curso": norm_upper(row.get("STATUS_CURSO")),
                    "condicao_aluno": norm_text(row.get("SENAI_CONDICAO_ALUNO_CURSO")),
                }

                erros = []

                if not payload["codturma"]:
                    erros.append("CODTURMA vazio")

                if not payload["ra"]:
                    erros.append("RA vazio")
                
                if not payload["dtmatricula"]:
                    erros.append("DTMATRICULA vazia ou inválida")

                flag_valida = len(erros) == 0

                if flag_valida:
                    total_validas += 1
                else:
                    total_invalidas += 1

                registros.append((
                    lote_id,
                    idx + 2,
                    hash_linha(payload),
                    payload["codturma"],
                    payload["ra"],
                    payload["dtmatricula"],
                    payload["status_pletivo"],
                    payload["status_curso"],
                    payload["condicao_aluno"],
                    flag_valida,
                    "; ".join(erros) if erros else None,
                ))

            await conn.executemany(
                """
                INSERT INTO sge_matriculas_staging (
                    lote_id, linha_numero, hash_linha,
                    codturma, ra, dtmatricula, status_pletivo, status_curso, condicao_aluno,
                    flag_valida, erro_validacao
                )
                VALUES (
                    $1, $2, $3,
                    $4, $5, $6, $7, $8, $9,
                    $10, $11
                )
                """,
                registros
            )

            await conn.execute(
                """
                UPDATE sge_import_lotes
                SET total_linhas = $2,
                    total_validas = $3,
                    total_invalidas = $4
                WHERE id = $1
                """,
                lote_id, len(registros), total_validas, total_invalidas
            )
        return {
            "ok": True,
            "lote_id": lote_id,
            "arquivo": arquivo.filename,
            "linhas_importadas": len(registros),
            "validas": total_validas,
            "invalidas": total_invalidas,
        }
    
@router.post("/importacoes/matriculas/processar/{lote_id}")
async def processar_lote_matriculas(request: Request, lote_id: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote = await conn.fetchrow(
                """
                SELECT *
                FROM sge_import_lotes
                WHERE id = $1
                  AND tipo_arquivo = 'relatorio_geral_matriculas'
                """,
                lote_id
            )

            if not lote:
                raise HTTPException(status_code=404, detail="Lote de matrículas não encontrado.")

            await conn.execute(
                """
                DELETE FROM sge_matriculas_snapshot
                WHERE lote_id = $1
                """,
                lote_id
            )

            await conn.execute(
                """
                UPDATE sge_import_lotes
                SET status_processamento = 'processando'
                WHERE id = $1
                """,
                lote_id
            )

            rows = await conn.fetch(
                """
                SELECT codturma, ra, status_pletivo
                FROM sge_matriculas_staging
                WHERE lote_id = $1
                  AND flag_valida = TRUE
                ORDER BY id
                """,
                lote_id
            )

            if not rows:
                raise HTTPException(status_code=400, detail="Lote sem linhas válidas para processar.")

            turmas = {}
            chaves_vistas = set()
            duplicados = 0

            for r in rows:
                cod_turma = (r["codturma"] or "").strip()
                ra = (r["ra"] or "").strip()
                status = (r["status_pletivo"] or "").strip().upper()

                if not cod_turma or not ra:
                    continue

                chave = (cod_turma, ra)

                if chave in chaves_vistas:
                    duplicados += 1
                    if cod_turma not in turmas:
                        turmas[cod_turma] = {
                            "total_alunos": 0,
                            "qtd_matriculado": 0,
                            "qtd_pre_matriculado": 0,
                            "qtd_cancelado": 0,
                            "qtd_desistente": 0,
                            "qtd_evadido": 0,
                            "qtd_duplicados": 0,
                        }
                    turmas[cod_turma]["qtd_duplicados"] += 1
                    continue

                chaves_vistas.add(chave)

                if cod_turma not in turmas:
                    turmas[cod_turma] = {
                        "total_alunos": 0,
                        "qtd_matriculado": 0,
                        "qtd_pre_matriculado": 0,
                        "qtd_cancelado": 0,
                        "qtd_desistente": 0,
                        "qtd_evadido": 0,
                        "qtd_duplicados": 0,
                    }

                turma = turmas[cod_turma]
                turma["total_alunos"] += 1

                if status == "MATRICULADO":
                    turma["qtd_matriculado"] += 1
                elif status in ("PRE_MATRICULADO", "PRÉ-MATRICULADO"):
                    turma["qtd_pre_matriculado"] += 1
                elif status == "CANCELADO":
                    turma["qtd_cancelado"] += 1
                elif status == "DESISTENTE":
                    turma["qtd_desistente"] += 1
                elif status == "EVADIDO":
                    turma["qtd_evadido"] += 1
                else:
                    # opção A: ignorar status fora do padrão
                    pass

            registros = []

            for cod_turma, resumo in turmas.items():
                hash_resumo = hash_linha({
                    "cod_turma": cod_turma,
                    "total_alunos": resumo["total_alunos"],
                    "qtd_matriculado": resumo["qtd_matriculado"],
                    "qtd_pre_matriculado": resumo["qtd_pre_matriculado"],
                    "qtd_cancelado": resumo["qtd_cancelado"],
                    "qtd_desistente": resumo["qtd_desistente"],
                    "qtd_evadido": resumo["qtd_evadido"],
                    "qtd_duplicados": resumo["qtd_duplicados"],
                })

                registros.append((
                    lote_id,
                    cod_turma,
                    resumo["total_alunos"],
                    resumo["qtd_matriculado"],
                    resumo["qtd_pre_matriculado"],
                    resumo["qtd_cancelado"],
                    resumo["qtd_desistente"],
                    resumo["qtd_evadido"],
                    resumo["qtd_duplicados"],
                    hash_resumo,
                ))

            if registros:
                await conn.executemany(
                    """
                    INSERT INTO sge_matriculas_snapshot (
                        lote_id, cod_turma,
                        total_alunos,
                        qtd_matriculado, qtd_pre_matriculado, qtd_cancelado,
                        qtd_desistente, qtd_evadido,
                        qtd_duplicados, hash_resumo
                    )
                    VALUES (
                        $1, $2,
                        $3,
                        $4, $5, $6,
                        $7, $8,
                        $9, $10
                    )
                    """,
                    registros
                )

            await conn.execute(
                """
                UPDATE sge_import_lotes
                SET status_processamento = 'processado',
                    data_processamento = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                lote_id
            )

            anos_lote = await conn.fetch(
                """
                SELECT DISTINCT EXTRACT(YEAR FROM dtmatricula)::int AS ano
                FROM sge_matriculas_staging
                WHERE lote_id = $1
                  AND flag_valida = TRUE
                  AND dtmatricula IS NOT NULL
                ORDER BY 1
                """,
                lote_id
            )

            anos_processados = [r["ano"] for r in anos_lote if r["ano"] is not None]

            for ano in anos_processados:
                await conn.execute(
                    """
                    DELETE FROM realizado_programas
                    WHERE ano = $1
                    """,
                    ano
                )

                await conn.execute(
                    """
                    INSERT INTO realizado_programas (
                        cod_programa,
                        ano,
                        mes,
                        matriculas_real
                    )
                    SELECT
                        t.cod_programa,
                        EXTRACT(YEAR FROM ms.dtmatricula)::int AS ano,
                        EXTRACT(MONTH FROM ms.dtmatricula)::int AS mes,
                        COUNT(*)::numeric AS matriculas_real
                    FROM sge_matriculas_staging ms
                    JOIN turmas t
                        ON t.codigo_sge = ms.codturma
                    WHERE ms.flag_valida = TRUE
                        AND ms.dtmatricula IS NOT NULL
                        AND EXTRACT(YEAR FROM ms.dtmatricula)::int = $1
                        AND UPPER(COALESCE(ms.status_pletivo, '')) = 'MATRICULADO'
                        AND t.cod_programa IS NOT NULL
                    GROUP BY
                        t.cod_programa,
                        EXTRACT(YEAR FROM ms.dtmatricula),
                        EXTRACT(MONTH FROM ms.dtmatricula)
                    ON CONFLICT (cod_programa, ano, mes)
                    DO UPDATE SET
                        matriculas_real = EXCLUDED.matriculas_real
                    """,
                    ano
                )

    return {
        "ok": True,
        "lote_id": lote_id,
        "turmas_processadas": len(registros),
        "linhas_lidas": len(rows),
        "duplicados_encontrados": duplicados,
        "anos_recalculados": anos_processados,
    }

@router.post("/importacoes/matriculas/conferir/{lote_matriculas_id}")
async def conferir_lote_matriculas(request: Request, lote_matriculas_id: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote_matriculas = await conn.fetchrow(
                """
                SELECT *
                FROM sge_import_lotes
                WHERE id = $1
                  AND tipo_arquivo = 'relatorio_geral_matriculas'
                """,
                lote_matriculas_id
            )

            if not lote_matriculas:
                raise HTTPException(status_code=404, detail="Lote de matrículas não encontrado.")

            lote_turmas = await conn.fetchrow(
                """
                SELECT id
                FROM sge_import_lotes
                WHERE tipo_arquivo = 'relatorio_geral_turmas'
                  AND status_processamento = 'processado'
                ORDER BY id DESC
                LIMIT 1
                """
            )

            if not lote_turmas:
                raise HTTPException(status_code=404, detail="Nenhum lote de turmas processado encontrado.")

            lote_turmas_id = lote_turmas["id"]

            await conn.execute(
                """
                DELETE FROM sge_matriculas_conferencia
                WHERE lote_matriculas_id = $1
                  AND lote_turmas_id = $2
                """,
                lote_matriculas_id,
                lote_turmas_id
            )

            rows_matriculas = await conn.fetch(
                """
                SELECT
                    cod_turma,
                    total_alunos,
                    qtd_matriculado,
                    qtd_pre_matriculado,
                    qtd_cancelado,
                    qtd_desistente,
                    qtd_evadido
                FROM sge_matriculas_snapshot
                WHERE lote_id = $1
                """,
                lote_matriculas_id
            )

            rows_turmas = await conn.fetch(
                """
                SELECT
                    t.codigo_sge AS cod_turma,
                    s.qtd_total AS total_alunos,
                    s.qtd_matriculado,
                    s.qtd_pre_matriculado,
                    s.qtd_cancelado,
                    s.qtd_desistente,
                    s.qtd_evadido
                FROM sge_turmas_snapshot s
                JOIN turmas t
                  ON t.codigo = s.cod_turma
                WHERE s.lote_id = $1
                """,
                lote_turmas_id
            )

            mapa_matriculas = {r["cod_turma"]: dict(r) for r in rows_matriculas}
            mapa_turmas = {r["cod_turma"]: dict(r) for r in rows_turmas}

            todas_turmas = sorted(set(mapa_matriculas.keys()) | set(mapa_turmas.keys()))

            registros = []
            ok = 0
            divergentes = 0
            ausente_no_matricula = 0
            ausente_no_geral = 0

            for cod_turma in todas_turmas:
                mat = mapa_matriculas.get(cod_turma)
                ger = mapa_turmas.get(cod_turma)

                campos_divergentes = {}

                if ger and not mat:
                    tipo = "ausente_no_matricula"
                    ausente_no_matricula += 1
                elif mat and not ger:
                    tipo = "ausente_no_geral"
                    ausente_no_geral += 1
                else:
                    pares = [
                        ("total", ger["total_alunos"], mat["total_alunos"]),
                        ("matriculado", ger["qtd_matriculado"], mat["qtd_matriculado"]),
                        ("pre_matriculado", ger["qtd_pre_matriculado"], mat["qtd_pre_matriculado"]),
                        ("cancelado", ger["qtd_cancelado"], mat["qtd_cancelado"]),
                        ("desistente", ger["qtd_desistente"], mat["qtd_desistente"]),
                        ("evadido", ger["qtd_evadido"], mat["qtd_evadido"]),
                    ]

                    for campo, v_geral, v_mat in pares:
                        if (v_geral or 0) != (v_mat or 0):
                            campos_divergentes[campo] = {
                                "geral": v_geral or 0,
                                "matriculas": v_mat or 0
                            }

                    if campos_divergentes:
                        tipo = "divergente"
                        divergentes += 1
                    else:
                        tipo = "ok"
                        ok += 1

                payload_hash = {
                    "cod_turma": cod_turma,
                    "tipo": tipo,
                    "campos_divergentes": campos_divergentes,
                    "ger": ger,
                    "mat": mat,
                }

                registros.append((
                    lote_matriculas_id,
                    lote_turmas_id,
                    cod_turma,
                    tipo,

                    ger["total_alunos"] if ger else None,
                    mat["total_alunos"] if mat else None,

                    ger["qtd_matriculado"] if ger else None,
                    mat["qtd_matriculado"] if mat else None,

                    ger["qtd_pre_matriculado"] if ger else None,
                    mat["qtd_pre_matriculado"] if mat else None,

                    ger["qtd_cancelado"] if ger else None,
                    mat["qtd_cancelado"] if mat else None,

                    ger["qtd_desistente"] if ger else None,
                    mat["qtd_desistente"] if mat else None,

                    ger["qtd_evadido"] if ger else None,
                    mat["qtd_evadido"] if mat else None,

                    json.dumps(campos_divergentes, ensure_ascii=False),
                    hash_linha(payload_hash),
                ))

            if registros:
                await conn.executemany(
                    """
                    INSERT INTO sge_matriculas_conferencia (
                        lote_matriculas_id, lote_turmas_id, cod_turma, tipo_conferencia,
                        total_geral, total_matriculas,
                        qtd_matriculado_geral, qtd_matriculado_matriculas,
                        qtd_pre_matriculado_geral, qtd_pre_matriculado_matriculas,
                        qtd_cancelado_geral, qtd_cancelado_matriculas,
                        qtd_desistente_geral, qtd_desistente_matriculas,
                        qtd_evadido_geral, qtd_evadido_matriculas,
                        campos_divergentes, hash_conferencia
                    )
                    VALUES (
                        $1, $2, $3, $4,
                        $5, $6,
                        $7, $8,
                        $9, $10,
                        $11, $12,
                        $13, $14,
                        $15, $16,
                        $17::jsonb, $18
                    )
                    """,
                    registros
                )

    return {
        "ok": True,
        "lote_matriculas_id": lote_matriculas_id,
        "lote_turmas_id": lote_turmas_id,
        "total_turmas_avaliadas": len(registros),
        "ok_count": ok,
        "divergentes": divergentes,
        "ausente_no_matricula": ausente_no_matricula,
        "ausente_no_geral": ausente_no_geral,
    }

@router.get("/importacoes/matriculas/conferencia/{lote_matriculas_id}")
async def listar_conferencia_matriculas(request: Request, lote_matriculas_id: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                cod_turma,
                tipo_conferencia,
                total_geral,
                total_matriculas,
                qtd_matriculado_geral,
                qtd_matriculado_matriculas,
                qtd_pre_matriculado_geral,
                qtd_pre_matriculado_matriculas,
                qtd_cancelado_geral,
                qtd_cancelado_matriculas,
                qtd_desistente_geral,
                qtd_desistente_matriculas,
                qtd_evadido_geral,
                qtd_evadido_matriculas,
                campos_divergentes
            FROM sge_matriculas_conferencia
            WHERE lote_matriculas_id = $1
            ORDER BY
                CASE tipo_conferencia
                    WHEN 'divergente' THEN 1
                    WHEN 'ausente_no_matricula' THEN 2
                    WHEN 'ausente_no_geral' THEN 3
                    WHEN 'ok' THEN 4
                    ELSE 5
                END,
                cod_turma
            LIMIT 3000
            """,
            lote_matriculas_id
        )

    return [dict(r) for r in rows]

@router.post("/importacoes/matriculas/aplicar-divergencia")
async def aplicar_divergencia_matriculas(request: Request, payload: dict):
    pool = request.app.state.pool

    lote_matriculas_id = payload.get("lote_matriculas_id")
    cod_turma = payload.get("cod_turma")

    if not lote_matriculas_id or not cod_turma:
        raise HTTPException(status_code=400, detail="lote_matriculas_id e cod_turma são obrigatórios.")

    async with pool.acquire() as conn:
        async with conn.transaction():
            conf = await conn.fetchrow(
                """
                SELECT *
                FROM sge_matriculas_conferencia
                WHERE lote_matriculas_id = $1
                  AND cod_turma = $2
                LIMIT 1
                """,
                lote_matriculas_id,
                cod_turma
            )

            if not conf:
                raise HTTPException(status_code=404, detail="Conferência não encontrada para a turma.")

            if conf["tipo_conferencia"] != "divergente":
                raise HTTPException(status_code=400, detail="Ação permitida apenas para turmas divergentes.")

            snap_mat = await conn.fetchrow(
                """
                SELECT *
                FROM sge_matriculas_snapshot
                WHERE lote_id = $1
                  AND cod_turma = $2
                LIMIT 1
                """,
                lote_matriculas_id,
                cod_turma
            )

            if not snap_mat:
                raise HTTPException(status_code=404, detail="Snapshot de matrículas não encontrado.")

            turma = await conn.fetchrow(
                """
                SELECT codigo
                FROM turmas
                WHERE codigo_sge = $1
                LIMIT 1
                """,
                cod_turma
            )

            if not turma:
                raise HTTPException(status_code=404, detail="Turma não encontrada na base principal.")

            cod_turma_int = turma["codigo"]

            await conn.execute(
                """
                UPDATE sge_turmas_snapshot
                SET
                    qtd_total = $2,
                    qtd_matriculado = $3,
                    qtd_pre_matriculado = $4,
                    qtd_cancelado = $5,
                    qtd_desistente = $6,
                    qtd_evadido = $7
                WHERE lote_id = $1
                  AND cod_turma = $8
                """,
                conf["lote_turmas_id"],
                snap_mat["total_alunos"],
                snap_mat["qtd_matriculado"],
                snap_mat["qtd_pre_matriculado"],
                snap_mat["qtd_cancelado"],
                snap_mat["qtd_desistente"],
                snap_mat["qtd_evadido"],
                cod_turma_int
            )

            await conn.execute(
                """
                UPDATE sge_matriculas_conferencia
                SET
                    tipo_conferencia = 'ok',
                    campos_divergentes = '{}'::jsonb
                WHERE lote_matriculas_id = $1
                  AND cod_turma = $2
                """,
                lote_matriculas_id,
                cod_turma
            )

    return {
        "ok": True,
        "cod_turma": cod_turma,
        "mensagem": "Divergência aplicada com sucesso."
    }

@router.post("/importacoes/matriculas/aplicar-divergencias-lote")
async def aplicar_divergencias_lote(request: Request, payload: dict):
    pool = request.app.state.pool

    lote_matriculas_id = payload.get("lote_matriculas_id")
    cod_turmas = payload.get("cod_turmas") or []

    if not lote_matriculas_id:
        raise HTTPException(status_code=400, detail="lote_matriculas_id é obrigatório.")

    if not isinstance(cod_turmas, list) or not cod_turmas:
        raise HTTPException(status_code=400, detail="cod_turmas deve ser uma lista com pelo menos uma turma.")

    atualizadas = []
    erros = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for cod_turma in cod_turmas:
                try:
                    conf = await conn.fetchrow(
                        """
                        SELECT *
                        FROM sge_matriculas_conferencia
                        WHERE lote_matriculas_id = $1
                          AND cod_turma = $2
                        LIMIT 1
                        """,
                        lote_matriculas_id,
                        cod_turma
                    )

                    if not conf:
                        erros.append({"cod_turma": cod_turma, "erro": "Conferência não encontrada"})
                        continue

                    if conf["tipo_conferencia"] != "divergente":
                        erros.append({"cod_turma": cod_turma, "erro": "Turma não está divergente"})
                        continue

                    snap_mat = await conn.fetchrow(
                        """
                        SELECT *
                        FROM sge_matriculas_snapshot
                        WHERE lote_id = $1
                          AND cod_turma = $2
                        LIMIT 1
                        """,
                        lote_matriculas_id,
                        cod_turma
                    )

                    if not snap_mat:
                        erros.append({"cod_turma": cod_turma, "erro": "Snapshot de matrículas não encontrado"})
                        continue

                    turma = await conn.fetchrow(
                        """
                        SELECT codigo
                        FROM turmas
                        WHERE codigo_sge = $1
                        LIMIT 1
                        """,
                        cod_turma
                    )

                    if not turma:
                        erros.append({"cod_turma": cod_turma, "erro": "Turma não encontrada"})
                        continue

                    cod_turma_int = turma["codigo"]

                    await conn.execute(
                        """
                        UPDATE sge_turmas_snapshot
                        SET
                            qtd_total = $2,
                            qtd_matriculado = $3,
                            qtd_pre_matriculado = $4,
                            qtd_cancelado = $5,
                            qtd_desistente = $6,
                            qtd_evadido = $7
                        WHERE lote_id = $1
                          AND cod_turma = $8
                        """,
                        conf["lote_turmas_id"],
                        snap_mat["total_alunos"],
                        snap_mat["qtd_matriculado"],
                        snap_mat["qtd_pre_matriculado"],
                        snap_mat["qtd_cancelado"],
                        snap_mat["qtd_desistente"],
                        snap_mat["qtd_evadido"],
                        cod_turma_int
                    )

                    await conn.execute(
                        """
                        UPDATE sge_matriculas_conferencia
                        SET
                            tipo_conferencia = 'ok',
                            campos_divergentes = '{}'::jsonb
                        WHERE lote_matriculas_id = $1
                          AND cod_turma = $2
                        """,
                        lote_matriculas_id,
                        cod_turma
                    )

                    atualizadas.append(cod_turma)

                except Exception as e:
                    erros.append({"cod_turma": cod_turma, "erro": str(e)})

    return {
        "ok": True,
        "lote_matriculas_id": lote_matriculas_id,
        "total_recebidas": len(cod_turmas),
        "total_atualizadas": len(atualizadas),
        "atualizadas": atualizadas,
        "total_erros": len(erros),
        "erros": erros
    }

@router.post("/processamentos/realizado/matriculas/{ano}")
async def recalcular_realizado_matriculas(request: Request, ano: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                DELETE FROM realizado_programas
                WHERE ano = $1
                """,
                ano
            )

            await conn.execute(
                """
                INSERT INTO realizado_programas (
                    cod_oferta,
                    cod_programa,
                    ano,
                    mes,
                    matriculas_real,
                    ha_real,
                    receita_real,
                    despesa_real
                )
                SELECT
                    MIN(op.codigo) AS cod_oferta,
                    t.cod_programa,
                    tmm.ano,
                    tmm.mes,
                    SUM(tmm.matriculados)::numeric AS matriculas_real,
                    0::numeric AS ha_real,
                    0::numeric AS receita_real,
                    0::numeric AS despesa_real
                FROM turmas_movimento_mensal tmm
                JOIN turmas t
                ON t.codigo = tmm.cod_turma
                LEFT JOIN LATERAL (
                    SELECT MIN(op.codigo) AS codigo
                    FROM ofertas_programas op
                    WHERE op.cod_programa = t.cod_programa
                    AND op.ano = tmm.ano
                ) op ON TRUE
                WHERE tmm.ano = $1
                AND t.cod_programa IS NOT NULL
                GROUP BY
                    t.cod_programa,
                    tmm.ano,
                    tmm.mes
                ON CONFLICT (cod_oferta, ano, mes)
                DO UPDATE SET
                    cod_programa = EXCLUDED.cod_programa,
                    matriculas_real = EXCLUDED.matriculas_real,
                    ha_real = EXCLUDED.ha_real,
                    receita_real = EXCLUDED.receita_real,
                    despesa_real = EXCLUDED.despesa_real;
                """,
                ano
            )

    return {
        "ok": True,
        "ano": ano,
        "mensagem": "Realizado de matrículas recalculado com sucesso."
    }

@router.get("/performance/resumo")
async def performance_resumo(
    request: Request,
    ano: int = 2026,
    subregioes: str | None = None
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote_id = await conn.fetchval(
            """
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento = 'processado'
            ORDER BY id DESC
            LIMIT 1
            """,
            ano
        )

        if not lote_id:
            return {
                "matriculas_total": 0,
                "gr_matriculas": 0,
                "gnr_matriculas": 0,
                "pago_matriculas": 0,
                "ha_total": 0,
                "gr_ha": 0,
                "gnr_ha": 0,
                "pago_ha": 0,
                "receita_total": 0,
                "gr_receita": 0,
                "gnr_receita": 0,
                "pago_receita": 0,
                "gr_matriculas_pct": 0,
                "gnr_matriculas_pct": 0,
                "pago_matriculas_pct": 0,
                "gr_ha_pct": 0,
                "gnr_ha_pct": 0,
                "pago_ha_pct": 0,
                "gr_receita_pct": 0,
                "gnr_receita_pct": 0,
                "pago_receita_pct": 0,
            }

        params = [lote_id]
        filtro_sub = ""

        if subregioes:
            ids = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
            if ids:
                filtro_sub = f" AND s.codigo = ANY(${len(params)+1}::int[])"
                params.append(ids)

        sql = f"""
        WITH base AS (
            SELECT
                UPPER(TRIM(COALESCE(ps.financiamento_raw, ''))) AS financiamento,
                UPPER(TRIM(COALESCE(ps.conta, ''))) AS conta,
                COALESCE(ps.jan, 0) AS jan,
                COALESCE(ps.fev, 0) AS fev,
                COALESCE(ps.mar, 0) AS mar,
                COALESCE(ps.abr, 0) AS abr,
                COALESCE(ps.mai, 0) AS mai,
                COALESCE(ps.jun, 0) AS jun,
                COALESCE(ps.jul, 0) AS jul,
                COALESCE(ps.ago, 0) AS ago,
                COALESCE(ps.set_, 0) AS set_,
                COALESCE(ps.out_, 0) AS out_,
                COALESCE(ps.nov, 0) AS nov,
                COALESCE(ps.dez, 0) AS dez
            FROM planejamento_staging ps
            JOIN subregioes s
              ON UPPER(TRIM(s.nome)) = UPPER(TRIM(ps.subregiao))
            WHERE ps.lote_id = $1
              AND ps.flag_valida = TRUE
              AND UPPER(TRIM(COALESCE(ps.tipo, ''))) = 'META'
              {filtro_sub}
        )
        SELECT
            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS matriculas_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gnr_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('MATRÍCULAS', 'MATRICULAS')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS pago_matriculas,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS ha_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_ha,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gnr_ha,

            COALESCE(SUM(CASE
                WHEN conta IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS pago_ha,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS receita_total,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento = 'GRATUIDADE REGIMENTAL'
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gr_receita,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento IN ('GRATUIDADE NÃO REGIMENTAL', 'GRATUIDADE NAO REGIMENTAL', 'GRATUITO')
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS gnr_receita,

            COALESCE(SUM(CASE
                WHEN conta IN ('RECEITAS CORRENTES', 'RECEITA', 'RECEITAS')
                 AND financiamento NOT IN (
                    'GRATUIDADE REGIMENTAL',
                    'GRATUIDADE NÃO REGIMENTAL',
                    'GRATUIDADE NAO REGIMENTAL',
                    'GRATUITO'
                 )
                THEN (jan + fev + mar + abr + mai + jun + jul + ago + set_ + out_ + nov + dez)
                ELSE 0
            END), 0) AS pago_receita
        FROM base
        """

        row = await conn.fetchrow(sql, *params)

    d = dict(row or {})

    def pct(parte, total):
        return round((float(parte or 0) / float(total or 0)) * 100, 2) if float(total or 0) else 0

    d["gr_matriculas_pct"] = pct(d["gr_matriculas"], d["matriculas_total"])
    d["gnr_matriculas_pct"] = pct(d["gnr_matriculas"], d["matriculas_total"])
    d["pago_matriculas_pct"] = pct(d["pago_matriculas"], d["matriculas_total"])

    d["gr_ha_pct"] = pct(d["gr_ha"], d["ha_total"])
    d["gnr_ha_pct"] = pct(d["gnr_ha"], d["ha_total"])
    d["pago_ha_pct"] = pct(d["pago_ha"], d["ha_total"])

    d["gr_receita_pct"] = pct(d["gr_receita"], d["receita_total"])
    d["gnr_receita_pct"] = pct(d["gnr_receita"], d["receita_total"])
    d["pago_receita_pct"] = pct(d["pago_receita"], d["receita_total"])

    return d

@router.get("/performance/subregioes")
async def performance_subregioes(
    request: Request,
    ano: int,
    mes: int,
    subregioes: Optional[str] = None,
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote_id = await conn.fetchval(
            """
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento IN ('importado', 'processado')
            ORDER BY id DESC
            LIMIT 1
            """,
            ano
        )

        lote_receita_id = await conn.fetchval(
            """
            SELECT id
            FROM importacao_receita_lotes
            WHERE ano_referencia = $1
            AND status IN ('IMPORTADO', 'PROCESSANDO', 'PROCESSADO', 'PROCESSADO_COM_ERRO')
            ORDER BY id DESC
            LIMIT 1
            """,
            ano
        )

        if not lote_id:
            return []

        params = [lote_id, ano, mes, lote_receita_id]
        filtro_sub = ""

        if subregioes:
            ids_sub = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
            if ids_sub:
                filtro_sub = f" AND s.codigo = ANY(${len(params)+1}::int[])"
                params.append(ids_sub)

        sql = f"""
        WITH base_subregioes AS (
            SELECT DISTINCT
                s.codigo AS cod_subregiao,
                s.nome   AS subregiao
            FROM planejamento_staging ps
            JOIN subregioes s
              ON UPPER(TRIM(s.nome)) = UPPER(TRIM(ps.subregiao))
            WHERE ps.lote_id = $1
              AND ps.flag_valida = TRUE
              AND COALESCE(TRIM(ps.subregiao), '') <> ''
              {filtro_sub}
        ),

        planejamento_agregado AS (
            SELECT
                s.codigo AS cod_subregiao,
                s.nome   AS subregiao,

                SUM(CASE
                    WHEN UPPER(TRIM(ps.tipo)) = 'META'
                     AND UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS')
                    THEN COALESCE(ps.total, 0) ELSE 0
                END) AS matriculas_meta,

                SUM(CASE
                    WHEN UPPER(TRIM(ps.tipo)) = 'PROJETADO'
                     AND UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS')
                    THEN COALESCE(ps.total, 0) ELSE 0
                END) AS matriculas_projetado,

                SUM(CASE
                    WHEN UPPER(TRIM(ps.tipo)) = 'META'
                     AND UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                    THEN COALESCE(ps.total, 0) ELSE 0
                END) AS ha_meta,

                SUM(CASE
                    WHEN UPPER(TRIM(ps.tipo)) = 'PROJETADO'
                     AND UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO')
                    THEN COALESCE(ps.total, 0) ELSE 0
                END) AS ha_projetado,

                SUM(CASE
                    WHEN UPPER(TRIM(ps.tipo)) = 'META'
                     AND UPPER(TRIM(ps.conta)) IN ('RECEITA', 'RECEITAS', 'RECEITAS CORRENTES')
                    THEN COALESCE(ps.total, 0) ELSE 0
                END) AS receita_meta,

                SUM(CASE
                    WHEN UPPER(TRIM(ps.tipo)) = 'PROJETADO'
                     AND UPPER(TRIM(ps.conta)) IN ('RECEITA', 'RECEITAS', 'RECEITAS CORRENTES')
                    THEN COALESCE(ps.total, 0) ELSE 0
                END) AS receita_projetado

            FROM planejamento_staging ps
            JOIN subregioes s
              ON UPPER(TRIM(s.nome)) = UPPER(TRIM(ps.subregiao))
            WHERE ps.lote_id = $1
              AND ps.flag_valida = TRUE
              {filtro_sub}
            GROUP BY s.codigo, s.nome
        ),

        realizado_matriculas AS (
            SELECT
                sr.codigo AS cod_subregiao,
                COALESCE(SUM(COALESCE(tmm.matriculados, 0)), 0) AS matriculas_realizado
            FROM subregioes sr
            LEFT JOIN uo u
            ON u.cod_subregiao = sr.codigo
            LEFT JOIN turmas t
            ON t.cod_uo = u.codigo
            LEFT JOIN turmas_movimento_mensal tmm
            ON tmm.cod_turma = t.codigo
            AND tmm.ano = $2
            AND tmm.mes <= $3
            WHERE 1=1
            {filtro_sub.replace("s.codigo", "sr.codigo")}
            GROUP BY sr.codigo
        ),

        realizado_receita AS (
            SELECT
                sr.codigo AS cod_subregiao,
                COALESCE(SUM(COALESCE(irs.valor, 0)), 0) AS receita_realizado
            FROM importacao_receita_staging irs
            JOIN uo u
            ON u.codigo_sge = irs.cod_uo
            JOIN subregioes sr
            ON sr.codigo = u.cod_subregiao
            WHERE irs.lote_id = $4
            AND irs.status = 'RESOLVIDO'
            AND irs.ano = $2
            AND irs.mes <= $3
            {filtro_sub.replace("s.codigo", "sr.codigo")}
            GROUP BY sr.codigo
        ),

        realizado_subregiao AS (
            SELECT
                bs.cod_subregiao,
                COALESCE(rm.matriculas_realizado, 0) AS matriculas_realizado,
                0 AS ha_realizado,
                COALESCE(rr.receita_realizado, 0) AS receita_realizado
            FROM base_subregioes bs
            LEFT JOIN realizado_matriculas rm
            ON rm.cod_subregiao = bs.cod_subregiao
            LEFT JOIN realizado_receita rr
            ON rr.cod_subregiao = bs.cod_subregiao
        )

        SELECT
            bs.subregiao,

            COALESCE(pa.matriculas_meta, 0) AS matriculas_meta,
            COALESCE(pa.matriculas_projetado, 0) AS matriculas_projetado,
            COALESCE(rs.matriculas_realizado, 0) AS matriculas_realizado,

            CASE
                WHEN COALESCE(pa.matriculas_meta, 0) = 0 THEN 0
                ELSE ROUND(
                        (COALESCE(rs.matriculas_realizado, 0) / NULLIF(pa.matriculas_meta, 0)) * 100,
                        1
                        )
            END AS matriculas_pct,

            CASE
                WHEN COALESCE(pa.matriculas_meta, 0) = 0 THEN 'Ainda não iniciado'

                WHEN (
                    COALESCE(rs.matriculas_realizado, 0) 
                    / NULLIF(pa.matriculas_meta, 0)
                ) >= 1 THEN 'Meta atingida'

                WHEN (
                    COALESCE(rs.matriculas_realizado, 0) 
                    / NULLIF(pa.matriculas_meta, 0)
                ) >= 0.8 THEN 'Atenção'

                WHEN COALESCE(rs.matriculas_realizado, 0) > 0 THEN 'Em andamento'

                ELSE 'Ainda não iniciado'
            END AS matriculas_status,

            COALESCE(pa.ha_meta, 0) AS ha_meta,
            COALESCE(pa.ha_projetado, 0) AS ha_projetado,
            COALESCE(rs.ha_realizado, 0) AS ha_realizado,

            CASE
                WHEN COALESCE(pa.ha_meta, 0) = 0 THEN 0
                ELSE ROUND((COALESCE(rs.ha_realizado, 0) / pa.ha_meta) * 100, 1)
            END AS ha_pct,

            CASE
                WHEN COALESCE(rs.ha_realizado, 0) >= COALESCE(pa.ha_meta, 0)
                     AND COALESCE(pa.ha_meta, 0) > 0
                THEN 'Meta atingida'
                WHEN COALESCE(rs.ha_realizado, 0) > 0
                THEN 'Atenção'
                ELSE 'Ainda não iniciado'
            END AS ha_status,

            COALESCE(pa.receita_meta, 0) AS receita_meta,
            COALESCE(pa.receita_projetado, 0) AS receita_projetado,
            COALESCE(rs.receita_realizado, 0) AS receita_realizado,

            CASE
                WHEN COALESCE(pa.receita_meta, 0) = 0 THEN 0
                ELSE ROUND((COALESCE(rs.receita_realizado, 0) / pa.receita_meta) * 100, 1)
            END AS receita_pct,

            CASE
                WHEN COALESCE(rs.receita_realizado, 0) >= COALESCE(pa.receita_meta, 0)
                     AND COALESCE(pa.receita_meta, 0) > 0
                THEN 'Meta atingida'
                WHEN COALESCE(rs.receita_realizado, 0) > 0
                THEN 'Atenção'
                ELSE 'Ainda não iniciado'
            END AS receita_status

        FROM base_subregioes bs
        LEFT JOIN planejamento_agregado pa
          ON pa.cod_subregiao = bs.cod_subregiao
        LEFT JOIN realizado_subregiao rs
          ON rs.cod_subregiao = bs.cod_subregiao
        ORDER BY bs.subregiao
        """

        rows = await conn.fetch(sql, *params)

    return [dict(r) for r in rows]

@router.get("/performance/subregioes/detalhe")
async def performance_subregioes_detalhe(
    request: Request,
    ano: int,
    subregioes: Optional[str] = None,
):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote_id = await conn.fetchval(
            """
            SELECT id
            FROM planejamento_import_lotes
            WHERE ano_referencia = $1
              AND status_processamento IN ('importado', 'processado')
            ORDER BY id DESC
            LIMIT 1
            """,
            ano
        )

        if not lote_id:
            return []

        params = [lote_id, ano]
        filtro_sub_plan = ""
        filtro_sub_real = ""

        if subregioes:
            ids_sub = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
            if ids_sub:
                filtro_sub_plan = f" AND s.codigo = ANY(${len(params)+1}::int[])"
                filtro_sub_real = f" AND sr.codigo = ANY(${len(params)+1}::int[])"
                params.append(ids_sub)

        sql = f"""
        WITH meses AS (
            SELECT generate_series(1, 12) AS mes
        ),

        sub_base AS (
            SELECT DISTINCT
                s.codigo AS cod_subregiao,
                s.nome AS subregiao
            FROM planejamento_staging ps
            JOIN subregioes s
              ON UPPER(TRIM(s.nome)) = UPPER(TRIM(ps.subregiao))
            WHERE ps.lote_id = $1
              AND ps.flag_valida = TRUE
              AND COALESCE(TRIM(ps.subregiao), '') <> ''
              {filtro_sub_plan}
        ),

        indicadores AS (
            SELECT 'MATRÍCULAS'::text AS indicador
            UNION ALL
            SELECT 'HORA ALUNO'::text
            UNION ALL
            SELECT 'RECEITA'::text
        ),

        grade AS (
            SELECT
                sb.cod_subregiao,
                sb.subregiao,
                i.indicador,
                m.mes
            FROM sub_base sb
            CROSS JOIN indicadores i
            CROSS JOIN meses m
        ),

        planejamento AS (
            SELECT
                s.codigo AS cod_subregiao,
                CASE
                    WHEN UPPER(TRIM(ps.conta)) IN ('MATRÍCULAS', 'MATRICULAS') THEN 'MATRÍCULAS'
                    WHEN UPPER(TRIM(ps.conta)) IN ('HORA ALUNO', 'HORA-ALUNO', 'HORA_ALUNO') THEN 'HORA ALUNO'
                    WHEN UPPER(TRIM(ps.conta)) IN ('RECEITA', 'RECEITAS', 'RECEITAS CORRENTES') THEN 'RECEITA'
                    ELSE NULL
                END AS indicador,
                UPPER(TRIM(ps.tipo)) AS tipo_linha,
                COALESCE(ps.jan, 0) AS m1,
                COALESCE(ps.fev, 0) AS m2,
                COALESCE(ps.mar, 0) AS m3,
                COALESCE(ps.abr, 0) AS m4,
                COALESCE(ps.mai, 0) AS m5,
                COALESCE(ps.jun, 0) AS m6,
                COALESCE(ps.jul, 0) AS m7,
                COALESCE(ps.ago, 0) AS m8,
                COALESCE(ps.set_, 0) AS m9,
                COALESCE(ps.out_, 0) AS m10,
                COALESCE(ps.nov, 0) AS m11,
                COALESCE(ps.dez, 0) AS m12
            FROM planejamento_staging ps
            JOIN subregioes s
              ON UPPER(TRIM(s.nome)) = UPPER(TRIM(ps.subregiao))
            WHERE ps.lote_id = $1
              AND ps.flag_valida = TRUE
              {filtro_sub_plan}
        ),

        planejamento_mensal AS (
            SELECT cod_subregiao, indicador, tipo_linha, 1 AS mes, SUM(m1) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 2 AS mes, SUM(m2) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 3 AS mes, SUM(m3) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 4 AS mes, SUM(m4) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 5 AS mes, SUM(m5) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 6 AS mes, SUM(m6) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 7 AS mes, SUM(m7) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 8 AS mes, SUM(m8) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 9 AS mes, SUM(m9) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 10 AS mes, SUM(m10) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 11 AS mes, SUM(m11) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
            UNION ALL
            SELECT cod_subregiao, indicador, tipo_linha, 12 AS mes, SUM(m12) AS valor FROM planejamento WHERE indicador IS NOT NULL GROUP BY 1,2,3
        ),

        realizado_mensal AS (

            -- MATRÍCULAS
            SELECT
                sr.codigo AS cod_subregiao,
                'MATRÍCULAS'::text AS indicador,
                rp.mes,
                COALESCE(SUM(rp.matriculas_real),0) AS valor
            FROM subregioes sr
            LEFT JOIN uo u
                ON u.cod_subregiao = sr.codigo
            LEFT JOIN ofertas_programas o
                ON o.cod_uo = u.codigo
            AND o.ano = $2
            LEFT JOIN realizado_programas rp
                ON rp.cod_oferta = o.codigo
            AND rp.ano = $2
            WHERE 1=1
            {filtro_sub_real}
            GROUP BY sr.codigo, rp.mes


            UNION ALL


            -- HORA ALUNO
            SELECT
                sr.codigo AS cod_subregiao,
                'HORA ALUNO'::text AS indicador,
                rp.mes,
                COALESCE(SUM(rp.ha_real),0) AS valor
            FROM subregioes sr
            LEFT JOIN uo u
                ON u.cod_subregiao = sr.codigo
            LEFT JOIN ofertas_programas o
                ON o.cod_uo = u.codigo
            AND o.ano = $2
            LEFT JOIN realizado_programas rp
                ON rp.cod_oferta = o.codigo
            AND rp.ano = $2
            WHERE 1=1
            {filtro_sub_real}
            GROUP BY sr.codigo, rp.mes


            UNION ALL


            -- RECEITA
            SELECT
                sr.codigo AS cod_subregiao,
                'RECEITA'::text AS indicador,
                rp.mes,
                COALESCE(SUM(rp.receita_real),0) AS valor
            FROM subregioes sr
            LEFT JOIN uo u
                ON u.cod_subregiao = sr.codigo
            LEFT JOIN ofertas_programas o
                ON o.cod_uo = u.codigo
            AND o.ano = $2
            LEFT JOIN realizado_programas rp
                ON rp.cod_oferta = o.codigo
            AND rp.ano = $2
            WHERE 1=1
            {filtro_sub_real}
            GROUP BY sr.codigo, rp.mes
        )

        SELECT
            g.subregiao,
            g.indicador,

            COALESCE(MAX(CASE WHEN g.mes = 1 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_1,
            COALESCE(MAX(CASE WHEN g.mes = 1 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_1,
            COALESCE(MAX(CASE WHEN g.mes = 1 THEN rm.valor END), 0) AS real_mes_1,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 1 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 1 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 1 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 1 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 1 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 1 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_1,

            COALESCE(MAX(CASE WHEN g.mes = 2 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_2,
            COALESCE(MAX(CASE WHEN g.mes = 2 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_2,
            COALESCE(MAX(CASE WHEN g.mes = 2 THEN rm.valor END), 0) AS real_mes_2,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 2 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 2 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 2 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 2 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 2 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 2 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_2,

            COALESCE(MAX(CASE WHEN g.mes = 3 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_3,
            COALESCE(MAX(CASE WHEN g.mes = 3 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_3,
            COALESCE(MAX(CASE WHEN g.mes = 3 THEN rm.valor END), 0) AS real_mes_3,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 3 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 3 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 3 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 3 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 3 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 3 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_3,

            COALESCE(MAX(CASE WHEN g.mes = 4 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_4,
            COALESCE(MAX(CASE WHEN g.mes = 4 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_4,
            COALESCE(MAX(CASE WHEN g.mes = 4 THEN rm.valor END), 0) AS real_mes_4,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 4 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 4 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 4 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 4 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 4 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 4 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_4,

            COALESCE(MAX(CASE WHEN g.mes = 5 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_5,
            COALESCE(MAX(CASE WHEN g.mes = 5 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_5,
            COALESCE(MAX(CASE WHEN g.mes = 5 THEN rm.valor END), 0) AS real_mes_5,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 5 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 5 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 5 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 5 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 5 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 5 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_5,

            COALESCE(MAX(CASE WHEN g.mes = 6 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_6,
            COALESCE(MAX(CASE WHEN g.mes = 6 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_6,
            COALESCE(MAX(CASE WHEN g.mes = 6 THEN rm.valor END), 0) AS real_mes_6,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 6 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 6 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 6 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 6 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 6 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 6 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_6,

            COALESCE(MAX(CASE WHEN g.mes = 7 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_7,
            COALESCE(MAX(CASE WHEN g.mes = 7 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_7,
            COALESCE(MAX(CASE WHEN g.mes = 7 THEN rm.valor END), 0) AS real_mes_7,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 7 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 7 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 7 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 7 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 7 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 7 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_7,

            COALESCE(MAX(CASE WHEN g.mes = 8 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_8,
            COALESCE(MAX(CASE WHEN g.mes = 8 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_8,
            COALESCE(MAX(CASE WHEN g.mes = 8 THEN rm.valor END), 0) AS real_mes_8,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 8 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 8 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 8 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 8 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 8 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 8 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_8,

            COALESCE(MAX(CASE WHEN g.mes = 9 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_9,
            COALESCE(MAX(CASE WHEN g.mes = 9 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_9,
            COALESCE(MAX(CASE WHEN g.mes = 9 THEN rm.valor END), 0) AS real_mes_9,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 9 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 9 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 9 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 9 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 9 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 9 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_9,

            COALESCE(MAX(CASE WHEN g.mes = 10 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_10,
            COALESCE(MAX(CASE WHEN g.mes = 10 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_10,
            COALESCE(MAX(CASE WHEN g.mes = 10 THEN rm.valor END), 0) AS real_mes_10,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 10 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 10 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 10 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 10 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 10 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 10 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_10,

            COALESCE(MAX(CASE WHEN g.mes = 11 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_11,
            COALESCE(MAX(CASE WHEN g.mes = 11 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_11,
            COALESCE(MAX(CASE WHEN g.mes = 11 THEN rm.valor END), 0) AS real_mes_11,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 11 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 11 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 11 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 11 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 11 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 11 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_11,

            COALESCE(MAX(CASE WHEN g.mes = 12 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) AS meta_mes_12,
            COALESCE(MAX(CASE WHEN g.mes = 12 AND pm.tipo_linha = 'PROJETADO' THEN pm.valor END), 0) AS proj_mes_12,
            COALESCE(MAX(CASE WHEN g.mes = 12 THEN rm.valor END), 0) AS real_mes_12,
            CASE
                WHEN COALESCE(MAX(CASE WHEN g.mes = 12 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) = 0 THEN 'Ainda não iniciado'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 12 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 12 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) THEN 'Meta atingida'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 12 THEN rm.valor END), 0) >= COALESCE(MAX(CASE WHEN g.mes = 12 AND pm.tipo_linha = 'META' THEN pm.valor END), 0) * 0.8 THEN 'Atenção'
                WHEN COALESCE(MAX(CASE WHEN g.mes = 12 THEN rm.valor END), 0) > 0 THEN 'Em andamento'
                ELSE 'Ainda não iniciado'
            END AS situacao_mes_12

        FROM grade g
        LEFT JOIN planejamento_mensal pm
          ON pm.cod_subregiao = g.cod_subregiao
         AND pm.indicador = g.indicador
         AND pm.mes = g.mes
        LEFT JOIN realizado_mensal rm
          ON rm.cod_subregiao = g.cod_subregiao
         AND rm.indicador = g.indicador
         AND rm.mes = g.mes
        GROUP BY g.subregiao, g.indicador
        ORDER BY g.subregiao, g.indicador
        """

        rows = await conn.fetch(sql, *params)

    resultado = []
    for row in rows:
        d = dict(row)
        for i in range(1, 13):
            for prefixo in ["meta", "proj", "real"]:
                chave = f"{prefixo}_mes_{i}"
                d[chave] = float(d[chave] or 0)
        resultado.append(d)

    return resultado

@router.post("/importacoes/data")
async def importar_data(request: Request, arquivo: UploadFile = File(...)):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo não informado.")

    nome = arquivo.filename.lower()
    if not (nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Envie um arquivo Excel .xlsx ou .xls.")

    conteudo = await arquivo.read()
    hash_arquivo = hashlib.sha256(conteudo).hexdigest()

    try:
        xls = pd.ExcelFile(io.BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler Excel: {e}")

    if "Export" not in xls.sheet_names:
        raise HTTPException(status_code=400, detail="A aba 'Export' não foi encontrada no arquivo.")

    try:
        df = pd.read_excel(io.BytesIO(conteudo), sheet_name="Export")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler a aba Export: {e}")

    df.columns = [str(c).strip() for c in df.columns]

    print("COLUNAS DO EXCEL:")
    for c in df.columns:
        print(f"[{c}]")

    def v(row, *nomes):
        for nome in nomes:
            if nome in df.columns:
                return row.get(nome)
        return None

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote = await conn.fetchrow(
                """
                INSERT INTO data_import_lotes (
                    nome_arquivo, hash_arquivo, status_processamento
                )
                VALUES ($1, $2, 'importado')
                RETURNING id
                """,
                arquivo.filename,
                hash_arquivo,
            )
            lote_id = lote["id"]

            registros = []

            for idx, row in df.iterrows():
                turma = norm_text(v(row, "cod_sge", "Turma", "CODTURMA"))
                curso = norm_text(v(row, "curso", "Curso", "CURSO"))
                codigo_curso = norm_text(v(row, "cod_curso", "codigo_curso", "Código Curso", "CODCURSO", "Codigo Curso"))
                codigo_programa = norm_text(v(row, "cod_programa", "codigo_programa", "COD_PROGRAMA", "Código Programa"))
                codigo_modalidade = norm_text(v(row, "cod_modalidade", "codigo_modalidade", "COD_MODALIDADE", "Código Modalidade"))

                unidade = norm_text(v(row, "nome_uo", "Unidade", "NOMEFANTASIA"))
                cod_unidade = norm_text(v(row, "cod_uo", "COD_UNIDADE", "COD_UO", "Cod UO", "CODFILIAL"))
                cnpj_raw = v(row, "cnpj", "CNPJ", "CNPJ Empresa", "CPF_CNPJ", "cpf_cnpj")

                if pd.isna(cnpj_raw):
                    cnpj = None
                else:
                    cnpj = str(cnpj_raw).strip()
                    if cnpj.endswith(".0"):
                        cnpj = cnpj[:-2]
                    cnpj = "".join(ch for ch in cnpj if ch.isdigit()) or None
                if idx < 5:
                    print("VALOR CNPJ LIDO:", cnpj)
                data_matricula = norm_date(v(row, "data_matricula", "Data da matrícula", "DTMATRICULA"))
                status_matricula = norm_text(v(row, "status_matricula", "Status da matrícula", "STATUS_CURSO", "STATUS_PLETIVO"))

                condicao_aluno = norm_text(v(
                    row,
                    "nome_financiamento",
                    "Condição do Aluno",
                    "SENAI_CONDICAO_ALUNO_CURSO"
                ))

                data_inicio = norm_date(v(row, "data_inicio_turma", "Data Início Turma", "DTINICIAL"))
                data_fim = norm_date(v(row, "data_final_turma", "Data Final Turma", "DTFINAL"))
                data_ini_contratoapr = norm_date(v(
                    row,
                    "data_inicio_contrato",
                    "DATA_INICIO_CONTRATO",
                    "Data Inicio Contrato"
                ))

                data_fim_contratoapr = norm_date(v(
                    row,
                    "data_fim_contrato",
                    "DATA_FIM_CONTRATO",
                    "Data Fim Contrato"
                ))

                formato = norm_text(v(row, "formato_turma", "Formato Turma", "TIPO_MEDIACAOTURMA"))
                turno = norm_text(v(row, "turno", "Turno", "TURNO"))
                vagas = norm_int(v(row, "vagas", "Vagas", "VAGAS", "nro_max_previstos_alunos", "NRO_MAX_PREVISTOS_ALUNOS", "NRO_MAX_PREVISTOS_ALUNOS", "NRO MAX PREVISTOS ALUNOS"))

                status = (status_matricula or "").strip().upper()

                matriculados = 1 if status == "MATRICULADO" else 0
                pre_matriculados = 1 if status in ("PRE_MATRICULADO", "PRÉ-MATRICULADO") else 0
                cancelados = 1 if status == "CANCELADO" else 0
                desistentes = 1 if status == "DESISTENTE" else 0
                evadidos = 1 if status == "EVADIDO" else 0
                falecidos = 1 if status == "FALECIDO" else 0

                registros.append((
                    lote_id,
                    turma,
                    curso,
                    codigo_curso,
                    codigo_programa,
                    codigo_modalidade,
                    unidade,
                    cod_unidade,
                    data_matricula,
                    status_matricula,
                    condicao_aluno,
                    data_inicio,
                    data_fim,
                    formato,
                    turno,
                    vagas,
                    matriculados,
                    pre_matriculados,
                    cancelados,
                    desistentes,
                    evadidos,
                    falecidos,
                    cnpj,
                    data_ini_contratoapr,
                    data_fim_contratoapr,
                    idx + 2
                ))

            if registros:
                print("REGISTROS PARA INSERIR:", len(registros))

                await conn.executemany(
                    """
                    INSERT INTO data_staging (
                        lote_id,
                        turma,
                        curso,
                        codigo_curso,
                        cod_programa,
                        cod_modalidade,
                        unidade,
                        cod_unidade,
                        data_matricula,
                        status_matricula,
                        condicao_aluno,
                        data_inicio,
                        data_fim,
                        formato,
                        turno,
                        vagas,
                        matriculados,
                        pre_matriculados,
                        cancelados,
                        desistentes,
                        evadidos,
                        falecidos,
                        cnpj,
                        data_ini_contratoapr,
                        data_fim_contratoapr,
                        linha_numero
                    )
                    VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                        $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26
                    )
                    """,
                    registros
                )

                total_staging = await conn.fetchval(
                    "SELECT COUNT(*) FROM data_staging WHERE lote_id = $1",
                    lote_id
                )

                print("TOTAL INSERIDO EM DATA_STAGING:", total_staging)

            await conn.execute(
                """
                UPDATE data_import_lotes
                SET total_linhas = $2
                WHERE id = $1
                """,
                lote_id,
                len(registros)
            )

    return {
        "ok": True,
        "lote_id": lote_id,
        "arquivo": arquivo.filename,
        "linhas_importadas": len(registros),
    }

@router.post("/importacoes/data/processar/{lote_id}")
async def processar_data(request: Request, lote_id: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote = await conn.fetchrow(
                """
                SELECT *
                FROM data_import_lotes
                WHERE id = $1
                """,
                lote_id
            )

            if not lote:
                raise HTTPException(status_code=404, detail="Lote não encontrado.")

            rows = await conn.fetch(
                """
                SELECT *
                FROM data_staging
                WHERE lote_id = $1
                ORDER BY id
                """,
                lote_id
            )

            if not rows:
                raise HTTPException(status_code=400, detail="Lote sem linhas na staging para processar.")
            
            await conn.execute(
                """
                INSERT INTO curso (codigo_sge, nome_curso)
                SELECT DISTINCT
                    TRIM(ds.codigo_curso) AS codigo_sge,
                    MAX(TRIM(ds.curso)) AS nome_curso
                FROM data_staging ds
                LEFT JOIN curso c
                ON TRIM(c.codigo_sge) = TRIM(ds.codigo_curso)
                WHERE ds.lote_id = $1
                AND ds.codigo_curso IS NOT NULL
                AND TRIM(ds.codigo_curso) <> ''
                AND ds.curso IS NOT NULL
                AND TRIM(ds.curso) <> ''
                AND c.codigo IS NULL
                GROUP BY TRIM(ds.codigo_curso)
                """,
                lote_id
            )

            turmas_processadas = 0

            codigos_sge = sorted({
                (r["turma"] or "").strip()
                for r in rows
                if (r["turma"] or "").strip()
            })

            turmas_existentes = {}
            if codigos_sge:
                existentes = await conn.fetch(
                    """
                    SELECT codigo, codigo_sge
                    FROM turmas
                    WHERE codigo_sge = ANY($1::text[])
                    """,
                    codigos_sge
                )
                turmas_existentes = {
                    row["codigo_sge"]: row["codigo"]
                    for row in existentes
                }

            movimentos_buffer = {}
            turmas_insert_buffer = {}
            turmas_update_buffer = {}

            uo_por_codigo_sge = {
                str(row["codigo_sge"]).strip(): row["codigo"]
                for row in await conn.fetch("""
                    SELECT codigo, codigo_sge
                    FROM uo
                    WHERE codigo_sge IS NOT NULL
                """)
            }

            uo_por_nome = {
                    norm_text(row["nome"]).upper(): row["codigo"]
                    for row in await conn.fetch("""
                        SELECT codigo, nome
                        FROM uo
                        WHERE nome IS NOT NULL
                    """)
                }
            
            turno_map = {
                norm_text(row["nome"]).upper(): row["codigo"]
                for row in await conn.fetch("""
                    SELECT codigo, nome
                    FROM turnos
                    WHERE nome IS NOT NULL
                """)
            }
            
            codigos_curso = sorted({
                str(r["codigo_curso"]).strip()
                for r in rows
                if r["codigo_curso"] is not None and str(r["codigo_curso"]).strip()
            })

            curso_map = {}
            if codigos_curso:
                curso_rows = await conn.fetch(
                    """
                    SELECT codigo, codigo_sge, codprograma
                    FROM curso
                    WHERE codigo_sge IS NOT NULL
                    """
                )

                curso_map = {
                    str(row["codigo_sge"]).strip(): {
                        "cod_curso": row["codigo"],
                        "cod_programa": row["codprograma"],
                    }
                    for row in curso_rows
                }

            formato_map = {
                "P": 4,   # PRESENCIAL
                "D": 5,   # EAD
                "S": 6    # SEMIPRESENCIAL
            }

            curso_nome_map = {
                row["nome_curso"].strip().upper(): row["codigo"]
                for row in await conn.fetch("SELECT codigo, nome_curso FROM curso WHERE nome_curso IS NOT NULL")
            }

            detalhes_por_turma = {}

            for r in rows:
                codigo_sge = (r["turma"] or "").strip()
                if not codigo_sge:
                    continue

                ano_referencia = r["data_matricula"].year if r["data_matricula"] else None
                mes_referencia = r["data_matricula"].month if r["data_matricula"] else None
                cod_uo = None
                
                cod_curso = None
                cod_programa = None

                codigo_curso_norm = str(r["codigo_curso"]).strip() if r["codigo_curso"] else None
                curso_info = curso_map.get(codigo_curso_norm) if codigo_curso_norm else None

                if r["cod_unidade"]:
                    try:
                        chave_uo = str(int(float(str(r["cod_unidade"]).strip())))
                        cod_uo = uo_por_codigo_sge.get(chave_uo)
                    except Exception:
                        cod_uo = None

                if curso_info:
                    cod_curso = curso_info["cod_curso"]

                # Prioridade 1: cod_programa vindo do data.xlsx
                if r["cod_programa"]:
                    try:
                        cod_programa = int(float(str(r["cod_programa"]).strip()))
                    except Exception:
                        cod_programa = None

                # Prioridade 2: programa vinculado ao curso
                if cod_programa is None and curso_info:
                    cod_programa = curso_info["cod_programa"]

                if cod_curso is None and codigo_curso_norm:
                    print("🚨 CURSO NÃO ENCONTRADO:", codigo_curso_norm)

                if cod_programa is None:
                    print("🚨 PROGRAMA NÃO INFORMADO/ENCONTRADO PARA A TURMA:", codigo_sge)
                
                cod_modalidade = None

                if r["cod_modalidade"]:
                    try:
                        cod_modalidade = int(float(str(r["cod_modalidade"]).strip()))
                    except Exception:
                        cod_modalidade = None

                cod_formato = None

                valor_formato = (r["formato"] or "").strip().upper()

                if "SEMIPRESENCIAL" in valor_formato or "SEMI" in valor_formato:
                    cod_formato = 6
                elif "PRESENCIAL DUAL" in valor_formato or "DUAL" in valor_formato:
                    cod_formato = 7
                elif "EDUCAÇÃO A DISTÂNCIA" in valor_formato or "EDUCACAO A DISTANCIA" in valor_formato or "EAD" in valor_formato:
                    cod_formato = 5
                elif "PRESENCIAL" in valor_formato:
                    cod_formato = 4
                
                if cod_formato is None:
                    cod_formato = 99

                cod_turno = None

                valor_turno = (r["turno"] or "").strip().upper()

                if valor_turno:
                    cod_turno = turno_map.get(valor_turno)

                cod_turma = turmas_existentes.get(codigo_sge)

                if cod_turma:
                    turmas_update_buffer[codigo_sge] = (
                        codigo_sge,
                        cod_uo,
                        cod_programa,
                        cod_curso,
                        cod_modalidade,
                        cod_formato,
                        cod_turno,
                        r["cnpj"],
                        r["data_inicio"],
                        r["data_fim"],
                        r["data_ini_contratoapr"],
                        r["data_fim_contratoapr"],
                        r["vagas"] or 0,
                        ano_referencia,
                        lote_id
                    )
                else:
                    turmas_insert_buffer[codigo_sge] = (
                        codigo_sge,
                        cod_uo,
                        cod_programa,
                        cod_curso,
                        cod_modalidade,
                        cod_formato,
                        cod_turno,
                        r["cnpj"],
                        r["data_inicio"],
                        r["data_fim"],
                        r["data_ini_contratoapr"],
                        r["data_fim_contratoapr"],
                        r["vagas"] or 0,
                        ano_referencia,
                        lote_id
                    )
                
                if ano_referencia and mes_referencia:
                    chave_mov = (codigo_sge, ano_referencia, mes_referencia)
                    if ano_referencia and mes_referencia:
                        chave_mov = (codigo_sge, ano_referencia, mes_referencia)

                        atual = movimentos_buffer.get(chave_mov, {
                            "matriculados": 0,
                            "pre_matriculados": 0
                        })

                        atual["matriculados"] += r["matriculados"] or 0
                        atual["pre_matriculados"] += r["pre_matriculados"] or 0

                        movimentos_buffer[chave_mov] = atual

                if codigo_sge not in detalhes_por_turma:
                    detalhes_por_turma[codigo_sge] = []

                detalhes_por_turma[codigo_sge].append({
                    "ra": None,
                    "cpf": None,
                    "nome_aluno": None,
                    "data_matricula": r["data_matricula"],
                    "cnpj": r["cnpj"],
                    "data_ini_contratoapr": r["data_ini_contratoapr"],
                    "data_fim_contratoapr": r["data_fim_contratoapr"],
                    "status_matricula": (r["status_matricula"] or "").strip().upper() if r["status_matricula"] else None,
                    "condicao_aluno": (r["condicao_aluno"] or "").strip() if r["condicao_aluno"] else None,
                })

            if turmas_update_buffer:
                await conn.executemany(
                    """
                    UPDATE turmas
                    SET cod_uo = $2,
                        cod_programa = $3,
                        cod_curso = $4,
                        cod_modalidade = $5,
                        cod_formato = $6,
                        cod_turno = $7,
                        cnpj = $8,
                        data_inicio = $9,
                        data_fim = $10,
                        data_ini_contratoapr = $11,
                        data_fim_contratoapr = $12,
                        vagas_total = COALESCE($13, 0),
                        ano_referencia = $14,
                        data_atualizacao = CURRENT_TIMESTAMP,
                        lote_origem_data_id = $15
                    WHERE codigo_sge = $1
                    """,
                    list(turmas_update_buffer.values())
                )

            if turmas_insert_buffer:
                novas_turmas = await conn.fetch(
                    """
                    INSERT INTO turmas (
                        codigo_sge,
                        cod_uo,
                        cod_programa,
                        cod_curso,
                        cod_modalidade,
                        cod_formato,
                        cod_turno,
                        cnpj,
                        data_inicio,
                        data_fim,
                        data_ini_contratoapr,
                        data_fim_contratoapr,
                        vagas_total,
                        ano_referencia,
                        lote_origem_data_id
                    )
                    SELECT
                        x.codigo_sge,
                        x.cod_uo,
                        x.cod_programa,
                        x.cod_curso,
                        x.cod_modalidade,
                        x.cod_formato,
                        x.cod_turno,
                        x.cnpj,
                        x.data_inicio,
                        x.data_fim,
                        x.data_ini_contratoapr,
                        x.data_fim_contratoapr,
                        x.vagas_total,
                        x.ano_referencia,
                        x.lote_id
                    FROM UNNEST(
                        $1::text[],
                        $2::int[],
                        $3::int[],
                        $4::int[],
                        $5::int[],
                        $6::int[],
                        $7::int[],
                        $8::text[],
                        $9::date[],
                        $10::date[],
                        $11::date[],
                        $12::date[],
                        $13::int[],
                        $14::int[],
                        $15::int[]
                    ) AS x(
                        codigo_sge,
                        cod_uo,
                        cod_programa,
                        cod_curso,
                        cod_modalidade,
                        cod_formato,
                        cod_turno,
                        cnpj,
                        data_inicio,
                        data_fim,
                        data_ini_contratoapr,
                        data_fim_contratoapr,
                        vagas_total,
                        ano_referencia,
                        lote_id
                    )
                    RETURNING codigo, codigo_sge
                    """,
                    [v[0] for v in turmas_insert_buffer.values()],
                    [v[1] for v in turmas_insert_buffer.values()],
                    [v[2] for v in turmas_insert_buffer.values()],
                    [v[3] for v in turmas_insert_buffer.values()],
                    [v[4] for v in turmas_insert_buffer.values()],
                    [v[5] for v in turmas_insert_buffer.values()],
                    [v[6] for v in turmas_insert_buffer.values()],
                    [v[7] for v in turmas_insert_buffer.values()],
                    [v[8] for v in turmas_insert_buffer.values()],
                    [v[9] for v in turmas_insert_buffer.values()],
                    [v[10] for v in turmas_insert_buffer.values()],
                    [v[11] for v in turmas_insert_buffer.values()],
                    [v[12] for v in turmas_insert_buffer.values()],
                    [v[13] for v in turmas_insert_buffer.values()],
                    [v[14] for v in turmas_insert_buffer.values()],
                )

                for row in novas_turmas:
                    turmas_existentes[row["codigo_sge"]] = row["codigo"]
                
                turmas_processadas = len(turmas_update_buffer) + len(turmas_insert_buffer)
            
            detalhe_alunos_rows = []

            if "detalhes_por_turma" in locals():
                for codigo_sge, itens in detalhes_por_turma.items():
                    cod_turma = turmas_existentes.get(codigo_sge)
                    if not cod_turma:
                        continue

                    for item in itens:
                        payload_hash = hash_linha({
                            "lote_id": lote_id,
                            "cod_turma": codigo_sge,
                            "ra": item["ra"],
                            "cpf": item["cpf"],
                            "nome_aluno": item["nome_aluno"],
                            "status_matricula": item["status_matricula"],
                            "condicao_aluno": item["condicao_aluno"],
                            "data_matricula": item["data_matricula"],
                        })

                        detalhe_alunos_rows.append((
                            lote_id,
                            codigo_sge,
                            item["ra"],
                            item["cpf"],
                            item["nome_aluno"],
                            item["status_matricula"],
                            item["cnpj"],
                            item["condicao_aluno"],
                            item["data_matricula"],
                            item["data_ini_contratoapr"],
                            item["data_fim_contratoapr"],
                            payload_hash,
                        ))
            
            codigos_turma_movimento = []
            anos_movimento = []

            for (codigo_sge, ano, mes) in movimentos_buffer.keys():
                cod_turma = turmas_existentes.get(codigo_sge)

                if cod_turma:
                    codigos_turma_movimento.append(cod_turma)
                    anos_movimento.append(ano)

            codigos_turma_movimento = sorted(set(codigos_turma_movimento))
            anos_movimento = sorted(set(anos_movimento))

            if anos_movimento:
                await conn.execute(
                    """
                    DELETE FROM turmas_movimento_mensal
                    WHERE ano = ANY($1::int[])
                    """,
                    anos_movimento
                )

            movimentos_finais = []

            for (codigo_sge, ano, mes), dados in movimentos_buffer.items():
                cod_turma = turmas_existentes.get(codigo_sge)
                if not cod_turma:
                    continue

                movimentos_finais.append((
                    cod_turma,
                    ano,
                    mes,
                    dados["matriculados"],
                    dados["pre_matriculados"]
                ))
            
            if movimentos_finais:
                await conn.executemany(
                    """
                    INSERT INTO turmas_movimento_mensal (
                        cod_turma,
                        ano,
                        mes,
                        matriculados,
                        pre_matriculados
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (cod_turma, ano, mes)
                    DO UPDATE SET
                        matriculados = EXCLUDED.matriculados,
                        pre_matriculados = EXCLUDED.pre_matriculados
                    """,
                    movimentos_finais
                )
            
            status_resumo_buffer = {}

            for r in rows:
                codigo_sge = (r["turma"] or "").strip()
                if not codigo_sge:
                    continue

                cod_turma = turmas_existentes.get(codigo_sge)
                if not cod_turma:
                    continue

                if cod_turma not in status_resumo_buffer:
                    status_resumo_buffer[cod_turma] = {
                        "matriculados": 0,
                        "pre_matriculados": 0,
                        "cancelados": 0,
                        "desistentes": 0,
                        "evadidos": 0,
                        "falecidos": 0,
                    }

                status_resumo_buffer[cod_turma]["matriculados"] += r["matriculados"] or 0
                status_resumo_buffer[cod_turma]["pre_matriculados"] += r["pre_matriculados"] or 0
                status_resumo_buffer[cod_turma]["cancelados"] += r["cancelados"] or 0
                status_resumo_buffer[cod_turma]["desistentes"] += r["desistentes"] or 0
                status_resumo_buffer[cod_turma]["evadidos"] += r["evadidos"] or 0
                status_resumo_buffer[cod_turma]["falecidos"] += r["falecidos"] or 0

            status_resumo_rows = [
                (
                    cod_turma,
                    vals["matriculados"],
                    vals["pre_matriculados"],
                    vals["cancelados"],
                    vals["desistentes"],
                    vals["evadidos"],
                    vals["falecidos"],
                )
                for cod_turma, vals in status_resumo_buffer.items()
            ]

            codigos_turma_processados = [
                codigo
                for codigo in turmas_existentes.values()
            ]

            if codigos_turma_processados:
                await conn.execute(
                    """
                    DELETE FROM sge_turma_detalhe_alunos
                    WHERE lote_id = $1
                    """,
                    lote_id
                )
            
            if detalhe_alunos_rows:
                await conn.executemany(
                    """
                    INSERT INTO sge_turma_detalhe_alunos (
                        lote_id,
                        cod_turma,
                        ra,
                        cpf,
                        nome_aluno,
                        status_matricula,
                        cnpj,
                        condicao_aluno,
                        data_matricula,
                        data_ini_contratoapr,
                        data_fim_contratoapr,
                        hash_linha
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    detalhe_alunos_rows
                )

            if status_resumo_rows:
                await conn.executemany(
                    """
                    INSERT INTO turmas_status_resumo (
                        cod_turma,
                        matriculados,
                        pre_matriculados,
                        cancelados,
                        desistentes,
                        evadidos,
                        falecidos,
                        atualizado_em
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP)
                    ON CONFLICT (cod_turma)
                    DO UPDATE SET
                        matriculados = EXCLUDED.matriculados,
                        pre_matriculados = EXCLUDED.pre_matriculados,
                        cancelados = EXCLUDED.cancelados,
                        desistentes = EXCLUDED.desistentes,
                        evadidos = EXCLUDED.evadidos,
                        falecidos = EXCLUDED.falecidos,
                        atualizado_em = CURRENT_TIMESTAMP
                    """,
                    status_resumo_rows
                )

            await conn.execute(
                """
                DELETE FROM data_staging
                WHERE lote_id = $1
                """,
                lote_id
            )

            await conn.execute(
                """
                UPDATE data_import_lotes
                SET status_processamento = 'processado',
                    data_processamento = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                lote_id
            )

    return {
        "ok": True,
        "lote_id": lote_id,
        "turmas_processadas": turmas_processadas,
        "mensagem": "Lote processado com sucesso."
    }

@router.post("/auth/login")
async def auth_login(payload: LoginPayload, request: Request, response: Response):
    usuario = (payload.usuario or "").strip()
    senha = payload.senha or ""

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                u.id,
                u.usuario,
                u.nome,
                u.deve_trocar_senha,
                p.nome AS perfil
            FROM usuarios u
            JOIN perfis p ON p.id = u.perfil_id
            WHERE u.usuario = $1
              AND u.ativo = TRUE
              AND u.senha_hash = crypt($2, u.senha_hash)
        """, usuario, senha)

    if not row:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

    token = secrets.token_urlsafe(32)

    SESSOES_ATIVAS[token] = {
        "usuario": row["usuario"],
        "nome": row["nome"],
        "perfil": row["perfil"]
    }

    response.set_cookie(
        key="painel_session",
        value=token,

        httponly=True,
        secure=True,
        samesite="none",

        path="/",
        max_age=60 * 60 * 8,
    )

    return {
        "ok": True,
        "usuario": row["usuario"],
        "nome": row["nome"],
        "perfil": row["perfil"],
        "deve_trocar_senha": row["deve_trocar_senha"]
    }


@router.get("/auth/me")
async def auth_me(request: Request):
    token = request.cookies.get("painel_session")

    if not token or token not in SESSOES_ATIVAS:
        raise HTTPException(status_code=401, detail="Não autenticado.")

    return {
        "ok": True,
        **SESSOES_ATIVAS[token]
    }

@router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("painel_session")

    if token and token in SESSOES_ATIVAS:
        del SESSOES_ATIVAS[token]

    response.delete_cookie(
        "painel_session",
        path="/",
        secure=True,
        samesite="none",
    )

    return {"ok": True}

@router.post("/auth/esqueci-senha")
async def auth_esqueci_senha(payload: EsqueciSenhaPayload, request: Request):
    identificador = (payload.identificador or "").strip()

    if not identificador:
        raise HTTPException(status_code=400, detail="Informe usuário ou e-mail.")

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id
            FROM usuarios
            WHERE ativo = TRUE
              AND (
                LOWER(usuario) = LOWER($1)
                OR LOWER(COALESCE(email, '')) = LOWER($1)
              )
        """, identificador)

        await conn.execute("""
            INSERT INTO usuarios_reset_solicitacoes (
                usuario_id,
                identificador
            )
            VALUES ($1, $2)
        """, row["id"] if row else None, identificador)

    return {
        "ok": True,
        "mensagem": "Solicitação registrada. Aguarde contato do administrador."
    }

@router.post("/auth/redefinir-senha")
async def auth_redefinir_senha(payload: RedefinirSenhaPayload, request: Request):
    token = (payload.token or "").strip()
    senha = payload.senha or ""

    if not token or not senha:
        raise HTTPException(status_code=400, detail="Dados inválidos.")

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT *
            FROM usuarios_recuperacao_senha
            WHERE token = $1
              AND usado = FALSE
              AND expira_em > NOW()
        """, token)

        if not row:
            raise HTTPException(status_code=400, detail="Token inválido ou expirado.")
        
        print("TOKEN RECEBIDO:", token)

        usuario_id = row["usuario_id"]

        await conn.execute("""
            UPDATE usuarios
            SET senha_hash = crypt($1, gen_salt('bf')),
                atualizado_em = NOW()
            WHERE id = $2
        """, senha, usuario_id)

        await conn.execute("""
            UPDATE usuarios_recuperacao_senha
            SET usado = TRUE
            WHERE id = $1
        """, row["id"])

    return {"ok": True}

def get_usuario_logado(request: Request):
    token = request.cookies.get("painel_session")

    if not token or token not in SESSOES_ATIVAS:
        raise HTTPException(status_code=401, detail="Não autenticado.")

    return SESSOES_ATIVAS[token]

@router.post("/auth/alterar-senha")
async def auth_alterar_senha(payload: AlterarSenhaPayload, request: Request):
    usuario_logado = get_usuario_logado(request)

    senha_atual = payload.senha_atual
    nova_senha = payload.nova_senha

    if not senha_atual or not nova_senha:
        raise HTTPException(status_code=400, detail="Dados inválidos.")

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id
            FROM usuarios
            WHERE usuario = $1
              AND senha_hash = crypt($2, senha_hash)
        """, usuario_logado["usuario"], senha_atual)

        if not row:
            raise HTTPException(status_code=400, detail="Senha atual incorreta.")

        await conn.execute("""
            UPDATE usuarios
            SET senha_hash = crypt($1, gen_salt('bf')),
                atualizado_em = NOW(),
                deve_trocar_senha = FALSE
            WHERE id = $2
        """, nova_senha, row["id"])

    return {"ok": True}

@router.get("/auth/reset-solicitacoes")
async def auth_reset_solicitacoes(request: Request):
    usuario_logado = get_usuario_logado(request)

    if usuario_logado["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado.")

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                s.id,
                s.identificador,
                s.criado_em,
                s.atendido,
                u.id AS usuario_id,
                u.nome AS usuario_nome,
                u.usuario AS usuario_login,
                u.email AS usuario_email
            FROM usuarios_reset_solicitacoes s
            LEFT JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.atendido = FALSE
            ORDER BY s.criado_em DESC
        """)

    return {
        "ok": True,
        "items": [
            {
                "id": r["id"],
                "identificador": r["identificador"],
                "criado_em": str(r["criado_em"]),
                "atendido": r["atendido"],
                "usuario_id": r["usuario_id"],
                "usuario_nome": r["usuario_nome"],
                "usuario_login": r["usuario_login"],
                "usuario_email": r["usuario_email"],
            }
            for r in rows
        ]
    }

@router.post("/auth/reset-solicitacoes/atender")
async def auth_reset_solicitacoes_atender(
    payload: ResetSolicitacaoAtenderPayload,
    request: Request
):
    usuario_logado = get_usuario_logado(request)

    if usuario_logado["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado.")

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE usuarios_reset_solicitacoes
            SET atendido = TRUE
            WHERE id = $1
        """, payload.id)

    return {"ok": True}

@router.post("/auth/reset-solicitacoes/definir-senha-temporaria")
async def auth_reset_definir_senha_temporaria(
    payload: ResetDefinirSenhaTemporariaPayload,
    request: Request
):
    usuario_logado = get_usuario_logado(request)

    if usuario_logado["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado.")

    nova_senha = (payload.nova_senha or "").strip()
    if len(nova_senha) < 4:
        raise HTTPException(status_code=400, detail="A senha temporária deve ter pelo menos 4 caracteres.")

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                s.id,
                s.usuario_id,
                s.atendido,
                u.usuario
            FROM usuarios_reset_solicitacoes s
            LEFT JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.id = $1
        """, payload.solicitacao_id)

        if not row:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

        if row["atendido"]:
            raise HTTPException(status_code=400, detail="Esta solicitação já foi atendida.")

        if not row["usuario_id"]:
            raise HTTPException(status_code=400, detail="Esta solicitação não está vinculada a um usuário válido.")

        await conn.execute("""
            UPDATE usuarios
            SET senha_hash = crypt($1, gen_salt('bf')),
                atualizado_em = NOW(),
                deve_trocar_senha = TRUE
            WHERE id = $2
        """, nova_senha, row["usuario_id"])

        await conn.execute("""
            UPDATE usuarios_reset_solicitacoes
            SET atendido = TRUE
            WHERE id = $1
        """, payload.solicitacao_id)

    return {
        "ok": True,
        "mensagem": "Senha temporária definida com sucesso."
    }

@router.get("/auth/perfis")
async def auth_perfis(request: Request):
    usuario_logado = get_usuario_logado(request)

    if usuario_logado["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado.")

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, nome, descricao
            FROM perfis
            WHERE ativo = TRUE
            ORDER BY nome
        """)

    return {
        "ok": True,
        "items": [
            {
                "id": r["id"],
                "nome": r["nome"],
                "descricao": r["descricao"]
            }
            for r in rows
        ]
    }

@router.get("/auth/usuarios")
async def auth_usuarios(request: Request):
    usuario_logado = get_usuario_logado(request)

    if usuario_logado["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado.")

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                u.id,
                u.nome,
                u.usuario,
                u.email,
                u.ativo,
                u.deve_trocar_senha,
                p.id AS perfil_id,
                p.nome AS perfil_nome
            FROM usuarios u
            JOIN perfis p ON p.id = u.perfil_id
            ORDER BY u.nome
        """)

    return {
        "ok": True,
        "items": [
            {
                "id": r["id"],
                "nome": r["nome"],
                "usuario": r["usuario"],
                "email": r["email"],
                "ativo": r["ativo"],
                "deve_trocar_senha": r["deve_trocar_senha"],
                "perfil_id": r["perfil_id"],
                "perfil_nome": r["perfil_nome"]
            }
            for r in rows
        ]
    }

@router.post("/auth/usuarios")
async def auth_criar_usuario(payload: CriarUsuarioPayload, request: Request):
    usuario_logado = get_usuario_logado(request)

    if usuario_logado["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado.")

    nome = (payload.nome or "").strip()
    usuario = (payload.usuario or "").strip()
    email = (payload.email or "").strip() or None
    perfil_id = payload.perfil_id
    ativo = bool(payload.ativo)

    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome.")
    if not usuario:
        raise HTTPException(status_code=400, detail="Informe o usuário.")
    if not perfil_id:
        raise HTTPException(status_code=400, detail="Informe o perfil.")

    senha_temporaria = secrets.token_urlsafe(6)

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        perfil = await conn.fetchrow("""
            SELECT id, nome
            FROM perfis
            WHERE id = $1
              AND ativo = TRUE
        """, perfil_id)

        if not perfil:
            raise HTTPException(status_code=400, detail="Perfil inválido.")

        usuario_existente = await conn.fetchrow("""
            SELECT id
            FROM usuarios
            WHERE LOWER(usuario) = LOWER($1)
        """, usuario)

        if usuario_existente:
            raise HTTPException(status_code=400, detail="Já existe um usuário com esse login.")

        if email:
            email_existente = await conn.fetchrow("""
                SELECT id
                FROM usuarios
                WHERE LOWER(email) = LOWER($1)
            """, email)

            if email_existente:
                raise HTTPException(status_code=400, detail="Já existe um usuário com esse e-mail.")

        row = await conn.fetchrow("""
            INSERT INTO usuarios (
                nome,
                usuario,
                email,
                senha_hash,
                perfil_id,
                ativo,
                deve_trocar_senha,
                criado_em,
                atualizado_em
            )
            VALUES (
                $1,
                $2,
                $3,
                crypt($4, gen_salt('bf')),
                $5,
                $6,
                TRUE,
                NOW(),
                NOW()
            )
            RETURNING id, nome, usuario, email, perfil_id, ativo, deve_trocar_senha
        """, nome, usuario, email, senha_temporaria, perfil_id, ativo)

    return {
        "ok": True,
        "mensagem": "Usuário cadastrado com sucesso.",
        "senha_temporaria": senha_temporaria,
        "item": {
            "id": row["id"],
            "nome": row["nome"],
            "usuario": row["usuario"],
            "email": row["email"],
            "perfil_id": row["perfil_id"],
            "ativo": row["ativo"],
            "deve_trocar_senha": row["deve_trocar_senha"]
        }
    }

@router.put("/auth/usuarios/{usuario_id}")
async def auth_atualizar_usuario(
    usuario_id: int,
    payload: AtualizarUsuarioPayload,
    request: Request
):
    usuario_logado = get_usuario_logado(request)

    if usuario_logado["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado.")

    nome = (payload.nome or "").strip()
    email = (payload.email or "").strip() or None
    perfil_id = payload.perfil_id
    ativo = bool(payload.ativo)

    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome.")
    if not perfil_id:
        raise HTTPException(status_code=400, detail="Informe o perfil.")

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id FROM usuarios WHERE id = $1
        """, usuario_id)

        if not row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        await conn.execute("""
            UPDATE usuarios
            SET
                nome = $1,
                email = $2,
                perfil_id = $3,
                ativo = $4,
                atualizado_em = NOW()
            WHERE id = $5
        """, nome, email, perfil_id, ativo, usuario_id)

    return {"ok": True, "mensagem": "Usuário atualizado com sucesso."}

@router.post("/importacoes/cotas")
async def importar_cotas(request: Request, arquivo: UploadFile = File(...)):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo não informado.")

    nome = arquivo.filename.lower()
    if not (nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Envie um arquivo Excel .xlsx ou .xls.")

    conteudo = await arquivo.read()

    try:
        df = pd.read_excel(io.BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler Excel: {e}")

    df.columns = [str(c).replace("\xa0", " ").strip().lower() for c in df.columns]

    obrigatorias = ["codigo", "municipio", "cota", "cod_regiao"]
    faltantes = [c for c in obrigatorias if c not in df.columns]

    if faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"Colunas obrigatórias ausentes no Excel: {', '.join(faltantes)}"
        )

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            lote = await conn.fetchrow(
                """
                INSERT INTO cotas_import_lotes (
                    nome_arquivo, status, linhas_importadas, validas, invalidas, processadas
                )
                VALUES ($1, 'IMPORTADO', 0, 0, 0, 0)
                RETURNING id
                """,
                arquivo.filename,
            )

            lote_id = lote["id"]
            registros = []
            validas = 0
            invalidas = 0

            for idx, row in df.iterrows():
                linha = idx + 2

                codigo_raw = row.get("codigo")
                municipio = norm_text(row.get("municipio"))
                cota_raw = row.get("cota")
                cod_regiao_raw = row.get("cod_regiao")

                if (
                    pd.isna(codigo_raw)
                    and not municipio
                    and pd.isna(cota_raw)
                    and pd.isna(cod_regiao_raw)
                ):
                    continue

                erros = []

                try:
                    codigo = norm_int(codigo_raw)
                    if codigo is None:
                        erros.append("Código não informado")
                except Exception:
                    codigo = None
                    erros.append("Código inválido")

                try:
                    cota = norm_int(cota_raw)
                    if cota is None:
                        erros.append("Cota não informada")
                except Exception:
                    cota = None
                    erros.append("Cota inválida")

                try:
                    cod_regiao = norm_int(cod_regiao_raw)
                except Exception:
                    cod_regiao = None
                    erros.append("cod_regiao inválido")

                if not municipio:
                    erros.append("Município não informado")

                status = "PENDENTE" if not erros else "ERRO"

                if status == "PENDENTE":
                    validas += 1
                else:
                    invalidas += 1

                registros.append((
                    lote_id,
                    linha,
                    codigo,
                    municipio,
                    cota,
                    cod_regiao,
                    status,
                    "; ".join(erros) if erros else None,
                ))

            if registros:
                await conn.executemany(
                    """
                    INSERT INTO cotas_staging (
                        lote_id, linha_origem, codigo, municipio, cota,
                        cod_regiao, status, erro
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                    """,
                    registros
                )

            await conn.execute(
                """
                UPDATE cotas_import_lotes
                SET linhas_importadas = $2,
                    validas = $3,
                    invalidas = $4
                WHERE id = $1
                """,
                lote_id,
                len(registros),
                validas,
                invalidas
            )

    return {
        "ok": True,
        "lote_id": lote_id,
        "arquivo": arquivo.filename,
        "linhas_importadas": len(registros),
        "validas": validas,
        "invalidas": invalidas,
    }


@router.post("/importacoes/cotas/processar/{lote_id}")
async def processar_cotas(request: Request, lote_id: int):
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        lote = await conn.fetchrow(
            """
            SELECT *
            FROM cotas_import_lotes
            WHERE id = $1
            """,
            lote_id
        )

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado.")

        rows = await conn.fetch(
            """
            SELECT *
            FROM cotas_staging
            WHERE lote_id = $1
              AND status = 'PENDENTE'
            ORDER BY id
            """,
            lote_id
        )

        if not rows:
            raise HTTPException(status_code=400, detail="Lote sem linhas válidas para processar.")

        registros = [
            (
                r["codigo"],
                r["municipio"],
                r["cota"],
                r["cod_regiao"],
                lote_id,
            )
            for r in rows
        ]

        await conn.executemany(
            """
            INSERT INTO cotas_municipios (
                codigo, municipio, cota, cod_regiao, lote_id
            )
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (codigo)
            DO UPDATE SET
                municipio = EXCLUDED.municipio,
                cota = EXCLUDED.cota,
                cod_regiao = EXCLUDED.cod_regiao,
                lote_id = EXCLUDED.lote_id
            """,
            registros
        )

        await conn.execute(
            """
            UPDATE cotas_staging
            SET status = 'PROCESSADO',
                erro = NULL
            WHERE lote_id = $1
              AND status = 'PENDENTE'
            """,
            lote_id
        )

        await conn.execute(
            """
            UPDATE cotas_import_lotes
            SET status = 'PROCESSADO',
                processadas = $2,
                processado_em = NOW()
            WHERE id = $1
            """,
            lote_id,
            len(registros)
        )

    return {
        "ok": True,
        "lote_id": lote_id,
        "processadas": len(registros)
    }

@router.post("/importacoes/cr-planejamento")
async def importar_cr_planejamento(
    request: Request,
    arquivo: UploadFile = File(...)
):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo não informado.")

    nome = arquivo.filename.lower()
    if not (nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Envie um arquivo Excel .xlsx ou .xls.")

    conteudo = await arquivo.read()

    try:
        df = pd.read_excel(io.BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler Excel: {e}")

    df.columns = [
        str(c).replace("\xa0", " ").strip().lower()
        for c in df.columns
    ]

    colunas_obrigatorias = ["cr", "cod_financiamento"]

    faltantes = [c for c in colunas_obrigatorias if c not in df.columns]
    if faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"Colunas obrigatórias ausentes no Excel: {', '.join(faltantes)}"
        )

    pool = request.app.state.pool

    registros = []
    ignoradas = 0

    for _, row in df.iterrows():
        cr = norm_cr(row.get("cr"))

        if not cr:
            ignoradas += 1
            continue

        descricao = (
            norm_text(row.get("descricao"))
            or norm_text(row.get("descricao_cr"))
            or norm_text(row.get("desc_cr"))
        )

        cod_uo = None
        cod_programa = None
        cod_modalidade = None
        cod_formato = None
        cod_financiamento = None

        try:
            if "cod_uo" in df.columns and not pd.isna(row.get("cod_uo")):
                cod_uo = norm_int(row.get("cod_uo"))
        except Exception:
            pass

        try:
            if "cod_programa" in df.columns and not pd.isna(row.get("cod_programa")):
                cod_programa = norm_int(row.get("cod_programa"))
        except Exception:
            pass

        try:
            if "cod_modalidade" in df.columns and not pd.isna(row.get("cod_modalidade")):
                cod_modalidade = norm_int(row.get("cod_modalidade"))
        except Exception:
            pass

        try:
            if "cod_formato" in df.columns and not pd.isna(row.get("cod_formato")):
                cod_formato = norm_int(row.get("cod_formato"))
        except Exception:
            pass

        try:
            cod_financiamento = norm_int(row.get("cod_financiamento"))
        except Exception:
            cod_financiamento = None

        if cod_financiamento is None:
            ignoradas += 1
            continue

        registros.append((
            cr,
            descricao,
            cod_uo,
            cod_programa,
            cod_modalidade,
            cod_formato,
            cod_financiamento,
        ))

    async with pool.acquire() as conn:
        async with conn.transaction():
            if registros:
                await conn.executemany(
                    """
                    INSERT INTO cr_planejamento (
                        cr,
                        descricao,
                        cod_uo,
                        cod_programa,
                        cod_modalidade,
                        cod_formato,
                        cod_financiamento
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT (cr)
                    DO UPDATE SET
                        descricao = COALESCE(EXCLUDED.descricao, cr_planejamento.descricao),
                        cod_uo = COALESCE(EXCLUDED.cod_uo, cr_planejamento.cod_uo),
                        cod_programa = COALESCE(EXCLUDED.cod_programa, cr_planejamento.cod_programa),
                        cod_modalidade = COALESCE(EXCLUDED.cod_modalidade, cr_planejamento.cod_modalidade),
                        cod_formato = COALESCE(EXCLUDED.cod_formato, cr_planejamento.cod_formato),
                        cod_financiamento = COALESCE(EXCLUDED.cod_financiamento, cr_planejamento.cod_financiamento)
                    """,
                    registros
                )

            corrigidas = await conn.fetchval(
                """
                UPDATE ofertas_programas o
                SET cod_financiamento = cp.cod_financiamento
                FROM cr_planejamento cp
                WHERE cp.cr = o.cr
                  AND o.cod_financiamento IS NULL
                  AND cp.cod_financiamento IS NOT NULL
                RETURNING 1
                """
            )

    return {
        "ok": True,
        "arquivo": arquivo.filename,
        "linhas_lidas": len(df),
        "registros_processados": len(registros),
        "linhas_ignoradas": ignoradas,
        "observacao": "CRs atualizados em cr_planejamento e ofertas sem financiamento corrigidas quando possível."
    }

@router.get("/performance/programa/market-share-aprendizagem")
async def market_share_aprendizagem(
    request: Request,
    ano: int,
    mes: int,
    subregioes: str | None = None,
):
    pool = request.app.state.pool

    data_ini = date(ano, mes, 1)
    if mes == 12:
        data_fim = date(ano + 1, 1, 1) - timedelta(days=1)
    else:
        data_fim = date(ano, mes + 1, 1) - timedelta(days=1)

    params = [ano, mes]
    filtro_sub = ""

    if subregioes:
        ids = [int(x) for x in subregioes.split(",") if x.strip().isdigit()]
        if ids:
            params.append(ids)
            filtro_sub = "AND u.cod_subregiao = ANY($3::int[])"

    sql = f"""
    WITH cotas AS (
        SELECT
            cm.cod_regiao,
            SUM(COALESCE(cm.cota, 0)) AS nro_cotas
        FROM cotas_municipios cm
        GROUP BY cm.cod_regiao
    ),
    dados AS (
        SELECT
            sr.codigo_regiao AS cod_regiao,
            rg.nome AS regiao,

            COUNT(DISTINCT NULLIF(TRIM(da.cnpj), '')) AS cnpjs,

            (
                SELECT SUM(COALESCE(mm2.matriculados, 0))
                FROM turmas_movimento_mensal mm2
                JOIN turmas t2 ON t2.codigo = mm2.cod_turma
                JOIN uo u2 ON u2.codigo = t2.cod_uo
                LEFT JOIN subregioes sr2 ON sr2.codigo = u2.cod_subregiao
                JOIN programas p2 ON p2.codigo = t2.cod_programa
                WHERE UPPER(TRIM(p2.nome_programa)) = 'JOVEM APRENDIZ'
                AND mm2.ano = $1
                AND mm2.mes = $2
                AND sr2.codigo_regiao = sr.codigo_regiao
            ) AS aprendizes

        FROM turmas_movimento_mensal mm
        JOIN turmas t ON t.codigo = mm.cod_turma
        JOIN sge_turma_detalhe_alunos da
            ON da.cod_turma = t.codigo_sge
        AND da.status_matricula = 'MATRICULADO'
        JOIN uo u ON u.codigo = t.cod_uo
        LEFT JOIN subregioes sr ON sr.codigo = u.cod_subregiao
        LEFT JOIN regioes rg ON rg.codigo = sr.codigo_regiao
        JOIN programas p ON p.codigo = t.cod_programa

        WHERE UPPER(TRIM(p.nome_programa)) = 'JOVEM APRENDIZ'
        AND mm.ano = $1
        AND mm.mes = $2
        {filtro_sub}

        GROUP BY sr.codigo_regiao, rg.nome
    )
    SELECT
        COALESCE(d.regiao, rg.nome, 'Sem região') AS regiao,
        COALESCE(d.cnpjs, 0) AS cnpjs,
        COALESCE(d.aprendizes, 0) AS aprendizes,
        COALESCE(c.nro_cotas, 0) AS nro_cotas,
        CASE
            WHEN COALESCE(c.nro_cotas, 0) > 0
            THEN ROUND((COALESCE(d.aprendizes, 0)::numeric * 100) / c.nro_cotas, 2)
            ELSE 0
        END AS market_share
    FROM cotas c
    LEFT JOIN regioes rg ON rg.codigo = c.cod_regiao
    LEFT JOIN dados d ON d.cod_regiao = c.cod_regiao
    ORDER BY regiao
    """

    sql_cards = f"""
    WITH base AS (
        SELECT
            COUNT(DISTINCT NULLIF(TRIM(da.cnpj), '')) AS total_cnpjs,
            (
                SELECT SUM(COALESCE(mm2.matriculados, 0))
                FROM turmas_movimento_mensal mm2
                JOIN turmas t2 ON t2.codigo = mm2.cod_turma
                JOIN programas p2 ON p2.codigo = t2.cod_programa
                JOIN uo u2 ON u2.codigo = t2.cod_uo
                WHERE UPPER(TRIM(p2.nome_programa)) = 'JOVEM APRENDIZ'
                AND mm2.ano = $1
                AND mm2.mes = $2
                {filtro_sub.replace("u.cod_subregiao", "u2.cod_subregiao")}
            ) AS total_aprendizes
        FROM turmas_movimento_mensal mm
        JOIN turmas t ON t.codigo = mm.cod_turma
        JOIN sge_turma_detalhe_alunos da
            ON da.cod_turma = t.codigo_sge
        AND da.status_matricula = 'MATRICULADO'
        JOIN programas p ON p.codigo = t.cod_programa
        JOIN uo u ON u.codigo = t.cod_uo
        WHERE UPPER(TRIM(p.nome_programa)) = 'JOVEM APRENDIZ'
        AND mm.ano = $1
        AND mm.mes = $2
        {filtro_sub}
    ),
    cotas AS (
        SELECT SUM(COALESCE(cm.cota, 0)) AS total_cotas
        FROM cotas_municipios cm
        JOIN regioes rg ON rg.codigo = cm.cod_regiao
        WHERE 1 = 1
    )
    SELECT
        COALESCE(base.total_cnpjs, 0) AS total_cnpjs,
        COALESCE(base.total_aprendizes, 0) AS total_aprendizes,
        COALESCE(cotas.total_cotas, 0) AS total_cotas,
        CASE
            WHEN COALESCE(cotas.total_cotas, 0) > 0
            THEN ROUND((COALESCE(base.total_aprendizes, 0)::numeric * 100) / cotas.total_cotas, 2)
            ELSE 0
        END AS market_share_total
    FROM base, cotas
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
        cards = await conn.fetchrow(sql_cards, *params)

    linhas = [dict(r) for r in rows]

    cards_dict = dict(cards) if cards else {
        "market_share_total": 0,
        "total_cotas": 0,
        "total_aprendizes": 0,
        "total_cnpjs": 0,
    }

    cards_dict["total_cnpjs"] = sum((r.get("cnpjs") or 0) for r in linhas)

    return {
        "cards": cards_dict,
        "linhas": linhas
    }