// Variável Global para controlar qual Receita (Pai) está selecionada
let currentFichaId = null;
let currentFichaNome = "";

// ==========================================
// FUNÇÕES UTILITÁRIAS GERAIS E MENSAGENS
// ==========================================
function safeVal(val) {
    if (val === null || val === undefined) return '-';
    let s = String(val).trim().toLowerCase();
    if (s === 'null' || s === 'none' || s === '') return '-';
    return val;
}

function safeEdit(val) {
    if (val === null || val === undefined) return '';
    let s = String(val).trim().toLowerCase();
    if (s === 'null' || s === 'none') return '';
    return val;
}

function showMsgProd(text) {
    const painel = document.createElement('div');
    painel.style.cssText = "position:fixed; top:20px; right:20px; background:#111; border: 2px solid #00ffcc; padding: 15px 20px; border-radius: 8px; z-index:9999; color: #fff; text-align: left; box-shadow: 0 0 20px rgba(0, 255, 204, 0.4); font-size: 14px;";
    painel.innerHTML = `<strong>Aviso do Sistema:</strong><br><br>${text} <br><br><button onclick="this.parentElement.remove()" class="btn-neon btn-neon-danger bg-transparent p-5" style="width:100%">Fechar</button>`;
    document.body.appendChild(painel);
    setTimeout(() => { if (painel.parentElement) painel.remove(); }, 5000);
}

// ==========================================
// SISTEMA DE MODAIS (CADASTRO / EDIÇÃO)
// ==========================================
function openModalProd(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.style.display = 'flex';
}

function closeModalProd(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.style.display = 'none';
}

window.novoCadastroProd = function(formId) {
    limparFormProd(formId);
    if (formId === 'form_fichas') {
        currentFichaId = null;
        currentFichaNome = "";
        refreshFichaBadge();
    }
    openModalProd(formId);
}

function limparFormProd(formId) {
    const form = document.getElementById(formId);
    if(form) {
        form.reset();
        const idField = form.querySelector('input[type="hidden"]');
        if(idField) idField.value = '';
    }
}

function serializeForm(formId, prefix) {
    const inputs = document.querySelectorAll(`#${formId} input:not(.ignore-serialize), #${formId} select:not(.ignore-serialize), #${formId} textarea:not(.ignore-serialize)`);
    const payload = {};
    inputs.forEach(input => {
        let key = input.id.replace(prefix, '');
        if(key) payload[key] = input.value;
    });
    return payload;
}

