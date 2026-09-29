// ==========================================
// FUNÇÕES UTILITÁRIAS E ANTI-NULL
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

window.toggleAll = function(source) {
    const table = source.closest('table');
    const checkboxes = table.querySelectorAll('tbody .row-check');
    checkboxes.forEach(cb => cb.checked = source.checked);
};

// ==========================================
// SISTEMA DE MODAIS E CONTROLE
// ==========================================
function openModalSup(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.classList.add('active');
}

function closeModalSup(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.classList.remove('active');
}

function novoCadastroSup(formId) {
    limparFormularioSup(formId);
    
    if(formId === 'form_transferencias') {
        const numRef = document.getElementById('trf_numero');
        if(numRef) numRef.value = 'TRF-' + Date.now().toString().slice(-6);
        const origemRef = document.getElementById('trf_origem');
        if(origemRef) origemRef.value = 'Matriz (Automático)'; 
    } else if(formId === 'form_descartes') {
        const dt = document.getElementById('dsc_data');
        const user = document.getElementById('dsc_usuario');
        if(dt) dt.value = new Date().toISOString().split('T')[0];
        if(user) user.value = 'Admin / Sistema';
    } else if(formId === 'form_balancos') {
        const dtBal = document.getElementById('bal_data');
        if(dtBal) dtBal.value = new Date().toISOString().split('T')[0]; 
    }

    openModalSup(formId);
}

function limparFormularioSup(formId) {
    const form = document.getElementById(formId);
    if(form) {
        form.reset();
        const idField = form.querySelector('input[type="hidden"]');
        if(idField) idField.value = '';
        document.querySelectorAll(`#${formId} .dynamic-list`).forEach(tbody => {
            tbody.innerHTML = '';
        });
        setTimeout(calcTotaisCompra, 50);
    }
}

// ==========================================
// CARREGAMENTO GLOBAL E BUSCAS (DROPDOWNS)
// ==========================================
let optsProdutos = '<option value="">-- Selecione o Produto --</option>';
window.custosProdutos = {};
window.optsCfopsGlobal = '<option value="">-- CFOP --</option>'; 
window.optionsBancos = '<option value="">-- Banco --</option>';

async function loadDropdownsSuprimentos() {
    try {
        const res = await fetch('/api/suprimentos/opcoes_formularios');
        let data = await res.json();
        
        // --- SISTEMA DE FALLBACK ANTI-FALHA ---
        // Se a API principal falhar a trazer as listas, puxa da rota de cadastros base
        if (!data.fornecedores || data.fornecedores.length === 0) {
            try {
                const req = await fetch('/api/cadastros/fornecedores');
                const cads = await req.json();
                data.fornecedores = cads.map(i => ({ nome: i.nome_razao || i.nome_fantasia || i.nome || 'Sem Nome' }));
            } catch(e) {}
        }
        if (!data.transportadoras || data.transportadoras.length === 0) {
            try {
                const req = await fetch('/api/cadastros/transportadoras');
                const cads = await req.json();
                data.transportadoras = cads.map(i => ({ nome: i.razao_social || i.nome || 'Sem Nome' }));
            } catch(e) {}
        }
        if (!data.empresas || data.empresas.length === 0) {
            try {
                const req = await fetch('/api/cadastros/empresas');
                const cads = await req.json();
                data.empresas = cads.map(i => ({ nome: i.razao_social || i.nome || 'Sem Nome' }));
            } catch(e) {}
        }
        if (!data.grupos || data.grupos.length === 0) {
            try {
                const req = await fetch('/api/cadastros/grupos_produtos');
                const cads = await req.json();
                data.grupos = cads.map(i => ({ nome: i.nome_grupo || i.nome || 'Sem Nome' }));
            } catch(e) {}
        }
        // --------------------------------------
        
        let optsGrupos = '<option value="">-- Selecione o Grupo --</option>';
        if (data.grupos) data.grupos.forEach(g => optsGrupos += `<option value="${g.nome}">${g.nome}</option>`);
        
        let optsForn = '<option value="">-- Fornecedor --</option>';
        if (data.fornecedores) data.fornecedores.forEach(i => optsForn += `<option value="${i.nome}">${i.nome}</option>`);
        
        let optsFuncionarios = '<option value="">-- Funcionário --</option>';
        if (data.funcionarios) data.funcionarios.forEach(i => optsFuncionarios += `<option value="${i.nome}">${i.nome}</option>`);
        
        let optsTransportadoras = '<option value="">-- Transportadora --</option>';
        if (data.transportadoras) data.transportadoras.forEach(i => optsTransportadoras += `<option value="${i.nome}">${i.nome}</option>`);

        let optsEmpresas = '<option value="">-- Filial --</option>';
        if (data.empresas) data.empresas.forEach(i => optsEmpresas += `<option value="${i.nome}">${i.nome}</option>`);
        
        let optsMarcas = '<option value="">-- Marca --</option>';
        if (data.marcas) data.marcas.forEach(i => optsMarcas += `<option value="${i.nome}">${i.nome}</option>`);

        if (data.cfops) {
            let optsCfops = '<option value="">-- CFOP --</option>';
            data.cfops.forEach(c => optsCfops += `<option value="${c.codigo || c.nome}">${c.codigo || c.nome}</option>`);
            window.optsCfopsGlobal = optsCfops;
        }

        if (data.bancos) {
            let optsBcos = '<option value="">-- Banco --</option>';
            data.bancos.forEach(c => optsBcos += `<option value="${c.nome}">${c.nome}</option>`);
            window.optionsBancos = optsBcos;
        }

        document.querySelectorAll('.ddl-fornecedores').forEach(el => el.innerHTML = optsForn);
        document.querySelectorAll('.ddl-funcionarios').forEach(el => el.innerHTML = optsFuncionarios);
        document.querySelectorAll('.ddl-transportadoras').forEach(el => el.innerHTML = optsTransportadoras);
        document.querySelectorAll('.ddl-grupos').forEach(el => el.innerHTML = optsGrupos);
        document.querySelectorAll('.ddl-empresas').forEach(el => el.innerHTML = optsEmpresas);
        document.querySelectorAll('.ddl-marcas').forEach(el => el.innerHTML = optsMarcas);
        document.querySelectorAll('.ddl-cfops').forEach(el => el.innerHTML = window.optsCfopsGlobal);
        
    } catch(e) { console.error("Erro ao carregar opcoes de suprimentos", e); }
}

