// ==========================================
// VARIÁVEIS DE ESTADO DO PDV
// ==========================================
let produtosPDV = [];
let carrinho = [];
let pagamentos = []; // Adicionado controle para múltiplos pagamentos
let totais = { subtotal: 0, desconto: 0, total: 0, pago: 0, troco: 0 };
let statusCaixa = 'FECHADO'; // Inicia FECHADO. O usuário é obrigado a abrir!

// Variável para o Scanner de Código de Barras
let html5QrCode = null;

// ==========================================
// INICIALIZAÇÃO E AUTO-CORREÇÕES
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    garantirModalCaixa(); // Cria o modal de caixa dinamicamente se faltar no HTML
    garantirScannerUI();  // Injeta o botão e o modal do scanner de câmera
    
    carregarDropdownsERP(); 
    carregarProdutos();
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'F2') {
            e.preventDefault();
            finalizarVenda();
        }
    });
});

// ==========================================
// FUNÇÕES UTILITÁRIAS
// ==========================================
function parsePreco(valorRaw) {
    if (valorRaw === null || valorRaw === undefined) return 0;
    if (typeof valorRaw === 'number') return valorRaw;
    
    let str = String(valorRaw).trim();
    str = str.replace(/[^\d.,]/g, '');
    
    if (!str) return 0;
    
    let ultimoPonto = str.lastIndexOf('.');
    let ultimaVirgula = str.lastIndexOf(',');
    
    if (ultimoPonto > -1 && ultimaVirgula > -1) {
        if (ultimaVirgula > ultimoPonto) {
            str = str.replace(/\./g, '').replace(',', '.');
        } else {
            str = str.replace(/,/g, '');
        }
    } else if (ultimaVirgula > -1) {
        str = str.replace(',', '.');
    }
    
    let num = parseFloat(str);
    return isNaN(num) ? 0 : num;
}

function obterValorInteligente(obj, palavrasChave) {
    if (!obj || typeof obj !== 'object') return null;
    const chaves = Object.keys(obj);

    for (let palavra of palavrasChave) {
        const match = chaves.find(k => k.toLowerCase().trim() === palavra.toLowerCase());
        if (match && obj[match] !== null && obj[match] !== '') return obj[match];
    }

    for (let palavra of palavrasChave) {
        const match = chaves.find(k => k.toLowerCase().includes(palavra.toLowerCase()));
        if (match && obj[match] !== null && obj[match] !== '') return obj[match];
    }

    return null;
}

// Bip sonoro para o scanner de código de barras
function playBeep() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, ctx.currentTime);
        osc.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.1);
    } catch(e) {}
}

// ==========================================
// FUNÇÕES DO CAIXA (MODAL E LÓGICA)
// ==========================================

