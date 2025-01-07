# -*- coding: utf-8 -*-
# @Time    : 2025/1/1
# @Author  : wenshao
# @Email   : wenshaoguo1026@gmail.com
# @Project : browser-use-webui
# @FileName: webui.py
from dotenv import load_dotenv
load_dotenv()
import argparse
import gradio as gr
import os
import asyncio
import glob
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

from src.utils import utils
from src.utils.file_utils import get_latest_files
from src.utils.stream_utils import stream_browser_view, capture_screenshot


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
        task,
        add_infos,
        max_steps,
        use_vision,
        browser_context=None  # Added optional argument
):
    # Ensure the recording directory exists
    os.makedirs(save_recording_path, exist_ok=True)

    # Get the list of existing videos before the agent runs
    existing_videos = set(glob.glob(os.path.join(save_recording_path, '*.[mM][pP]4')) + 
                          glob.glob(os.path.join(save_recording_path, '*.[wW][eE][bB][mM]')))

    # Run the agent
    llm = utils.get_llm_model(
        provider=llm_provider,
        model_name=llm_model_name,
        temperature=llm_temperature,
        base_url=llm_base_url,
        api_key=llm_api_key
    )
    if agent_type == "org":
        final_result, errors, model_actions, model_thoughts = await run_org_agent(
            llm=llm,
            headless=headless,
            disable_security=disable_security,
            window_w=window_w,
            window_h=window_h,
            save_recording_path=save_recording_path,
            task=task,
            max_steps=max_steps,
            use_vision=use_vision,
            browser_context=browser_context  # pass context
        )
    elif agent_type == "custom":
        final_result, errors, model_actions, model_thoughts = await run_custom_agent(
            llm=llm,
            use_own_browser=use_own_browser,
            headless=headless,
            disable_security=disable_security,
            window_w=window_w,
            window_h=window_h,
            save_recording_path=save_recording_path,
            task=task,
            add_infos=add_infos,
            max_steps=max_steps,
            use_vision=use_vision,
            browser_context=browser_context  # pass context
        )
    else:
        raise ValueError(f"Invalid agent type: {agent_type}")

    # Get the list of videos after the agent runs
    new_videos = set(glob.glob(os.path.join(save_recording_path, '*.[mM][pP]4')) + 
                     glob.glob(os.path.join(save_recording_path, '*.[wW][eE][bB][mM]')))

    # Find the newly created video
    latest_video = None
    if new_videos - existing_videos:
        latest_video = list(new_videos - existing_videos)[0]  # Get the first new video

    return final_result, errors, model_actions, model_thoughts, latest_video