// ==========================================
// MODAL DE PESQUISA GENÉRICA
// ==========================================
let alvoIdSup = null; let alvoNomeSup = null; let baseEndpointSup = ''; let gridTargetBtnSup = null; let gridTipoSup = null;

window.abrirPesquisaGridSup = function(entidade, btn, tipoGrid) {
    gridTargetBtnSup = btn;
    gridTipoSup = tipoGrid;
    abrirPesquisaSup(entidade, 'grid_add', 'grid_add');
};

window.abrirPesquisaSup = function(entidade, idInput, nomeInput) {
    if(idInput !== 'grid_add') { gridTargetBtnSup = null; gridTipoSup = null; }
    alvoIdSup = idInput; alvoNomeSup = nomeInput; baseEndpointSup = entidade;
    document.getElementById('mpesq_titulo').innerText = `Pesquisar ${entidade.toUpperCase()}`;
    document.getElementById('mpesq_input').value = '';
    document.getElementById('mpesq_tb').innerHTML = '';
    document.getElementById('modal_pesquisa_generica').classList.add('active');
    executarPesquisaSup();
};

window.fecharPesquisaSup = function() { document.getElementById('modal_pesquisa_generica').classList.remove('active'); };

window.executarPesquisaSup = async function() {
    const q = document.getElementById('mpesq_input').value.toLowerCase();
    const tb = document.getElementById('mpesq_tb'); 
    tb.innerHTML = '<tr><td colspan="3" class="text-center text-muted">A pesquisar...</td></tr>';
    
    try {
        let data = [];
        
        // 1. Tenta a rota rápida dedicada
        const res = await fetch(`/api/suprimentos/pesquisar/${baseEndpointSup}?q=${q}&_=${new Date().getTime()}`);
        if (res.ok) {
            data = await res.json();
        }

        // 2. Fallback de Segurança: Se não encontrar nada ou der erro, busca na rota mestra e filtra no cliente
        if (!res.ok || !Array.isArray(data) || data.length === 0) {
            // Corrige o endpoint se a pesquisa for de grupos
            let fetchEndpoint = baseEndpointSup;
            if (fetchEndpoint === 'grupos') fetchEndpoint = 'grupos_produtos';
            
            const fallbackRes = await fetch(`/api/cadastros/${fetchEndpoint}`);
            if (fallbackRes.ok) {
                const allData = await fallbackRes.json();
                if (Array.isArray(allData)) {
                    // Mapeia todas as possíveis variações de "nome" no banco de dados e pesquisa (inclui nome_grupo)
                    data = allData.filter(i => {
                        let str = (i.nome || i.razao_social || i.nome_razao || i.nome_fantasia || i.nome_grupo || i.cpf_cnpj || i.descricao || '').toLowerCase();
                        return str.includes(q);
                    }).slice(0, 15); // Limita a 15 resultados na visualização
                }
            }
        }
        
        tb.innerHTML = '';

        if (!Array.isArray(data) || data.length === 0) {
            tb.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Nenhum resultado encontrado.</td></tr>';
            return;
        }

        data.forEach(i => { 
            let valorUnitario = i.vlr_custo || i.preco || 0;
            if(typeof valorUnitario === 'string') valorUnitario = valorUnitario.replace(',', '.'); 

            // Tenta resgatar a propriedade nome_grupo que pertence à tabela de grupos
            let nomeDisplay = i.nome || i.razao_social || i.nome_razao || i.nome_fantasia || i.nome_grupo || i.descricao || 'Sem Nome';
            let extraCfop = i.cfop || i.codigo_cfop || '';

            tb.innerHTML += `<tr><td>${i.id}</td><td>${nomeDisplay}</td><td class="text-center"><button type="button" class="btn-neon btn-neon-success" style="padding:2px 8px; font-size:0.7rem;" onclick="selecionarPesquisaSup(${i.id}, '${nomeDisplay.replace(/'/g, "\\'")}', '${valorUnitario}', '${i.unidade_medida||'UN'}', '${extraCfop}')">OK</button></td></tr>`; 
        });
    } catch(e) { 
        console.error(e);
        document.getElementById('mpesq_tb').innerHTML = '<tr><td colspan="3" class="text-center">Falha na pesquisa.</td></tr>'; 
    }
};

window.selecionarPesquisaSup = function(id, nome, paramExtra, paramUnidade, paramCfop = '') {
    if (alvoIdSup === 'grid_add') {
        if (gridTargetBtnSup && gridTipoSup) addRowSup(gridTargetBtnSup, gridTipoSup, nome, paramExtra, paramUnidade, paramCfop);
        fecharPesquisaSup();
        return;
    }
    if(alvoIdSup && document.getElementById(alvoIdSup)) document.getElementById(alvoIdSup).value = id;
    if(alvoNomeSup && document.getElementById(alvoNomeSup)) document.getElementById(alvoNomeSup).value = nome;
    fecharPesquisaSup();
};