// Cria o HTML do modal via JS caso não exista
window.garantirModalCaixa = function() {
    if (!document.getElementById('modal_caixa')) {
        const modalHTML = `
        <div id="modal_caixa" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 10000; align-items: center; justify-content: center; backdrop-filter: blur(5px);">
            <div class="form-panel" style="width: 90%; max-width: 500px; background: #111827; border: 1px solid #00ffcc; border-radius: 8px; padding: 20px; box-shadow: 0 0 20px rgba(0,255,204,0.2);">
                <h2 class="text-center text-warning mb-20">💰 Gestão do Caixa</h2>
                
                <div class="form-grid">
                    <div class="col-span-2">
                        <label>Operação Desejada:</label>
                        <select id="modal_caixa_operacao" class="erp-input text-lg font-bold text-center" style="height: 50px;">
                            <option value="ABERTURA">🔓 Abrir Caixa</option>
                            <option value="FECHAMENTO">🔒 Fechar Caixa</option>
                            <option value="SANGRIA">💸 Sangria (Retirada de Dinheiro)</option>
                            <option value="SUPRIMENTO">📥 Suprimento (Entrada de Troco)</option>
                        </select>
                    </div>
                    
                    <div>
                        <label>Operador:</label>
                        <select id="modal_caixa_operador" class="erp-input"><option value="">Carregando...</option></select>
                    </div>
                    
                    <div>
                        <label>Nº do Caixa:</label>
                        <select id="modal_caixa_numero" class="erp-input"><option value="">Carregando...</option></select>
                    </div>
                    
                    <div class="col-span-2">
                        <label>Turno:</label>
                        <select id="modal_caixa_turno" class="erp-input"><option value="">Carregando...</option></select>
                    </div>
                    
                    <div class="col-span-2 mt-10">
                        <label>Valor (R$): <small class="text-muted">(Necessário para Saldo Inicial, Sangria ou Suprimento)</small></label>
                        <input type="number" id="modal_caixa_valor" class="erp-input text-success font-bold text-lg" value="0.00" step="0.01">
                    </div>
                </div>

                <div class="d-flex justify-end gap-10 mt-20 pt-15 border-top border-muted">
                    <button type="button" class="btn-neon btn-neon-danger" onclick="fecharModalCaixa()">Cancelar</button>
                    <button type="button" class="btn-neon btn-neon-success" onclick="salvarFuncaoCaixa()">✔️ Confirmar Operação</button>
                </div>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }
}

window.abrirModalCaixa = async function() {
    garantirModalCaixa();
    const modal = document.getElementById('modal_caixa');
    if (modal) modal.style.display = 'flex';
    
    // 1. CARREGAR APENAS OPERADORES CADASTRADOS NO ERP
    try {
        const selectOperador = document.getElementById('modal_caixa_operador');
        selectOperador.innerHTML = '<option value="">Buscando Operadores...</option>';
        
        const resOp = await fetch('/api/cadastros/funcionarios');
        if (resOp.ok) {
            const dataOp = await resOp.json();
            if (dataOp && dataOp.length > 0) {
                selectOperador.innerHTML = '<option value="">-- Selecione --</option>';
                dataOp.forEach(op => {
                    const nome = obterValorInteligente(op, ['nome', 'funcionario', 'usuario', 'login']);
                    if (nome) selectOperador.innerHTML += `<option value="${nome}">${nome}</option>`;
                });
            } else {
                selectOperador.innerHTML = '<option value="">(Nenhum funcionário cadastrado)</option>';
            }
        } else {
            selectOperador.innerHTML = '<option value="">(Erro ao carregar)</option>';
        }
    } catch (error) { 
        console.log("Erro operadores:", error); 
        document.getElementById('modal_caixa_operador').innerHTML = '<option value="">(Erro na conexão)</option>';
    }

    // 2. CARREGAR APENAS CAIXAS CADASTRADOS NO ERP
    try {
        const selectCaixa = document.getElementById('modal_caixa_numero');
        selectCaixa.innerHTML = '<option value="">Buscando Caixas...</option>';
        
        // Busca na rota correta: caixas_pdv
        const resCx = await fetch('/api/cadastros/caixas_pdv');
        if (resCx.ok) {
            const dataCx = await resCx.json();
            if (dataCx && dataCx.length > 0) {
                selectCaixa.innerHTML = '<option value="">-- Selecione --</option>';
                dataCx.forEach(cx => {
                    const nome = obterValorInteligente(cx, ['nome', 'descricao', 'caixa', 'numero', 'identificacao', 'conta']);
                    if (nome) selectCaixa.innerHTML += `<option value="${nome}">${nome}</option>`;
                });
            } else {
                selectCaixa.innerHTML = '<option value="">(Nenhum caixa cadastrado)</option>';
            }
        } else {
            selectCaixa.innerHTML = '<option value="">(Erro ao carregar)</option>';
        }
    } catch (error) { 
        console.log("Erro caixas:", error); 
        document.getElementById('modal_caixa_numero').innerHTML = '<option value="">(Erro na conexão)</option>';
    }

    // 3. CARREGAR APENAS TURNOS CADASTRADOS NO ERP
    try {
        const selectTurno = document.getElementById('modal_caixa_turno');
        selectTurno.innerHTML = '<option value="">Buscando Turnos...</option>';
        
        const resTu = await fetch('/api/cadastros/turnos');
        if (resTu.ok) {
            const dataTu = await resTu.json();
            if (dataTu && dataTu.length > 0) {
                selectTurno.innerHTML = '<option value="">-- Selecione --</option>';
                dataTu.forEach(tu => {
                    const nome = obterValorInteligente(tu, ['nome', 'descricao', 'turno', 'periodo']);
                    const inicio = obterValorInteligente(tu, ['hora_inicio', 'inicio', 'abertura', 'hr_inicio']);
                    const fim = obterValorInteligente(tu, ['hora_fim', 'fim', 'fechamento', 'hr_fim']);
                    
                    let label = nome || 'Turno Indefinido';
                    if (inicio && fim) label += ` (${inicio} às ${fim})`;
                    
                    if (nome) selectTurno.innerHTML += `<option value="${nome}">${label}</option>`;
                });
            } else {
                selectTurno.innerHTML = '<option value="">(Nenhum turno cadastrado)</option>';
            }
        } else {
            selectTurno.innerHTML = '<option value="">(Erro ao carregar)</option>';
        }
    } catch (error) { 
        console.log("Erro turnos:", error); 
        document.getElementById('modal_caixa_turno').innerHTML = '<option value="">(Erro na conexão)</option>';
    }
}

window.fecharModalCaixa = function() {
    const modal = document.getElementById('modal_caixa');
    if (modal) modal.style.display = 'none';
    
    const inputValor = document.getElementById('modal_caixa_valor');
    if (inputValor) inputValor.value = '0.00';
}

window.salvarFuncaoCaixa = function() {
    const operacao = document.getElementById('modal_caixa_operacao').value;
    const operador = document.getElementById('modal_caixa_operador').value;
    const caixa = document.getElementById('modal_caixa_numero').value;
    const turno = document.getElementById('modal_caixa_turno').value;
    const valor = parseFloat(document.getElementById('modal_caixa_valor').value) || 0;

    // Validação estrita das dropdowns (Impede abrir caixa se o ERP estiver vazio)
    if (!operador || !caixa || !turno) {
        alert("⚠️ ATENÇÃO: É obrigatório selecionar Operador, Caixa e Turno para realizar operações!\n\nSe os campos estiverem vazios, acesse o módulo de Cadastros do ERP e cadastre essas informações nas suas respectivas tabelas.");
        return;
    }

    if (operacao === 'ABERTURA') {
        statusCaixa = 'ABERTO';
        
        const lblOp = document.getElementById('lbl_operador');
        const lblCx = document.getElementById('lbl_caixa_numero');
        const lblStatus = document.getElementById('lbl_status_caixa');
        
        if (lblOp) { lblOp.innerText = operador; lblOp.className = "text-info"; }
        if (lblCx) { lblCx.innerText = caixa; lblCx.className = "text-info"; }
        if (lblStatus) { lblStatus.innerText = "ABERTO"; lblStatus.className = "text-success font-bold"; }
        
        alert(`Caixa Aberto com sucesso!\nOperador: ${operador}\nTurno: ${turno}\nSaldo Inicial: R$ ${valor.toFixed(2)}`);
    } 
    else if (operacao === 'FECHAMENTO') {
        statusCaixa = 'FECHADO';
        
        const lblOp = document.getElementById('lbl_operador');
        const lblCx = document.getElementById('lbl_caixa_numero');
        const lblStatus = document.getElementById('lbl_status_caixa');
        
        if (lblOp) { lblOp.innerText = "Indefinido"; lblOp.className = "text-danger"; }
        if (lblCx) { lblCx.innerText = "Indefinido"; lblCx.className = "text-danger"; }
        if (lblStatus) { lblStatus.innerText = "FECHADO"; lblStatus.className = "text-danger font-bold"; }
        
        alert(`Caixa Fechado com sucesso!\nOperador: ${operador}\nTurno: ${turno}`);
    } 
    else if (operacao === 'SANGRIA') {
        alert(`Sangria (Retirada) Registrada!\nValor: R$ ${valor.toFixed(2)}\nCaixa: ${caixa}`);
    } 
    else if (operacao === 'SUPRIMENTO') {
        alert(`Suprimento (Entrada) Registrado!\nValor: R$ ${valor.toFixed(2)}\nCaixa: ${caixa}`);
    }

    fecharModalCaixa();
}

// ==========================================
// BUSCA DOS DROPDOWNS DIRETAMENTE DAS TABELAS ERP
// ==========================================
window.carregarDropdownsERP = async function() {
    // Categorias
    try {
        const selectCat = document.getElementById('pdv_categoria');
        if (selectCat) {
            const resCat = await fetch('/api/cadastros/categorias');
            if (resCat.ok) {
                const dataCat = await resCat.json();
                if (dataCat && dataCat.length > 0) {
                    selectCat.innerHTML = '<option value="">Todas Categorias</option>';
                    dataCat.forEach(cat => {
                        const nomeCat = obterValorInteligente(cat, ['nome', 'descricao', 'categoria']);
                        if (nomeCat) selectCat.innerHTML += `<option value="${nomeCat}">${nomeCat}</option>`;
                    });
                } else {
                    selectCat.innerHTML = '<option value="">(Nenhuma categoria cadastrada)</option>';
                }
            }
        }
    } catch (error) {}

    // Formas de Pagamento
    try {
        const selectPg = document.getElementById('forma_pagamento');
        if (selectPg) {
            const resPg = await fetch('/api/cadastros/formas_pagamento');
            if (resPg.ok) {
                const dataPg = await resPg.json();
                if (dataPg && dataPg.length > 0) {
                    selectPg.innerHTML = '<option value="">-- Selecione a Forma de Pgto --</option>';
                    dataPg.forEach(forma => {
                        const nomePgto = obterValorInteligente(forma, ['nome', 'descricao', 'forma', 'condicao', 'pagamento']);
                        if (nomePgto) selectPg.innerHTML += `<option value="${nomePgto}">${nomePgto}</option>`;
                    });
                } else {
                    selectPg.innerHTML = '<option value="">(Nenhuma forma cadastrada no ERP)</option>';
                }
            } else {
                selectPg.innerHTML = '<option value="">(Erro ao carregar formas de pgto)</option>';
            }
        }
    } catch (error) {}
}

// ==========================================
// BUSCA E RENDERIZAÇÃO DE PRODUTOS
// ==========================================
window.carregarProdutos = async function() {
    try {
        let response = await fetch('/api/cadastros/produtos');
        if (!response.ok) response = await fetch('/api/pdv/produtos');
        if (!response.ok) throw new Error("Falha ao carregar produtos do ERP");
        
        const produtosBrutos = await response.json();
        
        if(produtosBrutos.length === 0) {
            const grid = document.getElementById('grid_produtos');
            if(grid) grid.innerHTML = `<div class="text-warning text-center w-full mt-20">Nenhum produto cadastrado no ERP. <br><small>Cadastre produtos em Cadastros > Produtos para exibir aqui.</small></div>`;
            return;
        }

        produtosPDV = produtosBrutos.map(p => {
            const idBruto = obterValorInteligente(p, ['id', 'codigo', 'cod', 'código']);
            const nomeBruto = obterValorInteligente(p, ['nome', 'descricao', 'produto', 'descrição']);
            const valorBruto = obterValorInteligente(p, ['vlr_varejo', 'valor_varejo', 'varejo', 'vlr_venda', 'preco_venda', 'preco', 'valor', 'venda', 'preço', 'unitario']);
            const catBruto = obterValorInteligente(p, ['categoria', 'grupo', 'tipo', 'secao', 'seção']);
            const codBarrasBruto = obterValorInteligente(p, ['codigo_barras', 'cod_barras', 'ean', 'gtin', 'barras', 'codigo_barra']);

            let isAtivo = true;
            const statusBruto = obterValorInteligente(p, ['ativo', 'status', 'situacao', 'disponivel']);
            if (statusBruto !== null) {
                const s = String(statusBruto).toLowerCase().trim();
                if (s === '0' || s === 'nao' || s === 'não' || s === 'false' || s === 'inativo') {
                    isAtivo = false;
                }
            }

            return {
                ...p,
                id: idBruto || Math.floor(Math.random() * 1000000), 
                codigo_barras: codBarrasBruto || '', // Adicionado para Scanner Automático
                nome: nomeBruto || 'Produto Sem Nome',
                preco_venda: parsePreco(valorBruto),
                categoria: catBruto || 'Geral',
                _ativo: isAtivo
            };
        }).filter(p => p._ativo);
        
        renderizarProdutos(produtosPDV);
    } catch (error) {
        console.error("Erro ao buscar produtos do ERP", error);
        const grid = document.getElementById('grid_produtos');
        if(grid) grid.innerHTML = `<div class="text-danger text-center w-full mt-20">Erro ao comunicar com a API do ERP. Verifique o backend.</div>`;
    }
}

window.renderizarProdutos = function(lista) {
    const grid = document.getElementById('grid_produtos');
    if (!grid) return;
    grid.innerHTML = '';
    
    if (lista.length === 0) {
        grid.innerHTML = `<div class="text-muted text-center w-full mt-20">Nenhum produto corresponde à busca.</div>`;
        return;
    }
    
    lista.forEach(prod => {
        const precoFmt = prod.preco_venda.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
        
        const card = document.createElement('div');
        card.className = 'produto-card';
        card.onclick = () => adicionarAoCarrinho(prod);
        card.innerHTML = `
            <div class="text-xs text-muted">${prod.categoria}</div>
            <div class="font-bold mt-5 mb-5" style="font-size: 0.9rem">${prod.nome}</div>
            <div class="produto-preco">${precoFmt}</div>
        `;
        grid.appendChild(card);
    });
}

window.filtrarProdutos = function() {
    const buscaEl = document.getElementById('pdv_busca');
    const catEl = document.getElementById('pdv_categoria');
    
    const termo = buscaEl ? buscaEl.value.toLowerCase() : '';
    const categoria = catEl ? catEl.value : '';
    
    const filtrados = produtosPDV.filter(p => {
        const nomeProd = p.nome.toLowerCase();
        const codProd = String(p.id).toLowerCase();
        const barrasProd = String(p.codigo_barras).toLowerCase();
        
        const matchNomeOuCodigo = nomeProd.includes(termo) || codProd === termo || barrasProd === termo;
        const matchCat = categoria === "" || p.categoria === categoria;
        
        return matchNomeOuCodigo && matchCat;
    });
    
    renderizarProdutos(filtrados);
}

// ==========================================
// GERENCIAMENTO DO CARRINHO
// ==========================================
window.adicionarAoCarrinho = function(produto) {
    if (statusCaixa !== 'ABERTO') {
        alert("🔒 O Caixa está fechado! Abra o caixa antes de passar produtos.");
        return;
    }

    const itemExistente = carrinho.find(item => item.id === produto.id);
    
    if (itemExistente) {
        itemExistente.quantidade++;
        itemExistente.subtotal = itemExistente.quantidade * itemExistente.preco_unitario;
    } else {
        carrinho.push({
            id: produto.id,
            nome: produto.nome,
            quantidade: 1,
            preco_unitario: produto.preco_venda,
            subtotal: produto.preco_venda
        });
    }
    atualizarCarrinho();
}

window.alterarQuantidade = function(index, delta) {
    if (carrinho[index]) {
        carrinho[index].quantidade += delta;
        if (carrinho[index].quantidade <= 0) {
            removerItem(index);
        } else {
            carrinho[index].subtotal = carrinho[index].quantidade * carrinho[index].preco_unitario;
            atualizarCarrinho();
        }
    }
}

window.removerItem = function(index) {
    carrinho.splice(index, 1);
    atualizarCarrinho();
}

window.limparCarrinho = function() {
    if(carrinho.length === 0) return;
    if(confirm("Deseja realmente cancelar a venda atual?")) {
        carrinho = [];
        pagamentos = [];
        totais.desconto = 0;
        atualizarCarrinho();
    }
}

window.aplicarDesconto = function() {
    const valorDesconto = prompt("Informe o valor de desconto em R$:");
    if (valorDesconto !== null) {
        const desc = parseFloat(valorDesconto.replace(',', '.'));
        if (!isNaN(desc) && desc >= 0) {
            totais.desconto = desc;
            atualizarCarrinho();
        } else {
            alert("Valor de desconto inválido.");
        }
    }
}

window.atualizarCarrinho = function() {
    const lista = document.getElementById('lista_carrinho');
    if (!lista) return;
    lista.innerHTML = '';
    
    totais.subtotal = 0;
    
    if (carrinho.length === 0) {
        lista.innerHTML = '<div class="text-center text-muted mt-20">Carrinho vazio</div>';
        totais.desconto = 0;
        pagamentos = []; // Limpa os pagamentos ao esvaziar carrinho
    } else {
        carrinho.forEach((item, index) => {
            totais.subtotal += item.subtotal;
            
            const itemHTML = `
                <div class="carrinho-item">
                    <div style="flex-grow: 1;">
                        <div class="font-bold">${item.nome}</div>
                        <div class="text-xs text-muted d-flex align-center gap-5 mt-5">
                            <button class="btn-neon text-xs p-0" style="width: 20px; height: 20px;" onclick="alterarQuantidade(${index}, -1)">-</button>
                            <span>${item.quantidade}x ${item.preco_unitario.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})}</span>
                            <button class="btn-neon text-xs p-0" style="width: 20px; height: 20px;" onclick="alterarQuantidade(${index}, 1)">+</button>
                        </div>
                    </div>
                    <div class="font-bold mr-10">${item.subtotal.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})}</div>
                    <div class="carrinho-item-acoes">
                        <button onclick="removerItem(${index})" title="Remover Produto">✖</button>
                    </div>
                </div>
            `;
            lista.insertAdjacentHTML('beforeend', itemHTML);
        });
    }
    
    if (totais.desconto > totais.subtotal) totais.desconto = totais.subtotal;
    totais.total = totais.subtotal - totais.desconto;
    
    // Cálculo dos Múltiplos Pagamentos e Troco
    totais.pago = pagamentos.reduce((acc, p) => acc + p.valor, 0);
    totais.troco = Math.max(0, totais.pago - totais.total);
    
    // Atualiza o input sugerindo o valor restante a pagar
    const falta = Math.max(0, totais.total - totais.pago);
    const inputPgto = document.getElementById('valor_pagamento');
    if (inputPgto && falta > 0) {
        inputPgto.value = falta.toFixed(2);
    } else if (inputPgto) {
        inputPgto.value = '';
    }
    
    const elSubtotal = document.getElementById('lbl_subtotal');
    const elDesconto = document.getElementById('lbl_desconto');
    const elTotal = document.getElementById('lbl_total');
    const elPago = document.getElementById('lbl_pago');
    const elTroco = document.getElementById('lbl_troco');
    
    if (elSubtotal) elSubtotal.innerText = totais.subtotal.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
    if (elDesconto) elDesconto.innerText = totais.desconto.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
    if (elTotal) elTotal.innerText = totais.total.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
    if (elPago) elPago.innerText = totais.pago.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
    if (elTroco) elTroco.innerText = totais.troco.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
    
    renderizarPagamentos();
}

// Lógica de Pagamentos Múltiplos
window.adicionarPagamento = function() {
    const formaEl = document.getElementById('forma_pagamento');
    const valorEl = document.getElementById('valor_pagamento');
    
    if (!formaEl || !valorEl) return;
    
    const forma = formaEl.value;
    const valor = parseFloat(valorEl.value);
    
    if (!forma) {
        alert("Selecione uma forma de pagamento cadastrada.");
        return;
    }
    
    if (isNaN(valor) || valor <= 0) {
        alert("Informe um valor numérico maior que zero para o pagamento.");
        return;
    }
    
    pagamentos.push({ forma: forma, valor: valor });
    atualizarCarrinho();
}

window.removerPagamento = function(index) {
    pagamentos.splice(index, 1);
    atualizarCarrinho();
}

window.renderizarPagamentos = function() {
    const lista = document.getElementById('lista_pagamentos');
    if (!lista) return;
    
    lista.innerHTML = '';
    pagamentos.forEach((p, index) => {
        lista.innerHTML += `
            <div class="d-flex justify-between align-center border-bottom border-muted py-5 text-muted">
                <span>${p.forma}</span>
                <span>
                    ${p.valor.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})}
                    <button class="btn-neon text-xs p-0 text-danger ml-5" style="border:none" onclick="removerPagamento(${index})" title="Remover Pagamento">✖</button>
                </span>
            </div>
        `;
    });
}

// ==========================================
// FINALIZAÇÃO DE VENDA E INTEGRAÇÃO
// ==========================================
window.finalizarVenda = async function() {
    if (statusCaixa !== 'ABERTO') {
        alert("🔒 O Caixa está fechado!\n\nPor favor, abra o caixa no menu 'Funções do Caixa' antes de realizar vendas.");
        return;
    }

    if (carrinho.length === 0) {
        alert("O carrinho está vazio!");
        return;
    }
    
    if (pagamentos.length === 0) {
        alert("Atenção: Adicione pelo menos um pagamento usando o botão '➕' antes de finalizar a venda.");
        return;
    }
    
    if (totais.pago < totais.total) {
        alert(`O valor pago (R$ ${totais.pago.toFixed(2)}) é menor que o total da venda (R$ ${totais.total.toFixed(2)}). Adicione o pagamento restante.`);
        return;
    }
    
    const lblOperador = document.getElementById('lbl_operador');
    const lblCaixa = document.getElementById('lbl_caixa_numero');
    
    const formaPagamentoPrincipal = pagamentos[0].forma; // O ERP antigo usa a primeira forma como base principal
    
    const payload = {
        subtotal: totais.subtotal,
        desconto: totais.desconto,
        total: totais.total,
        valor_pago: totais.pago,
        troco: totais.troco,
        forma_pagamento: formaPagamentoPrincipal,
        multiplos_pagamentos: pagamentos, // Array complexo para contas a receber flexíveis
        operador: lblOperador ? lblOperador.innerText : 'Indefinido',
        caixa: lblCaixa ? lblCaixa.innerText : 'Indefinido',
        itens: carrinho
    };
    
    try {
        const response = await fetch('/api/pdv/finalizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        
        if (result.sucesso) {
            alert(`Venda finalizada com sucesso! (ID: ${result.venda_id})\nEnviado automaticamente para o Financeiro (Contas a Receber).`);
            carrinho = [];
            pagamentos = [];
            totais.desconto = 0;
            atualizarCarrinho();
        } else {
            alert("Erro ao finalizar venda: " + (result.erro || "Verifique o backend."));
        }
    } catch (error) {
        console.error("Erro na requisição:", error);
        alert("Erro de conexão ao finalizar a venda. Assegure-se de que a rota de integração (/api/pdv/finalizar) e as tabelas iniciadas com er_ estão disponíveis.");
    }
}

// ==========================================
// LÓGICA DO SCANNER DE CÓDIGO DE BARRAS (CÂMERA)
// ==========================================

window.garantirScannerUI = function() {
    // 1. Injeta a biblioteca do leitor de código de barras no cabeçalho se não existir
    if (!document.getElementById('script_html5_qrcode')) {
        const script = document.createElement('script');
        script.id = 'script_html5_qrcode';
        script.src = 'https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js';
        document.head.appendChild(script);
    }

    // 2. Adiciona o botão da câmera ao lado da barra de busca
    const searchBar = document.querySelector('.pdv-search-bar');
    if (searchBar && !document.getElementById('btn_abrir_scanner')) {
        const btnScanner = document.createElement('button');
        btnScanner.id = 'btn_abrir_scanner';
        btnScanner.className = 'btn-neon btn-neon-info';
        btnScanner.innerHTML = '📷 Ler Código';
        btnScanner.onclick = abrirScanner;
        btnScanner.style.flexShrink = '0';
        searchBar.appendChild(btnScanner);
    }

    // 3. Injeta a tela (modal) invisível para o vídeo do scanner
    if (!document.getElementById('modal_scanner')) {
        const modalHTML = `
        <div id="modal_scanner" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 10001; align-items: center; justify-content: center; backdrop-filter: blur(5px);">
            <div class="form-panel" style="width: 90%; max-width: 500px; background: #111827; border: 1px solid #00ffcc; border-radius: 8px; padding: 20px; text-align: center; box-shadow: 0 0 20px rgba(0,255,204,0.3);">
                <h2 class="text-warning mb-10">📷 Escanear Produto</h2>
                <p class="text-muted text-sm mb-20">Aponte a câmera traseira do celular para o código de barras.</p>
                
                <div id="leitor_qrcode" style="width: 100%; min-height: 250px; background: #000; border-radius: 8px; overflow: hidden; margin-bottom: 20px;"></div>
                
                <button type="button" class="btn-neon btn-neon-danger w-full mt-10" onclick="fecharScanner()">❌ Cancelar Câmera</button>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }
}

