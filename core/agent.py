import os
import random


from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
)
from langchain.memory import ConversationBufferMemory
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from duckduckgo_search import duckduckgo_search
from core.utils.models.google_ai import GoggleConnectionGemini
from core.utils.llm_prompts import CHARACTER_SELECTION_PROMPT, PRINCIPAL_GAME_PROMPT


# Carrega variáveis de ambiente (como GOOGLE_API_KEY)
from dotenv import load_dotenv

load_dotenv()


class GuessingGameAgent:
    """
    Agente de IA para o jogo de adivinhação, utilizando LangChain.
    Gerencia a interação com o modelo Gemini, o histórico da conversa,
    as regras do jogo (incluindo tentativas) e a geração de imagens.
    """

    def __init__(self):

        # Define o template do prompt principal do jogo.
        # Inclui instruções, regras, parâmetros da rodada e placeholder para o histórico.
        self.llm_chat, self.llm_character_selection, self.llm_classification = (
            GoggleConnectionGemini.connect()
        )
        self.game_prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    PRINCIPAL_GAME_PROMPT,
                ),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
            ]
        )

        # Inicializa a memória da conversa.
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
        )

        # Cria a cadeia principal do LangChain.
        self.chain = (
            RunnablePassthrough.assign(
                chat_history=lambda x: self.memory.load_memory_variables({})[
                    "chat_history"
                ]
            )
            | self.game_prompt_template
            | self.llm_chat
            | StrOutputParser()
        )

        # Variáveis de estado do jogo
        self.current_theme = ""
        self.current_level = ""
        self.character_name = ""
        self.max_attempts = 0
        self.attempts_left = 0

    def start_new_game(self, theme: str, level: str, last_character_names: list) -> str:
        """
        Inicia uma nova rodada do jogo.
        Limpa o histórico, define tema/nível/tentativas, escolhe o personagem e gera a dica inicial.
        """
        # self.memory.clear()
        self.character_name = ""
        self.current_theme = theme
        self.current_level = level
        self.last_character_names = (
            ", ".join(last_character_names) if last_character_names else ""
        )

        # Define o número máximo de tentativas com base no nível
        attempts_map = {
            "Facil": 10,
            "Medio": 8,
            "Dificil": 5,
        }
        self.max_attempts = attempts_map.get(level, 7)
        self.attempts_left = self.max_attempts

        # Se o nível for "Aleatório", escolhe um nível real
        if self.current_level == "Aleatorio":
            self.current_level = random.choice(["Facil", "Medio", "Dificil"])
            print(f"DEBUG Agent: Nível aleatório escolhido: {self.current_level}")

        try:
            # 1. Escolhe o personagem internamente (com um prompt separado para controle)
            character_selection_prompt_template = PromptTemplate.from_template(
                CHARACTER_SELECTION_PROMPT
            )
            character_selection_chain = (
                character_selection_prompt_template
                | self.llm_character_selection
                | StrOutputParser()
            )

            self.character_name = character_selection_chain.invoke(
                {
                    "theme": self.current_theme,
                    "level": self.current_level,
                    "character_name": self.character_name,
                    "last_character_names": self.last_character_names,
                }
            ).strip()
            print(f"DEBUG Agent: Personagem escolhido pela IA: {self.character_name}")

            # 2. Gera a primeira dica usando o prompt principal do jogo
            # A instrução de tentativas é incluída aqui.
            attempts_instruction_text = (
                f"Você é este personagem que já foi escolhido {self.character_name}. "
                f"Cuidado ao revelar suas dicas. "
                f"Você tem {self.attempts_left} tentativas diretas restantes para adivinhar o personagem. "
                f"Se o jogador tentar adivinhar e errar, mencione as tentativas restantes. "
                f"Se as tentativas chegarem a 0 e o jogador não acertou, diga 'Suas tentativas acabaram! O personagem era {self.character_name}.'"
            )

            initial_response_text = self.chain.invoke(
                {
                    "tema": self.current_theme,
                    "nivel": self.current_level,
                    "character_name": self.character_name,
                    "attempts_instruction": attempts_instruction_text,  # Passa a instrução de tentativas
                    "input": "Por favor, me dê a dica inicial.",
                }
            )

            # Salva a interação na memória
            self.memory.save_context(
                {"input": "Por favor, me dê a dica inicial."},
                {"output": initial_response_text},
            )

            return initial_response_text

        except Exception as e:
            print(f"Erro ao iniciar novo jogo com a IA: {e}")
            return "Desculpe, não consegui iniciar um novo jogo no momento. Tente novamente."

    def classify_user_input(self, user_input: str) -> str:
        """
        Classifica a entrada do usuário como 'guess' (tentativa de adivinhação) ou 'question'.
        Utiliza um LLM separado para uma classificação precisa.
        """
        classification_prompt_template = PromptTemplate.from_template(
            "A seguinte entrada do usuário é uma tentativa de adivinhar o personagem "
            "ou uma pergunta sobre o personagem? Responda APENAS 'guess' ou 'question'."
            "\n\nEntrada do usuário: '{user_input}'"
        )
        classification_chain = (
            classification_prompt_template | self.llm_classification | StrOutputParser()
        )

        try:
            classification = (
                classification_chain.invoke({"user_input": user_input}).strip().lower()
            )
            if classification == "guess":
                return "guess"
            return "question"
        except Exception as e:
            print(f"Erro ao classificar entrada do usuário: {e}")
            return "question"  # Padrão para pergunta em caso de erro

    def process_player_input(
        self,
        player_input: str,
        number_attempts_left_session: int,
    ) -> str:
        """
        Processa a entrada do jogador, interage com a IA e retorna a resposta.
        Gerencia a contagem de tentativas e verifica o fim do jogo.
        """
        # Classifica a entrada do usuário para determinar se é uma tentativa
        input_type = self.classify_user_input(player_input)
        print(f"DEBUG Agent: Entrada do usuário classificada como: {input_type}")
        print(
            f"DEBUG Agent: Tentativas restantes na sessão: {number_attempts_left_session}"
        )

        # Decrementa tentativas apenas se for uma tentativa de adivinhação
        if input_type == "guess":
            self.attempts_left -= 1
            print(f"DEBUG Agent: Tentativas restantes: {self.attempts_left}")

        # Adiciona a instrução sobre tentativas restantes ao prompt principal para a IA
        attempts_instruction_text = (
            f"Você tem {self.attempts_left} tentativas diretas restantes para adivinhar o personagem. "
            f"Se o jogador tentar adivinhar e errar, mencione as tentativas restantes. "
            f"Se as tentativas chegarem a 0 e o jogador não acertou, diga 'Suas tentativas acabaram! O personagem era {self.character_name}.'"
        )

        # Invoca a cadeia LangChain com a nova entrada do jogador e as instruções atualizadas.
        agent_response_text = self.chain.invoke(
            {
                "tema": self.current_theme,
                "nivel": self.current_level,
                "character_name": self.character_name,
                "attempts_instruction": attempts_instruction_text,  # Passa a instrução de tentativas atualizada
                "input": player_input,
            }
        )
        agent_response_text = agent_response_text.strip()

        # Salva a interação atual na memória.
        self.memory.save_context(
            {"input": player_input},
            {"output": agent_response_text},
        )

        # Heurística para tentar capturar o nome do personagem quando o jogador acerta.
        if "Sim, você acertou!" in agent_response_text:
            try:
                self.character_name = (
                    agent_response_text.split("Sim, você acertou! Eu sou ")[1]
                    .replace(".", "")
                    .strip()
                )
            except IndexError:
                print(
                    "Aviso: Falha ao extrair o nome do personagem da resposta do agente."
                )
                pass
        elif (
            "Suas tentativas acabaram!" in agent_response_text
            or self.attempts_left <= 0
        ):
            # Garante que o character_name esteja definido mesmo se as tentativas acabarem
            if not self.character_name:
                print(
                    "Aviso: Tentativas acabaram, mas character_name não foi definido."
                )
                # Tenta uma última extração ou define um fallback
                self.character_name = "Personagem Desconhecido"  # Fallback

        return agent_response_text

    def generate_character_image_prompt(self):
        """
        Gera uma consulta de busca para encontrar uma imagem do personagem.
        """
        if not self.character_name:
            return "personagem desconhecido"

        # Adapta o prompt para uma consulta de busca de imagem
        return f"imagem de {self.character_name}"

    def generate_image(self, prompt_image: str):
        try:
            results = duckduckgo_search.DDGS().images(
                keywords=prompt_image,
                region="us-en",
                safesearch="moderate",
                size=None,
                color=None,
                type_image="photo",
                layout=None,
                license_image=None,
                max_results=1,
            )
            return results[0].get("image", "")
        except IndexError:
            print(f"Nenhum resultado de imagem foi encontrado para {prompt_image}")
            return ""
        except Exception as err:
            print(f"Error on gen image result {err}")
            return ""
