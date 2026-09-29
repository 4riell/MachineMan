// ==========================================
// CONTROLO DINÂMICO DO MENU LATERAL (ERP) E MODAIS
// ==========================================
async function switchErpView(viewId, btnElement) {
    document.querySelectorAll('.erp-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(viewId).classList.add('active');
    btnElement.classList.add('active');

    localStorage.setItem('lastErpView', viewId);

    const loadMap = {
        'view_produtos': async () => { await loadDropdownsProdutos(); await loadTabelasPreco(); await loadProdutos(); },
        'view_clientes': async () => { await loadDropdownsClientes(); await loadTabelasPreco(); await loadClientes(); },
        'view_fornecedores': loadFornecedores,
        'view_transportadores': loadTransportadores,
        'view_convenios': loadConvenios,
        'view_funcionarios': loadFuncionarios,
        'view_grupos_produtos': async () => { await loadDropdownsProdutos(); await loadGruposProdutos(); },
        'view_marcas': loadMarcas,
        'view_cores': loadCores,
        'view_tamanhos': loadTamanhos,
        'view_carteiras': async () => { await loadDropdownsVendedores(); await loadCarteiras(); },
        'view_indicacoes': loadIndicacoes
    };
    
    if (loadMap[viewId]) await loadMap[viewId]();
}

// SISTEMA DE MODAIS
function openModal(formId) {
    const modal = document.getElementById(formId + (formId.includes('modal') ? '' : '_modal'));
    if(modal) modal.classList.add('active');
}

function closeModal(formId) {
    const modal = document.getElementById(formId + (formId.includes('modal') ? '' : '_modal'));
    if(modal) modal.classList.remove('active');
}

function novoCadastro(formId) {
    limparFormulario(formId);
    if(formId === 'form_funcionarios') {
        funcLists = { remuneracoes: [], frequencias: [], periodicos: [] };
        renderFuncLists();
    }
    if(formId === 'form_produtos') {
        prodPrecos = [];
        renderProdPrecos();
    }
    openModal(formId);
}

function limparFormulario(formId) {
    const form = document.getElementById(formId);
    if(form) {
        form.reset();
        const idField = form.querySelector('input[type="hidden"]');
        if(idField) idField.value = '';
    }
}

// RESTAURAÇÃO DE ESTADO (F5)
document.addEventListener("DOMContentLoaded", () => { 
    carregarEstadosIBGEDinamico(); 
    
    let lastView = localStorage.getItem('lastErpView') || 'view_clientes';
    let btn = document.querySelector(`button[onclick*="${lastView}"]`);
    
    if(btn) {
        switchErpView(lastView, btn);
    } else {
        let firstBtn = document.querySelector('.menu-item');
        if(firstBtn) switchErpView('view_clientes', firstBtn);
    }
});

// ==========================================
// CÁLCULO DINÂMICO - SALDO PREVISTO PRODUTOS
// ==========================================
window.calcularSaldoPrevisto = function() {
    const fisico = parseFloat(document.getElementById('prod_saldo_fisico')?.value) || 0;
    const reserva = parseFloat(document.getElementById('prod_reserva')?.value) || 0;
    const previsto = fisico - reserva;
    
    const elPrevisto = document.getElementById('prod_saldo_previsto');
    if(elPrevisto) elPrevisto.value = previsto.toFixed(2);
};

// ==========================================
// CARREGAMENTO DAS DROPDOWNS E PESQUISAS DA API
// ==========================================
async function loadDropdownsClientes() {
    try {
        const res = await fetch('/api/cadastros/opcoes_cliente');
        const data = await res.json();
        
        let convHtml = '<option value="">-- Selecione Convênio --</option>';
        if(data.convenios) data.convenios.forEach(c => convHtml += `<option value="${c.id}">${c.nome}</option>`);
        document.querySelectorAll('.ddl-convenios').forEach(el => el.innerHTML = convHtml);
        
        let cartHtml = '<option value="">-- Selecione Carteira --</option>';
        if(data.carteiras) data.carteiras.forEach(c => cartHtml += `<option value="${c.id}">${c.carteira}</option>`);
        document.querySelectorAll('.ddl-carteiras').forEach(el => el.innerHTML = cartHtml);
    } catch(e) { console.error("Erro dropdowns clientes", e); }
}

async function loadDropdownsProdutos() {
    try {
        const res = await fetch('/api/cadastros/opcoes_produto');
        const data = await res.json();
        
        const resGrupos = await fetch('/api/cadastros/grupos_produtos');
        const gruposData = await resGrupos.json();
        
        let grupHtml = '<option value="">-- Selecione Grupo --</option>';
        if(gruposData) gruposData.forEach(g => grupHtml += `<option value="${g.id}">${g.nome_grupo || g.nome || 'Sem Nome'}</option>`);
        document.querySelectorAll('.ddl-grupos-produto').forEach(el => el.innerHTML = grupHtml);
        
        let marcHtml = '<option value="">-- Selecione Marca --</option>';
        if(data.marcas) data.marcas.forEach(m => marcHtml += `<option value="${m.id}">${m.nome}</option>`);
        document.querySelectorAll('.ddl-marcas-produto').forEach(el => el.innerHTML = marcHtml);
    } catch(e) { console.error("Erro dropdowns produtos", e); }
}

async function loadTabelasPreco() {
    try {
        const res = await fetch('/api/cadastros/tabelas_preco');
        const data = await res.json();
        let html = '<option value="">-- Selecione a Tabela --</option>';
        data.forEach(t => html += `<option value="${t.nome}">${t.nome}</option>`);
        
        const selectProd = document.getElementById('add_preco_tabela');
        if(selectProd) selectProd.innerHTML = html;
        
        const selectCli = document.getElementById('cli_tabela_preco');
        if(selectCli) selectCli.innerHTML = html;
        
    } catch(e) { console.error("Erro tabelas preco", e); }
}

async function loadDropdownsVendedores() {
    try {
        const res = await fetch('/api/cadastros/funcionarios');
        const data = await res.json();
        let vendHtml = '<option value="">-- Selecione Vendedor --</option>';
        data.forEach(f => vendHtml += `<option value="${f.nome}">${f.nome}</option>`);
        document.querySelectorAll('.ddl-vendedores').forEach(el => el.innerHTML = vendHtml);
    } catch(e) { console.error("Erro dropdowns vendedores", e); }
}

// ==========================================
// MODAIS DE PESQUISA (NCM E CLIENTE)
// ==========================================
function openNcmSearch() { openModal('modal_busca_ncm'); }

async function executarBuscaNCM() {
    const q = document.getElementById('ncm_busca_input').value;
    const tb = document.getElementById('tb_busca_ncm');
    tb.innerHTML = '<tr><td colspan="3" class="text-center">Buscando...</td></tr>';
    try {
        const res = await fetch(`/api/cadastros/pesquisa/ncms?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="3" class="text-center">Nenhum NCM encontrado.</td></tr>';
        data.forEach(n => {
            tb.innerHTML += `<tr><td>${n.codigo}</td><td>${n.descricao}</td><td><button class="btn-neon btn-neon-green text-xs p-5" onclick="selecionarNCM('${n.codigo}')">Usar</button></td></tr>`;
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="3" class="text-danger text-center">Erro.</td></tr>'; }
}

function selecionarNCM(codigo) {
    const el = document.getElementById('prod_ncm');
    if(el) el.value = codigo;
    closeModal('modal_busca_ncm');
}

function openClienteSearch(targetId) { 
    window.targetClienteId = targetId; 
    openModal('modal_busca_cliente'); 
}

async function executarBuscaCliente() {
    const q = document.getElementById('cliente_busca_input').value;
    const tb = document.getElementById('tb_busca_cliente');
    tb.innerHTML = '<tr><td colspan="4" class="text-center">Buscando...</td></tr>';
    try {
        const res = await fetch(`/api/cadastros/pesquisa/clientes?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum cliente encontrado.</td></tr>';
        data.forEach(c => {
            tb.innerHTML += `<tr><td>${c.id}</td><td>${c.nome}</td><td>${c.cpf_cnpj || '-'}</td><td><button class="btn-neon btn-neon-green text-xs p-5" onclick="selecionarCliente('${c.nome}')">Selecionar</button></td></tr>`;
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="4" class="text-danger text-center">Erro.</td></tr>'; }
}

function selecionarCliente(nome) {
    const el = document.getElementById(window.targetClienteId);
    if(el) el.value = nome;
    closeModal('modal_busca_cliente');
}

// ==========================================
// CORE: FILTRO RÍGIDO DE SERIALIZAÇÃO 
// ==========================================
function serializeForm(formId, prefix) {
    const inputs = document.querySelectorAll(`#${formId} input, #${formId} select, #${formId} textarea`);
    const payload = {};
    inputs.forEach(input => {
        if(input.id && input.id.startsWith(prefix) && !input.disabled) {
            let key = input.id.substring(prefix.length);
            if(key) {
                if(input.type === 'checkbox') {
                    payload[key] = input.checked ? 'S' : 'N';
                } else if(input.multiple) {
                    payload[key] = Array.from(input.selectedOptions).map(opt => opt.value).join(', ');
                } else {
                    payload[key] = input.value;
                }
            }
        }
    });
    return payload;
}

function editFormGeneric(formId, prefix, itemObj) {
    limparFormulario(formId);
    for (const [key, value] of Object.entries(itemObj)) {
        const el = document.getElementById(prefix + key);
        if (el) {
            if (el.type === 'checkbox') {
                el.checked = (value === 'S' || value === true || value === 1);
            } else if (el.multiple) {
                const vals = (value || '').toString().split(',').map(v => v.trim());
                Array.from(el.options).forEach(opt => { opt.selected = vals.includes(opt.value); });
            } else {
                el.value = (value !== null && value !== undefined) ? value : '';
            }
        }
    }
}

window.dispatchEdit = async function(formId, prefix, encoded) {
    const itemObj = JSON.parse(decodeURIComponent(encoded));
    
    const ufField = itemObj.uf;
    const cityField = itemObj.cidade || itemObj.municipio;
    
    if (ufField) {
        const selectId = prefix + 'municipio';
        if (document.getElementById(selectId)) {
            await carregarMunicipiosIBGEDinamico(ufField, selectId);
        }
    }

    editFormGeneric(formId, prefix, itemObj);
    
    if(ufField && cityField) {
         const selectId = prefix + 'municipio';
         const sel = document.getElementById(selectId);
         if(sel) sel.value = cityField;
    }
    
    if (formId === 'form_produtos') {
        prodPrecos = itemObj.tabelasPreco || [];
        renderProdPrecos();
    }
    
    if (formId === 'form_funcionarios') {
        funcLists.remuneracoes = itemObj.remuneracoes_json ? JSON.parse(itemObj.remuneracoes_json) : [];
        funcLists.frequencias = itemObj.frequencias_json ? JSON.parse(itemObj.frequencias_json) : [];
        funcLists.periodicos = itemObj.periodicos_json ? JSON.parse(itemObj.periodicos_json) : [];
        renderFuncLists();
    }
    
    openModal(formId);
};

// ==========================================
// INTEGRAÇÃO COM A API DO BACKEND REAL
// ==========================================
const mapEndpoints = {
    'cores': 'grade_cor',
    'tamanhos': 'grade_tamanho',
    'transportadores': 'transportadoras'
};

async function postRecord(endpoint, payload, formId) {
    const realEndpoint = mapEndpoints[endpoint] || endpoint;
    try {
        const res = await fetch(`/api/cadastros/${realEndpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if(data.sucesso) {
            if(formId) { limparFormulario(formId); closeModal(formId); }
            return { sucesso: true, id: data.id };
        } else {
            alert("Erro ao salvar: " + (data.erro || 'Desconhecido'));
            return { sucesso: false };
        }
    } catch (e) {
        console.error(e);
        alert("Erro de comunicação com o servidor.");
    }
}

async function deleteRecord(endpoint, id, callbackLoad) {
    if(!confirm("Tem certeza que deseja excluir este registro?")) return;
    const realEndpoint = mapEndpoints[endpoint] || endpoint;
    try {
        const res = await fetch(`/api/cadastros/${realEndpoint}/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if(data.sucesso) {
            callbackLoad();
        } else {
            alert("Erro ao excluir: " + (data.erro || 'Desconhecido'));
        }
    } catch (e) {
        console.error(e);
        alert("Erro de comunicação com o servidor.");
    }
}

async function salvarGenerico(e, endpoint, formId, callbackLoad) {
    e.preventDefault();
    const prefix = formId.replace('form_', '').substring(0, 4) + '_';
    let finalPrefix = prefix;
    if(formId === 'form_produtos') finalPrefix = 'prod_';
    if(formId === 'form_clientes') finalPrefix = 'cli_';
    if(formId === 'form_fornecedores') finalPrefix = 'for_';
    if(formId === 'form_transportadores') finalPrefix = 'trans_';
    if(formId === 'form_convenios') finalPrefix = 'conv_';
    if(formId === 'form_funcionarios') finalPrefix = 'func_';
    if(formId === 'form_grupos_produtos') finalPrefix = 'gprod_';
    if(formId === 'form_marcas') finalPrefix = 'mar_';
    if(formId === 'form_cores') finalPrefix = 'cor_';
    if(formId === 'form_tamanhos') finalPrefix = 'tam_';
    if(formId === 'form_carteiras') finalPrefix = 'cart_';
    if(formId === 'form_indicacoes') finalPrefix = 'ind_';

    let payload = serializeForm(formId, finalPrefix);
    
    if(formId === 'form_funcionarios') {
        payload.listasExtras = funcLists; 
        
        // --- EXTRAÇÃO INTELIGENTE DE FUNÇÃO ---
        // Pega os tipos de remuneração adicionados (Vendedor, Técnico, etc)
        // Remove duplicatas usando o Set e une com vírgula para salvar na coluna `funcao` do banco
        if (funcLists.remuneracoes.length > 0) {
            const funcoes = [...new Set(funcLists.remuneracoes.map(r => r.tipo))];
            payload.funcao = funcoes.join(', ');
        } else {
            payload.funcao = ''; // Se não houver remuneração, fica vazio
        }
    }
    
    if(formId === 'form_produtos') {
        payload.tabelasPreco = prodPrecos;
    }

    const result = await postRecord(endpoint, payload, formId);
    if(result && result.sucesso) {
        callbackLoad();
    }
}

// ==========================================
// INTEGRAÇÃO IBGE DINÂMICA
// ==========================================
async function carregarEstadosIBGEDinamico() {
    try {
        const res = await fetch('https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome');
        const ibgeEstados = await res.json();
        let html = '<option value="">-- UF --</option>';
        ibgeEstados.forEach(uf => { html += `<option value="${uf.sigla}" data-id="${uf.id}">${uf.sigla}</option>`; });
        document.querySelectorAll('.ddl-estados').forEach(el => el.innerHTML = html);
    } catch(e) { console.error("Erro IBGE Estados", e); }
}

async function carregarMunicipiosIBGEDinamico(ufSigla, selectCidadeId) {
    const selectCidade = document.getElementById(selectCidadeId);
    if(!selectCidade) return;
    selectCidade.innerHTML = '<option value="">Aguarde...</option>';
    if (!ufSigla) { selectCidade.innerHTML = '<option value="">-- Selecione UF 1º --</option>'; return; }
    try {
        const res = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${ufSigla}/municipios`);
        const ibgeMunicipios = await res.json();
        let html = '<option value="">-- Município --</option>';
        ibgeMunicipios.forEach(mun => { html += `<option value="${mun.nome}">${mun.nome}</option>`; });
        selectCidade.innerHTML = html;
    } catch(e) { 
        selectCidade.innerHTML = '<option value="">Erro ao carregar</option>';
    }
}


// ==========================================
// FUNÇÕES DE LOAD DE TABELAS (BUSCA NA API)
// ==========================================

// PRODUTOS & TABELAS DE PREÇO
let prodPrecos = [];

async function loadProdutos() {
    const tb = document.getElementById('tb_produtos'); tb.innerHTML = '<tr><td colspan="8">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/produtos'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="8" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-info">${item.nome}</td><td>${item.sku || '-'}</td><td>${item.cod_gtin || '-'}</td><td>${item.referencia || item.cod_interno || '-'}</td><td>${item.saldo_fisico || item.qtd_estoque || '0'}</td><td>R$ ${parseFloat(item.vlr_varejo || 0).toFixed(2)}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_produtos', 'prod_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('produtos', ${item.id}, loadProdutos)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="8" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

window.addProdPreco = function() {
    const tab = document.getElementById('add_preco_tabela').value;
    const custo_medio = document.getElementById('add_preco_custo_medio').value;
    const mkp = document.getElementById('add_preco_markup').value;
    const vlr = document.getElementById('add_preco_valor').value;
    const min = document.getElementById('add_preco_minimo').value;
    
    if(!tab || !vlr) { alert('Preencha pelo menos a Tabela e o Valor.'); return; }

    prodPrecos.push({ tabela: tab, custo_medio: custo_medio || 0, markup: mkp || 0, valor: vlr, minimo: min || 0 });
    
    document.getElementById('add_preco_tabela').value = '';
    document.getElementById('add_preco_custo_medio').value = '';
    document.getElementById('add_preco_markup').value = '';
    document.getElementById('add_preco_valor').value = '';
    document.getElementById('add_preco_minimo').value = '';
    
    renderProdPrecos();
};

window.removeProdPreco = function(index) {
    prodPrecos.splice(index, 1);
    renderProdPrecos();
};

function renderProdPrecos() {
    const tb = document.getElementById('tb_prod_precos'); 
    if(!tb) return;
    tb.innerHTML = '';
    prodPrecos.forEach((p, i) => { 
        tb.innerHTML += `<tr>
            <td class="font-bold text-info">${p.tabela}</td>
            <td>R$ ${parseFloat(p.custo_medio || 0).toFixed(2)}</td>
            <td>${p.markup}%</td>
            <td>R$ ${parseFloat(p.valor).toFixed(2)}</td>
            <td>R$ ${parseFloat(p.minimo).toFixed(2)}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-danger p-5 text-xs" onclick="removeProdPreco(${i})">X</button></td>
        </tr>`; 
    });
}

// CLIENTES
async function loadClientes() {
    const tb = document.getElementById('tb_clientes'); tb.innerHTML = '<tr><td colspan="7">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/clientes'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="7" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-primary">${item.nome}</td><td>${item.cpf_cnpj || item.cpf || '-'}</td><td>${item.telefone || '-'}</td><td>${item.email || '-'}</td><td>${item.cidade || item.municipio || '-'}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_clientes', 'cli_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('clientes', ${item.id}, loadClientes)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="7" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

// FORNECEDORES
async function loadFornecedores() {
    const tb = document.getElementById('tb_fornecedores'); tb.innerHTML = '<tr><td colspan="7">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/fornecedores'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="7" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-success">${item.nome_razao || item.nome || '-'}</td><td>${item.cnpj_cpf || item.cnpj || item.cpf_cnpj || item.cpf || '-'}</td><td>${item.telefone || '-'}</td><td>${item.email || '-'}</td><td>${item.cidade || item.municipio || '-'}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_fornecedores', 'for_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('fornecedores', ${item.id}, loadFornecedores)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="7" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

// TRANSPORTADORES
async function loadTransportadores() {
    const tb = document.getElementById('tb_transportadores'); tb.innerHTML = '<tr><td colspan="7">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/transportadoras'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="7" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-info">${item.razao_social || item.nome || '-'}</td><td>${item.cnpj || item.cpf_cnpj || '-'}</td><td>${item.telefone || '-'}</td><td>${item.email || '-'}</td><td>${item.cidade || item.municipio || '-'}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_transportadores', 'trans_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('transportadoras', ${item.id}, loadTransportadores)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="7" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

// CONVÊNIOS
async function loadConvenios() {
    const tb = document.getElementById('tb_convenios'); tb.innerHTML = '<tr><td colspan="6">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/convenios'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="6" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-warning">${item.nome}</td><td>${item.cnpj || item.cpf_cnpj || '-'}</td><td>${item.telefone || '-'}</td><td>${item.email || '-'}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_convenios', 'conv_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('convenios', ${item.id}, loadConvenios)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="6" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

// FUNCIONÁRIOS (COM LÓGICA DE LISTAS INLINE SALVAS NO DB)
let funcLists = { remuneracoes: [], frequencias: [], periodicos: [] };

async function loadFuncionarios() {
    const tb = document.getElementById('tb_funcionarios'); tb.innerHTML = '<tr><td colspan="8">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/funcionarios'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="8" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            // Lógica dinâmica para forçar a exibição da função lendo das remunerações caso esteja vazio
            let funcoesStr = item.funcao || '';
            if (!funcoesStr && item.remuneracoes_json) {
                try {
                    const rems = JSON.parse(item.remuneracoes_json);
                    if (rems && rems.length > 0) {
                        funcoesStr = [...new Set(rems.map(r => r.tipo))].join(', ');
                    }
                } catch(e) {}
            }
            funcoesStr = funcoesStr || '-';

            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-info">${item.nome}</td><td>${item.cpf || '-'}</td><td>${item.telefone || '-'}</td><td>${item.email || '-'}</td><td class="text-warning">${funcoesStr}</td><td class="text-success">${(item.inativo === 'S' ? 'Inativo' : 'Ativo')}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_funcionarios', 'func_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('funcionarios', ${item.id}, loadFuncionarios)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="8" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

window.addFuncionarioSubList = function(type) {
    if(type === 'remuneracoes') {
        funcLists.remuneracoes.push({
            ativo: document.getElementById('add_rem_ativo').checked,
            tipo: document.getElementById('add_rem_tipo').value,
            comissao: document.getElementById('add_rem_comissao').value,
            perc: document.getElementById('add_rem_perc').value
        });
    } else if(type === 'frequencias') {
        funcLists.frequencias.push({
            mes: document.getElementById('add_freq_mes').value,
            dias: document.getElementById('add_freq_dias').value,
            uteis: document.getElementById('add_freq_uteis').value,
            faltas: document.getElementById('add_freq_faltas').value
        });
    } else if(type === 'periodicos') {
        funcLists.periodicos.push({
            periodo: document.getElementById('add_per_periodo').value,
            modulo: document.getElementById('add_per_modulo').value,
            info: document.getElementById('add_per_info').value,
            criacao: document.getElementById('add_per_criacao').value
        });
    }
    renderFuncLists();
};

window.removeFuncionarioSubList = function(type, index) {
    funcLists[type].splice(index, 1);
    renderFuncLists();
};

function renderFuncLists() {
    const tbRem = document.getElementById('tb_func_remuneracoes'); tbRem.innerHTML = '';
    funcLists.remuneracoes.forEach((r, i) => { tbRem.innerHTML += `<tr><td>${r.ativo?'Sim':'Não'}</td><td>${r.tipo}</td><td>${r.comissao}</td><td>${r.perc}%</td><td><button type="button" class="btn-neon btn-neon-danger p-5 text-xs" onclick="removeFuncionarioSubList('remuneracoes', ${i})">X</button></td></tr>`; });

    const tbFreq = document.getElementById('tb_func_frequencias'); tbFreq.innerHTML = '';
    funcLists.frequencias.forEach((f, i) => { tbFreq.innerHTML += `<tr><td>${f.mes}</td><td>${f.dias}</td><td>${f.uteis}</td><td>${f.faltas}</td><td><button type="button" class="btn-neon btn-neon-danger p-5 text-xs" onclick="removeFuncionarioSubList('frequencias', ${i})">X</button></td></tr>`; });

    const tbPer = document.getElementById('tb_func_periodicos'); tbPer.innerHTML = '';
    funcLists.periodicos.forEach((p, i) => { tbPer.innerHTML += `<tr><td>${p.periodo}</td><td>${p.modulo}</td><td>${p.info}</td><td>${p.criacao}</td><td><button type="button" class="btn-neon btn-neon-danger p-5 text-xs" onclick="removeFuncionarioSubList('periodicos', ${i})">X</button></td></tr>`; });
}

// GRUPOS PRODUTOS
async function loadGruposProdutos() {
    const tb = document.getElementById('tb_grupos_produtos'); tb.innerHTML = '<tr><td colspan="4">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/grupos_produtos'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-info">${item.nome_grupo || item.nome || '-'}</td><td>${item.n_produtos || '0'}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_grupos_produtos', 'gprod_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('grupos_produtos', ${item.id}, loadGruposProdutos)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="4" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

// MARCAS
async function loadMarcas() {
    const tb = document.getElementById('tb_marcas'); tb.innerHTML = '<tr><td colspan="3">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/marcas'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="3" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-warning">${item.nome || item.descricao || '-'}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_marcas', 'mar_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('marcas', ${item.id}, loadMarcas)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="3" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

// CORES
async function loadCores() {
    const tb = document.getElementById('tb_cores'); tb.innerHTML = '<tr><td colspan="4">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/grade_cor'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>${item.ordem || '-'}</td><td class="font-bold text-primary">${item.nome}</td><td class="text-success">${item.status || 'Ativo'}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_cores', 'cor_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('cores', ${item.id}, loadCores)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="4" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

// TAMANHOS
async function loadTamanhos() {
    const tb = document.getElementById('tb_tamanhos'); tb.innerHTML = '<tr><td colspan="4">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/grade_tamanho'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>${item.ordem || '-'}</td><td class="font-bold text-success">${item.nome}</td><td class="text-success">${item.status || 'Ativo'}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_tamanhos', 'tam_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('tamanhos', ${item.id}, loadTamanhos)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="4" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

// CARTEIRAS
async function loadCarteiras() {
    const tb = document.getElementById('tb_carteiras'); tb.innerHTML = '<tr><td colspan="4">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/carteiras'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-info">${item.carteira}</td><td>${item.vendedor || '-'}</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_carteiras', 'cart_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('carteiras', ${item.id}, loadCarteiras)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="4" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}

// INDICAÇÕES
async function loadIndicacoes() {
    const tb = document.getElementById('tb_indicacoes'); tb.innerHTML = '<tr><td colspan="4">A carregar...</td></tr>';
    try {
        const res = await fetch('/api/cadastros/indicacoes'); const data = await res.json();
        tb.innerHTML = '';
        if(data.length === 0) return tb.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum registo encontrado.</td></tr>';
        data.forEach(item => { 
            tb.innerHTML += `<tr><td>#${item.id}</td><td class="font-bold text-warning">${item.cliente || '-'}</td><td>${item.porcentagem || item.indicacao || '-'}%</td>
            <td class="text-center"><button type="button" class="btn-neon btn-neon-warning" style="padding:4px 8px; font-size:0.7rem" onclick="dispatchEdit('form_indicacoes', 'ind_', '${encodeURIComponent(JSON.stringify(item))}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:4px 8px; font-size:0.7rem" onclick="deleteRecord('indicacoes', ${item.id}, loadIndicacoes)">🗑️</button></td></tr>`; 
        });
    } catch(e) { tb.innerHTML = '<tr><td colspan="4" class="text-danger text-center">Erro ao carregar os dados.</td></tr>'; }
}