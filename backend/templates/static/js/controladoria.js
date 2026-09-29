// Log de versão para garantir que o cache do navegador foi limpo
console.log("🟢 Módulo Controladoria JS carregado com sucesso (v2.5) - Correção Vínculo CFOP e Plano de Contas");

// ==========================================
// FUNÇÕES UTILITÁRIAS
// ==========================================
function safeVal(val) { return (val === null || val === undefined || String(val).trim()==='' || val==='null') ? '-' : val; }

function showMsg(text) {
    const painel = document.createElement('div');
    painel.style.cssText = "position:fixed; top:20px; right:20px; background:#111; border: 2px solid #00ffcc; padding: 15px 20px; border-radius: 8px; z-index:9999; color: #fff; text-align: left; box-shadow: 0 0 20px rgba(0, 255, 204, 0.4); font-size: 14px;";
    painel.innerHTML = `<strong>Aviso do Sistema:</strong><br><br>${text} <br><br><button type="button" onclick="this.parentElement.remove()" class="btn-neon btn-neon-danger w-full bg-transparent p-5">Fechar</button>`;
    document.body.appendChild(painel);
    setTimeout(() => { if (painel.parentElement) painel.remove(); }, 5000);
}

function fetchNoCacheCtrl(url) {
    const ts = new Date().getTime();
    const sep = url.includes('?') ? '&' : '?';
    return fetch(url + sep + '_t=' + ts, { cache: "no-store" });
}

window.getMultiSelectValues = function(id) {
    const el = document.getElementById(id);
    if (!el || !el.selectedOptions) return [];
    return Array.from(el.selectedOptions).map(opt => opt.value).filter(v => v !== '');
}

window.toggleAll = function(source) {
    const table = source.closest('table');
    if(table) {
        const checkboxes = table.querySelectorAll('tbody .row-check');
        checkboxes.forEach(cb => cb.checked = source.checked);
    }
};

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
            if (j === 0 && cols[j].querySelector('input[type="checkbox"]')) continue; 
            
            let clone = cols[j].cloneNode(true);
            clone.querySelectorAll('button').forEach(b => b.remove()); 
            let data = clone.innerText.replace(/"/g, '""').trim();
            row.push('"' + data + '"');
        }
        if(row.length > 0) csv.push(row.join(';'));
    }
    
    let csvFile = new Blob(["\ufeff" + csv.join('\r\n')], {type: 'text/csv;charset=utf-8;'});
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
// SISTEMA DE MODAIS (CADASTRO / EDIÇÃO)
// ==========================================
function openModalCtrl(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.style.display = 'flex';
}

function closeModalCtrl(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.style.display = 'none';
}

function novoCadastroControladoria(formId) {
    limparFormulario(formId);
    openModalCtrl(formId);
}

// ==========================================
// INTEGRAÇÃO IBGE (UFs e MUNICÍPIOS)
// ==========================================
async function carregarUFsIBGE() {
    try {
        const res = await fetch('https://servicodados.ibge.gov.br/api/v1/localidades/estados');
        let ufs = await res.json();
        ufs.sort((a, b) => a.sigla.localeCompare(b.sigla));

        let html = '<option value="">Selecione</option>';
        ufs.forEach(uf => {
            html += `<option value="${uf.sigla}">${uf.sigla} - ${uf.nome}</option>`;
        });

        document.querySelectorAll('.ddl-ufs').forEach(el => {
            el.innerHTML = html;
        });
    } catch(e) {
        console.error("Erro ao carregar UFs do IBGE", e);
    }
}

