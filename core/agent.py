# Importações necessárias do LangChain e outras bibliotecas
import os
from dotenv import load_dotenv
from langchain.memory import ConversationBufferMemory
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


load_dotenv()
# --- Configuração da Chave de API ---
# Para usar o Google Gemini, você precisa de uma chave de API.
# É altamente recomendado definir esta chave como uma variável de ambiente.
# Exemplo (no seu terminal antes de executar):
# export GOOGLE_API_KEY="SUA_CHAVE_API_AQUI"
# No ambiente Canvas, a chave será injetada automaticamente, então você pode deixar a linha abaixo comentada.
# os.environ["GOOGLE_API_KEY"] = "SUA_CHAVE_API_AQUI"

SYSTEM_PROMPT_AI = """
            Você é o mestre do jogo "Quem Sou Eu?". Seu objetivo é **SER UM PERSONAGEM** (ou uma entidade, conceito, etc.) e dar dicas para o jogador adivinhar quem você é.

            **No início de cada nova rodada, você DEVE escolher um personagem (ou entidade) com base no TEMA e NÍVEL de dificuldade fornecidos e MANTÊ-LO CONSISTENTEMENTE durante toda a rodada.**
            **É CRUCIAL que você mantenha o mesmo personagem durante toda a rodada até que ele seja adivinhado ou uma nova rodada seja iniciada.**

            **Regras do Jogo:**
            1.  **Escolha do Personagem:** Ao receber o TEMA e NÍVEL, escolha um personagem (ou entidade) que se encaixe. **Mantenha este personagem em mente durante toda a interação.**
            2.  **Dica Inicial:** Sua primeira resposta deve ser uma dica **amigável, contextual e descritiva de uma cena ou situação** que envolva o personagem, sem revelar sua identidade. O nível de detalhes e a clareza do contexto devem variar com o NÍVEL de dificuldade.
            3.  **Respostas a Perguntas:** O jogador fará perguntas para tentar adivinhar quem você é. Você deve responder estritamente com "Sim", "Não", "Talvez", ou uma dica curta e objetiva se a pergunta não puder ser respondida com sim/não.
            4.  **Tentativas de Adivinhação:** Se o jogador fizer uma tentativa de adivinhação (ex: "É o Batman?", "Você é a Rainha Elizabeth?"), você deve responder com:
                * "Sim, você acertou! Eu sou [Nome do Personagem]." (Se correto)
                * "Não, não sou [Nome do Personagem]. Tente novamente! Aqui vai outra dica: [Nova Dica sobre o Personagem]." (Se incorreto)
            5.  **NÃO REVELE SUA IDENTIDADE DIRETAMENTE** em nenhuma outra circunstância, apenas quando o jogador adivinhar corretamente.
            6.  Mantenha o tom divertido e desafiador.

            **Instruções de Parâmetros da Rodada Atual:**
            * **TEMA:** {tema}
            * **NÍVEL:** {nivel}
                * **Fácil:** A dica inicial deve ser um cenário bem descrito, com detalhes claros e que remetam diretamente ao personagem.
                * **Médio:** A dica inicial deve ser um cenário com contexto moderado, talvez com um elemento mais sutil ou indireto, exigindo um pouco mais de raciocínio.
                * **Difícil:** A dica inicial deve ser um cenário com contexto muito limitado, mais abstrata ou que exige inferência profunda e conhecimento mais específico.
                * **Aleatório:** Você deve escolher um nível (Fácil, Médio, Difícil) internamente para esta rodada e adaptar o personagem e as dicas a ele, seguindo as regras de contexto acima.

            **Formato de Saída:**
            Sua resposta deve ser apenas a dica ou a confirmação/negação da adivinhação.

            **Exemplo de Início de Rodada (para você):**
            Input: TEMA: Filmes, NÍVEL: Fácil
            Seu pensamento: Ok, vou ser o "Darth Vader".
            Sua saída: "Em uma galáxia muito, muito distante, eu sou uma figura imponente, envolto em um capacete preto e uma capa esvoaçante. Minha respiração pesada ecoa pelos corredores de uma estação espacial, enquanto lidero tropas imperiais em busca de rebeldes. Sinto uma perturbação na Força..."

            Input: TEMA: História, NÍVEL: Difícil
            Seu pensamento: Ok, vou ser a "Hipátia de Alexandria".
            Sua saída: "No crepúsculo da Antiguidade, em uma cidade de grande saber, eu me dedicava aos estudos de matemática e astronomia, ensinando em um centro de conhecimento que um dia foi grandioso. Minha mente brilhava, mas os ventos da mudança eram perigosos."

            ---
            **Início da Rodada:**
            """


