const todosProdutos = JSON.parse(document.getElementById('todos-produtos-data').textContent);
const todosAdicionais = JSON.parse(document.getElementById('todos-adicionais-data').textContent || '[]');
const mapaEmojis = JSON.parse(document.getElementById('mapa-emojis-data').textContent || '{}');

function inicializar() {
    const cats = new Set();
    todosProdutos.forEach(p => { if(p.label_categoria) cats.add(p.label_categoria + "|" + p.categoria); });
    const catsArray = Array.from(cats).sort();
    const selectors = ['filterEstoqueCat', 'filterMaisPedidosCat', 'filterDestCat', 'filterPromoCat', 'filterApelidoCat'];
    
    selectors.forEach(id => {
        const sel = document.getElementById(id);
        if(sel) {
            sel.innerHTML = '<option value="">-- Selecione --</option>';
            catsArray.forEach(c => { 
                const [l, v] = c.split('|'); 
                const opt = document.createElement('option'); 
                opt.value = v; 
                const emoji = mapaEmojis[v] || '📦';
                opt.innerText = `${emoji} ${l}`; 
                sel.appendChild(opt); 
            });
            if(id === 'filterApelidoCat') { 
                const opt = document.createElement('option'); opt.value = 'adicional'; opt.innerText = '➕ Adicionais/Opções'; sel.appendChild(opt); 
            }
        }
    });
    
    // --- CARREGAMENTO INICIAL DAS LISTAS DO PAINEL ---
    filtrarEstoque();
    loadConfigCadastro(); 
    
    // As duas linhas abaixo foram adicionadas para carregar automaticamente ao abrir a página
    carregarMensagensAgendadas();
    carregarModosEnvio();

    // --- SISTEMA DE ACORDEÃO PARA CARDS NO MOBILE ---
    if (window.innerWidth <= 768) {
        document.querySelectorAll('.config-card').forEach((card, index) => {
            // Deixa todos os cards fechados por padrão
            card.classList.add('collapsed');
            
            const titulo = card.querySelector('h2');
            if (titulo) {
                // Adiciona o evento de clique para abrir/fechar
                titulo.addEventListener('click', () => {
                    card.classList.toggle('collapsed');
                });
            }
        });
    }
}