window.carregarMunicipios = async function(uf, targetId, selectedCity = '') {
    const select = document.getElementById(targetId);
    if (!select) return;

    if (!uf) {
        select.innerHTML = '<option value="">Selecione a UF primeiro</option>';
        return;
    }

    select.innerHTML = '<option value="">Carregando...</option>';
    try {
        const res = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${uf}/municipios`);
        let municipios = await res.json();
        municipios.sort((a, b) => a.nome.localeCompare(b.nome));

        let html = '<option value="">Selecione</option>';
        municipios.forEach(m => {
            html += `<option value="${m.nome}">${m.nome}</option>`;
        });
        select.innerHTML = html;

        if (selectedCity) {
            select.value = selectedCity;
        }
    } catch(e) {
        console.error("Erro ao carregar municípios", e);
        select.innerHTML = '<option value="">Erro ao carregar</option>';
    }
};

// ==========================================
// AUTOPREENCHIMENTO CEP E RECEITA
// ==========================================
window.buscarCep = async function(cep, prefix) {
    let cleanCep = cep.replace(/\D/g, '');
    if (cleanCep.length !== 8) return;
    try {
        let res = await fetch(`https://viacep.com.br/ws/${cleanCep}/json/`);
        let data = await res.json();
        
        if (!data.erro) {
            if(document.getElementById(prefix + 'logradouro')) document.getElementById(prefix + 'logradouro').value = data.logradouro;
            if(document.getElementById(prefix + 'bairro')) document.getElementById(prefix + 'bairro').value = data.bairro;
            
            let ufField = document.getElementById(prefix + 'uf');
            if (ufField && data.uf) {
                ufField.value = data.uf;
                await window.carregarMunicipios(data.uf, prefix + 'municipio', data.localidade);
            }
        }
    } catch(e) {}
};

window.autoFillNatReceita = function() {
    const cstPis = document.getElementById('int_cst_pis')?.value;
    const cstCofins = document.getElementById('int_cst_cofins')?.value;
    const input = document.getElementById('int_nat_receita');
    if (!input) return;
    
    if (cstPis === '01' || cstCofins === '01') input.value = "101 - Receita Bruta";
    else if (cstPis === '04' || cstCofins === '04') input.value = "102 - Receita Financeira";
    else input.value = "999 - Não se aplica";
};

// ==========================================
// CONTROLE DO MENU LATERAL E DROPDOWNS
// ==========================================
window.emitentesCache = []; 
window.tributacoesCache = [];
window.planoContasCache = []; // Nova Cache para Plano de Contas

async function switchControladoriaView(viewId, btnElement) {
    document.querySelectorAll('.erp-view, .menu-item').forEach(el => el.classList.remove('active'));
    document.getElementById(viewId)?.classList.add('active');
    btnElement?.classList.add('active');
    localStorage.setItem('lastCtrlView', viewId);
    await loadDropdownsControladoria();

    const loadMap = {
        'view_emitentes': loadEmitentes, 'view_contadores': loadContadores,
        'view_integracao': loadIntegracaoFiscal, 'view_cfop': loadCfops,
        'view_tributacoes': loadTributacoes, 'view_usuarios': loadUsuarios,
        'view_precos': loadTabelasPreco, 'view_portarias': loadPortarias,
        'view_plano_contas': loadPlanoContas 
    };
    if (loadMap[viewId]) loadMap[viewId]();
}

async function loadDropdownsControladoria() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/opcoes_formularios'); 
        const data = await res.json();
        
        let htmlCfop = '<option value="">--Selecione--</option>';
        if(data.cfops) data.cfops.forEach(c => htmlCfop += `<option value="${c.cfop}">${c.cfop} - ${c.nome}</option>`);
        if(document.getElementById('int_cfop')) document.getElementById('int_cfop').innerHTML = htmlCfop;

        let resCnt = await fetchNoCacheCtrl('/api/controladoria/contadores');
        let dataCnt = await resCnt.json();
        let htmlCnt = '<option value="">--Selecione--</option>';
        dataCnt.forEach(c => htmlCnt += `<option value="${c.nome}">${c.nome}</option>`);
        if(document.getElementById('emi_contabilidade')) document.getElementById('emi_contabilidade').innerHTML = htmlCnt;

        let resEmi = await fetchNoCacheCtrl('/api/controladoria/emitentes');
        let dataEmi = await resEmi.json();
        window.emitentesCache = dataEmi; 
        let selEmp = document.getElementById('int_empresa_nome');
        if (selEmp) {
            const currentVal = selEmp.value;
            let htmlEmi = '<option value="">--Selecione--</option>';
            dataEmi.forEach(e => htmlEmi += `<option value="${e.razao_social || e.fantasia}" data-cnpj="${e.cnpj||''}">${e.razao_social || e.fantasia}</option>`);
            selEmp.innerHTML = htmlEmi;
            if (currentVal) selEmp.value = currentVal;
        }

        // CARREGA PLANO DE CONTAS PARA CACHE E DROPDOWN
        let resPlano = await fetchNoCacheCtrl('/api/controladoria/plano_contas');
        if(resPlano.ok) {
            window.planoContasCache = await resPlano.json();
            let cfoPlano = document.getElementById('cfo_plano_conta');
            if (cfoPlano) {
                const curVal = cfoPlano.value;
                let htmlPlano = '<option value="">--Selecione o Plano de Contas--</option>';
                window.planoContasCache.forEach(p => htmlPlano += `<option value="${p.nome}">${p.codigo_cta||''} - ${p.nome}</option>`);
                cfoPlano.innerHTML = htmlPlano;
                if(curVal) cfoPlano.value = curVal;
            }
        }
        
    } catch(e) {}
}