// ==========================================
// CONTROLE DO MENU LATERAL E CARGAS DE DADOS
// ==========================================
function switchProdView(viewId, btnElement) {
    document.querySelectorAll('.erp-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(btn => btn.classList.remove('active'));
    
    const target = document.getElementById(viewId);
    if (target) {
        target.classList.add('active');
        btnElement.classList.add('active');
    }

    // Persistência ao recarregar a página
    localStorage.setItem('lastProdView', viewId);

    if(viewId === 'view_ordens') loadOrdens();
    if(viewId === 'view_composicoes') loadFichas();
    if(viewId === 'view_insumos') loadInsumos();
}

async function loadDropdownsProducao() {
    try {
        const res = await fetch('/api/producao/opcoes_formularios');
        const data = await res.json();
        
        let htmlUn = '<option value="">-- Selecione a Unidade --</option>';
        if(data.unidades) {
            data.unidades.forEach(u => htmlUn += `<option value="${u.nome}">${u.nome} - ${u.descricao}</option>`);
        }
        document.querySelectorAll('.ddl-unidades').forEach(el => el.innerHTML = htmlUn);
        window.optUnidades = htmlUn;

        let htmlForn = '<option value="">-- Selecione o Fornecedor --</option>';
        if(data.fornecedores) {
            data.fornecedores.forEach(f => htmlForn += `<option value="${f.id}">${f.nome}</option>`);
        }
        document.querySelectorAll('.ddl-fornecedores').forEach(el => el.innerHTML = htmlForn);

    } catch(e) { console.warn("Erro ao carregar opções básicas."); }

    try {
        const resUsr = await fetch('/api/cadastros/funcionarios');
        const dataUsr = await resUsr.json();
        let htmlUsr = '<option value="">-- Selecione o Responsável --</option>';
        dataUsr.forEach(u => htmlUsr += `<option value="${u.nome}">${u.nome}</option>`);
        document.querySelectorAll('.ddl-responsaveis').forEach(el => el.innerHTML = htmlUsr);
    } catch(e) { console.warn("Erro ao carregar responsáveis (funcionários).", e); }
    
    try {
        const resFichas = await fetch('/api/producao/fichas_tecnicas');
        const dataFichas = await resFichas.json();
        let htmlFichas = '<option value="">-- Selecione a Ficha / Receita --</option>';
        dataFichas.forEach(f => {
            const nome = safeEdit(f.produto_pai_nome || f.produto_final_nome || `Ficha #${f.id}`);
            const prodId = safeEdit(f.produto_id || f.produto_pai_id || f.produto_final_id);
            htmlFichas += `<option value="${f.id}" data-prod-id="${prodId}" data-prod-nome="${nome.replace(/"/g, '&quot;')}">${nome}</option>`;
        });
        document.querySelectorAll('.ddl-fichas-op').forEach(el => el.innerHTML = htmlFichas);
    } catch(e) { console.warn("Erro ao carregar fichas no dropdown."); }

    await loadInsumosDropdown();
}

async function loadInsumosDropdown() {
    try {
        const res = await fetch('/api/producao/insumos');
        const data = await res.json();
        
        let htmlIns = '<option value="">-- Selecione o Insumo --</option>';
        let htmlInsOp = '<option value="">-- Selecione o Insumo --</option>';
        
        data.forEach(i => {
            htmlIns += `<option value="${i.id}" data-nome="${safeEdit(i.nome).replace(/"/g, '&quot;')}" data-unidade="${safeEdit(i.unidade_medida)}" data-custo="${safeEdit(i.custo_unitario)}">${i.nome}</option>`;
            htmlInsOp += `<option value="${safeEdit(i.nome).replace(/"/g, '&quot;')}" data-unidade="${safeEdit(i.unidade_medida)}">${i.nome}</option>`;
        });
        
        window.optInsumos = htmlIns;
        window.optInsumosOp = htmlInsOp;
        
        document.querySelectorAll('.ddl-insumos').forEach(el => {
            const currentVal = el.value;
            el.innerHTML = htmlIns;
            el.value = currentVal;
        });
        
        document.querySelectorAll('.ddl-insumos-op').forEach(el => {
            const currentVal = el.value;
            el.innerHTML = htmlInsOp;
            el.value = currentVal;
        });
    } catch(e) { console.warn("Erro ao carregar dropdown de insumos."); }
}

document.addEventListener("DOMContentLoaded", async () => {
    await loadDropdownsProducao();
    
    // Restaura a aba através da persistência do F5
    let lastView = localStorage.getItem('lastProdView') || 'view_ordens';
    let btn = document.querySelector(`button[onclick*="${lastView}"]`);
    
    if(btn) {
        switchProdView(lastView, btn);
    } else {
        let firstBtn = document.querySelector('.menu-item');
        if(firstBtn) switchProdView('view_ordens', firstBtn);
    }
});


// ==========================================
// MÉTODOS CRUD GENÉRICOS (API)
// ==========================================
async function postRecordProd(tabela, payload, formId) {
    try {
        const res = await fetch(`/api/producao/${tabela}`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify(payload) 
        });
        
        if (!res.ok) {
            const errData = await res.json();
            showMsgProd('Falha ao guardar os dados no servidor:\n' + (errData.erro || 'Erro desconhecido.'));
            return false;
        }

        const data = await res.json();
        
        if(data.sucesso !== false) { 
            limparFormProd(formId); 
            return true; 
        }
        
        showMsgProd('Erro ao salvar os dados: ' + (data.erro || 'Erro desconhecido BD')); 
        return false;
    } catch(e) { 
        console.error(e);
        showMsgProd('Falha de rede ou sistema indisponível.'); 
        return false; 
    }
}

