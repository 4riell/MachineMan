// ==========================================
// GESTÃO DE MODAIS E CONTROLO DE VISTAS
// ==========================================
async function switchComercialView(viewId, btnElement) {
    document.querySelectorAll('.erp-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(viewId).classList.add('active');
    btnElement.classList.add('active');

    localStorage.setItem('lastComercialView', viewId);
    await loadDropdownsComercial();

    const loadMapComercial = {
        'view_nfe': loadNfe, 'view_nfce': loadNfce, 'view_nfse': loadNfse,
        'view_pedidos': loadPedidos, 'view_canais': loadCanaisVenda, 
        'view_promocoes': loadPromocoes, 'view_metas': loadMetas, 
        'view_integracoes': loadIntegracoes, 'view_relatorios': loadRelatorios
    };
    
    if (loadMapComercial[viewId]) loadMapComercial[viewId]();
}

function openModal(formId) {
    const modal = document.getElementById(formId + '_modal');
    if(modal) modal.classList.add('active');
}

function closeModal(formId) {
    const modal = document.getElementById(formId + '_modal');
    if(modal) modal.classList.remove('active');
}

function novoCadastro(formId) {
    limparFormulario(formId);
    openModal(formId);
}

function limparFormulario(formId) {
    const form = document.getElementById(formId);
    if(form) {
        form.reset();
        const idField = form.querySelector('input[type="hidden"]');
        if(idField) idField.value = '';
        form.querySelectorAll('.dynamic-list').forEach(tbody => tbody.innerHTML = '');
        form.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
    }
}

document.addEventListener("DOMContentLoaded", () => { 
    let lastView = localStorage.getItem('lastComercialView') || 'view_nfe';
    let btn = document.querySelector(`button[onclick*="${lastView}"]`);
    
    if(btn) switchComercialView(lastView, btn);
    else {
        let firstBtn = document.querySelector('.menu-item');
        if(firstBtn) switchComercialView('view_nfe', firstBtn);
    }
});

// ==========================================
// FUNÇÕES GLOBAIS
// ==========================================
window.toggleAll = function(source) {
    const table = source.closest('table');
    const checkboxes = table.querySelectorAll('tbody .row-check');
    checkboxes.forEach(cb => cb.checked = source.checked);
};

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

window.precosProdutos = {};
window.unidadesProdutos = {};
window.transportadorasData = [];
window.veiculosData = [];

window.optionsCfops = '<option value="">-- CFOP --</option>';
window.optionsUnidades = '<option value="">-- Unidade --</option>';

window.optionsFormasPgto = '<option value="">-- Forma Pgto --</option>';
window.optionsCondicoes = '<option value="">-- Condição --</option>';
window.optionsBancos = '<option value="">-- Banco --</option>';

window.onProdutoChange = function(sel) {
    const tr = sel.closest('tr');
    const nome = sel.value;
    const preco = window.precosProdutos[nome] || 0;
    const unid = window.unidadesProdutos ? (window.unidadesProdutos[nome] || '') : '';
    
    const inputVlr = tr.querySelector('.vlr-un-input');
    if (inputVlr) inputVlr.value = preco;

    const ths = tr.closest('table').querySelectorAll('thead th');
    for(let i = 0; i < ths.length - 1; i++) {
        const thText = ths[i].innerText.toLowerCase().trim();
        if (thText === 'unid' || thText === 'uni') {
            const selectUni = tr.children[i].querySelector('select');
            if (selectUni && unid) {
                let opt = Array.from(selectUni.options).find(o => o.value.trim().toUpperCase() === String(unid).trim().toUpperCase());
                if(opt) selectUni.value = opt.value;
                else { selectUni.add(new Option(unid, unid, true, true)); }
            }
        }
    }
    calcSub(sel);
};

window.calcSub = function(el) {
    const tr = el.closest('tr');
    const vlrInput = tr.querySelector('.vlr-un-input');
    const qtdInput = tr.querySelector('.qtd-input');
    const subInput = tr.querySelector('.subtotal-input');
    const acrescimoInput = tr.querySelector('.acrescimo-input');
    const descVlrInput = tr.querySelector('.desc-vlr-input') || tr.querySelector('.descontos-input');

    if(vlrInput && subInput) {
        const vlr = parseFloat(vlrInput.value || 0);
        const qtd = qtdInput ? parseFloat(qtdInput.value || 1) : 1; 
        let descVlr = descVlrInput ? parseFloat(descVlrInput.value || 0) : 0;
        const acrescimo = acrescimoInput ? parseFloat(acrescimoInput.value || 0) : 0;

        let sub = (vlr * qtd) + acrescimo - descVlr;
        subInput.value = sub.toFixed(2);
    }
    
    if (el.closest('form') && el.closest('form').id === 'form_pedidos') calcTotalPedido();
    else if (el.closest('form') && el.closest('form').id === 'form_nfe') calcTotalNfe();
    else if (el.closest('form') && el.closest('form').id === 'form_nfse') calcTotalNfse();
};

window.calcTotalPedido = function() {
    let totalProd = 0;
    document.querySelectorAll('#tb_itens_ped .subtotal-input').forEach(inp => totalProd += parseFloat(inp.value || 0));
    const fieldProds = document.getElementById('ped_total_produtos');
    if(fieldProds) fieldProds.value = totalProd.toFixed(2);
    
    const frete = parseFloat(document.getElementById('ped_frete')?.value || 0);
    const acrescimos = parseFloat(document.getElementById('ped_acrescimos')?.value || 0);
    const descPerc = parseFloat(document.getElementById('ped_desconto_percent')?.value || 0);
    let descVlr = parseFloat(document.getElementById('ped_desconto_valor')?.value || 0);

    let baseTotal = totalProd + frete + acrescimos;
    if (descPerc > 0) descVlr += baseTotal * (descPerc / 100);

    let totalFinal = baseTotal - descVlr;
    const fieldTotal = document.getElementById('ped_vlr_total');
    if(fieldTotal) fieldTotal.value = totalFinal.toFixed(2);
};

window.calcTotalNfe = function() {
    let totalProd = 0;
    document.querySelectorAll('#tb_itens_nfe .subtotal-input').forEach(inp => totalProd += parseFloat(inp.value || 0));
    const fieldProds = document.getElementById('nfe_total_produtos');
    if(fieldProds) fieldProds.value = totalProd.toFixed(2);
    
    const seguro = parseFloat(document.getElementById('nfe_valor_seguro')?.value || 0);
    const despesas = parseFloat(document.getElementById('nfe_despesas')?.value || 0);
    const descPerc = parseFloat(document.getElementById('nfe_desconto_percent')?.value || 0);
    let descVlr = parseFloat(document.getElementById('nfe_desconto_valor')?.value || 0);

    let baseTotal = totalProd + seguro + despesas;
    if (descPerc > 0) descVlr += baseTotal * (descPerc / 100);

    if(document.getElementById('nfe_base_icms')) document.getElementById('nfe_base_icms').value = baseTotal.toFixed(2);
    if(document.getElementById('nfe_valor_icms')) document.getElementById('nfe_valor_icms').value = (baseTotal * 0.18).toFixed(2);

    let totalFinal = baseTotal - descVlr;
    const fieldTotal = document.getElementById('nfe_total_nota');
    if(fieldTotal) fieldTotal.value = totalFinal.toFixed(2);
};

window.calcTotalNfse = function() {
    let totalServ = 0;
    let totalIss = 0;
    document.querySelectorAll('#tb_itens_nfse .subtotal-input').forEach(inp => totalServ += parseFloat(inp.value || 0));
    document.querySelectorAll('#tb_itens_nfse .iss-vlr-input').forEach(inp => totalIss += parseFloat(inp.value || 0));
    
    const fieldServs = document.getElementById('nfse_total_servicos');
    if(fieldServs) fieldServs.value = totalServ.toFixed(2);
    if(document.getElementById('nfse_vlr_iss')) document.getElementById('nfse_vlr_iss').value = totalIss.toFixed(2);

    const acrescimos = parseFloat(document.getElementById('nfse_acrescimos')?.value || 0);
    const descPerc = parseFloat(document.getElementById('nfse_desconto_percent')?.value || 0);
    let descVlr = parseFloat(document.getElementById('nfse_desconto_valor')?.value || 0);

    let baseTotal = totalServ + acrescimos;
    if (descPerc > 0) descVlr += baseTotal * (descPerc / 100);

    let totalFinal = baseTotal - descVlr;
    const fieldTotal = document.getElementById('nfse_total');
    if(fieldTotal) fieldTotal.value = totalFinal.toFixed(2);
};

window.recalcSeq = function(tb) {
    if(!tb) return;
    setTimeout(() => {
        const rows = tb.querySelectorAll('tr');
        rows.forEach((tr, idx) => {
            const ths = tr.closest('table').querySelectorAll('thead th');
            const inputs = tr.querySelectorAll('input, select');
            ths.forEach((th, thIdx) => {
                if(th.innerText.toLowerCase() === 'seq') {
                    if(inputs[thIdx]) inputs[thIdx].value = idx + 1;
                }
            });
        });
    }, 50);
};

function extrairNomeTransportadora(idOuNome) {
    if(!isNaN(idOuNome) && idOuNome !== '') {
        const tr = window.transportadorasData.find(t => t.id == idOuNome);
        if(tr) return tr.razao_social || tr.nome || tr.nome_razao || '';
    }
    return idOuNome; 
}

// ==========================================
// OPÇÕES GLOBAIS PARA INSERÇÃO DINÂMICA
// ==========================================
let optionsProdutos = '<option value="">-- Selecione --</option>';

async function loadDropdownsComercial() {
    try {
        const res = await fetch('/api/comercial/opcoes_formularios?_=' + new Date().getTime()); 
        const data = await res.json();
        
        window.precosProdutos = {};
        window.unidadesProdutos = {};
        if(data.produtos) {
            optionsProdutos = '<option value="">-- Selecione --</option>';
            data.produtos.forEach(p => {
                optionsProdutos += `<option value="${p.nome}">${p.nome}</option>`;
                window.precosProdutos[p.nome] = p.preco || p.vlr_varejo || 0;
                window.unidadesProdutos[p.nome] = (p.unidade_medida || '').toString().toUpperCase().trim();
            });
        }
        
        if(data.cfops) {
            window.optionsCfops = '<option value="">-- CFOP --</option>';
            data.cfops.forEach(c => window.optionsCfops += `<option value="${c.codigo_cfop}">${c.codigo_cfop} - ${c.descricao}</option>`);
        }
        
        if(data.unidades) {
            let optionsStr = '<option value="">-- Unidade --</option>';
            const uniqueUnits = [...new Set(data.unidades.map(u => (u.nome || u.unidade_medida || '').trim().toUpperCase()))].filter(Boolean);
            uniqueUnits.forEach(u => optionsStr += `<option value="${u}">${u}</option>`);
            window.optionsUnidades = optionsStr;
        }

        if(data.formas_pgto) {
            window.optionsFormasPgto = '<option value="">-- Forma Pgto --</option>';
            data.formas_pgto.forEach(c => window.optionsFormasPgto += `<option value="${c.nome}">${c.nome}</option>`);
        }
        if(data.condicoes) {
            window.optionsCondicoes = '<option value="">-- Condição --</option>';
            data.condicoes.forEach(c => window.optionsCondicoes += `<option value="${c.nome}">${c.nome}</option>`);
        }
        if(data.bancos) {
            window.optionsBancos = '<option value="">-- Banco --</option>';
            data.bancos.forEach(c => window.optionsBancos += `<option value="${c.nome}">${c.nome}</option>`);
        }
        
        if(data.transportadoras) window.transportadorasData = data.transportadoras;
        
        const preencher = (seletor, items, label) => {
            let html = `<option value="">-- ${label} --</option>`;
            if(items) items.forEach(i => {
                let txt = i.nome || i.descricao || i.id;
                html += `<option value="${txt}">${txt}</option>`;
            });
            document.querySelectorAll(seletor).forEach(el => el.innerHTML = html);
        };

        preencher('.ddl-tabelas', data.tabelas, 'Tabela Preço');
        preencher('.ddl-clientes', data.clientes, 'Todos');
        preencher('.ddl-categorias', data.categorias, 'Categorias');
        preencher('.ddl-grupos', data.grupos, 'Grupos');
        preencher('.ddl-marcas', data.marcas, 'Marcas');
        preencher('.ddl-canais', data.canais || [{nome:'Canal Web'},{nome:'Loja Física'}], 'Canais');
        
        if (data.portarias) {
            document.querySelectorAll('.ddl-portarias').forEach(el => {
                let defaultLabel = el.options.length > 0 ? el.options[0].text : '-- Selecionar Portaria --';
                let html = `<option value="">${defaultLabel}</option>`;
                data.portarias.forEach(p => {
                    let textToInsert = p.mensagem || p.descricao || p.nome || '';
                    let displayLabel = p.id ? `${p.id} - ${p.nome || p.descricao}` : (p.nome || p.descricao);
                    html += `<option value="${textToInsert}">${displayLabel}</option>`;
                });
                el.innerHTML = html;
            });
        }

    } catch(e) { console.warn("Falha opções cruzadas.", e); }
}

const ALIAS_MAP = {
    'codigo_cupom': 'referencia', 'ref_externa': 'referencia',
    'inicio_vigencia': 'data_inicial', 'fim_vigencia': 'data_final',
    'desconto_percentual': 'valor_percentual', 'desconto_global': 'valor_percentual',
    'mes_ano': 'periodo', 'valor_alcancado': 'valor_atingido', 'valor_alvo': 'valor_meta',
    'forma_recompensa': 'tipo_pagamento', 'valor_recompensa': 'valor_comissao',
    'pct_desconto': 'desconto_percent', 'vlr_desconto': 'desconto_valor',
    'total_nota': 'vlr_total', 'total_servicos': 'vlr_total', 'data_pedido': 'data'
};

function cleanFieldKey(key, prefix) {
    let raw = key;
    if (prefix && raw.startsWith(prefix)) raw = raw.substring(prefix.length);
    if (ALIAS_MAP[raw]) return ALIAS_MAP[raw];
    return raw;
}

function serializeForm(formId, prefix) {
    const inputs = document.querySelectorAll(`#${formId} input:not(.ignore-serialize), #${formId} select:not(.ignore-serialize), #${formId} textarea:not(.ignore-serialize)`);
    const payload = {};
    inputs.forEach(input => {
        let originalKey = input.id || input.name;
        if(originalKey) {
            let baseKey = originalKey.replace(prefix, '');
            let mappedKey = cleanFieldKey(originalKey, prefix);
            
            let finalVal = '';
            if(input.type === 'checkbox' || input.type === 'radio') {
                if(input.checked) finalVal = input.value;
            } else if(input.multiple) {
                let selected = Array.from(input.selectedOptions).map(opt => opt.value);
                finalVal = selected.join(', ');
            } else {
                finalVal = input.value;
            }
            
            if (finalVal !== undefined && finalVal !== '') {
                payload[baseKey] = finalVal;
                if (mappedKey && mappedKey !== baseKey) {
                    payload[mappedKey] = finalVal;
                }
            }
        }
    });
    return payload;
}

window.dispatchEditComercial = function(formId, prefix, encodedData) {
    try {
        const data = JSON.parse(decodeURIComponent(encodedData));
        const form = document.getElementById(formId);
        if (!form) return;
        
        limparFormulario(formId);
        
        Object.keys(data).forEach(key => {
            if (data[key] === null || data[key] === undefined || data[key] === '') return;

            let fieldId = prefix + key;
            if(!document.getElementById(fieldId) && ALIAS_MAP[key]) fieldId = prefix + ALIAS_MAP[key];
            if(!document.getElementById(fieldId)) {
                for(let ali in ALIAS_MAP) if(ALIAS_MAP[ali] === key) { fieldId = prefix + ali; break; }
            }
            
            const field = document.getElementById(fieldId);
            if (field) {
                if(field.type === 'checkbox') {
                    field.checked = (field.value === String(data[key]));
                } else if(field.multiple) {
                    let vals = String(data[key]).split(',').map(v => v.trim());
                    Array.from(field.options).forEach(opt => opt.selected = vals.includes(opt.value));
                } else if (field.tagName === 'SELECT') {
                    let opt = Array.from(field.options).find(o => String(o.value).trim().toUpperCase() === String(data[key]).trim().toUpperCase() || String(o.text).trim().toUpperCase() === String(data[key]).trim().toUpperCase());
                    if (opt) field.value = opt.value;
                    else field.value = data[key];
                } else {
                    field.value = data[key];
                }
            }
        });

        const idField = document.getElementById(prefix + 'id');
        if (idField) idField.value = data.id || '';
        
        const parseJ = (v) => { try { return JSON.parse(v || '[]'); } catch(e){ return []; } };
        
        if(data.itens_json) {
            if(formId === 'form_pedidos') renderizarTabelaInterna(formId, 'tb_itens_ped', parseJ(data.itens_json));
            if(formId === 'form_nfe') renderizarTabelaInterna(formId, 'tb_itens_nfe', parseJ(data.itens_json));
            if(formId === 'form_nfse') renderizarTabelaInterna(formId, 'tb_itens_nfse', parseJ(data.itens_json));
        }
        if(data.financeiro_json) {
            if(formId === 'form_pedidos') renderizarTabelaInterna(formId, 'tb_financeiro_ped', parseJ(data.financeiro_json));
            if(formId === 'form_nfe') renderizarTabelaInterna(formId, 'tb_financeiro_nfe', parseJ(data.financeiro_json));
            if(formId === 'form_nfse') renderizarTabelaInterna(formId, 'tb_financeiro_nfse', parseJ(data.financeiro_json));
        }
        if(data.cobranca_json) {
            if(formId === 'form_pedidos') renderizarTabelaInterna(formId, 'tb_cobranca_ped', parseJ(data.cobranca_json));
            if(formId === 'form_nfe') renderizarTabelaInterna(formId, 'tb_cobranca_nfe', parseJ(data.cobranca_json));
            if(formId === 'form_nfse') renderizarTabelaInterna(formId, 'tb_cobranca_nfse', parseJ(data.cobranca_json));
        }
        if(data.produtos_especificos_json) renderizarTabelaInterna(formId, 'tb_produtos_promo', parseJ(data.produtos_especificos_json));

        if(formId === 'form_pedidos') calcTotalPedido();
        if(formId === 'form_nfe') calcTotalNfe();
        if(formId === 'form_nfse') calcTotalNfse();

        openModal(formId);
    } catch (e) { console.error(e); }
};

function renderizarTabelaInterna(formId, tableId, dataArray) {
    const tb = document.querySelector(`#${formId} #${tableId}`);
    if(!tb) return;
    tb.innerHTML = '';
    
    const ths = tb.closest('table').querySelectorAll('thead th');

    dataArray.forEach((row, rowIndex) => {
        const tr = document.createElement('tr');
        
        for(let i = 0; i < ths.length - 1; i++) { 
            const td = document.createElement('td');
            const thText = ths[i].innerText.toLowerCase().trim();
            
            let v = '';
            if(thText === 'produto' || thText === 'serviço' || thText === 'servico') v = row.produto || row.servico || '';
            else if(thText === 'ref') v = row.ref || '';
            else if(thText.includes('forma pgto')) v = row.forma || '';
            else if(thText.includes('banco')) v = row.banco || '';
            else if(thText.includes('condição') || thText.includes('condicoes')) v = row.condicao || '';
            else if(thText.includes('cfop')) v = row.cfop || '';
            else if(thText === 'seq') v = row.seq || (rowIndex + 1);
            else if(thText.includes('vencimento')) v = row.vencimento || '';
            else if(thText.includes('valor promoção')) v = row.vlr_promocao || '';
            else if(thText.includes('valor un') || thText.includes('valor uni') || thText === 'valor') v = row.vlr_un || row.valor || '';
            else if(thText.includes('qtd')) v = row.qtd || '';
            else if(thText.includes('acréscimos') || thText.includes('acrescimos')) v = row.acrescimos || '';
            else if(thText.includes('descontos') || thText.includes('v. desc')) v = row.desc_valor || '';
            else if(thText.includes('v. iss')) v = row.iss_valor || '';
            else if(thText.includes('subtotal')) v = row.subtotal || '';
            else if(thText.includes('parcela')) v = row.parcelas || '';
            else if(thText === 'unid' || thText === 'uni') v = row.unid || row.uni || '';
            else if(thText === 'cod') v = row.cod || '';

            if(thText === 'produto' || thText === 'serviço' || thText === 'servico') {
                td.innerHTML = `<input type="text" class="ignore-serialize" value="${safeEdit(v)}" readonly>`;
            } else if(thText === 'ref') {
                td.innerHTML = `<input type="text" class="ignore-serialize" value="${safeEdit(v)}">`;
            } else if(thText === 'cfop') {
                td.innerHTML = `<select class="erp-select ignore-serialize">${window.optionsCfops}</select>`;
            } else if(thText === 'unid' || thText === 'uni') {
                td.innerHTML = `<select class="erp-select ignore-serialize">${window.optionsUnidades}</select>`;
            } else if(thText.includes('forma pgto')) {
                td.innerHTML = `<select class="erp-select ignore-serialize">${window.optionsFormasPgto}</select>`;
            } else if(thText.includes('condição') || thText.includes('condicoes')) {
                td.innerHTML = `<select class="erp-select ignore-serialize">${window.optionsCondicoes}</select>`;
            } else if(thText.includes('banco')) {
                td.innerHTML = `<select class="erp-select ignore-serialize">${window.optionsBancos}</select>`;
            } else if(thText === 'seq') {
                td.innerHTML = `<input type="number" class="ignore-serialize" style="width:50px; text-align:center;" value="${safeEdit(v)}" readonly>`;
            } else if(thText === 'cod') {
                td.innerHTML = `<input type="text" class="ignore-serialize" style="width:60px; text-align:center;" value="${safeEdit(v)}" readonly>`;
            } else if(thText.includes('vencimento')) {
                td.innerHTML = `<input type="date" class="ignore-serialize" value="${safeEdit(v)}">`;
            } else if(thText.includes('valor un') || thText.includes('valor uni') || thText === 'valor') {
                td.innerHTML = `<input type="number" step="0.01" class="ignore-serialize vlr-un-input" value="${safeEdit(v)}" onchange="calcSub(this)">`;
            } else if(thText.includes('qtd')) {
                td.innerHTML = `<input type="number" step="0.01" class="ignore-serialize qtd-input" value="${safeEdit(v)}" onchange="calcSub(this)">`;
            } else if(thText.includes('acréscimos') || thText.includes('acrescimos')) {
                td.innerHTML = `<input type="number" step="0.01" class="ignore-serialize acrescimo-input" value="${safeEdit(v)}" onchange="calcSub(this)">`;
            } else if(thText.includes('descontos') || thText.includes('v. desc')) {
                td.innerHTML = `<input type="number" step="0.01" class="ignore-serialize desc-vlr-input descontos-input" value="${safeEdit(v)}" onchange="calcSub(this)">`;
            } else if(thText.includes('v. iss')) {
                td.innerHTML = `<input type="number" step="0.01" class="ignore-serialize iss-vlr-input" value="${safeEdit(v)}" readonly>`;
            } else if(thText.includes('subtotal')) {
                td.innerHTML = `<input type="number" step="0.01" class="ignore-serialize subtotal-input" value="${safeEdit(v)}" readonly>`;
            } else {
                td.innerHTML = `<input type="text" class="ignore-serialize" value="${safeEdit(v)}">`;
            }
            
            const selectEl = td.querySelector('select');
            if (selectEl && v) {
                let opt = Array.from(selectEl.options).find(o => String(o.value).trim().toUpperCase() === String(v).trim().toUpperCase());
                if (opt) {
                    selectEl.value = opt.value;
                    opt.setAttribute('selected', 'selected');
                } else {
                    const newOpt = new Option(v, v, true, true);
                    newOpt.setAttribute('selected', 'selected');
                    selectEl.add(newOpt);
                }
            }
            
            tr.appendChild(td);
        }
        
        const actionTd = document.createElement('td');
        actionTd.className = 'text-center';
        actionTd.innerHTML = `<button type="button" class="btn-neon-danger bg-transparent p-5" onclick="const t = this.closest('tbody'); this.closest('tr').remove(); recalcSeq(t); calcSub(t.firstElementChild);">X</button>`;
        tr.appendChild(actionTd);
        
        tb.appendChild(tr);
    });
}

window.calcStaging = function(type) {
    const vlr = parseFloat(document.getElementById(`stg_${type}_vlr`)?.value || 0);
    const qtd = type === 'nfse' ? 1 : parseFloat(document.getElementById(`stg_${type}_qtd`)?.value || 1);
    const acresc = parseFloat(document.getElementById(`stg_${type}_acresc`)?.value || 0);
    const descPerc = parseFloat(document.getElementById(`stg_${type}_desc_perc`)?.value || 0);
    let descVlr = parseFloat(document.getElementById(`stg_${type}_desc_vlr`)?.value || 0);
    
    let sub = (vlr * qtd) + acresc;
    
    if(descPerc > 0) {
        descVlr = sub * (descPerc / 100);
        const elDesc = document.getElementById(`stg_${type}_desc_vlr`);
        if(elDesc) elDesc.value = descVlr.toFixed(2);
    }
    
    sub -= descVlr;

    const issPerc = parseFloat(document.getElementById(`stg_${type}_iss_perc`)?.value || 0);
    if(issPerc > 0) {
        const issVlr = sub * (issPerc / 100);
        const elIss = document.getElementById(`stg_${type}_iss_vlr`);
        if(elIss) elIss.value = issVlr.toFixed(2);
    }

    const elSub = document.getElementById(`stg_${type}_sub`);
    if(elSub) elSub.value = sub.toFixed(2);
};

window.addFromStaging = function(type) {
    const id = document.getElementById(`stg_${type}_id`)?.value || Math.floor(Math.random() * 10000); 
    const nome = document.getElementById(`stg_${type}_nome`)?.value || '';
    if(!nome) { alert('Pesquise o produto/serviço primeiro.'); return; }

    const ref = '';
    const qtd = type === 'nfse' ? '1' : (document.getElementById(`stg_${type}_qtd`)?.value || '1');
    const vlr = document.getElementById(`stg_${type}_vlr`)?.value || '0';
    const acresc = document.getElementById(`stg_${type}_acresc`)?.value || '0';
    const desc = document.getElementById(`stg_${type}_desc_vlr`)?.value || '0';
    const iss = document.getElementById(`stg_${type}_iss_vlr`)?.value || '0';
    const sub = document.getElementById(`stg_${type}_sub`)?.value || '0';
    
    const cod = id; 
    let cfop = ''; 
    let unid = ''; 

    if (type === 'nfse') {
        unid = document.getElementById(`stg_nfse_unid`)?.value || '';
    } else if (window.stagingProdUnid && window.stagingProdUnid[type]) {
        unid = window.stagingProdUnid[type];
        window.stagingProdUnid[type] = ''; 
    }

    if (window.stagingIntCfop && window.stagingIntCfop[type]) {
        cfop = window.stagingIntCfop[type];
        window.stagingIntCfop[type] = ''; 
    }

    const tb = document.getElementById(`tb_itens_${type}`);
    const nextSeq = tb.children.length + 1;
    const ths = tb.closest('table').querySelectorAll('thead th');
    
    let cols = '';
    for(let i = 0; i < ths.length - 1; i++) {
        const thText = ths[i].innerText.toLowerCase().trim();
        let val = '';
        
        if(thText === 'produto' || thText === 'serviço' || thText === 'servico') val = nome;
        else if(thText === 'ref') val = ref;
        else if(thText === 'seq') val = nextSeq;
        else if(thText === 'cod') val = cod;
        else if(thText === 'cfop') val = cfop;
        else if(thText === 'unid' || thText === 'uni') val = unid;
        else if(thText.includes('qtd')) val = qtd;
        else if(thText.includes('valor un') || thText.includes('valor uni') || thText === 'valor') val = vlr;
        else if(thText.includes('acréscimos') || thText.includes('acrescimos')) val = acresc;
        else if(thText.includes('descontos') || thText.includes('v. desc')) val = desc;
        else if(thText.includes('v. iss')) val = iss;
        else if(thText.includes('subtotal')) val = sub;

        if(thText === 'produto' || thText === 'serviço' || thText === 'servico') {
             cols += `<td><input type="text" class="ignore-serialize" value="${val}" readonly></td>`;
        }
        else if(thText === 'ref') cols += `<td><input type="text" class="ignore-serialize" value="${val}"></td>`;
        else if(thText === 'seq') cols += `<td><input type="number" class="ignore-serialize" style="width:50px; text-align:center;" value="${val}" readonly></td>`;
        else if(thText === 'cod') cols += `<td><input type="text" class="ignore-serialize" style="width:60px; text-align:center;" value="${val}" readonly></td>`;
        else if(thText === 'cfop') cols += `<td><select class="erp-select ignore-serialize">${window.optionsCfops}</select></td>`;
        else if(thText === 'unid' || thText === 'uni') cols += `<td><select class="erp-select ignore-serialize">${window.optionsUnidades}</select></td>`;
        else if(thText.includes('valor un') || thText.includes('valor uni') || thText === 'valor') cols += `<td><input type="number" step="0.01" class="ignore-serialize vlr-un-input" value="${val}" onchange="calcSub(this)"></td>`;
        else if(thText.includes('qtd')) cols += `<td><input type="number" step="0.01" class="ignore-serialize qtd-input" value="${val}" onchange="calcSub(this)"></td>`;
        else if(thText.includes('acréscimos') || thText.includes('acrescimos')) cols += `<td><input type="number" step="0.01" class="ignore-serialize acrescimo-input" value="${val}" onchange="calcSub(this)"></td>`;
        else if(thText.includes('descontos') || thText.includes('v. desc')) cols += `<td><input type="number" step="0.01" class="ignore-serialize desc-vlr-input descontos-input" value="${val}" onchange="calcSub(this)"></td>`;
        else if(thText.includes('v. iss')) cols += `<td><input type="number" step="0.01" class="ignore-serialize iss-vlr-input" value="${val}" readonly></td>`;
        else if(thText.includes('subtotal')) cols += `<td><input type="number" step="0.01" class="ignore-serialize subtotal-input" value="${val}" readonly></td>`;
        else cols += `<td><input type="text" class="ignore-serialize" value="${val}"></td>`;
    }

    const tr = document.createElement('tr');
    tr.innerHTML = `${cols}<td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="const t = this.closest('tbody'); this.closest('tr').remove(); recalcSeq(t); calcSub(t.firstElementChild);">X</button></td>`;
    tb.appendChild(tr);

    for(let i = 0; i < ths.length - 1; i++) {
        const thText = ths[i].innerText.toLowerCase().trim();
        const select = tr.children[i].querySelector('select');
        if (select) {
             if(thText === 'cfop' && cfop) {
                 let opt = Array.from(select.options).find(o => o.value.trim().toUpperCase() === String(cfop).trim().toUpperCase());
                 if(opt) select.value = opt.value;
             }
             else if((thText === 'unid' || thText === 'uni') && unid) {
                 let opt = Array.from(select.options).find(o => o.value.trim().toUpperCase() === String(unid).trim().toUpperCase());
                 if(opt) select.value = opt.value;
                 else {
                     const newOpt = new Option(unid, unid, true, true);
                     select.add(newOpt);
                 }
             }
        }
    }

    if(type === 'nfe') calcTotalNfe();
    if(type === 'nfse') calcTotalNfse();
    if(type === 'ped') calcTotalPedido();

    ['id', 'nome', 'int_id', 'int_nome', 'qtd', 'vlr', 'acresc', 'desc_perc', 'desc_vlr', 'iss_perc', 'iss_vlr', 'sub', 'unid'].forEach(f => {
        const el = document.getElementById(`stg_${type}_${f}`);
        if(el) el.value = (f==='qtd' ? '1' : '');
    });
};

window.addRow = function(btn, defaultProdName = '') {
    const tb = btn.closest('.section-box').querySelector('tbody');
    const colsCount = btn.closest('.section-box').querySelectorAll('thead th').length - 1;
    let cols = '';
    
    const ths = btn.closest('.section-box').querySelectorAll('thead th');
    const nextSeq = tb.children.length + 1;
    
    for(let i=0; i<colsCount; i++) {
        const thText = ths[i].innerText.toLowerCase().trim();
        
        if(thText === 'produto' || thText === 'serviço' || thText === 'servico') cols += `<td><select class="erp-select ignore-serialize" onchange="onProdutoChange(this)">${optionsProdutos}</select></td>`;
        else if(thText === 'ref') cols += `<td><input type=\"text\" class=\"ignore-serialize\"></td>`;
        else if(thText === 'seq') cols += `<td><input type=\"number\" class=\"ignore-serialize\" style=\"width:50px; text-align:center;\" value=\"${nextSeq}\" readonly></td>`;
        else if(thText === 'cod') cols += `<td><input type=\"text\" class=\"ignore-serialize\" style=\"width:60px; text-align:center;\" readonly></td>`;
        else if(thText === 'cfop') cols += `<td><select class=\"erp-select ignore-serialize\">${window.optionsCfops}</select></td>`;
        else if(thText === 'unid' || thText === 'uni') cols += `<td><select class=\"erp-select ignore-serialize\">${window.optionsUnidades}</select></td>`;
        else if(thText.includes('forma pgto')) cols += `<td><select class=\"erp-select ignore-serialize\">${window.optionsFormasPgto}</select></td>`;
        else if(thText.includes('condição') || thText.includes('condicoes')) cols += `<td><select class=\"erp-select ignore-serialize\">${window.optionsCondicoes}</select></td>`;
        else if(thText.includes('banco')) cols += `<td><select class=\"erp-select ignore-serialize\">${window.optionsBancos}</select></td>`;
        else if(thText.includes('vencimento')) cols += `<td><input type=\"date\" class=\"ignore-serialize\"></td>`;
        else if(thText.includes('valor un') || thText === 'valor') cols += `<td><input type=\"number\" step=\"0.01\" class=\"ignore-serialize vlr-un-input\" onchange=\"calcSub(this)\"></td>`;
        else if(thText.includes('qtd')) cols += `<td><input type=\"number\" step=\"0.01\" class=\"ignore-serialize qtd-input\" value=\"1\" onchange=\"calcSub(this)\"></td>`;
        else if(thText.includes('acréscimos') || thText.includes('acrescimos')) cols += `<td><input type=\"number\" step=\"0.01\" class=\"ignore-serialize acrescimo-input\" onchange=\"calcSub(this)\"></td>`;
        else if(thText.includes('descontos') || thText.includes('v. desc')) cols += `<td><input type=\"number\" step=\"0.01\" class=\"ignore-serialize desc-vlr-input descontos-input\" onchange=\"calcSub(this)\"></td>`;
        else if(thText.includes('v. iss')) cols += `<td><input type=\"number\" step=\"0.01\" class=\"ignore-serialize iss-vlr-input\" readonly></td>`;
        else if(thText.includes('subtotal')) cols += `<td><input type=\"number\" step=\"0.01\" class=\"ignore-serialize subtotal-input\" readonly></td>`;
        else cols += `<td><input type=\"text\" class=\"ignore-serialize\"></td>`;
    }
    
    const tr = document.createElement('tr');
    tr.innerHTML = `${cols}<td class=\"text-center\"><button type=\"button\" class=\"btn-neon-danger bg-transparent p-5\" onclick=\"const t = this.closest('tbody'); this.closest('tr').remove(); recalcSeq(t); calcSub(t.firstElementChild);\">X</button></td>`;
    tb.appendChild(tr);

    if(defaultProdName) {
        const prodSelect = tr.querySelector('select');
        if(prodSelect) {
            prodSelect.value = defaultProdName;
            if(prodSelect.onchange) prodSelect.onchange(); 
        } else {
            const input = tr.querySelector('input');
            if(input) input.value = defaultProdName;
        }
    }
}

function extrairTabelaInterna(formId, tableId) {
    const tb = document.querySelector(`#${formId} #${tableId}`);
    if(!tb) return "[]";
    const data = [];
    const ths = tb.closest('table').querySelectorAll('thead th');
    
    tb.querySelectorAll('tr').forEach(tr => {
        let obj = {};
        let temValor = false;
        
        for(let i = 0; i < ths.length - 1; i++) {
            const thText = ths[i].innerText.toLowerCase().trim();
            const td = tr.children[i];
            const input = td ? td.querySelector('input, select') : null;
            const val = input ? input.value : '';
            
            let k = 'extra';
            if(thText === 'produto') k = 'produto';
            else if(thText === 'serviço' || thText === 'servico') k = 'servico';
            else if(thText === 'ref') k = 'ref';
            else if(thText.includes('forma pgto')) k = 'forma';
            else if(thText.includes('banco')) k = 'banco';
            else if(thText.includes('condição') || thText.includes('condicoes')) k = 'condicao';
            else if(thText.includes('cfop')) k = 'cfop';
            else if(thText === 'seq') k = 'seq';
            else if(thText.includes('vencimento')) k = 'vencimento';
            else if(thText.includes('valor promoção')) k = 'vlr_promocao';
            else if(thText.includes('valor un') || thText.includes('valor uni') || thText === 'valor') k = 'vlr_un';
            else if(thText.includes('qtd')) k = 'qtd';
            else if(thText.includes('acréscimos') || thText.includes('acrescimos')) k = 'acrescimos';
            else if(thText.includes('descontos') || thText.includes('v. desc')) k = 'desc_valor';
            else if(thText.includes('v. iss')) k = 'iss_valor';
            else if(thText.includes('subtotal')) k = 'subtotal';
            else if(thText.includes('parcela')) k = 'parcelas';
            else if(thText === 'unid' || thText === 'uni') k = 'unid';
            else if(thText === 'cod') k = 'cod';
            
            obj[k] = val;
            if(val && val !== '0' && k !== 'seq') temValor = true;
        }
        if(temValor) data.push(obj);
    });
    return JSON.stringify(data);
}

async function postRecordComercial(tabela, payload, formId, loaderFunc) {
    try {
        const res = await fetch(`/api/comercial/${tabela}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (!res.ok) { alert('Falha ao salvar.'); return false; }
        if(formId) { limparFormulario(formId); closeModal(formId); }
        if(loaderFunc) loaderFunc();
        return true; 
    } catch(e) { alert('Falha de rede.'); return false; }
}

async function deleteRecordComercial(endpoint, id, callbackLoad) {
    if(confirm("Excluir registro permanentemente?")) {
        try {
            const res = await fetch(`/api/comercial/${endpoint}/${id}`, { method: 'DELETE' });
            if(res.ok) callbackLoad();
        } catch(e) {}
    }
}

// ==========================================
// CÓDIGOS ESPECÍFICOS: PEDIDOS
// ==========================================
async function loadPedidos() {
    try {
        const res = await fetch('/api/comercial/pedidos'); const data = await res.json();
        const tb = document.getElementById('tb_pedidos'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="font-bold">${safeVal(i.numero)}</td><td>${safeVal(i.data_pedido || i.data)}</td><td>${safeVal(i.data_faturamento)}</td><td class="text-info">${safeVal(i.cliente_nome)}</td><td>${safeVal(i.vendedor_nome)}</td><td class="text-success font-bold">R$ ${i.vlr_total || i.total || 0}</td><td>R$ ${safeVal(i.comissao)}</td><td class="text-warning">${safeVal(i.status)}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditComercial('form_pedidos', 'ped_', '${encodeURIComponent(JSON.stringify(i))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordComercial('pedidos', ${i.id}, loadPedidos)">🗑️</button></td></tr>`; });
    } catch(e) {}
}

