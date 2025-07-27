import os
import json
import requests
import random  # Para escolher nível aleatório
from typing import List, Dict, Any

# Importações do LangChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
)
from langchain.memory import ConversationBufferMemory
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from duckduckgo_search import duckduckgo_search


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
        # Configura a chave da API Gemini.
        # A chave será injetada automaticamente no ambiente Canvas se deixada vazia.
        self.api_key = os.environ.get("GOOGLE_API_KEY", "")
        self.model_ai = os.environ.get("GOOGLE_MODEL_AI", "gemini-2.5-flash")
        if not self.api_key:
            print(
                "AVISO: GOOGLE_API_KEY não configurada. Usando chave padrão do ambiente Canvas."
            )

        # Inicializa o modelo de linguagem grande (LLM) do Google Gemini.
        # Modelos específicos para diferentes propósitos para otimização e controle.
        self.llm_chat = ChatGoogleGenerativeAI(
            model=self.model_ai,
            google_api_key=self.api_key,
            temperature=0.7,
        )
        self.llm_character_selection = ChatGoogleGenerativeAI(
            model=self.model_ai,
            google_api_key=self.api_key,
            temperature=0.1,
        )  # Baixa temperatura para escolha consistente
        self.llm_classification = ChatGoogleGenerativeAI(
            model=self.model_ai,
            google_api_key=self.api_key,
            temperature=0.0,
            max_output_tokens=10,
        )  # Temperatura zero para classificação binária

        # Define o template do prompt principal do jogo.
        # Inclui instruções, regras, parâmetros da rodada e placeholder para o histórico.
        self.game_prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
            Você é o mestre do jogo "Quem Sou Eu?". Seu objetivo é **SER UM PERSONAGEM** (ou uma entidade, conceito, etc.) e dar dicas para o jogador adivinhar quem você é.

            **No início de cada nova rodada, você DEVE escolher um personagem (ou entidade) com base no TEMA e NÍVEL de dificuldade fornecidos e MANTÊ-LO CONSISTENTEMENTE durante toda a rodada.**
            **É CRUCIAL que você mantenha o mesmo personagem durante toda a rodada até que ele seja adivinhado ou uma nova rodada seja iniciada.**

            **Regras do Jogo:**
            1.  **Escolha do Personagem:** Ao receber o personagem, gere uma abordagem divertida e empolgante **Mantenha este personagem em mente durante toda a interação.**
            2.  **Dica Inicial:** Sua primeira resposta deve ser uma dica **amigável, contextual e descritiva de uma cena ou situação** que envolva o personagem, sem revelar sua identidade. O nível de detalhes e a clareza do contexto devem variar com o NÍVEL de dificuldade. Tente contar uma história rápida para que o usuário entenda a situação.
            3.  **Respostas a Perguntas:** O jogador fará perguntas para tentar adivinhar quem você é. Você deve responder estritamente com "Sim", "Não", "Talvez", ou uma dica curta e objetiva se a pergunta não puder ser respondida com sim/não.
            4.  **Tentativas de Adivinhação:** Se o jogador fizer uma tentativa de adivinhação (ex: "É o Batman?", "Você é a Rainha Elizabeth?"), você deve responder com:
                * "Sim, você acertou! Eu sou [Nome do Personagem]." (Se correto)
                * "Não, não sou [Nome do Personagem]. Tente novamente! Aqui vai outra dica: [Nova Dica sobre o Personagem]." (Se incorreto)
            5.  **NÃO REVELE SUA IDENTIDADE DIRETAMENTE** em nenhuma outra circunstância, apenas quando o jogador adivinhar corretamente.
            6.  Mantenha o tom divertido e desafiador.
            7.  Não repetir personagens já usados em rodadas anteriores para aumentar a dinamica do jogo.

            **Instruções de Parâmetros da Rodada Atual:**
            * **TEMA:** {tema}
            * **NÍVEL:** {nivel}
            * **Você é {character_name}, ja foi escolhido anteriormente
            * **TENTATIVAS RESTANTES:** {attempts_instruction}
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
            """,
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
                """Você é um mestre na escolha de personagens para o jogo 'Quem Sou Eu?'. Sua tarefa é pensar em um personagem famoso (real ou fictício) do tema '{theme}' que se encaixe perfeitamente no nível de dificuldade '{level}'.

                **Diretrizes para a escolha do personagem:**
                - **Relevância:** O personagem DEVE ser diretamente associado ao tema '{theme}'.
                - **Variedade e Aleatoriedade:** Tente escolher um personagem diferente a cada vez, evitando repetições óbvias se o jogo for reiniciado. Seja criativo e explore a amplitude do tema.
                - **Não repetir estes personagens pois já foram utilizados em rodadas anteriores {last_character_names}
                - **Nível de Dificuldade:**
                    - **Fácil:** Escolha um personagem muito conhecido, icônico e central ao tema. Aquele que a maioria das pessoas reconheceria facilmente.
                    - **Médio:** Escolha um personagem conhecido, mas que talvez exija um pouco mais de conhecimento ou seja ligeiramente menos óbvio que os "fáceis". Pode ser um coadjuvante importante ou alguém de uma obra um pouco menos mainstream.
                    - **Difícil:** Escolha um personagem mais obscuro, de nicho, ou que seja conhecido apenas por fãs mais dedicados do tema. Pode ser alguém com um papel menor, mas ainda relevante, ou de uma obra menos popular.

                Responda APENAS com o nome do personagem. Não forneça nenhum outro texto, explicação ou formatação adicional.
                Exemplo de resposta: 'Darth Vader' ou 'Cleópatra' ou 'Sherlock Holmes'."""
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
            {"input": player_input}, {"output": agent_response_text}
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
            and self.attempts_left <= 0
        ):
            # Garante que o character_name esteja definido mesmo se as tentativas acabarem
            if not self.character_name:
                print(
                    "Aviso: Tentativas acabaram, mas character_name não está definido."
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
