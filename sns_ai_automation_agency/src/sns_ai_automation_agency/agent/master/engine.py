from sns_ai_automation_agency.agent.access import survey_access_information
from sns_ai_automation_agency.agent.restaurant import survey_restaurant_information
from sns_ai_automation_agency.agent.scene import run_scene_agent
from sns_ai_automation_agency.agent.thumbnail import run_thumbnail_agent


def run_master_agent(
    station_name: str,
    num_highlight_stations: int,
    num_iterations: int,
    total_seconds: int,
    image_count: int,
    thread_id: str = None,
    max_concurrent: int = 5,
) -> dict:
    access_data = survey_access_information(
        station_name=station_name,
        num_highlight_stations=num_highlight_stations,
        thread_id=thread_id,
    )

    restaurant_data = survey_restaurant_information(
        station_name=station_name,
        num_iterations=num_iterations,
        thread_id=thread_id,
    )

    scene_data = run_scene_agent(
        restaurant_info=restaurant_data,
        access_info=access_data,
        total_seconds=total_seconds,
        station_name=station_name,
        thread_id=thread_id,
    )

    thumbnail_data = run_thumbnail_agent(
        scene_data=scene_data,
        count=image_count,
        station_name=station_name,
        max_concurrent=max_concurrent,
        thread_id=thread_id,
    )

    return {
        "access_data": access_data,
        "restaurant_data": restaurant_data,
        "scene_data": scene_data,
        "thumbnail_data": thumbnail_data,
    }