async function deleteRecordProd(tabela, id, callback) {
    if(!confirm("Tem certeza que deseja excluir o registro?")) return;
    try {
        const res = await fetch(`/api/producao/${tabela}/${id}`, { method: 'DELETE' });
        if(res.ok) callback();
    } catch(e) {}
}


// ==========================================
// CADASTRO DE INSUMOS / MATÉRIAS-PRIMAS
// ==========================================
window.salvarInsumo = async function(e) {
    e.preventDefault();
    const payload = serializeForm('form_insumos', 'ins_');
    if(await postRecordProd('insumos', payload, 'form_insumos')) {
        closeModalProd('form_insumos');
        showMsgProd("Insumo guardado com sucesso!");
        loadInsumos();
    }
};

window.dispatchEditInsumo = function(encoded) {
    const itemObj = JSON.parse(decodeURIComponent(encoded));
    limparFormProd('form_insumos');
    for (const [key, value] of Object.entries(itemObj)) {
        const el = document.getElementById('ins_' + key);
        if (el) el.value = safeEdit(value);
    }
    openModalProd('form_insumos');
};

async function loadInsumos() {
    try {
        const res = await fetch('/api/producao/insumos'); const data = await res.json();
        const tb = document.getElementById('tb_insumos'); tb.innerHTML = '';
        data.forEach(i => {
            const enc = encodeURIComponent(JSON.stringify(i));
            tb.innerHTML += `<tr>
                <td class="font-bold text-info">#${i.id}</td>
                <td>${safeVal(i.nome)}</td>
                <td>${safeVal(i.unidade_medida)}</td>
                <td class="text-success">R$ ${safeVal(i.custo_unitario)}</td>
                <td>${safeVal(i.estoque_atual)}</td>
                <td class="text-center">
                    <button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditInsumo('${enc}')">✏️</button> 
                    <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordProd('insumos', ${i.id}, loadInsumos)">🗑️</button>
                </td>
            </tr>`; 
        });
        loadInsumosDropdown(); 
    } catch(e) {}
}


// ==========================================
// ORDENS DE PRODUÇÃO (OP) E GRELHA
// ==========================================
window.preencherProdutoPorFicha = function(sel) {
    const opt = sel.options[sel.selectedIndex];
    if(opt && opt.value) {
        const prodId = opt.getAttribute('data-prod-id');
        const prodNome = opt.getAttribute('data-prod-nome');
        
        if(prodId && prodId !== 'undefined' && prodId !== 'null') {
            document.getElementById('op_produto_id').value = prodId;
        }
        if(prodNome && prodNome !== 'undefined' && prodNome !== 'null') {
            document.getElementById('op_produto_nome').value = prodNome;
        }
    }
};

window.addRowOP = function() {
    const tb = document.getElementById('tb_itens_op');
    const cols = `
        <td><select class="erp-select ignore-serialize ddl-insumos-op" onchange="updateOpRow(this)">${window.optInsumosOp || '<option value="">-- Selecione --</option>'}</select></td>
        <td><input type="number" class="erp-input ignore-serialize" step="0.01"></td>
        <td><select class="erp-select ignore-serialize">${window.optUnidades || '<option value="">-- Selecione --</option>'}</select></td>
        <td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="this.closest('tr').remove()">X</button></td>
    `;
    tb.insertAdjacentHTML('beforeend', `<tr>${cols}</tr>`);
};