const el = document.getElementById('listaCategorias');
if (el) { Sortable.create(el, { handle: '.drag-handle', animation: 150, ghostClass: 'sortable-ghost', onEnd: function (evt) { salvarNovaOrdem(); } }); }
async function salvarNovaOrdem() {
    const itens = document.querySelectorAll('#listaCategorias .cat-item'); const novaOrdem = [];
    itens.forEach((item, index) => { novaOrdem.push({ id: item.getAttribute('data-id'), ordem: index + 1 }); });
    try { await fetch('/api/categorias/reordenar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ordem: novaOrdem }) }); } catch(e) { console.error(e); }
}

function atualizarStatusCategoria(id, ativa) { apiCall(`/api/categorias/${id}`, 'PUT', { ativa: ativa }); }
async function apiCall(url, method, body) { 
    try { 
        const res = await fetch(url, { method: method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) }); 
        const data = await res.json(); 
        if(data.ok) window.location.reload(); 
        else alert("Erro: " + data.erro); 
    } catch(e) { alert("Erro de conexão"); } 
}

function renomearCategoria(id, nome, emoji) { if(nome) apiCall(`/api/categorias/${id}`, 'PUT', {nome, emoji}); }
function adicionarCategoria() { const nome = document.getElementById('novaCatNome').value; const emoji = document.getElementById('novaCatEmoji').value; if(nome) apiCall('/api/categorias', 'POST', {nome, emoji}); }
function excluirCategoria(id) { if(confirm("Tem certeza?")) apiCall(`/api/categorias/${id}`, 'DELETE', {}); }

// --- APPS DE DELIVERY (PLATAFORMAS) ---
function adicionarPlataforma() { const nome = document.getElementById('newPlatNome').value; if(nome) apiCall('/api/plataformas', 'POST', {nome: nome}); }
function salvarPlataforma(id) { const nome = document.getElementById('plat_nome_' + id).value; if(nome) fetch(`/api/plataformas/${id}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nome: nome}) }); }
function removerPlataforma(id) { if(confirm("Remover este app?")) apiCall(`/api/plataformas/${id}`, 'DELETE', {}); }

// --- FORMAS DE PAGAMENTO ---
function abrirModalFormaPagamento(fp = null) {
    document.getElementById('editFpId').value = fp ? fp.id : '';
    document.getElementById('modalFpNome').value = fp ? fp.nome : '';
    document.getElementById('modalFpWpp').checked = fp ? fp.disponivel_wpp : true;
    document.getElementById('modalFpDet').checked = fp ? fp.pede_detalhe : false;
    document.getElementById('modalFpPergunta').value = fp ? (fp.pergunta_detalhe || '') : '';
    
    toggleFpPergunta();
    
    document.getElementById('modalFormaPagamentoTitulo').innerText = fp ? '✏️ Editar Pagamento' : '➕ Nova Forma de Pagamento';
    document.getElementById('modalFormaPagamento').style.display = 'flex';
}

function fecharModalFormaPagamento() {
    document.getElementById('modalFormaPagamento').style.display = 'none';
}

function toggleFpPergunta() {
    document.getElementById('boxFpPergunta').style.display = document.getElementById('modalFpDet').checked ? 'block' : 'none';
}

async function salvarFormaPagamentoModal() { 
    const id = document.getElementById('editFpId').value;
    const data = {
        nome: document.getElementById('modalFpNome').value,
        disponivel_wpp: document.getElementById('modalFpWpp').checked,
        pede_detalhe: document.getElementById('modalFpDet').checked,
        pergunta_detalhe: document.getElementById('modalFpPergunta').value
    };
    
    if(!data.nome) return alert("Digite o nome da forma de pagamento!");
    
    const url = id ? `/api/formas_pagamento/${id}` : '/api/formas_pagamento';
    const method = id ? 'PUT' : 'POST';
    
    try {
        const res = await fetch(url, { method: method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
        if(res.ok) window.location.reload(); // Recarrega para Jinja refazer a lista
        else alert("Erro ao salvar pagamento.");
    } catch(e) { alert("Erro de conexão"); }
}

function removerFormaPagamento(id) { 
    if(confirm("Remover esta forma de pagamento?")) apiCall(`/api/formas_pagamento/${id}`, 'DELETE', {}); 
}

// --- RESERVAS ---
function adicionarReserva() {
    const data = document.getElementById('resData').value; const nome = document.getElementById('resNome').value;
    if(data && nome) apiCall('/api/reservas', 'POST', { data, horario: document.getElementById('resHora').value, pessoas: document.getElementById('resPessoas').value, nome, telefone: document.getElementById('resTel').value, obs: document.getElementById('resObs').value });
}
function removerReserva(id) { if(confirm("Cancelar esta reserva?")) apiCall(`/api/reservas/${id}`, 'DELETE', {}); }
function verReserva(data, hora, pessoas, nome, tel, obs) {
    document.getElementById('detResData').innerText = data; document.getElementById('detResHora').innerText = hora; document.getElementById('detResPessoas').innerText = pessoas; document.getElementById('detResNome').innerText = nome; document.getElementById('detResTel').innerText = tel; document.getElementById('detResObs').innerText = obs || 'Nenhuma observação.'; document.getElementById('modalReserva').style.display = 'flex';
}

// --- BAIRROS ---
function adicionarBairro() { const nome = document.getElementById('newBairroNome').value; const taxa = document.getElementById('newBairroTaxa').value; if(nome) apiCall('/api/bairros', 'POST', {nome, taxa}); }
function editarBairro(id, nome, taxa) { fetch(`/api/bairros/${id}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nome, taxa}) }); }
function removerBairro(id) { if(confirm("Remover bairro?")) apiCall(`/api/bairros/${id}`, 'DELETE', {}); }