async function populateDropdown(endpoint, targetSelectId, valueField, textField, emptyText='--Selecione--') {
    try {
        const res = await fetchNoCacheCtrl(endpoint);
        if(!res.ok) return;
        const data = await res.json();
        const select = document.getElementById(targetSelectId);
        if (!select) return;
        
        const currentValue = select.value;
        select.innerHTML = emptyText ? `<option value="">${emptyText}</option>` : '';
        data.forEach(item => select.insertAdjacentHTML('beforeend', `<option value="${item[valueField]}">${item[textField]}</option>`));
        if (currentValue) select.value = currentValue;
    } catch (e) {}
}

document.addEventListener("DOMContentLoaded", () => {
    carregarUFsIBGE().then(() => {
        loadDropdownsControladoria().then(() => {
            let lastView = localStorage.getItem('lastCtrlView') || 'view_emitentes';
            let btn = document.querySelector(`button[onclick*="${lastView}"]`) || document.querySelector('.menu-item');
            if(btn) switchControladoriaView(lastView, btn);
        });
    });

    populateDropdown('/api/controladoria/integracao_fiscal', 'tri_integracao_fiscal', 'descricao', 'descricao', '--Selecione--');
    populateDropdown('/api/controladoria/integracao_fiscal', 'filtro_integracao', 'descricao', 'descricao', null);

    const intEmpresaSelect = document.getElementById('int_empresa_nome');
    if (intEmpresaSelect) {
        intEmpresaSelect.addEventListener('change', function() {
            const opt = this.options[this.selectedIndex];
            document.getElementById('int_empresa_cnpj').value = (opt && opt.getAttribute('data-cnpj')) ? opt.getAttribute('data-cnpj') : '';
        });
    }
});

// ==========================================
// REGRAS DE NEGÓCIO - VÍNCULO CFOP <-> PLANO DE CONTAS
// ==========================================
window.vincularPlanoContaCFOP = function(nomePlano) {
    const inputTipo = document.getElementById('cfo_tipo');
    const inputNatCredito = document.getElementById('cfo_nat_credito');
    
    if (!inputTipo || !inputNatCredito) return;
    
    if (!nomePlano) {
        inputTipo.value = '';
        inputNatCredito.value = '';
        return;
    }
    
    const planoEncontrado = window.planoContasCache.find(p => p.nome === nomePlano);
    
    if (planoEncontrado) {
        inputTipo.value = planoEncontrado.tipo || '';
        inputNatCredito.value = planoEncontrado.natureza || '';
    } else {
        inputTipo.value = '';
        inputNatCredito.value = '';
    }
}

// ==========================================
// UTILIDADES CRUD GENÉRICO
// ==========================================
function limparFormulario(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.reset();
        const idField = form.querySelector('input[type="hidden"]');
        if(idField) idField.value = '';

        form.querySelectorAll('select[id$="_municipio"]').forEach(el => {
            el.innerHTML = '<option value="">Selecione a UF primeiro</option>';
        });

        document.querySelectorAll(`#${formId} .dynamic-list`).forEach(tbody => {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Aguardando inserção.</td></tr>';
        });
    }
}

