// ==========================================
// AÇÕES DE GRELHA (EXPORTAR / PDF / PESQUISA)
// ==========================================
window.filterTable = function(inputId, tbodyId) {
    const query = document.getElementById(inputId).value.toLowerCase();
    const rows = document.getElementById(tbodyId).querySelectorAll('tr');
    rows.forEach(row => {
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
    });
}

window.exportToCSV = function(tableId, filename) {
    const table = document.getElementById(tableId).closest('table');
    if(!table) return;

    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    for (let i = 0; i < rows.length; i++) {
        if (rows[i].style.display === 'none') continue; 
        
        let row = [], cols = rows[i].querySelectorAll('td, th');
        for (let j = 0; j < cols.length; j++) {
            let clone = cols[j].cloneNode(true);
            clone.querySelectorAll('button').forEach(b => b.remove()); 
            let data = clone.innerText.replace(/"/g, '""').trim();
            row.push('"' + data + '"');
        }
        csv.push(row.join(','));
    }
    
    let csvFile = new Blob(["\ufeff" + csv.join('\n')], {type: 'text/csv;charset=utf-8;'});
    let downloadLink = document.createElement("a");
    downloadLink.download = filename + '.csv';
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = "none";
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

window.printView = function() {
    window.print();
}

// ==========================================
// CONTROLE DO MENU E UTILITÁRIOS
// ==========================================
function switchServicosView(viewId, btnElement) {
    document.querySelectorAll('.erp-view, .menu-item').forEach(el => el.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
    if(btnElement) btnElement.classList.add('active');

    localStorage.setItem('lastSrvView', viewId);
    loadDropdownsServicos();

    const loadMapServicos = { 'view_ordens': loadOrdensServico, 'view_identificadores': loadIdentificadores, 'view_itens_servico': loadItensServico };
    if (loadMapServicos[viewId]) loadMapServicos[viewId]();
}

function openModalSrv(formId) { document.getElementById(formId + '_modal')?.classList.add('active'); }
function closeModalSrv(formId) { document.getElementById(formId + '_modal')?.classList.remove('active'); }

window.novoCadastroSrv = function(formId) {
    limparFormularioSrv(formId);
    openModalSrv(formId);
}

function safeVal(val) { return (val === null || val === undefined || String(val).trim()==='' || val==='null') ? '-' : val; }
function safeEdit(val) { return (val === null || val === undefined || String(val).trim()==='' || val==='null') ? '' : val; }

function limparFormularioSrv(formId) {
    const form = document.getElementById(formId);
    if(form) {
        form.reset();
        const idField = form.querySelector('input[type="hidden"]');
        if(idField) idField.value = '';
        document.querySelectorAll(`#${formId} tbody.dynamic-list, #${formId} tbody[id^="tb_"]`).forEach(tbody => tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted">Aguardando inserção.</td></tr>`);
        if(formId === 'form_ordens_servico') {
            document.getElementById('os_total_produtos').value = '0.00';
            document.getElementById('os_total_servicos').value = '0.00';
            document.getElementById('os_total_geral').value = '0.00';
            // Garantir que status default não seja nulo após reset
            if(document.getElementById('os_status')) document.getElementById('os_status').value = 'Aberto';
        }
    }
}

// ==========================================
// INTEGRAÇÃO DE DROPDOWNS E FILTROS
// ==========================================
window.osCache = [];

async function loadDropdownsServicos() {
    try {
        const res = await fetch('/api/servicos/opcoes_formularios'); 
        const data = await res.json();
        
        const populateDdl = (cls, arr, placeholder) => {
            let html = `<option value="">${placeholder}</option>`;
            if(arr) arr.forEach(x => {
                if(typeof x === 'object') html += `<option value="${x.nome}" data-id="${x.id}">${x.nome}</option>`;
                else html += `<option value="${x}">${x}</option>`;
            });
            document.querySelectorAll(cls).forEach(el => { const cur = el.value; el.innerHTML = html; if(cur) el.value = cur; });
        };

        populateDdl('.ddl-tabelas-preco', data.tabelas_preco, '-- Selecione --');
        populateDdl('.ddl-formas-pgto', data.formas_pgto, '-- Selecione --');
        populateDdl('.ddl-condicoes', data.condicoes, '-- Selecione --');
        populateDdl('.ddl-bancos', data.bancos, '-- Selecione --');
        populateDdl('.ddl-tecnicos', data.tecnicos, '-- Selecione --');
        populateDdl('.ddl-itens-servico', data.itens_servico, '-- Selecione --');
        populateDdl('.ddl-clientes-filtro', data.clientes, 'Todos');
        populateDdl('.ddl-atendentes-filtro', data.atendentes, 'Todos');

        let htmlPortarias = '<option value="">-- Selecione a Portaria --</option>';
        if (data.portarias_list) {
            data.portarias_list.forEach(p => {
                htmlPortarias += `<option value="${p.nome}" data-msg="${(p.mensagem||'').replace(/"/g, '&quot;')}">${p.nome}</option>`;
            });
        }
        document.querySelectorAll('.ddl-portarias').forEach(el => { const cur = el.value; el.innerHTML = htmlPortarias; if(cur) el.value = cur; });

    } catch(e) {}

    // Requisição separada para povoar os dropdowns automáticos de Identificadores
    try {
        const resId = await fetch('/api/servicos/identificadores');
        const dataId = await resId.json();
        let htmlIdent = '<option value="">-- Selecione o Identificador --</option>';
        dataId.forEach(x => { htmlIdent += `<option value="${x.nome}">${x.nome}</option>`; });
        document.querySelectorAll('.ddl-identificadores').forEach(el => el.innerHTML = htmlIdent);
    } catch(e) {}
}

document.addEventListener("DOMContentLoaded", () => { 
    loadDropdownsServicos().then(() => {
        let lastView = localStorage.getItem('lastSrvView') || 'view_ordens';
        let btn = document.querySelector(`button[onclick*="${lastView}"]`);
        if(btn) switchServicosView(lastView, btn);
        else switchServicosView('view_ordens', document.querySelector('.menu-item'));
    });
});

window.filtrarOS = function() {
    const fData = document.getElementById('filtro_data').value;
    const fCli = document.getElementById('filtro_cliente').value.toLowerCase();
    const fAte = document.getElementById('filtro_atendente').value.toLowerCase();
    const fSta = document.getElementById('filtro_status').value.toLowerCase();
    const fFin = document.getElementById('filtro_finalidade').value.toLowerCase();

    const filtered = window.osCache.filter(i => {
        let match = true;
        if(fData && i.data_registro !== fData) match = false;
        if(fCli && !(i.cliente_nome||'').toLowerCase().includes(fCli)) match = false;
        if(fAte && !(i.atendente_nome||'').toLowerCase().includes(fAte)) match = false;
        if(fSta && !(i.status||'').toLowerCase().includes(fSta)) match = false;
        if(fFin && !(i.finalidade||'').toLowerCase().includes(fFin)) match = false;
        return match;
    });
    renderOSGrid(filtered);
};

window.limparFiltrosOS = function() {
    document.querySelectorAll('.filter-bar input, .filter-bar select').forEach(el => el.value = '');
    renderOSGrid(window.osCache);
};

function renderOSGrid(data) {
    const tb = document.getElementById('tb_ordens_servico'); tb.innerHTML = '';
    data.forEach(i => { 
        // CORREÇÃO: Utilizando parseFloat na renderização do valor total
        tb.innerHTML += `<tr>
            <td class="font-bold text-warning">${safeVal(i.numero)}</td>
            <td>${safeVal(i.data_registro)}</td>
            <td class="text-info">${safeVal(i.cliente_nome)}</td>
            <td class="text-success font-bold">R$ ${parseFloat(i.total_geral||0).toFixed(2)}</td>
            <td><span style="background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px;">${safeVal(i.status)}</span></td>
            <td class="text-center">${actBtns('form_ordens_servico', 'os_', i, 'ordens_servico', 'loadOrdensServico')}</td>
        </tr>`; 
    });
}

// ==========================================
// CALCULADORA TEMPORÁRIA (ADD ITENS)
// ==========================================
window.calcularTempItem = function(fromPercent = true) {
    const qtd = parseFloat(document.getElementById('tmp_os_item_qtd').value) || 0;
    const vlrUn = parseFloat(document.getElementById('tmp_os_item_vlr').value) || 0;
    const acresc = parseFloat(document.getElementById('tmp_os_item_acresc').value) || 0;
    
    const elP = document.getElementById('tmp_os_item_descp');
    const elV = document.getElementById('tmp_os_item_descv');
    
    let descP = parseFloat(elP.value) || 0;
    let descV = parseFloat(elV.value) || 0;

    let subBruto = (qtd * vlrUn) + acresc;

    if(fromPercent && descP > 0) { descV = subBruto * (descP/100); elV.value = descV.toFixed(2); }
    else if(!fromPercent && subBruto > 0) { descP = (descV / subBruto) * 100; elP.value = descP.toFixed(2); }

    let final = subBruto - descV;
    document.getElementById('tmp_os_item_sub').value = final > 0 ? final.toFixed(2) : '0.00';
};

window.calcularTotalGeralOS = function(fromPercent = true) {
    let tProd = 0; let tServ = 0;
    document.querySelectorAll('#tb_os_itens tr').forEach(tr => {
        if(tr.querySelector('td.text-muted')) return;
        const tds = tr.querySelectorAll('td');
        if(tds.length < 6) return;
        const tipo = tr.getAttribute('data-tipo') || 'servico';
        const sub = parseFloat(tds[5].innerText) || 0;
        if(tipo === 'produto') tProd += sub; else tServ += sub;
    });

    document.getElementById('os_total_produtos').value = tProd.toFixed(2);
    document.getElementById('os_total_servicos').value = tServ.toFixed(2);
    
    const desp = parseFloat(document.getElementById('os_despesas').value) || 0;
    let baseTotal = tProd + tServ + desp;

    const elP = document.getElementById('os_desconto_percent');
    const elV = document.getElementById('os_desconto_valor');
    let dP = parseFloat(elP.value) || 0;
    let dV = parseFloat(elV.value) || 0;

    if(fromPercent && dP > 0) { dV = baseTotal * (dP/100); elV.value = dV.toFixed(2); }
    else if(!fromPercent && baseTotal > 0) { dP = (dV / baseTotal) * 100; elP.value = dP.toFixed(2); }

    let final = baseTotal - dV;
    document.getElementById('os_total_geral').value = final > 0 ? final.toFixed(2) : '0.00';
};

// ==========================================
// FUNÇÕES DE ADIÇÃO NAS TABELAS (GRIDS)
// ==========================================
window.addOsItem = function() {
    const nome = document.getElementById('tmp_os_item_nome').value;
    const tipo = document.getElementById('tmp_os_item_tipo').value;
    const tec = document.getElementById('tmp_os_item_tecnico').value;
    const qtd = document.getElementById('tmp_os_item_qtd').value;
    const vlr = document.getElementById('tmp_os_item_vlr').value;
    const descv = document.getElementById('tmp_os_item_descv').value;
    const sub = document.getElementById('tmp_os_item_sub').value;

    if(!nome) { alert("Pesquise e selecione um Produto/Serviço!"); return; }

    const tb = document.getElementById('tb_os_itens');
    if(tb.querySelector('td.text-muted')) tb.innerHTML = '';
    
    tb.insertAdjacentHTML('beforeend', `<tr data-tipo="${tipo}">
        <td>${nome}</td><td>${tec}</td><td>${qtd}</td><td>${vlr}</td><td>${descv}</td><td>${sub}</td>
        <td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="this.closest('tr').remove(); calcularTotalGeralOS();">X</button></td>
    </tr>`);
    
    // Limpar campos
    ['tmp_os_item_nome','tmp_os_item_tipo','tmp_os_item_tecnico','tmp_os_item_acresc','tmp_os_item_descp','tmp_os_item_descv'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('tmp_os_item_qtd').value = '1'; document.getElementById('tmp_os_item_vlr').value = ''; document.getElementById('tmp_os_item_sub').value = '';
    calcularTotalGeralOS();
};

window.addOsFinanceiro = function() {
    const forma = document.getElementById('tmp_fin_forma').value;
    const cond = document.getElementById('tmp_fin_cond').value;
    const valor = document.getElementById('tmp_fin_valor').value;
    const parc = document.getElementById('tmp_fin_parc').value;
    if(!forma || !valor) return;
    const tb = document.getElementById('tb_os_financeiro');
    if(tb.querySelector('td.text-muted')) tb.innerHTML = '';
    const seq = tb.querySelectorAll('tr').length + 1;
    tb.insertAdjacentHTML('beforeend', `<tr><td>${seq}</td><td>${forma}</td><td>${cond}</td><td>${valor}</td><td>${parc}</td><td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="this.closest('tr').remove()">X</button></td></tr>`);
};

window.addOsCobranca = function() {
    const bnc = document.getElementById('tmp_cob_banco').value;
    const venc = document.getElementById('tmp_cob_venc').value;
    const valor = document.getElementById('tmp_cob_valor').value;
    if(!bnc || !valor) return;
    const tb = document.getElementById('tb_os_cobranca');
    if(tb.querySelector('td.text-muted')) tb.innerHTML = '';
    const seq = tb.querySelectorAll('tr').length + 1;
    tb.insertAdjacentHTML('beforeend', `<tr><td>${seq}</td><td>${bnc}</td><td>${venc}</td><td>${valor}</td><td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="this.closest('tr').remove()">X</button></td></tr>`);
};

window.addIdentificadorVinculo = function() {
    const sel = document.getElementById('tmp_ident_nome_sel');
    const infoInput = document.getElementById('tmp_ident_info_sel');
    const idxSel = document.getElementById('tmp_ident_idx_sel');
    
    if(!sel || !sel.value) return;
    
    const nome = sel.value;
    const info = infoInput ? infoInput.value : '';
    const idx = idxSel ? idxSel.value : 'Sim';
    
    const tb = document.getElementById('tb_vinculos_ident');
    if(tb.querySelector('td.text-muted')) tb.innerHTML = '';
    
    const ord = tb.querySelectorAll('tr').length + 1; // Incremento automático
    
    tb.insertAdjacentHTML('beforeend', `<tr><td>${ord}</td><td>${nome}</td><td>${info}</td><td>${idx}</td><td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="this.closest('tr').remove()">X</button></td></tr>`);
    
    sel.value = ''; // Limpa para a próxima
    if(infoInput) infoInput.value = '';
    if(idxSel) idxSel.value = 'Sim';
};

window.inserirPortariaNaOS = function() {
    const sel = document.getElementById('tmp_os_sel_portaria');
    const txt = document.getElementById('os_portarias');
    if(sel && sel.value && txt) {
        let atual = txt.value; if(atual && !atual.endsWith('\n')) atual += '\n\n';
        const opt = sel.options[sel.selectedIndex];
        txt.value = atual + "PORTARIA/TERMO:\n" + (opt ? opt.getAttribute('data-msg') : sel.value);
    }
};

// ==========================================
// LÓGICA DE CRUD E CONECTIVIDADE COM A API
// ==========================================
function serializeFormFields(formId, prefix) {
    const inputs = document.querySelectorAll(`#${formId} input:not(.ignore-serialize), #${formId} select:not(.ignore-serialize), #${formId} textarea:not(.ignore-serialize)`);
    const payload = {};
    inputs.forEach(input => {
        let key = input.id.replace(prefix, '');
        if(key) { if (key === 'id' && !input.value) return; payload[key] = input.value; }
    });
    return payload;
}

function tableToJson(tableId, chaves) {
    const tb = document.getElementById(tableId);
    if(!tb) return "[]";
    const data = [];
    tb.querySelectorAll('tr').forEach(tr => {
        if(tr.querySelector('td.text-muted')) return;
        let obj = {}; let tds = tr.querySelectorAll('td');
        if(tds.length > 0) chaves.forEach((k, idx) => { if(tds[idx]) obj[k] = tds[idx].innerText; });
        if(tr.getAttribute('data-tipo')) obj['tipo'] = tr.getAttribute('data-tipo');
        data.push(obj);
    });
    return JSON.stringify(data);
}

function renderTableFromJson(tableId, jsonStr, chaves, extraCols=1) {
    const tb = document.getElementById(tableId);
    if(!tb) return;
    tb.innerHTML = '';
    try {
        const arr = JSON.parse(jsonStr || '[]');
        if(arr.length === 0) { tb.innerHTML = `<tr><td colspan="${chaves.length+extraCols}" class="text-center text-muted">Nenhum registro.</td></tr>`; return; }
        arr.forEach(row => {
            let cols = '';
            chaves.forEach(k => { cols += `<td>${safeEdit(row[k])}</td>`; });
            const dataTipo = row['tipo'] ? `data-tipo="${row['tipo']}"` : '';
            const delAction = tableId === 'tb_os_itens' ? 'this.closest(\'tr\').remove(); calcularTotalGeralOS();' : 'this.closest(\'tr\').remove();';
            tb.insertAdjacentHTML('beforeend', `<tr ${dataTipo}>${cols}<td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="${delAction}">X</button></td></tr>`);
        });
    } catch(e) { tb.innerHTML = `<tr><td colspan="${chaves.length+extraCols}" class="text-center text-muted">Erro ao carregar dados.</td></tr>`; }
}

window.dispatchEdit = function(formId, prefix, encoded) {
    const itemObj = JSON.parse(decodeURIComponent(encoded));
    limparFormularioSrv(formId);
    
    for (const [key, value] of Object.entries(itemObj)) {
        const el = document.getElementById(prefix + key);
        if (el) el.value = safeEdit(value);
    }
    
    if(formId === 'form_ordens_servico') {
        renderTableFromJson('tb_os_itens', itemObj.itens_json, ['produto', 'tecnico', 'qtd', 'valor', 'desconto', 'subtotal']);
        renderTableFromJson('tb_os_financeiro', itemObj.financeiro_json, ['seq', 'forma', 'condicao', 'valor', 'parcelas']);
        renderTableFromJson('tb_os_cobranca', itemObj.cobranca_json, ['seq', 'banco', 'vencimento', 'valor']);
        calcularTotalGeralOS(); 
    } else if (formId === 'form_itens_servico') {
        renderTableFromJson('tb_vinculos_ident', itemObj.identificadores_json, ['ord', 'nome', 'informacoes', 'idx']);
    }
    openModalSrv(formId);
};

// CORREÇÃO: Tratamento rigoroso de erros na API para exibir na tela qualquer falha no banco
async function postRecordSrv(tabela, payload, formId) {
    try {
        const res = await fetch(`/api/servicos/${tabela}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const jsonRes = await res.json();
        
        if(res.ok && jsonRes.sucesso !== false) { 
            limparFormularioSrv(formId); 
            closeModalSrv(formId); 
            return true; 
        } else {
            alert("Erro ao salvar: " + (jsonRes.erro || "Verifique os dados informados."));
            return false;
        }
    } catch(e) { 
        alert("Falha de comunicação com o servidor.");
        return false; 
    }
}

async function deleteRecordSrv(tabela, id, callbackLoad) {
    if(!confirm("Tem certeza que deseja excluir?")) return;
    try { const res = await fetch(`/api/servicos/${tabela}/${id}`, { method: 'DELETE' }); if(res.ok) window[callbackLoad](); } catch(e) {}
}

function actBtns(frm, prefix, item, tbName, loadFunc) {
    let enc = encodeURIComponent(JSON.stringify(item));
    return `<button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEdit('${frm}', '${prefix}', '${enc}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordSrv('${tbName}', ${item.id}, '${loadFunc}')">🗑️</button>`;
}

window.salvarOrdemServico = async function(e) {
    e.preventDefault();
    const payload = serializeFormFields('form_ordens_servico', 'os_');
    payload.itens_json = tableToJson('tb_os_itens', ['produto', 'tecnico', 'qtd', 'valor', 'desconto', 'subtotal']);
    payload.financeiro_json = tableToJson('tb_os_financeiro', ['seq', 'forma', 'condicao', 'valor', 'parcelas']);
    payload.cobranca_json = tableToJson('tb_os_cobranca', ['seq', 'banco', 'vencimento', 'valor']);
    if(await postRecordSrv('ordens_servico', payload, 'form_ordens_servico')) loadOrdensServico();
};

window.salvarItemServico = async function(e) {
    e.preventDefault();
    const payload = serializeFormFields('form_itens_servico', 'its_');
    payload.identificadores_json = tableToJson('tb_vinculos_ident', ['ord', 'nome', 'informacoes', 'idx']);
    if(await postRecordSrv('itens_servico', payload, 'form_itens_servico')) loadItensServico();
};

window.salvarServicoBase = async function(e, tabela) {
    e.preventDefault();
    const payload = serializeFormFields(`form_${tabela}`, 'idt_');
    if(await postRecordSrv(tabela, payload, `form_${tabela}`)) loadIdentificadores();
};

// LOADERS
async function loadOrdensServico() {
    try {
        const res = await fetch('/api/servicos/ordens_servico'); 
        window.osCache = await res.json();
        filtrarOS();
    } catch(e) {}
}

async function loadIdentificadores() {
    try {
        const res = await fetch('/api/servicos/identificadores'); const data = await res.json();
        const tb = document.getElementById('tb_identificadores'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-muted">#${i.id}</td><td class="font-bold text-info">${safeVal(i.nome)}</td><td class="text-center">${actBtns('form_identificadores', 'idt_', i, 'identificadores', 'loadIdentificadores')}</td></tr>`; });
    } catch(e) {}
}

async function loadItensServico() {
    try {
        const res = await fetch('/api/servicos/itens_servico'); const data = await res.json();
        const tb = document.getElementById('tb_itens_servico'); tb.innerHTML = '';
        data.forEach(i => { 
            let idsStr = "Nenhum";
            try { if(i.identificadores_json) idsStr = JSON.parse(i.identificadores_json).map(x => x.nome).join(', '); } catch(e){}
            tb.innerHTML += `<tr><td class="text-muted">#${i.id}</td><td class="font-bold text-info">${safeVal(i.nome)}</td><td>${idsStr}</td><td class="text-center">${actBtns('form_itens_servico', 'its_', i, 'itens_servico', 'loadItensServico')}</td></tr>`; 
        });
    } catch(e) {}
}

// ==========================================
// MODAL DE PESQUISA INTELIGENTE (AUTO-PREENCHIMENTO)
// ==========================================
let alvoSrvId = null; let alvoSrvNome = null; let baseSrvEndpoint = ''; let isItemOS = false;
window.abrirPesquisaSrv = function(entidade, idInput, nomeInput, isItem = false) {
    alvoSrvId = idInput; alvoSrvNome = nomeInput; baseSrvEndpoint = entidade; isItemOS = isItem;
    document.getElementById('msrv_titulo').innerText = `Pesquisar`;
    document.getElementById('msrv_input').value = '';
    document.getElementById('msrv_resultados').innerHTML = '<tr><td colspan="3" class="text-center text-muted">Aguardando busca...</td></tr>';
    document.getElementById('modal_pesquisa_srv').style.display = 'flex';
};
window.fecharPesquisaSrv = function() { document.getElementById('modal_pesquisa_srv').style.display = 'none'; };
window.executarPesquisaSrv = async function() {
    const q = document.getElementById('msrv_input').value;
    try {
        const res = await fetch(`/api/servicos/pesquisar/${baseSrvEndpoint}?q=${q}`);
        const data = await res.json();
        const tb = document.getElementById('msrv_resultados'); tb.innerHTML = '';
        if(data.length === 0) { tb.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Nenhum registro.</td></tr>'; return; }
        data.forEach(i => { 
            const ext = isItemOS ? ` - R$ ${i.vlr}` : '';
            tb.innerHTML += `<tr><td>${i.id}</td><td>${i.nome}${ext}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-success" style="padding:2px 8px;" onclick="selecionarPesquisaSrv('${i.id}', '${i.nome.replace(/'/g, "\\'")}', '${i.vlr||0}', '${i.tipo||''}')">OK</button></td></tr>`; 
        });
    } catch(e) { document.getElementById('msrv_resultados').innerHTML = '<tr><td colspan="3" class="text-center">Falha na pesquisa</td></tr>'; }
};
window.selecionarPesquisaSrv = function(id, nome, vlr, tipo) {
    if(document.getElementById(alvoSrvId)) document.getElementById(alvoSrvId).value = id;
    if(document.getElementById(alvoSrvNome)) document.getElementById(alvoSrvNome).value = nome;
    
    // Auto-preenchimento para Itens da OS
    if(isItemOS) {
        if(document.getElementById('tmp_os_item_vlr')) document.getElementById('tmp_os_item_vlr').value = vlr;
        if(document.getElementById('tmp_os_item_tipo')) document.getElementById('tmp_os_item_tipo').value = tipo;
        calcularTempItem();
    }
    fecharPesquisaSrv();
};