// --- ESTOQUE ---
// 1. Filtrar Estoque
function filtrarEstoque() {
    const cat = document.getElementById('filterEstoqueCat').value; 
    const div = document.getElementById('listaEstoque'); 
    div.innerHTML = '';
    let itens = cat ? todosProdutos.filter(p => p.categoria === cat) : todosProdutos.filter(p => p.disponivel == 0);
    if(!itens.length) { div.innerHTML = '<p class="empty-table-msg">Nenhum item indisponível ou categoria vazia.</p>'; return; }
    itens.sort((a,b) => a.nome.localeCompare(b.nome));
    itens.forEach(p => {
        const d = document.createElement('div'); 
        d.className = 'item-card justify-between'; 
        const styleClass = p.disponivel ? 'item-estoque-on' : 'item-estoque-off';
        d.innerHTML = `<div class="${styleClass}">${p.nome}</div><div class="toggle-item m-0"><input type="checkbox" ${p.disponivel?'checked':''} onchange="toggleEst('${p.categoria}','${p.id}',this.checked)"></div>`;
        div.appendChild(d);
    });
}

// 2. Carregar Modos Envio
async function carregarModosEnvio() {
    const res = await fetch('/api/modos_envio');
    const dados = await res.json();
    const tbody = document.getElementById('tbody-modos-envio');
    tbody.innerHTML = '';
    dados.forEach(m => {
        let regras = [];
        if(m.pede_endereco) regras.push("📍 Pede Endereço");
        if(m.pede_horario) regras.push("🕒 Faz Pergunta");
        
        tbody.innerHTML += `
            <tr style="border-bottom: 1px solid #333;">
                <td class="p-10 text-white font-bold">${m.nome}</td>
                <td class="modo-regras-text">${regras.join('<br>') || 'Nenhuma regra'}</td>
                <td><input type="checkbox" ${m.disponivel_wpp ? 'checked' : ''} onchange="toggleModoWpp(${m.id}, this.checked)" style="transform: scale(1.2);"></td>
                <td class="text-right">
                    <button class="btn-action-sm btn-action-edit" onclick='abrirModalModoEnvio(${JSON.stringify(m)})'>✏️</button>
                    <button class="btn-action-sm btn-action-del-red" onclick="deletarModoEnvio(${m.id})">🗑️</button>
                </td>
            </tr>
        `;
    });
}