class GuessingGameAgent:
    """
    Classe que encapsula a lógica do agente de IA para o jogo "Quem Sou Eu?".
    Gerencia a interação com o modelo Gemini, o histórico da conversa e as regras do jogo.
    """

    def __init__(self):
        # Inicializa o modelo de linguagem grande (LLM) do Google Gemini.
        # "gemini-pro" é um modelo adequado para tarefas de conversação e geração de texto.
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            api_key=os.getenv("GOOGLE_API_KEY"),
        )

        # Define o template do prompt que será enviado ao LLM.
        # Ele inclui instruções para o agente, regras do jogo, parâmetros da rodada
        # e um placeholder para o histórico da conversa (`MessagesPlaceholder`).
        self.game_prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    SYSTEM_PROMPT_AI,
                ),
                # MessagesPlaceholder é crucial para injetar o histórico da conversa no prompt do LLM.
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),  # Onde a entrada do usuário será inserida.
            ]
        )

        # Inicializa a memória da conversa.
        # ConversationBufferMemory armazena todas as mensagens da conversa.
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
        )

        # Cria a cadeia principal do LangChain usando LCEL (LangChain Expression Language).
        # Isso permite passar múltiplas variáveis de entrada de forma mais robusta e gerenciar o histórico.
        self.chain = (
            # RunnablePassthrough.assign permite adicionar novas chaves ao dicionário de entrada.
            # Aqui, estamos carregando o histórico da memória e atribuindo-o à chave 'chat_history'
            # que o MessagesPlaceholder no prompt espera.
            RunnablePassthrough.assign(
                chat_history=lambda x: self.memory.load_memory_variables({})[
                    "chat_history"
                ]
            )
            # Em seguida, passamos o dicionário de entrada (agora com tema, nivel, input e chat_history) para o prompt.
            | self.game_prompt_template
            # O prompt renderizado é passado para o LLM.
            | self.llm
            # Finalmente, a saída do LLM é convertida em uma string simples.
            | StrOutputParser()
        )

        # Variáveis para armazenar o tema e nível da rodada atual, e o nome do personagem adivinhado.
        self.current_theme = None
        self.current_level = None
        self.character_name = None  # Será preenchido quando o jogador acertar.

    def start_new_game(self, theme: str, level: str) -> str:
        """
        Inicia uma nova rodada do jogo.
        Limpa o histórico da conversa, define o tema e o nível, e solicita a dica inicial ao agente.

        Args:
            theme (str): O tema escolhido pelo usuário (ex: "Filmes", "História").
            level (str): O nível de dificuldade escolhido pelo usuário (ex: "Fácil", "Médio", "Difícil", "Aleatório").

        Returns:
            str: A dica inicial fornecida pelo agente de IA.
        """
        self.memory.clear()  # Limpa todo o histórico da conversa para uma nova rodada.
        self.current_theme = theme
        self.current_level = level
        self.character_name = None  # Reseta o nome do personagem adivinhado.

        # Invoca a cadeia LangChain para obter a dica inicial.
        # Passamos todas as variáveis que o prompt espera.
        initial_response_text = self.chain.invoke(
            {
                "tema": self.current_theme,
                "nivel": self.current_level,
                "input": "Por favor, me dê a dica inicial.",  # Esta é a "entrada" do usuário para a primeira interação
            }
        )

        # Salva a primeira interação na memória para que o histórico seja mantido.
        # A "pergunta" inicial do usuário é a instrução para a dica, e a "resposta" é a dica do agente.
        self.memory.save_context(
            {"input": "Por favor, me dê a dica inicial."},
            {"output": initial_response_text},
        )

        return initial_response_text

    def process_player_input(self, player_input: str) -> str:
        """
        Processa a entrada do jogador (pergunta ou tentativa de adivinhação) e retorna a resposta do agente.
        Também tenta identificar se o personagem foi revelado na resposta do agente.

        Args:
            player_input (str): A pergunta ou adivinhação do jogador.

        Returns:
            str: A resposta do agente de IA.
        """
        # Invoca a cadeia LangChain com a nova entrada do jogador.
        # O `chat_history` é injetado automaticamente pelo `RunnablePassthrough.assign`
        # antes que o prompt seja processado.
        agent_response_text = self.chain.invoke(
            {
                "tema": self.current_theme,
                "nivel": self.current_level,
                "input": player_input,
            }
        )

        # Salva a interação atual (entrada do jogador e resposta do agente) na memória.
        self.memory.save_context(
            {"input": player_input}, {"output": agent_response_text}
        )

        # Heurística para tentar capturar o nome do personagem quando o jogador acerta.
        # O prompt instrui o LLM a usar o formato "Sim, você acertou! Eu sou [Nome do Personagem]."
        if "Sim, você acertou! Eu sou" in agent_response_text:
            try:
                # Extrai o nome do personagem da string de resposta.
                # Remove o prefixo e o sufixo (ponto final) para obter apenas o nome.
                self.character_name = (
                    agent_response_text.split("Sim, você acertou! Eu sou ")[1]
                    .replace(".", "")
                    .strip()
                )
            except IndexError:
                # Em caso de falha na extração (formato inesperado), o nome permanece None.
                print(
                    "Aviso: Falha ao extrair o nome do personagem da resposta do agente."
                )
                pass

        return agent_response_text


