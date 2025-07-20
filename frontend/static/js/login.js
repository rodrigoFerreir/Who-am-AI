
document.getElementById('login-form').addEventListener('submit', async function (event) {
    event.preventDefault(); // Impede o envio padrão do formulário

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMessageDiv = document.getElementById('error-message');

    errorMessageDiv.classList.add('hidden'); // Esconde mensagens de erro anteriores
    errorMessageDiv.textContent = ''; // Limpa o texto da mensagem de erro

    try {
        const response = await fetch('/api/login/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') // Obtém o token CSRF para segurança
            },
            body: JSON.stringify({ username, password }) // Envia os dados como JSON
        });

        const data = await response.json(); // Analisa a resposta JSON do servidor

        if (response.ok) { // Se a resposta HTTP for 2xx (sucesso)
            localStorage.setItem('access_token', data.access); // Armazena o token de acesso
            localStorage.setItem('refresh_token', data.refresh); // Armazena o token de refresh
            alert('Login bem-sucedido!'); // Alerta de sucesso
            window.location.href = '/'; // Redireciona para a página principal do jogo
        } else { // Se a resposta HTTP for um erro (ex: 400, 401)
            errorMessageDiv.textContent = data.detail || 'Credenciais inválidas.'; // Exibe a mensagem de erro do servidor
            errorMessageDiv.classList.remove('hidden'); // Mostra a div de erro
        }
    } catch (error) { // Lida com erros de rede ou outros erros inesperados
        errorMessageDiv.textContent = 'Ocorreu um erro inesperado. Tente novamente.';
        errorMessageDiv.classList.remove('hidden');
        console.error('Erro de login:', error);
    }
});

// Função auxiliar para obter o token CSRF do cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Verifica se a string do cookie começa com o nome que procuramos
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
