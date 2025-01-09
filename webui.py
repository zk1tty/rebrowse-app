# -*- coding: utf-8 -*-
# @Time    : 2025/1/1
# @Author  : wenshao
# @Email   : wenshaoguo1026@gmail.com
# @Project : browser-use-webui
# @FileName: webui.py

import pdb
import glob

from dotenv import load_dotenv
load_dotenv()
import argparse
import gradio as gr
import os
import asyncio
from playwright.async_api import async_playwright
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import (
    BrowserContextConfig,
    BrowserContextWindowSize,
)
from browser_use.agent.service import Agent
from src.browser.custom_browser import CustomBrowser
from src.controller.custom_controller import CustomController
from src.agent.custom_agent import CustomAgent
from src.agent.custom_prompts import CustomSystemPrompt
from src.browser.custom_browser import CustomBrowser
from src.browser.custom_context import BrowserContextConfig
from src.controller.custom_controller import CustomController
from src.utils import utils
from src.utils.utils import update_model_dropdown
from src.utils.file_utils import get_latest_files
from src.utils.stream_utils import capture_screenshot


async def run_browser_agent(
        agent_type,
        llm_provider,
        llm_model_name,
        llm_temperature,
        llm_base_url,
        llm_api_key,
        use_own_browser,
        headless,
        disable_security,
        window_w,
        window_h,
        save_recording_path,
        save_trace_path,
        enable_recording,
        task,
        add_infos,
        max_steps,
        use_vision,
        max_actions_per_step,
        tool_call_in_content,
        browser_context=None  
):
    """Run the browser agent with proper browser context initialization"""
    browser = None
    try:
        # Run the agent
        llm = utils.get_llm_model(
            provider=llm_provider,
            model_name=llm_model_name,
            temperature=llm_temperature,
            base_url=llm_base_url,
            api_key=llm_api_key,
        )

        if agent_type == "org":
            result = await run_org_agent(
                llm=llm,
                headless=headless,
                disable_security=disable_security,
                window_w=window_w,
                window_h=window_h,
                save_recording_path=save_recording_path,
                task=task,
                max_steps=max_steps,
                use_vision=use_vision,
                max_actions_per_step=max_actions_per_step,
                tool_call_in_content=tool_call_in_content,
                browser_context=browser_context,
            )
        elif agent_type == "custom":
            result = await run_custom_agent(
                llm=llm,
                use_own_browser=use_own_browser,
                headless=headless,
                disable_security=disable_security,
                window_w=window_w,
                window_h=window_h,
                save_recording_path=save_recording_path,
                save_trace_path=save_trace_path,
                task=task,
                add_infos=add_infos,
                max_steps=max_steps,
                use_vision=use_vision,
                max_actions_per_step=max_actions_per_step,
                tool_call_in_content=tool_call_in_content,
                browser_context=browser_context,
            )
        else:
            raise ValueError(f"Invalid agent type: {agent_type}")
        
        return result

    finally:
        if browser:
            await browser.close()