// 3. Load Config Cadastro
async function loadConfigCadastro() {
    const res = await fetch('/api/config_cadastro');
    const campos = await res.json();
    const lista = document.getElementById('listaCamposCadastro');
    lista.innerHTML = '';

    const colunasFixas = ['nome', 'cpf', 'rua', 'numero_casa', 'bairro', 'ponto_referencia'];

    campos.forEach(c => {
        const item = document.createElement('div');
        item.className = 'item-card d-flex align-center justify-between'; 
        item.setAttribute('data-id', c.id);
        
        const isFixo = colunasFixas.includes(c.coluna);
        const btnDeletar = isFixo 
            ? '<span class="text-muted text-xs ml-10" title="Campo de Sistema">Fixo</span>' 
            : `<button type="button" class="btn-del ml-10" onclick="removerCampoCadastro(${c.id})">🗑️</button>`;

        const cJson = JSON.stringify(c).replace(/'/g, "&apos;").replace(/"/g, "&quot;");

        item.innerHTML = `
            <div class="d-flex align-center flex-1 gap-10">
                <span class="drag-handle ml-10 mr-10 text-lg" style="cursor: grab;" title="Arraste para reordenar">☰</span>
                <span class="font-bold text-white text-lg">${c.label} ${!c.ativo_wpp ? '<span class="text-muted text-xs">(Inativo)</span>' : ''}</span>
            </div>
            <div class="d-flex align-center gap-5">
                <button type="button" class="btn-action-sm btn-action-edit" onclick='abrirModalCampoCadastro(${cJson})' title="Editar">✏️</button>
                ${btnDeletar}
            </div>
        `;
        lista.appendChild(item);
    });

    Sortable.create(lista, { 
        handle: '.drag-handle', animation: 150, scroll: true, scrollSensitivity: 120, scrollSpeed: 25, forceFallback: true, fallbackOnBody: true,
        onEnd: async function() {
            const novaOrdem = Array.from(lista.children).map((el, i) => ({ id: el.dataset.id, ordem: i + 1 })).filter(item => item.id); 
            try { await fetch('/api/config_cadastro/reordenar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ordem: novaOrdem }) }); } 
            catch(e) { console.error("Erro na reordenação", e); }
        }
    });
}

// 4. Carregar Mensagens Agendadas
async function carregarMensagensAgendadas() {
    try {
        const res = await fetch('/api/mensagens_agendadas');
        const dados = await res.json();
        const lista = document.getElementById('listaMensagensAgendadas');
        lista.innerHTML = '';

        if(dados.length === 0) {
            lista.innerHTML = '<li class="empty-table-msg p-10">Nenhum disparo configurado.</li>';
            return;
        }

        dados.forEach(msg => {
            lista.innerHTML += `
                <li class="item-card msg-agenda-item" style="opacity: ${msg.ativo ? '1' : '0.6'};">
                    <div class="d-flex w-100 justify-between align-center">
                        <div class="flex-1">
                            <div class="msg-agenda-title">⏰ Todos os dias às ${msg.horario_envio}</div>
                            <div class="msg-agenda-desc">${msg.texto || '(Apenas Imagem)'}</div>
                            ${msg.imagem_base64 ? '<span class="msg-agenda-img-tag">🖼️ Com Imagem</span>' : ''}
                        </div>
                        
                        <div class="d-flex align-center gap-10">
                            <label class="d-flex align-center gap-5 text-muted text-sm" style="cursor:pointer;">
                                <input type="checkbox" ${msg.ativo ? 'checked' : ''} onchange="toggleDisparoAtivo(${msg.id}, this.checked)" style="transform: scale(1.2);">
                                ${msg.ativo ? 'Ativo' : 'Pausado'}
                            </label>
                            
                            <button type="button" class="btn-action-sm btn-action-edit" onclick='abrirModalDisparo(${JSON.stringify(msg)})' title="Editar">✏️</button>
                            <button type="button" class="btn-del" onclick="deletarMensagemAgendada(${msg.id})">🗑️</button>
                        </div>
                    </div>
                </li>
            `;
        });
    } catch (e) {
        console.error("Erro ao carregar disparos:", e);
    }
}
async function toggleEst(cat, id, atv) { await fetch('/api/produtos/toggle', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({categoria:cat, id, ativo:atv})}); }

// --- DESTAQUES E MAIS PEDIDOS ---
function filtrarProdutosMaisPedidos() { helperFilter('filterMaisPedidosCat', 'newMaisPedidoProd'); }
function adicionarMaisPedido() { const prod = document.getElementById('newMaisPedidoProd').value; if(prod) apiCall('/api/mais_pedidos', 'POST', {produto: prod}); }
function removerMaisPedido(id) { if(confirm("Remover?")) apiCall(`/api/mais_pedidos/${id}`, 'DELETE', {}); }
function atualizarProdutosStories() { helperFilter('filterDestCat', 'newDestProd'); }
function adicionarDestaque() { const prod = document.getElementById('newDestProd').value; if(prod) apiCall('/api/destaques', 'POST', {produto: prod}); }
function removerDestaque(id) { if(confirm("Remover?")) apiCall(`/api/destaques/${id}`, 'DELETE', {}); }

// --- PROMOÇÕES ---
function filtrarProdutosPromo() {
    const cat = document.getElementById('filterPromoCat').value; const sel = document.getElementById('newPromoProd'); sel.innerHTML = '<option value="">Item...</option>';
    if (cat) { const o = document.createElement('option'); o.value = `${cat}|0|Todos`; o.innerText = `🔥 TODOS`; sel.appendChild(o); }
    const filtrados = todosProdutos.filter(p => cat === "" || p.categoria === cat);
    filtrados.sort((a,b) => a.nome.localeCompare(b.nome));
    filtrados.forEach(p => { const o = document.createElement('option'); o.value = `${p.categoria}|${p.id}|${p.nome}`; o.innerText = p.nome; sel.appendChild(o); });
}
function adicionarPromo() { const prod = document.getElementById('newPromoProd').value; const desc = document.getElementById('newPromoDesc').value; if(prod && desc) apiCall('/api/promocoes', 'POST', {produto: prod, desconto: desc}); }
function removerPromo(id) { if(confirm("Remover?")) apiCall(`/api/promocoes/${id}`, 'DELETE', {}); }

// --- APELIDOS ---
function filtrarProdutosApelido() {
    const cat = document.getElementById('filterApelidoCat').value; const sel = document.getElementById('newApelidoProd'); sel.innerHTML = '<option value="">Alvo...</option>';
    const namesVistos = new Set(); 
    if (cat === 'adicional') { 
        todosAdicionais.sort((a,b) => a.nome.localeCompare(b.nome));
        todosAdicionais.forEach(ad => { if(!namesVistos.has(ad.nome)) { namesVistos.add(ad.nome); const o = document.createElement('option'); o.value = `adicional|${ad.id}|${ad.nome}`; o.innerText = ad.nome; sel.appendChild(o); } }); 
    } else { 
        if(cat) { const o = document.createElement('option'); o.value = `sistema_categoria|${cat}|CAT`; o.innerText = `📂 CATEGORIA`; sel.appendChild(o); }
        const filtrados = todosProdutos.filter(p => cat === "" || p.categoria === cat);
        filtrados.sort((a,b) => a.nome.localeCompare(b.nome));
        filtrados.forEach(p => { if(!namesVistos.has(p.nome)) { namesVistos.add(p.nome); const o = document.createElement('option'); o.value = `${p.categoria}|${p.id}|${p.nome}`; o.innerText = p.nome; sel.appendChild(o); } }); 
    }
}
function adicionarApelido() { const prod = document.getElementById('newApelidoProd').value; const apelido = document.getElementById('newApelidoNome').value; if(prod && apelido) apiCall('/api/apelidos', 'POST', {produto: prod, apelido}); }
function removerApelido(origin, id) { if(confirm("Remover?")) apiCall(`/api/apelidos/${origin}/${id}`, 'DELETE', {}); }

function helperFilter(idCat, idProd) {
    const cat = document.getElementById(idCat).value; const sel = document.getElementById(idProd); sel.innerHTML = '<option value="">Produto...</option>';
    const namesVistos = new Set();
    const filtrados = todosProdutos.filter(p => cat === "" || p.categoria === cat);
    filtrados.sort((a,b) => a.nome.localeCompare(b.nome));
    filtrados.forEach(p => { if(!namesVistos.has(p.nome)) { namesVistos.add(p.nome); const o = document.createElement('option'); o.value = `${p.categoria}|${p.id}|${p.nome}`; o.innerText = p.nome; sel.appendChild(o); } });
}

// --- CHAVES PIX ---
function adicionarPix() { const chave = document.getElementById('newPixChave').value; if(chave) apiCall('/api/pix', 'POST', { chave, titular: document.getElementById('newPixTitular').value, banco: document.getElementById('newPixBanco').value }); }
async function editarPix(id) { await fetch(`/api/pix/${id}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ chave: document.getElementById(`chave_${id}`).value, titular: document.getElementById(`titular_${id}`).value, banco: document.getElementById(`banco_${id}`).value }) }); }
async function selecionarPix(id) { await fetch('/api/pix/selecionar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) }); }
function removerPix(id) { if(confirm("Remover?")) apiCall(`/api/pix/${id}`, 'DELETE', {}); }

// --- MODOS DE ENVIO ---
async function carregarModosEnvio() {
    const res = await fetch('/api/modos_envio');
    const dados = await res.json();
    const tbody = document.getElementById('tbody-modos-envio');
    tbody.innerHTML = '';
    dados.forEach(m => {
        let regras = [];
        if(m.pede_endereco) regras.push("📍 Pede Endereço");
        if(m.pede_horario) regras.push("🕒 Faz Pergunta");
        
        tbody.innerHTML += `
            <tr style="border-bottom: 1px solid #333;">
                <td class="p-10 text-white font-bold">${m.nome}</td>
                <td class="modo-regras-text">${regras.join('<br>') || 'Nenhuma regra'}</td>
                <td><input type="checkbox" ${m.disponivel_wpp ? 'checked' : ''} onchange="toggleModoWpp(${m.id}, this.checked)" style="transform: scale(1.2);"></td>
                <td class="text-right">
                    <button class="btn-action-sm btn-action-edit" onclick='abrirModalModoEnvio(${JSON.stringify(m)})'>✏️</button>
                    <button class="btn-action-sm btn-action-del-red" onclick="deletarModoEnvio(${m.id})">🗑️</button>
                </td>
            </tr>
        `;
    });
}

function abrirModalModoEnvio(btn) {
    let m = null;
    if (btn instanceof HTMLElement) {
        m = JSON.parse(btn.getAttribute('data-modo'));
    } else {
        m = btn; 
    }

    if(m) {
        document.getElementById('modoEnvioId').value = m.id;
        document.getElementById('modoNome').value = m.nome;
        document.getElementById('modoPedeEndereco').checked = m.pede_endereco === 1;
        document.getElementById('modoPedeHorario').checked = m.pede_horario === 1;
        document.getElementById('modoPergunta').value = m.pergunta_horario || '';
        document.getElementById('boxPerguntaHorario').style.display = m.pede_horario === 1 ? 'block' : 'none';
        
        // Novos campos
        document.getElementById('modoPedePagamento').checked = m.pede_pagamento !== 0; // Padrão é true
        document.getElementById('modoPedeObsFinal').checked = m.pede_obs_final !== 0; // Padrão é true
        document.getElementById('modoPerguntaObsFinal').value = m.pergunta_obs_final || "📝 Alguma observação geral para o pedido? (ex: interfone estragado)\nDigite a observação ou 'não'.";
        document.getElementById('boxPerguntaObsFinal').style.display = m.pede_obs_final !== 0 ? 'block' : 'none';

    } else {
        document.getElementById('modoEnvioId').value = '';
        document.getElementById('modoNome').value = '';
        document.getElementById('modoPedeEndereco').checked = false;
        document.getElementById('modoPedeHorario').checked = false;
        document.getElementById('modoPergunta').value = '';
        document.getElementById('boxPerguntaHorario').style.display = 'none';
        
        // Padrões Novo
        document.getElementById('modoPedePagamento').checked = true;
        document.getElementById('modoPedeObsFinal').checked = true;
        document.getElementById('modoPerguntaObsFinal').value = "📝 Alguma observação geral para o pedido? (ex: interfone estragado)\nDigite a observação ou 'não'.";
        document.getElementById('boxPerguntaObsFinal').style.display = 'block';
    }
    document.getElementById('modalModoEnvio').style.display = 'flex';
}

async function salvarModoEnvio() {
    const id = document.getElementById('modoEnvioId').value;
    const data = {
        nome: document.getElementById('modoNome').value,
        pede_endereco: document.getElementById('modoPedeEndereco').checked ? 1 : 0,
        pede_horario: document.getElementById('modoPedeHorario').checked ? 1 : 0,
        pergunta_horario: document.getElementById('modoPergunta').value,
        pede_pagamento: document.getElementById('modoPedePagamento').checked ? 1 : 0,
        pede_obs_final: document.getElementById('modoPedeObsFinal').checked ? 1 : 0,
        pergunta_obs_final: document.getElementById('modoPerguntaObsFinal').value
    };
    
    if(!data.nome) return alert("Digite o nome!");
    
    const res = await fetch(id ? `/api/modos_envio/${id}` : '/api/modos_envio', { 
        method: id ? 'PUT' : 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify(data) 
    });

    if (res.ok) {
        document.getElementById('modalModoEnvio').style.display = 'none';
        carregarModosEnvio(); 
    } else {
        alert("Erro ao salvar modo de envio");
    }
}

async function toggleModoWpp(id, ativo) {
    await fetch(`/api/modos_envio/${id}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ apenas_status: true, disponivel_wpp: ativo ? 1 : 0 }) });
}

