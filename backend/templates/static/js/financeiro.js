// ==========================================
// FUNÇÕES UTILITÁRIAS E PARSER SEGURO
// ==========================================
function safeVal(val) {
    if (val === null || val === undefined || String(val).toLowerCase() === 'null') return '';
    return val;
}

function parseSafeJSON(data) {
    if (!data) return [];
    if (typeof data === 'string') {
        try { return JSON.parse(data); } catch(e) { return []; }
    }
    if (Array.isArray(data)) return data;
    return [];
}

// Formatador de data para exibir corretamente (YYYY-MM-DD para DD/MM/YYYY)
function formatDateBR(val) {
    if (!val) return '';
    let d = String(val).split('T')[0];
    let parts = d.split('-');
    if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
    return val;
}

function fetchNoCache(url) {
    const timestamp = new Date().getTime();
    const separador = url.includes('?') ? '&' : '?';
    return fetch(url + separador + '_t=' + timestamp, { cache: "no-store" });
}

// Global Checkbox Toggle
window.toggleAll = function(source) {
    const table = source.closest('table');
    const checkboxes = table.querySelectorAll('tbody .row-check');
    checkboxes.forEach(cb => cb.checked = source.checked);
};

// ==========================================
// MODAIS E ABAS
// ==========================================
function openModal(formId) {
    const modal = document.getElementById(formId + '_modal');
    if(modal) modal.classList.add('active');
}

function closeModal(formId) {
    const modal = document.getElementById(formId + '_modal');
    if(modal) modal.classList.remove('active');
}

window.novoCadastroFinanceiro = function(formId) {
    limparFormulario(formId);
    
    // Auto-preenchimentos requeridos
    const today = new Date().toISOString().split('T')[0];
    const form = document.getElementById(formId);
    if(form) {
        if(formId === 'form_recebimentos' || formId === 'form_pagamentos') {
            const pre = formId === 'form_recebimentos' ? 'rec_' : 'pag_';
            const pgtoEl = document.getElementById(`${pre}pagamento`);
            if(pgtoEl) pgtoEl.value = today;
            
            const vencEl = document.getElementById(`${pre}vencimento`);
            if(vencEl && !vencEl.value) vencEl.value = today;
            
            const emissaoEl = document.getElementById(`${pre}data_emissao`);
            if(emissaoEl) emissaoEl.value = today;
            
            // Zerar os readonly
            ['tarifa', 'desconto', 'juros', 'encargos', 'amortizado', 'saldo_aberto', 'valor_recebido', 'valor_pago'].forEach(k => {
                const el = document.getElementById(`${pre}${k}`);
                if(el) el.value = "0.00";
            });
        }
    }
    
    const tabs = document.querySelectorAll(`#${formId}_modal .tab-btn`);
    if(tabs.length > 0) switchFinTab(tabs[0], tabs[0].getAttribute('onclick').match(/'([^']+)'/)[1]);

    openModal(formId);
}

window.switchFinTab = function(btnElement, tabId) {
    let container = btnElement.closest('.erp-modal-content');
    if (!container) container = btnElement.closest('.erp-view'); // Para a aba de fluxo que fica fora do modal
    
    container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    btnElement.classList.add('active');
    document.getElementById(tabId).classList.add('active');
}

// ==========================================
// CALCULADORAS AUTOMÁTICAS
// ==========================================
function setupCalculators() {
    ['rec', 'pag'].forEach(pre => {
        const valInput = document.getElementById(`${pre}_valor`);
        if (valInput) {
            valInput.addEventListener('input', () => {
                const val = parseFloat(valInput.value) || 0;
                const saldoEl = document.getElementById(`${pre}_saldo_aberto`);
                const liqEl = document.getElementById(pre === 'rec' ? 'rec_valor_recebido' : 'pag_valor_pago');
                
                if(saldoEl) saldoEl.value = val.toFixed(2); 
                if(liqEl) liqEl.value = val.toFixed(2);
            });
        }
    });
}

// ==========================================
// CARREGAMENTO GLOBAL DE DROPDOWNS E BUSCA
// ==========================================
async function loadDropdownsFinanceiro() {
    try {
        const res = await fetchNoCache('/api/financeiro/opcoes_formularios');
        const data = await res.json();
        
        function fill(selector, arr) {
            let html = '';
            document.querySelectorAll(selector).forEach(el => {
                if(el.tagName === 'SELECT') html = '<option value="">-- Selecione --</option>';
                else html = ''; 

                if(arr) {
                    arr.forEach(i => {
                        let nm = typeof i === 'object' ? (i.nome || i.descricao) : i;
                        if(nm) html += `<option value="${nm.replace(/"/g, '&quot;')}">${nm}</option>`;
                    });
                }
                el.innerHTML = html;
            });
        }

        fill('.ddl-clientes', data.clientes);
        fill('.ddl-fornecedores', data.fornecedores);
        fill('.ddl-bancos', data.bancos);
        fill('.ddl-contas', data.contas_bancarias);
        fill('.ddl-centros', data.centro_custo);
        fill('.ddl-formas', data.formas_pagamento);
        fill('.ddl-status', data.status_financeiro);
        fill('.ddl-planos', data.plano_contas);
        fill('.ddl-funcionarios', data.funcionarios);
        fill('.ddl-caixas', data.caixas_pdv);
        fill('.ddl-operadoras', data.operadoras);
        fill('.ddl-cheques', data.cheques);
        fill('.ddl-naturezas', data.naturezas);
        
    } catch(e) { console.warn(e); }
}

// Lógica de Modal de Pesquisa Generica (Importado do Comercial)
let alvoId = null; let alvoNome = null; let baseEndpoint = '';

