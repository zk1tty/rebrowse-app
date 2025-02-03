
import pdb

from dotenv import load_dotenv

load_dotenv()
import asyncio
import os
import sys
from pprint import pprint
from uuid import uuid4
from src.utils import utils
from src.agent.custom_agent import CustomAgent
import json
from browser_use.agent.service import Agent
from browser_use.browser.browser import BrowserConfig, Browser
from langchain.schema import SystemMessage, HumanMessage
from json_repair import repair_json
from src.agent.custom_prompts import CustomSystemPrompt, CustomAgentMessagePrompt


async def deep_research(task, llm, **kwargs):
    
    save_dir = kwargs.get("save_dir", os.path.join(f"./tmp/deep_research/{task_id}"))
    os.makedirs(save_dir, exist_ok=True)

    # 搜索的信息
    search_infos = ""
    # 搜索的LLM历史信息
    max_query_num = 3
    search_system_prompt = f"""
    You are an expert task planner for an AI agent that uses a web browser with **automated execution capabilities**. Your goal is to analyze user instructions and, based on available information, 
    determine what further search queries are necessary to fulfill the user's request. You will output a JSON object with the following structure:

    [
        "search query 1",
        "search query 2",
        //... up to a maximum of {max_query_num} search queries
    ]
    ```

    Here's an example of the type of `search` tasks we are expecting:
    [
        "weather in Tokyo",
        "cheap flights to Paris"
    ]
    ```

    **Important:**

    *   Your output should *only* include search queries as strings in a JSON array. Do not include other task types like navigate, click, extract, etc.
    *   Limit your output to a **maximum of {max_query_num}** search queries.
    *   Make the search queries to help the automated agent find the needed information. Consider what keywords are most likely to lead to useful results.
    *   If you have gathered for all the information you want and no further search queries are required, output an empty list: `[]`
    *   Make sure your search queries are different from the previous queries.

    **Inputs:**

    1.  **User Instruction:** The original instruction given by the user.
    2.  **Previous Search Results:** Textual data gathered from prior search queries. If there are no previous search results this string will be empty.
    """
    search_messages = [SystemMessage(content=search_system_prompt)]
    # 记录和总结的历史信息，保存到raw_infos
    record_system_prompt = """
    You are an expert information recorder. Your role is to process user instructions, current search results, and previously recorded information to extract, summarize, and record new, useful information that helps fulfill the user's request. Your output will be a concise textual summary of new information.

    **Important Considerations:**

    1.  **Avoid Redundancy:** Do not record information that is already present in the `Previous Recorded Information`. Check for semantic similarity, not just exact matches.

    2.  **Utility Focus:** Only record information that is likely to be useful for completing the user's original instruction. Ask yourself: "Will this help the AI agent achieve its goal?" Discard irrelevant details.

    3.  **Include Source Information:** When summarizing information extracted from a specific source (like a webpage or article), always include the source title and URL if available. This helps in verifying the information and providing context.

    4.  **Format:** Provide your output as a textual summary. When source information is available, use the format: `[title](url): summarized content`. If no specific source is identified, just provide the concise summary. No JSON or other structured output is needed beyond this format.

    **Inputs:**

    1.  **User Instruction:** The original instruction given by the user. This helps you determine what kind of information will be useful.
    2.  **Current Search Results:** Textual data gathered from the most recent search query.
    3.  **Previous Recorded Information:** Textual data gathered and recorded from previous searches and processing, represented as a single text string. This string might be empty if no information has been recorded yet.
    """
    record_messages = [SystemMessage(content=record_system_prompt)]

    browser = Browser(
        config=BrowserConfig(
            disable_security=True,
            headless=False, # Set to False to see browser actions
        )
    )
    search_iteration = 0
    max_search_iterations = 5 # Limit search iterations to prevent infinite loop
    max_history_len = 2
    use_vision = True

    try:
        while search_iteration < max_search_iterations:
            search_iteration += 1
            print(f"开始第 {search_iteration} 轮搜索...")

            query_prompt = f"User Instruction:{task} \n Previous Search Results:\n {search_infos}"
            search_messages.append(HumanMessage(content=query_prompt))
            ai_query_msg = llm.invoke(search_messages[:1] + search_messages[1:][-max_history_len:])
            if hasattr(ai_query_msg, "reasoning_content"):
                print("🤯 Start Search Deep Thinking: ")
                print(ai_query_msg.reasoning_content)
                print("🤯 End Search Deep Thinking")
            ai_content = ai_query_msg.content.replace("```json", "").replace("```", "")
            ai_content = repair_json(ai_content)
            query_tasks = json.loads(ai_content)
            if not query_tasks:
                break
            else:
                search_messages.append(ai_query_msg)
            print(f"搜索关键词/问题: {query_tasks}")

            # 2. Perform Web Search and Auto exec
            agents = [CustomAgent(task=task + ". Please click on the most relevant link to get information and go deeper, instead of just staying on the search page.", 
                                  llm=llm_bu, 
                                  browser=browser, 
                                  use_vision=use_vision,
                                  system_prompt_class=CustomSystemPrompt,
                                  agent_prompt_class=CustomAgentMessagePrompt,
                                  max_actions_per_step=5
                                  ) for task in query_tasks]
            query_results = await asyncio.gather(*[agent.run(max_steps=10) for agent in agents])
            
            # 3. Summarize Search Result
            cur_search_rets = ""
            for i in range(len(query_tasks)):
                cur_search_rets += f"{i+1}. {query_tasks[i]}\n {query_results[i].final_result()}\n"
            record_prompt = f"User Instruction:{task}. \n Current Search Results: {cur_search_rets}\n Previous Search Results:\n {search_infos}"
            record_messages.append(HumanMessage(content=record_prompt))
            ai_record_msg = llm.invoke(record_messages[:1] + record_messages[-1:])
            if hasattr(ai_record_msg, "reasoning_content"):
                print("🤯 Start Record Deep Thinking: ")
                print(ai_record_msg.reasoning_content)
                print("🤯 End Record Deep Thinking")
            record_content = ai_record_msg.content
            search_infos += record_content + "\n"
            record_messages.append(ai_record_msg)
            print(search_infos)

        print("\n搜索完成, 开始生成报告...")

        # 5. Report Generation in Markdown (or JSON if you prefer)
        writer_system_prompt = """
        create polished, high-quality reports that fully meet the user's needs, based on the user's instructions and the relevant information provided.  Please write the report using Markdown format, ensuring it is both informative and visually appealing.

Specific Instructions:
*   **Structure for Impact:** The report must have a clear, logical, and impactful structure. Begin with a compelling introduction that immediately grabs the reader's attention. Develop well-structured body paragraphs that flow smoothly and logically, and conclude with a concise and memorable conclusion that summarizes key takeaways and leaves a lasting impression.
*   **Engaging and Vivid Language:** Employ precise, vivid, and descriptive language to make the report captivating and enjoyable to read.  Use stylistic techniques to enhance engagement. Tailor your tone, vocabulary, and writing style to perfectly suit the subject matter and the intended audience to maximize impact and readability.
*   **Accuracy and Credibility:**  Ensure that all information presented is meticulously accurate, rigorously truthful, and robustly supported by the available data.  Cite sources professionally and appropriately to enhance credibility and allow for verification.
*   **Publication-Ready Formatting:** Adhere strictly to Markdown formatting for excellent readability and a clean, highly professional visual appearance. Pay close attention to formatting details like headings, lists, emphasis, and spacing to optimize the visual presentation and reader experience. The report should be ready for immediate publication upon completion, requiring minimal to no further editing for style or format.
*   **Conciseness and Clarity (Unless Specified Otherwise):** When the user does not provide a specific length, prioritize concise and to-the-point writing, maximizing information density while maintaining clarity.
*   **Length Adherence:** When the user specifies a length constraint, meticulously stay within reasonable bounds of that specification, ensuring the content is appropriately scaled without sacrificing quality or completeness.
*   **Comprehensive Instruction Following:** Pay meticulous attention to all details and nuances provided in the user instructions.  Strive to fulfill every aspect of the user's request with the highest degree of accuracy and attention to detail, creating a report that not only meets but exceeds expectations for quality and professionalism.
*   **Output Final Report Only Instruction:**  This new instruction is explicitly added at the end to directly address the user's requirement.  It clearly commands the LLM to output *only* the final article and to avoid any other elements.  The bolded emphasis further reinforces this crucial point.
        """
        report_prompt = f"User Instruction:{task} \n Search Information:\n {search_infos}"
        report_messages = [SystemMessage(content=writer_system_prompt), HumanMessage(content=report_prompt)] # New context for report generation
        ai_report_msg = llm.invoke(report_messages)
        if hasattr(ai_report_msg, "reasoning_content"):
            print("🤯 Start Report Deep Thinking: ")
            print(ai_report_msg.reasoning_content)
            print("🤯 End Report Deep Thinking")
        report_content = ai_report_msg.content

        if report_content:
            report_file_path = os.path.join(save_dir, "result.md")
            with open(report_file_path, "w", encoding="utf-8") as f:
                f.write(report_content)
            print(f"报告已生成并保存到: {report_file_path}")

            print("\nFinal Result: (Report Content)")
            pprint(report_content, indent=4) # Print the final report content

        else:
            print("未能生成报告内容。")


    except Exception as e:
        print(f"Deep research 过程中发生错误: {e}")
    finally:
        if browser:
            await browser.close()
            print("Browser closed.")