// ==========================================
// GESTÃO DAS GRELHAS INTERNAS (ITENS)
// ==========================================
window.calcSubSup = function(el) {
    const tr = el.closest('tr');
    if (!tr) return;
    
    const vlrInput = tr.querySelector('.vlr-un-input');
    const qtdInput = tr.querySelector('.qtd-input');
    const subInput = tr.querySelector('.subtotal-input');
    
    if(vlrInput && qtdInput && subInput) {
        const vlr = parseFloat(vlrInput.value || 0);
        const qtd = parseFloat(qtdInput.value || 0); 
        subInput.value = (vlr * qtd).toFixed(2);
    }
    calcTotaisCompra(); 
};

window.calcTotaisCompra = function() {
    const form = document.getElementById('form_compras');
    if(!form) return;

    let totalProdutos = 0;
    form.querySelectorAll('#tb_itens_compra .subtotal-input').forEach(sub => { totalProdutos += parseFloat(sub.value || 0); });

    const elTotalProd = document.getElementById('comp_total_produtos');
    const elBaseIcms = document.getElementById('comp_base_icms');
    const elValorIcms = document.getElementById('comp_vlr_icms');
    const elDescAuto = document.getElementById('comp_descontos'); 
    
    if (elTotalProd) elTotalProd.value = totalProdutos.toFixed(2);
    
    if (elBaseIcms) elBaseIcms.value = totalProdutos.toFixed(2);
    if (elValorIcms) elValorIcms.value = (totalProdutos * 0.18).toFixed(2);
    if (elDescAuto) elDescAuto.value = (totalProdutos > 1000 ? totalProdutos * 0.05 : 0).toFixed(2); 

    const vFrete = parseFloat(document.getElementById('comp_vlr_frete')?.value || 0);
    const vSeg = parseFloat(document.getElementById('comp_vlr_seg')?.value || 0);
    const vDesp = parseFloat(document.getElementById('comp_despesas')?.value || 0);
    const vEncargos = parseFloat(document.getElementById('comp_encargos')?.value || 0);
    const vDescontos = parseFloat(elDescAuto?.value || 0);
    
    const valorTotalNF = totalProdutos + vFrete + vSeg + vDesp + vEncargos - vDescontos;

    const elTotalNota = document.getElementById('comp_total_nota');
    if (elTotalNota) elTotalNota.value = valorTotalNF.toFixed(2);
};

window.calcSaldoLote = function() {
    const ent = parseFloat(document.getElementById('lot_qtd_entrada')?.value || 0);
    const sai = parseFloat(document.getElementById('lot_qtd_saida')?.value || 0);
    const saldoEl = document.getElementById('lot_saldo');
    if(saldoEl) saldoEl.value = (ent - sai).toFixed(2);
};

window.addRowSup = function(btn, tipo, preNome = '', preVal = '0', preUn = 'UN', preCfop = '') {
    const tb = btn.closest('.section-box').querySelector('tbody');
    let cols = '';
    
    if (tipo === 'compras_itens') {
        cols = `
            <td><input type="text" class="erp-input ignore-serialize" value="${preNome}" readonly></td>
            <td><input type="text" class="erp-input ignore-serialize text-center" value="${preUn}" style="width:60px;" readonly></td>
            <td><input type="text" class="erp-input ignore-serialize" placeholder="Ref"></td>
            <td><select class="erp-select ignore-serialize text-center ddl-cfops" style="width:100px;">${window.optsCfopsGlobal}</select></td>
            <td><input type="number" class="erp-input ignore-serialize qtd-input" value="1" step="0.01" oninput="calcSubSup(this)"></td>
            <td><input type="number" class="erp-input ignore-serialize vlr-un-input" value="${preVal}" step="0.01" oninput="calcSubSup(this)"></td>
            <td><input type="number" class="erp-input ignore-serialize subtotal-input" value="${preVal}" step="0.01" readonly></td>
        `;
    } else if (tipo === 'transferencia_itens') {
        cols = `
            <td class="text-muted text-center" style="width:30px;">#</td>
            <td><input type="text" class="erp-input ignore-serialize" value="${preNome}" readonly></td>
            <td><input type="text" class="erp-input ignore-serialize" placeholder="Ref"></td>
            <td><input type="number" class="erp-input ignore-serialize" value="1" step="0.01"></td>
        `;
    } else if (tipo === 'compras_financeiro') {
        cols = `
            <td><select class="erp-select ignore-serialize">${window.optionsBancos}</select></td>
            <td><input type="text" class="erp-input ignore-serialize" placeholder="Num Fatura"></td>
            <td><input type="date" class="erp-input ignore-serialize"></td>
            <td><input type="number" class="erp-input ignore-serialize" value="0.00" step="0.01"></td>
        `;
    } else if (tipo === 'historico_lote') {
        const dStr = new Date().toISOString().split('T')[0];
        cols = `
            <td><input type="date" class="erp-input ignore-serialize" value="${dStr}"></td>
            <td><select class="erp-select ignore-serialize">
                <option>NF-e</option>
                <option>NFC-e</option>
                <option>Pedido</option>
                <option>OS</option>
                <option>Compra</option>
                <option>Manual</option>
            </select></td>
            <td><input type="text" class="erp-input ignore-serialize" placeholder="Documento"></td>
            <td><input type="number" class="erp-input ignore-serialize" value="1" step="0.01"></td>
        `;
    } else if (tipo === 'descarte_itens') {
        cols = `
            <td><input type="text" class="erp-input ignore-serialize" value="${preNome}" readonly></td>
            <td><input type="text" class="erp-input ignore-serialize" placeholder="Referência"></td>
            <td><input type="number" class="erp-input ignore-serialize qtd-input" value="1" step="0.01"></td>
        `;
    }
    
    tb.insertAdjacentHTML('beforeend', `<tr>${cols}<td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="this.closest('tr').remove(); calcTotaisCompra();">X</button></td></tr>`);
    
    const lastRow = tb.lastElementChild;

    if(tipo === 'compras_itens') {
        calcSubSup(lastRow.querySelector('.qtd-input'));
        if(preCfop) {
            const selCfop = lastRow.querySelector('.ddl-cfops');
            if(selCfop) {
                let opt = Array.from(selCfop.options).find(o => String(o.value).trim().toUpperCase() === String(preCfop).trim().toUpperCase());
                if(opt) { selCfop.value = opt.value; opt.selected = true; }
                else { selCfop.add(new Option(preCfop, preCfop, true, true)); }
            }
        }
    }
};