window.abrirPesquisa = function(entidade, idInput, nomeInput) {
    alvoId = idInput; alvoNome = nomeInput; baseEndpoint = entidade;
    document.getElementById('mpesq_titulo').innerText = `Pesquisar ${entidade.toUpperCase()}`;
    document.getElementById('mpesq_input').value = '';
    document.getElementById('mpesq_tb').innerHTML = '';
    document.getElementById('modal_pesquisa_generica').classList.add('active');
};

window.fecharPesquisa = function() { 
    document.getElementById('modal_pesquisa_generica').classList.remove('active'); 
};

window.executarPesquisa = async function() {
    const q = document.getElementById('mpesq_input').value;
    try {
        const res = await fetch(`/api/financeiro/pesquisar/${baseEndpoint}?q=${q}&_=${new Date().getTime()}`);
        const data = await res.json();
        const tb = document.getElementById('mpesq_tb'); tb.innerHTML = '';
        if(data.length === 0) {
             tb.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Nenhum registro encontrado.</td></tr>';
             return;
        }
        data.forEach(i => { 
            let nomeDisplay = i.nome || i.razao_social || i.descricao || 'Sem Nome';
            tb.innerHTML += `<tr><td>${i.id}</td><td>${nomeDisplay}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-success" style="padding:2px 8px; font-size:0.7rem;" onclick="selecionarPesquisa(${i.id}, '${nomeDisplay.replace(/'/g, "\\'")}')">OK</button></td></tr>`; 
        });
    } catch(e) { document.getElementById('mpesq_tb').innerHTML = '<tr><td colspan="3" class="text-center">Falha na pesquisa</td></tr>'; }
};

window.selecionarPesquisa = function(id, nome) {
    if(alvoId && document.getElementById(alvoId)) document.getElementById(alvoId).value = id;
    if(alvoNome && document.getElementById(alvoNome)) document.getElementById(alvoNome).value = nome;
    fecharPesquisa();
};

// ==========================================
// GESTOR DE VIEWS E EXPORTAÇÕES
// ==========================================
window.switchFinView = function(viewId, btnElement) {
    document.querySelectorAll('.erp-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(viewId).classList.add('active');
    if(btnElement) btnElement.classList.add('active');
    
    localStorage.setItem('lastFinView', viewId);

    const loaders = {
        'view_recebimentos': loadRecebimentos, 'view_pagamentos': loadPagamentos,
        'view_boletos': loadBoletos, 'view_cheques': loadCheques, 
        'view_fechamento_pdv': loadFechamentoPdv, 'view_conciliacoes': loadConciliacoes,
        'view_renegociacoes': loadRenegociacoes, 'view_comissoes': loadComissoes,
        'view_plano_contas': loadPlanoContas, 'view_natureza': loadNatureza,
        'view_condicoes': loadCondicoes, 'view_formas': loadFormas,
        'view_bandeiras': loadBandeiras, 'view_contas_banc': loadContasBancarias,
        'view_bancos': loadBancos, 'view_centro_custo': loadCentroCusto, 'view_status': loadStatus
    };
    
    if (viewId === 'view_fluxo') {
        loadFluxo();
        if (typeof loadTransferencias === 'function') loadTransferencias();
    } else if (loaders[viewId]) {
        loaders[viewId]();
    }
}

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
            clone.querySelectorAll('button, input').forEach(b => b.remove()); 
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

document.addEventListener("DOMContentLoaded", () => {
    loadDropdownsFinanceiro();
    setupCalculators();
    
    let lastView = localStorage.getItem('lastFinView') || 'view_recebimentos';
    let btn = document.querySelector(`button[onclick*="${lastView}"]`);
    if(btn) switchFinView(lastView, btn);
    else switchFinView('view_recebimentos', document.querySelector('.menu-item'));
});

// ==========================================
// GRIDS INTERNAS DE CADASTRO
// ==========================================
let bandeiraFaixasCache = [];
let planNaturezasCache = [];
let recPlanosCache = [];
let recBaixasCache = [];
let recChequesCache = [];
let pagPlanosCache = [];
let pagBaixasCache = [];
let cheqRefCache = [];
let cheqHistCache = [];

function renderBandeiraFaixas() {
    const tbody = document.querySelector('#tb_bandeiras_faixas tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    bandeiraFaixasCache.forEach((f, idx) => {
        tbody.innerHTML += `<tr>
            <td>${f.ini}</td>
            <td>${f.fim}</td>
            <td class="text-warning">${f.taxa}%</td>
            <td class="text-center"><button type="button" onclick="remFaixaBandeira(${idx})" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem">❌</button></td>
        </tr>`;
    });
    const hd = document.getElementById('band_faixas_json');
    if(hd) hd.value = JSON.stringify(bandeiraFaixasCache);
}
window.addFaixaBandeira = function() {
    const ini = document.getElementById('tmp_parc_ini').value;
    const fim = document.getElementById('tmp_parc_fim').value;
    const taxa = document.getElementById('tmp_taxa').value;
    if(!ini || !fim || !taxa) return;
    bandeiraFaixasCache.push({ini: parseInt(ini), fim: parseInt(fim), taxa: parseFloat(taxa)});
    document.getElementById('tmp_parc_ini').value = '';
    document.getElementById('tmp_parc_fim').value = '';
    document.getElementById('tmp_taxa').value = '';
    renderBandeiraFaixas();
};
window.remFaixaBandeira = function(idx) { bandeiraFaixasCache.splice(idx, 1); renderBandeiraFaixas(); };