async function deletarModoEnvio(id) {
    if(confirm("Tem certeza que deseja apagar este modo de envio?")) {
        await fetch(`/api/modos_envio/${id}`, { method: 'DELETE' });
        carregarModosEnvio();
    }
}

// --- FLUXO DE CADASTRO ---


function abrirModalCampoCadastro(c = null) {
    document.getElementById('editCadId').value = c ? c.id : '';
    document.getElementById('modalCadLabel').value = c ? c.label : '';
    document.getElementById('modalCadPergunta').value = c ? c.pergunta_wpp : '';
    document.getElementById('modalCadAtivo').checked = c ? c.ativo_wpp : true;
    document.getElementById('modalCadObrig').checked = c ? c.obrigatorio : false;
    
    // Se for uma coluna fixa do sistema, impede a alteração do Nome
    const colunasFixas = ['nome', 'cpf', 'rua', 'numero_casa', 'bairro', 'ponto_referencia'];
    const isFixo = c && colunasFixas.includes(c.coluna);
    document.getElementById('modalCadLabel').disabled = isFixo;
    
    document.getElementById('modalCampoCadastroTitulo').innerText = c ? '✏️ Editar Campo' : '➕ Novo Campo';
    document.getElementById('modalCampoCadastro').style.display = 'flex';
}