function extrairGridJsonSup(tableId, chaves) {
    const tb = document.getElementById(tableId);
    if (!tb) return "[]";
    const data = [];
    tb.querySelectorAll('tr').forEach(tr => {
        const inputs = tr.querySelectorAll('input, select');
        if (inputs.length === 0) return;
        let obj = {}; let temValor = false;
        chaves.forEach((k, idx) => { 
            if (inputs[idx]) { obj[k] = inputs[idx].value; if (inputs[idx].value) temValor = true; } 
        });
        if (temValor) data.push(obj);
    });
    return JSON.stringify(data);
}

function renderizarGridSup(tableId, dataArray, tipo) {
    const tb = document.getElementById(tableId);
    if (!tb) return;
    tb.innerHTML = '';
    
    dataArray.forEach(row => {
        let cols = '';
        if (tipo === 'compras_itens') {
            cols = `
                <td><input type="text" value="${safeEdit(row.produto)}" class="erp-input ignore-serialize" readonly></td>
                <td><input type="text" value="${safeEdit(row.unidade)}" class="erp-input ignore-serialize text-center" style="width:60px;" readonly></td>
                <td><input type="text" value="${safeEdit(row.ref)}" class="erp-input ignore-serialize"></td>
                <td><select class="erp-select ignore-serialize text-center ddl-cfops" style="width:100px;">${window.optsCfopsGlobal}</select></td>
                <td><input type="number" value="${safeEdit(row.qtd)}" class="erp-input ignore-serialize qtd-input" step="0.01" oninput="calcSubSup(this)"></td>
                <td><input type="number" value="${safeEdit(row.vlr_un)}" class="erp-input ignore-serialize vlr-un-input" step="0.01" oninput="calcSubSup(this)"></td>
                <td><input type="number" value="${safeEdit(row.subtotal)}" class="erp-input ignore-serialize subtotal-input" step="0.01" readonly></td>
            `;
        } else if (tipo === 'compras_financeiro') {
            cols = `
                <td><select class="erp-select ignore-serialize">${window.optionsBancos}</select></td>
                <td><input type="text" value="${safeEdit(row.numero)}" class="erp-input ignore-serialize"></td>
                <td><input type="date" value="${safeEdit(row.vencimento)}" class="erp-input ignore-serialize"></td>
                <td><input type="number" value="${safeEdit(row.valor)}" class="erp-input ignore-serialize" step="0.01"></td>
            `;
        } else if (tipo === 'transferencia_itens') {
            cols = `
                <td class="text-muted text-center" style="width:30px;">#</td>
                <td><input type="text" value="${safeEdit(row.produto)}" class="erp-input ignore-serialize" readonly></td>
                <td><input type="text" value="${safeEdit(row.ref)}" class="erp-input ignore-serialize"></td>
                <td><input type="number" value="${safeEdit(row.qtd)}" class="erp-input ignore-serialize" step="0.01"></td>
            `;
        } else if (tipo === 'historico_lote') {
            cols = `
                <td><input type="date" value="${safeEdit(row.data)}" class="erp-input ignore-serialize"></td>
                <td><select class="erp-select ignore-serialize"><option value="${safeEdit(row.tipo)}">${safeEdit(row.tipo)}</option></select></td>
                <td><input type="text" value="${safeEdit(row.documento)}" class="erp-input ignore-serialize"></td>
                <td><input type="number" value="${safeEdit(row.qtd)}" class="erp-input ignore-serialize" step="0.01"></td>
            `;
        } else if (tipo === 'descarte_itens') {
            cols = `
                <td><input type="text" value="${safeEdit(row.produto)}" class="erp-input ignore-serialize" readonly></td>
                <td><input type="text" value="${safeEdit(row.ref)}" class="erp-input ignore-serialize"></td>
                <td><input type="number" value="${safeEdit(row.qtd)}" class="erp-input ignore-serialize qtd-input" step="0.01"></td>
            `;
        }
        
        tb.insertAdjacentHTML('beforeend', `<tr>${cols}<td class="text-center"><button type="button" class="btn-neon-danger bg-transparent p-5" onclick="this.closest('tr').remove(); calcTotaisCompra();">X</button></td></tr>`);
        
        const lastRow = tb.lastElementChild;
        
        if (tipo === 'compras_itens' && row.cfop) {
            const selectCfop = lastRow.querySelector('select');
            if (selectCfop) {
                let opt = Array.from(selectCfop.options).find(o => String(o.value).trim().toUpperCase() === String(row.cfop).trim().toUpperCase());
                if (opt) { selectCfop.value = opt.value; opt.selected = true; }
                else { selectCfop.add(new Option(row.cfop, row.cfop, true, true)); }
            }
        } else if (tipo === 'compras_financeiro' && row.banco) {
            const selectBanco = lastRow.querySelector('select');
            if (selectBanco) {
                let opt = Array.from(selectBanco.options).find(o => String(o.value).trim().toUpperCase() === String(row.banco).trim().toUpperCase());
                if (opt) { selectBanco.value = opt.value; opt.selected = true; }
                else { selectBanco.add(new Option(row.banco, row.banco, true, true)); }
            }
        }
    });
    
    if(tipo === 'compras_itens') calcTotaisCompra();
}