async def run_org_agent(
        llm,
        headless,
        disable_security,
        window_w,
        window_h,
        save_recording_path,
        save_trace_path,
        task,
        max_steps,
        use_vision,
        max_actions_per_step,
        tool_call_in_content,
        browser_context=None,  # receive context
):
    browser = None
    if browser_context is None:
        browser = Browser(
            config=BrowserConfig(
                headless=headless,  # Force non-headless for streaming
                disable_security=disable_security,
                extra_chromium_args=[f'--window-size={window_w},{window_h}'],
            )
        )
        async with await browser.new_context(
                config=BrowserContextConfig(
                    trace_path=save_trace_path if save_trace_path else None,
                    save_recording_path=save_recording_path if save_recording_path else None,
                    no_viewport=False,
                    browser_window_size=BrowserContextWindowSize(width=window_w, height=window_h),
                )
        ) as browser_context_in:
            agent = Agent(
                task=task,
                llm=llm,
                use_vision=use_vision,
                browser_context=browser_context_in,
            )
            history = await agent.run(max_steps=max_steps)
            
            final_result = history.final_result()
            errors = history.errors()
            model_actions = history.model_actions()
            model_thoughts = history.model_thoughts()
        
        recorded_files = get_latest_files(save_recording_path)
        trace_file = get_latest_files(save_recording_path + "/../traces")
        
        await browser.close()
        return final_result, errors, model_actions, model_thoughts, recorded_files.get('.webm'), trace_file.get('.zip')
    else:
        # Reuse existing context
        agent = Agent(
            task=task,
            llm=llm,
            use_vision=use_vision,
            max_actions_per_step=max_actions_per_step,
            browser_context=browser_context,
        )
        history = await agent.run(max_steps=max_steps)
        final_result = history.final_result()
        errors = history.errors()
        model_actions = history.model_actions()
        model_thoughts = history.model_thoughts()
        recorded_files = get_latest_files(save_recording_path)
        trace_file = get_latest_files(save_recording_path + "/../traces")
        return final_result, errors, model_actions, model_thoughts, recorded_files.get('.webm'), trace_file.get('.zip')

async def run_custom_agent(
        llm,
        use_own_browser,
        headless,
        disable_security,
        window_w,
        window_h,
        save_recording_path,
        save_trace_path,
        task,
        add_infos,
        max_steps,
        use_vision,
        max_actions_per_step,
        tool_call_in_content,
        browser_context=None,  # receive context
):
    controller = CustomController()
    playwright = None
    browser = None
    try:
        if use_own_browser:
            playwright = await async_playwright().start()
            chrome_exe = os.getenv("CHROME_PATH", "")
            chrome_use_data = os.getenv("CHROME_USER_DATA", "")

            if chrome_exe == "":
                chrome_exe = None
            elif not os.path.exists(chrome_exe):
                raise ValueError(f"Chrome executable not found at {chrome_exe}")

            if chrome_use_data == "":
                chrome_use_data = None

            browser_context_ = await playwright.chromium.launch_persistent_context(
                user_data_dir=chrome_use_data if chrome_use_data else "",
                executable_path=chrome_exe,
                no_viewport=False,
                headless=headless,  # 保持浏览器窗口可见
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36"
                ),
                java_script_enabled=True,
                bypass_csp=disable_security,
                ignore_https_errors=disable_security,
                record_video_dir=save_recording_path if save_recording_path else None,
                record_video_size={"width": window_w, "height": window_h},
            )
        else:
            browser_context_ = None

        if browser_context is not None:
            # Reuse context
            agent = CustomAgent(
                task=task,
                add_infos=add_infos,
                use_vision=use_vision,
                llm=llm,
                browser_context=browser_context,
                controller=controller,
                system_prompt_class=CustomSystemPrompt
            )
            history = await agent.run(max_steps=max_steps)
            final_result = history.final_result()
            errors = history.errors()
            model_actions = history.model_actions()
            model_thoughts = history.model_thoughts()
            recorded_files = get_latest_files(save_recording_path)
            trace_file = get_latest_files(save_recording_path + "/../traces")
            return final_result, errors, model_actions, model_thoughts, recorded_files.get('.webm'), trace_file.get('.zip')
        else:
            browser = CustomBrowser(
                config=BrowserConfig(
                    headless=headless,
                    disable_security=disable_security,
                    extra_chromium_args=[f"--window-size={window_w},{window_h}"],
                )
            )
            async with await browser.new_context(
                    config=BrowserContextConfig(
                        trace_path=save_trace_path if save_trace_path else None,
                        save_recording_path=save_recording_path
                        if save_recording_path
                        else None,
                        no_viewport=False,
                        browser_window_size=BrowserContextWindowSize(
                            width=window_w, height=window_h
                        ),
                    ),
                    context=browser_context_,
            ) as browser_context:
                agent = CustomAgent(
                    task=task,
                    add_infos=add_infos,
                    use_vision=use_vision,
                    llm=llm,
                    browser_context=browser_context,
                    controller=controller,
                    system_prompt_class=CustomSystemPrompt,
                    max_actions_per_step=max_actions_per_step,
                    tool_call_in_content=tool_call_in_content
                )
                history = await agent.run(max_steps=max_steps)
                final_result = history.final_result()
                errors = history.errors()
                model_actions = history.model_actions()
                model_thoughts = history.model_thoughts()
                recorded_files = get_latest_files(save_recording_path)
                trace_file = get_latest_files(save_recording_path + "/../traces")
                return final_result, errors, model_actions, model_thoughts, recorded_files.get('.webm'), trace_file.get('.zip')

    except Exception as e:
        import traceback

        traceback.print_exc()
        final_result = ""
        errors = str(e) + "\n" + traceback.format_exc()
        model_actions = ""
        model_thoughts = ""
        recorded_files = {}
        trace_file = {}
    finally:
        # 显式关闭持久化上下文
        if browser_context_:
            await browser_context_.close()

        # 关闭 Playwright 对象
        if playwright:
            await playwright.stop()
        if browser:
            await browser.close()
    return final_result, errors, model_actions, model_thoughts, trace_file.get('.webm'), recorded_files.get('.zip')

