let dadosNFeAtual = null;
let listaInsumosDB = [];

document.addEventListener("DOMContentLoaded", async () => {
    try {
        const resp = await fetch('/api/fiscal/insumos');
        if (resp.ok) listaInsumosDB = await resp.json();
    } catch (e) { console.error("Erro ao carregar insumos:", e); }
    
    // Deixamos a tela aguardando o upload do XML (área de dropzone visível)
    document.getElementById('area_upload_xml').classList.remove('hidden');
    document.getElementById('workspace_importacao').classList.add('hidden');
});

function switchTabFiscal(tabId, btnElement) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-${tabId}`).classList.add('active');
    btnElement.classList.add('active');

    if(tabId === 'emitente') carregarDadosEmitente();
    if(tabId === 'cardapio') carregarCardapioFiscal();
    if(tabId === 'emissao') carregarFilaEmissao();
}

// ==========================================
// FORMULÁRIO DE IMPORTAÇÃO DE COMPRA (ABA 1)
// ==========================================
function abrirCompraManual(inserirMock = false) {
    dadosNFeAtual = null;
    
    // Limpa ou simula o preenchimento do cabeçalho
    document.getElementById('ws_operacao').value = inserirMock ? 'NOTA DE ECF' : '';
    document.getElementById('ws_numero').value = inserirMock ? '34387' : '';
    document.getElementById('ws_serie').value = inserirMock ? '002' : '';
    document.getElementById('ws_modelo').value = inserirMock ? '55' : '55';
    document.getElementById('ws_dt_emissao').value = inserirMock ? '2026-02-02' : new Date().toISOString().split('T')[0];
    document.getElementById('ws_dt_entrada').value = inserirMock ? '2026-02-02' : new Date().toISOString().split('T')[0];
    document.getElementById('ws_fornecedor').value = inserirMock ? 'D. F. FAVORETO SUPERMERCADO EIRELI | 00.483.394/0001-86' : '';
    document.getElementById('ws_chave_acesso').value = '';
    
    document.getElementById('ws_lista_itens').innerHTML = '';
    
    if (inserirMock) {
        // Exemplo requisitado 
        adicionarLinhaManual({ produto: "Macarrões Talharim", qtd: 10, unid: "PCT", cfop: "5102", preco: 45.90 });
        adicionarLinhaManual({ produto: "Piraque Espaguete", qtd: 5, unid: "PCT", cfop: "5102", preco: 22.50 });
        adicionarLinhaManual({ produto: "Macarrão Fidelinho", qtd: 3, unid: "PCT", cfop: "5102", preco: 15.00 });
        adicionarLinhaManual({ produto: "Macarrão Pena", qtd: 8, unid: "PCT", cfop: "5102", preco: 38.00 });
        adicionarLinhaManual({ produto: "Bebida Soja Ades Maçã", qtd: 12, unid: "CX", cfop: "5405", preco: 65.00 });
        adicionarLinhaManual({ produto: "Bebida Soja Ades Uva", qtd: 12, unid: "CX", cfop: "5405", preco: 65.00 });
        adicionarLinhaManual({ produto: "Atum Gomes da Costa", qtd: 24, unid: "LT", cfop: "5102", preco: 180.00 });
        adicionarLinhaManual({ produto: "Energético Monster Ultra Fiesta Mango", qtd: 6, unid: "LT", cfop: "5405", preco: 54.00 });
    } else {
        adicionarLinhaManual(); 
    }
}

function adicionarLinhaManual(item = null) {
    const tb = document.getElementById('ws_lista_itens');
    const seq = tb.children.length + 1;
    
    let p_nf="", q_nf="1", u_nf="UN", c_nf="", pis_nf="0.00", ipi_nf="0.00", preco_nf="0.00";
    let c_imp="1102";
    
    if(item) {
        p_nf = item.produto || item.nome_fornecedor || ""; 
        q_nf = item.qtd || item.quantidade_comprada || 1; 
        u_nf = item.unid || item.unidade_fornecedor || "UN";
        c_nf = item.cfop || item.cfop_fornecedor || "5102"; 
        preco_nf = item.preco ? item.preco.toFixed(2) : (item.custo_total_real ? item.custo_total_real.toFixed(2) : "0.00");
        if(item.v_pis_cofins) pis_nf = item.v_pis_cofins.toFixed(2);
        if(item.v_ipi) ipi_nf = item.v_ipi.toFixed(2);
        if(item.cfop_sugerido) c_imp = item.cfop_sugerido;
        else if (c_nf.startsWith('5')) c_imp = '1'+c_nf.substring(1);
    }

    let optionsInsumos = '<option value="">-- Identificar / Cadastrar --</option>';
    listaInsumosDB.forEach(ins => {
        optionsInsumos += `<option value="${ins.id}">${ins.nome}</option>`;
    });

    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td class="text-center font-bold text-muted" style="background: rgba(0,0,0,0.2);">${seq}</td>
        <td><input type="text" class="erp-input nf-produto" value="${p_nf}"></td>
        <td><input type="number" class="erp-input text-center nf-qtd" value="${q_nf}" step="0.01"></td>
        <td><input type="text" class="erp-input text-center nf-unid" value="${u_nf}"></td>
        <td><input type="text" class="erp-input text-center nf-cfop" value="${c_nf}"></td>
        <td><input type="number" class="erp-input nf-piscofins" value="${pis_nf}" step="0.01"></td>
        <td><input type="number" class="erp-input nf-ipi" value="${ipi_nf}" step="0.01"></td>
        <td style="border-right: 3px solid #111;"><input type="number" class="erp-input nf-preco text-warning font-bold" value="${preco_nf}" step="0.01"></td>
        
        <td style="display:flex; gap:5px; align-items:center;">
            <select class="erp-input imp-insumo-id" style="flex:1;">${optionsInsumos}</select>
            <button class="btn-neon btn-neon-primary" style="padding: 4px 8px; font-size: 0.7rem;" title="Cadastrar Rápido">➕</button>
        </td>
        <td><input type="number" class="erp-input text-center imp-qtd" value="${q_nf}" step="0.01"></td>
        <td><input type="text" class="erp-input text-center imp-unid" value="${u_nf}"></td>
        <td><input type="text" class="erp-input text-center imp-cfop" value="${c_imp}"></td>
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
    tb.appendChild(tr);
}

// ==========================================
// PREENCHIMENTO AUTOMÁTICO (XML)
// ==========================================
function handleFileSelect(event) {
    if (event.target.files.length > 0) enviarArquivoXML(event.target.files[0]);
}

async function enviarArquivoXML(file) {
    if (!file.name.toLowerCase().endsWith('.xml')) return alert("Selecione um XML válido.");
    
    document.getElementById('upload_status').innerHTML = '<span class="text-info">⏳ A ler XML...</span>';
    const formData = new FormData(); 
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/fiscal/processar-xml-entrada', { method: 'POST', body: formData });
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.detail);
        document.getElementById('upload_status').innerHTML = '<span class="text-success">✅ Auto-preenchido com sucesso!</span>';
        
        document.getElementById('ws_operacao').value = data.operacao || '';
        document.getElementById('ws_numero').value = data.numero_nota || '';
        document.getElementById('ws_serie').value = data.serie || '';
        document.getElementById('ws_modelo').value = data.modelo || '55';
        
        let emissao = new Date(data.data_emissao);
        document.getElementById('ws_dt_emissao').value = isNaN(emissao) ? '' : emissao.toISOString().split('T')[0];
        document.getElementById('ws_fornecedor').value = `${data.fornecedor.nome} | ${data.fornecedor.cnpj}`;
        
        document.getElementById('ws_lista_itens').innerHTML = '';
        data.itens.forEach(item => adicionarLinhaManual(item));
        
    } catch (error) { 
        document.getElementById('upload_status').innerHTML = `<span class="text-danger">❌ Erro: ${error.message}</span>`; 
    }
}

async function efetivarImportacao() {
    const linhas = document.querySelectorAll('#ws_lista_itens tr');
    const itensMapeados = [];
    
    linhas.forEach(tr => {
        const insumoSelect = tr.querySelector('.imp-insumo-id');
        if (insumoSelect && insumoSelect.value) {
            itensMapeados.push({
                n_item: tr.querySelector('td').innerText,
                insumo_id: parseInt(insumoSelect.value),
                quantidade_xml: parseFloat(tr.querySelector('.imp-qtd').value || 0),
                fator_conversao: 1,
                custo_total_real: parseFloat(tr.querySelector('.nf-preco').value || 0),
                cfop: tr.querySelector('.imp-cfop').value || '1102'
            });
        }
    });
    
    if (itensMapeados.length === 0) {
        return alert("Necessita de identificar e vincular pelo menos um Produto no painel interno para efetivar a entrada.");
    }
    
    const payload = {
        chave_acesso: document.getElementById('ws_chave_acesso').value || 'COMPRA-MANUAL-' + Date.now(),
        numero_nota: document.getElementById('ws_numero').value || 'S/N',
        itens: itensMapeados
    };
    
    try {
        const resp = await fetch('/api/fiscal/efetivar-entrada', {
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const result = await resp.json();
        if (!resp.ok) throw new Error(result.detail);
        
        alert("✅ " + result.mensagem);
        abrirCompraManual(); // Limpa e prepara nova
        document.getElementById('upload_status').innerText = '';
        
    } catch (e) { 
        alert("❌ Erro ao efetivar entrada: " + e.message); 
    }
}

// ==========================================
// ABA 2: DADOS DO EMITENTE
// ==========================================
async function carregarDadosEmitente() {
    try {
        const resp = await fetch('/api/fiscal/emitente');
        const dados = await resp.json();
        
        if (dados && dados.cnpj) {
            const campos = ['cnpj', 'razao_social', 'inscricao_estadual', 'crt', 'cep', 'logradouro', 'numero', 'bairro', 'codigo_municipio_ibge', 'uf', 'ambiente', 'csc_id', 'csc_codigo', 'certificado_senha'];
            campos.forEach(campo => {
                const el = document.getElementById(`em_${campo}`);
                if (el) el.value = dados[campo] || '';
            });
            
            if(dados.certificado_path) {
                const statusCert = document.getElementById('status_certificado');
                statusCert.innerHTML = "✅ Certificado A1 já carregado no sistema.";
                statusCert.classList.remove('text-muted', 'text-warning');
                statusCert.classList.add('text-success');
            }
        }
    } catch (e) { console.error("Erro ao carregar emitente:", e); }
}

async function salvarDadosEmitente(event) {
    event.preventDefault();
    const form = document.getElementById('formEmitente');
    const formData = new FormData(form);
    
    try {
        const resp = await fetch('/api/fiscal/emitente', { method: 'POST', body: formData });
        const result = await resp.json();
        
        if (resp.ok) { 
            alert("✅ " + result.mensagem); 
            carregarDadosEmitente(); 
        } else {
            alert("❌ Erro: " + result.detail);
        }
    } catch (error) { alert("❌ Erro de comunicação com o servidor."); }
}

// ==========================================
// ABA 3: TRIBUTAÇÃO DO CARDÁPIO
// ==========================================
async function carregarCardapioFiscal() {
    const tbody = document.getElementById('lista_cardapio_fiscal');
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">A analisar catálogo de produtos...</td></tr>';
    
    try {
        const resp = await fetch('/api/fiscal/cardapio');
        const data = await resp.json();
        
        if (data.sucesso && data.itens) {
            tbody.innerHTML = '';
            data.itens.forEach(item => {
                let corInputNCM = item.ncm === '' ? 'border-color: #ef4444; background: rgba(239,68,68,0.1);' : 'border-color: #444;';
                let corInputCFOP = item.cfop_venda === '' ? 'border-color: #f59e0b; background: rgba(245,158,11,0.1);' : 'border-color: #444;';
                
                tbody.innerHTML += `
                    <tr class="linha-produto-fiscal" data-tabela="${item.tabela_origem}" data-id="${item.produto_id}">
                        <td><span class="tag-fiscal text-uppercase">${item.tabela_origem}</span></td>
                        <td><strong class="text-white nome-produto">${item.produto_nome}</strong></td>
                        <td><input type="text" class="form-control input-ncm" value="${item.ncm}" placeholder="8 dígitos" maxlength="8" style="width: 130px; background: #222; color: #fff; ${corInputNCM}"></td>
                        <td><input type="text" class="form-control input-cfop" value="${item.cfop_venda}" placeholder="Ex: 5102" maxlength="4" style="width: 90px; background: #222; color: #fff; ${corInputCFOP}"></td>
                    </tr>
                `;
            });
        }
    } catch (e) { tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Erro ao carregar catálogo.</td></tr>'; }
}

function filtrarCardapioFiscal() {
    let input = document.getElementById('busca_cardapio_fiscal').value.toLowerCase();
    let linhas = document.querySelectorAll('.linha-produto-fiscal');
    
    linhas.forEach(linha => {
        let nome = linha.querySelector('.nome-produto').innerText.toLowerCase();
        let categoria = linha.querySelector('.tag-fiscal').innerText.toLowerCase();
        linha.style.display = (nome.includes(input) || categoria.includes(input)) ? '' : 'none';
    });
}

async function salvarTributacaoCardapio() {
    const linhas = document.querySelectorAll('.linha-produto-fiscal');
    const itensParaSalvar = [];
    
    linhas.forEach(linha => {
        const ncmVal = linha.querySelector('.input-ncm').value.replace(/\D/g, ''); 
        const cfopVal = linha.querySelector('.input-cfop').value.replace(/\D/g, '');
        
        if (ncmVal.length > 0 || cfopVal.length > 0) {
            itensParaSalvar.push({
                tabela_origem: linha.dataset.tabela, produto_id: parseInt(linha.dataset.id), ncm: ncmVal, cfop_venda: cfopVal || '5102'
            });
        }
    });
    
    if(itensParaSalvar.length === 0) return alert("Sem dados tributários preenchidos para guardar.");
    
    try {
        const resp = await fetch('/api/fiscal/cardapio', { 
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ itens: itensParaSalvar }) 
        });
        
        const result = await resp.json();
        if(resp.ok) { 
            alert("✅ " + result.mensagem); carregarCardapioFiscal(); 
        } else alert("❌ Erro ao guardar: " + result.detail);
    } catch (e) { alert("❌ Falha na comunicação com o servidor."); }
}

// ==========================================
// ABA 4: FILA DE EMISSÃO (NFC-e)
// ==========================================
async function carregarFilaEmissao() {
    const tbody = document.getElementById('lista_pedidos_fiscal');
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">A analisar base de dados de pedidos...</td></tr>';
    
    try {
        const resp = await fetch('/api/fiscal/fila-emissao');
        const data = await resp.json();
        
        if (data.sucesso && data.pedidos) {
            tbody.innerHTML = '';
            
            data.pedidos.forEach(p => {
                let badgeStatus = '', botoes = '';
                let valorStr = (p.valor_total || 0).toFixed(2).replace('.', ',');
                
                if (p.status_fiscal === 'autorizado') {
                    badgeStatus = '<span class="tag-fiscal text-success" style="border-color: #10b981; background: rgba(16,185,129,0.1);">✅ Autorizado</span>';
                    botoes = `<button class="btn-neon btn-neon-green" style="padding: 5px 10px; font-size: 0.8rem;" onclick="window.open('${p.url_danfe}', '_blank')">📄 Ver/Imprimir PDF</button>`;
                } else if (p.status_fiscal === 'rejeitado') {
                    badgeStatus = `<span class="tag-fiscal text-danger" title="${p.motivo_rejeicao}">❌ Rejeitado SEFAZ</span>`;
                    botoes = `<button class="btn-neon btn-neon-orange" style="padding: 5px 10px; font-size: 0.8rem;" onclick="emitirNFCe(${p.id}, this)">🔄 Tentar Novamente</button>`;
                } else {
                    badgeStatus = '<span class="tag-fiscal text-warning">⏳ Pendente</span>';
                    botoes = `<button class="btn-neon btn-neon-primary" style="padding: 5px 10px; font-size: 0.8rem;" onclick="emitirNFCe(${p.id}, this)">📠 Emitir NFC-e</button>`;
                }

                tbody.innerHTML += `
                    <tr style="border-bottom: 1px solid #333;">
                        <td class="font-bold text-lg">#${p.id}</td>
                        <td><strong class="text-white">${p.cliente_nome || 'Consumidor Final'}</strong><br><span class="text-xs text-muted">${p.cliente_telefone || 'Sem identificação'}</span></td>
                        <td class="text-warning font-bold text-lg">R$ ${valorStr}</td>
                        <td>${badgeStatus}</td>
                        <td class="text-center">${botoes}</td>
                    </tr>`;
            });
            if (data.pedidos.length === 0) tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-20">Nenhum pedido finalizado encontrado na base de dados.</td></tr>';
        } else throw new Error(data.detail);
    } catch (e) { tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">Erro ao carregar fila: ${e.message}</td></tr>`; }
}

async function emitirNFCe(pedidoId, btnElement) {
    if(!confirm(`Confirma a transmissão eletrónica do Pedido #${pedidoId} para a SEFAZ?`)) return;
    try {
        btnElement.innerHTML = '⏳ Transmitindo...'; btnElement.disabled = true;
        const resp = await fetch(`/api/fiscal/emitir-nfce/${pedidoId}`, { method: 'POST' });
        const result = await resp.json();
        if (resp.ok) alert("✅ " + result.mensagem);
        else alert("❌ Rejeição SEFAZ: " + result.detail);
        carregarFilaEmissao();
    } catch (e) { alert("❌ Falha de rede ou servidor interno."); carregarFilaEmissao(); }
}