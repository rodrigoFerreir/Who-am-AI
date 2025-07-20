
let currentSessionId = null;
let chatSocket = null;
let accessToken = localStorage.getItem('access_token');
let refreshToken = localStorage.getItem('refresh_token');

const chatMessagesDiv = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendButton = document.getElementById('send-button');
const themeSelect = document.getElementById('theme-select');
const levelSelect = document.getElementById('level-select');
const startGameButton = document.getElementById('start-game-button');
const scoreDisplay = document.getElementById('score-display');
const attemptsDisplay = document.getElementById('attempts-display'); // NOVO: Elemento para exibir tentativas

const gameOverModal = document.getElementById('gameOverModal');
const closeModalButton = document.querySelector('#gameOverModal .close-button');
const playAgainButton = document.getElementById('play-again-button');
const modalMessage = document.getElementById('modal-message');
const finalScoreSpan = document.getElementById('final-score');
const revealedCharacterSpan = document.getElementById('revealed-character');
const characterImage = document.getElementById('character-image');

const usernameDisplay = document.getElementById('username-display');
const loginLink = document.getElementById('login-link');
const signupLink = document.getElementById('signup-link');
const logoutLink = document.getElementById('logout-link');

const statusBar = document.getElementById('status-bar');

let currentScore = 0;
let currentAttempts = 0; // NOVO: Variável para armazenar as tentativas restantes

// Função para adicionar mensagens à interface do chat (apenas user e ai)
function appendMessage(sender, message) {
    if (sender === 'user' || sender === 'ai') {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);
        messageDiv.textContent = message;
        chatMessagesDiv.appendChild(messageDiv);
        chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;
    }
}

// Função para atualizar a barra de status
function updateStatusBar(message) {
    statusBar.textContent = message;
}

// Função para atualizar a exibição da pontuação
function updateScore(score) {
    currentScore = score;
    scoreDisplay.textContent = `Pontuação: ${currentScore}`;
}

// NOVO: Função para atualizar a exibição das tentativas
function updateAttemptsDisplay(attempts) {
    currentAttempts = attempts;
    attemptsDisplay.textContent = `Tentativas: ${currentAttempts}`;
}

// Função para mostrar o modal de fim de jogo
function showGameOverModal(message, score, characterName, characterImageUrl) { // NOVO: characterImageUrl
    modalMessage.textContent = message;
    finalScoreSpan.textContent = score;
    revealedCharacterSpan.textContent = characterName;
    gameOverModal.style.display = 'flex';

    if (characterImageUrl) { // Exibe a imagem se houver uma URL
        characterImage.src = characterImageUrl;
        characterImage.classList.remove('hidden');
    } else {
        characterImage.classList.add('hidden'); // Esconde se não houver
    }
}

// Função para buscar e exibir a imagem do personagem (agora usa a URL real)
function fetchCharacterImage(characterName) {
    // Esta função não é mais estritamente necessária se a URL da imagem já vem no evento game_over
    // Mas pode ser mantida como fallback ou se a imagem for gerada no frontend
    // Por enquanto, a lógica principal de exibição da imagem está em showGameOverModal
    console.log(`DEBUG JS: Tentando buscar imagem para ${characterName} (via fallback ou para depuração)`);
    const imageUrl = `https://placehold.co/200x200/cccccc/000000?text=${encodeURIComponent(characterName)}`;
    characterImage.src = imageUrl;
    characterImage.classList.remove('hidden');
}

// Função para configurar a conexão WebSocket
function setupWebSocket(sessionId) {
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.close();
    }
    chatSocket = new WebSocket(
        'ws://' + window.location.host + '/ws/game/' + sessionId + '/'
    );

    // Manipuladores de eventos WebSocket
    chatSocket.onmessage = function (e) {
        const data = JSON.parse(e.data);
        if (data.type === 'chat_message') {
            appendMessage(data.sender, data.message);
        } else if (data.type === 'system_message') {
            updateStatusBar(data.message);
        } else if (data.type === 'game_over') {
            updateScore(data.score);
            // Passa a URL da imagem para o modal
            showGameOverModal(data.message, data.score, data.character_name, data.character_image_url);
        } else if (data.type === 'error') {
            updateStatusBar(`Erro: ${data.message}`);
        } else if (data.type === 'update_attempts') { // NOVO: Handler para tentativas
            updateAttemptsDisplay(data.attempts_left);
        }
    };

    chatSocket.onclose = function (e) {
        console.error('Chat socket fechado inesperadamente');
        updateStatusBar('Conexão com o jogo perdida. Por favor, inicie um novo jogo.');
    };

    chatSocket.onopen = function (e) {
        updateStatusBar(`Conectado à sessão de jogo: ${sessionId}.`);
    };
}

// Manipulador de evento para entrada do chat (tecla Enter)
chatInput.onkeyup = function (e) {
    if (e.keyCode === 13) {
        sendButton.click();
    }
};