function fecharModalCampoCadastro() {
    document.getElementById('modalCampoCadastro').style.display = 'none';
}

async function salvarCampoCadastroModal() {
    const id = document.getElementById('editCadId').value;
    const data = {
        label: document.getElementById('modalCadLabel').value,
        pergunta: document.getElementById('modalCadPergunta').value,
        ativo: document.getElementById('modalCadAtivo').checked,
        obrigatorio: document.getElementById('modalCadObrig').checked
    };

    if (!data.label || !data.pergunta) return alert("Preencha o Nome e a Pergunta!");

    const url = id ? `/api/config_cadastro/${id}` : '/api/config_cadastro';
    const method = id ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, { method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
        if (res.ok) {
            fecharModalCampoCadastro();
            loadConfigCadastro(); // Recarrega a lista sem precisar dar F5 na página
        } else {
            const result = await res.json();
            alert("Erro ao salvar campo: " + result.erro);
        }
    } catch (e) {
        console.error(e);
        alert("Erro de conexão ao tentar salvar.");
    }
}

async function removerCampoCadastro(id) {
    if (!confirm("Remover esta pergunta do fluxo? (Dados salvos dos clientes não serão apagados)")) return;
    try {
        const res = await fetch(`/api/config_cadastro/${id}`, { method: 'DELETE' });
        if (res.ok) loadConfigCadastro(); 
        else alert("Erro ao remover.");
    } catch (e) { alert("Erro de conexão."); }
}