// ==========================================
// CONTROLE DE VISTAS, PERSISTÊNCIA (F5) E INICIALIZAÇÃO
// ==========================================
function switchSupView(viewId, btnElement) {
    document.querySelectorAll('.erp-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(btn => btn.classList.remove('active'));
    
    const target = document.getElementById(viewId);
    if (target) {
        target.classList.add('active');
        if(btnElement) btnElement.classList.add('active');
    }

    localStorage.setItem('lastSupView', viewId);

    const loadMap = {
        'view_compras': loadCompras, 'view_balancos': loadBalancos,
        'view_transferencias': loadTransferencias, 'view_lotes': loadLotes,
        'view_descartes': loadDescartes
    };
    if (loadMap[viewId]) loadMap[viewId]();
}

document.addEventListener("DOMContentLoaded", async () => {
    await loadDropdownsSuprimentos(); 
    
    let lastView = localStorage.getItem('lastSupView') || 'view_compras';
    let btn = document.querySelector(`button[onclick*="${lastView}"]`);
    
    if(btn) switchSupView(lastView, btn);
    else switchSupView('view_compras', document.querySelector('.menu-item'));

    const dropZone = document.getElementById('xml_drop_zone');
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.style.backgroundColor = 'rgba(0, 242, 255, 0.1)'; });
        dropZone.addEventListener('dragleave', (e) => { e.preventDefault(); dropZone.style.backgroundColor = 'transparent'; });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault(); dropZone.style.backgroundColor = 'transparent';
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                document.getElementById('xml_file').files = e.dataTransfer.files; 
                if (window.lerArquivoXML) window.lerArquivoXML(document.getElementById('xml_file')); 
            }
        });
    }

    const inputIds = ['comp_vlr_frete', 'comp_vlr_seg', 'comp_despesas', 'comp_encargos'];
    inputIds.forEach(id => {
        const el = document.getElementById(id);
        if(el) el.addEventListener('input', calcTotaisCompra);
    });
});

window.filterTableSup = function(tbodyId, query) {
    const lowerQuery = query.toLowerCase();
    const rows = document.getElementById(tbodyId).querySelectorAll('tr');
    rows.forEach(row => {
        row.style.display = row.innerText.toLowerCase().includes(lowerQuery) ? '' : 'none';
    });
};

// ==========================================
// CRUD GENÉRICO E SALVAGUARDA
// ==========================================
function serializeFormFieldsSup(formId, prefix) {
    const inputs = document.querySelectorAll(`#${formId} input:not(.ignore-serialize), #${formId} select:not(.ignore-serialize), #${formId} textarea:not(.ignore-serialize)`);
    const payload = {};
    inputs.forEach(input => {
        let key = input.id.replace(prefix, '');
        if(key) payload[key] = input.value;
    });
    return payload;
}

window.dispatchEdit = function(formId, prefix, encoded) {
    try {
        const itemObj = JSON.parse(decodeURIComponent(encoded));
        limparFormularioSup(formId);
        
        for (const [key, value] of Object.entries(itemObj)) {
            const el = document.getElementById(prefix + key);
            if (el) el.value = safeEdit(value);
        }
        
        if (formId === 'form_compras') {
            renderizarGridSup('tb_itens_compra', JSON.parse(itemObj.itens_json || '[]'), 'compras_itens');
            renderizarGridSup('tb_financeiro_compra', JSON.parse(itemObj.financeiro_json || '[]'), 'compras_financeiro');
        } else if (formId === 'form_transferencias') {
            renderizarGridSup('tb_itens_transf', JSON.parse(itemObj.itens_json || '[]'), 'transferencia_itens');
        } else if (formId === 'form_serie_lote') {
            renderizarGridSup('tb_historico_lote', JSON.parse(itemObj.historico_json || '[]'), 'historico_lote');
        } else if (formId === 'form_descartes') {
            renderizarGridSup('tb_itens_descarte', JSON.parse(itemObj.itens_json || '[]'), 'descarte_itens');
        }
        
        openModalSup(formId);
    } catch(e) { console.error("Erro ao carregar dados para edição:", e); }
};

async function postRecordSup(tabela, payload, formId) {
    try {
        const res = await fetch(`/api/suprimentos/${tabela}`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify(payload) 
        });
        if (!res.ok) { alert('Falha ao guardar os dados.'); return false; }
        const data = await res.json();
        if(data.sucesso) { limparFormularioSup(formId); return true; }
        return false;
    } catch(e) { alert('Falha de rede.'); return false; }
}

window.deleteRecordSup = async function(tabela, id, callbackLoad) {
    if(!confirm("Excluir permanentemente?")) return;
    try { 
        const res = await fetch(`/api/suprimentos/${tabela}/${id}`, { method: 'DELETE' }); 
        if(res.ok) callbackLoad(); 
    } catch(e) { console.error(e); }
}

