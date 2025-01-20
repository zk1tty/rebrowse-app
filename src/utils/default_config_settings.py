import os
import pickle


def load_config_from_file(file_path: str='./.config.pkl',) -> dict:
    try:
        with open(file_path, 'rb') as file:
            loaded_config = pickle.load(file)
    except FileNotFoundError as FNFE:
        from dotenv import load_dotenv
        load_dotenv()
        return {
            "agent_type": "custom",
            "max_steps": 100,
            "max_actions_per_step": 10,
            "use_vision": True,
            "tool_call_in_content": True,
            "llm_provider": "openai",
            "llm_model_name": "gpt-4o",
            "llm_temperature": 1.0,
            "llm_base_url": '',
            "llm_api_key": '',
            "use_own_browser": False,
            "keep_browser_open": os.getenv("CHROME_PERSISTENT_SESSION", "False").lower() == "true",
            "headless": False,
            "disable_security": True,
            "enable_recording": True,
            "window_w": 1280,
            "window_h": 1100,
            "save_recording_path": "./tmp/record_videos",
            "save_trace_path": "./tmp/traces",
            "save_agent_history_path": "./tmp/agent_history",
            "task": "go to google.com and type 'OpenAI' click search and give me the first url",
        }
    return loaded_config


def save_config_to_file(config, file_path: str='./.config.pkl',) -> None:
    with open(file_path, 'wb') as file:
        pickle.dump(config, file)