// Inicia as funções ao carregar a página
window.onload = inicializar;

// ==========================================
// MENSAGENS AGENDADAS (DISPAROS DIÁRIOS)
// ==========================================

async function carregarMensagensAgendadas() {
    try {
        const res = await fetch('/api/mensagens_agendadas');
        const dados = await res.json();
        const lista = document.getElementById('listaMensagensAgendadas');
        lista.innerHTML = '';

        if(dados.length === 0) {
            lista.innerHTML = '<li class="empty-table-msg p-10">Nenhum disparo configurado.</li>';
            return;
        }

        dados.forEach(msg => {
            lista.innerHTML += `
                <li class="item-card msg-agenda-item" style="opacity: ${msg.ativo ? '1' : '0.6'};">
                    <div class="d-flex w-100 justify-between align-center">
                        <div class="flex-1">
                            <div class="msg-agenda-title">⏰ Todos os dias às ${msg.horario_envio}</div>
                            <div class="msg-agenda-desc">${msg.texto || '(Apenas Imagem)'}</div>
                            ${msg.imagem_base64 ? '<span class="msg-agenda-img-tag">🖼️ Com Imagem</span>' : ''}
                        </div>
                        
                        <div class="d-flex align-center gap-10">
                            <label class="d-flex align-center gap-5 text-muted text-sm" style="cursor:pointer;">
                                <input type="checkbox" ${msg.ativo ? 'checked' : ''} onchange="toggleDisparoAtivo(${msg.id}, this.checked)" style="transform: scale(1.2);">
                                ${msg.ativo ? 'Ativo' : 'Pausado'}
                            </label>
                            
                            <button type="button" class="btn-action-sm btn-action-edit" onclick='abrirModalDisparo(${JSON.stringify(msg)})' title="Editar">✏️</button>
                            <button type="button" class="btn-del" onclick="deletarMensagemAgendada(${msg.id})">🗑️</button>
                        </div>
                    </div>
                </li>
            `;
        });
    } catch (e) {
        console.error("Erro ao carregar disparos:", e);
    }
}