function actBtnsSup(frm, prefix, item, tbName, loadFuncStr) {
    let enc = encodeURIComponent(JSON.stringify(item)).replace(/'/g, "%27");
    return `<button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEdit('${frm}', '${prefix}', '${enc}')">✏️</button> 
            <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordSup('${tbName}', ${item.id}, ${loadFuncStr})">🗑️</button>`;
}

window.salvarSup = async function(e, tabela) {
    e.preventDefault();
    const prefixMap = { 'compras': 'comp_', 'balancos': 'bal_', 'transferencias': 'trf_', 'serie_lote': 'lot_', 'descartes': 'dsc_' };
    const loadMap = { 'compras': loadCompras, 'balancos': loadBalancos, 'transferencias': loadTransferencias, 'serie_lote': loadLotes, 'descartes': loadDescartes };
    
    const formId = `form_${tabela}`;
    const payload = serializeFormFieldsSup(formId, prefixMap[tabela]);

    if (tabela === 'compras') {
        payload.itens_json = extrairGridJsonSup('tb_itens_compra', ['produto', 'unidade', 'ref', 'cfop', 'qtd', 'vlr_un', 'subtotal']);
        payload.financeiro_json = extrairGridJsonSup('tb_financeiro_compra', ['banco', 'numero', 'vencimento', 'valor']);
    } else if (tabela === 'transferencias') {
        payload.itens_json = extrairGridJsonSup('tb_itens_transf', ['produto', 'ref', 'qtd']);
    } else if (tabela === 'serie_lote') {
        payload.historico_json = extrairGridJsonSup('tb_historico_lote', ['data', 'tipo', 'documento', 'qtd']);
    } else if (tabela === 'descartes') {
        payload.itens_json = extrairGridJsonSup('tb_itens_descarte', ['produto', 'ref', 'qtd']);
    }

    if(await postRecordSup(tabela, payload, formId)) {
        closeModalSup(formId);
        if(loadMap[tabela]) loadMap[tabela]();
    }
};

// ==========================================
// LOADERS E FILTROS DINÂMICOS
// ==========================================
async function fetchAndRenderSup(tabela, filters, containerId, renderCallback) {
    try {
        const timestamp = new Date().getTime();
        const res = await fetch(`/api/suprimentos/${tabela}?_t=${timestamp}`);
        let data = await res.json();
        
        for (const [key, val] of Object.entries(filters)) {
            if (val && val.trim() !== '') {
                data = data.filter(item => {
                    let itemVal = item[key];
                    if(key === 'tipo_data_aux' || key === 'data_aux') return true; 
                    if(key === 'data_especial') {
                        let dataRef = filters['tipo_data_aux'] === 'emissao' ? item.data_emissao : (filters['tipo_data_aux'] === 'fabricacao' ? item.data_fabricacao : item.data_entrada || item.data);
                        return !filters['data_aux'] || dataRef === filters['data_aux'];
                    }
                    return String(itemVal).toLowerCase().includes(String(val).toLowerCase());
                });
            }
        }

        const tb = document.getElementById(containerId);
        if (!tb) return;
        tb.innerHTML = '';
        if (data.length === 0) { tb.innerHTML = `<tr><td colspan="15" class="text-center text-muted">Vazio.</td></tr>`; return; }
        data.forEach(i => { tb.innerHTML += renderCallback(i); });
    } catch(e) { console.error(`Erro ao carregar ${tabela}:`, e); }
}

window.loadCompras = async function() {
    const filters = {
        data_especial: 'sim',
        data_aux: document.getElementById('flt_comp_data')?.value,
        tipo_data_aux: document.getElementById('flt_comp_tipo_data')?.value,
        fornecedor_id: document.getElementById('flt_comp_fornecedor')?.value,
        comprador_id: document.getElementById('flt_comp_comprador')?.value
    };
    fetchAndRenderSup('compras', filters, 'tb_compras', i => 
        `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="font-bold text-success">${safeVal(i.numero)} ${safeVal(i.serie) !== '-' ? '- S:'+i.serie : ''}</td><td>${safeVal(i.data_entrada)}</td><td class="text-info">${safeVal(i.fornecedor_nome)}</td><td class="font-bold">R$ ${parseFloat(i.total_nota || i.valor_total || 0).toFixed(2)}</td><td class="text-center">${actBtnsSup('form_compras', 'comp_', i, 'compras', 'loadCompras')}</td></tr>`
    );
}

window.loadBalancos = async function() {
    const filters = {
        data: document.getElementById('flt_bal_data')?.value,
        responsavel: document.getElementById('flt_bal_responsavel')?.value,
        status: document.getElementById('flt_bal_status')?.value
    };
    fetchAndRenderSup('balancos', filters, 'tb_balancos', i => 
        `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td>${i.id}</td><td class="font-bold">${safeVal(i.data)}</td><td class="text-warning">${safeVal(i.responsavel)}</td><td>${safeVal(i.status)}</td><td class="text-center">${actBtnsSup('form_balancos', 'bal_', i, 'balancos', 'loadBalancos')}</td></tr>`
    );
}

window.loadTransferencias = async function() {
    const filters = {
        data: document.getElementById('flt_trf_data')?.value,
        destino: document.getElementById('flt_trf_destino')?.value,
        responsavel: document.getElementById('flt_trf_responsavel')?.value,
        status: document.getElementById('flt_trf_status')?.value
    };
    fetchAndRenderSup('transferencias', filters, 'tb_transferencias', i => 
        `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td class="font-bold text-info">${safeVal(i.numero)}</td><td>${safeVal(i.data)}</td><td>${safeVal(i.destino)}</td><td>${safeVal(i.responsavel)}</td><td>${safeVal(i.status)}</td><td class="text-center">${actBtnsSup('form_transferencias', 'trf_', i, 'transferencias', 'loadTransferencias')}</td></tr>`
    );
}

window.loadLotes = async function() {
    const filters = {
        tipo: document.getElementById('flt_lot_tipo')?.value,
        data_especial: 'sim',
        data_aux: document.getElementById('flt_lot_data')?.value,
        tipo_data_aux: document.getElementById('flt_lot_tipo_data')?.value,
        produto_nome: document.getElementById('flt_lot_produto')?.value,
        fornecedor_nome: document.getElementById('flt_lot_fornecedor')?.value
    };
    fetchAndRenderSup('serie_lote', filters, 'tb_serie_lote', i => 
        `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td>${i.id}</td><td>${safeVal(i.tipo || 'Entrada')}</td><td class="text-muted">${safeVal(i.produto_id)}</td><td class="text-info">${safeVal(i.produto_nome)}</td><td class="font-bold">${safeVal(i.numero)}</td><td>${safeVal(i.data_fabricacao)}</td><td>${safeVal(i.data_validade)}</td><td>${i.qtd_entrada || 0}</td><td>${i.qtd_saida || 0}</td><td class="text-success font-bold">${i.saldo || 0}</td><td class="text-center">${actBtnsSup('form_serie_lote', 'lot_', i, 'serie_lote', 'loadLotes')}</td></tr>`
    );
}

window.loadDescartes = async function() {
    const filters = {
        data: document.getElementById('flt_dsc_data')?.value
    };
    fetchAndRenderSup('descartes', filters, 'tb_descartes', i => 
        `<tr><td class="text-center"><input type="checkbox" class="row-check" value="${i.id||''}"></td><td>${i.id}</td><td>${safeVal(i.data)}</td><td class="text-warning">${safeVal(i.usuario)}</td><td class="text-center">${actBtnsSup('form_descartes', 'dsc_', i, 'descartes', 'loadDescartes')}</td></tr>`
    );
}

function executarAcaoExternaSup(nomeAcao) {
    if (nomeAcao === 'Importar XML') {
        switchSupView('view_import_xml', document.querySelector('.menu-item:nth-child(2)'));
    } else {
        alert("Ação: " + nomeAcao);
    }
}

// ==========================================
// FUNÇÕES DE IMPORTAÇÃO E WORKSPACE XML
// ==========================================
window.lerArquivoXML = function(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const reader = new FileReader();
    
    simularProcessoSup('Importação de XML - SEFAZ', [
        "> Lendo ficheiro XML anexado...",
        "> Analisando tags de cabeçalho e emitente...",
        "> Extraindo produtos e convertendo quantidades...",
        "<span style='color:#0f0;'>✔ Leitura concluída. Revise os dados importados abaixo!</span>"
    ]);

    reader.onload = function(e) {
        const xmlText = e.target.result;
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlText, "text/xml");
        
        setTimeout(() => {
            const painelSimulacao = document.getElementById('btn-close-sim')?.parentElement;
            if(painelSimulacao) painelSimulacao.remove();

            document.getElementById('xml_drop_zone').style.display = 'none';
            document.getElementById('workspace_importacao').style.display = 'block';

            const getVal = (parent, tag) => {
                if(!parent) return '';
                const node = parent.getElementsByTagName(tag)[0];
                return node ? node.textContent : '';
            };
            
            const infNFe = xmlDoc.getElementsByTagName('infNFe')[0];
            const ide = xmlDoc.getElementsByTagName('ide')[0];
            const emit = xmlDoc.getElementsByTagName('emit')[0];

            if (!infNFe || !ide || !emit) {
                alert("Ficheiro XML inválido ou não reconhecido como NF-e da SEFAZ.");
                abrirCompraManual();
                return;
            }

            const emitNome = getVal(emit, 'xNome');
            const emitCnpj = getVal(emit, 'CNPJ');
            document.getElementById('ws_fornecedor').value = `${emitNome} | ${emitCnpj}`;
            
            document.getElementById('ws_operacao').value = getVal(ide, 'natOp');
            document.getElementById('ws_numero').value = getVal(ide, 'nNF');
            document.getElementById('ws_serie').value = getVal(ide, 'serie');
            document.getElementById('ws_modelo').value = getVal(ide, 'mod');
            
            let dhEmi = getVal(ide, 'dhEmi');
            if(dhEmi) document.getElementById('ws_dt_emissao').value = dhEmi.substring(0, 10);
            document.getElementById('ws_dt_entrada').value = new Date().toISOString().split('T')[0];
            
            let chave = infNFe.getAttribute('Id') || '';
            document.getElementById('ws_chave_acesso').value = chave.replace('NFe', '');

            document.getElementById('ws_lista_itens').innerHTML = ''; 
            
            const dets = xmlDoc.getElementsByTagName('det');
            for (let i = 0; i < dets.length; i++) {
                const prod = dets[i].getElementsByTagName('prod')[0];
                if(prod) {
                    adicionarLinhaManual({
                        nome: getVal(prod, 'xProd'),
                        qtd: parseFloat(getVal(prod, 'qCom') || 0),
                        un: getVal(prod, 'uCom'),
                        cfop: getVal(prod, 'CFOP'),
                        preco: parseFloat(getVal(prod, 'vProd') || 0).toFixed(2)
                    });
                }
            }
            input.value = ''; 
        }, 3000); 
    };
    reader.readAsText(file);
};