window.abrirScanner = function() {
    // Se a biblioteca ainda não carregou da internet, aguarda 500ms e tenta de novo
    if (typeof Html5Qrcode === 'undefined') {
        console.log("Aguardando carregamento da biblioteca de câmera...");
        setTimeout(window.abrirScanner, 500);
        return;
    }

    document.getElementById('modal_scanner').style.display = 'flex';
    
    if (!html5QrCode) {
        html5QrCode = new Html5Qrcode("leitor_qrcode");
    }
    
    const config = { fps: 10, qrbox: { width: 250, height: 250 } };
    
    // Função executada quando um código é identificado com sucesso!
    const qrCodeSuccessCallback = (decodedText, decodedResult) => {
        playBeep();
        fecharScanner();
        processarCodigoLido(decodedText);
    };

    html5QrCode.start({ facingMode: "environment" }, config, qrCodeSuccessCallback)
    .catch((err) => {
        console.error("Erro ao iniciar câmera", err);
        alert("Não foi possível acessar a câmera. Verifique se o seu dispositivo tem câmera e se as permissões do navegador foram aceitas.");
        fecharScanner();
    });
}

window.fecharScanner = function() {
    document.getElementById('modal_scanner').style.display = 'none';
    if (html5QrCode && html5QrCode.isScanning) {
        html5QrCode.stop().then(() => {
            html5QrCode.clear();
        }).catch(err => console.log(err));
    }
}

window.processarCodigoLido = function(codigoLido) {
    const codigoFormatado = String(codigoLido).trim().toLowerCase();
    
    // Procura o produto pelo ID ou Código de Barras (EAN, GTIN, etc.) extraído do Banco
    const produtoEncontrado = produtosPDV.find(p => {
        const idProduto = String(p.id).toLowerCase();
        const codBarras = String(p.codigo_barras || '').toLowerCase();
        return idProduto === codigoFormatado || codBarras === codigoFormatado;
    });

    if (produtoEncontrado) {
        adicionarAoCarrinho(produtoEncontrado);
        
        // Feedback visual na barra de pesquisa
        const searchEl = document.getElementById('pdv_busca');
        if(searchEl) {
            searchEl.value = `Adicionado: ${produtoEncontrado.nome}`;
            setTimeout(() => { searchEl.value = ''; filtrarProdutos(); }, 2000);
        }
    } else {
        alert(`Nenhum produto cadastrado com o código: ${codigoLido}`);
    }
}