async def run_org_agent(
        llm,
        headless,
        disable_security,
        window_w,
        window_h,
        save_recording_path,
        task,
        max_steps,
        use_vision,
        browser_context=None  # receive context
):
    browser = None
    if browser_context is None:
        browser = Browser(
            config=BrowserConfig(
                headless=False,  # Force non-headless for streaming
                disable_security=disable_security,
                extra_chromium_args=[f'--window-size={window_w},{window_h}'],
            )
        )
        async with await browser.new_context(
                config=BrowserContextConfig(
                    trace_path='./tmp/traces',
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
            browser_context=browser_context
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
        task,
        add_infos,
        max_steps,
        use_vision,
        browser_context=None  # receive context
):
    controller = CustomController()
    playwright = None
    browser = None
    try:
        if use_own_browser:
            playwright = await async_playwright().start()
            chrome_exe = os.getenv("CHROME_PATH", "")
            chrome_use_data = os.getenv("CHROME_USER_DATA", "")
            browser_context_ = await playwright.chromium.launch_persistent_context(
                user_data_dir=chrome_use_data,
                executable_path=chrome_exe,
                no_viewport=False,
                headless=headless,  # 保持浏览器窗口可见
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'
                ),
                java_script_enabled=True,
                bypass_csp=disable_security,
                ignore_https_errors=disable_security,
                record_video_dir=save_recording_path if save_recording_path else None,
                record_video_size={'width': window_w, 'height': window_h}
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
                    extra_chromium_args=[f'--window-size={window_w},{window_h}'],
                )
            )
            async with await browser.new_context(
                    config=BrowserContextConfig(
                        trace_path='./tmp/result_processing',
                        save_recording_path=save_recording_path if save_recording_path else None,
                        no_viewport=False,
                        browser_window_size=BrowserContextWindowSize(width=window_w, height=window_h),
                    ),
                    context=browser_context_
            ) as browser_context_in:
                agent = CustomAgent(
                    task=task,
                    add_infos=add_infos,
                    use_vision=use_vision,
                    llm=llm,
                    browser_context=browser_context_in,
                    controller=controller,
                    system_prompt_class=CustomSystemPrompt
                )
                history = await agent.run(max_steps=max_steps)

                final_result = history.final_result()
                errors = history.errors()
                model_actions = history.model_actions()
                model_thoughts = history.model_thoughts()
                
                recorded_files = get_latest_files(save_recording_path)

    except Exception as e:
        import traceback
        traceback.print_exc()
        final_result = ""
        errors = str(e) + "\n" + traceback.format_exc()
        model_actions = ""
        model_thoughts = ""
        recorded_files = {}
    finally:
        # 显式关闭持久化上下文
        if browser_context_:
            await browser_context_.close()

        # 关闭 Playwright 对象
        if playwright:
            await playwright.stop()
        if browser:
            await browser.close()
    return final_result, errors, model_actions, model_thoughts, recorded_files.get('.webm'), recorded_files.get('.zip')


async def run_with_stream(*args):
    """Wrapper to run agent and handle streaming"""
    browser = None
    try:
        browser = CustomBrowser(config=BrowserConfig(
            headless=False,
            disable_security=args[8],
            extra_chromium_args=[f'--window-size={args[9]},{args[10]}'],
        ))

        async with await browser.new_context(
            config=BrowserContextConfig(
                trace_path='./tmp/traces',
                save_recording_path=args[11],
                no_viewport=False,
                browser_window_size=BrowserContextWindowSize(width=args[9], height=args[10]),
            )
        ) as browser_context:
            # No need to explicitly create page - context creation handles it
            
            # Run agent in background
            agent_task = asyncio.create_task(run_browser_agent(*args, browser_context=browser_context))
            
            # Initialize values
            html_content = "<div>Starting browser...</div>"
            final_result = errors = model_actions = model_thoughts = ""
            recording = trace = None

            while not agent_task.done():
                try:
                    html_content = await capture_screenshot(browser_context)
                except Exception as e:
                    html_content = f"<div class='error'>Screenshot error: {str(e)}</div>"
                    
                yield [html_content, final_result, errors, model_actions, model_thoughts, recording, trace]
                await asyncio.sleep(0.01)

            # Get agent results when done
            try:
                result = await agent_task
                if isinstance(result, tuple) and len(result) == 6:
                    final_result, errors, model_actions, model_thoughts, recording, trace = result
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
                trace
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
            None
        ]
    finally:
        if browser:
            await browser.close()