window.adicionarLinhaManual = function(mockData = null) {
    const tbody = document.getElementById('ws_lista_itens');
    const seq = tbody.children.length + 1;
    const tr = document.createElement('tr');

    let pNome = mockData ? mockData.nome : '';
    let pQtd = mockData ? mockData.qtd : '1';
    let pUn = mockData ? mockData.un : 'UN';
    let pCfop = mockData ? mockData.cfop : '';
    let pPreco = mockData ? mockData.preco : '0.00';

    tr.innerHTML = `
        <td class="text-center font-bold text-muted" style="background: rgba(0,0,0,0.2);">${seq}</td>
        <td><input type="text" class="erp-input nf-produto" value="${pNome}" placeholder="Nome no XML"></td>
        <td><input type="number" class="erp-input text-center nf-qtd" value="${pQtd}" step="0.01"></td>
        <td><input type="text" class="erp-input text-center nf-unid" value="${pUn}"></td>
        <td><input type="text" class="erp-input text-center nf-cfop" value="${pCfop}"></td>
        <td><input type="number" class="erp-input nf-piscofins" value="0.00" step="0.01"></td>
        <td><input type="number" class="erp-input nf-ipi" value="0.00" step="0.01"></td>
        <td style="border-right: 3px solid #111;"><input type="number" class="erp-input nf-preco text-warning font-bold" value="${pPreco}" step="0.01"></td>
        
        <td style="display:flex; gap:5px; align-items:center;">
            <input type="text" class="erp-input imp-insumo-id text-success" placeholder="Nome Interno">
            <button class="btn-neon btn-neon-danger bg-transparent" style="padding: 4px 8px; font-size: 0.7rem;" title="Remover" onclick="this.closest('tr').remove()">🗑️</button>
        </td>
        <td><input type="number" class="erp-input text-center imp-qtd" value="${pQtd}" step="0.01"></td>
        <td><input type="text" class="erp-input text-center imp-unid" value="${pUn}"></td>
        <td><input type="text" class="erp-input text-center imp-cfop" value="1102"></td>
        <td>
            <select class="erp-input imp-piscofins">
                <option value="identificar">-- Identificar --</option>
                <option value="credito">Crédito</option>
                <option value="custo">Custo</option>
            </select>
        </td>
        <td>
            <select class="erp-input imp-ipi">
                <option value="identificar">-- Identificar --</option>
                <option value="credito">Crédito</option>
                <option value="custo">Custo</option>
            </select>
        </td>
        <td><input type="number" class="erp-input imp-venda text-success" placeholder="R$ 0,00" step="0.01"></td>
    `;
    tbody.appendChild(tr);
};