window.updateOpRow = function(sel) {
    const opt = sel.options[sel.selectedIndex];
    const tr = sel.closest('tr');
    const unSel = tr.querySelectorAll('select')[1];
    if(unSel && opt && opt.getAttribute('data-unidade')) {
        unSel.value = opt.getAttribute('data-unidade');
    }
};

function extrairGridJson(tableId, chaves) {
    const tb = document.getElementById(tableId);
    if(!tb) return "[]";
    const data = [];
    tb.querySelectorAll('tr').forEach(tr => {
        const inputs = tr.querySelectorAll('input, select');
        if(inputs.length === 0) return;
        let obj = {};
        let temValor = false;
        chaves.forEach((k, idx) => { 
            if(inputs[idx]) { obj[k] = inputs[idx].value; if(inputs[idx].value) temValor = true; } 
        });
        if(temValor) data.push(obj);
    });
    return JSON.stringify(data);
}

function renderizarGrid(tableId, dataArray) {
    const tb = document.getElementById(tableId);
    if(!tb) return;
    tb.innerHTML = '';
    if (!dataArray || dataArray.length === 0) return;

    dataArray.forEach(row => {
        const cols = `
            <td><select class="erp-select ignore-serialize ddl-insumos-op" onchange="updateOpRow(this)" data-val="${safeEdit(row.produto)}">${window.optInsumosOp || '<option value="">-- Selecione --</option>'}</select></td>
            <td><input type="number" value="${safeEdit(row.qtd)}" class="erp-input ignore-serialize" step="0.01"></td>
            <td><select class="erp-select ignore-serialize" data-val="${safeEdit(row.unidade)}">${window.optUnidades || '<option value="">-- Selecione --</option>'}</select></td>
            <td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="this.closest('tr').remove()">X</button></td>
        `;
        tb.insertAdjacentHTML('beforeend', `<tr>${cols}</tr>`);
        
        const lastRow = tb.lastElementChild;
        const selects = lastRow.querySelectorAll('select');
        selects.forEach(sel => {
            if(sel.getAttribute('data-val')) sel.value = sel.getAttribute('data-val');
        });
    });
}

window.salvarProd = async function(e, tabela) {
    e.preventDefault();
    const payload = serializeForm('form_ordens', 'op_');
    
    // Espelha valores solicitados para compatibilidade BD
    if(payload.data) payload.data_emissao = payload.data;
    if(payload.qtd_planejada) payload.quantidade_planejada = payload.qtd_planejada;
    if(payload.qtd_produzida) payload.quantidade_produzida = payload.qtd_produzida;
    if(payload.custo_total) payload.custo_realizado = payload.custo_total;
    if(payload.notas) payload.anotacoes = payload.notas;

    payload.itens_consumidos_json = extrairGridJson('tb_itens_op', ['produto', 'qtd', 'unidade']);
    
    if(await postRecordProd('ordens_producao', payload, 'form_ordens')) {
        closeModalProd('form_ordens');
        showMsgProd("Ordem de Produção guardada com sucesso!");
        loadOrdens();
    }
};

window.dispatchEditOP = function(encoded) {
    const itemObj = JSON.parse(decodeURIComponent(encoded));
    limparFormProd('form_ordens');
    for (const [key, value] of Object.entries(itemObj)) {
        const el = document.getElementById('op_' + key);
        if (el) el.value = safeEdit(value);
    }
    if(itemObj.itens_consumidos_json) renderizarGrid('tb_itens_op', JSON.parse(itemObj.itens_consumidos_json));
    
    openModalProd('form_ordens');
};

