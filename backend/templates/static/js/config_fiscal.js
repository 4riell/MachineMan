document.addEventListener("DOMContentLoaded", () => {
    
    const arquivoInput = document.getElementById('cert_arquivo');
    const nomeExibicao = document.getElementById('cert_nome_exibicao');
    const formLogin = document.getElementById('form_login_sefaz');
    
    if(arquivoInput) {
        arquivoInput.addEventListener('change', function(e) {
            if (this.files && this.files.length > 0) {
                nomeExibicao.innerText = "📄 " + this.files[0].name;
                nomeExibicao.style.color = "#4cd137";
            } else {
                nomeExibicao.innerText = "Clique ou arraste o arquivo .pfx";
                nomeExibicao.style.color = "#00f2ff";
            }
        });
    }

    if(formLogin) {
        formLogin.addEventListener('submit', async function(event) {
            event.preventDefault();
            
            const cnpjInput = document.getElementById('cert_cnpj');
            const senhaInput = document.getElementById('cert_senha');
            const ambienteInput = document.getElementById('cert_ambiente'); 
            const btnConectar = document.getElementById('btn_conectar');
            const msgBox = document.getElementById('cert_msg');
            
            if (arquivoInput.files.length === 0) {
                msgBox.className = "mt-20 text-sm font-bold text-center text-danger";
                msgBox.innerText = "❌ Selecione o arquivo do certificado primeiro.";
                return;
            }

            // Remove máscara do CNPJ (pontos, traços, barras) para enviar apenas os números
            const cnpjLimpo = cnpjInput.value.replace(/\D/g, '');
            if(cnpjLimpo.length !== 14) {
                msgBox.className = "mt-20 text-sm font-bold text-center text-warning";
                msgBox.innerText = "⚠️ O CNPJ deve conter exatamente 14 dígitos.";
                return;
            }

            const formData = new FormData();
            formData.append("arquivo", arquivoInput.files[0]);
            formData.append("senha", senhaInput.value);
            formData.append("ambiente", ambienteInput.value); 
            formData.append("cnpj", cnpjLimpo); 
            formData.append("empresa_id", 1); 

            btnConectar.disabled = true;
            btnConectar.innerHTML = "⏳ Validando Chaves e Conexão na SEFAZ...";
            msgBox.innerHTML = "";

            try {
                const response = await fetch('/api/config/certificado', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok && data.sucesso) {
                    msgBox.className = "mt-20 text-sm font-bold text-center text-success";
                    msgBox.innerHTML = "✅ " + data.mensagem;
                    formLogin.reset();
                    nomeExibicao.innerText = "Clique ou arraste o arquivo .pfx";
                    nomeExibicao.style.color = "#00f2ff";
                    
                    setTimeout(() => {
                        window.location.href = "/documentos-fiscais";
                    }, 3000);
                    
                } else {
                    msgBox.className = "mt-20 text-sm font-bold text-center text-danger";
                    msgBox.innerHTML = "❌ " + (data.erro || "Falha ao autenticar. Verifique a senha.");
                }
            } catch (error) {
                msgBox.className = "mt-20 text-sm font-bold text-center text-danger";
                msgBox.innerHTML = "❌ Erro de comunicação com o servidor principal.";
            } finally {
                btnConectar.disabled = false;
                btnConectar.innerHTML = "🚀 Conectar à SEFAZ";
            }
        });
    }
});