# --- Exemplo de Uso (para demonstração em console) ---
if __name__ == "__main__":
    # Este bloco é executado apenas quando o script é executado diretamente.
    # Ele simula a interação do jogo no console.

    game = GuessingGameAgent()

    print("Bem-vindo ao jogo 'Quem Sou Eu?'!")
    print("Você pode definir o tema e o nível de dificuldade.")
    print(
        "Temas disponíveis: Filmes, Séries, História, Política, Literatura, Ciência, Esportes, Música, Jogos, Personalidades, Mitologia, Personagens de Desenho Animado"
    )
    print("Níveis disponíveis: Fácil, Médio, Difícil, Aleatório")
    print("Digite 'sair' a qualquer momento para sair do jogo.")
    print("Digite 'nova' durante o jogo para iniciar uma nova rodada.")

    while True:
        # Loop para escolher tema e nível para uma nova rodada
        theme = input("\nEscolha um tema: ").strip()
        if theme.lower() == "sair":
            break
        level = input("Escolha um nível: ").strip()
        if level.lower() == "sair":
            break

        print(f"\nIniciando nova rodada: Tema '{theme}', Nível '{level}'")
        try:
            # Inicia o jogo e obtém a primeira dica
            initial_hint = game.start_new_game(theme, level)
            print(f"Agente: {initial_hint}")
        except Exception as e:
            print(f"Erro ao iniciar o jogo: {e}")
            print(
                f"Por favor, verifique se a GOOGLE_API_KEY está configurada corretamente ou se há um problema de conexão."
            )
            continue  # Volta para o início do loop para tentar novamente.

        # Loop para a interação do jogo (perguntas e adivinhações)
        while True:
            player_input = input(
                "Sua pergunta ou adivinhação (ou 'nova' para nova rodada, 'sair' para sair): "
            ).strip()

            if player_input.lower() == "sair":
                print("Obrigado por jogar!")
                exit()  # Sai do programa
            elif player_input.lower() == "nova":
                print("\nSolicitando uma nova rodada...")
                break  # Sai do loop interno para pedir novo tema/nível novamente
            else:
                try:
                    # Processa a entrada do jogador e obtém a resposta do agente
                    agent_response = game.process_player_input(player_input)
                    print(f"Agente: {agent_response}")

                    # Verifica se o jogador acertou
                    if "Sim, você acertou!" in agent_response:
                        if game.character_name:
                            print(f"Parabéns! O personagem era: {game.character_name}")
                        else:
                            print("Parabéns! Você acertou o personagem!")
                        print("Iniciando uma nova rodada...")
                        break  # Sai do loop interno para pedir novo tema/nível novamente
                except Exception as e:
                    print(f"Erro ao processar sua entrada: {e}")
                    print("Por favor, tente novamente ou verifique sua conexão.")

    print("Jogo encerrado.")