async def run_with_stream(
    agent_type,
    llm_provider,
    llm_model_name,
    llm_temperature,
    llm_base_url,
    llm_api_key,
    use_own_browser,
    headless,
    disable_security,
    window_w,
    window_h,
    save_recording_path,
    save_trace_path,
    enable_recording,
    task,
    add_infos,
    max_steps,
    use_vision,
    max_actions_per_step,
    tool_call_in_content,
):
    """Wrapper to run the agent and handle streaming."""
    browser = None
    try:
        # Initialize the browser
        browser = CustomBrowser(
            config=BrowserConfig(
                headless=False,
                disable_security=disable_security,
                extra_chromium_args=[f"--window-size={window_w},{window_h}"],
            )
        )

        # Create a new browser context
        async with await browser.new_context(
            config=BrowserContextConfig(
                trace_path=save_trace_path if save_trace_path else None,
                save_recording_path=save_recording_path if save_recording_path else None,
                no_viewport=False,
                browser_window_size=BrowserContextWindowSize(
                    width=window_w, height=window_h
                ),
            )
        ) as browser_context:
            # Run the browser agent in the background
            agent_task = asyncio.create_task(
                run_browser_agent(
                    agent_type=agent_type,
                    llm_provider=llm_provider,
                    llm_model_name=llm_model_name,
                    llm_temperature=llm_temperature,
                    llm_base_url=llm_base_url,
                    llm_api_key=llm_api_key,
                    use_own_browser=use_own_browser,
                    headless=headless,
                    disable_security=disable_security,
                    window_w=window_w,
                    window_h=window_h,
                    save_recording_path=save_recording_path,
                    save_trace_path=save_trace_path,
                    enable_recording=enable_recording,
                    task=task,
                    add_infos=add_infos,
                    max_steps=max_steps,
                    use_vision=use_vision,
                    max_actions_per_step=max_actions_per_step,
                    tool_call_in_content=tool_call_in_content,
                    browser_context=browser_context  # Explicit keyword argument
                )
            )

            # Initialize values for streaming
            html_content = "<div>Starting browser...</div>"
            final_result = errors = model_actions = model_thoughts = ""
            recording = trace = None

            # Periodically update the stream while the agent task is running
            while not agent_task.done():
                try:
                    html_content = await capture_screenshot(browser_context)
                except Exception as e:
                    html_content = f"<div class='error'>Screenshot error: {str(e)}</div>"
                
                yield [
                    html_content,
                    final_result,
                    errors,
                    model_actions,
                    model_thoughts,
                    recording,
                    trace,
                ]
                await asyncio.sleep(0.01)

            # Once the agent task completes, get the results
            try:
                result = await agent_task
                if isinstance(result, tuple) and len(result) == 6:
                    (
                        final_result,
                        errors,
                        model_actions,
                        model_thoughts,
                        recording,
                        trace,
                    ) = result
                else:
                    errors = "Unexpected result format from agent"
            except Exception as e:
                errors = f"Agent error: {str(e)}"

            yield [
                html_content,
                final_result,
                errors,
                model_actions,
                model_thoughts,
                recording,
                trace,
            ]

    except Exception as e:
        import traceback

        yield [
            f"<div class='error'>Browser error: {str(e)}</div>",
            "",
            f"Error: {str(e)}\n{traceback.format_exc()}",
            "",
            "",
            None,
            None,
        ]
    finally:
        if browser:
            await browser.close()