function serializeForm(formId, prefix) {
    const inputs = document.querySelectorAll(`#${formId} input:not(.ignore-serialize), #${formId} select:not(.ignore-serialize), #${formId} textarea:not(.ignore-serialize)`);
    const payload = {};
    inputs.forEach(input => {
        let key = input.id.replace(prefix, '');
        if(key) {
            if(input.type === 'checkbox') {
                payload[key] = input.checked ? 'S' : 'N';
            } else if (input.multiple) { 
                payload[key] = Array.from(input.selectedOptions).map(opt => opt.value).join(', ');
            } else {
                payload[key] = input.value;
            }
        }
    });
    return payload;
}

window.dispatchEdit = async function(formId, prefix, encoded) {
    try {
        const itemObj = JSON.parse(decodeURIComponent(encoded));
        limparFormulario(formId);

        for (const [key, value] of Object.entries(itemObj)) {
            if (key === 'municipio') continue; 
            
            const el = document.getElementById(prefix + key);
            if (el) {
                if(el.type === 'checkbox') {
                    el.checked = (value === 'S');
                } else if (el.multiple) { 
                    const vals = (value || '').toString().split(',').map(v => v.trim());
                    Array.from(el.options).forEach(opt => {
                        opt.selected = vals.includes(opt.value);
                    });
                } else {
                    el.value = (value !== null && value !== undefined) ? value : '';
                }
            }
        }

        const ufEl = document.getElementById(prefix + 'uf');
        if (ufEl && itemObj.uf) {
            await window.carregarMunicipios(itemObj.uf, prefix + 'municipio', itemObj.municipio);
        }

        if (formId === 'form_integracao_fiscal' && itemObj.tabelas_uf_json) {
             renderizarTabelaInterna('tb_tabelas_uf', JSON.parse(itemObj.tabelas_uf_json || '[]'));
        }
        openModalCtrl(formId);
        
        // --- GARANTIA: Aciona o vínculo visualmente após preencher o formulário de edição de CFOP
        if (formId === 'form_cfops') {
            const planoEl = document.getElementById('cfo_plano_conta');
            if (planoEl) window.vincularPlanoContaCFOP(planoEl.value);
        }

    } catch (e) { console.error(e); }
};

// ==========================================
// LÓGICA DE GRID INTERNA (TABELAS UF COM MODAL)
// ==========================================

let linhaEdicaoAtual = null;

window.abrirModalUF = function(btnContexto = null) {
    document.getElementById('form_integracao_uf').reset();
    
    if (btnContexto) {
        linhaEdicaoAtual = btnContexto.closest('tr');
        let jsonData = linhaEdicaoAtual.getAttribute('data-json');
        if (jsonData) {
            let data = JSON.parse(jsonData);
            for(let key in data) {
                let input = document.getElementById('uf_' + key);
                if (input) {
                    if (input.type === 'checkbox') input.checked = (data[key] === 'S');
                    else input.value = data[key];
                }
            }
        }
    } else {
        linhaEdicaoAtual = null;
    }
    
    document.getElementById('form_integracao_uf_modal').style.display = 'flex';
};

window.salvarModalUF = function(e) {
    e.preventDefault();
    let payload = serializeForm('form_integracao_uf', 'uf_');
    
    let rowHtml = `
        <td class="font-bold text-info">${payload.uf}</td>
        <td>${payload.p_base_icms || '-'}</td>
        <td>${payload.p_base_icms_st || '-'}</td>
        <td>${payload.aliq_icms_st || '-'}</td>
        <td class="text-center">
            <button type="button" class="btn-neon-warning bg-transparent p-5" style="font-size:0.75rem;" onclick="abrirModalUF(this)">✏️</button>
            <button type="button" class="btn-neon-danger bg-transparent p-5" style="font-size:0.75rem;" onclick="this.closest('tr').remove()">X</button>
        </td>
    `;
    
    if (linhaEdicaoAtual) {
        linhaEdicaoAtual.innerHTML = rowHtml;
        linhaEdicaoAtual.setAttribute('data-json', JSON.stringify(payload));
    } else {
        let tr = document.createElement('tr');
        tr.innerHTML = rowHtml;
        tr.setAttribute('data-json', JSON.stringify(payload));
        document.getElementById('tb_tabelas_uf').appendChild(tr);
    }
    
    let placeholder = document.querySelector('#tb_tabelas_uf .text-muted');
    if(placeholder) placeholder.closest('tr').remove();
    
    document.getElementById('form_integracao_uf_modal').style.display = 'none';
};