function renderPlanNaturezas() {
    const tbody = document.querySelector('#tb_plan_naturezas tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    planNaturezasCache.forEach((f, idx) => {
        tbody.innerHTML += `<tr>
            <td class="text-info">${f.nome}</td>
            <td>${f.inativo ? '<span class="badge-fin bg-atrasado">Sim</span>' : '<span class="badge-fin bg-pago">Não</span>'}</td>
            <td class="text-center"><button type="button" onclick="remPlanNatureza(${idx})" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem">❌</button></td>
        </tr>`;
    });
    const hd = document.getElementById('plan_plan_naturezas_json');
    if(hd) hd.value = JSON.stringify(planNaturezasCache);
}
window.addPlanNatureza = function() {
    const nat = document.getElementById('tmp_plan_natureza_grid').value;
    const inativo = document.getElementById('tmp_plan_natureza_inativo').checked;
    if(!nat) return;
    
    const existing = planNaturezasCache.find(n => n.nome === nat);
    if(existing) {
        existing.inativo = inativo;
    } else {
        planNaturezasCache.push({nome: nat, inativo});
    }
    
    document.getElementById('tmp_plan_natureza_grid').value = '';
    document.getElementById('tmp_plan_natureza_inativo').checked = false;
    renderPlanNaturezas();
};
window.remPlanNatureza = function(idx) { planNaturezasCache.splice(idx, 1); renderPlanNaturezas(); };

function renderRecPlanos() {
    const tbody = document.querySelector('#tb_rec_planos tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    recPlanosCache.forEach((p, idx) => {
        tbody.innerHTML += `<tr>
            <td>${p.plano}</td>
            <td class="text-success">${p.valor}</td>
            <td class="text-center"><button type="button" onclick="remRecPlano(${idx})" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem">❌</button></td>
        </tr>`;
    });
    const hd = document.getElementById('rec_planos_contas_json');
    if(hd) hd.value = JSON.stringify(recPlanosCache);
}
window.addRecPlano = function() {
    const sel = document.getElementById('tmp_rec_plano');
    const plano = sel.options[sel.selectedIndex]?.text || sel.value;
    const valor = document.getElementById('tmp_rec_plano_valor').value;
    if(!plano || !valor || sel.value === '') return;
    recPlanosCache.push({ plano: plano, valor: parseFloat(valor).toFixed(2) });
    sel.value = ''; document.getElementById('tmp_rec_plano_valor').value = '';
    renderRecPlanos();
};
window.remRecPlano = function(idx) { recPlanosCache.splice(idx, 1); renderRecPlanos(); };


// ========================= NOVAS LISTAS REC / PAG / CHEQ ==============================
// Baixas (Recebimentos)
function renderRecBaixas() {
    const tbody = document.querySelector('#tb_rec_baixas tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    recBaixasCache.forEach((b, idx) => {
        tbody.innerHTML += `<tr>
            <td>${formatDateBR(b.data)}</td>
            <td>${b.conta}</td>
            <td>${b.forma}</td>
            <td class="text-warning">${b.amortizado}</td>
            <td class="text-success">${b.pago}</td>
            <td class="text-center"><button type="button" onclick="remRecBaixa(${idx})" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem">❌</button></td>
        </tr>`;
    });
    const hd = document.getElementById('rec_itens_baixas_json');
    if(hd) hd.value = JSON.stringify(recBaixasCache);
}
window.addRecBaixa = function() {
    const data = document.getElementById('tmp_rec_baixa_data').value;
    const conta = document.getElementById('tmp_rec_baixa_conta').options[document.getElementById('tmp_rec_baixa_conta').selectedIndex]?.text || '';
    const forma = document.getElementById('tmp_rec_baixa_forma').options[document.getElementById('tmp_rec_baixa_forma').selectedIndex]?.text || '';
    const amortizado = document.getElementById('tmp_rec_baixa_amortizado').value;
    const pago = document.getElementById('tmp_rec_baixa_pago').value;

    if(!data || !conta || (!amortizado && !pago)) return;
    recBaixasCache.push({
        data, conta, forma, 
        amortizado: parseFloat(amortizado||0).toFixed(2), 
        pago: parseFloat(pago||0).toFixed(2)
    });
    
    document.getElementById('tmp_rec_baixa_data').value = '';
    document.getElementById('tmp_rec_baixa_amortizado').value = '';
    document.getElementById('tmp_rec_baixa_pago').value = '';
    renderRecBaixas();
};
window.remRecBaixa = function(idx) { recBaixasCache.splice(idx, 1); renderRecBaixas(); };

// Cheques (Recebimentos)
function renderRecCheques() {
    const tbody = document.querySelector('#tb_rec_cheques tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    recChequesCache.forEach((c, idx) => {
        tbody.innerHTML += `<tr>
            <td>${c.numero || c.cheque || '-'}</td>
            <td>${formatDateBR(c.emissao)}</td>
            <td>${formatDateBR(c.vencimento)}</td>
            <td>${c.status || '-'}</td>
            <td>${formatDateBR(c.data)}</td>
            <td class="text-info">${c.valor}</td>
            <td class="text-center"><button type="button" onclick="remRecCheque(${idx})" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem">❌</button></td>
        </tr>`;
    });
    const hd = document.getElementById('rec_cheques_json');
    if(hd) hd.value = JSON.stringify(recChequesCache);
}
window.addRecCheque = function() {
    const numero = document.getElementById('tmp_rec_cheque_numero').value;
    const emissao = document.getElementById('tmp_rec_cheque_emissao').value;
    const vencimento = document.getElementById('tmp_rec_cheque_venc').value;
    const statusSel = document.getElementById('tmp_rec_cheque_status');
    const status = statusSel.options[statusSel.selectedIndex]?.text || statusSel.value;
    const data = document.getElementById('tmp_rec_cheque_data').value;
    const valor = document.getElementById('tmp_rec_cheque_valor').value;

    if(!numero || !valor) return;
    recChequesCache.push({ 
        numero, emissao, vencimento, status, data, 
        valor: parseFloat(valor).toFixed(2), cheque: numero 
    });
    
    document.getElementById('tmp_rec_cheque_numero').value = '';
    document.getElementById('tmp_rec_cheque_valor').value = '';
    renderRecCheques();
};
window.remRecCheque = function(idx) { recChequesCache.splice(idx, 1); renderRecCheques(); };