from gradio.themes import Citrus, Default, Glass, Monochrome, Ocean, Origin, Soft, Base

# Define the theme map globally
theme_map = {
    "Default": Default(),
    "Soft": Soft(),
    "Monochrome": Monochrome(),
    "Glass": Glass(),
    "Origin": Origin(),
    "Citrus": Citrus(),
    "Ocean": Ocean(),
    "Base": Base()
}

# Create the Gradio UI
def create_ui(theme_name="Ocean"):
    css = """
    .gradio-container {
        max-width: 1200px !important;
        margin: auto !important;
        padding-top: 20px !important;
    }
    .header-text {
        text-align: center;
        margin-bottom: 30px;
    }
    .theme-section {
        margin-bottom: 20px;
        padding: 15px;
        border-radius: 10px;
    }
    """

    with gr.Blocks(title="Browser Use WebUI", theme=theme_map[theme_name], css=css) as demo:
        # Header
        with gr.Row():
            gr.Markdown(
                """
                # 🌐 Browser Use WebUI
                ### Control your browser with AI assistance
                """,
                elem_classes=["header-text"],
            )

        with gr.Tabs() as tabs:
            with gr.TabItem("⚙️ Agent Settings", id=1):
                with gr.Group():
                    agent_type = gr.Radio(
                        ["org", "custom"],
                        label="Agent Type",
                        value="custom",
                        info="Select the type of agent to use",
                    )
                    max_steps = gr.Slider(
                        minimum=1,
                        maximum=200,
                        value=100,
                        step=1,
                        label="Max Run Steps",
                        info="Maximum number of steps the agent will take",
                    )
                    max_actions_per_step = gr.Slider(
                        minimum=1,
                        maximum=20,
                        value=10,
                        step=1,
                        label="Max Actions per Step",
                        info="Maximum number of actions the agent will take per step",
                    )
                    use_vision = gr.Checkbox(
                        label="Use Vision",
                        value=True,
                        info="Enable visual processing capabilities",
                    )
                    tool_call_in_content = gr.Checkbox(
                        label="Use Tool Calls in Content",
                        value=True,
                        info="Enable Tool Calls in content",
                    )

            with gr.TabItem("🔧 LLM Configuration", id=2):
                with gr.Group():
                    llm_provider = gr.Dropdown(
                        ["anthropic", "openai", "deepseek", "gemini", "ollama", "azure_openai"],
                        label="LLM Provider",
                        value="",
                        info="Select your preferred language model provider"
                    )
                    llm_model_name = gr.Dropdown(
                        label="Model Name",
                        value="",
                        interactive=True,
                        allow_custom_value=True,  # Allow users to input custom model names
                        info="Select a model from the dropdown or type a custom model name"
                    )
                    llm_temperature = gr.Slider(
                        minimum=0.0,
                        maximum=2.0,
                        value=1.0,
                        step=0.1,
                        label="Temperature",
                        info="Controls randomness in model outputs"
                    )
                    with gr.Row():
                        llm_base_url = gr.Textbox(
                            label="Base URL",
                            value=os.getenv(f"{llm_provider.value.upper()}_BASE_URL ", ""),  # Default to .env value
                            info="API endpoint URL (if required)"
                        )
                        llm_api_key = gr.Textbox(
                            label="API Key",
                            type="password",
                            value=os.getenv(f"{llm_provider.value.upper()}_API_KEY", ""),  # Default to .env value
                            info="Your API key (leave blank to use .env)"
                        )

            with gr.TabItem("🌐 Browser Settings", id=3):
                with gr.Group():
                    with gr.Row():
                        use_own_browser = gr.Checkbox(
                            label="Use Own Browser",
                            value=False,
                            info="Use your existing browser instance",
                        )
                        headless = gr.Checkbox(
                            label="Headless Mode",
                            value=False,
                            info="Run browser without GUI",
                        )
                        disable_security = gr.Checkbox(
                            label="Disable Security",
                            value=True,
                            info="Disable browser security features",
                        )
                        enable_recording = gr.Checkbox(
                            label="Enable Recording",
                            value=True,
                            info="Enable saving browser recordings",
                        )

                    with gr.Row():
                        window_w = gr.Number(
                            label="Window Width",
                            value=1280,
                            info="Browser window width",
                        )
                        window_h = gr.Number(
                            label="Window Height",
                            value=1100,
                            info="Browser window height",
                        )

                    save_recording_path = gr.Textbox(
                        label="Recording Path",
                        placeholder="e.g. ./tmp/record_videos",
                        value="./tmp/record_videos",
                        info="Path to save browser recordings",
                        interactive=True,  # Allow editing only if recording is enabled
                    )

                    save_trace_path = gr.Textbox(
                        label="Trace Path",
                        placeholder="e.g. ./tmp/traces",
                        value="./tmp/traces",
                        info="Path to save Agent traces",
                        interactive=True,
                    )

            with gr.TabItem("🤖 Run Agent", id=4):
                task = gr.Textbox(
                    lines=4,
                    value="go to google.com and type 'OpenAI' click search and give me the first url",
                    info="Describe what you want the agent to do",
                )
                add_infos = gr.Textbox(lines=3, label="Additional Information")

            # Results
            with gr.Tab("📊 Results"):
                browser_view = gr.HTML(
                    value="<div>Waiting for browser session...</div>",
                    label="Live Browser View",
                )
                final_result_output = gr.Textbox(label="Final Result", lines=3)
                errors_output = gr.Textbox(label="Errors", lines=3)
                model_actions_output = gr.Textbox(label="Model Actions", lines=3)
                model_thoughts_output = gr.Textbox(label="Model Thoughts", lines=3)
                recording_file = gr.Video(label="Latest Recording")
                trace_file = gr.File(label="Trace File")
        with gr.Row():
            run_button = gr.Button("▶️ Run Agent", variant="primary")

        # Attach the callback to the LLM provider dropdown
        llm_provider.change(
            lambda provider, api_key, base_url: update_model_dropdown(provider, api_key, base_url),
            inputs=[llm_provider, llm_api_key, llm_base_url],
            outputs=llm_model_name
        )

        # Add this after defining the components
        enable_recording.change(
            lambda enabled: gr.update(interactive=enabled),
            inputs=enable_recording,
            outputs=save_recording_path
        )
        
        # Button logic
        run_button.click(
            fn=run_with_stream,
            inputs=[
                agent_type, llm_provider, llm_model_name, llm_temperature, llm_base_url, llm_api_key,
                use_own_browser, headless, disable_security, window_w, window_h, save_recording_path, save_trace_path,
                enable_recording, task, add_infos, max_steps, use_vision, max_actions_per_step, tool_call_in_content
            ],
            outputs=[
                browser_view,
                final_result_output,
                errors_output,
                model_actions_output,
                model_thoughts_output,
                recording_file,
                trace_file
            ],
            queue=True,
        )

    return demo


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gradio UI for Browser Agent")
    parser.add_argument("--ip", type=str, default="0.0.0.0", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=7860, help="Port to listen on")
    parser.add_argument("--theme", type=str, default="Ocean", choices=theme_map.keys())
    args = parser.parse_args()

    ui = create_ui(theme_name=args.theme)
    ui.launch(server_name=args.ip, server_port=args.port, share=True)