function extrairTabelaInterna(tableId) {
    const tb = document.getElementById(tableId);
    if(!tb) return "[]";
    const data = [];
    tb.querySelectorAll('tr[data-json]').forEach(tr => {
        try { data.push(JSON.parse(tr.getAttribute('data-json'))); } catch(e){}
    });
    return JSON.stringify(data);
}

function renderizarTabelaInterna(tableId, dataArray) {
    const tb = document.getElementById(tableId);
    if(!tb) return;
    tb.innerHTML = '';
    
    if (!dataArray || dataArray.length === 0) {
        tb.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Aguardando UFs.</td></tr>`; 
        return;
    }
    
    dataArray.forEach(row => {
        let cols = `
            <td class="font-bold text-info">${row.uf || ''}</td>
            <td>${row.p_base_icms || '-'}</td>
            <td>${row.p_base_icms_st || '-'}</td>
            <td>${row.aliq_icms_st || '-'}</td>
            <td class="text-center">
                <button type="button" class="btn-neon-warning bg-transparent p-5" style="font-size:0.75rem;" onclick="abrirModalUF(this)">✏️</button>
                <button type="button" class="btn-neon-danger bg-transparent p-5" style="font-size:0.75rem;" onclick="this.closest('tr').remove()">X</button>
            </td>
        `;
        let tr = document.createElement('tr');
        tr.innerHTML = cols;
        tr.setAttribute('data-json', JSON.stringify(row));
        tb.appendChild(tr);
    });
}

// ==========================================
// SALVAR E EXCLUIR
// ==========================================
async function postRecordCtrl(tabela, payload, formId) {
    try {
        const res = await fetch(`/api/controladoria/${tabela}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if(res.ok) { limparFormulario(formId); return true; }
        showMsg('Erro ao salvar os dados.'); return false;
    } catch(e) { showMsg('Falha de rede.'); return false; }
}

async function deleteRecordCtrl(tabela, id, callbackLoad) {
    if(!confirm("Tem certeza que deseja excluir?")) return;
    try { const res = await fetch(`/api/controladoria/${tabela}/${id}`, { method: 'DELETE' }); if(res.ok) window[callbackLoad](); } catch(e) {}
}