// Baixas (Pagamentos)
function renderPagBaixas() {
    const tbody = document.querySelector('#tb_pag_baixas tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    pagBaixasCache.forEach((b, idx) => {
        tbody.innerHTML += `<tr>
            <td>${formatDateBR(b.data)}</td>
            <td>${b.conta}</td>
            <td>${b.forma}</td>
            <td class="text-warning">${b.amortizado}</td>
            <td class="text-success">${b.pago}</td>
            <td class="text-center"><button type="button" onclick="remPagBaixa(${idx})" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem">❌</button></td>
        </tr>`;
    });
    const hd = document.getElementById('pag_itens_baixas_json'); // Atualizado ID para match DB
    if(hd) hd.value = JSON.stringify(pagBaixasCache);
}
window.addPagBaixa = function() {
    const data = document.getElementById('tmp_pag_baixa_data').value;
    const conta = document.getElementById('tmp_pag_baixa_conta').options[document.getElementById('tmp_pag_baixa_conta').selectedIndex]?.text || '';
    const forma = document.getElementById('tmp_pag_baixa_forma').options[document.getElementById('tmp_pag_baixa_forma').selectedIndex]?.text || '';
    const amortizado = document.getElementById('tmp_pag_baixa_amortizado').value;
    const pago = document.getElementById('tmp_pag_baixa_pago').value;

    if(!data || !conta || (!amortizado && !pago)) return;
    pagBaixasCache.push({
        data, conta, forma, 
        amortizado: parseFloat(amortizado||0).toFixed(2), 
        pago: parseFloat(pago||0).toFixed(2)
    });
    
    document.getElementById('tmp_pag_baixa_data').value = '';
    document.getElementById('tmp_pag_baixa_amortizado').value = '';
    document.getElementById('tmp_pag_baixa_pago').value = '';
    renderPagBaixas();
};
window.remPagBaixa = function(idx) { pagBaixasCache.splice(idx, 1); renderPagBaixas(); };

function renderPagPlanos() {
    const tbody = document.querySelector('#tb_pag_planos tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    pagPlanosCache.forEach((p, idx) => {
        tbody.innerHTML += `<tr>
            <td>${p.plano}</td>
            <td class="text-danger">${p.valor}</td>
            <td class="text-center"><button type="button" onclick="remPagPlano(${idx})" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem">❌</button></td>
        </tr>`;
    });
    const hd = document.getElementById('pag_planos_contas_json');
    if(hd) hd.value = JSON.stringify(pagPlanosCache);
}
window.addPagPlano = function() {
    const sel = document.getElementById('tmp_pag_plano');
    const plano = sel.options[sel.selectedIndex]?.text || sel.value;
    const valor = document.getElementById('tmp_pag_plano_valor').value;
    if(!plano || !valor || sel.value === '') return;
    pagPlanosCache.push({ plano: plano, valor: parseFloat(valor).toFixed(2) });
    sel.value = ''; document.getElementById('tmp_pag_plano_valor').value = '';
    renderPagPlanos();
};
window.remPagPlano = function(idx) { pagPlanosCache.splice(idx, 1); renderPagPlanos(); };

// Cheques: Referências
function renderCheqRef() {
    const tbody = document.querySelector('#tb_cheq_referencias tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    cheqRefCache.forEach((r, idx) => {
        tbody.innerHTML += `<tr>
            <td>${r.num_doc}</td>
            <td>${formatDateBR(r.emissao)}</td>
            <td>${formatDateBR(r.vencimento)}</td>
            <td>${r.contato}</td>
            <td class="text-info">${r.valor}</td>
            <td>${r.situacao}</td>
            <td class="text-center"><button type="button" onclick="remCheqRef(${idx})" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem">❌</button></td>
        </tr>`;
    });
    const hd = document.getElementById('cheq_referencias_json');
    if(hd) hd.value = JSON.stringify(cheqRefCache);
}
window.addCheqRef = function() {
    const num_doc = document.getElementById('tmp_cheq_ref_doc').value;
    const emissao = document.getElementById('tmp_cheq_ref_emi').value;
    const vencimento = document.getElementById('tmp_cheq_ref_ven').value;
    const contato = document.getElementById('tmp_cheq_ref_contato').value;
    const valor = document.getElementById('tmp_cheq_ref_valor').value;
    const sitEl = document.getElementById('tmp_cheq_ref_sit');
    const situacao = sitEl.options[sitEl.selectedIndex]?.text || sitEl.value;

    if(!num_doc || !valor) return;
    cheqRefCache.push({ num_doc, emissao, vencimento, contato, valor: parseFloat(valor).toFixed(2), situacao });
    
    document.getElementById('tmp_cheq_ref_doc').value = '';
    document.getElementById('tmp_cheq_ref_valor').value = '';
    renderCheqRef();
};
window.remCheqRef = function(idx) { cheqRefCache.splice(idx, 1); renderCheqRef(); };

// Cheques: Histórico
function renderCheqHist() {
    const tbody = document.querySelector('#tb_cheq_historico tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    cheqHistCache.forEach((h, idx) => {
        tbody.innerHTML += `<tr>
            <td>${formatDateBR(h.data_reg)}</td>
            <td>${formatDateBR(h.data_stat)}</td>
            <td>${h.status}</td>
            <td class="text-warning">${h.usuario}</td>
            <td class="text-center"><button type="button" onclick="remCheqHist(${idx})" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem">❌</button></td>
        </tr>`;
    });
    const hd = document.getElementById('cheq_historico_json');
    if(hd) hd.value = JSON.stringify(cheqHistCache);
}
window.addCheqHist = function() {
    const data_reg = document.getElementById('tmp_cheq_hist_data_reg').value;
    const data_stat = document.getElementById('tmp_cheq_hist_data_stat').value;
    const statEl = document.getElementById('tmp_cheq_hist_status');
    const status = statEl.options[statEl.selectedIndex]?.text || statEl.value;
    const usuario = document.getElementById('tmp_cheq_hist_usuario').value;

    if(!data_reg || !status) return;
    cheqHistCache.push({ data_reg, data_stat, status, usuario });
    
    document.getElementById('tmp_cheq_hist_data_reg').value = '';
    document.getElementById('tmp_cheq_hist_usuario').value = '';
    renderCheqHist();
};
window.remCheqHist = function(idx) { cheqHistCache.splice(idx, 1); renderCheqHist(); };



