# utils/smart_search.py

import re
import difflib

def normalizar_tamanho_fuzzy(tamanho_raw, variacoes_db):
    """Converte '8 fatias' ou 'P' no nome oficial da variação (ex: Grande)."""
    if not tamanho_raw: return None
    t_raw = str(tamanho_raw).lower().strip()
    
    t_raw_clean = t_raw.replace("fatias", "").replace("fatia", "").replace("pedacos", "").replace("pedaços", "").replace("cm", "").strip()

    # 1. Busca Exata
    for v in variacoes_db:
        if v["nome"].lower() == t_raw: return v["nome"]

    # 2. Busca Numérica (Fatias ou CM)
    if t_raw_clean.isdigit():
        val_num = int(t_raw_clean)
        for v in variacoes_db:
            if v.get("fatias") and int(v["fatias"]) == val_num: return v["nome"]
            cm_db = str(v.get("tamanho_cm", "")).lower().replace("cm", "").strip()
            if cm_db.isdigit() and int(cm_db) == val_num: return v["nome"]

    # 3. Mapa de Siglas/Apelidos
    mapa_siglas = {}
    for v in variacoes_db:
        nome = v["nome"].lower()
        if v.get("sigla"): mapa_siglas[v["sigla"].lower()] = v["nome"]
        
        # Fallback Heurístico
        if "pequena" in nome or "broto" in nome: mapa_siglas.setdefault("p", v["nome"])
        elif "media" in nome or "média" in nome: mapa_siglas.setdefault("m", v["nome"])
        elif "grande" in nome: mapa_siglas.setdefault("g", v["nome"])
        elif "familia" in nome or "família" in nome: mapa_siglas.setdefault("f", v["nome"])
        elif "gigante" in nome: mapa_siglas.setdefault("gg", v["nome"])

    apelidos = {"peq": "p", "med": "m", "grd": "g", "fam": "f", "gig": "gg"}
    chave_busca = apelidos.get(t_raw, t_raw)
    if chave_busca in mapa_siglas: return mapa_siglas[chave_busca]

    # 4. Fuzzy
    for v in variacoes_db:
        if t_raw in v["nome"].lower(): return v["nome"]

    return tamanho_raw.title()


def motor_busca_produto(produtos_db, nome_busca, func_remover_acentos):
    """
    Busca um produto na lista de produtos do DB usando match exato, parcial ou Fuzzy.
    Retorna 1 dicionário (se exato), uma Lista (se ambíguo) ou None.
    """
    nome_clean = func_remover_acentos(str(nome_busca).lower().strip()).replace("-", " ")
    
    # 1. Match Exato
    for p in produtos_db:
        p_nome_clean = func_remover_acentos(str(p["nome"]).lower()).replace("-", " ")
        if p_nome_clean == nome_clean:
            return p
            
    # 2. Match Parcial (Retorna lista para resolver ambiguidade depois)
    candidatos = []
    for p in produtos_db:
        p_nome_clean = func_remover_acentos(str(p["nome"]).lower()).replace("-", " ")
        if nome_clean in p_nome_clean:
            candidatos.append(p)
            
    if len(candidatos) > 1: return candidatos
    if len(candidatos) == 1: return candidatos[0]

    # 3. Match Fuzzy (Adivinhação de erros de digitação)
    mapa = {func_remover_acentos(str(p["nome"]).lower()): p for p in produtos_db}
    matches = difflib.get_close_matches(nome_clean, list(mapa.keys()), n=1, cutoff=0.85)
    if matches:
        return mapa[matches[0]]
        
    return None


def resolver_sabores_pizza_avancado(sabores_raw, db_pizzas, db_apelidos, func_remover_acentos):
    """
    Recebe sabores da IA e retorna uma lista de sabores reais do banco.
    Possui heurística para não quebrar nomes compostos como "Calabresa com Bacon".
    """
    if not sabores_raw: return [], []
    
    nomes_validos = {func_remover_acentos(str(p["nome"]).lower()): p for p in db_pizzas}
    mapa_alias = {}
    for r in db_apelidos:
        if r.get("apelido"):
            mapa_alias[func_remover_acentos(str(r["apelido"]).lower())] = r["sabor_produto_id"]
            
    mapa_id_para_nome = {p["id"]: p["nome"] for p in db_pizzas}
    
    validos = []
    invalidos = []

    def tentar_match(termo):
        t_clean = func_remover_acentos(termo.lower())
        t_clean = re.sub(r"\b(pizza|de|sabor)\b", "", t_clean).strip()
        if not t_clean: return None
        
        # 1. Match Exato no Nome
        if t_clean in nomes_validos:
            return nomes_validos[t_clean]
            
        # 2. Match Exato no Apelido
        if t_clean in mapa_alias:
            pid = mapa_alias[t_clean]
            if pid in mapa_id_para_nome:
                nome_recuperado = mapa_id_para_nome[pid]
                chave_nome = func_remover_acentos(str(nome_recuperado).lower())
                return nomes_validos.get(chave_nome)
                
        # 3. Fuzzy Match no Banco
        matches = difflib.get_close_matches(t_clean, list(nomes_validos.keys()), n=1, cutoff=0.85)
        if matches:
            return nomes_validos[matches[0]]
            
        return None

    def resolver_parte(parte_str):
        # Tenta encontrar a string inteira primeiro (Ex: "Calabresa com Bacon")
        match_data = tentar_match(parte_str)
        if match_data: return [match_data]
        
        # Se a string inteira falhou, aí sim tenta separar pela palavra "com"
        # (Útil caso o cliente tenha dito "Frango com Calabresa" e isso não seja um sabor único)
        sub_partes = re.split(r"(?:\s+com\s+)", parte_str, flags=re.IGNORECASE)
        sub_partes = [p.strip() for p in sub_partes if p.strip()]
        
        if len(sub_partes) > 1:
            resultados = []
            for sp in sub_partes:
                match_sp = tentar_match(sp)
                if match_sp: 
                    resultados.append(match_sp)
                else: 
                    return [] # Se falhar algum pedaço, aborta a separação
            return resultados
            
        return []

    for s in sabores_raw:
        s_str = str(s).strip()
        if not s_str: continue
        
        # Quebra primária segura: Quebra por "e", "+", ",", "/" (MAS NÃO POR "com")
        partes_seguras = re.split(r"(?:\s+e\s+|\s*\/\s*|\s*\+\s*|,\s*)", s_str, flags=re.IGNORECASE)
        partes_seguras = [p.strip() for p in partes_seguras if p.strip()]
        
        for parte in partes_seguras:
            resultados = resolver_parte(parte)
            if resultados:
                for r in resultados:
                    if r.get("disponivel", 1) == 0:
                        invalidos.append(f"{r['nome']} (Esgotado)")
                    else:
                        if r["nome"] not in validos:
                            validos.append(r["nome"])
            else:
                invalidos.append(parte.title())
                
    return validos, invalidos