async function salvarControladoria(e, tabela) {
    if (e) e.preventDefault();
    
    if(tabela === 'usuarios') {
        const s = document.getElementById('usr_senha').value;
        const rs = document.getElementById('usr_repetir_senha').value;
        if (s !== rs) { showMsg("As senhas não coincidem!"); return; }
    }

    let prefixMap = { 'emitentes': 'emi_', 'usuarios': 'usr_', 'cfop': 'cfo_', 'cfops': 'cfo_', 'portarias': 'prt_', 'integracao_fiscal': 'int_', 'contadores': 'cnt_', 'tabelas_preco': 'prc_', 'tributacoes': 'tri_', 'plano_contas': 'pla_' };
    let loadMap = { 'emitentes': loadEmitentes, 'usuarios': loadUsuarios, 'cfop': loadCfops, 'cfops': loadCfops, 'portarias': loadPortarias, 'integracao_fiscal': loadIntegracaoFiscal, 'contadores': loadContadores, 'tabelas_preco': loadTabelasPreco, 'tributacoes': loadTributacoes, 'plano_contas': loadPlanoContas };
    
    const apiTable = (tabela === 'cfops') ? 'cfop' : tabela;
    const formId = `form_${tabela}`;
    const payload = serializeForm(formId, prefixMap[tabela]);

    if (tabela === 'integracao_fiscal') {
        payload.tabelas_uf_json = extrairTabelaInterna('tb_tabelas_uf');
    }

    // --- GARANTIA: Força a injeção da natureza de crédito e do tipo direto no objeto do Backend ---
    if (tabela === 'cfops' || tabela === 'cfop') {
        const cfoPlano = document.getElementById('cfo_plano_conta');
        if (cfoPlano && cfoPlano.value) {
            const planoEncontrado = window.planoContasCache.find(p => p.nome === cfoPlano.value);
            if (planoEncontrado) {
                payload['tipo'] = planoEncontrado.tipo || '';
                payload['nat_credito'] = planoEncontrado.natureza || '';
            }
        }
    }

    if(await postRecordCtrl(apiTable, payload, formId)) {
        showMsg("✅ Registro salvo com sucesso!");
        closeModalCtrl(formId);
        
        // Se salvar plano de contas, atualiza a cache e dropdowns
        if(tabela === 'plano_contas') await loadDropdownsControladoria();
        
        if(loadMap[tabela]) loadMap[tabela]();
    }
}

function actBtns(frm, prefix, item, tbName, loadFunc) {
    let enc = encodeURIComponent(JSON.stringify(item)).replace(/'/g, "%27");
    return `<button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEdit('${frm}', '${prefix}', '${enc}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordCtrl('${tbName}', ${item.id}, '${loadFunc}')">🗑️</button>`;
}

// ==========================================
// MODAL DE PESQUISA (NCM)
// ==========================================
let alvoId = null; let alvoNome = null; let baseEndpoint = '';
window.abrirPesquisa = function(entidade, idInput, nomeInput) {
    alvoId = idInput; alvoNome = nomeInput; baseEndpoint = entidade;
    document.getElementById('mpesq_titulo').innerText = `Pesquisar ${entidade}`;
    document.getElementById('mpesq_input').value = '';
    document.getElementById('mpesq_tb').innerHTML = '<tr><td colspan=\"3\" class=\"text-center text-muted\">Aguardando busca...</td></tr>';
    document.getElementById('modal_pesquisa_generica').style.display = 'flex';
};
window.fecharPesquisa = function() { document.getElementById('modal_pesquisa_generica').style.display = 'none'; };
window.executarPesquisa = async function() {
    const q = document.getElementById('mpesq_input').value;
    try {
        const res = await fetchNoCacheCtrl(`/api/controladoria/pesquisar/${baseEndpoint}?q=${q}`);
        const data = await res.json();
        const tb = document.getElementById('mpesq_tb'); tb.innerHTML = '';
        if(data.length === 0) { tb.innerHTML = '<tr><td colspan=\"3\" class=\"text-center text-muted\">Nenhum registro encontrado</td></tr>'; return; }
        data.forEach(i => { tb.innerHTML += `<tr><td>${i.id}</td><td>${i.nome}</td><td class=\"text-center\"><button type=\"button\" class=\"btn-neon btn-neon-success\" style=\"padding:2px 8px; font-size:0.7rem;\" onclick=\"selecionarPesquisa('${i.id}', '${i.nome.replace(/'/g, "\\'")}')\">OK</button></td></tr>`; });
    } catch(e) {}
};
window.selecionarPesquisa = function(id, nome) {
    if(document.getElementById(alvoId)) document.getElementById(alvoId).value = id;
    if(document.getElementById(alvoNome)) document.getElementById(alvoNome).value = nome;
    fecharPesquisa();
};

// ==========================================
// CARGAS DE DADOS (LOADERS) & FILTROS
// ==========================================
window.filtrarTributacoes = function() {
    const fData = document.getElementById('filtro_data').value;
    const fFin = getMultiSelectValues('filtro_finalidade').map(v => v.toLowerCase());
    const fPes = document.getElementById('filtro_pessoa').value.toLowerCase();
    const fCon = document.getElementById('filtro_consumidor').value.toLowerCase();
    const fInt = getMultiSelectValues('filtro_integracao').map(v => v.toLowerCase());
    const fTip = document.getElementById('filtro_tipo_trib').value.toLowerCase();
    const fIna = document.getElementById('filtro_inativo').value;

    const filtered = window.tributacoesCache.filter(i => {
        let match = true;
        if(fData && i.data_registro !== fData) match = false;
        if(fFin.length > 0 && !fFin.some(val => (i.finalidade||'').toLowerCase().includes(val))) match = false;
        if(fPes && !(i.tipo_pessoa||'').toLowerCase().includes(fPes)) match = false;
        if(fCon && !(i.consumidor_final||'').toLowerCase().includes(fCon)) match = false;
        if(fInt.length > 0 && !fInt.some(val => (i.integracao_fiscal||'').toLowerCase().includes(val))) match = false;
        if(fTip && !(i.tipo_tributacao||'').toLowerCase().includes(fTip)) match = false;
        if(fIna && i.inativo !== fIna) match = false;
        return match;
    });
    renderTributacoesGrid(filtered);
};

window.limparFiltrosTributacao = function() {
    document.querySelectorAll('.filter-bar input, .filter-bar select').forEach(el => {
        if (el.multiple) el.selectedIndex = -1; else el.value = '';
    });
    renderTributacoesGrid(window.tributacoesCache);
};

function renderTributacoesGrid(data) {
    const tb = document.getElementById('tb_tributacoes'); tb.innerHTML = '';
    data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="text-muted">#${i.id}</td><td>${safeVal(i.data_registro)}</td><td>${safeVal(i.finalidade)}</td><td>${safeVal(i.tipo_pessoa)}</td><td>${safeVal(i.consumidor_final)}</td><td>${safeVal(i.ncm)}</td><td class="font-bold text-success">${safeVal(i.uf)}</td><td class="text-warning">${safeVal(i.integracao_fiscal)}</td><td class="text-info">${safeVal(i.tipo_tributacao)}</td><td class="text-center">${actBtns('form_tributacoes', 'tri_', i, 'tributacoes', 'loadTributacoes')}</td></tr>`; });
}

async function loadTributacoes() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/tributacoes'); 
        window.tributacoesCache = await res.json();
        filtrarTributacoes();
    } catch(e) {}
}