// ==========================================
// CRUD / SERIALIZATION
// ==========================================
const ALIAS_MAP = {
    'numero': 'n_numero', 'vencimento': 'data_vencimento', 'abertura': 'data_abertura', 'fechamento': 'data_fechamento', 'caixa': 'pdc', 'data_conciliacao': 'data'
};

function serializeForm(formId, prefix) {
    const form = document.getElementById(formId);
    if (!form) return {};
    
    const inputs = form.querySelectorAll(`input:not(.ignore-serialize), select:not(.ignore-serialize), textarea:not(.ignore-serialize)`);
    const payload = {};

    inputs.forEach(input => {
        let key = input.id.replace(prefix, '');
        if (!key) return;

        if (input.type === 'checkbox') {
            payload[key] = input.checked ? 'S' : 'N';
        } else if (input.tagName === 'SELECT' && input.multiple) {
            payload[key] = Array.from(input.selectedOptions).map(opt => opt.value).join(', ');
        } else if (input.type !== 'file' && input.value !== undefined) {
            payload[key] = input.value;
            if(ALIAS_MAP[key]) payload[ALIAS_MAP[key]] = input.value;
        }
    });
    
    const idField = form.querySelector('input[type="hidden"]');
    if (idField && idField.value) payload['id'] = idField.value;

    return payload;
}

window.limparFormulario = function(formId) {
    const form = document.getElementById(formId);
    if(form) {
        form.reset();
        const idField = form.querySelector('input[type="hidden"]');
        if(idField) idField.value = '';
        
        form.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);

        if (formId === 'form_bandeiras') { bandeiraFaixasCache = []; renderBandeiraFaixas(); }
        if (formId === 'form_plano_contas') { planNaturezasCache = []; renderPlanNaturezas(); }
        if (formId === 'form_recebimentos') { 
            recPlanosCache = []; renderRecPlanos(); 
            recChequesCache = []; renderRecCheques();
            recBaixasCache = []; renderRecBaixas();
        }
        if (formId === 'form_pagamentos') { 
            pagPlanosCache = []; renderPagPlanos(); 
            pagBaixasCache = []; renderPagBaixas();
        }
        if (formId === 'form_cheques') {
            cheqRefCache = []; renderCheqRef();
            cheqHistCache = []; renderCheqHist();
        }
    }
}

window.dispatchEdit = function(formId, prefix, encoded) {
    const itemObj = JSON.parse(decodeURIComponent(encoded));
    const form = document.getElementById(formId);
    if(!form) return;
    
    limparFormulario(formId); 
    
    form.querySelectorAll('input:not([type="file"]), select, textarea').forEach(el => {
        let key = el.id.replace(prefix, '');
        let val = itemObj[key];
        
        if(val === undefined && ALIAS_MAP[key]) val = itemObj[ALIAS_MAP[key]];

        if (el.type === 'checkbox') {
            el.checked = (val === 'S' || val === true || val === 1);
        } else if (el.tagName === 'SELECT' && el.multiple) {
            let vals = (val || '').split(',').map(s => s.trim());
            Array.from(el.options).forEach(opt => opt.selected = vals.includes(opt.value));
        } else if (val !== undefined && val !== null) {
            el.value = safeVal(val);
        }
    });

    // Populate Grids Caches safely from JSON string
    if (formId === 'form_bandeiras') {
        bandeiraFaixasCache = parseSafeJSON(itemObj.faixas_json || itemObj.faixas_taxas_json);
        renderBandeiraFaixas();
    }
    if (formId === 'form_plano_contas') {
        planNaturezasCache = parseSafeJSON(itemObj.plan_naturezas_json || itemObj.naturezas_json);
        renderPlanNaturezas();
    }
    if (formId === 'form_recebimentos') {
        recPlanosCache = parseSafeJSON(itemObj.planos_contas_json || itemObj.rateio_json);
        renderRecPlanos();
        recChequesCache = parseSafeJSON(itemObj.cheques_json || itemObj.cheques);
        renderRecCheques();
        recBaixasCache = parseSafeJSON(itemObj.itens_baixas_json || itemObj.baixas);
        renderRecBaixas();
    }
    if (formId === 'form_pagamentos') {
        pagPlanosCache = parseSafeJSON(itemObj.planos_contas_json || itemObj.rateio_json);
        renderPagPlanos();
        pagBaixasCache = parseSafeJSON(itemObj.itens_baixas_json || itemObj.baixas);
        renderPagBaixas();
    }
    if (formId === 'form_cheques') {
        cheqRefCache = parseSafeJSON(itemObj.referencias_json);
        renderCheqRef();
        cheqHistCache = parseSafeJSON(itemObj.historico_json);
        renderCheqHist();
    }
    
    const tabs = form.querySelectorAll('.tab-btn');
    if(tabs.length > 0) switchFinTab(tabs[0], tabs[0].getAttribute('onclick').match(/'([^']+)'/)[1]);

    openModal(formId);
};