def main():
    # Gradio UI setup
    with gr.Blocks(title="Browser Use WebUI", theme=gr.themes.Soft(font=[gr.themes.GoogleFont("Plus Jakarta Sans")])) as demo:
        gr.Markdown("<center><h1>Browser Use WebUI</h1></center>")
        
        with gr.Tabs():
            # Tab for LLM Settings
            with gr.Tab("LLM Settings"):
                with gr.Row():
                    llm_provider = gr.Dropdown(
                        ["anthropic", "openai", "gemini", "azure_openai", "deepseek"], label="LLM Provider", value="gemini"
                    )
                    llm_model_name = gr.Textbox(label="LLM Model Name", value="gemini-2.0-flash-exp")
                    llm_temperature = gr.Number(label="LLM Temperature", value=1.0)
                with gr.Row():
                    llm_base_url = gr.Textbox(label="LLM Base URL")
                    llm_api_key = gr.Textbox(label="LLM API Key", type="password")
            
            # Tab for Browser Settings
            with gr.Tab("Browser Settings"):
                with gr.Accordion("Browser Settings", open=True):
                    use_own_browser = gr.Checkbox(label="Use Own Browser", value=False)
                    headless = gr.Checkbox(label="Headless", value=False)
                    disable_security = gr.Checkbox(label="Disable Security", value=True)
                    with gr.Row():
                        window_w = gr.Number(label="Window Width", value=1920)
                        window_h = gr.Number(label="Window Height", value=1080)
                    save_recording_path = gr.Textbox(label="Save Recording Path", placeholder="e.g. ./tmp/record_videos",
                                                     value="./tmp/record_videos")
            
            # Tab for Task Settings
            with gr.Tab("Task Settings"):
                with gr.Accordion("Task Settings", open=True):
                    task = gr.Textbox(label="Task", lines=10,
                                      value="go to google.com and type 'OpenAI' click search and give me the first url")
                    add_infos = gr.Textbox(label="Additional Infos (Optional): Hints to help LLM complete Task", lines=5)
                    agent_type = gr.Radio(["org", "custom"], label="Agent Type", value="custom")
                    max_steps = gr.Number(label="Max Run Steps", value=100)
                    use_vision = gr.Checkbox(label="Use Vision", value=True)
            
            # Tab for Stream + File Download and Agent Thoughts
            with gr.Tab("Results"):
                with gr.Column():
                    # Add live stream viewer before other components
                    browser_view = gr.HTML(
                        label="Live Browser View",
                        value="<div style='width:100%; height:600px; border:1px solid #ccc; display:flex; align-items:center; justify-content:center;'><p>Waiting for browser session...</p></div>"
                    )
                    final_result_output = gr.Textbox(label="Final Result", lines=5)
                    errors_output = gr.Textbox(label="Errors", lines=5)
                    model_actions_output = gr.Textbox(label="Model Actions", lines=5)
                    model_thoughts_output = gr.Textbox(label="Model Thoughts", lines=5)
                    with gr.Row():
                        recording_file = gr.Video(label="Recording File")  # Changed from gr.File to gr.Video
                        trace_file = gr.File(label="Trace File (ZIP)")
                    
                    # Add a refresh button
                    refresh_button = gr.Button("Refresh Files")
                    
                    def refresh_files():
                        recorded_files = get_latest_files("./tmp/record_videos")
                        trace_file = get_latest_files("./tmp/traces")
                        return (
                            recorded_files.get('.webm') if recorded_files.get('.webm') else None,
                            trace_file.get('.zip') if trace_file.get('.zip') else None
                        )
                    
                    refresh_button.click(
                        fn=refresh_files,
                        inputs=[],
                        outputs=[recording_file, trace_file]
                    )
        
        # Run button outside tabs for global execution
        run_button = gr.Button("Run Agent", variant="primary")
        run_button.click(
            fn=run_with_stream,
            inputs=[
                agent_type, llm_provider, llm_model_name, llm_temperature,
                llm_base_url, llm_api_key, use_own_browser, headless,
                disable_security, window_w, window_h, save_recording_path,
                task, add_infos, max_steps, use_vision
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
            queue=True
        )

    demo.launch(server_name=args.ip, server_port=args.port, share=True)

if __name__ == "__main__":

    # For local development
    import argparse
    parser = argparse.ArgumentParser(description="Gradio UI for Browser Agent")
    parser.add_argument("--ip", type=str, default="0.0.0.0", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=7860, help="Port to listen on")
    args = parser.parse_args()
    main()
else:
    # For Vercel deployment
    main()