async function loadPlanoContas() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/plano_contas'); const data = await res.json();
        const tb = document.getElementById('tb_plano_contas'); tb.innerHTML = '';
        data.forEach(i => { 
            tb.innerHTML += `<tr>
                <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
                <td class="text-muted">${safeVal(i.nivel)}</td>
                <td class="text-warning font-bold">${safeVal(i.codigo_cta)}</td>
                <td class="text-info font-bold">${safeVal(i.nome)}</td>
                <td>${safeVal(i.tipo)}</td>
                <td>${safeVal(i.natureza)}</td>
                <td>${safeVal(i.classificacao)}</td>
                <td class="${i.inativo==='S'?'text-danger':'text-success'}">${i.inativo==='S'?'Inativo':'Ativo'}</td>
                <td class="text-center">${actBtns('form_plano_contas', 'pla_', i, 'plano_contas', 'loadPlanoContas')}</td>
            </tr>`; 
        });
    } catch(e) {}
}

async function loadEmitentes() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/emitentes'); const data = await res.json();
        const tb = document.getElementById('tb_emitentes'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="text-info font-bold">${safeVal(i.razao_social)}</td><td class="text-warning">${safeVal(i.cnpj)}</td><td>${safeVal(i.crt)}</td><td>${safeVal(i.municipio)}/${safeVal(i.uf)}</td><td class="${i.inativo==='S'?'text-danger':'text-success'}">${i.inativo==='S'?'Inativo':'Ativo'}</td><td class="text-center">${actBtns('form_emitentes', 'emi_', i, 'emitentes', 'loadEmitentes')}</td></tr>`; });
    } catch(e) {}
}

async function loadContadores() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/contadores'); const data = await res.json();
        const tb = document.getElementById('tb_contadores'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="font-bold text-info">${safeVal(i.nome)}</td><td>${safeVal(i.crc)}</td><td>${safeVal(i.telefone)}</td><td>${safeVal(i.email)}</td><td class="text-center">${actBtns('form_contadores', 'cnt_', i, 'contadores', 'loadContadores')}</td></tr>`; });
    } catch(e) {}
}