// Manipulador de evento para o botão de enviar
sendButton.onclick = async function () {
    const message = chatInput.value.trim();
    if (!accessToken) {
        updateStatusBar('Você precisa estar logado para enviar mensagens.');
        return;
    }
    if (!currentSessionId) {
        updateStatusBar('Por favor, inicie um novo jogo primeiro.');
        return;
    }
    if (message) {
        try {
            const response = await fetch('/api/message/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Authorization': `Bearer ${accessToken}`
                },
                body: JSON.stringify({
                    session_id: currentSessionId,
                    message: message
                })
            });

            if (!response.ok) {
                if (response.status === 401) {
                    const refreshed = await refreshAccessToken();
                    if (refreshed) {
                        await sendButton.click();
                        return;
                    } else {
                        updateStatusBar('Sessão expirada. Por favor, faça login novamente.');
                        return;
                    }
                }
                const errorData = await response.json();
                throw new Error(errorData.error || 'Erro ao enviar mensagem.');
            }

            chatInput.value = '';
        } catch (error) {
            updateStatusBar(`Erro ao enviar mensagem: ${error.message}`);
            console.error('Erro ao enviar mensagem:', error);
        }
    }
};

// Manipulador de evento para o botão iniciar jogo
startGameButton.onclick = async function () {
    if (!accessToken) {
        updateStatusBar('Você precisa estar logado para iniciar um novo jogo.');
        return;
    }

    const theme = themeSelect.value;
    const level = levelSelect.value;
    chatMessagesDiv.innerHTML = ''; // Limpa as mensagens do chat
    updateScore(0); // Reseta a pontuação
    updateAttemptsDisplay(0); // Reseta as tentativas
    gameOverModal.style.display = 'none';
    characterImage.classList.add('hidden');

    try {
        const response = await fetch('/api/new/game/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({
                theme: theme,
                level: level
            })
        });

        if (response.ok) {
            const data = await response.json();
            currentSessionId = data.session_id;
            setupWebSocket(currentSessionId);
            updateStatusBar(`Jogo iniciado! Tema: ${theme}, Nível: ${level}. Aguardando a primeira dica...`);
        } else {
            if (response.status === 401) {
                const refreshed = await refreshAccessToken();
                if (refreshed) {
                    await startGameButton.click();
                    return;
                } else {
                    updateStatusBar('Sessão expirada. Por favor, faça login novamente.');
                    return;
                }
            }
            const errorData = await response.json();
            throw new Error(errorData.error || 'Erro ao iniciar o jogo.');
        }
    } catch (error) {
        updateStatusBar(`Falha ao iniciar jogo: ${error.message}`);
        console.error('Erro ao iniciar jogo:', error);
    }
};

// Manipulador de evento para fechar o modal de fim de jogo
closeModalButton.onclick = function () {
    gameOverModal.style.display = 'none';
};

// Manipulador de evento para o botão jogar novamente
playAgainButton.onclick = function () {
    gameOverModal.style.display = 'none';
    characterImage.classList.add('hidden');
    startGameButton.click();
};

// Fecha o modal se clicado fora dele
window.onclick = function (event) {
    if (event.target == gameOverModal) {
        gameOverModal.style.display = 'none';
    }
};

// Função auxiliar para obter o token CSRF do cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Função para refrescar o token de acesso JWT
async function refreshAccessToken() {
    if (!refreshToken) {
        return false;
    }
    try {
        const response = await fetch('/api/token/refresh/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ refresh: refreshToken })
        });

        if (response.ok) {
            const data = await response.json();
            accessToken = data.access;
            localStorage.setItem('access_token', accessToken);
            localStorage.setItem('refresh_token', data.refresh);
            return true;
        } else {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            accessToken = null;
            refreshToken = null;
            return false;
        }
    } catch (error) {
        console.error('Erro ao refrescar token:', error);
        return false;
    }
}

// Função para verificar o status de login e atualizar a UI
async function checkLoginStatus() {
    if (accessToken) {
        try {
            const response = await fetch('/api/me/', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            });

            if (response.ok) {
                const userData = await response.json();
                usernameDisplay.textContent = `Olá, ${userData.username || 'Usuário'}!`;
                usernameDisplay.style.display = 'inline';
                loginLink.style.display = 'none';
                signupLink.style.display = 'none';
                logoutLink.style.display = 'inline';
            } else if (response.status === 401) {
                const refreshed = await refreshAccessToken();
                if (refreshed) {
                    await checkLoginStatus();
                } else {
                    handleLogout();
                }
            } else {
                console.error('Erro ao buscar dados do usuário:', await response.text());
                handleLogout();
            }
        } catch (e) {
            console.error("Erro ao buscar dados do usuário ou decodificar token:", e);
            handleLogout();
        }
    } else {
        handleLogout();
    }
}

// Função para lidar com o logout do usuário
function handleLogout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    accessToken = null;
    refreshToken = null;
    usernameDisplay.textContent = '';
    usernameDisplay.style.display = 'none';
    loginLink.style.display = 'inline';
    signupLink.style.display = 'inline';
    logoutLink.style.display = 'none';
    updateStatusBar('Você foi desconectado.');
}

// Manipulador de evento para o link de logout
logoutLink.onclick = function (event) {
    event.preventDefault();
    handleLogout();
    window.location.href = '/accounts/login/';
};

// Ao carregar a página, verifica o status de login e fornece instruções iniciais
window.onload = function () {
    checkLoginStatus();
    updateStatusBar('Por favor, faça login e clique em "Iniciar Novo Jogo" para começar.');
};
