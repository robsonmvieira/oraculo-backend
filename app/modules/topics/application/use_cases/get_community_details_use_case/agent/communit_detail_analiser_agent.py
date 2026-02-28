import os

from langchain_openai import ChatOpenAI

from app.modules.shared.application.services.llm_factory import extract_response_text
from langgraph.graph import END, START, StateGraph

from app.modules.topics.application.use_cases.get_community_details_use_case.agent.prompts.analizy_community_prompt import (
    analyze_community_node_prompt,
)
from app.modules.topics.application.use_cases.get_community_details_use_case.agent.state import (
    CommunityAnalyzerState,
)


def analyze_community(state: CommunityAnalyzerState) -> dict:
    """
    Analisa título e descrição da comunidade para gerar termos derivados
    """
    llm = ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
        temperature=0,
    )

    prompt = analyze_community_node_prompt(
        state["title"],
        state["public_description"],
        language=state.get("language", "en"),
    )

    response = llm.invoke(prompt)

    # Parsear a resposta - separar por vírgula e limpar espaços
    terms = [term.strip() for term in extract_response_text(response).split(",")]

    return {"derived_terms": terms[:10]}


def create_community_analyzer_agent():
    """
    Cria o agente LangGraph para análise de comunidades
    """
    workflow = StateGraph(CommunityAnalyzerState)

    workflow.add_node("analyze", analyze_community)

    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", END)

    return workflow.compile()


def analyze_community_for_related_terms(
    title: str,
    public_description: str,
    language: str = "en",
) -> list[str]:
    """
    Executa o agente e retorna os termos derivados

    Args:
        title: Título da comunidade
        public_description: Descrição pública da comunidade
        language: Idioma preferido do usuário

    Returns:
        Lista de termos derivados para buscar comunidades relacionadas
    """
    agent = create_community_analyzer_agent()

    result = agent.invoke(
        {
            "title": title,
            "public_description": public_description,
            "language": language,
            "derived_terms": [],
        }
    )

    return result["derived_terms"]