window.salvarPedido = async function(e) {
    e.preventDefault(); const p = serializeForm("form_pedidos", "ped_");
    p.itens_json = extrairTabelaInterna("form_pedidos", "tb_itens_ped");
    p.financeiro_json = extrairTabelaInterna("form_pedidos", "tb_financeiro_ped");
    p.cobranca_json = extrairTabelaInterna("form_pedidos", "tb_cobranca_ped");
    
    if(p.status === 'Fechado' && !p.data_finalizacao) {
        p.data_finalizacao = new Date().toISOString().split('T')[0];
    }
    p.vlr_total = p.vlr_total || p.total || p.total_produtos || 0;
    await postRecordComercial('pedidos', p, 'form_pedidos', loadPedidos);
};

// ==========================================
// CÓDIGOS ESPECÍFICOS: NF-E
// ==========================================
async function loadNfe() {
    try {
        const res = await fetch('/api/comercial/nfe'); const data = await res.json();
        const tb = document.getElementById('tb_nfe'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="font-bold">${safeVal(i.numero || i.id)}</td><td>${safeVal(i.data_emissao)}</td><td class="text-info">${safeVal(i.cliente_nome)}</td><td class="text-success font-bold">R$ ${i.vlr_total || i.total_nota || 0}</td><td>${safeVal(i.finalidade)}</td><td class="text-warning">${safeVal(i.status)}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditComercial('form_nfe', 'nfe_', '${encodeURIComponent(JSON.stringify(i))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordComercial('nfe', ${i.id}, loadNfe)">🗑️</button></td></tr>`; });
    } catch(e) {}
}

window.salvarNfe = async function(e) {
    e.preventDefault(); 
    const p = serializeForm("form_nfe", "nfe_");
    p.itens_json = extrairTabelaInterna("form_nfe", "tb_itens_nfe");
    p.financeiro_json = extrairTabelaInterna("form_nfe", "tb_financeiro_nfe");
    p.cobranca_json = extrairTabelaInterna("form_nfe", "tb_cobranca_nfe");

    p.tipo_nota = 'NF-e';
    p.transportador = extrairNomeTransportadora(p.transp_id);
    p.vlr_total = parseFloat(p.total_nota || 0);
    p.status = p.status || 'Digitação'; // Status NFe Automático

    await postRecordComercial('nfe', p, 'form_nfe', loadNfe);
};

// ==========================================
// CÓDIGOS ESPECÍFICOS: NFC-E
// ==========================================
async function loadNfce() {
    try {
        const res = await fetch('/api/comercial/nfce'); const data = await res.json();
        const tb = document.getElementById('tb_nfce'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="font-bold">${safeVal(i.numero)}</td><td>${safeVal(i.data_emissao || i.data)}</td><td class="text-success font-bold">R$ ${i.vlr_total || i.valor || 0}</td><td class="text-info">${safeVal(i.cliente_nome)}</td><td class="text-warning">${safeVal(i.status)}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordComercial('nfce', ${i.id}, loadNfce)">🗑️</button></td></tr>`; });
    } catch(e) {}
}

// ==========================================
// CÓDIGOS ESPECÍFICOS: NFS-E
// ==========================================
async function loadNfse() {
    try {
        const res = await fetch('/api/comercial/nfse'); const data = await res.json();
        const tb = document.getElementById('tb_nfse'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="font-bold">${safeVal(i.numero || i.id)}</td><td>${safeVal(i.data_emissao)}</td><td>${safeVal(i.data_inicio)}</td><td>${safeVal(i.data_termino)}</td><td class="text-info">${safeVal(i.cliente_nome)}</td><td>${safeVal(i.vendedor_nome)}</td><td class="text-warning">${safeVal(i.status)}</td><td class="text-success font-bold">R$ ${i.vlr_total || i.total_servicos || 0}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditComercial('form_nfse', 'nfse_', '${encodeURIComponent(JSON.stringify(i))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordComercial('nfse', ${i.id}, loadNfse)">🗑️</button></td></tr>`; });
    } catch(e) {}
}

window.salvarNfse = async function(e) {
    e.preventDefault(); const p = serializeForm("form_nfse", "nfse_");
    p.itens_json = extrairTabelaInterna("form_nfse", "tb_itens_nfse");
    p.financeiro_json = extrairTabelaInterna("form_nfse", "tb_financeiro_nfse");
    p.cobranca_json = extrairTabelaInterna("form_nfse", "tb_cobranca_nfse"); 
    p.tipo_nota = 'NFS-e';
    p.vlr_total = parseFloat(p.total || 0);
    p.reter_impostos = document.getElementById('nfse_reter_impostos').checked ? 'S' : 'N';
    await postRecordComercial('nfse', p, 'form_nfse', loadNfse);
};

// ==========================================
// CÓDIGOS ESPECÍFICOS: CANAIS / MARKETPLACES E INTEGRAÇÕES 
// ==========================================
async function loadCanaisVenda() {
    try {
        const res = await fetch('/api/comercial/canais_venda'); const data = await res.json();
        const tb = document.getElementById('tb_canais'); if(!tb) return; 
        tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td>${i.id}</td><td class="font-bold text-info">${safeVal(i.mkt_integracao)}</td><td>${safeVal(i.mkt_tabela_preco)}</td><td>${safeVal(i.data_criacao)}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditComercial('form_canais', 'cnl_', '${encodeURIComponent(JSON.stringify(i))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordComercial('canais_venda', ${i.id}, loadCanaisVenda)">🗑️</button></td></tr>`; });
    } catch(e) { }
}

async function loadPromocoes() {
    try {
        const res = await fetch('/api/comercial/promocoes'); const data = await res.json();
        const tb = document.getElementById('tb_promocoes'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td>${i.id}</td><td class="font-bold text-info">${safeVal(i.descricao_campanha || i.descricao || i.nome)}</td><td>${safeVal(i.data_inicial || i.inicio_vigencia)}</td><td>${safeVal(i.data_final || i.fim_vigencia)}</td><td>${safeVal(i.tabela_preco || i.tabela_alvo)}</td><td>${safeVal(i.inativo)==='S'?'Não':'Sim'}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditComercial('form_promocoes', 'prm_', '${encodeURIComponent(JSON.stringify(i))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordComercial('promocoes', ${i.id}, loadPromocoes)">🗑️</button></td></tr>`; });
    } catch(e) {}
}

// ==========================================
// CÓDIGOS ESPECÍFICOS: INTEGRAÇÕES / APIS
// ==========================================
async function loadIntegracoes() {
    try {
        // Busca na tabela separada de CONFIGURAÇÕES
        const res = await fetch('/api/comercial/integracoes_config'); 
        const data = await res.json();
        const tb = document.getElementById('tb_integracoes'); if(!tb) return;
        tb.innerHTML = '';
        data.forEach(i => { 
            let tipo = i.entidade || 'Configuração API';
            tb.innerHTML += `<tr>
                <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
                <td class="font-bold text-warning">${safeVal(i.plataforma)}</td>
                <td>${tipo}</td>
                <td class="text-center">
                    <button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditComercial('${tipo === 'Conexao API' ? 'form_conexao' : 'form_integracoes'}', '${tipo === 'Conexao API' ? 'cnx_' : 'int_'}', '${encodeURIComponent(JSON.stringify(i))}')">✏️</button> 
                    <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordComercial('integracoes_config', ${i.id}, loadIntegracoes)">🗑️</button>
                </td>
            </tr>`; 
        });
    } catch(e) {}
}

window.salvarIntegracao = async function(e) {
    e.preventDefault();
    const p = serializeForm('form_integracoes', 'int_');
    const opts = [];
    document.querySelectorAll('#form_integracoes .int-opt:checked').forEach(cb => opts.push(cb.value));
    p.opcoes_json = JSON.stringify(opts);
    p.entidade = "Configuracao Hub API";
    p.data_criacao = new Date().toISOString();
    
    // Salva na tabela separada de CONFIGURAÇÕES
    await postRecordComercial('integracoes_config', p, 'form_integracoes', loadIntegracoes);
};

window.salvarConexao = async function(e) {
    e.preventDefault();
    const p = serializeForm("form_conexao", "cnx_");
    p.entidade = "Conexao API";
    p.data_criacao = new Date().toISOString();
    
    // Salva na tabela separada de CONFIGURAÇÕES
    await postRecordComercial('integracoes_config', p, 'form_conexao', loadIntegracoes);
}

window.gerarTokenAutomatico = function() {
    let now = new Date();
    now.setHours(now.getHours() + 24);
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    document.getElementById('cnx_token_validade').value = now.toISOString().slice(0,16);
    document.getElementById('cnx_token_acesso').value = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.IntegrationToken" + Math.random().toString(36).substr(2);
    document.getElementById('cnx_token_reconexao').value = "ReconToken_" + Math.random().toString(36).substr(2);
}

// ==========================================
// CÓDIGOS ESPECÍFICOS: METAS
// ==========================================
async function loadMetas() {
    try {
        const res = await fetch('/api/comercial/metas'); const data = await res.json();
        const tb = document.getElementById('tb_metas'); tb.innerHTML = '';
        data.forEach(i => { tb.innerHTML += `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td>${i.id}</td><td class="font-bold text-warning">${safeVal(i.status)}</td><td>${safeVal(i.nivel)}</td><td>${safeVal(i.data_inicio)}</td><td>${safeVal(i.data_fim)}</td><td class="text-success font-bold">R$ ${safeVal(i.valor_meta)}</td><td>R$ ${safeVal(i.valor_atingido)}</td><td>${safeVal(i.tipo_meta)}</td><td>${safeVal(i.comissao)}</td><td>${safeVal(i.funcionarios)}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEditComercial('form_metas', 'met_', '${encodeURIComponent(JSON.stringify(i))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordComercial('metas', ${i.id}, loadMetas)">🗑️</button></td></tr>`; });
    } catch(e) {}
}

// ==========================================
// CÓDIGOS ESPECÍFICOS: RELATÓRIOS
// ==========================================
async function loadRelatorios() {
    try {
        const res = await fetch('/api/comercial/relatorios'); 
        const data = await res.json();
        const tb = document.getElementById('tb_relatorios'); tb.innerHTML = '';
        
        if (data.length === 0) {
            tb.innerHTML = `<tr><td colspan="6" class="text-center">Utilize os filtros acima para gerar relatórios.</td></tr>`;
            return;
        }

        data.forEach(i => { 
            tb.innerHTML += `
            <tr>
                <td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td>
                <td class="font-bold text-success">${safeVal(i.modelo)}</td>
                <td>${safeVal(i.data_geracao)}</td>
                <td>${safeVal(i.periodo_base)}</td>
                <td>${safeVal(i.usuario)}</td>
                <td class="text-center">
                    <button class="btn-neon btn-neon-primary p-5 text-xs" onclick="alert('Download do Arquivo iniciado (PDF/ZIP)!')">Baixar PDF</button>
                    <button class="btn-neon btn-neon-danger p-5 text-xs" onclick="deleteRecordComercial('relatorios', ${i.id}, loadRelatorios)">🗑️</button>
                </td>
            </tr>`; 
        });
    } catch(e) { console.error(e) }
}

window.gerarRelatorioSistema = async function() {
    const modelo = document.getElementById('rel_modelo').value;
    const periodo = document.getElementById('rel_periodo').value;
    const payload = {
        modelo: modelo,
        data_geracao: new Date().toISOString().split('T')[0],
        periodo_base: periodo,
        usuario: "Admin", 
        status: "Gerado"
    };
    alert(`⏳ Gerando e Salvando [${modelo}]...\nAguarde.`);
    await postRecordComercial('relatorios', payload, null, loadRelatorios);
};

// ==========================================
// CÓDIGOS ESPECÍFICOS: OUTROS
// ==========================================
window.salvarComercial = async function(e, endpoint) {
    e.preventDefault();
    const mapConfig = {
        'canais_venda': { prefix: 'cnl_', form: 'form_canais', loader: loadCanaisVenda },
        'promocoes':    { prefix: 'prm_', form: 'form_promocoes', loader: loadPromocoes },
        'metas':        { prefix: 'met_', form: 'form_metas', loader: loadMetas }
    };
    const conf = mapConfig[endpoint];
    if (!conf) return;
    
    const p = serializeForm(conf.form, conf.prefix);
    
    if(endpoint === 'promocoes') {
        p.produtos_especificos_json = extrairTabelaInterna(conf.form, 'tb_produtos_promo');
        p.apenas_estoque = document.getElementById('prm_apenas_estoque').checked ? 'S' : 'N';
    }
    
    if(endpoint === 'canais_venda' && (!p.data_criacao || p.data_criacao === '')) {
        p.data_criacao = new Date().toISOString().split('T')[0];
    }
    
    await postRecordComercial(endpoint, p, conf.form, conf.loader);
};

// MODAL DE PESQUISA E INSERÇÃO EM GRIDS
let alvoId = null; let alvoNome = null; let baseEndpoint = ''; let gridTargetBtn = null;

window.abrirPesquisaGrid = function(entidade, btn) {
    gridTargetBtn = btn;
    abrirPesquisa(entidade, 'grid_add', 'grid_add');
};

window.abrirPesquisa = function(entidade, idInput, nomeInput) {
    if(idInput !== 'grid_add') gridTargetBtn = null;
    alvoId = idInput; alvoNome = nomeInput; baseEndpoint = entidade;
    document.getElementById('mpesq_titulo').innerText = `Pesquisar ${entidade.toUpperCase()}`;
    document.getElementById('mpesq_input').value = '';
    document.getElementById('mpesq_tb').innerHTML = '';
    document.getElementById('modal_pesquisa_generica').classList.add('active');
    executarPesquisa();
};

window.fecharPesquisa = function() { 
    document.getElementById('modal_pesquisa_generica').classList.remove('active'); 
};

window.executarPesquisa = async function() {
    const q = document.getElementById('mpesq_input').value;
    try {
        const res = await fetch(`/api/comercial/pesquisar/${baseEndpoint}?q=${q}&_=${new Date().getTime()}`);
        const data = await res.json();
        const tb = document.getElementById('mpesq_tb'); tb.innerHTML = '';
        data.forEach(i => { 
            let nomeDisplay = i.nome || i.razao_social || i.descricao || 'Sem Nome';
            let extraStr = '';
            
            let precoVal = i.preco || i.vlr_varejo || i.valor_base || i.vlr_base || i.vlr_unitario || 0;
            window.precosProdutos[nomeDisplay] = precoVal;

            if (baseEndpoint === 'integracoes') extraStr = i.cfop || '';
            else if (baseEndpoint === 'produtos' || baseEndpoint === 'servicos') extraStr = i.unidade_medida || '';

            tb.innerHTML += `<tr><td>${i.id}</td><td>${nomeDisplay}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-success" style="padding:2px 8px; font-size:0.7rem;" onclick="selecionarPesquisa(${i.id}, '${nomeDisplay.replace(/'/g, "\\'")}', '${extraStr}')">OK</button></td></tr>`; 
        });
    } catch(e) { document.getElementById('mpesq_tb').innerHTML = '<tr><td colspan="3" class="text-center">Falha na pesquisa</td></tr>'; }
};

window.selecionarPesquisa = function(id, nome, extra = '') {
    if (alvoId === 'grid_add') {
        if (gridTargetBtn) addRow(gridTargetBtn, nome);
        fecharPesquisa();
        return;
    }

    if(alvoId && document.getElementById(alvoId)) document.getElementById(alvoId).value = id;
    if(alvoNome && document.getElementById(alvoNome)) {
        const inputNome = document.getElementById(alvoNome);
        
        if(inputNome.value && (inputNome.id === 'met_funcionarios' || inputNome.id === 'flt_met_func' || inputNome.id === 'prm_emitentes')) {
            inputNome.value += ', ' + nome; 
        } else {
            inputNome.value = nome;
            
            if (baseEndpoint === 'integracoes') {
                let match = alvoNome.match(/stg_(nfe|nfse|ped)_int_nome/);
                if (match) {
                    window.stagingIntCfop = window.stagingIntCfop || {};
                    window.stagingIntCfop[match[1]] = extra; 
                }
            }

            if(baseEndpoint === 'produtos' || baseEndpoint === 'servicos') {
                let match = alvoId ? alvoId.match(/stg_(nfe|nfse|ped)_id/) : null;
                if (match) {
                    let type = match[1];
                    let vlrInput = document.getElementById(`stg_${type}_vlr`);
                    if(vlrInput && window.precosProdutos && window.precosProdutos[nome] !== undefined) {
                        vlrInput.value = window.precosProdutos[nome];
                    }

                    if (type === 'nfse') {
                        let unidInput = document.getElementById('stg_nfse_unid');
                        if(unidInput) unidInput.value = extra || '';
                    } else {
                        window.stagingProdUnid = window.stagingProdUnid || {};
                        window.stagingProdUnid[type] = extra || (window.unidadesProdutos ? window.unidadesProdutos[nome] : '');
                    }
                    calcStaging(type);
                }
            }
        }
        
        if(alvoId === 'nfe_transp_id') {
            const tr = window.transportadorasData.find(t => t.id == id);
            if(tr) {
                document.getElementById('nfe_placa').value = tr.placa_veiculo || '';
                document.getElementById('nfe_veiculo_uf').value = tr.uf_veiculo || tr.uf || '';
                document.getElementById('nfe_rntrc').value = tr.rntrc || '';
            }
        }
    }
    fecharPesquisa();
};

function exportToExcel(tableName) {
    const activeView = document.querySelector('.erp-view.active');
    if(!activeView) return;
    const table = activeView.querySelector('.erp-table');
    if(!table) { alert('Nenhuma listagem encontrada para exportar nesta tela.'); return; }

    let csvContent = "";
    const rows = table.querySelectorAll("tr");

    rows.forEach(row => {
        let rowData = [];
        const cols = row.querySelectorAll("th, td");
        cols.forEach((col, index) => {
            if (index === cols.length - 1 && (col.innerText.includes('Ações') || col.querySelector('button'))) return;
            if (index === 0 && col.querySelector('input[type="checkbox"]')) return;
            let text = col.innerText.replace(/"/g, '""'); 
            rowData.push(`"${text}"`);
        });
        if(rowData.length > 0) csvContent += rowData.join(";") + "\r\n";
    });

    const blob = new Blob(["\uFEFF" + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    let safeName = tableName.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    link.setAttribute("download", `exportacao_${safeName}_${new Date().getTime()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function printActiveTable(title) {
    const activeView = document.querySelector('.erp-view.active');
    if(!activeView) return;
    const table = activeView.querySelector('.erp-table');
    if(!table) { alert('Nenhuma listagem encontrada para imprimir.'); return; }

    const cloneTable = table.cloneNode(true);
    cloneTable.querySelectorAll('tr').forEach(tr => {
        if(tr.lastElementChild) tr.lastElementChild.remove();
        if(tr.firstElementChild && tr.firstElementChild.querySelector('input[type="checkbox"]')) tr.firstElementChild.remove();
    });

    const win = window.open('', '_blank');
    win.document.write(`
        <html><head><title>Impressão - ${title}</title>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; color: #333; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }
            th, td { border: 1px solid #ccc; padding: 8px 10px; text-align: left; }
            th { background-color: #f5f5f5; font-weight: bold; }
            h2 { color: #222; border-bottom: 2px solid #ccc; padding-bottom: 10px; margin-bottom: 5px; }
            .date { font-size: 12px; color: #777; margin-bottom: 20px; }
        </style>
        </head><body>
        <h2>Lista: ${title}</h2>
        <div class="date">Gerado pelo sistema em: ${new Date().toLocaleString()}</div>
        ${cloneTable.outerHTML}
        </body></html>
    `);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); win.close(); }, 800);
}

async function documentActionPrompt(actionName) {
    let entity = actionName.split(' ').pop(); 
    let mensagem = `Ação Selecionada: ${actionName}\n\nDigite o ID ou Número correspondente para prosseguir:`;
    
    if (actionName.includes('Inutilizar')) {
        mensagem = `Ação: INUTILIZAR NUMERAÇÃO (${entity})\n\nDigite o intervalo da numeração e justificativa (Ex: 100-150 Erro sistêmico):`;
    }

    let input = prompt(mensagem);
    if(!input) return;

    alert(`⏳ Processando [${actionName}] para o registro fornecido...\nAguarde.`);
    setTimeout(() => {
        alert(`✅ Sucesso!\n\n${actionName} processado(a) corretamente para os dados inseridos.`);
    }, 1500);
}

function executarAcaoExterna(nomeAcao) {
    const activeView = document.querySelector('.erp-view.active');
    const viewTitle = activeView ? (activeView.querySelector('h3') ? activeView.querySelector('h3').innerText.replace(/[^\w\sÀ-ÿ]/gi, '').trim() : 'Exportacao') : 'Relatorio';

    if (nomeAcao === 'Exportar Excel') {
        exportToExcel(viewTitle);
    } 
    else if (nomeAcao === 'Exportar PDF' || nomeAcao === 'Imprimir Lista') {
        printActiveTable(viewTitle);
    } 
    else if (nomeAcao.includes('Relatório') && nomeAcao !== 'Gerar Relatório de Vendas') {
        let btnRelatorio = document.querySelector(`button[onclick*="view_relatorios"]`);
        if(btnRelatorio) switchComercialView('view_relatorios', btnRelatorio);
        alert(`Filtros de relatórios pré-selecionados para: ${nomeAcao.replace('Relatórios ', '')}. Selecione o período e clique em Gerar.`);
    } 
    else if (nomeAcao === 'Gerar Relatório de Vendas') {
        loadRelatorios(true); 
    }
    else if (nomeAcao.includes('Enviar E-mail') || nomeAcao.includes('Transmitir') || nomeAcao.includes('Inutilizar') || nomeAcao.includes('XML vs Cupom') ||
             nomeAcao.includes('Cancelar') || nomeAcao.includes('Reenviar') || nomeAcao.includes('Importar') || nomeAcao.includes('Consultar') || nomeAcao.includes('Status')) {
        documentActionPrompt(nomeAcao);
    } 
    else {
        alert(`Ação [${nomeAcao}] chamada, porém não possui vínculo de função específica ainda.`);
    }
}