window.abrirCompraManual = function() {
    document.querySelectorAll('#workspace_importacao input').forEach(i => i.value = '');
    document.getElementById('ws_lista_itens').innerHTML = '';
    document.getElementById('workspace_importacao').style.display = 'none';
    document.getElementById('xml_drop_zone').style.display = 'block';
};

window.efetivarImportacao = async function() {
    const payload = {
        fornecedor_nome: document.getElementById('ws_fornecedor').value,
        operacao: document.getElementById('ws_operacao').value,
        numero: document.getElementById('ws_numero').value,
        serie: document.getElementById('ws_serie').value,
        modelo: document.getElementById('ws_modelo').value,
        data_emissao: document.getElementById('ws_dt_emissao').value,
        data_entrada: document.getElementById('ws_dt_entrada').value,
        chave_nfe: document.getElementById('ws_chave_acesso').value,
        status: 'PROCESSADA'
    };

    const itens = []; let total = 0;
    
    document.querySelectorAll('#ws_lista_itens tr').forEach(tr => {
        const produtoNome = tr.querySelector('.imp-insumo-id').value; 
        const qtd = parseFloat(tr.querySelector('.imp-qtd').value || 0);
        const subtotal = parseFloat(tr.querySelector('.nf-preco').value || 0);
        const unid = tr.querySelector('.imp-unid').value;
        const cfop = tr.querySelector('.imp-cfop').value;
        const vlrUn = qtd > 0 ? (subtotal / qtd) : 0;

        total += subtotal;

        if (produtoNome && produtoNome.trim() !== "") {
            itens.push({ produto: produtoNome, unidade: unid, ref: 'IMP-XML', cfop: cfop, qtd: qtd, vlr_un: vlrUn.toFixed(2), subtotal: subtotal.toFixed(2) });
        }
    });

    if (itens.length === 0) { alert("Atenção: Nome interno não preenchido."); return; }

    payload.itens_json = JSON.stringify(itens);
    payload.valor_total = total; payload.total_nota = total; payload.financeiro_json = '[]'; 

    const sucesso = await postRecordSup('compras', payload, 'form_compras');
    if(sucesso) {
        alert('✅ Importação concluída com sucesso!');
        abrirCompraManual(); loadCompras(); switchSupView('view_compras', document.querySelectorAll('.menu-item')[0]);
    }
};

function simularProcessoSup(acao, logs) {
    const painel = document.createElement('div');
    painel.style.cssText = "position:fixed; top:50%; left:50%; transform:translate(-50%, -50%); background:#111; border: 2px solid #00f2ff; padding: 20px; border-radius: 8px; z-index:9999; color: #fff; width: 400px; text-align: center; box-shadow: 0 0 20px rgba(0, 242, 255, 0.4);";
    painel.innerHTML = `<h3 style="color:#00f2ff; margin-top:0;">⚡ Sistema: ${acao}</h3><div id="sim-log" style="background:#000; padding:10px; height:120px; overflow-y:auto; text-align:left; font-family:monospace; font-size:12px; margin-bottom:15px; border:1px solid #333; line-height: 1.5;"></div><button onclick="this.parentElement.remove()" class="btn-neon btn-neon-success" style="display:none; width: 100%;" id="btn-close-sim">Concluir e Fechar</button>`;
    document.body.appendChild(painel);
    const logContainer = painel.querySelector('#sim-log'); const btn = painel.querySelector('#btn-close-sim');
    let delay = 0;
    logs.forEach((linha, index) => {
        delay += 600; 
        setTimeout(() => {
            logContainer.innerHTML += linha.replace(/\n/g, '<br>') + '<br>';
            logContainer.scrollTop = logContainer.scrollHeight;
            if (index === logs.length - 1) btn.style.display = "block";
        }, delay);
    });
}