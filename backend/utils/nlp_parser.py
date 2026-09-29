# utils/nlp_parser.py

import re

def detectar_adicionais_na_frase(obs_temp, opcoes, aliases_por_nome, max_esc, func_remover_acentos):
    """
    Varre a observação em busca de opções e quantidades explícitas.
    Retorna uma tupla: (lista_de_opcoes_encontradas, observacao_mascarada)
    """
    itens_detectados = []
    
    for op in opcoes:
        nome_op = func_remover_acentos(op["nome"].lower())
        
        # Monta lista de termos para buscar (Nome Oficial + Apelidos)
        termos_busca = [nome_op]
        if nome_op in aliases_por_nome:
            termos_busca.extend(aliases_por_nome[nome_op])
            
        termos_busca.sort(key=len, reverse=True) # Prioriza termos maiores
        
        for termo_atual in termos_busca:
            pattern = rf"(?:(\d+)\s*(?:x|vezes|unidades)?\s*(?:de)?\s*)?(?:\b(?:adicionar|adicional|extra|com|mais)\s+(?:de\s+)?)?{re.escape(termo_atual)}\b"
            
            while True:
                match = re.search(pattern, obs_temp)
                if not match:
                    break
                    
                start, end = match.span()
                prefix_context = obs_temp[:start].strip().lower()
                
                # --- PROTEÇÃO CONTRA FALSOS POSITIVOS ---
                termos_compostos_proibidos = ["anel de", "aneis de", "creme de", "doce de", "paçoca de", "bala de", "molho de"]
                eh_falso_positivo = any(prefix_context.endswith(p) and p not in termo_atual for p in termos_compostos_proibidos)
                
                if eh_falso_positivo:
                    obs_temp = obs_temp[:start] + (" " * (end - start)) + obs_temp[end:]
                    continue
                # ----------------------------------------
                
                qtd_match = int(match.group(1)) if match.group(1) else 1
                is_explicit = bool(match.group(1))
                
                if not (prefix_context.endswith("sem") or prefix_context.endswith("no")):
                    itens_detectados.append({"qtd": qtd_match, "explicit": is_explicit, "op": op})
                    
                obs_temp = obs_temp[:start] + " " + obs_temp[end:]
                
    # Deduplicação (Prioridade Explícita)
    itens_finais = []
    agrupados = {}
    for d in itens_detectados:
        agrupados.setdefault(d["op"]["id"], []).append(d)
        
    for oid, lista in agrupados.items():
        tem_explicito = any(x["explicit"] for x in lista)
        total_add = sum(x["qtd"] for x in lista if x["explicit"]) if tem_explicito else sum(x["qtd"] for x in lista)
        
        op_obj = lista[0]["op"]
        for _ in range(total_add):
            if len(itens_finais) < max_esc:
                itens_finais.append(op_obj)
            else:
                break
                
    return itens_finais, obs_temp


def limpar_observacao_pos_extracao(obs_temp):
    """Remove sujeiras, verbos soltos e conectores após a extração dos itens."""
    clean_pattern = r"\b(adicionar|adicional de|adicionais|adicional|extra|com|mais|e|quero|colocar|pode|por|favor)\b"
    obs_temp = re.sub(clean_pattern, " ", obs_temp, flags=re.IGNORECASE)
    obs_temp = obs_temp.replace("|", " ").replace("/", " ")
    return re.sub(r"\s+", " ", obs_temp).strip(" ,.|-")


def expandir_multiplicadores(texto):
    """Expande strings como '3x queijo' para 'queijo queijo queijo'."""
    def repl(m):
        qtd = min(int(m.group(1)), 10) # Limite de segurança de 10
        return " ".join([m.group(2)] * qtd)
    return re.sub(r"\b(\d+)\s*(?:[xX*]|vezes)\s*([\w]+)", repl, texto, flags=re.IGNORECASE)