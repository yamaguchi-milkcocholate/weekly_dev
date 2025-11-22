from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

import sns_ai_automation_agency.agent.station_sign.prompt as prompt
import sns_ai_automation_agency.agent.station_sign.schema as schema
import sns_ai_automation_agency.agent.station_sign.search as search


def run_station_sign_agent(station_name: str) -> Dict[str, Any]:
    search_result = search.search_station_sign_images(station_name)

    system_prompt = prompt.get_system_prompt()
    user_prompt = prompt.get_user_prompt(station_name=station_name, search_results=search_result)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm = llm.with_structured_output(schema.StationSignResponse)
    thumbnail_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("user", user_prompt),
        ]
    )

    # 構造化LLMチェーンを実行
    chain = thumbnail_prompt | llm
    thumbnail_result = chain.invoke({})

    filtered_result = [sr for sr in search_result if sr["id"] == thumbnail_result.selected_id]

    if len(filtered_result) > 0:
        selected_result = filtered_result[0]
    else:
        raise ValueError("Selected ID not found in search results")

    return selected_result