async function loadOrdens() {
    try {
        const res = await fetch('/api/producao/ordens_producao'); const data = await res.json();
        const tb = document.getElementById('tb_ordens'); tb.innerHTML = '';
        data.forEach(i => {
            const enc = encodeURIComponent(JSON.stringify(i));
            tb.innerHTML += `<tr><td class="font-bold text-warning">${safeVal(i.numero)}</td><td>${safeVal(i.data || i.data_emissao)}</td><td class="text-info">${safeVal(i.produto_nome)}</td><td>${safeVal(i.qtd_planejada || i.quantidade_planejada)}</td><td>${safeVal(i.qtd_produzida || i.quantidade_produzida)}</td><td>${safeVal(i.status)}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditOP('${enc}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordProd('ordens_producao', ${i.id}, loadOrdens)">🗑️</button></td></tr>`; 
        });
    } catch(e) {}
}


// ==========================================
// FICHAS TÉCNICAS E RECEITUÁRIO (BOM)
// ==========================================
async function loadFichas() {
    try {
        const res = await fetch('/api/producao/fichas_tecnicas'); const data = await res.json();
        const tb = document.getElementById('tb_fichas'); tb.innerHTML = '';
        data.forEach(i => {
            const enc = encodeURIComponent(JSON.stringify(i));
            tb.innerHTML += `<tr>
                <td class="text-warning font-bold cursor-pointer" onclick="dispatchEditFicha('${enc}')">${safeVal(i.produto_pai_nome || i.produto_final_nome)}</td>
                <td>${safeVal(i.rendimento_padrao || i.rendimento)}</td>
                <td class="text-success font-bold">R$ ${parseFloat(i.custo_total_estimado || 0).toFixed(2)}</td>
                <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditFicha('${enc}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordProd('fichas_tecnicas', ${i.id}, loadFichas)">🗑️</button></td>
            </tr>`; 
        });
        if(!currentFichaId) document.getElementById('tb_ficha_itens').innerHTML = '<tr><td colspan="6" class="text-center text-muted">Selecione uma Receita Pai primeiro.</td></tr>';
    } catch(e) {}
}

window.dispatchEditFicha = function(encoded) {
    const itemObj = JSON.parse(decodeURIComponent(encoded));
    limparFormProd('form_fichas');
    for (const [key, value] of Object.entries(itemObj)) {
        const el = document.getElementById('fch_' + key);
        if (el) el.value = safeEdit(value);
    }
    
    // Carrega a segunda parte do modal baseada na seleção
    selecionarFicha(itemObj.id, itemObj.produto_pai_nome || itemObj.produto_final_nome);
    openModalProd('form_fichas');
};

window.salvarFichaPai = async function(e) {
    e.preventDefault();
    const payload = serializeForm('form_fichas', 'fch_');
    
    // Espelha valores para manter compatibilidade com nomenclaturas antigas
    if(payload.produto_pai_nome) payload.produto_final_nome = payload.produto_pai_nome;
    if(payload.produto_pai_id) payload.produto_final_id = payload.produto_pai_id;
    if(payload.rendimento_padrao) payload.rendimento = payload.rendimento_padrao;
    if(payload.tempo_preparo) payload.tempo_preparo_min = payload.tempo_preparo;
    if(payload.instrucoes) payload.descricao = payload.instrucoes;

    if(await postRecordProd('fichas_tecnicas', payload, 'form_fichas')) {
        currentFichaId = null;
        refreshFichaBadge();
        loadFichas();
        loadDropdownsProducao();
        
        closeModalProd('form_fichas');
        showMsgProd("Ficha / Receita Base guardada com sucesso! Utilize o botão de edição na lista para inserir ingredientes.");
    }
};

window.selecionarFicha = function(id, nome) {
    currentFichaId = id;
    currentFichaNome = nome;
    document.getElementById('fci_ficha_id').value = id;
    refreshFichaBadge();
    loadFichaItens(id);
};

window.updateFichaItemName = function(sel) {
    const opt = sel.options[sel.selectedIndex];
    if(opt && opt.value) {
        document.getElementById('fci_produto_filho_nome').value = opt.getAttribute('data-nome') || '';
        document.getElementById('fci_unidade').value = opt.getAttribute('data-unidade') || '';
        document.getElementById('fci_custo_unitario').value = opt.getAttribute('data-custo') || '0';
        calcSubFichaItem();
    }
};

