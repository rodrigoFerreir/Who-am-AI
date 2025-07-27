import os
from langchain_google_genai import ChatGoogleGenerativeAI


class GoggleConnectionGemini:

    @staticmethod
    def connect():
        # Configura a chave da API Gemini.
        # A chave será injetada automaticamente no ambiente Canvas se deixada vazia.
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        model_ai = os.environ.get("GOOGLE_MODEL_AI", "gemini-2.5-flash")
        if not api_key:
            print(
                "AVISO: GOOGLE_API_KEY não configurada. Usando chave padrão do ambiente Canvas."
            )

        # Inicializa o modelo de linguagem grande (LLM) do Google Gemini.
        # Modelos específicos para diferentes propósitos para otimização e controle.
        llm_chat = ChatGoogleGenerativeAI(
            model=model_ai,
            google_api_key=api_key,
            temperature=0.7,
        )
        llm_character_selection = ChatGoogleGenerativeAI(
            model=model_ai,
            google_api_key=api_key,
            temperature=0.1,
        )  # Baixa temperatura para escolha consistente
        llm_classification = ChatGoogleGenerativeAI(
            model=model_ai,
            google_api_key=api_key,
            temperature=0.0,
            max_output_tokens=10,
        )  # Temperatura zero para classificação binária

        return llm_chat, llm_character_selection, llm_classification