function actBtns(formId, prefix, item, tabela, loadFunc) {
    const encoded = encodeURIComponent(JSON.stringify(item)).replace(/'/g, "%27");
    return `<button type="button" class="btn-neon btn-neon-warning p-5" onclick="dispatchEdit('${formId}', '${prefix}', '${encoded}')">✏️</button>
            <button type="button" class="btn-neon btn-neon-danger p-5" onclick="deleteRecord('${tabela}', ${item.id}, ${loadFunc})">🗑️</button>`;
}

async function postRecord(tabela, payload, formId) {
    try {
        const res = await fetch(`/api/financeiro/${tabela}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if(res.ok) { 
            limparFormulario(formId);
            closeModal(formId);
            return true; 
        }
        return false;
    } catch(e) { return false; }
}

window.deleteRecord = async function(tabela, id, callback) {
    if(!confirm("Excluir registro permanentemente?")) return;
    try {
        const res = await fetch(`/api/financeiro/${tabela}/${id}`, { method: 'DELETE' });
        if(res.ok) callback();
    } catch(e) {}
}

window.salvarFinanceiro = async function(e, tabela) {
    e.preventDefault();
    const prefMap = {
        'pagamentos':'pag_', 'recebimentos': 'rec_', 'boletos':'bol_', 'cheques':'cheq_', 
        'plano_contas':'plan_', 'natureza':'nat_', 'condicoes':'cond_', 'formas':'form_', 
        'bandeiras':'band_', 'contas_bancarias':'cb_', 'bancos':'ban_', 'centro_custo':'cc_', 
        'status_financeiro':'stat_', 'operadoras':'op_', 'conciliacoes':'conc_', 'renegociacoes':'ren_',
        'transferencias': 'transf_', 'fechamento_pdv': 'fech_'
    };
    
    const prefix = prefMap[tabela] || `${tabela.substring(0,3)}_`;
    const formId = `form_${tabela}`;
    const payload = serializeForm(formId, prefix); 

    if (await postRecord(tabela, payload, formId)) {
        if(tabela === 'transferencias') loadFluxo(); 
        
        const loaders = {
            'recebimentos':loadRecebimentos, 'pagamentos':loadPagamentos, 'boletos':loadBoletos,
            'cheques':loadCheques, 'plano_contas':loadPlanoContas, 'natureza':loadNatureza, 
            'condicoes':loadCondicoes, 'formas':loadFormas, 'bandeiras':loadBandeiras, 
            'contas_bancarias':loadContasBancarias, 'bancos':loadBancos, 'centro_custo':loadCentroCusto, 
            'status_financeiro':loadStatus, 'conciliacoes':loadConciliacoes, 'renegociacoes':loadRenegociacoes,
            'transferencias': loadTransferencias, 'fechamento_pdv': loadFechamentoPdv
        };
        if (loaders[tabela]) loaders[tabela]();
    }
}

// ==========================================
// LOADERS E FILTROS
// ==========================================
async function loadFilteredDataFin(tabela, filters, rowCallback, tbId) {
    try {
        const res = await fetchNoCache(`/api/financeiro/${tabela}`);
        let data = await res.json();
        
        for (const [key, val] of Object.entries(filters)) {
            if (val && val.trim() !== '') {
                data = data.filter(item => {
                    let itemVal = item[key];
                    if(key === 'data_especial_aux') return true; 
                    
                    if(key === 'tipo_data') {
                        let dataRef = val === 'emissao' ? (item.data_emissao || item.emissao || item.data_criacao || item.data) : (val === 'pagamento' ? item.pagamento : item.vencimento);
                        let filtroData = filters['data_especial_aux'];
                        return !filtroData || dataRef === filtroData;
                    }

                    return String(itemVal).toLowerCase().includes(String(val).toLowerCase());
                });
            }
        }
        
        const tb = document.getElementById(tbId);
        tb.innerHTML = '';
        if (data.length === 0) tb.innerHTML = `<tr><td colspan="15" class="text-center text-muted">Nenhum registro encontrado.</td></tr>`;
        else data.forEach(i => { tb.innerHTML += rowCallback(i); });
    } catch(e) { console.error(e); }
}

window.loadRecebimentos = async function() {
    let auxDt = document.getElementById('filtro_rec_data')?.value;
    let tpDt = document.getElementById('filtro_rec_tipo_data')?.value || 'vencimento';
    
    const filters = {
        cliente: document.getElementById('filtro_rec_cliente_filtro')?.value,
        situacao: document.getElementById('filtro_rec_situacao')?.value,
        status: document.getElementById('filtro_rec_status')?.value,
        conta_banco: document.getElementById('filtro_rec_conta')?.value,
        forma_pgto: document.getElementById('filtro_rec_forma')?.value,
        plano_contas: document.getElementById('filtro_rec_plano')?.value,
        tipo_data: tpDt,
        data_especial_aux: auxDt
    };

    loadFilteredDataFin('recebimentos', filters, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${formatDateBR(i.data_emissao || i.emissao || i.data_criacao || i.data)}</td>
        <td>${formatDateBR(i.vencimento)}</td>
        <td class="font-bold">${safeVal(i.cliente)}</td>
        <td>${formatDateBR(i.pagamento)}</td>
        <td class="text-info font-bold">R$ ${i.valor||0}</td>
        <td class="text-success font-bold">R$ ${i.valor_recebido||0}</td>
        <td class="text-warning">R$ ${i.saldo_aberto || i.saldo || 0}</td>
        <td class="text-center">${actBtns('form_recebimentos', 'rec_', i, 'recebimentos', 'loadRecebimentos')}</td>
    </tr>`, 'tb_recebimentos');
}

window.loadPagamentos = async function() {
    let auxDt = document.getElementById('filtro_pag_data')?.value;
    let tpDt = document.getElementById('filtro_pag_tipo_data')?.value || 'vencimento';
    
    const filters = {
        fornecedor: document.getElementById('filtro_pag_fornecedor_filtro')?.value,
        situacao: document.getElementById('filtro_pag_situacao')?.value,
        status: document.getElementById('filtro_pag_status')?.value,
        conta_banco: document.getElementById('filtro_pag_conta')?.value,
        forma_pgto: document.getElementById('filtro_pag_forma')?.value,
        plano_contas: document.getElementById('filtro_pag_plano')?.value,
        tipo_data: tpDt,
        data_especial_aux: auxDt
    };

    loadFilteredDataFin('pagamentos', filters, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${formatDateBR(i.vencimento)}</td>
        <td class="font-bold text-warning">${safeVal(i.fornecedor)}</td>
        <td>${formatDateBR(i.pagamento)}</td>
        <td class="text-danger font-bold">R$ ${i.valor||0}</td>
        <td class="text-success font-bold">R$ ${i.valor_pago || i.vlr_pgto || 0}</td>
        <td class="text-warning">R$ ${i.saldo_aberto || i.saldo || 0}</td>
        <td class="text-center">${actBtns('form_pagamentos', 'pag_', i, 'pagamentos', 'loadPagamentos')}</td>
    </tr>`, 'tb_pagamentos');
}

window.loadBoletos = async function() {
    let auxDt = document.getElementById('filtro_bol_data')?.value;
    let tpDt = document.getElementById('filtro_bol_tipo_data')?.value || 'vencimento';
    
    const filters = {
        conta_cobranca: document.getElementById('filtro_bol_conta_cobranca')?.value,
        status: document.getElementById('filtro_bol_status')?.value,
        tipo_data: tpDt,
        data_especial_aux: auxDt
    };

    loadFilteredDataFin('boletos', filters, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${formatDateBR(i.vencimento)}</td>
        <td class="text-info">${safeVal(i.conta_cobranca || i.conta || i.banco)}</td>
        <td>${safeVal(i.nosso_numero)}</td>
        <td>${safeVal(i.documento || i.numero)}</td>
        <td>${safeVal(i.cliente)}</td>
        <td>${safeVal(i.remessa)}</td>
        <td class="font-bold">R$ ${i.valor||0}</td>
        <td>${safeVal(i.status)}</td>
        <td class="text-center">${actBtns('form_boletos', 'bol_', i, 'boletos', 'loadBoletos')}</td>
    </tr>`, 'tb_boletos');
}

window.loadCheques = async function() {
    let auxDt = document.getElementById('filtro_cheq_data')?.value;
    let tpDt = document.getElementById('filtro_cheq_tipo_data')?.value || 'vencimento';
    
    const filters = {
        portador: document.getElementById('filtro_cheq_portador')?.value,
        status: document.getElementById('filtro_cheq_status')?.value,
        tipo_data: tpDt,
        data_especial_aux: auxDt
    };

    loadFilteredDataFin('cheques', filters, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td class="text-warning">${safeVal(i.numero)}</td>
        <td>${safeVal(i.portador)}</td>
        <td>${formatDateBR(i.vencimento)}</td>
        <td class="font-bold">R$ ${i.valor||0}</td>
        <td>${formatDateBR(i.data_status)}</td>
        <td>${safeVal(i.status || i.situacao)}</td>
        <td class="text-center">${actBtns('form_cheques', 'cheq_', i, 'cheques', 'loadCheques')}</td>
    </tr>`, 'tb_cheques');
}

window.loadFluxo = async function() {
    const filters = {
        data: document.getElementById('filtro_flu_data')?.value,
        tipo: document.getElementById('filtro_flu_tipo')?.value,
        conta_banco: document.getElementById('filtro_flu_conta')?.value
    };

    loadFilteredDataFin('fluxo_caixa', filters, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${formatDateBR(i.data)}</td>
        <td class="${i.tipo === 'Entrada' ? 'text-success' : 'text-danger'} font-bold">${safeVal(i.tipo)}</td>
        <td>${safeVal(i.forma_pgto || i.forma_pagamento)}</td>
        <td>R$ ${i.valor||0}</td>
        <td class="text-muted">${safeVal(i.historico)}</td>
    </tr>`, 'tb_fluxo_caixa');
}

window.loadTransferencias = async function() {
    loadFilteredDataFin('transferencias', {}, i => `<tr>
        <td>${formatDateBR(i.data)}</td>
        <td class="text-danger font-bold">${safeVal(i.origem)}</td>
        <td class="text-success font-bold">${safeVal(i.destino)}</td>
        <td class="font-bold">R$ ${i.valor||0}</td>
        <td class="text-center"><button type="button" class="btn-neon btn-neon-danger" style="padding:2px 5px; font-size:0.7rem" onclick="deleteRecord('transferencias', ${i.id}, loadTransferencias)">🗑️</button></td>
    </tr>`, 'tb_transferencias');
}

window.loadFechamentoPdv = async function() {
    const filters = {
        data_fechamento: document.getElementById('filtro_fech_data')?.value,
        caixa: document.getElementById('filtro_fech_caixa')?.value,
        operador: document.getElementById('filtro_fech_operador')?.value
    };

    loadFilteredDataFin('fechamento_pdv', filters, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td class="font-bold">${safeVal(i.caixa || i.pdc)}</td>
        <td class="text-info">${safeVal(i.operador)}</td>
        <td>${formatDateBR(i.abertura)}</td>
        <td>${formatDateBR(i.data_fechamento || i.fechamento)}</td>
        <td class="text-success">${safeVal(i.conciliado)}</td>
        <td>R$ ${i.inicial||0}</td>
        <td class="font-bold text-warning">R$ ${i.final||0}</td>
    </tr>`, 'tb_fechamento_pdv');
}

window.loadComissoes = async function() {
    const filters = {
        data: document.getElementById('filtro_com_data')?.value,
        funcionario: document.getElementById('filtro_com_funcionario')?.value,
        status: document.getElementById('filtro_com_status')?.value,
        tipo: document.getElementById('filtro_com_tipo')?.value
    };

    loadFilteredDataFin('comissoes', filters, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${i.id}</td>
        <td>${formatDateBR(i.data)}</td>
        <td class="font-bold text-info">${safeVal(i.funcionario)}</td>
        <td>${safeVal(i.documento)}</td>
        <td class="text-success font-bold">R$ ${i.valor || i.vlr_comissao || 0}</td>
        <td>${safeVal(i.status)}</td>
    </tr>`, 'tb_comissoes');
}

window.loadConciliacoes = async function() {
    loadFilteredDataFin('conciliacoes', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${i.id}</td>
        <td>${formatDateBR(i.data)}</td>
        <td class="text-warning">${safeVal(i.banco)}</td>
        <td>${safeVal(i.agencia)}</td>
        <td>${safeVal(i.conta)}</td>
        <td>${safeVal(i.status)}</td>
        <td class="text-center">${actBtns('form_conciliacoes', 'conc_', i, 'conciliacoes', 'loadConciliacoes')}</td>
    </tr>`, 'tb_conciliacoes');
}

window.loadRenegociacoes = async function() {
    loadFilteredDataFin('renegociacoes', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${i.id}</td>
        <td>${safeVal(i.tipo)}</td>
        <td class="font-bold">${safeVal(i.para_quem)}</td>
        <td>${safeVal(i.status || i.conferencia_status)}</td>
        <td class="text-center">${actBtns('form_renegociacoes', 'ren_', i, 'renegociacoes', 'loadRenegociacoes')}</td>
    </tr>`, 'tb_renegociacoes');
}

window.loadPlanoContas = async function() {
    loadFilteredDataFin('plano_contas', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${i.id}</td>
        <td class="font-bold">${safeVal(i.nome)}</td>
        <td>${safeVal(i.tipo)}</td>
        <td>${safeVal(i.classificacao)}</td>
        <td>${safeVal(i.ocorrencia)}</td>
        <td>${i.inativo === 'S' ? 'Inativo' : 'Ativo'}</td>
        <td class="text-center">${actBtns('form_plano_contas', 'plan_', i, 'plano_contas', 'loadPlanoContas')}</td>
    </tr>`, 'tb_plano_contas');
}

window.loadNatureza = async function() {
    loadFilteredDataFin('natureza', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${i.id}</td>
        <td class="font-bold">${safeVal(i.descricao)}</td>
        <td>${safeVal(i.sku)}</td>
        <td class="text-center">${actBtns('form_natureza', 'nat_', i, 'natureza', 'loadNatureza')}</td>
    </tr>`, 'tb_natureza');
}

window.loadCondicoes = async function() {
    loadFilteredDataFin('condicoes', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td class="font-bold">${safeVal(i.nome)}</td>
        <td>${safeVal(i.forma_pgto)}</td>
        <td>${i.no_parcelas || 1}x</td>
        <td>${i.inativo === 'S' ? 'Inativo' : 'Ativo'}</td>
        <td class="text-center">${actBtns('form_condicoes', 'cond_', i, 'condicoes', 'loadCondicoes')}</td>
    </tr>`, 'tb_condicoes');
}

window.loadFormas = async function() {
    loadFilteredDataFin('formas', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${i.id}</td>
        <td class="font-bold">${safeVal(i.descricao)}</td>
        <td>${safeVal(i.codigo_fiscal)}</td>
        <td class="text-warning">${safeVal(i.conta_banco)}</td>
        <td>${i.inativo === 'S' ? 'Inativo' : 'Ativo'}</td>
        <td>${i.gera_financeiro === 'S' ? 'Sim' : 'Não'}</td>
        <td>${i.baixa_automatica === 'S' ? 'Sim' : 'Não'}</td>
        <td class="text-center">${actBtns('form_formas', 'form_', i, 'formas', 'loadFormas')}</td>
    </tr>`, 'tb_formas');
}

window.loadBandeiras = async function() {
    loadFilteredDataFin('bandeiras', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${i.id}</td>
        <td class="font-bold">${safeVal(i.nome)}</td>
        <td>${safeVal(i.f_pgto)}</td>
        <td>${safeVal(i.bandeira_nfe)}</td>
        <td class="text-info">${safeVal(i.operadora)}</td>
        <td>${i.inativo === 'S' ? 'Inativo' : 'Ativo'}</td>
        <td class="text-center">${actBtns('form_bandeiras', 'band_', i, 'bandeiras', 'loadBandeiras')}</td>
    </tr>`, 'tb_bandeiras');
}

window.loadContasBancarias = async function() {
    loadFilteredDataFin('contas_bancarias', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td class="font-bold">${safeVal(i.nome)}</td>
        <td class="text-info">${safeVal(i.conta_corrente || i.conta)}</td>
        <td>${safeVal(i.agencia)}</td>
        <td>${safeVal(i.juros_mes)}%</td>
        <td>${safeVal(i.multa)}%</td>
        <td>${safeVal(i.dias_de_carencia)}</td>
        <td class="text-center">${actBtns('form_contas_bancarias', 'cb_', i, 'contas_bancarias', 'loadContasBancarias')}</td>
    </tr>`, 'tb_contas_bancarias');
}

window.loadBancos = async function() {
    loadFilteredDataFin('bancos', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td>${safeVal(i.codigo || i.id)}</td>
        <td class="font-bold text-info">${safeVal(i.nome)}</td>
        <td class="text-center">${actBtns('form_bancos', 'ban_', i, 'bancos', 'loadBancos')}</td>
    </tr>`, 'tb_bancos');
}

window.loadCentroCusto = async function() {
    loadFilteredDataFin('centro_custo', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td class="font-bold text-warning">${safeVal(i.nome)}</td>
        <td class="text-center">${actBtns('form_centro_custo', 'cc_', i, 'centro_custo', 'loadCentroCusto')}</td>
    </tr>`, 'tb_centro_custo');
}

window.loadStatus = async function() {
    loadFilteredDataFin('status_financeiro', {}, i => `<tr>
        <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
        <td class="font-bold">${safeVal(i.nome)}</td>
        <td class="text-center">${actBtns('form_status_financeiro', 'stat_', i, 'status_financeiro', 'loadStatus')}</td>
    </tr>`, 'tb_status_financeiro');
}