window.calcSubFichaItem = function() {
    const qtd = parseFloat(document.getElementById('fci_qtd_necessaria').value) || 0;
    const vlr = parseFloat(document.getElementById('fci_custo_unitario').value) || 0;
    document.getElementById('fci_subtotal').value = (qtd * vlr).toFixed(2);
};

function refreshFichaBadge() {
    const badge = document.getElementById('ficha_badge');
    const formItens = document.getElementById('form_ficha_itens');
    if(currentFichaId) {
        badge.style.display = 'block';
        badge.innerText = `Inclusão Liberada para: ${currentFichaNome}`;
        formItens.style.opacity = '1';
        formItens.style.pointerEvents = 'auto';
    } else {
        badge.style.display = 'none';
        formItens.style.opacity = '0.5';
        formItens.style.pointerEvents = 'none';
        document.getElementById('tb_ficha_itens').innerHTML = '<tr><td colspan="6" class="text-center text-muted">Aguardando registo do Produto Pai.</td></tr>';
    }
}

async function atualizarCustoFichaSilencioso(ficha_id, custoTotal) {
    try {
        await fetch(`/api/producao/fichas_tecnicas`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: ficha_id, custo_total_estimado: custoTotal })
        });
        loadFichas(); // Recarrega lista sutilmente ao fundo
    } catch(e) {}
}

async function loadFichaItens(ficha_id) {
    try {
        const res = await fetch(`/api/producao/fichas_itens/${ficha_id}`); 
        const data = await res.json();
        const tb = document.getElementById('tb_ficha_itens'); tb.innerHTML = '';
        
        let custoTotalParent = 0;

        if(data.length === 0) {
            tb.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nenhum ingrediente cadastrado nesta receita.</td></tr>';
            document.getElementById('fch_custo_total_estimado').value = "0.00";
            atualizarCustoFichaSilencioso(ficha_id, 0.00); 
            return;
        }

        data.forEach(i => {
            custoTotalParent += parseFloat(i.subtotal || 0);
            tb.innerHTML += `<tr>
                <td class="text-info">${safeVal(i.produto_filho_nome)}</td>
                <td>${safeVal(i.qtd_necessaria)}</td>
                <td>${safeVal(i.unidade)}</td>
                <td>${safeVal(i.custo_unitario)}</td>
                <td class="font-bold">R$ ${parseFloat(i.subtotal || 0).toFixed(2)}</td>
                <td class="text-center"><button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordProd('fichas_itens', ${i.id}, () => loadFichaItens(${ficha_id}))">🗑️</button></td>
            </tr>`;
        });

        const elTotalPai = document.getElementById('fch_custo_total_estimado');
        if(elTotalPai) elTotalPai.value = custoTotalParent.toFixed(2);
        
        atualizarCustoFichaSilencioso(ficha_id, custoTotalParent.toFixed(2));
        
    } catch(e) {}
}

window.salvarFichaItem = async function(e) {
    e.preventDefault();
    if(!currentFichaId) return;
    const payload = serializeForm('form_ficha_itens', 'fci_');
    if(await postRecordProd('fichas_itens', payload, 'form_ficha_itens')) {
        document.getElementById('fci_ficha_id').value = currentFichaId; 
        loadFichaItens(currentFichaId);
    }
};

// ==========================================
// MODAL DE PESQUISA INTELIGENTE (PRODUÇÃO)
// ==========================================
let cPesq = { ent: '', idInput: '', nomeInput: '' };

window.abrirPesq = function(entidade, idInput, nomeInput) {
    cPesq = { ent: entidade, idInput: idInput, nomeInput: nomeInput };
    document.getElementById('mpesq_titulo').innerText = `Buscar ${entidade.toUpperCase()}`;
    document.getElementById('mpesq_input').value = '';
    document.getElementById('mpesq_resultados').innerHTML = '<tr><td colspan="3" class="text-center text-muted">Aguardando busca...</td></tr>';
    document.getElementById('modal_pesquisa_prod').style.display = 'flex';
}

