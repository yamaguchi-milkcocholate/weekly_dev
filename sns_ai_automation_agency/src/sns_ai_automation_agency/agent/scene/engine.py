import json

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

import sns_ai_automation_agency.agent.scene.prompt as prompt
import sns_ai_automation_agency.agent.scene.schema as schema
import sns_ai_automation_agency.utils as utils


def run_scene_agent(
    restaurant_info: dict, access_info: dict, total_seconds: int, thread_id: str = None, station_name: str = None
) -> dict:
    load_dotenv()

    if thread_id:
        cache = utils.CachePathManager(app_name=thread_id)
        cache_file = cache.file(f"scene_{station_name}.json")

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
    else:
        cache, cache_file = None, None

    access_json = json.dumps(access_info, indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
    restaurant_json = json.dumps(restaurant_info, indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")

    system_prompt = prompt.get_systemprompt()
    user_prompt = prompt.get_userprompt(
        access_json=access_json, restaurant_json=restaurant_json, total_seconds=total_seconds
    )

    scene_llm = ChatOpenAI(model="gpt-5.1", temperature=0, reasoning_effort="high")
    scene_llm = scene_llm.with_structured_output(schema.MovieResponse)
    scene_prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("user", user_prompt)])

    chain = scene_prompt | scene_llm
    scene_output: schema.MovieResponse = chain.invoke({})
    result_dict = utils.to_serializable(scene_output)

    if cache:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=4)

    return result_dict