function abrirModalDisparo(msg = null) {
    const modal = document.getElementById('modalDisparo');
    const titulo = document.getElementById('modalDisparoTitulo');
    const idField = document.getElementById('editDispId');
    const avisoImg = document.getElementById('avisoEdicaoImagem');
    
    // Limpar campos sempre que abrir
    document.getElementById('newDispDataHora').value = '';
    document.getElementById('newDispTexto').value = '';
    document.getElementById('newDispImagem').value = '';
    document.getElementById('newDispAtivo').checked = true;

    if (msg) {
        // Modo Edição
        titulo.innerText = "✏️ Editar Disparo Diário";
        idField.value = msg.id;
        document.getElementById('newDispDataHora').value = msg.horario_envio;
        document.getElementById('newDispTexto').value = msg.texto || '';
        document.getElementById('newDispAtivo').checked = msg.ativo === 1;
        avisoImg.style.display = 'block'; // Mostra o aviso da imagem
    } else {
        // Modo Novo
        titulo.innerText = "➕ Novo Disparo Diário";
        idField.value = '';
        avisoImg.style.display = 'none';
    }

    modal.style.display = 'flex';
}

function fecharModalDisparo() {
    document.getElementById('modalDisparo').style.display = 'none';
}

async function salvarMensagemAgendada() {
    const id = document.getElementById('editDispId').value;
    const horario = document.getElementById('newDispDataHora').value;
    const texto = document.getElementById('newDispTexto').value;
    const ativo = document.getElementById('newDispAtivo').checked;
    const fileInput = document.getElementById('newDispImagem');
    
    if (!horario) return alert("Por favor, informe o Horário do disparo (ex: 18:00).");

    let base64Image = null;
    let atualizarImagem = false;

    if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        base64Image = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result);
            reader.onerror = error => reject(error);
        });
        atualizarImagem = true;
    }

    const payload = {
        texto: texto,
        imagem_base64: base64Image,
        horario_envio: horario,
        ativo: ativo,
        atualizar_imagem: atualizarImagem
    };

    const url = id ? `/api/mensagens_agendadas/${id}` : '/api/mensagens_agendadas';
    const method = id ? 'PUT' : 'POST';

    const res = await fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        carregarMensagensAgendadas();
        fecharModalDisparo();
    } else {
        alert("Erro ao salvar disparo.");
    }
}

async function toggleDisparoAtivo(id, status) {
    await fetch(`/api/mensagens_agendadas/${id}`, { 
        method: 'PUT', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ apenas_status: true, ativo: status }) 
    });
    carregarMensagensAgendadas(); // Recarrega para mudar a cor
}

async function deletarMensagemAgendada(id) {
    if(confirm("Tem certeza que deseja apagar este disparo permanente?")) {
        await fetch(`/api/mensagens_agendadas/${id}`, { method: 'DELETE' });
        carregarMensagensAgendadas();
    }
}