window.fecharPesquisa = function() {
    document.getElementById('modal_pesquisa_prod').style.display = 'none';
}

window.executarPesquisa = async function() {
    const q = document.getElementById('mpesq_input').value;
    const tb = document.getElementById('mpesq_resultados');
    tb.innerHTML = '<tr><td colspan="3" class="text-center text-info">Buscando...</td></tr>';
    
    try {
        const res = await fetch(`/api/producao/pesquisar/${cPesq.ent}?q=${q}`); 
        const data = await res.json();
        
        tb.innerHTML = data.map(i => `<tr>
            <td class="text-muted">#${i.id}</td>
            <td class="text-white font-bold">${i.nome}</td>
            <td class="text-center">
                <button type="button" class="btn-neon btn-neon-success" style="padding:2px 8px; font-size:0.7rem;" onclick="selecPesq(${i.id}, '${i.nome.replace(/'/g,"\\'")}')">✔ Selecionar</button>
            </td>
        </tr>`).join('') || '<tr><td colspan="3" class="text-center text-danger">Nenhum registro encontrado.</td></tr>';
    } catch(e) {
        tb.innerHTML = '<tr><td colspan="3" class="text-center text-danger">Falha na pesquisa</td></tr>';
    }
}

window.selecPesq = function(id, nome) {
    if(cPesq.idInput) document.getElementById(cPesq.idInput).value = id;
    if(cPesq.nomeInput) document.getElementById(cPesq.nomeInput).value = nome;
    
    if(cPesq.idInput === 'fch_produto_id') {
        document.getElementById('fch_produto_pai_id').value = id;
        document.getElementById('fch_produto_final_id').value = id;
    }
    if(cPesq.nomeInput === 'fch_produto_pai_nome') {
        document.getElementById('fch_produto_final_nome').value = nome;
    }
    fecharPesquisa();
}

// ==========================================
// EXPORTAÇÃO E IMPRESSÃO (EXCEL, PDF)
// ==========================================
function getCleanTableData(tableId) {
    const table = document.getElementById(tableId);
    const headers = [];
    const rows = [];
    const headerCells = table.querySelectorAll('thead th');
    let skipCols = [];

    headerCells.forEach((th, index) => {
        const thText = th.innerText.toLowerCase().trim();
        if (thText !== 'ação' && thText !== 'ações') {
            headers.push(th.innerText);
        } else {
            skipCols.push(index);
        }
    });

    const tbodyRows = table.querySelectorAll('tbody tr');
    tbodyRows.forEach(tr => {
        const rowData = [];
        const cells = tr.querySelectorAll('td');
        if(cells.length === 1 && cells[0].colSpan > 1) return;

        cells.forEach((td, index) => {
            if (!skipCols.includes(index)) {
                rowData.push(td.innerText);
            }
        });
        if (rowData.length > 0) rows.push(rowData);
    });

    return { headers, rows };
}

window.exportarExcel = function(tableId, fileName) {
    if (typeof XLSX === 'undefined') { alert('A biblioteca Excel não carregou.'); return; }
    const data = getCleanTableData(tableId);
    const ws = XLSX.utils.aoa_to_sheet([data.headers, ...data.rows]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Relatório");
    XLSX.writeFile(wb, fileName + ".xlsx");
};

window.exportarPDF = function(tableId, title) {
    if (typeof window.jspdf === 'undefined') { alert('A biblioteca PDF não carregou.'); return; }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    const data = getCleanTableData(tableId);
    doc.text(title, 14, 15);
    doc.autoTable({ head: [data.headers], body: data.rows, startY: 20, theme: 'grid' });
    doc.save(title.replace(/\s+/g, '_') + ".pdf");
};