async function loadIntegracaoFiscal() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/integracao_fiscal'); const data = await res.json();
        const tb = document.getElementById('tb_integracao_fiscal'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="text-muted">#${i.id}</td><td class="font-bold">${safeVal(i.descricao)}</td><td class="text-info">${safeVal(i.cfop)}</td><td>${safeVal(i.tipo)}</td><td>${safeVal(i.cst_icms)}</td><td>${safeVal(i.cst_pis)}</td><td>${safeVal(i.cst_cofins)}</td><td>${safeVal(i.cst_ipi)}</td><td>${safeVal(i.nat_receita)}</td><td class="${i.inativo==='S'?'text-danger':'text-success'}">${i.inativo==='S'?'Inativo':'Ativo'}</td><td class="text-center">${actBtns('form_integracao_fiscal', 'int_', i, 'integracao_fiscal', 'loadIntegracaoFiscal')}</td></tr>`; });
        populateDropdown('/api/controladoria/integracao_fiscal', 'tri_integracao_fiscal', 'descricao', 'descricao', '--Selecione--');
        populateDropdown('/api/controladoria/integracao_fiscal', 'filtro_integracao', 'descricao', 'descricao', null);
    } catch(e) {}
}

async function loadCfops() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/cfop'); const data = await res.json();
        const tb = document.getElementById('tb_cfops'); tb.innerHTML = '';
        data.forEach(i => { 
            let badgeEstoque = (i.movimenta_estoque === 'S') ? '<span class="text-success font-bold">SIM</span>' : '<span class="text-danger font-bold">NÃO</span>';
            tb.innerHTML += `<tr>
                <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
                <td class="font-bold text-primary">${safeVal(i.codigo_cfop)}</td>
                <td class="text-white">${safeVal(i.nome)}</td>
                <td class="text-muted">${safeVal(i.plano_conta)}</td>
                <td class="${i.tipo==='Receita'?'text-success':'text-warning'}">${safeVal(i.tipo)}</td>
                <td class="text-info">${safeVal(i.nat_credito)}</td>
                <td>${badgeEstoque}</td>
                <td class="text-center">${actBtns('form_cfops', 'cfo_', i, 'cfop', 'loadCfops')}</td>
            </tr>`; 
        });
    } catch(e) {}
}

async function loadTabelasPreco() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/tabelas_preco'); const data = await res.json();
        const tb = document.getElementById('tb_tabelas_preco'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="font-bold text-success">${safeVal(i.nome)}</td><td class="text-center">${actBtns('form_tabelas_preco', 'prc_', i, 'tabelas_preco', 'loadTabelasPreco')}</td></tr>`; });
    } catch(e) {}
}

async function loadUsuarios() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/usuarios'); const data = await res.json();
        const tb = document.getElementById('tb_usuarios'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="font-bold">${safeVal(i.nome)}</td><td class="text-warning">${safeVal(i.usuario)}</td><td>${safeVal(i.telefone)}</td><td class="text-info">${safeVal(i.email)}</td><td class="text-center">${actBtns('form_usuarios', 'usr_', i, 'usuarios', 'loadUsuarios')}</td></tr>`; });
    } catch(e) {}
}

async function loadPortarias() {
    try {
        const res = await fetchNoCacheCtrl('/api/controladoria/portarias'); const data = await res.json();
        const tb = document.getElementById('tb_portarias'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="text-muted">#${i.id}</td><td class="text-warning font-bold">${safeVal(i.nome)}</td><td>${safeVal(i.mensagem).substring(0,30)}...</td><td>${safeVal(i.tipo)}</td><td class="text-center">${actBtns('form_portarias', 'prt_', i, 'portarias', 'loadPortarias')}</td></tr>`; });
    } catch(e) {}
}